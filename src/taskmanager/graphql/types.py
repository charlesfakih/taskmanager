import datetime as dt

import strawberry

from taskmanager.domain.enums import TaskPriority, TaskStatus
from taskmanager.models import Project as ProjectModel
from taskmanager.models import Task as TaskModel
from taskmanager.models import User as UserModel

TaskStatusGQL = strawberry.enum(TaskStatus, name="TaskStatus")
TaskPriorityGQL = strawberry.enum(TaskPriority, name="TaskPriority")


@strawberry.type(name="User")
class UserType:
    id: strawberry.ID
    email: str
    display_name: str

    @staticmethod
    def from_model(m: UserModel) -> "UserType":
        return UserType(id=strawberry.ID(str(m.id)), email=m.email, display_name=m.display_name)


@strawberry.type(name="Project")
class ProjectType:
    id: strawberry.ID
    key: str
    name: str
    description: str | None
    _owner_id: strawberry.Private[int]

    @strawberry.field
    async def owner(self, info: strawberry.Info) -> UserType:
        user = await info.context.loaders.user_by_id.load(self._owner_id)
        assert user is not None  # FK guarantees a valid owner
        return UserType.from_model(user)

    @staticmethod
    def from_model(m: ProjectModel) -> "ProjectType":
        return ProjectType(
            id=strawberry.ID(str(m.id)),
            key=m.key,
            name=m.name,
            description=m.description,
            _owner_id=m.owner_id,
        )


@strawberry.type(name="Task")
class TaskType:
    id: strawberry.ID
    title: str
    description: str | None
    status: TaskStatusGQL  # type: ignore[valid-type]
    priority: TaskPriorityGQL  # type: ignore[valid-type]
    due_date: dt.date | None
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime
    _project_id: strawberry.Private[int]
    _assignee_id: strawberry.Private[int | None]
    _created_by_id: strawberry.Private[int]

    @strawberry.field
    async def project(self, info: strawberry.Info) -> ProjectType:
        project = await info.context.loaders.project_by_id.load(self._project_id)
        assert project is not None  # FK (ON DELETE RESTRICT) guarantees this
        return ProjectType.from_model(project)

    @strawberry.field
    async def assignee(self, info: strawberry.Info) -> UserType | None:
        if self._assignee_id is None:
            return None
        user = await info.context.loaders.user_by_id.load(self._assignee_id)
        return UserType.from_model(user) if user else None

    @strawberry.field
    async def created_by(self, info: strawberry.Info) -> UserType:
        user = await info.context.loaders.user_by_id.load(self._created_by_id)
        assert user is not None  # created_by is a required FK
        return UserType.from_model(user)

    @staticmethod
    def from_model(m: TaskModel) -> "TaskType":
        return TaskType(
            id=strawberry.ID(str(m.id)),
            title=m.title,
            description=m.description,
            status=TaskStatus(m.status),
            priority=TaskPriority(m.priority),
            due_date=m.due_date,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
            _project_id=m.project_id,
            _assignee_id=m.assignee_id,
            _created_by_id=m.created_by_id,
        )


@strawberry.type(name="PageInfo")
class PageInfo:
    has_next_page: bool
    end_cursor: str | None


@strawberry.type(name="TaskEdge")
class TaskEdge:
    cursor: str
    node: TaskType


@strawberry.type(name="TaskConnection")
class TaskConnection:
    edges: list[TaskEdge]
    page_info: PageInfo
    total_count: int
