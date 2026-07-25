import strawberry

from taskmanager.config import settings
from taskmanager.domain.errors import InvalidArgumentError, InvalidCursorError
from taskmanager.graphql.context import Context
from taskmanager.graphql.errors import as_graphql_error
from taskmanager.graphql.guards import check_context
from taskmanager.graphql.inputs import TaskFilterInput, TaskSortGQL
from taskmanager.graphql.types import PageInfo, TaskConnection, TaskEdge, TaskType
from taskmanager.services import tasks as tasks_service
from taskmanager.services.pagination import TaskSort


@strawberry.type
class Query:
    @strawberry.field(description="Fetch a single task by id, or null if it doesn't exist.")
    async def task(
        self, info: strawberry.Info[Context, None], id: strawberry.ID
    ) -> TaskType | None:
        check_context(info)
        task = await tasks_service.get_task(int(id))
        return TaskType.from_model(task) if task else None

    @strawberry.field(
        description=(
            "List tasks in a project, with optional filtering and sorting, "
            "keyset-paginated so it stays fast at thousands of tasks per project."
        )
    )
    async def tasks(
        self,
        info: strawberry.Info[Context, None],
        project_id: strawberry.ID,
        filter: TaskFilterInput | None = None,
        sort: TaskSortGQL = TaskSort.CREATED_AT_DESC,  # type: ignore[assignment]
        first: int = 25,
        after: str | None = None,
    ) -> TaskConnection:
        check_context(info)

        domain_filter = None
        if filter is not None:
            domain_filter = tasks_service.TaskFilter(
                status=filter.status,
                priority=filter.priority,
                assignee_id=int(filter.assignee_id) if filter.assignee_id is not None else None,
            )

        try:
            page = await tasks_service.list_tasks(
                project_id=int(project_id),
                filter=domain_filter,
                sort=sort,
                first=first,
                after=after,
                max_page_size=settings.max_page_size,
            )
        except (InvalidArgumentError, InvalidCursorError) as exc:
            raise as_graphql_error(exc) from exc

        edges = [
            TaskEdge(cursor=cursor, node=TaskType.from_model(task))
            for cursor, task in zip(page.cursors, page.tasks, strict=True)
        ]
        return TaskConnection(
            edges=edges,
            page_info=PageInfo(
                has_next_page=page.has_next_page,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=page.total_count,
        )
