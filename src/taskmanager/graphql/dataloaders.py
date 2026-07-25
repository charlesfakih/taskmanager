from dataclasses import dataclass

from sqlalchemy import select
from strawberry.dataloader import DataLoader

from taskmanager.db.session import session_scope
from taskmanager.models import Project, User


async def _load_users(ids: list[int]) -> list[User | None]:
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.id.in_(ids)))
        by_id = {u.id: u for u in result.scalars()}
    return [by_id.get(i) for i in ids]


async def _load_projects(ids: list[int]) -> list[Project | None]:
    async with session_scope() as session:
        result = await session.execute(select(Project).where(Project.id.in_(ids)))
        by_id = {p.id: p for p in result.scalars()}
    return [by_id.get(i) for i in ids]


@dataclass
class Loaders:
    user_by_id: DataLoader[int, User | None]
    project_by_id: DataLoader[int, Project | None]


def build_loaders() -> Loaders:
    """Fresh loaders per request — batched state must never leak across requests."""
    return Loaders(
        user_by_id=DataLoader(load_fn=_load_users),
        project_by_id=DataLoader(load_fn=_load_projects),
    )
