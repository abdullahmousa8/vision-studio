from __future__ import annotations

import functools
import json
import os
import subprocess
import time
from typing import Literal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import api_calls_total, api_latency
from app.schemas.job import DecompositionResult, PartManifest

logger = get_logger("model_router")


class LLMClientError(Exception):
    pass


class CircuitOpenError(LLMClientError):
    pass


def _record_llm_call(func):
    """Record provider/model latency + call outcome, and drive the circuit breaker.

    Decorated ABOVE @retry so one logical LLM call (including its retries) is
    recorded as a single sample.
    """

    @functools.wraps(func)
    def wrapper(self, model, *args, **kwargs):
        start = time.perf_counter()
        status = "error"
        try:
            result = func(self, model, *args, **kwargs)
            status = "ok"
            ModelRouter.record_success(self.provider)
            return result
        except Exception:
            ModelRouter.record_failure(self.provider)
            raise
        finally:
            api_calls_total.labels(provider=self.provider, model=model, status=status).inc()
            api_latency.labels(provider=self.provider, model=model).observe(time.perf_counter() - start)

    return wrapper


class BaseModelClient:
    provider = "base"

    def generate(self, model: str, prompt: str, system: str = None, temperature: float = 0.2) -> str:
        raise NotImplementedError


class OllamaClient(BaseModelClient):
    """Ollama client with exponential-backoff retry for transient failures."""

    provider = "ollama"

    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.ollama_base_url

    @_record_llm_call
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        retry=lambda e: isinstance(e, (httpx.TimeoutException, httpx.ConnectError)),
    )
    def generate(self, model: str, prompt: str, system: str = None, temperature: float = 0.2) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 8192},
        }
        if system:
            payload["system"] = system

        response = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["response"]


class OpenRouterClient(BaseModelClient):
    """OpenRouter client with rate-limit (429) retry handling."""

    provider = "openrouter"

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_url

    @_record_llm_call
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429,
    )
    def generate(self, model: str, prompt: str, system: str = None, temperature: float = 0.2) -> str:
        if not self.api_key:
            raise LLMClientError("OPENROUTER_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:3000"),
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class GrokClient(BaseModelClient):
    """xAI (GROK) client. Uses the OpenAI-compatible /chat/completions endpoint."""

    provider = "grok"

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or settings.grok_api_key
        self.base_url = base_url or settings.grok_url

    @_record_llm_call
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429,
    )
    def generate(self, model: str, prompt: str, system: str = None, temperature: float = 0.2) -> str:
        if not self.api_key:
            raise LLMClientError("GROK_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class ModelRouter:
    """
    Routes model selection between local Ollama and remote OpenRouter.
    Applies a simple circuit breaker: after N consecutive failures the local
    path is skipped and requests go straight to the remote fallback.
    """

    VRAM_MAP = {
        "qwen2.5-coder:3b": 1900,
        "qwen2.5-coder:latest": 5200,
        "gemma4:latest": 5000,
        "gameover:latest": 5000,
        "deepseek-r1:8b": 6500,
        "phi4-mini": 3200,
    }

    FALLBACKS = {
        "planning": ["qwen2.5-coder:3b", "qwen2.5-coder:latest", "gemma4:latest"],
        "coding": ["qwen2.5-coder:3b", "qwen2.5-coder:latest", "gemma4:latest"],
    }

    # Remote models (OpenRouter) - free tiers so the pipeline runs at no cost.
    # "planning" needs reliable structured-JSON output, "coding" needs strong
    # code generation for OpenSCAD.
    REMOTE_MODELS = {
        "planning": "openai/gpt-oss-20b:free",
        "coding": "poolside/laguna-s-2.1:free",
    }

    # Extra free remote coding models tried (in order) when the primary model
    # produces invalid OpenSCAD. Free tiers are flaky, so retry with fallbacks.
    REMOTE_CODING_FALLBACKS = [
        "cohere/north-mini-code:free",
        "openai/gpt-oss-20b:free",
    ]

    GROK_MODELS = {
        "planning": "grok-3",
        "coding": "grok-code-fast-1",
    }

    _loaded_model: str | None = None
    _failures = 0
    _threshold = 5
    _circuit_open_until = 0.0
    _cooldown_seconds = 120.0

    @classmethod
    def select(
        cls, source: Literal["local", "remote", "auto"], task_type: str
    ) -> BaseModelClient:
        """Return the preferred client for the given source and task.

        - "local"  -> always Ollama.
        - "remote" -> OpenRouter (Grok when no OpenRouter key is configured).
        - "auto"   -> always Ollama first (fast and free); a remote provider is
                      used only while the local circuit breaker is open.
        """
        if source == "local":
            return OllamaClient()
        if source == "remote":
            if settings.openrouter_api_key:
                return OpenRouterClient()
            if settings.grok_api_key:
                logger.warning("model_router.grok_selected", task_type=task_type)
                return GrokClient()
            logger.warning("model_router.no_remote_key", task_type=task_type)
            return OllamaClient()
        # auto: prefer local Ollama for speed/cost; remote only on local outage.
        if cls._circuit_open_until > time.time():
            if settings.openrouter_api_key:
                return OpenRouterClient()
            if settings.grok_api_key:
                logger.warning("model_router.remote_forced", source=source, task_type=task_type)
                return GrokClient()
        return OllamaClient()

    @classmethod
    def record_success(cls, provider: str) -> None:
        cls._failures = 0

    @classmethod
    def record_failure(cls, provider: str) -> None:
        cls._failures += 1
        if cls._failures >= cls._threshold:
            cls._circuit_open_until = time.time() + cls._cooldown_seconds
            logger.error("model_router.circuit_open", failures=cls._failures)

    @classmethod
    def model_for(cls, task_type: str, remote: bool = False) -> str:
        if remote:
            return cls.REMOTE_MODELS.get(task_type, cls.REMOTE_MODELS["coding"])
        chain = cls.FALLBACKS.get(task_type, cls.FALLBACKS["coding"])
        return chain[0]

    @classmethod
    def client_candidates(
        cls, source: Literal["local", "remote", "auto"], task_type: str
    ) -> list[tuple[BaseModelClient, str]]:
        """Ordered (client, model) pairs to try, primary first.

        - "local"  -> Ollama only.
        - "remote" -> remote provider (OpenRouter, or Grok) first, Ollama last.
        - "auto"   -> Ollama first (fast, local), remote only as a fallback so
                      a part never blocks forever when local output is invalid.
        """
        local_tail = [(OllamaClient(), m) for m in cls.FALLBACKS.get(task_type, cls.FALLBACKS["coding"])]

        def _remote_head() -> list[tuple[BaseModelClient, str]]:
            if settings.openrouter_api_key:
                models = [cls.REMOTE_MODELS.get(task_type, cls.REMOTE_MODELS["coding"])]
                if task_type == "coding":
                    models += cls.REMOTE_CODING_FALLBACKS
                return [(OpenRouterClient(), m) for m in models]
            if settings.grok_api_key:
                model = cls.GROK_MODELS.get(task_type, cls.GROK_MODELS["coding"])
                return [(GrokClient(), model)]
            return []

        if source == "local":
            return local_tail
        if source == "remote":
            return _remote_head() + local_tail
        # auto: local Ollama first, remote as fallback.
        return local_tail + _remote_head()

    @classmethod
    def vram_free_mb(cls) -> int | None:
        """Return free VRAM in MB via nvidia-smi, or None when unavailable."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return int(result.stdout.strip().split("\n")[0])
        except Exception:
            return None

    @classmethod
    def fits_in_vram(cls, model_name: str) -> bool:
        free = cls.vram_free_mb()
        if free is None:
            return True  # cannot measure -> assume yes (CPU fallback handled by Ollama)
        return free >= cls.VRAM_MAP.get(model_name, 5000)

    @classmethod
    def load_model(cls, model_name: str) -> None:
        """Preload a model into Ollama memory (keep_alive window)."""
        if cls._loaded_model == model_name:
            return
        client = OllamaClient()
        try:
            client.generate(model_name, "", temperature=0.0)
            cls._loaded_model = model_name
            logger.info("ollama.model_loaded", model=model_name)
        except Exception as exc:
            logger.warning("ollama.model_load_failed", model=model_name, error=str(exc))


class Planner:
    """Turns a free-form prompt into a validated PartManifest via the LLM."""

    SYSTEM_PROMPT = (
        "You are a mechanical engineering assistant that decomposes a 3D printable "
        "object into an assembly of simple, manufacturable parts. You respond ONLY "
        "with a single valid JSON object, never with markdown or prose.\n\n"
        "Schema:\n"
        '{"object_name": string, "complexity_score": number 1-10, '
        '"estimated_parts": int 1-50, "global_parameters": {string: number}, '
        '"parts": [{"id": int, "name": "lowercase_snake_case", "priority": int 1-10, '
        '"dependencies": [int], "bounding_box": {"x","y","z": number>0}, '
        '"key_features": [string]}], "assembly_order": [int]}\n\n'
        "Part names must match ^[a-z_][a-z0-9_]*$ and every id in dependencies and "
        "assembly_order must reference an existing part. Keep dimensions in mm."
    )

    def __init__(self, client: BaseModelClient):
        self.client = client

    def decompose(self, prompt: str, detail_level: str = "medium") -> DecompositionResult:
        part_budget = {"low": 2, "medium": 4, "high": 8}[detail_level]
        user_prompt = (
            f"Decompose the following object into at most {part_budget} parts:\n\n{prompt}"
        )

        model = ModelRouter.model_for("planning", remote=self.client.provider != "ollama")
        last_error: str | None = None
        # Self-heal loop: local 3B models occasionally emit malformed JSON, so on
        # a parse/validation failure we re-prompt the model to fix its own output
        # instead of failing the whole job on the first attempt.
        for _attempt in range(3):
            raw = self.client.generate(model=model, prompt=user_prompt, system=self.SYSTEM_PROMPT, temperature=0.1)
            try:
                data = self._parse_json(raw)
                result = DecompositionResult.model_validate(data)
                if 1 <= result.estimated_parts <= 50:
                    return result
                last_error = f"Unsupported part count: {result.estimated_parts}"
            except Exception as exc:
                last_error = str(exc)
            user_prompt = (
                f"Your previous answer was not valid JSON: {last_error}\n\n"
                f"Fix it and respond with ONLY a single valid JSON manifest for:\n\n{prompt}"
            )
        raise LLMClientError(f"Invalid decomposition output after retries: {last_error}")

    @staticmethod
    def _parse_json(raw: str) -> dict:
        text = (raw or "").strip()
        if not text:
            raise LLMClientError("Empty LLM response, expected a JSON manifest")
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise


class CodeGenerator:
    """Generates OpenSCAD source for a single part."""

    SYSTEM_PROMPT = (
        "You are an expert OpenSCAD developer. Write ONLY raw OpenSCAD code with no "
        "markdown fences and no explanatory prose. Define a module named after the part "
        "with no parameters. Use mm units. Prefer primitive operations "
        "(cube, cylinder, sphere, translate, rotate, difference, union, linear_extrude). "
        "Every statement ends with a semicolon."
    )

    def __init__(self, client: BaseModelClient):
        self.client = client

    def generate(self, part: PartManifest, object_name: str = "", model: str | None = None) -> str:
        feature_list = ", ".join(part.key_features) or "none"
        bbox = part.bounding_box
        user_prompt = (
            f"Write OpenSCAD code for the part named '{part.name}' of '{object_name}'.\n"
            f"Bounding box approx: {bbox.x} x {bbox.y} x {bbox.z} mm.\n"
            f"Key features: {feature_list}.\n"
            f"Manufacturing hint: {part.manufacturing_hint or 'none'}.\n\n"
            f"module {part.name}() {{ ... }}"
        )
        if model is None:
            model = ModelRouter.model_for("coding", remote=self.client.provider != "ollama")
        code = self.client.generate(model=model, prompt=user_prompt, system=self.SYSTEM_PROMPT, temperature=0.2)
        return self._clean_code(code)

    _SCAD_START_KEYWORDS = frozenset(
        {
            "cube", "sphere", "cylinder", "translate", "rotate", "union",
            "difference", "intersection", "scale", "linear_extrude", "circle",
            "square", "polyhedron", "polygon", "import", "include", "use",
            "minkowski", "hull", "offset", "mirror", "resize", "color", "for",
        }
    )

    @staticmethod
    def _clean_code(raw: str) -> str:
        """Strip markdown fences, leading prose and trailing HTML garbage."""
        text = (raw or "").strip()
        if not text:
            return ""
        lines = text.splitlines()
        # Drop a leading code fence (```openscad / ```) and the trailing one.
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
        # Skip leading prose: OpenSCAD source starts with a keyword/module or
        # a comment or an empty line; cut at the first line that is not prose.
        code_start = 0
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "/*")):
                continue
            first = stripped.split(" ", 1)[0].rstrip("();{}")
            if stripped.startswith("module ") or first in CodeGenerator._SCAD_START_KEYWORDS:
                code_start = idx
                break
        lines = lines[code_start:]
        # Cut at the first HTML/XML closing tag (e.g. hallucinated </module>
        # or </code> runs appended by the model). OpenSCAD never contains such.
        cut = len(lines)
        for idx, line in enumerate(lines):
            if line.lstrip().startswith("</"):
                cut = idx
                break
        return "\n".join(lines[:cut]).strip()
