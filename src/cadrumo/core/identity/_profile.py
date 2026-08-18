"""Profile UUID identity for the per-operator profile aggregate.

The profile identity is the immutable handle the bucket directory, the
keystore directory, the secure-object key, and the active-profile
pointer all key on. Promoting the alias to :mod:`cadrumo.core.identity`
lets every consumer — adapters, persistence, application services, the
CLI surface — import it without crossing a sibling-domain boundary.

Profile identities are minted as canonical UUIDv4 strings via
:func:`cadrumo.domain.user_profile._values.new_profile_id`. Operator labels
resolve to profile UUIDs through the application profile resolver before
they reach this identity boundary.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

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


def canonical_profile_bucket_id(profile_id: str | UUID) -> str:
    """Return the canonical bucket-identity spelling of ``profile_id``.

    The profile aggregate keys its bucket directory on the canonical profile
    UUID; this states the bridge from either spelling of that identity — the
    canonical string or a ``uuid.UUID`` object — to the one canonical string
    every persisted address composes on. It is the named counterpart of
    :func:`cadrumo.core.identity.canonical_bucket_id`, on the profile side of
    the boundary: where that function states a bucket identity, this one
    states a profile identity that is about to BECOME a bucket address.

    Args:
        profile_id: A profile identity in either of its two spellings.

    Returns:
        The canonical lowercase-hyphenated UUIDv4 string.

    Raises:
        ValueError: When the value is not a canonical profile identity.
            Deliberately the plain builtin: each caller translates it into
            its own typed refusal, so the shared helper does not impose one
            surface's error class on every other.
    """
    try:
        parsed = UUID(str(profile_id))
    except (ValueError, TypeError) as exc:
        raise ValueError("profile_id is not a canonical profile identity") from exc
    if parsed.version != 4:
        raise ValueError("profile_id is not a canonical profile identity")
    return str(parsed)


__all__ = ("ProfileId", "canonical_profile_bucket_id")
