"""Delete is the one access-controlled task operation: creator, current
assignee, or the owning project's owner may delete a task; anyone else
gets a typed ForbiddenError. Also covers the auth-header edge cases that
apply to every operation.
"""

from tests.factories import make_project, make_task, make_user
from tests.helpers import gql

DELETE_TASK_MUTATION = """
mutation($id: ID!, $expectedVersion: Int!) {
  deleteTask(id: $id, input: {expectedVersion: $expectedVersion}) {
    __typename
    ... on DeleteTaskSuccess { id }
    ... on ForbiddenError { message }
    ... on TaskNotFoundError { message }
  }
}
"""

TASK_QUERY = "query($id: ID!) { task(id: $id) { id title } }"


async def _delete(client, task_id: int, user_id: int) -> dict:
    result = await gql(
        client, DELETE_TASK_MUTATION, {"id": str(task_id), "expectedVersion": 1}, user_id=user_id
    )
    return result["data"]["deleteTask"]


async def test_creator_can_delete(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=owner.id)

    result = await _delete(client, task.id, owner.id)
    assert result["__typename"] == "DeleteTaskSuccess"


async def test_assignee_can_delete(client):
    owner = await make_user(email="owner@example.com")
    assignee = await make_user(email="assignee@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=owner.id, assignee_id=assignee.id)

    result = await _delete(client, task.id, assignee.id)
    assert result["__typename"] == "DeleteTaskSuccess"


async def test_project_owner_can_delete(client):
    owner = await make_user(email="owner@example.com")
    creator = await make_user(email="creator@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=creator.id)

    result = await _delete(client, task.id, owner.id)
    assert result["__typename"] == "DeleteTaskSuccess"


async def test_unrelated_user_cannot_delete(client):
    owner = await make_user(email="owner@example.com")
    bystander = await make_user(email="bystander@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=owner.id)

    result = await _delete(client, task.id, bystander.id)
    assert result["__typename"] == "ForbiddenError"


async def test_anonymous_read_is_allowed(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=owner.id)

    result = await gql(client, TASK_QUERY, {"id": str(task.id)})  # no user_id -> no header
    assert result.get("errors") is None
    assert result["data"]["task"]["id"] == str(task.id)


async def test_anonymous_mutation_is_rejected(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    task = await make_task(project_id=project.id, created_by_id=owner.id)

    result = await gql(client, DELETE_TASK_MUTATION, {"id": str(task.id), "expectedVersion": 1})
    assert result["data"] is None
    assert result["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


async def test_invalid_user_header_is_rejected_even_for_reads(client):
    result = await gql(client, TASK_QUERY, {"id": "1"}, user_id=999_999)
    # `task` is a nullable field, so GraphQL nulls just that field rather than
    # the whole `data` object -- the error still surfaces in `errors`.
    assert result["data"] == {"task": None}
    assert result["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"
