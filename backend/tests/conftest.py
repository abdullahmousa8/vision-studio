import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_openscad(tmp_path, script_name, script_body):
    """Create a Python helper + a .cmd launcher (Windows cannot exec .py directly)."""
    script = tmp_path / script_name
    script.write_text(script_body, encoding="utf-8")
    launcher = tmp_path / "fake_openscad.cmd"
    launcher.write_text(
        f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n',
        encoding="utf-8",
    )
    return str(launcher)


@pytest.fixture
def fake_openscad(tmp_path):
    return _make_openscad(
        tmp_path,
        "fake_openscad.py",
        """import sys
scad_path = sys.argv[1]
output_path = None
for i, arg in enumerate(sys.argv):
    if arg == "-o" and i + 1 < len(sys.argv):
        output_path = sys.argv[i + 1]
code = open(scad_path, encoding="utf-8").read()
if "SYNTAX_ERROR" in code:
    print("ERROR: Parser error in file model.scad, line 3", file=sys.stderr)
    sys.exit(1)
if output_path:
    open(output_path, "wb").write(b"fake-stl")
sys.exit(0)
""",
    )


@pytest.fixture
def fake_openscad_timeout(tmp_path):
    return _make_openscad(
        tmp_path,
        "fake_openscad_hang.py",
        """import time
time.sleep(300)
""",
    )
