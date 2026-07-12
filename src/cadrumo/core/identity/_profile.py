"""Profile UUID identity for the per-operator profile aggregate.

The profile identity is the immutable handle the bucket directory, the
keystore directory, the secure-object key, and the active-profile
pointer all key on. Promoting the alias to :mod:`aeat.core.identity`
lets every consumer — adapters, persistence, application services, the
CLI surface — import it without crossing a sibling-domain boundary.

Profile identities are minted as canonical UUIDv4 strings via
:func:`aeat.domain.user_profile._values.new_profile_id`. Operator labels
resolve to profile UUIDs through the application profile resolver before
they reach this identity boundary.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

ProfileId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=36,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    ),
]
"""Per-operator profile identity (canonical UUIDv4 string)."""

__all__ = ("ProfileId",)
