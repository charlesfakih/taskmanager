"""Keyset ("seek") pagination for the tasks list, not offset/limit.

Offset pagination degrades at scale and shifts under concurrent writes between
page requests, which is the failure mode the assignment calls out for a
project that can accumulate thousands of tasks. Each sort has one fixed
direction (rather than exposing independent asc/desc per field) since the
brief asks to sort *by* a field, not for arbitrary directionality.
"""

import base64
import binascii
import datetime as dt
import enum
import json
from typing import Any

import sqlalchemy as sa

from taskmanager.domain.enums import TaskPriority
from taskmanager.domain.errors import InvalidCursorError
from taskmanager.models import Task

CURSOR_VERSION = "task_cursor_v1"

# priority is stored as text, which sorts alphabetically ("low" > "high") --
# not by severity. Rank it explicitly so PRIORITY_DESC means "most urgent
# first", both in the ORDER BY and in the keyset predicate below.
_PRIORITY_RANK: dict[str, int] = {p.value: rank for rank, p in enumerate(TaskPriority)}
_priority_rank_expr = sa.case(
    *((Task.priority == value, rank) for value, rank in _PRIORITY_RANK.items()),
    else_=0,
)


class TaskSort(enum.StrEnum):
    CREATED_AT_DESC = "created_at_desc"  # newest first (default)
    STATUS_ASC = "status_asc"
    PRIORITY_DESC = "priority_desc"  # most urgent first
    ASSIGNEE_ASC = "assignee_asc"  # unassigned tasks sort last


def sort_cursor_value(sort: TaskSort, task: Task) -> Any:
    """The value to encode in a row's cursor for a given sort."""
    if sort is TaskSort.CREATED_AT_DESC:
        return task.created_at
    if sort is TaskSort.STATUS_ASC:
        return task.status
    if sort is TaskSort.PRIORITY_DESC:
        return _PRIORITY_RANK[task.priority]
    if sort is TaskSort.ASSIGNEE_ASC:
        return task.assignee_id
    raise AssertionError(sort)


def order_by_clauses(sort: TaskSort) -> list[Any]:
    # id is a strict tiebreaker on every sort, giving keyset pagination a total order.
    if sort is TaskSort.CREATED_AT_DESC:
        return [Task.created_at.desc(), Task.id.desc()]
    if sort is TaskSort.STATUS_ASC:
        return [Task.status.asc(), Task.id.asc()]
    if sort is TaskSort.PRIORITY_DESC:
        return [_priority_rank_expr.desc(), Task.id.desc()]
    if sort is TaskSort.ASSIGNEE_ASC:
        return [Task.assignee_id.asc().nullslast(), Task.id.asc()]
    raise AssertionError(sort)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat()
    return value


def _deserialize_value(sort: TaskSort, raw: Any) -> Any:
    if sort is TaskSort.CREATED_AT_DESC:
        if raw is None:
            raise InvalidCursorError()
        return dt.datetime.fromisoformat(raw)
    return raw  # status: str; priority: int rank; assignee_id: int | None


def encode_cursor(sort: TaskSort, value: Any, task_id: int) -> str:
    payload = {"t": CURSOR_VERSION, "sort": sort.value, "v": _serialize_value(value), "id": task_id}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str, expected_sort: TaskSort) -> tuple[Any, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        payload = json.loads(raw)
        if payload.get("t") != CURSOR_VERSION or payload.get("sort") != expected_sort.value:
            raise InvalidCursorError(
                "Cursor was issued for a different sort; re-query without `after` "
                "to change sort order."
            )
        return _deserialize_value(expected_sort, payload["v"]), int(payload["id"])
    except InvalidCursorError:
        raise
    except (ValueError, TypeError, KeyError, binascii.Error, json.JSONDecodeError) as exc:
        raise InvalidCursorError() from exc


def build_keyset_predicate(sort: TaskSort, cursor_value: Any, cursor_id: int) -> Any:
    id_col = Task.id
    if sort is TaskSort.CREATED_AT_DESC:
        return sa.tuple_(Task.created_at, id_col) < sa.tuple_(cursor_value, cursor_id)
    if sort is TaskSort.STATUS_ASC:
        return sa.tuple_(Task.status, id_col) > sa.tuple_(cursor_value, cursor_id)
    if sort is TaskSort.PRIORITY_DESC:
        return sa.tuple_(_priority_rank_expr, id_col) < sa.tuple_(cursor_value, cursor_id)
    if sort is TaskSort.ASSIGNEE_ASC:
        col = Task.assignee_id
        # NULLS LAST: cursor in the non-null segment still has NULLs ahead of it;
        # cursor already NULL means we're seeking further into the NULL segment.
        if cursor_value is None:
            return sa.and_(col.is_(None), id_col > cursor_id)
        return sa.or_(
            sa.and_(col.isnot(None), sa.tuple_(col, id_col) > sa.tuple_(cursor_value, cursor_id)),
            col.is_(None),
        )
    raise AssertionError(sort)
