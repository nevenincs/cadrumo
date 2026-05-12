"""Stable storage-namespace constants for the operator's autónomo profile.

The constants below pin the encrypted ``SecureObjectRepository``
namespace, schema version, and natural-key projection used to store
the operator's :class:`AutonomoProfile`. The namespace string and
HKDF context byte string are stable identifiers carried in the
encrypted store and MUST NOT change: persisted rows reference
``aeat.application.setup.profile`` and decrypt under
``b"aeat.application.setup.profile.v1"``. Only the Python module
path moves with the wizard rewrite.

Callers: the archive registry (``aeat.application.archive._registry``)
and the storage rotation surface that re-keys archived profile
envelopes.
"""

from __future__ import annotations

from pathlib import Path

_PROFILE_NAMESPACE = "aeat.application.setup.profile"
_PROFILE_VERSION = 1
_PROFILE_HKDF_CONTEXT = b"aeat.application.setup.profile.v1"


def _profile_object_key(target: Path) -> str:
    """Return the secure-object natural key for a logical profile path."""

    return target.expanduser().resolve().as_posix()


__all__ = [
    "_PROFILE_HKDF_CONTEXT",
    "_PROFILE_NAMESPACE",
    "_PROFILE_VERSION",
    "_profile_object_key",
]
