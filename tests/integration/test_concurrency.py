"""Two clients acting on the same task at the same time.

The stale-version case proves the sequential-conflict path; the
`asyncio.gather` case proves real DB-level atomicity under a genuine race,
not just sequential logic that happens to check a field.
"""

import asyncio

from tests.factories import make_project, make_task, make_user
from tests.helpers import gql

UPDATE_TASK_MUTATION = """
mutation($id: ID!, $input: UpdateTaskInput!) {
  updateTask(id: $id, input: $input) {
    __typename
    ... on Task { id title version }
    ... on TaskConflictError { message currentTask { version } }
  }
}
"""


async def test_stale_version_update_is_rejected_as_conflict(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=owner.id)

    # Two "clients" both read the task at version 1.
    first = await gql(
        client,
        UPDATE_TASK_MUTATION,
        {"id": str(task.id), "input": {"expectedVersion": 1, "title": "First writer wins"}},
        user_id=owner.id,
    )
    assert first["data"]["updateTask"]["__typename"] == "Task"
    assert first["data"]["updateTask"]["version"] == 2

    # Second client still has the stale version=1 it originally read.
    second = await gql(
        client,
        UPDATE_TASK_MUTATION,
        {"id": str(task.id), "input": {"expectedVersion": 1, "title": "Second writer loses"}},
        user_id=owner.id,
    )
    result = second["data"]["updateTask"]
    assert result["__typename"] == "TaskConflictError"
    assert result["currentTask"]["version"] == 2


async def test_concurrent_updates_to_same_task_only_one_wins(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=owner.id)

    responses = await asyncio.gather(
        gql(
            client,
            UPDATE_TASK_MUTATION,
            {"id": str(task.id), "input": {"expectedVersion": 1, "title": "Writer A"}},
            user_id=owner.id,
        ),
        gql(
            client,
            UPDATE_TASK_MUTATION,
            {"id": str(task.id), "input": {"expectedVersion": 1, "title": "Writer B"}},
            user_id=owner.id,
        ),
    )

    typenames = sorted(r["data"]["updateTask"]["__typename"] for r in responses)
    assert typenames == ["Task", "TaskConflictError"], (
        "exactly one concurrent writer should succeed and the other should "
        f"see a version conflict, got {typenames}"
    )
