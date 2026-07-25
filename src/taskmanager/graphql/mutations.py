import strawberry
from pydantic import ValidationError as PydanticValidationError

from taskmanager.domain.errors import (
    ForbiddenError,
    ProjectNotFoundError,
    TaskConflictError,
    TaskNotFoundError,
    UserNotFoundError,
)
from taskmanager.domain.schemas import ChangeStatusFields, CreateTaskFields, UpdateTaskFields
from taskmanager.graphql.context import Context
from taskmanager.graphql.guards import require_authenticated
from taskmanager.graphql.inputs import (
    AssignTaskInput,
    ChangeTaskStatusInput,
    CreateTaskInput,
    DeleteTaskInput,
    UnassignTaskInput,
    UpdateTaskInput,
)
from taskmanager.graphql.mutation_types import (
    AssignTaskResult,
    ChangeTaskStatusResult,
    CreateTaskResult,
    DeleteTaskResult,
    DeleteTaskSuccessType,
    FieldErrorType,
    ForbiddenErrorType,
    ProjectNotFoundErrorType,
    TaskConflictErrorType,
    TaskNotFoundErrorType,
    UnassignTaskResult,
    UpdateTaskResult,
    UserNotFoundErrorType,
    ValidationErrorType,
)
from taskmanager.graphql.types import TaskType
from taskmanager.services import tasks as tasks_service


def _validation_error(exc: PydanticValidationError) -> ValidationErrorType:
    return ValidationErrorType(
        errors=[
            FieldErrorType(field=".".join(str(p) for p in e["loc"]), message=e["msg"])
            for e in exc.errors()
        ]
    )


async def _conflict(exc: TaskConflictError) -> TaskConflictErrorType:
    current = await tasks_service.get_task(exc.task_id)
    assert current is not None  # it exists -- that's *why* this is a conflict, not a 404
    return TaskConflictErrorType(message=str(exc), current_task=TaskType.from_model(current))


def _not_found(exc: TaskNotFoundError) -> TaskNotFoundErrorType:
    return TaskNotFoundErrorType(message=str(exc), task_id=strawberry.ID(str(exc.task_id)))


@strawberry.type
class Mutation:
    @strawberry.mutation(description="Create a task in a project.")
    async def create_task(
        self, info: strawberry.Info[Context, None], input: CreateTaskInput
    ) -> CreateTaskResult:
        user = require_authenticated(info)

        payload = {
            "project_id": int(input.project_id),
            "title": input.title,
            "description": input.description,
            "assignee_id": int(input.assignee_id) if input.assignee_id is not None else None,
            "due_date": input.due_date,
        }
        if input.priority is not None:
            payload["priority"] = input.priority
        try:
            fields = CreateTaskFields.model_validate(payload)
        except PydanticValidationError as exc:
            return _validation_error(exc)

        try:
            task = await tasks_service.create_task(
                project_id=fields.project_id,
                title=fields.title,
                description=fields.description,
                priority=fields.priority,
                assignee_id=fields.assignee_id,
                due_date=fields.due_date,
                created_by_id=user.id,
            )
        except ProjectNotFoundError as exc:
            return ProjectNotFoundErrorType(
                message=str(exc), project_id=strawberry.ID(str(exc.project_id))
            )
        except UserNotFoundError as exc:
            return UserNotFoundErrorType(message=str(exc), user_id=strawberry.ID(str(exc.user_id)))

        return TaskType.from_model(task)

    @strawberry.mutation(description="Update a task's editable fields.")
    async def update_task(
        self, info: strawberry.Info[Context, None], id: strawberry.ID, input: UpdateTaskInput
    ) -> UpdateTaskResult:
        require_authenticated(info)

        provided: dict = {}
        if input.title is not None:
            provided["title"] = input.title
        if input.priority is not None:
            provided["priority"] = input.priority
        if input.description is not strawberry.UNSET:
            provided["description"] = input.description
        if input.due_date is not strawberry.UNSET:
            provided["due_date"] = input.due_date

        try:
            validated = UpdateTaskFields.model_validate(provided)
        except PydanticValidationError as exc:
            return _validation_error(exc)

        fields = {f: getattr(validated, f) for f in validated.model_fields_set}

        try:
            task = await tasks_service.update_task(
                task_id=int(id), fields=fields, expected_version=input.expected_version
            )
        except TaskNotFoundError as exc:
            return _not_found(exc)
        except TaskConflictError as exc:
            return await _conflict(exc)

        return TaskType.from_model(task)

    @strawberry.mutation(description="Change a task's status.")
    async def change_task_status(
        self, info: strawberry.Info[Context, None], id: strawberry.ID, input: ChangeTaskStatusInput
    ) -> ChangeTaskStatusResult:
        require_authenticated(info)
        fields = ChangeStatusFields.model_validate({"status": input.status})

        try:
            task = await tasks_service.change_task_status(
                task_id=int(id), status=fields.status, expected_version=input.expected_version
            )
        except TaskNotFoundError as exc:
            return _not_found(exc)
        except TaskConflictError as exc:
            return await _conflict(exc)

        return TaskType.from_model(task)

    @strawberry.mutation(description="Assign a task to a user.")
    async def assign_task(
        self, info: strawberry.Info[Context, None], id: strawberry.ID, input: AssignTaskInput
    ) -> AssignTaskResult:
        require_authenticated(info)
        try:
            task = await tasks_service.assign_task(
                task_id=int(id),
                assignee_id=int(input.assignee_id),
                expected_version=input.expected_version,
            )
        except TaskNotFoundError as exc:
            return _not_found(exc)
        except UserNotFoundError as exc:
            return UserNotFoundErrorType(message=str(exc), user_id=strawberry.ID(str(exc.user_id)))
        except TaskConflictError as exc:
            return await _conflict(exc)

        return TaskType.from_model(task)

    @strawberry.mutation(description="Unassign a task (clears its assignee).")
    async def unassign_task(
        self, info: strawberry.Info[Context, None], id: strawberry.ID, input: UnassignTaskInput
    ) -> UnassignTaskResult:
        require_authenticated(info)
        try:
            task = await tasks_service.unassign_task(
                task_id=int(id), expected_version=input.expected_version
            )
        except TaskNotFoundError as exc:
            return _not_found(exc)
        except TaskConflictError as exc:
            return await _conflict(exc)

        return TaskType.from_model(task)

    @strawberry.mutation(
        description="Delete a task. Only its creator, current assignee, or the "
        "owning project's owner may do this."
    )
    async def delete_task(
        self, info: strawberry.Info[Context, None], id: strawberry.ID, input: DeleteTaskInput
    ) -> DeleteTaskResult:
        user = require_authenticated(info)
        try:
            deleted_id = await tasks_service.delete_task(
                task_id=int(id), expected_version=input.expected_version, actor=user
            )
        except TaskNotFoundError as exc:
            return _not_found(exc)
        except ForbiddenError as exc:
            return ForbiddenErrorType(message=str(exc))
        except TaskConflictError as exc:
            return await _conflict(exc)

        return DeleteTaskSuccessType(id=strawberry.ID(str(deleted_id)))
