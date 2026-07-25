from tests.factories import make_project, make_user
from tests.helpers import gql

CREATE = """
mutation($input: CreateTaskInput!) {
  createTask(input: $input) {
    __typename
    ... on Task { id title status priority version }
    ... on ValidationError { errors { field message } }
  }
}
"""

TASK_QUERY = """
query($id: ID!) {
  task(id: $id) { id title status priority assignee { id } createdBy { id } project { key } }
}
"""


async def test_full_task_lifecycle(client):
    owner = await make_user(email="owner@example.com")
    assignee = await make_user(email="assignee@example.com")
    project = await make_project(owner_id=owner.id, key="LIFE")

    created = await gql(
        client,
        CREATE,
        {"input": {"projectId": str(project.id), "title": "Ship it", "priority": "HIGH"}},
        user_id=owner.id,
    )
    task = created["data"]["createTask"]
    assert task["__typename"] == "Task"
    assert task["status"] == "TODO"
    task_id = task["id"]
    version = task["version"]

    fetched = await gql(client, TASK_QUERY, {"id": task_id}, user_id=owner.id)
    assert fetched["data"]["task"]["title"] == "Ship it"
    assert fetched["data"]["task"]["createdBy"]["id"] == str(owner.id)
    assert fetched["data"]["task"]["project"]["key"] == "LIFE"

    updated = await gql(
        client,
        """mutation($id: ID!, $v: Int!) {
             updateTask(id: $id, input: {expectedVersion: $v, title: "Ship it faster"}) {
               __typename ... on Task { title version }
             }
           }""",
        {"id": task_id, "v": version},
        user_id=owner.id,
    )
    assert updated["data"]["updateTask"]["title"] == "Ship it faster"
    version = updated["data"]["updateTask"]["version"]

    status_changed = await gql(
        client,
        """mutation($id: ID!, $v: Int!) {
             changeTaskStatus(id: $id, input: {status: IN_PROGRESS, expectedVersion: $v}) {
               __typename ... on Task { status version }
             }
           }""",
        {"id": task_id, "v": version},
        user_id=owner.id,
    )
    assert status_changed["data"]["changeTaskStatus"]["status"] == "IN_PROGRESS"
    version = status_changed["data"]["changeTaskStatus"]["version"]

    assigned = await gql(
        client,
        """mutation($id: ID!, $v: Int!, $u: ID!) {
             assignTask(id: $id, input: {assigneeId: $u, expectedVersion: $v}) {
               __typename ... on Task { assignee { id } version }
             }
           }""",
        {"id": task_id, "v": version, "u": str(assignee.id)},
        user_id=owner.id,
    )
    assert assigned["data"]["assignTask"]["assignee"]["id"] == str(assignee.id)
    version = assigned["data"]["assignTask"]["version"]

    unassigned = await gql(
        client,
        """mutation($id: ID!, $v: Int!) {
             unassignTask(id: $id, input: {expectedVersion: $v}) {
               __typename ... on Task { assignee { id } version }
             }
           }""",
        {"id": task_id, "v": version},
        user_id=owner.id,
    )
    assert unassigned["data"]["unassignTask"]["assignee"] is None
    version = unassigned["data"]["unassignTask"]["version"]

    deleted = await gql(
        client,
        """mutation($id: ID!, $v: Int!) {
             deleteTask(id: $id, input: {expectedVersion: $v}) {
               __typename ... on DeleteTaskSuccess { id }
             }
           }""",
        {"id": task_id, "v": version},
        user_id=owner.id,
    )
    assert deleted["data"]["deleteTask"]["__typename"] == "DeleteTaskSuccess"

    gone = await gql(client, TASK_QUERY, {"id": task_id}, user_id=owner.id)
    assert gone["data"]["task"] is None


async def test_create_task_validation_error_surfaces_as_typed_union_member(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)

    result = await gql(
        client,
        CREATE,
        {"input": {"projectId": str(project.id), "title": "   "}},
        user_id=owner.id,
    )
    task = result["data"]["createTask"]
    assert task["__typename"] == "ValidationError"
    assert task["errors"][0]["field"] == "title"
