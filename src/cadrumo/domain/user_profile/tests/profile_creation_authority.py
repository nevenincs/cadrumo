"""Profile-creation authority for tests that build records outside a leased operation.

The profile schema comes from the published registry generation through the
runtime reader, never from authored source. Tests that run inside a leased
authority operation should take the lease's own creation context instead, so
their records carry that operation's generation pin.
"""

from __future__ import annotations

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.authority_artifact import ProfileCreateContext, ProfileSchemaComponentQuery
from ...calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader
from ...calculations.registry.tests.published_authority import published_profile_schema


def profile_creation_context_for_test() -> ProfileCreateContext:
    """Pin the published profile schema in one explicit test authority and return its creation context."""
    reader = FakeAuthorityComponentReader({ProfileSchemaComponentQuery(): published_profile_schema()})
    operation = PinnedAuthorityOperation(reader, reader.pin())
    return operation.profile_create_context()
