import os
import shutil
import subprocess
import tempfile

from app.core.logging import get_logger
from app.core.minio_client import minio_client

logger = get_logger("export_engine")


class ExportEngineError(Exception):
    pass


class ExportEngine:
    """Renders assembly SCAD files to STL meshes and PNG previews via OpenSCAD CLI."""

    def __init__(self, binary: str = None, stl_timeout: int = 120, preview_timeout: int = 60):
        self.binary = binary or shutil.which("openscad")
        self.stl_timeout = stl_timeout
        self.preview_timeout = preview_timeout

    def _fetch(self, object_name: str) -> str:
        response = minio_client.get_object("artifacts", object_name)
        return response.read().decode("utf-8")

    def _write_scad(self, code: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".scad")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        return path

    def _run(self, args: list, timeout: int) -> subprocess.CompletedProcess:
        if not self.binary:
            raise ExportEngineError("OpenSCAD CLI not found")
        try:
            return subprocess.run(
                [self.binary, *args], capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            raise ExportEngineError(f"OpenSCAD timed out after {timeout}s") from None
        except OSError as exc:
            raise ExportEngineError(f"OpenSCAD execution failed: {exc}") from exc

    def to_stl(self, scad_object_name: str, job_id: str) -> str:
        code = self._fetch(scad_object_name)
        scad_path = self._write_scad(code)
        stl_path = scad_path.replace(".scad", ".stl")
        try:
            result = self._run([scad_path, "-o", stl_path], self.stl_timeout)
            if result.returncode != 0:
                raise ExportEngineError(f"OpenSCAD STL export failed: {result.stderr[:500]}")

            stl_object = f"jobs/{job_id}/output/model.stl"
            minio_client.fput_object("artifacts", stl_object, stl_path)
            logger.info("export.stl_uploaded", job_id=job_id, object_name=stl_object)
            return stl_object
        finally:
            os.unlink(scad_path)
            if os.path.exists(stl_path):
                os.unlink(stl_path)

    def to_preview(self, scad_object_name: str, job_id: str) -> str:
        code = self._fetch(scad_object_name)
        scad_path = self._write_scad(code)
        png_path = scad_path.replace(".scad", ".png")
        try:
            result = self._run([scad_path, "-o", png_path, "--imgsize=800,600"], self.preview_timeout)
            if result.returncode != 0:
                raise ExportEngineError(f"OpenSCAD preview failed: {result.stderr[:500]}")

            png_object = f"jobs/{job_id}/output/preview.png"
            minio_client.fput_object("artifacts", png_object, png_path)
            logger.info("export.preview_uploaded", job_id=job_id, object_name=png_object)
            return png_object
        finally:
            os.unlink(scad_path)
            if os.path.exists(png_path):
                os.unlink(png_path)
