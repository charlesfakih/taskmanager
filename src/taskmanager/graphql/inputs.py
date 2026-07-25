import datetime as dt

import strawberry

from taskmanager.graphql.types import TaskPriorityGQL, TaskStatusGQL
from taskmanager.services.pagination import TaskSort

TaskSortGQL = strawberry.enum(TaskSort, name="TaskSort")


@strawberry.input(name="TaskFilter")
class TaskFilterInput:
    status: TaskStatusGQL | None = strawberry.field(default=None)  # type: ignore[valid-type]
    priority: TaskPriorityGQL | None = strawberry.field(default=None)  # type: ignore[valid-type]
    assignee_id: strawberry.ID | None = strawberry.field(default=None)


@strawberry.input(name="CreateTaskInput")
class CreateTaskInput:
    project_id: strawberry.ID
    title: str
    description: str | None = None
    priority: TaskPriorityGQL | None = None  # type: ignore[valid-type]
    assignee_id: strawberry.ID | None = None
    due_date: dt.date | None = None


@strawberry.input(name="UpdateTaskInput")
class UpdateTaskInput:
    expected_version: int
    # title/priority: omitted (None) means "leave unchanged" -- neither ever
    # needs to be explicitly cleared. description/due_date are genuinely
    # nullable domain fields, so they use UNSET to distinguish "not provided"
    # from "explicitly set to null" (clearing them).
    title: str | None = None
    priority: TaskPriorityGQL | None = None  # type: ignore[valid-type]
    description: str | None = strawberry.UNSET
    due_date: dt.date | None = strawberry.UNSET


@strawberry.input(name="ChangeTaskStatusInput")
class ChangeTaskStatusInput:
    status: TaskStatusGQL  # type: ignore[valid-type]
    expected_version: int


@strawberry.input(name="AssignTaskInput")
class AssignTaskInput:
    assignee_id: strawberry.ID
    expected_version: int


@strawberry.input(name="UnassignTaskInput")
class UnassignTaskInput:
    expected_version: int


@strawberry.input(name="DeleteTaskInput")
class DeleteTaskInput:
    expected_version: int
