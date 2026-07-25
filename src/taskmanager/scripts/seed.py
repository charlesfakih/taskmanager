"""Seed a handful of demo rows so the API is immediately usable after `alembic upgrade head`.

Run with: uv run python -m taskmanager.scripts.seed
"""

import asyncio

from taskmanager.db.session import async_session_factory
from taskmanager.domain.enums import TaskPriority, TaskStatus
from taskmanager.models import Project, Task, User


async def seed() -> None:
    async with async_session_factory() as session:
        alice = User(email="alice@example.com", display_name="Alice Nakamura")
        bob = User(email="bob@example.com", display_name="Bob Okafor")
        session.add_all([alice, bob])
        await session.flush()

        project = Project(
            key="ENG",
            name="Engineering",
            description="Core engineering workstream",
            owner_id=alice.id,
        )
        session.add(project)
        await session.flush()

        session.add_all(
            [
                Task(
                    project_id=project.id,
                    title="Set up CI pipeline",
                    status=TaskStatus.IN_PROGRESS.value,
                    priority=TaskPriority.HIGH.value,
                    assignee_id=bob.id,
                    created_by_id=alice.id,
                ),
                Task(
                    project_id=project.id,
                    title="Write onboarding docs",
                    status=TaskStatus.TODO.value,
                    priority=TaskPriority.LOW.value,
                    assignee_id=None,
                    created_by_id=alice.id,
                ),
            ]
        )
        await session.commit()

        print("Seeded users:")
        print(f"  alice -> X-User-Id: {alice.id}")
        print(f"  bob   -> X-User-Id: {bob.id}")
        print(f"Seeded project '{project.key}' (id={project.id}) with 2 tasks.")


if __name__ == "__main__":
    asyncio.run(seed())
