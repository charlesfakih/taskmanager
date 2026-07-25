"""Domain exceptions raised by the services layer.

GraphQL resolvers catch these and map each 1:1 onto a typed union member
(see graphql/errors.py) — nothing here should ever reach a client as a
raw stack trace.
"""


class DomainError(Exception):
    """Base class for all expected, typed domain failures."""


class NotAuthenticatedError(DomainError):
    """No (or no valid) identity was presented for an operation that requires one."""


class ForbiddenError(DomainError):
    """An authenticated user attempted an operation they are not permitted to do."""


class TaskNotFoundError(DomainError):
    def __init__(self, task_id: int):
        self.task_id = task_id
        super().__init__(f"Task {task_id} not found")


class ProjectNotFoundError(DomainError):
    def __init__(self, project_id: int):
        self.project_id = project_id
        super().__init__(f"Project {project_id} not found")


class UserNotFoundError(DomainError):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


class TaskConflictError(DomainError):
    """Optimistic-concurrency check failed: the task was modified concurrently."""

    def __init__(self, task_id: int, expected_version: int):
        self.task_id = task_id
        self.expected_version = expected_version
        super().__init__(
            f"Task {task_id} was modified by someone else (expected version {expected_version})"
        )


class InvalidCursorError(DomainError):
    def __init__(self, message: str = "Invalid or incompatible pagination cursor"):
        super().__init__(message)


class InvalidArgumentError(DomainError):
    """A client-supplied query argument is out of the allowed range/shape
    (e.g. `first` above the server-enforced max)."""

    def __init__(self, message: str):
        super().__init__(message)


class ValidationError(DomainError):
    """Wraps one or more Pydantic field errors for a mutation input."""

    def __init__(self, field_errors: list[tuple[str, str]]):
        self.field_errors = field_errors
        super().__init__("; ".join(f"{f}: {m}" for f, m in field_errors))
