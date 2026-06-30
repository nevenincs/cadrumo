"""Logical keys for encrypted AEAT browser-session objects.

:func:`aeat_auth_session_storage_state_path` composes the active bucket id
and provider storage stem into the durable logical key consumed by the encrypted
AEAT browser-session store. The returned :class:`~pathlib.Path` is an object
key, not a plaintext filesystem destination.

This module is the core-side authority for the auth-session object-key grammar
introduced when AEAT browser sessions moved from plaintext token-directory
paths to encrypted secure-object storage. Application probes and provider
adapters call the same helper so certificate and Cl@ve Móvil session reads,
writes, and deletes agree on one active-bucket/provider partition. The key is
deliberately independent of ``Settings.aeat_token_dir``; the secure repository
digests the logical key before persistence.
"""

from __future__ import annotations

from pathlib import Path

AEAT_AUTH_SESSION_LOGICAL_ROOT = Path(".aeat") / "auth" / "sessions"
"""Stable logical root for encrypted AEAT browser-session object keys.

The root is part of the secure-object logical key. It names the auth-session
namespace for humans and tests, but it is not a directory this module creates or
writes.
"""


def aeat_auth_session_storage_state_path(bucket_id: str, storage_stem: str) -> Path:
    """Return the stable logical session key for ``bucket_id`` and provider stem.

    The returned path is not a filesystem destination. It is a durable logical
    object key consumed by the encrypted browser-session store. The caller owns
    resolving the active bucket id and selecting the provider stem (for example
    ``"storage"`` for certificate auth or ``"clave-movil-storage"`` for Cl@ve
    Móvil).

    Args:
        bucket_id: Active bucket/profile identifier that partitions session
            state between operator profiles.
        storage_stem: Provider-specific storage-state stem.

    Returns:
        A :class:`~pathlib.Path` under :data:`AEAT_AUTH_SESSION_LOGICAL_ROOT`
        suitable for the encrypted browser-session store.
    """
    return AEAT_AUTH_SESSION_LOGICAL_ROOT / f"{bucket_id}-{storage_stem}.json"
