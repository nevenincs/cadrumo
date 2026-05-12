"""Stable storage-namespace constants for the operator's autónomo profile.

The constants below pin the encrypted ``SecureObjectRepository``
namespace, schema version, and natural-key projection used to store
the operator's :class:`AutonomoProfile`. They are referenced by the
archive registry (``aeat.application.archive._registry``) and by
filing-runtime tests that seed a profile envelope directly.
"""

from __future__ import annotations

from pathlib import Path

_PROFILE_NAMESPACE = "aeat.application.setup.profile"
_PROFILE_VERSION = 1


def _profile_object_key(target: Path) -> str:
    """Return the secure-object natural key for a logical profile path."""

    return target.expanduser().resolve().as_posix()


__all__ = ["_PROFILE_NAMESPACE", "_PROFILE_VERSION", "_profile_object_key"]
