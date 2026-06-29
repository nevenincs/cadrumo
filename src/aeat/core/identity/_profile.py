"""Profile-identity alias for the per-operator profile aggregate.

The profile identity is the immutable handle the bucket directory, the
keystore directory, the secure-object key, and the active-profile
pointer all key on. Promoting the alias to :mod:`aeat.core.identity`
lets every consumer — adapters, persistence, application services, the
CLI surface — import it without crossing a sibling-domain boundary.

The constraint shape mirrors the canonical pin already established by
:data:`aeat.domain.user_profile._values._ProfileId`:
``min_length=1``, ``max_length=96``, surrounding whitespace stripped,
matching ``^[A-Za-z0-9][A-Za-z0-9_.-]*$``. Profile identities are
minted as canonical UUIDv4 strings via
:func:`aeat.domain.user_profile._values.new_profile_id`, but the
constraint stays permissive enough to accept operator labels that are
still valid on the persistence boundary.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

ProfileId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z_0-9.-]*$",
    ),
]
"""Per-operator profile identity (canonical UUIDv4 or operator label)."""

__all__ = ("ProfileId",)
