import datetime as dt

import pytest

from taskmanager.domain.errors import InvalidCursorError
from taskmanager.services.pagination import TaskSort, decode_cursor, encode_cursor


def test_cursor_round_trip_datetime_value():
    now = dt.datetime(2026, 7, 24, 12, 30, 0, tzinfo=dt.UTC)
    cursor = encode_cursor(TaskSort.CREATED_AT_DESC, now, 42)
    value, task_id = decode_cursor(cursor, TaskSort.CREATED_AT_DESC)
    assert value == now
    assert task_id == 42


def test_cursor_round_trip_nullable_value():
    cursor = encode_cursor(TaskSort.ASSIGNEE_ASC, None, 7)
    value, task_id = decode_cursor(cursor, TaskSort.ASSIGNEE_ASC)
    assert value is None
    assert task_id == 7


def test_cursor_round_trip_string_value():
    cursor = encode_cursor(TaskSort.STATUS_ASC, "in_progress", 3)
    value, task_id = decode_cursor(cursor, TaskSort.STATUS_ASC)
    assert value == "in_progress"
    assert task_id == 3


def test_cursor_rejects_mismatched_sort():
    cursor = encode_cursor(TaskSort.CREATED_AT_DESC, dt.datetime.now(dt.UTC), 1)
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor, TaskSort.STATUS_ASC)


def test_cursor_rejects_garbage_input():
    with pytest.raises(InvalidCursorError):
        decode_cursor("not-valid-base64-json!!!", TaskSort.CREATED_AT_DESC)


def test_cursor_rejects_wrong_version_payload():
    import base64
    import json

    payload = json.dumps({"t": "old_version", "sort": "created_at_desc", "v": "x", "id": 1})
    cursor = base64.urlsafe_b64encode(payload.encode()).decode()
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor, TaskSort.CREATED_AT_DESC)
