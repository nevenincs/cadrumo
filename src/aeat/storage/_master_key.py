"""Master-key acquisition for the at-rest crypto stack.

Three concrete providers implement the :class:`MasterKeyProvider`
protocol:

- :class:`KeyringMasterKeyProvider` — backed by the ``keyring`` package
  (Windows Credential Manager, macOS Keychain, Linux Secret Service via
  libsecret). The master key is stored under a fixed service name and
  account; on first use the provider mints a 32-byte random key and
  persists it.
- :class:`FileFallbackMasterKeyProvider` — backed by a passphrase-
  derived KEK (scrypt) wrapping an AES-256-GCM master key persisted
  alongside a per-store random salt.
- :class:`EphemeralMasterKeyProvider` — an in-memory provider used
  exclusively by tests; the key vanishes when the provider object is
  garbage-collected.

The :func:`get_master_key_provider` factory selects a provider per
:attr:`Settings.aeat_secret_store_backend`. The ``auto`` backend tries
the OS keychain and falls back to the file backend only when the
keychain is unusable. The ``keyring`` backend refuses to fall back; the
``file`` backend never consults the keychain.

The on-disk file backend persists three artefacts in
:attr:`Settings.aeat_secret_store_dir`:

- ``salt`` — 16 random bytes (read at startup, never rotated).
- ``master.key`` — the AES-256-GCM ciphertext of the master key, plus
  its 12-byte nonce, plus the 16-byte tag, base64-encoded.
- ``master.kdf`` — a small JSON document carrying the scrypt
  parameters used to derive the KEK from the operator's passphrase.
  This file is human-readable; only ``master.key`` is sensitive.

Passphrase resolution: ``AEAT_SECRET_PASSPHRASE`` env var is consulted
first; absent that, the passphrase is prompted interactively via
:func:`getpass.getpass`. The passphrase is cached in memory for the
process lifetime so subsequent provider calls do not re-prompt.
"""

from __future__ import annotations

import base64
import binascii
import getpass
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, runtime_checkable

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ..config import Settings

from ..logging import get_logger
from ._crypto import KEY_SIZE, EncryptedBlob, decrypt_record, encrypt_record
from .errors import (
    KeyringUnavailableError,
    MasterKeyUnavailableError,
    SecretStoreError,
)

_log = get_logger(__name__)

KEYRING_SERVICE: Final[str] = "aeat:secure-persistence"
"""Stable service identifier under which the keyring backend stores the key."""

KEYRING_USERNAME: Final[str] = "master"
"""Account identifier for the master-key entry in the OS keychain."""

PASSPHRASE_ENV_VAR: Final[str] = "AEAT_SECRET_PASSPHRASE"  # noqa: S105 — env var name, not a value
"""Environment variable consulted by the file backend before prompting."""

_SCRYPT_N: Final[int] = 2**17
"""scrypt cost parameter ``N`` (CPU/memory cost). 2**17 is OWASP-aligned."""

_SCRYPT_R: Final[int] = 8
"""scrypt block-mix parameter ``r``."""

_SCRYPT_P: Final[int] = 1
"""scrypt parallelism parameter ``p``."""

_SALT_SIZE: Final[int] = 16
"""Per-store salt size in bytes."""

_KDF_PARAMS_VERSION: Final[int] = 1
"""Bumped when the on-disk KDF parameter shape changes."""

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


@runtime_checkable
class MasterKeyProvider(Protocol):
    """Source of the master key used by every at-rest crypto consumer."""

    def get_master_key(self) -> bytes:
        """Return the 32-byte AES-256 master key.

        Raises:
            MasterKeyUnavailableError: If the master key cannot be
                acquired from this provider.
        """
        ...


class _KdfParameters(BaseModel):
    """On-disk record of the scrypt parameters used to derive the KEK."""

    model_config = _STRICT_FROZEN

    version: int = Field(default=_KDF_PARAMS_VERSION)
    algorithm: str = Field(default="scrypt")
    n: int
    r: int
    p: int
    salt_b64: str


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def _derive_kek(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a 32-byte KEK from the operator's passphrase and the per-store salt."""
    scrypt = Scrypt(salt=salt, length=KEY_SIZE, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return scrypt.derive(passphrase)


PassphraseCallback = Callable[[], str]
"""Pluggable hook for tests — callable returning the passphrase as a str."""


def _default_passphrase_callback() -> str:
    """Resolve the operator's passphrase from env or stdin."""
    env_value = os.environ.get(PASSPHRASE_ENV_VAR)
    if env_value:
        return env_value
    return getpass.getpass(prompt="AEAT secret-store passphrase: ")


class KeyringMasterKeyProvider:
    """OS-keychain-backed master-key provider.

    The provider lazily imports the ``keyring`` package and lazily
    queries the active backend. Any keyring exception (missing backend,
    locked store, refused write) is wrapped in
    :class:`KeyringUnavailableError`.
    """

    _lock: ClassVar[Lock] = Lock()
    _cache: ClassVar[bytes | None] = None

    def __init__(
        self,
        *,
        service: str = KEYRING_SERVICE,
        username: str = KEYRING_USERNAME,
    ) -> None:
        """Bind the provider to a keyring service and account.

        Args:
            service: Service identifier under which the master key is
                stored. Defaults to :data:`KEYRING_SERVICE`.
            username: Account identifier within that service. Defaults
                to :data:`KEYRING_USERNAME`.
        """
        self._service = service
        self._username = username

    def get_master_key(self) -> bytes:
        """Fetch (or mint and store) the master key via the OS keychain."""
        with KeyringMasterKeyProvider._lock:
            cached = KeyringMasterKeyProvider._cache
            if cached is not None:
                return cached
            try:
                import keyring
                from keyring.errors import KeyringError
            except ImportError as exc:  # pragma: no cover - keyring is a hard dep
                raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
            try:
                stored = keyring.get_password(self._service, self._username)
            except KeyringError as exc:
                raise KeyringUnavailableError(f"OS keychain refused get_password: {exc}") from exc
            except Exception as exc:  # pragma: no cover - defensive
                raise KeyringUnavailableError(f"OS keychain raised unexpectedly: {exc}") from exc
            if stored is not None:
                try:
                    key = _b64decode(stored)
                except (ValueError, binascii.Error) as exc:
                    raise KeyringUnavailableError(
                        "OS keychain returned a malformed master-key entry; clear it and re-run.",
                    ) from exc
                if len(key) != KEY_SIZE:
                    raise KeyringUnavailableError(
                        f"OS keychain master key has wrong size: {len(key)} (expected {KEY_SIZE}).",
                    )
                KeyringMasterKeyProvider._cache = key
                return key
            new_key = secrets.token_bytes(KEY_SIZE)
            try:
                keyring.set_password(self._service, self._username, _b64encode(new_key))
            except KeyringError as exc:
                raise KeyringUnavailableError(f"OS keychain refused set_password: {exc}") from exc
            except Exception as exc:  # pragma: no cover - defensive
                raise KeyringUnavailableError(f"OS keychain raised unexpectedly: {exc}") from exc
            _log.info("master key minted in OS keychain (service=%s)", self._service)
            KeyringMasterKeyProvider._cache = new_key
            return new_key

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Clear the in-process cache so tests can verify fetch paths cleanly."""
        with cls._lock:
            cls._cache = None


class FileFallbackMasterKeyProvider:
    """Encrypted-file-backed master-key provider.

    Persists ``salt`` and ``master.key`` (plus a human-readable
    ``master.kdf`` parameters document) under
    :attr:`Settings.aeat_secret_store_dir`. The KEK is derived from a
    passphrase via scrypt and wraps the master key with AES-256-GCM.
    """

    _lock: ClassVar[Lock] = Lock()
    _cached_passphrase: ClassVar[bytes | None] = None
    _cached_master_key: ClassVar[dict[Path, bytes]] = {}

    def __init__(
        self,
        *,
        store_dir: Path,
        passphrase_callback: PassphraseCallback | None = None,
    ) -> None:
        """Bind the provider to a store directory.

        Args:
            store_dir: Directory containing ``salt``, ``master.key``,
                and ``master.kdf``. Created on first use.
            passphrase_callback: Optional override for passphrase
                resolution. Defaults to
                :func:`_default_passphrase_callback`. Tests inject a
                stub that returns a deterministic value.
        """
        self._store_dir = Path(store_dir)
        self._passphrase_callback = passphrase_callback or _default_passphrase_callback

    @property
    def _salt_path(self) -> Path:
        return self._store_dir / "salt"

    @property
    def _kdf_params_path(self) -> Path:
        return self._store_dir / "master.kdf"

    @property
    def _master_key_path(self) -> Path:
        return self._store_dir / "master.key"

    def _resolve_passphrase(self) -> bytes:
        with FileFallbackMasterKeyProvider._lock:
            cached = FileFallbackMasterKeyProvider._cached_passphrase
            if cached is not None:
                return cached
            value = self._passphrase_callback()
            if not value:
                raise SecretStoreError(
                    "secret-store passphrase resolved to empty string; set "
                    f"{PASSPHRASE_ENV_VAR} or supply a non-empty value at the prompt.",
                )
            material = value.encode("utf-8")
            FileFallbackMasterKeyProvider._cached_passphrase = material
            return material

    def get_master_key(self) -> bytes:
        with FileFallbackMasterKeyProvider._lock:
            cached = FileFallbackMasterKeyProvider._cached_master_key.get(self._store_dir)
            if cached is not None:
                return cached
        self._store_dir.mkdir(parents=True, exist_ok=True)
        passphrase = self._resolve_passphrase()
        if self._master_key_path.exists() and self._kdf_params_path.exists() and self._salt_path.exists():
            key = self._unwrap_existing(passphrase)
        else:
            key = self._mint_new(passphrase)
        with FileFallbackMasterKeyProvider._lock:
            FileFallbackMasterKeyProvider._cached_master_key[self._store_dir] = key
        return key

    def _unwrap_existing(self, passphrase: bytes) -> bytes:
        try:
            params = _KdfParameters.model_validate_json(self._kdf_params_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MasterKeyUnavailableError(
                f"failed to parse KDF parameters at {self._kdf_params_path}: {exc}",
            ) from exc
        if params.version != _KDF_PARAMS_VERSION:
            raise MasterKeyUnavailableError(
                f"unsupported KDF parameters version {params.version}; expected {_KDF_PARAMS_VERSION}.",
            )
        if params.algorithm != "scrypt":
            raise MasterKeyUnavailableError(
                f"unsupported KDF algorithm {params.algorithm!r}; expected 'scrypt'.",
            )
        try:
            salt = _b64decode(params.salt_b64)
        except (ValueError, binascii.Error) as exc:
            raise MasterKeyUnavailableError("KDF parameters carry malformed salt.") from exc
        kek = self._derive_kek_with_params(passphrase, salt, params)
        try:
            wire = base64.b64decode(self._master_key_path.read_bytes(), validate=True)
            blob = EncryptedBlob.from_wire(wire)
        except Exception as exc:
            raise MasterKeyUnavailableError(
                f"failed to read wrapped master key at {self._master_key_path}: {exc}",
            ) from exc
        try:
            return decrypt_record(blob, key=kek, associated_data=b"aeat.master-key.v1")
        except Exception as exc:
            raise MasterKeyUnavailableError(
                "failed to decrypt master key; passphrase may be wrong or the file may be tampered with.",
            ) from exc

    def _mint_new(self, passphrase: bytes) -> bytes:
        salt = secrets.token_bytes(_SALT_SIZE)
        params = _KdfParameters(
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            salt_b64=_b64encode(salt),
        )
        kek = self._derive_kek_with_params(passphrase, salt, params)
        master_key = secrets.token_bytes(KEY_SIZE)
        blob = encrypt_record(master_key, key=kek, associated_data=b"aeat.master-key.v1")
        self._kdf_params_path.write_text(params.model_dump_json(), encoding="utf-8")
        self._master_key_path.write_bytes(base64.b64encode(blob.to_wire()))
        self._salt_path.write_bytes(salt)
        _log.info("master key minted in encrypted file at %s", self._master_key_path)
        return master_key

    @staticmethod
    def _derive_kek_with_params(passphrase: bytes, salt: bytes, params: _KdfParameters) -> bytes:
        scrypt = Scrypt(salt=salt, length=KEY_SIZE, n=params.n, r=params.r, p=params.p)
        return scrypt.derive(passphrase)

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Clear caches so tests can verify mint vs unwrap paths cleanly."""
        with cls._lock:
            cls._cached_passphrase = None
            cls._cached_master_key.clear()


class EphemeralMasterKeyProvider:
    """In-memory master-key provider used exclusively by tests.

    The key is generated once per provider instance and never persisted.
    """

    def __init__(self, *, key: bytes | None = None) -> None:
        """Construct a provider with an optional fixed key.

        Args:
            key: Optional 32-byte key. When ``None``, a fresh random
                key is minted.
        """
        if key is None:
            key = secrets.token_bytes(KEY_SIZE)
        if len(key) != KEY_SIZE:
            raise SecretStoreError(
                f"ephemeral master key must be {KEY_SIZE} bytes; got {len(key)}",
            )
        self._key = key

    def get_master_key(self) -> bytes:
        return self._key


def get_master_key_provider(
    *,
    backend: str | None = None,
    settings_override: Settings | None = None,
    passphrase_callback: PassphraseCallback | None = None,
) -> MasterKeyProvider:
    """Resolve the active :class:`MasterKeyProvider` per project settings.

    Args:
        backend: Optional explicit backend selector (``auto`` /
            ``keyring`` / ``file``). Overrides the value resolved from
            settings.
        settings_override: Optional pre-built settings instance. Tests
            inject a settings stub bound to ``tmp_path`` so the file
            backend writes inside the test sandbox.
        passphrase_callback: Optional override for passphrase
            resolution; only consulted by the file backend.

    Returns:
        A live provider instance honouring the resolved backend.

    Raises:
        KeyringUnavailableError: When the resolved backend is
            ``keyring`` and no usable keychain is detected.
        SecretStoreError: When ``backend`` is not a known value.
    """
    from ..config import SecretStoreBackend, load_settings  # local import to avoid cycles

    settings = settings_override if settings_override is not None else load_settings()
    backend_value = settings.aeat_secret_store_backend.value if backend is None else backend
    try:
        resolved = SecretStoreBackend(backend_value)
    except ValueError as exc:
        raise SecretStoreError(f"unknown secret-store backend: {backend_value!r}") from exc
    store_dir = Path(settings.aeat_secret_store_dir)
    if resolved is SecretStoreBackend.KEYRING:
        provider = KeyringMasterKeyProvider()
        # Probe early so callers see the failure at construction.
        provider.get_master_key()
        return provider
    if resolved is SecretStoreBackend.FILE:
        return FileFallbackMasterKeyProvider(
            store_dir=store_dir,
            passphrase_callback=passphrase_callback,
        )
    keyring_provider = KeyringMasterKeyProvider()
    try:
        keyring_provider.get_master_key()
        return keyring_provider
    except KeyringUnavailableError as exc:
        _log.info("OS keychain unavailable (%s); falling back to encrypted-file backend", exc)
        return FileFallbackMasterKeyProvider(
            store_dir=store_dir,
            passphrase_callback=passphrase_callback,
        )
