from typing import Annotated

import strawberry

from taskmanager.graphql.types import TaskType


@strawberry.type(name="FieldError")
class FieldErrorType:
    field: str
    message: str


@strawberry.type(name="ValidationError")
class ValidationErrorType:
    errors: list[FieldErrorType]


@strawberry.type(name="TaskNotFoundError")
class TaskNotFoundErrorType:
    message: str
    task_id: strawberry.ID


@strawberry.type(name="ProjectNotFoundError")
class ProjectNotFoundErrorType:
    message: str
    project_id: strawberry.ID


@strawberry.type(name="UserNotFoundError")
class UserNotFoundErrorType:
    message: str
    user_id: strawberry.ID


@strawberry.type(name="TaskConflictError")
class TaskConflictErrorType:
    message: str
    current_task: TaskType


@strawberry.type(name="ForbiddenError")
class ForbiddenErrorType:
    message: str


@strawberry.type(name="DeleteTaskSuccess")
class DeleteTaskSuccessType:
    id: strawberry.ID


CreateTaskResult = Annotated[
    TaskType | ValidationErrorType | ProjectNotFoundErrorType | UserNotFoundErrorType,
    strawberry.union("CreateTaskResult"),
]
UpdateTaskResult = Annotated[
    TaskType | ValidationErrorType | TaskNotFoundErrorType | TaskConflictErrorType,
    strawberry.union("UpdateTaskResult"),
]
ChangeTaskStatusResult = Annotated[
    TaskType | TaskNotFoundErrorType | TaskConflictErrorType,
    strawberry.union("ChangeTaskStatusResult"),
]
AssignTaskResult = Annotated[
    TaskType | TaskNotFoundErrorType | TaskConflictErrorType | UserNotFoundErrorType,
    strawberry.union("AssignTaskResult"),
]
UnassignTaskResult = Annotated[
    TaskType | TaskNotFoundErrorType | TaskConflictErrorType,
    strawberry.union("UnassignTaskResult"),
]
DeleteTaskResult = Annotated[
    DeleteTaskSuccessType | TaskNotFoundErrorType | TaskConflictErrorType | ForbiddenErrorType,
    strawberry.union("DeleteTaskResult"),
]
