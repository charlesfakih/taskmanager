import datetime as dt
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.db.session import session_scope
from taskmanager.domain.enums import TaskPriority, TaskStatus
from taskmanager.domain.errors import (
    ForbiddenError,
    InvalidArgumentError,
    ProjectNotFoundError,
    TaskConflictError,
    TaskNotFoundError,
    UserNotFoundError,
)
from taskmanager.models import Project, Task, User
from taskmanager.services.auth import can_delete_task
from taskmanager.services.pagination import (
    TaskSort,
    build_keyset_predicate,
    decode_cursor,
    encode_cursor,
    order_by_clauses,
    sort_cursor_value,
)


async def get_task(task_id: int) -> Task | None:
    async with session_scope() as session:
        return await session.get(Task, task_id)


@dataclass
class TaskFilter:
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None


@dataclass
class TaskPage:
    tasks: list[Task]
    cursors: list[str]
    has_next_page: bool
    total_count: int


def _filter_conditions(project_id: int, filter: TaskFilter | None) -> list:
    conditions = [Task.project_id == project_id]
    if filter is not None:
        if filter.status is not None:
            conditions.append(Task.status == filter.status.value)
        if filter.priority is not None:
            conditions.append(Task.priority == filter.priority.value)
        if filter.assignee_id is not None:
            conditions.append(Task.assignee_id == filter.assignee_id)
    return conditions


async def list_tasks(
    *,
    project_id: int,
    filter: TaskFilter | None,
    sort: TaskSort,
    first: int,
    after: str | None,
    max_page_size: int,
) -> TaskPage:
    if not (1 <= first <= max_page_size):
        raise InvalidArgumentError(f"`first` must be between 1 and {max_page_size}, got {first}")

    base_conditions = _filter_conditions(project_id, filter)
    list_conditions = list(base_conditions)
    if after is not None:
        cursor_value, cursor_id = decode_cursor(after, sort)
        list_conditions.append(build_keyset_predicate(sort, cursor_value, cursor_id))

    async with session_scope() as session:
        stmt = (
            select(Task).where(*list_conditions).order_by(*order_by_clauses(sort)).limit(first + 1)
        )
        rows = list((await session.execute(stmt)).scalars())

        has_next_page = len(rows) > first
        rows = rows[:first]

        count_stmt = select(func.count()).select_from(Task).where(*base_conditions)
        total_count = (await session.execute(count_stmt)).scalar_one()

    cursors = [encode_cursor(sort, sort_cursor_value(sort, t), t.id) for t in rows]

    return TaskPage(
        tasks=rows, cursors=cursors, has_next_page=has_next_page, total_count=total_count
    )


async def _conditional_update(
    session: AsyncSession, task_id: int, expected_version: int, values: dict
) -> Task:
    """Single write path for every mutation: UPDATE gated on `version`."""
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.version == expected_version)
        .values(**values, version=Task.version + 1, updated_at=func.now())
        .returning(Task)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row

    existing = await session.get(Task, task_id)
    if existing is None:
        raise TaskNotFoundError(task_id)
    raise TaskConflictError(task_id, expected_version)


async def create_task(
    *,
    project_id: int,
    title: str,
    description: str | None,
    priority: TaskPriority,
    assignee_id: int | None,
    due_date: dt.date | None,
    created_by_id: int,
) -> Task:
    async with session_scope() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        if assignee_id is not None and await session.get(User, assignee_id) is None:
            raise UserNotFoundError(assignee_id)

        task = Task(
            project_id=project_id,
            title=title,
            description=description,
            status=TaskStatus.TODO.value,
            priority=priority.value,
            assignee_id=assignee_id,
            created_by_id=created_by_id,
            due_date=due_date,
        )
        session.add(task)
        await session.flush()
        return task


async def update_task(*, task_id: int, fields: dict, expected_version: int) -> Task:
    """`fields` contains only the keys the caller wants to change."""
    db_values: dict = {}
    if "title" in fields:
        db_values["title"] = fields["title"]
    if "description" in fields:
        db_values["description"] = fields["description"]
    if "priority" in fields:
        db_values["priority"] = fields["priority"].value
    if "due_date" in fields:
        db_values["due_date"] = fields["due_date"]

    async with session_scope() as session:
        return await _conditional_update(session, task_id, expected_version, db_values)


async def change_task_status(*, task_id: int, status: TaskStatus, expected_version: int) -> Task:
    async with session_scope() as session:
        return await _conditional_update(
            session, task_id, expected_version, {"status": status.value}
        )


async def assign_task(*, task_id: int, assignee_id: int, expected_version: int) -> Task:
    async with session_scope() as session:
        if await session.get(User, assignee_id) is None:
            raise UserNotFoundError(assignee_id)
        return await _conditional_update(
            session, task_id, expected_version, {"assignee_id": assignee_id}
        )


async def unassign_task(*, task_id: int, expected_version: int) -> Task:
    async with session_scope() as session:
        return await _conditional_update(session, task_id, expected_version, {"assignee_id": None})


async def delete_task(*, task_id: int, expected_version: int, actor: User) -> int:
    async with session_scope() as session:
        task = await session.get(Task, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        project = await session.get(Project, task.project_id)
        assert project is not None  # FK (ON DELETE RESTRICT) guarantees this

        if not can_delete_task(actor, task, project):
            raise ForbiddenError(
                f"User {actor.id} may not delete task {task_id}: must be its creator, "
                "current assignee, or the owning project's owner"
            )

        stmt = (
            delete(Task)
            .where(Task.id == task_id, Task.version == expected_version)
            .returning(Task.id)
        )
        deleted_id = (await session.execute(stmt)).scalar_one_or_none()
        if deleted_id is None:
            # Modified or deleted by someone else between our read and the delete.
            if await session.get(Task, task_id) is None:
                raise TaskNotFoundError(task_id)
            raise TaskConflictError(task_id, expected_version)
        return deleted_id
