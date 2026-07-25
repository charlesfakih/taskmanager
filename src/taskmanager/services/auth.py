from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.models import Project, Task, User


async def resolve_current_user(
    session: AsyncSession, header_value: str | None, header_name: str
) -> tuple[User | None, str | None]:
    """Resolve the stubbed identity header into a user.

    Three outcomes:
    - No header at all -> (None, None): anonymous, reads allowed.
    - Header present but doesn't resolve to a real user -> (None, <error message>):
      always rejected, never silently downgraded to anonymous (that would mask a
      client bug where it thinks it's authenticated as someone but isn't).
    - Header present and valid -> (user, None): authenticated.
    """
    if header_value is None:
        return None, None

    try:
        user_id = int(header_value)
    except ValueError:
        return None, f"{header_name} header must be an integer user id, got {header_value!r}"

    user = await session.get(User, user_id)
    if user is None:
        return None, f"{header_name} header does not match any known user (id={user_id})"

    return user, None


def can_delete_task(user: User, task: Task, project: Project) -> bool:
    """Delete is the one access-controlled task operation: creator, current
    assignee, or the owning project's owner may delete a task."""
    return user.id in (task.created_by_id, task.assignee_id, project.owner_id)
