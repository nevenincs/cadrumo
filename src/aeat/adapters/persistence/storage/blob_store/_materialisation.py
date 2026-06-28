"""Materialisation helpers for path-shaped secret consumers.

Some third-party libraries (Google's
:func:`google.oauth2.service_account.Credentials.from_service_account_file`,
Playwright's ``storage_state`` parameter, certain cert-based clients)
demand a path on disk rather than bytes in memory. The substrate
stores ciphertext; these helpers bridge the gap.

:func:`materialise_secret` is a context manager that yields a
:class:`Path` to a short-lived secure tempfile. The file is created
under the OS tempdir with mode ``0o600`` (POSIX) via the same
``_write_bytes_secure`` primitive used by the master-key file
backend; on context exit the file is unlinked.

:func:`export_to_temp_path` is the explicit-cleanup variant for
callers that need the path beyond a single ``with`` block. It returns
a ``(path, cleanup)`` tuple; the caller is responsible for invoking
``cleanup()`` when the consumer no longer needs the path.

Both helpers consult the active :class:`SecretStore` via
:func:`get_secret_store`, a process-singleton lazy factory keyed by
the resolved :class:`Settings`.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from .....core.logging import get_logger
from ..errors import StorageValidationError
from ..secret_store._secret_store import SecretStore
from ._blob_store import EncryptedBlobStore

if TYPE_CHECKING:
    from .....core.config import Settings

_log = get_logger(__name__)
_factory_lock = Lock()
_singleton_store: SecretStore | None = None
_DEFAULT_TEMPFILE_PREFIX = "aeat-secret"
_EMPTY_SUFFIX = ""
_TEMPFILE_PREFIX_SEPARATOR = "-"
_FORBIDDEN_TEMPFILE_TOKEN_CHARS = frozenset(("/", "\\", "\0"))
_MATERIALISATION_ERROR_CONTEXT = {"surface": "secret_materialisation"}


def get_secret_store(*, settings: Settings | None = None) -> SecretStore:
    """Return the process-wide singleton :class:`SecretStore`.

    The first call constructs the store from the resolved
    :class:`Settings`; subsequent calls return the same instance.
    Tests should call :func:`override_secret_store` to inject a
    deterministic implementation.

    Args:
        settings: Optional pre-built settings instance. When ``None``,
            :func:`load_settings` is consulted on first use.

    Returns:
        The singleton :class:`SecretStore`.
    """
    global _singleton_store
    with _factory_lock:
        if _singleton_store is not None:
            return _singleton_store
        from .....core.config import load_settings

        resolved = settings if settings is not None else load_settings()
        # Stores fall through to ``get_active_master_key()`` (the
        # active :class:`BucketSession`) when ``master_key_provider`` is
        # absent. The CLI root callback opens the session before any
        # consumer reaches this factory.
        blob_store = EncryptedBlobStore(root_dir=Path(resolved.aeat_blob_store_dir))
        _singleton_store = SecretStore(
            store_dir=Path(resolved.aeat_secret_store_dir),
            blob_store=blob_store,
        )
        return _singleton_store


def override_secret_store(store: SecretStore | None) -> None:
    """Test helper: install (or clear) a process-wide secret-store override.

    Args:
        store: The :class:`SecretStore` to install. ``None`` clears
            the override and reverts to the standard
            :func:`get_secret_store` resolution.
    """
    global _singleton_store
    with _factory_lock:
        _singleton_store = store


def _write_bytes_secure_fd(fd: int, payload: bytes) -> None:
    """Write ``payload`` through an already-opened file descriptor.

    The caller is responsible for opening the descriptor with the
    correct flags (``O_NOFOLLOW`` etc.) and closing it afterwards.
    Splitting the write from the open closes the TOCTOU window between
    ``mkstemp`` and the eventual write that would otherwise let a
    local attacker on shared ``/tmp`` symlink-replace the path.
    """
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise StorageValidationError(
                "secure tempfile write made no progress",
                context={**_MATERIALISATION_ERROR_CONTEXT, "operation": "write"},
                translated_message="errors.integrity.integrity_storage_validation",
            )
        offset += written


def _validate_tempfile_affix(value: str, *, field_name: str) -> str:
    if any(char in _FORBIDDEN_TEMPFILE_TOKEN_CHARS for char in value):
        raise StorageValidationError(
            "secure tempfile affix must not contain path separators",
            context={**_MATERIALISATION_ERROR_CONTEXT, "field": field_name},
            translated_message="errors.integrity.integrity_storage_validation",
        )
    if value in {".", ".."}:
        raise StorageValidationError(
            "secure tempfile affix must not be a dot path token",
            context={**_MATERIALISATION_ERROR_CONTEXT, "field": field_name},
            translated_message="errors.integrity.integrity_storage_validation",
        )
    return value


def _tempfile_name_parts(prefix: str, suffix: str) -> tuple[str, str]:
    safe_prefix = _validate_tempfile_affix(prefix, field_name="prefix")
    safe_suffix = _validate_tempfile_affix(suffix, field_name="suffix")
    return f"{safe_prefix}{_TEMPFILE_PREFIX_SEPARATOR}", safe_suffix


def _unlink_materialised_temp_path(tmp_path: Path) -> None:
    try:
        tmp_path.unlink()
    except FileNotFoundError:
        _log.debug("secret materialisation cleanup skipped missing temp path")


def _create_materialised_temp_path(
    payload: bytes,
    *,
    tempfile_prefix: str,
    tempfile_suffix: str,
) -> Path:
    # ``tempfile.mkstemp`` already creates the file with mode 0o600 on
    # POSIX (default). Writing directly through the returned fd
    # closes the TOCTOU window that would have otherwise existed
    # between ``os.close(fd)`` and a separate ``os.open(target,
    # O_CREAT|O_TRUNC)`` re-open: a local attacker on a shared
    # tempdir cannot symlink-replace a path that we never re-open.
    fd, tmp_path_str = tempfile.mkstemp(prefix=tempfile_prefix, suffix=tempfile_suffix)
    tmp_path = Path(tmp_path_str)
    fd_open = True
    try:
        _write_bytes_secure_fd(fd, payload)
        os.close(fd)
        fd_open = False
    except (OSError, StorageValidationError):
        if fd_open:
            try:
                os.close(fd)
            except OSError:
                _log.debug(
                    "secret materialisation fd close failed after write/setup failure",
                    exc_info=True,
                )
        _unlink_materialised_temp_path(tmp_path)
        raise
    return tmp_path


@contextmanager
def materialise_secret(
    key: str,
    *,
    store: SecretStore | None = None,
    prefix: str = _DEFAULT_TEMPFILE_PREFIX,
    suffix: str = _EMPTY_SUFFIX,
) -> Iterator[Path]:
    """Context-managed secure tempfile holding the secret value.

    The tempfile lives under the OS tempdir with mode ``0o600`` on
    POSIX (Windows inherits the parent ACL — out of scope for this
    helper). The file is unlinked on context exit, including on
    exception.

    Args:
        key: Natural key passed to :meth:`SecretStore.get`.
        store: Optional :class:`SecretStore` override. When ``None``,
            the process-wide singleton from :func:`get_secret_store`
            is used.
        prefix: Filename prefix for the tempfile. Defaults to
            ``aeat-secret``.
        suffix: Filename suffix (e.g. ``.json`` for a Google
            service-account JSON file). Defaults to empty.

    Yields:
        :class:`Path` to the materialised file.
    """
    tempfile_prefix, tempfile_suffix = _tempfile_name_parts(prefix, suffix)
    active_store = store if store is not None else get_secret_store()
    record = active_store.get(key)
    tmp_path = _create_materialised_temp_path(
        record.value,
        tempfile_prefix=tempfile_prefix,
        tempfile_suffix=tempfile_suffix,
    )
    try:
        yield tmp_path
    finally:
        _unlink_materialised_temp_path(tmp_path)


def export_to_temp_path(
    key: str,
    *,
    store: SecretStore | None = None,
    prefix: str = _DEFAULT_TEMPFILE_PREFIX,
    suffix: str = _EMPTY_SUFFIX,
) -> tuple[Path, Callable[[], None]]:
    """Return ``(path, cleanup)`` for callers that need the path beyond a ``with`` block.

    The caller is responsible for invoking ``cleanup()`` once the
    consumer no longer needs the path. ``cleanup()`` is idempotent:
    repeated calls are safe and cost nothing on the second-and-later
    invocations.

    Args:
        key: Natural key passed to :meth:`SecretStore.get`.
        store: Optional :class:`SecretStore` override.
        prefix: Filename prefix for the tempfile.
        suffix: Filename suffix.

    Returns:
        A ``(path, cleanup)`` tuple.
    """
    tempfile_prefix, tempfile_suffix = _tempfile_name_parts(prefix, suffix)
    active_store = store if store is not None else get_secret_store()
    record = active_store.get(key)
    tmp_path = _create_materialised_temp_path(
        record.value,
        tempfile_prefix=tempfile_prefix,
        tempfile_suffix=tempfile_suffix,
    )

    cleaned = False

    def _cleanup() -> None:
        nonlocal cleaned
        if cleaned:
            return
        _unlink_materialised_temp_path(tmp_path)
        cleaned = True

    return tmp_path, _cleanup


__all__ = [
    "export_to_temp_path",
    "get_secret_store",
    "materialise_secret",
    "override_secret_store",
]
