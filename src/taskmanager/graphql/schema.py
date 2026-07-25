import strawberry
from strawberry.extensions import MaskErrors

from taskmanager.graphql.errors import should_mask_error
from taskmanager.graphql.mutations import Mutation
from taskmanager.graphql.queries import Query

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[lambda: MaskErrors(should_mask_error=should_mask_error)],
)
