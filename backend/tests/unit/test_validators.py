import shutil

from app.services.validators import OpenSCADValidator


class TestOpenSCADValidator:
    def test_valid_cube(self, fake_openscad):
        code = "cube([10, 10, 10]);"
        result = OpenSCADValidator(binary=fake_openscad).check_syntax(code)
        assert result.valid is True
        assert result.error is None

    def test_syntax_error(self, fake_openscad):
        code = "cube([10, 10, 10]);\nSYNTAX_ERROR"
        result = OpenSCADValidator(binary=fake_openscad).check_syntax(code)
        assert result.valid is False
        assert result.line_number == 3
        assert result.error is not None

    def test_binary_not_found(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda _name: None)
        validator = OpenSCADValidator()
        assert validator.available is False
        result = validator.check_syntax("cube([1,1,1]);")
        assert result.valid is False
        assert "not found" in result.error

    def test_explicit_missing_binary(self):
        validator = OpenSCADValidator(binary="C:\\definitely\\missing\\openscad.exe")
        assert validator.available is True
        result = validator.check_syntax("cube([1,1,1]);")
        assert result.valid is False
        assert "execution failed" in result.error

    def test_timeout(self, monkeypatch):
        import subprocess

        def _raise_timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=[], timeout=1)

        monkeypatch.setattr(subprocess, "run", _raise_timeout)
        result = OpenSCADValidator(binary="openscad.exe").check_syntax(
            "for(i=[0:1000000]) cube([i,i,i]);"
        )
        assert result.valid is False
        assert "timeout" in result.error.lower()

    def test_line_number_extraction(self):
        assert OpenSCADValidator._extract_line_number("Parser error in line 42") == 42
        assert OpenSCADValidator._extract_line_number("no line here") is None
