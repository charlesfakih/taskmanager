from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from taskmanager.graphql.context import TaskManagerGraphQL
from taskmanager.graphql.schema import schema


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


graphql_app = TaskManagerGraphQL(schema, graphql_ide="graphiql")

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/graphql", graphql_app, methods=["GET", "POST"]),
    ],
)
