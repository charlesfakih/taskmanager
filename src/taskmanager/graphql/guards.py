import strawberry

from taskmanager.domain.errors import NotAuthenticatedError
from taskmanager.graphql.context import Context
from taskmanager.graphql.errors import as_graphql_error
from taskmanager.models import User


def check_context(info: strawberry.Info[Context, None]) -> User | None:
    """Call at the top of every query/mutation. Reads are allowed anonymously;
    an invalid identity header is always rejected, even for reads."""
    ctx = info.context
    if ctx.auth_error:
        raise as_graphql_error(NotAuthenticatedError(ctx.auth_error))
    return ctx.current_user


def require_authenticated(info: strawberry.Info[Context, None]) -> User:
    """Call at the top of every mutation: anonymous access is rejected."""
    user = check_context(info)
    if user is None:
        raise as_graphql_error(NotAuthenticatedError("Authentication required for this operation"))
    return user
