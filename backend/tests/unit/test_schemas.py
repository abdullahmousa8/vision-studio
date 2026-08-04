import pytest
from pydantic import ValidationError

from app.schemas.job import CreateJobRequest, DecompositionResult, PartManifest


def test_create_job_request_valid():
    req = CreateJobRequest(prompt="a simple cube", mode="3d_model")
    assert req.detail_level == "medium"
    assert req.model_source == "auto"


def test_create_job_request_rejects_short_prompt():
    with pytest.raises(ValidationError):
        CreateJobRequest(prompt="cube")


def test_create_job_request_rejects_bad_mode():
    with pytest.raises(ValidationError):
        CreateJobRequest(prompt="a cube", mode="image")


def test_part_manifest_name_pattern():
    with pytest.raises(ValidationError):
        PartManifest(
            id=1,
            name="Invalid Name!",
            priority=1,
            dependencies=[],
            bounding_box={"x": 1, "y": 1, "z": 1},
        )


def test_bounding_box_positive():
    with pytest.raises(ValidationError):
        PartManifest(
            id=1,
            name="leg",
            priority=1,
            dependencies=[],
            bounding_box={"x": 0, "y": 1, "z": 1},
        )


def test_decomposition_result_roundtrip():
    data = {
        "task_type": "3d_model",
        "object_name": "box",
        "complexity_score": 2.0,
        "estimated_parts": 1,
        "global_parameters": {"wall": 2},
        "parts": [
            {
                "id": 1,
                "name": "box",
                "priority": 1,
                "dependencies": [],
                "bounding_box": {"x": 10, "y": 10, "z": 10},
            }
        ],
        "assembly_order": [1],
    }
    result = DecompositionResult.model_validate(data)
    assert result.parts[0].name == "box"
