"""Application-owned profile-key catalogue projection.

The operation-scoped setup flow is the sole authoring source. The catalogue
is compiled for the caller's pinned generation; no domain slot, registration
push, or import-order bootstrap is involved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.requirement import Requirement
from ...domain.contribuyente.normalise import normalise_key
from .profile_key import ProfileKey

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def profile_keys(operation: PinnedAuthorityOperation) -> tuple[ProfileKey, ...]:
    """Compile and return profile keys from the caller's pinned wizard flow."""
    from ..wizard.catalogue import build_setup_flow
    from ..wizard.compiler import compile_profile_keys

    return compile_profile_keys((build_setup_flow(operation),))


def profile_key(raw: str, *, operation: PinnedAuthorityOperation) -> ProfileKey:
    """Return the catalogue record matching ``raw`` after key normalisation."""
    canonical = normalise_key(raw)
    for entry in profile_keys(operation):
        if entry.key == canonical:
            return entry
    raise KeyError(f"unknown profile key: {raw!r}")


def optional_profile_keys(operation: PinnedAuthorityOperation) -> tuple[ProfileKey, ...]:
    """Return catalogue entries whose requirement is ``OPTIONAL``."""
    return tuple(entry for entry in profile_keys(operation) if entry.requirement is Requirement.OPTIONAL)


__all__ = ["ProfileKey", "optional_profile_keys", "profile_key", "profile_keys"]
