from taskmanager.domain.enums import TaskPriority, TaskStatus
from tests.factories import make_project, make_task, make_user
from tests.helpers import gql

LIST_QUERY = """
query($projectId: ID!, $filter: TaskFilter, $sort: TaskSort, $first: Int!, $after: String) {
  tasks(projectId: $projectId, filter: $filter, sort: $sort, first: $first, after: $after) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges { cursor node { id title status priority } }
  }
}
"""


async def _all_pages(client, project_id, owner_id, *, first, sort=None, filter=None):
    """Walk every page via `after` and return the concatenated node ids, also
    asserting no duplicates/gaps -- the real correctness property of keyset
    pagination under a stable dataset."""
    ids: list[str] = []
    after = None
    pages = 0
    while True:
        variables = {"projectId": str(project_id), "first": first, "after": after}
        if sort is not None:
            variables["sort"] = sort
        if filter is not None:
            variables["filter"] = filter
        result = await gql(client, LIST_QUERY, variables, user_id=owner_id)
        assert result.get("errors") is None, result
        page = result["data"]["tasks"]
        ids.extend(e["node"]["id"] for e in page["edges"])
        pages += 1
        assert pages < 100, "pagination did not terminate"
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return ids


async def test_pagination_covers_every_row_exactly_once(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    created = [
        await make_task(project_id=project.id, created_by_id=owner.id, title=f"T{i}")
        for i in range(23)
    ]

    ids = await _all_pages(client, project.id, owner.id, first=5)

    assert len(ids) == len(created)
    assert len(set(ids)) == len(ids)  # no duplicates
    assert set(ids) == {str(t.id) for t in created}


async def test_sort_created_at_desc_orders_newest_first(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    first = await make_task(project_id=project.id, created_by_id=owner.id, title="first")
    second = await make_task(project_id=project.id, created_by_id=owner.id, title="second")

    result = await gql(
        client,
        LIST_QUERY,
        {"projectId": str(project.id), "first": 10},
        user_id=owner.id,
    )
    ids = [e["node"]["id"] for e in result["data"]["tasks"]["edges"]]
    assert ids == [str(second.id), str(first.id)]


async def test_sort_priority_desc_orders_by_severity_not_alphabetically(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    low = await make_task(
        project_id=project.id, created_by_id=owner.id, priority=TaskPriority.LOW.value
    )
    urgent = await make_task(
        project_id=project.id, created_by_id=owner.id, priority=TaskPriority.URGENT.value
    )
    high = await make_task(
        project_id=project.id, created_by_id=owner.id, priority=TaskPriority.HIGH.value
    )
    medium = await make_task(
        project_id=project.id, created_by_id=owner.id, priority=TaskPriority.MEDIUM.value
    )

    result = await gql(
        client,
        LIST_QUERY,
        {"projectId": str(project.id), "first": 10, "sort": "PRIORITY_DESC"},
        user_id=owner.id,
    )
    ids = [e["node"]["id"] for e in result["data"]["tasks"]["edges"]]
    # Alphabetically "low" sorts above "high", which would be wrong here.
    assert ids == [str(urgent.id), str(high.id), str(medium.id), str(low.id)]


async def test_filter_by_status(client):
    owner = await make_user(email="owner@example.com")
    project = await make_project(owner_id=owner.id)
    await make_task(project_id=project.id, created_by_id=owner.id, status=TaskStatus.DONE.value)
    await make_task(project_id=project.id, created_by_id=owner.id, status=TaskStatus.TODO.value)

    result = await gql(
        client,
        LIST_QUERY,
        {"projectId": str(project.id), "first": 10, "filter": {"status": "DONE"}},
        user_id=owner.id,
    )
    page = result["data"]["tasks"]
    assert page["totalCount"] == 1
    assert page["edges"][0]["node"]["status"] == "DONE"


async def test_filter_by_priority_and_assignee(client):
    owner = await make_user(email="owner@example.com")
    assignee = await make_user(email="assignee@example.com")
    project = await make_project(owner_id=owner.id)
    target = await make_task(
        project_id=project.id,
        created_by_id=owner.id,
        priority=TaskPriority.URGENT.value,
        assignee_id=assignee.id,
    )
    await make_task(project_id=project.id, created_by_id=owner.id, priority=TaskPriority.LOW.value)

    result = await gql(
        client,
        LIST_QUERY,
        {
            "projectId": str(project.id),
            "first": 10,
            "filter": {"priority": "URGENT", "assigneeId": str(assignee.id)},
        },
        user_id=owner.id,
    )
    page = result["data"]["tasks"]
    assert page["totalCount"] == 1
    assert page["edges"][0]["node"]["id"] == str(target.id)


async def test_pagination_is_stable_across_all_sort_fields(client):
    """Every sort variant should paginate without dropping or duplicating rows,
    including the nullable ASSIGNEE sort's NULLS LAST handling."""
    owner = await make_user(email="owner@example.com")
    assignee = await make_user(email="assignee@example.com")
    project = await make_project(owner_id=owner.id)
    created = []
    for i in range(11):
        created.append(
            await make_task(
                project_id=project.id,
                created_by_id=owner.id,
                title=f"T{i}",
                status=[TaskStatus.TODO, TaskStatus.DONE][i % 2].value,
                priority=[TaskPriority.LOW, TaskPriority.HIGH][i % 2].value,
                assignee_id=assignee.id if i % 3 == 0 else None,
            )
        )
    expected_ids = {str(t.id) for t in created}

    for sort in ["CREATED_AT_DESC", "STATUS_ASC", "PRIORITY_DESC", "ASSIGNEE_ASC"]:
        ids = await _all_pages(client, project.id, owner.id, first=4, sort=sort)
        assert set(ids) == expected_ids, f"sort={sort} lost or duplicated rows"
        assert len(ids) == len(expected_ids), f"sort={sort} produced wrong count"
