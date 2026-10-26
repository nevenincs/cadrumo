"""Profile decode authority for auth tests that run under a leased operation.

The auth identity guards decode profile facts through the schema context of
the authority operation the caller holds. Tests take that context from the
lease already in scope, so the guard and the test agree on one generation pin
without composing any persistence-backed profile runtime.
"""

from __future__ import annotations

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope


def leased_profile_decode_context() -> ProfileDecodeContext:
    """Return the profile decode context of the authority operation leased for the running test.

    A test module obtains the lease with ``pytest.mark.usefixtures("operation")``
    or an explicit ``validating_governed_facts`` block; outside a lease this
    refuses instead of opening a lease of its own.
    """
    operation = governed_facts_in_scope()
    if not isinstance(operation, PinnedAuthorityOperation):
        raise LookupError("a profile decode context requires a leased authority operation in scope")
    return operation.profile_decode_context()


__all__ = ["leased_profile_decode_context"]
