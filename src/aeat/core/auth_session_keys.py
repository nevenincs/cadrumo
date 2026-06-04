"""Logical keys for encrypted AEAT browser-session objects."""

from __future__ import annotations

from pathlib import Path

AEAT_AUTH_SESSION_LOGICAL_ROOT = Path(".aeat") / "auth" / "sessions"
"""Stable logical root for encrypted AEAT browser-session object keys."""


def aeat_auth_session_storage_state_path(bucket_id: str, storage_stem: str) -> Path:
    """Return the stable logical session key for ``bucket_id`` and provider stem.

    The returned path is not a filesystem destination. It is a durable logical
    object key consumed by the encrypted browser-session store.
    """
    return AEAT_AUTH_SESSION_LOGICAL_ROOT / f"{bucket_id}-{storage_stem}.json"
