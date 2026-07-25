"""The flagship test for the assignment's N+1 requirement: listing tasks with
their nested assignee/createdBy/project fields must issue a constant number
of SQL statements regardless of how many tasks are on the page.
"""

from sqlalchemy import event

from taskmanager.db.session import engine
from tests.factories import make_project, make_task, make_user
from tests.helpers import gql

TASKS_WITH_RELATIONS_QUERY = """
query($projectId: ID!, $first: Int!) {
  tasks(projectId: $projectId, first: $first) {
    edges {
      node {
        id
        assignee { displayName }
        createdBy { displayName }
        project { name }
      }
    }
  }
}
"""


async def _count_statements_for_n_tasks(client, project_id: int, creator_id: int, n: int) -> int:
    statements: list[str] = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    for i in range(n):
        await make_task(project_id=project_id, created_by_id=creator_id, title=f"T{i}")

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        result = await gql(
            client,
            TASKS_WITH_RELATIONS_QUERY,
            {"projectId": str(project_id), "first": n},
            user_id=creator_id,
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)

    assert result.get("errors") is None, result
    assert len(result["data"]["tasks"]["edges"]) == n
    return len(statements)


async def test_task_list_query_count_is_independent_of_row_count(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)

    small_count = await _count_statements_for_n_tasks(client, project.id, owner.id, n=3)
    large_count = await _count_statements_for_n_tasks(client, project.id, owner.id, n=40)

    # 1 auth-header user lookup (get_context) + 1 list query + 1 totalCount
    # query + 1 batched user lookup (covers both assignee and createdBy via
    # the same DataLoader) + 1 batched project lookup.
    assert small_count == 5
    assert large_count == small_count, (
        f"query count should be flat regardless of row count, got {small_count} "
        f"for 3 tasks vs {large_count} for 40 tasks"
    )
