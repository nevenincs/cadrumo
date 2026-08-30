"""Route-canonical :class:`SecretStore` factory.

:func:`get_secret_store` is a route-aware lazy factory keyed by the resolved
secret-store and blob-store roots from :class:`Settings`. Stores are cached
by normalized route so an explicit Settings route never inherits the first
store constructed by an unrelated profile root; callers needing an isolated
store inject one directly at the consuming boundary (a ``store=`` parameter
on the secret-store consumer) rather than through a process-wide override.

This module previously also carried a path-shaped secret bridge
(``materialise_secret`` / ``export_to_temp_path``) for third-party SDKs that
demand a filesystem path rather than in-memory bytes. It was deleted as
unexercised, security-adjacent dormant capability -- a route to writing
decrypted secrets to the OS tempdir that no production caller had ever
taken, sitting in the public facade with an inviting docstring. Every
current consumer of a secret (the certificate backend, OAuth flow, custody
sessions) reads bytes from :class:`SecretStore` directly. A future SDK that
genuinely cannot consume in-memory bytes gets a purpose-built bridge
declared and enrolled at the point it is needed, not one kept live "just in
case."
"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from ._blob_store import EncryptedBlobStore

if TYPE_CHECKING:
    from .....core.config import Settings
    from ..secret_store.store import SecretStore

# ``secret_store`` imports this package to build its own blob store, so binding
# ``SecretStore`` at module scope closes a real import cycle. It resolved before
# only because the parent facade happened to import one side first; that
# ordering disappeared when the facade became lazy. The single runtime use is
# deferred into the factory below, and every other reference is an annotation.

_factory_lock = Lock()
_stores_by_route: dict[tuple[str, str], SecretStore] = {}


def get_secret_store(*, settings: Settings | None = None) -> SecretStore:
    """Return the route-canonical :class:`SecretStore`.

    Stores are cached by normalized secret-store and blob-store roots, so an
    explicit Settings route never inherits the first store constructed by an
    unrelated profile root. Callers needing an isolated store inject it
    directly at the consuming boundary (the ``store=`` / ``settings=``
    parameters on the secret-store consumers) rather than through a
    process-wide override.

    Args:
        settings: Optional pre-built settings instance. When ``None``,
            :func:`load_settings` is consulted for the current route.

    Returns:
        The cached :class:`SecretStore` for the resolved route.
    """
    with _factory_lock:
        from .....core.config import load_settings

        resolved = settings if settings is not None else load_settings()
        route = (
            os.path.normcase(str(Path(resolved.cadrumo_secret_store_dir).resolve())),
            os.path.normcase(str(Path(resolved.cadrumo_blob_store_dir).resolve())),
        )
        cached = _stores_by_route.get(route)
        if cached is not None:
            return cached
        # Stores fall through to ``get_active_master_key()`` (the
        # active :class:`BucketSession`) when ``master_key_provider`` is
        # absent. The CLI root callback opens the session before any
        # consumer reaches this factory.
        #
        # ``EncryptedBlobStore.root_dir`` is documented as "the directory
        # containing the blobs/ subtree" -- the PARENT of ``blobs/``, i.e.
        # the storage root -- and the store appends its own ``blobs``
        # segment internally (``_shard_dir_for``). Passing
        # ``cadrumo_blob_store_dir`` here (already ``<storage_root>/blobs``)
        # doubled that segment: every blob landed at
        # ``<storage_root>/blobs/blobs/<hex[:2]>/<hash>`` instead of the
        # declared ``<storage_root>/blobs/<hex[:2]>/<hash>``. Passing the
        # storage root honours the class's existing documented contract
        # rather than redefining what ``root_dir`` means for every caller.
        from ..secret_store.store import SecretStore

        blob_store = EncryptedBlobStore(root_dir=Path(resolved.cadrumo_local_storage_root))
        store = SecretStore(
            store_dir=Path(resolved.cadrumo_secret_store_dir),
            blob_store=blob_store,
        )
        _stores_by_route[route] = store
        return store


__all__ = [
    "get_secret_store",
]
