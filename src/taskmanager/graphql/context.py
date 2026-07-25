from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket
from strawberry.asgi import GraphQL

from taskmanager.config import settings
from taskmanager.db.session import session_scope
from taskmanager.graphql.dataloaders import Loaders, build_loaders
from taskmanager.models import User
from taskmanager.services.auth import resolve_current_user


@dataclass
class Context:
    current_user: User | None
    auth_error: str | None
    loaders: Loaders


class TaskManagerGraphQL(GraphQL):
    async def get_context(
        self, request: Request | WebSocket, response: Response | WebSocket
    ) -> Context:
        header_value = request.headers.get(settings.auth_header_name)

        async with session_scope() as session:
            current_user, auth_error = await resolve_current_user(
                session, header_value, settings.auth_header_name
            )

        return Context(
            current_user=current_user,
            auth_error=auth_error,
            loaders=build_loaders(),
        )
