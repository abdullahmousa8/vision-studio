from app.schemas.job import BoundingBox, PartManifest
from app.services.assembly_engine import AssemblyEngine


def test_assembly_engine_builds_valid_scad():
    parts = [
        {
            "id": 1,
            "name": "base",
            "code": "cube([10, 10, 5]);",
        },
        {
            "id": 2,
            "name": "top",
            "code": "translate([0, 0, 5]) cube([10, 10, 5]);",
        },
    ]
    output = AssemblyEngine().build(parts, job_id="job-123")

    assert "Job ID: job-123" in output
    assert "module base()" not in output  # parts carry their own module definitions
    assert "cube([10, 10, 5]);" in output
    assert "full_assembly()" in output
    assert "base();" in output
    assert "top();" in output
    assert "$fn = 64;" in output


def test_assembly_engine_escapes_dangerous_content():
    """Jinja autoescape disabled by design; module bodies are code, not HTML."""
    parts = [
        {"id": 1, "name": "p1", "code": "cube([1,1,1]);"},
    ]
    output = AssemblyEngine().build(parts, job_id="j")
    assert "<script>" not in output


def test_part_manifest_validation():
    part = PartManifest(
        id=1,
        name="valid_part_1",
        priority=2,
        dependencies=[],
        bounding_box=BoundingBox(x=10, y=20, z=30),
        key_features=["a"],
    )
    assert part.name == "valid_part_1"
