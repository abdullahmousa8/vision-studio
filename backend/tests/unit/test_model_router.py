import pytest

from app.schemas.job import DecompositionResult, PartManifest
from app.services.model_router import (
    CodeGenerator,
    LLMClientError,
    ModelRouter,
    Planner,
)

VALID_MANIFEST = {
    "task_type": "3d_model",
    "object_name": "chair",
    "complexity_score": 5.0,
    "estimated_parts": 2,
    "global_parameters": {"seat_height": 450},
    "parts": [
        {
            "id": 1,
            "name": "seat",
            "priority": 1,
            "dependencies": [],
            "bounding_box": {"x": 400, "y": 400, "z": 30},
            "key_features": ["flat top"],
        },
        {
            "id": 2,
            "name": "leg",
            "priority": 2,
            "dependencies": [1],
            "bounding_box": {"x": 40, "y": 40, "z": 400},
            "key_features": ["square"],
        },
    ],
    "assembly_order": [1, 2],
}


class FakeClient:
    provider = "ollama"

    def __init__(self, response: str):
        self.response = response

    def generate(self, model, prompt, system=None, temperature=0.2):
        return self.response


class TestPlanner:
    def test_decompose_valid_json(self):
        import json

        client = FakeClient(json.dumps(VALID_MANIFEST))
        result = Planner(client).decompose("a chair", detail_level="medium")
        assert isinstance(result, DecompositionResult)
        assert len(result.parts) == 2
        assert result.assembly_order == [1, 2]

    def test_decompose_strips_markdown_fence(self):
        import json

        fenced = f"```json\n{json.dumps(VALID_MANIFEST)}\n```"
        result = Planner(FakeClient(fenced)).decompose("a chair")
        assert result.object_name == "chair"

    def test_decompose_rejects_self_dependency(self):
        import json

        bad = json.loads(json.dumps(VALID_MANIFEST))
        bad["parts"][0]["dependencies"] = [1]
        client = FakeClient(json.dumps(bad))
        with pytest.raises(LLMClientError):
            Planner(client).decompose("a chair")

    def test_decompose_rejects_bad_assembly_order(self):
        import json

        bad = json.loads(json.dumps(VALID_MANIFEST))
        bad["assembly_order"] = [99]
        client = FakeClient(json.dumps(bad))
        with pytest.raises(LLMClientError):
            Planner(client).decompose("a chair")

    def test_parse_json_raw_text(self):
        payload = (
            'some text {"object_name": "x", "complexity_score": 1, '
            '"estimated_parts": 1, "global_parameters": {}, '
            '"parts": [], "assembly_order": []} trailing'
        )
        parsed = Planner._parse_json(payload)
        assert parsed["object_name"] == "x"


class TestCodeGenerator:
    def test_generates_code(self):
        part = PartManifest.model_validate(VALID_MANIFEST["parts"][0])
        generator = CodeGenerator(FakeClient("cube([1,1,1]);"))
        code = generator.generate(part, object_name="chair")
        assert code == "cube([1,1,1]);"

    def test_clean_code_strips_fences(self):
        raw = "```openscad\nmodule seat() { cube([1,1,1]); }\n```"
        assert CodeGenerator._clean_code(raw) == "module seat() { cube([1,1,1]); }"

    def test_clean_code_drops_leading_prose(self):
        raw = "Here is the OpenSCAD code:\n\nmodule seat() { cube([1,1,1]); }"
        cleaned = CodeGenerator._clean_code(raw)
        assert cleaned == "module seat() { cube([1,1,1]); }"

    def test_clean_code_strips_trailing_html_garbage(self):
        raw = (
            "module base() {\n"
            "    cube([30, 30, 2]);\n"
            "}\n"
            "base();\n"
            "</module>\n</module>\n</code>\n"
        )
        cleaned = CodeGenerator._clean_code(raw)
        assert cleaned == "module base() {\n    cube([30, 30, 2]);\n}\nbase();"

    def test_clean_code_handles_none(self):
        assert CodeGenerator._clean_code(None) == ""
        assert CodeGenerator._clean_code("   ") == ""

    def test_client_candidates_auto_prefers_local_then_remote(self):
        candidates = ModelRouter.client_candidates("auto", "coding")
        providers = [type(client).__name__ for client, _ in candidates]
        assert providers[0] == "OllamaClient"
        assert "OpenRouterClient" in providers

    def test_client_candidates_remote_prefers_remote_then_local(self):
        candidates = ModelRouter.client_candidates("remote", "coding")
        providers = [type(client).__name__ for client, _ in candidates]
        assert providers[0] == "OpenRouterClient"
        assert candidates[0][1] == "poolside/laguna-s-2.1:free"
        assert "OllamaClient" in providers


class TestModelRouter:
    def test_select_local_by_default(self):
        client = ModelRouter.select("local", "coding")
        from app.services.model_router import OllamaClient

        assert isinstance(client, OllamaClient)

    def test_select_remote_explicit(self):
        from app.services.model_router import OpenRouterClient

        client = ModelRouter.select("remote", "coding")
        assert isinstance(client, OpenRouterClient)

    def test_circuit_breaker_forces_remote(self, monkeypatch):
        import time

        from app.services.model_router import OpenRouterClient

        monkeypatch.setattr(time, "time", lambda: 10_000)
        ModelRouter._circuit_open_until = 10_000 + 1
        client = ModelRouter.select("auto", "coding")
        assert isinstance(client, OpenRouterClient)

    def test_fallback_chain(self):
        assert ModelRouter.model_for("planning") == "qwen2.5-coder:3b"
        assert ModelRouter.model_for("coding") == "qwen2.5-coder:3b"

    def test_remote_models(self):
        assert ModelRouter.model_for("planning", remote=True) == "openai/gpt-oss-20b:free"
        assert ModelRouter.model_for("coding", remote=True) == "poolside/laguna-s-2.1:free"
