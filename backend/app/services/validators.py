import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    valid: bool
    error: str | None = None
    line_number: int | None = None
    warnings: list = field(default_factory=list)


class OpenSCADValidator:
    """
    Deterministic OpenSCAD syntax validator backed by the OpenSCAD CLI.
    Validation is never delegated to an LLM -- that is critical for reliability.
    """

    def __init__(self, binary: str | None = None, timeout: int = 30):
        self.binary = binary or shutil.which("openscad")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return self.binary is not None

    def check_syntax(self, code: str) -> ValidationResult:
        """Validate OpenSCAD source code by attempting to render it."""
        if not self.available:
            return ValidationResult(valid=False, error="OpenSCAD CLI not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            scad_path = os.path.join(tmpdir, "model.scad")
            out_path = os.path.join(tmpdir, "model.stl")

            with open(scad_path, "w", encoding="utf-8") as f:
                f.write(code)

            try:
                result = subprocess.run(
                    [self.binary, scad_path, "-o", out_path],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                return ValidationResult(
                    valid=False, error=f"Validation timeout ({self.timeout}s)"
                )
            except OSError as exc:
                return ValidationResult(valid=False, error=f"OpenSCAD execution failed: {exc}")

            if result.returncode == 0:
                return ValidationResult(valid=True, warnings=[])

            stderr = result.stderr or ""
            stdout = result.stdout or ""
            error_msg = f"{stderr}\n{stdout}".strip()
            return ValidationResult(
                valid=False,
                error=error_msg or "Unknown OpenSCAD error",
                line_number=self._extract_line_number(error_msg),
                warnings=[],
            )

    @staticmethod
    def _extract_line_number(error_msg: str) -> int | None:
        match = re.search(r"line (\d+)", error_msg)
        return int(match.group(1)) if match else None
