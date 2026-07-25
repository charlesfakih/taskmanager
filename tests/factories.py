from taskmanager.db.session import async_session_factory
from taskmanager.domain.enums import TaskPriority, TaskStatus
from taskmanager.models import Project, Task, User


async def make_user(email: str = "user@example.com", display_name: str = "Test User") -> User:
    async with async_session_factory() as session:
        user = User(email=email, display_name=display_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def make_project(owner_id: int, key: str = "TST", name: str = "Test Project") -> Project:
    async with async_session_factory() as session:
        project = Project(key=key, name=name, owner_id=owner_id)
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


async def make_task(project_id: int, created_by_id: int, **overrides) -> Task:
    defaults = dict(
        title="Test task",
        status=TaskStatus.TODO.value,
        priority=TaskPriority.MEDIUM.value,
        assignee_id=None,
        due_date=None,
    )
    defaults.update(overrides)
    async with async_session_factory() as session:
        task = Task(project_id=project_id, created_by_id=created_by_id, **defaults)
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task
