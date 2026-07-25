import pytest
from pydantic import ValidationError

from taskmanager.domain.enums import TaskPriority
from taskmanager.domain.schemas import CreateTaskFields, UpdateTaskFields


def test_create_task_strips_and_accepts_valid_title():
    fields = CreateTaskFields(project_id=1, title="  Ship the thing  ")
    assert fields.title == "Ship the thing"
    assert fields.priority == TaskPriority.MEDIUM  # default


def test_create_task_rejects_blank_title():
    with pytest.raises(ValidationError):
        CreateTaskFields(project_id=1, title="   ")


def test_create_task_rejects_title_over_max_length():
    with pytest.raises(ValidationError):
        CreateTaskFields(project_id=1, title="x" * 201)


def test_create_task_rejects_description_over_max_length():
    with pytest.raises(ValidationError):
        CreateTaskFields(project_id=1, title="ok", description="x" * 10_001)


def test_update_task_all_fields_optional():
    fields = UpdateTaskFields()
    assert fields.model_fields_set == set()


def test_update_task_tracks_only_explicitly_provided_fields():
    fields = UpdateTaskFields.model_validate({"title": "New title", "description": None})
    assert fields.model_fields_set == {"title", "description"}
    assert fields.title == "New title"
    assert fields.description is None
    assert "priority" not in fields.model_fields_set
    assert "due_date" not in fields.model_fields_set


def test_update_task_rejects_blank_title():
    with pytest.raises(ValidationError):
        UpdateTaskFields(title="   ")
