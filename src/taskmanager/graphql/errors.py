"""Top-level (request-scope) GraphQL error helpers.

These are for errors that apply above any single mutation's typed result
union — chiefly authentication/authorization failures on context itself,
which can occur on queries as well as mutations. Per-mutation domain errors
(not found, version conflict, validation) are instead returned as typed
union members — see graphql/mutations.py.
"""

from graphql import GraphQLError

from taskmanager.domain.errors import (
    DomainError,
    ForbiddenError,
    InvalidArgumentError,
    InvalidCursorError,
    NotAuthenticatedError,
)

_ERROR_CODES: dict[type[DomainError], str] = {
    NotAuthenticatedError: "UNAUTHENTICATED",
    ForbiddenError: "FORBIDDEN",
    InvalidCursorError: "BAD_USER_INPUT",
    InvalidArgumentError: "BAD_USER_INPUT",
}


def as_graphql_error(exc: DomainError) -> GraphQLError:
    code = _ERROR_CODES.get(type(exc), "DOMAIN_ERROR")
    return GraphQLError(message=str(exc), extensions={"code": code}, original_error=exc)


def should_mask_error(error: GraphQLError) -> bool:
    """Only mask truly unexpected exceptions; let domain errors' messages through.

    Note: graphql-core's `located_error` re-wraps a raised GraphQLError, so by the
    time this runs `error.original_error` is our raised GraphQLError itself, not the
    underlying DomainError — but `extensions` (including `code`) is copied through
    from it, so we key off that instead of an isinstance check.
    """
    return "code" not in (error.extensions or {})
