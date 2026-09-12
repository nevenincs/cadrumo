"""Application-owned profile-key catalogue projection.

The wizard's :data:`WIZARD_FLOWS` tuple is the sole authoring source.  The
catalogue is compiled on first use and cached as an immutable tuple; no domain
slot, registration push, or import-order bootstrap is involved.
"""

from __future__ import annotations

from functools import cache

from ...core.requirement import Requirement
from ...domain.contribuyente.normalise import normalise_key
from .profile_key import ProfileKey


@cache
def profile_keys() -> tuple[ProfileKey, ...]:
    """Compile and return the wizard-owned profile-key catalogue."""
    from ..wizard.catalogue import WIZARD_FLOWS
    from ..wizard.compiler import compile_profile_keys

    return compile_profile_keys(WIZARD_FLOWS)


def profile_key(raw: str) -> ProfileKey:
    """Return the catalogue record matching ``raw`` after key normalisation."""
    canonical = normalise_key(raw)
    for entry in profile_keys():
        if entry.key == canonical:
            return entry
    raise KeyError(f"unknown profile key: {raw!r}")


def optional_profile_keys() -> tuple[ProfileKey, ...]:
    """Return catalogue entries whose requirement is ``OPTIONAL``."""
    return tuple(entry for entry in profile_keys() if entry.requirement is Requirement.OPTIONAL)


__all__ = ["ProfileKey", "optional_profile_keys", "profile_key", "profile_keys"]
