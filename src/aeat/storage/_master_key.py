"""Master-key acquisition for the at-rest crypto stack.

Three concrete providers implement the :class:`MasterKeyProvider`
protocol:

- :class:`KeyringMasterKeyProvider` — backed by the ``keyring`` package
  (Windows Credential Manager, macOS Keychain, Linux Secret Service via
  libsecret). The master key is stored under a fixed service name and
  account; on first use the provider mints a 32-byte random key and
  persists it.
- :class:`FileFallbackMasterKeyProvider` — backed by a passphrase-
  derived KEK (Argon2id) wrapping an AES-256-GCM master key persisted
  alongside a per-store random salt. Wave-12 migrated the KDF from
  scrypt to Argon2id; the historical (v1, scrypt) format is no longer
  loadable and must be migrated via :func:`migrate_master_key_kdf`.
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
- ``master.kdf`` — a small JSON document carrying the Argon2id
  parameters used to derive the KEK from the operator's passphrase.
  This file is human-readable; only ``master.key`` is sensitive.

Passphrase resolution: ``AEAT_SECRET_PASSPHRASE`` env var is consulted
first; absent that, the passphrase is prompted interactively via
:func:`getpass.getpass`. The passphrase is cached in memory for the
process lifetime so subsequent provider calls do not re-prompt.
"""

from __future__ import annotations

import atexit
import base64
import binascii
import contextlib
import getpass
import json
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, ClassVar, Final, Literal, Protocol, runtime_checkable

from argon2.low_level import Type as _Argon2Type
from argon2.low_level import hash_secret_raw as _argon2_hash_secret_raw
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt as _LegacyScrypt
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ..config import Settings

from ..logging import get_logger
from ._crypto import KEY_SIZE, EncryptedBlob, decrypt_record, encrypt_record
from ._lock import exclusive_file_lock
from .errors import (
    KeyringUnavailableError,
    MasterKeyKdfVersionError,
    MasterKeyPassphraseMismatchError,
    MasterKeyUnavailableError,
    SecretStoreError,
    UnsecuredModeRefusedError,
)

_log = get_logger(__name__)

KEYRING_SERVICE: Final[str] = "aeat:secure-persistence"
"""Stable service identifier under which the keyring backend stores the key."""

KEYRING_USERNAME: Final[str] = "master"
"""Account identifier for the master-key entry in the OS keychain."""

PASSPHRASE_ENV_VAR: Final[str] = "AEAT_SECRET_PASSPHRASE"  # noqa: S105 — env var name, not a value
"""Environment variable consulted by the file backend before prompting."""

_ARGON2_MEMORY_COST_KIB: Final[int] = 19 * 1024
"""Argon2id ``memory_cost`` in KiB (19 MiB — OWASP-current top tier)."""

_ARGON2_TIME_COST: Final[int] = 2
"""Argon2id ``time_cost`` (number of iterations) — OWASP-current top tier."""

_ARGON2_PARALLELISM: Final[int] = 1
"""Argon2id ``parallelism`` — OWASP-current top tier."""

_SALT_SIZE: Final[int] = 16
"""Per-store salt size in bytes."""

_KDF_PARAMS_VERSION: Final[int] = 2
"""Bumped when the on-disk KDF parameter shape changes.

* v1: scrypt (N=2**17, r=8, p=1). Wave-1 through wave-11.
* v2: Argon2id (memory_cost=19 MiB, time_cost=2, parallelism=1). Wave-12.
"""

_LEGACY_KDF_PARAMS_VERSION: Final[int] = 1
"""Wave-1..11 KDF parameter version. Read-only — only the migration helper consumes it."""

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
    """On-disk record of the Argon2id parameters used to derive the KEK.

    The active (v2) shape. Loading a v1 (scrypt) ``master.kdf`` against
    this model fails by design — the version-gate in
    :meth:`FileFallbackMasterKeyProvider._unwrap_existing` produces a
    typed :class:`MasterKeyKdfVersionError` pointing the operator at
    the migration tool instead of letting a strict-pydantic
    ``ValidationError`` bubble up unannotated.
    """

    model_config = _STRICT_FROZEN

    version: int = Field(default=_KDF_PARAMS_VERSION)
    algorithm: Literal["argon2id"] = Field(default="argon2id")
    memory_cost: int
    time_cost: int
    parallelism: int
    salt_b64: str


class _LegacyKdfParameters(BaseModel):
    """Parser for v1 (scrypt) ``master.kdf`` files.

    Used **only** by :func:`migrate_master_key_kdf` when re-wrapping an
    existing master key into the v2 (Argon2id) format. The substrate's
    regular load path never instantiates this model.
    """

    model_config = _STRICT_FROZEN

    version: Literal[1]
    algorithm: Literal["scrypt"]
    n: int
    r: int
    p: int
    salt_b64: str


class MigrationResult(BaseModel):
    """Outcome of a one-shot ``master.kdf`` migration run.

    Attributes:
        migrated: ``1`` if the store was on v1 and is now v2; ``0`` if
            the store was already v2 and required no action.
        skipped: ``1`` if the store was already v2; ``0`` otherwise.
        store_dir: The store directory the migration acted on.
    """

    model_config = _STRICT_FROZEN

    migrated: int = Field(default=0, ge=0, le=1)
    skipped: int = Field(default=0, ge=0, le=1)
    store_dir: Path


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def atomic_write_secure_bytes(target: Path, payload: bytes) -> None:
    """Atomically write ``payload`` to ``target`` with mode ``0o600``.

    Writes to a sibling tempfile created with ``O_CREAT|O_EXCL`` and
    ``mode=0o600`` so the file lands restricted from creation (no
    chmod-after-close TOCTOU window where a sensitive payload is
    briefly readable by other users on the host). ``os.fsync``s the
    fd, then ``os.replace`` atomically swaps the tempfile in. A crash
    between create and replace leaves the original ``target``
    untouched; the orphan tempfile is removed on the error path.

    Use this for any persisted sensitive material (master-key state,
    portable export bundles) where partial writes or world-readable
    intermediate states are unacceptable. On Windows the mode argument
    is ignored and the file inherits the parent directory's ACL; the
    confidentiality posture there depends on per-user profile
    permissions, not on POSIX mode bits.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f"{target.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOINHERIT"):
        flags |= os.O_NOINHERIT  # type: ignore[attr-defined]
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd = os.open(tmp_path, flags, 0o600)
    try:
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _zeroise(buffer: bytearray | None) -> None:
    """Best-effort overwrite of a mutable buffer with zero bytes.

    Python's `bytes` is immutable so true zeroisation requires a
    `bytearray`. The substrate's master-key + passphrase caches use
    bytearray buffers so a memory-disclosure bug elsewhere (e.g. a
    debug traceback printing locals) does not surface the key bytes.
    The atexit hook (registered below) calls this on every cached
    buffer at shutdown.
    """
    if buffer is None:
        return
    for i in range(len(buffer)):
        buffer[i] = 0


def _derive_kek(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a 32-byte KEK from the operator's passphrase and the per-store salt.

    Uses Argon2id with the OWASP-current top-tier parameters
    (``memory_cost=19 MiB, time_cost=2, parallelism=1``). The result is
    a 32-byte KEK suitable for AES-256-GCM-wrapping the master key.
    """
    return _argon2_hash_secret_raw(
        secret=passphrase,
        salt=salt,
        time_cost=_ARGON2_TIME_COST,
        memory_cost=_ARGON2_MEMORY_COST_KIB,
        parallelism=_ARGON2_PARALLELISM,
        hash_len=KEY_SIZE,
        type=_Argon2Type.ID,
    )


def _derive_legacy_scrypt_kek(passphrase: bytes, salt: bytes, params: _LegacyKdfParameters) -> bytes:
    """Derive the 32-byte KEK under the v1 (scrypt) parameter set.

    Used **only** by :func:`migrate_master_key_kdf`. Once a store has
    been migrated to v2, this function is no longer reachable from the
    regular load path.
    """
    scrypt = _LegacyScrypt(salt=salt, length=KEY_SIZE, n=params.n, r=params.r, p=params.p)
    return scrypt.derive(passphrase)


PassphraseCallback = Callable[[], str]
"""Pluggable hook for tests — callable returning the passphrase as a str."""


def _default_passphrase_callback() -> str:
    """Resolve the operator's passphrase from env or stdin.

    When the env-var path is taken, the value is consumed (popped) from
    ``os.environ`` after a successful read so child processes spawned
    later in the lifecycle do NOT inherit the passphrase. The in-memory
    cache in :class:`FileFallbackMasterKeyProvider` is sufficient for
    the parent process; subprocesses that need the passphrase must
    re-supply it explicitly.

    Trailing CRLF is stripped (some shells append it via
    ``$(cat .secret)``), but interior whitespace is preserved (some
    passphrase policies require it).
    """
    env_value = os.environ.get(PASSPHRASE_ENV_VAR)
    if env_value:
        # Strip trailing CRLF only — the shell often appends it.
        normalized = env_value.rstrip("\r\n")
        if not normalized:
            raise SecretStoreError(
                f"{PASSPHRASE_ENV_VAR} is set to whitespace-only; supply a non-empty passphrase.",
            )
        # Pop after read so child processes do not inherit the value.
        os.environ.pop(PASSPHRASE_ENV_VAR, None)
        return normalized
    return getpass.getpass(prompt="AEAT secret-store passphrase: ")


class KeyringMasterKeyProvider:
    """OS-keychain-backed master-key provider.

    The provider lazily imports the ``keyring`` package and lazily
    queries the active backend. Before any read or write, the active
    keyring backend is inspected; the no-op ``fail.Keyring`` and
    ``null.Keyring`` backends raise :class:`KeyringUnavailableError`
    so the auto fallback can route to the file backend without
    silently dropping the master key into a sink.

    The in-process cache is keyed by ``(service, username)`` so two
    providers bound to distinct identities never share key material.
    """

    _lock: ClassVar[Lock] = Lock()
    _cache: ClassVar[dict[tuple[str, str], bytearray]] = {}

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

    @staticmethod
    def _probe_backend() -> None:
        """Refuse no-op keyring backends up-front.

        ``keyring.backends.fail.Keyring`` and ``keyring.backends.null.Keyring``
        are placeholder backends installed when the platform has no
        usable keychain. ``set_password`` on these silently succeeds
        (or raises ``NoKeyringError``) but never persists the value, so
        the master key would be lost on the next process restart.
        """
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - keyring is a hard dep
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        try:
            from keyring.backends import fail as _fail_backend

            backend = keyring.get_keyring()
        except Exception as exc:  # pragma: no cover - defensive
            raise KeyringUnavailableError(f"unable to inspect OS keychain backend: {exc}") from exc
        if isinstance(backend, _fail_backend.Keyring):
            raise KeyringUnavailableError(
                f"OS keychain backend is the no-op fail.Keyring (resolved {type(backend).__name__}); "
                "install a usable backend or set AEAT_SECRET_STORE_BACKEND=file.",
            )
        # Null backend is best-detected by class name to avoid an import
        # against a module that may not exist on every platform.
        if type(backend).__name__ == "Keyring" and type(backend).__module__.endswith(".null"):
            raise KeyringUnavailableError(
                "OS keychain backend is the no-op null.Keyring; "
                "install a usable backend or set AEAT_SECRET_STORE_BACKEND=file.",
            )

    def get_master_key(self) -> bytes:
        """Fetch (or mint and store) the master key via the OS keychain."""
        cache_key = (self._service, self._username)
        with KeyringMasterKeyProvider._lock:
            cached = KeyringMasterKeyProvider._cache.get(cache_key)
            if cached is not None:
                return bytes(cached)
            self._probe_backend()
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
                KeyringMasterKeyProvider._cache[cache_key] = bytearray(key)
                return key
            new_key = secrets.token_bytes(KEY_SIZE)
            try:
                keyring.set_password(self._service, self._username, _b64encode(new_key))
            except KeyringError as exc:
                raise KeyringUnavailableError(f"OS keychain refused set_password: {exc}") from exc
            except Exception as exc:  # pragma: no cover - defensive
                raise KeyringUnavailableError(f"OS keychain raised unexpectedly: {exc}") from exc
            # Read back to verify the backend actually persisted the value.
            try:
                roundtrip = keyring.get_password(self._service, self._username)
            except KeyringError as exc:
                raise KeyringUnavailableError(f"OS keychain refused round-trip read: {exc}") from exc
            if roundtrip is None or _b64decode(roundtrip) != new_key:
                raise KeyringUnavailableError(
                    "OS keychain accepted set_password but the round-trip read disagreed; "
                    "the backend may be a silent dropper.",
                )
            _log.info("master key minted in OS keychain (service=%s)", self._service)
            KeyringMasterKeyProvider._cache[cache_key] = bytearray(new_key)
            return new_key

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Clear the in-process cache so tests can verify fetch paths cleanly."""
        with cls._lock:
            for buf in cls._cache.values():
                _zeroise(buf)
            cls._cache.clear()


class FileFallbackMasterKeyProvider:
    """Encrypted-file-backed master-key provider.

    Persists ``salt`` and ``master.key`` (plus a human-readable
    ``master.kdf`` parameters document) under
    :attr:`Settings.aeat_secret_store_dir`. The KEK is derived from a
    passphrase via scrypt and wraps the master key with AES-256-GCM.
    """

    _lock: ClassVar[Lock] = Lock()
    _cached_passphrase: ClassVar[bytearray | None] = None
    _cached_master_key: ClassVar[dict[Path, bytearray]] = {}

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
                return bytes(cached)
            value = self._passphrase_callback()
            if not value:
                raise SecretStoreError(
                    "secret-store passphrase resolved to empty string; set "
                    f"{PASSPHRASE_ENV_VAR} or supply a non-empty value at the prompt.",
                )
            material = bytearray(value.encode("utf-8"))
            FileFallbackMasterKeyProvider._cached_passphrase = material
            return bytes(material)

    def get_master_key(self) -> bytes:
        # Normalise the path so casing / relative-vs-absolute differences
        # do not produce two cache entries for the same logical store
        # (vs-M-1).
        self._store_dir.mkdir(parents=True, exist_ok=True)
        cache_key = self._store_dir.resolve()
        with FileFallbackMasterKeyProvider._lock:
            cached = FileFallbackMasterKeyProvider._cached_master_key.get(cache_key)
            if cached is not None:
                return bytes(cached)
        passphrase = self._resolve_passphrase()
        # Serialise the unwrap-or-mint decision under the on-disk lock
        # so two first-time callers cannot both decide to mint and then
        # race-write conflicting master.key + master.kdf pairs. Re-check
        # file existence inside the lock; the second caller will see
        # the artefacts the first caller wrote and route to unwrap.
        lock_target = self._store_dir / "master.lock"
        with exclusive_file_lock(lock_target):
            if self._master_key_path.exists() and self._kdf_params_path.exists() and self._salt_path.exists():
                key = self._unwrap_existing(passphrase)
            else:
                key = self._mint_new(passphrase)
        with FileFallbackMasterKeyProvider._lock:
            FileFallbackMasterKeyProvider._cached_master_key[cache_key] = bytearray(key)
        return key

    def _unwrap_existing(self, passphrase: bytes) -> bytes:
        raw_text = self._kdf_params_path.read_text(encoding="utf-8")
        # Version-gate before strict pydantic parsing so a v1 file
        # produces a typed runbook-pointing error instead of a raw
        # ValidationError.
        try:
            preview = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise MasterKeyUnavailableError(
                f"failed to parse KDF parameters at {self._kdf_params_path}: {exc}",
            ) from exc
        if not isinstance(preview, dict):
            raise MasterKeyUnavailableError(
                f"master.kdf at {self._kdf_params_path} must be a JSON object, got {type(preview).__name__}",
            )
        on_disk_version = preview.get("version")
        if on_disk_version != _KDF_PARAMS_VERSION:
            raise MasterKeyKdfVersionError(
                f"master.kdf at {self._kdf_params_path} is version {on_disk_version!r}; "
                f"this build expects version {_KDF_PARAMS_VERSION}. "
                "Run `aeat security migrate-master-key-kdf` to upgrade.",
            )
        try:
            params = _KdfParameters.model_validate_json(raw_text)
        except Exception as exc:
            raise MasterKeyUnavailableError(
                f"failed to parse KDF parameters at {self._kdf_params_path}: {exc}",
            ) from exc
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
            # Distinguish passphrase-mismatch from material-missing so
            # the CLI can render an actionable hint
            # (`aeat security recover --recovery-key` for forgotten
            # passphrase vs `aeat security provision` for absent
            # material).
            raise MasterKeyPassphraseMismatchError(
                "passphrase did not unlock the master key at "
                f"{self._master_key_path}; verify the passphrase or use "
                "`aeat security recover --recovery-key`.",
            ) from exc

    def _mint_new(self, passphrase: bytes) -> bytes:
        salt = secrets.token_bytes(_SALT_SIZE)
        params = _KdfParameters(
            memory_cost=_ARGON2_MEMORY_COST_KIB,
            time_cost=_ARGON2_TIME_COST,
            parallelism=_ARGON2_PARALLELISM,
            salt_b64=_b64encode(salt),
        )
        kek = self._derive_kek_with_params(passphrase, salt, params)
        master_key = secrets.token_bytes(KEY_SIZE)
        blob = encrypt_record(master_key, key=kek, associated_data=b"aeat.master-key.v1")
        # Restrict directory permissions on POSIX so the wrapped master
        # key, the salt, and the KDF parameters cannot be world-read.
        # On Windows os.chmod is a no-op; POSIX gets 0o700 on the dir
        # and 0o600 on every file. icacls hardening is out of scope
        # here (the broader session-state pattern handles that).
        self._restrict_dir_permissions(self._store_dir)
        self._write_bytes_secure(
            self._kdf_params_path,
            params.model_dump_json().encode("utf-8"),
        )
        self._write_bytes_secure(
            self._master_key_path,
            base64.b64encode(blob.to_wire()),
        )
        self._write_bytes_secure(self._salt_path, salt)
        _log.info("master key minted in encrypted file at %s", self._master_key_path)
        return master_key

    def complete_recovery(self, master_key: bytes) -> None:
        """Re-mint the file-fallback artefacts under recovered key bytes.

        Writes ``master.kdf``, ``master.key``, and ``salt`` for the
        operator's *current* passphrase (via the configured callback),
        wrapping ``master_key`` under a freshly-derived Argon2id KEK.
        The three artefacts are written via the atomic
        tempfile-and-replace pattern so a crash between writes leaves
        the existing on-disk state untouched.

        Use after a recovery-key unwrap (`unwrap_master_key`) to bind
        the recovered master-key bytes to a new passphrase. The
        substrate's in-process cache is invalidated so subsequent
        ``get_master_key()`` calls re-read the freshly-written
        artefacts under the new passphrase.

        Args:
            master_key: The 32-byte recovered master-key value.

        Raises:
            SecretStoreError: When the master key has the wrong
                length, the resolved passphrase is empty, or the
                target directory is not writable.
        """
        if len(master_key) != KEY_SIZE:
            raise SecretStoreError(
                f"recovered master key must be {KEY_SIZE} bytes; got {len(master_key)}",
            )
        # Drop any stale cached state so the new artefacts are picked
        # up by subsequent get_master_key() calls (and so the cached
        # passphrase is freshly resolved against the operator's
        # current shell environment).
        FileFallbackMasterKeyProvider._reset_for_tests()
        passphrase = self._resolve_passphrase()
        salt = secrets.token_bytes(_SALT_SIZE)
        params = _KdfParameters(
            memory_cost=_ARGON2_MEMORY_COST_KIB,
            time_cost=_ARGON2_TIME_COST,
            parallelism=_ARGON2_PARALLELISM,
            salt_b64=_b64encode(salt),
        )
        kek = self._derive_kek_with_params(passphrase, salt, params)
        blob = encrypt_record(master_key, key=kek, associated_data=b"aeat.master-key.v1")
        self._restrict_dir_permissions(self._store_dir)
        atomic_write_secure_bytes(
            self._kdf_params_path,
            params.model_dump_json().encode("utf-8"),
        )
        atomic_write_secure_bytes(
            self._master_key_path,
            base64.b64encode(blob.to_wire()),
        )
        atomic_write_secure_bytes(self._salt_path, salt)
        with FileFallbackMasterKeyProvider._lock:
            FileFallbackMasterKeyProvider._cached_master_key[self._store_dir.resolve()] = bytearray(master_key)
        _log.info(
            "master key recovered and re-wrapped under new passphrase at %s",
            self._master_key_path,
        )

    @staticmethod
    def _restrict_dir_permissions(target: Path) -> None:
        """Chmod ``target`` to 0o700 on POSIX; no-op on Windows."""
        if os.name == "posix":
            try:
                os.chmod(target, 0o700)
            except OSError:  # pragma: no cover - best-effort
                _log.debug("chmod 0o700 failed on %s; continuing", target)

    @staticmethod
    def _write_bytes_secure(target: Path, payload: bytes) -> None:
        """Write ``payload`` to ``target`` with mode 0o600 on POSIX.

        Uses ``os.open(O_WRONLY|O_CREAT|O_TRUNC, 0o600)`` on POSIX so
        the file lands restricted from creation rather than relying on
        a chmod after the fact (which has a TOCTOU window). On Windows
        the mode argument is ignored and the file inherits the parent
        directory's ACL; the file backend's confidentiality posture on
        Windows depends on per-user profile permissions plus the
        operator's passphrase, not on POSIX mode bits.
        """
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        # Avoid inheriting handles into child processes on Windows.
        if hasattr(os, "O_NOINHERIT"):
            flags |= os.O_NOINHERIT  # type: ignore[attr-defined]
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        fd = os.open(target, flags, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)

    @staticmethod
    def _derive_kek_with_params(passphrase: bytes, salt: bytes, params: _KdfParameters) -> bytes:
        return _argon2_hash_secret_raw(
            secret=passphrase,
            salt=salt,
            time_cost=params.time_cost,
            memory_cost=params.memory_cost,
            parallelism=params.parallelism,
            hash_len=KEY_SIZE,
            type=_Argon2Type.ID,
        )

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Clear caches so tests can verify mint vs unwrap paths cleanly."""
        with cls._lock:
            _zeroise(cls._cached_passphrase)
            cls._cached_passphrase = None
            for buf in cls._cached_master_key.values():
                _zeroise(buf)
            cls._cached_master_key.clear()


def _purge_caches_at_exit() -> None:
    """atexit hook: zeroise every cached key buffer at process shutdown.

    sec-M-1 hardening — a memory-disclosure bug elsewhere in the
    process (or a post-mortem core dump) cannot surface key bytes
    that have been overwritten with zeros.
    """
    KeyringMasterKeyProvider._reset_for_tests()
    FileFallbackMasterKeyProvider._reset_for_tests()


atexit.register(_purge_caches_at_exit)


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


# Published deterministic key for the unsecured-mode provider. Public by
# design — the goal is to keep the substrate's encryption pipeline intact
# (every record is still a CipherEnvelope / EncryptedBlob) while making
# the wrapping key trivially recoverable so testing / educational /
# throwaway scenarios do not require key management. Provides ZERO
# confidentiality. The hostile-named env var + NIF-canary refusal at
# profile-load time guard against accidental real-data use.
_UNSECURED_KEY_PREFIX: Final[bytes] = b"AEAT_UNSECURED_TEST_KEY"
_UNSECURED_PUBLISHED_KEY: Final[bytes] = _UNSECURED_KEY_PREFIX + b"\x00" * (KEY_SIZE - len(_UNSECURED_KEY_PREFIX))
assert len(_UNSECURED_PUBLISHED_KEY) == KEY_SIZE


class UnsecuredMasterKeyProvider:
    """Master-key provider for testing / throwaway scenarios.

    Returns a published deterministic 32-byte master key. The substrate's
    encryption pipeline is unchanged; only the wrapping key is publicly
    known. Provides **ZERO confidentiality**.

    Activation requires both signals:

    - ``AEAT_ALLOW_UNENCRYPTED=1`` environment variable (the hostile-
      named opt-out gate).
    - ``aeat_secret_store_backend=unsecured`` setting (or equivalent
      explicit backend selection at the substrate boundary).

    Refused at profile-load time when the operator profile carries a
    valid NIF/NIE/CIF (NIF-canary) — see :func:`refuse_unsecured_with_real_nif`
    in the consumer modules. Real tax data is incompatible with a
    published deterministic master key.
    """

    def get_master_key(self) -> bytes:
        return _UNSECURED_PUBLISHED_KEY


# Synthetic-NIF allow-list: tax-id-shaped strings that are valid under
# the Spanish checksum algorithm but conventionally used as placeholders
# in fixtures, tutorials, and tests. Any tax-id that is NOT in this set
# AND is structurally valid is treated as REAL and refused by the
# unsecured-mode canary. The list is intentionally small — tightening
# the canary at the boundary is preferred over a permissive heuristic.
_SYNTHETIC_TAX_IDS: Final[frozenset[str]] = frozenset(
    {
        "00000000T",  # all-zero NIF body — Hacienda's documented placeholder.
        "X0000000T",  # all-zero NIE body.
        "Z0000000T",  # all-zero NIE body, alt prefix.
        "Y0000000Z",  # all-zero NIE body, alt prefix + check.
        "B00000000",  # all-zero CIF body, common test prefix.
    }
)


def looks_like_real_tax_id(value: str) -> bool:
    """Return ``True`` when ``value`` parses as a real Spanish tax id.

    Used by the unsecured-mode NIF-canary to refuse the unsecured
    backend whenever the operator profile carries a real NIF / NIE /
    CIF. Synthetic placeholders (all-zero bodies, documented test
    sentinels — see :data:`_SYNTHETIC_TAX_IDS`) return ``False``.

    Args:
        value: Raw tax identifier (already-canonical or operator-input).

    Returns:
        ``True`` when the value validates under the Hacienda checksum
        algorithm AND is not a synthetic placeholder. ``False`` for
        invalid inputs and for synthetic placeholders alike — both
        cases are safe to allow under the unsecured backend.
    """
    from ..financial.invoices._validators import validate_spanish_tax_id

    try:
        canonical = validate_spanish_tax_id(value)
    except ValueError:
        return False
    return canonical not in _SYNTHETIC_TAX_IDS


def refuse_unsecured_with_real_nif(
    tax_id: str,
    *,
    provider: MasterKeyProvider,
) -> None:
    """Refuse the unsecured backend when the operator profile is real.

    Called at the profile-load / profile-write boundary. When the active
    master-key provider is :class:`UnsecuredMasterKeyProvider` AND the
    profile's tax id parses as a real NIF / NIE / CIF (per
    :func:`looks_like_real_tax_id`), raises
    :class:`UnsecuredModeRefusedError`. No-op when the provider is any
    other class.

    Args:
        tax_id: The operator profile's tax id.
        provider: The active master-key provider.

    Raises:
        UnsecuredModeRefusedError: When the unsecured backend is active
            and the tax id is real.
    """
    if not isinstance(provider, UnsecuredMasterKeyProvider):
        return
    if looks_like_real_tax_id(tax_id):
        raise UnsecuredModeRefusedError(
            f"unsecured master-key backend is incompatible with the "
            f"real tax id {tax_id!r}; either remove "
            "AEAT_ALLOW_UNENCRYPTED=1 / aeat_secret_store_backend=unsecured, "
            "or use a synthetic placeholder (e.g. '00000000T').",
        )


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
    if resolved is SecretStoreBackend.UNSECURED:
        # Hostile-named opt-out gate: the unsecured backend requires the
        # operator to explicitly set AEAT_ALLOW_UNENCRYPTED=1. Refuse
        # otherwise. The NIF-canary that fences off real tax data lives
        # at the profile-load boundary (see consumer modules).
        if not settings.aeat_allow_unencrypted:
            raise UnsecuredModeRefusedError(
                "aeat_secret_store_backend='unsecured' requires "
                "AEAT_ALLOW_UNENCRYPTED=1. The unsecured backend uses a "
                "published deterministic master key and provides ZERO "
                "confidentiality; intended for testing / throwaway data only.",
            )
        return UnsecuredMasterKeyProvider()
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


def migrate_master_key_kdf(
    *,
    store_dir: Path,
    passphrase: bytes,
) -> MigrationResult:
    """One-shot scrypt -> Argon2id migration of the file-fallback ``master.kdf``.

    Reads the v1 (scrypt) on-disk parameters, derives the legacy KEK,
    decrypts the wrapped master key, derives a fresh KEK under
    Argon2id with the **same per-store salt + same passphrase**,
    re-wraps the master key, and atomically replaces ``master.kdf`` +
    ``master.key``. The on-disk salt file is untouched.

    The function is resume-idempotent: on a store that is already at
    v2 it returns ``MigrationResult(skipped=1)`` without rewriting any
    artefact.

    Args:
        store_dir: Directory containing ``salt``, ``master.key``, and
            ``master.kdf``. Must already exist.
        passphrase: The operator's passphrase as raw bytes (UTF-8
            encoded). Must match the passphrase used to write the
            existing v1 store; mismatch produces
            :class:`MasterKeyUnavailableError` with the v1 store
            untouched.

    Returns:
        A :class:`MigrationResult` recording whether the migration
        ran or was a no-op.

    Raises:
        MasterKeyUnavailableError: If the on-disk store is malformed,
            the passphrase does not unwrap the existing master key, or
            an I/O error prevents the atomic rewrite.
    """
    store_dir = Path(store_dir).resolve()
    kdf_params_path = store_dir / "master.kdf"
    master_key_path = store_dir / "master.key"
    salt_path = store_dir / "salt"
    for required in (kdf_params_path, master_key_path, salt_path):
        if not required.exists():
            raise MasterKeyUnavailableError(
                f"required artefact missing for KDF migration: {required}",
            )

    raw_text = kdf_params_path.read_text(encoding="utf-8")
    try:
        preview = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise MasterKeyUnavailableError(
            f"failed to parse master.kdf at {kdf_params_path}: {exc}",
        ) from exc
    if not isinstance(preview, dict):
        raise MasterKeyUnavailableError(
            f"master.kdf at {kdf_params_path} must be a JSON object, got {type(preview).__name__}",
        )
    on_disk_version = preview.get("version")
    if on_disk_version == _KDF_PARAMS_VERSION:
        return MigrationResult(migrated=0, skipped=1, store_dir=store_dir)
    if on_disk_version != _LEGACY_KDF_PARAMS_VERSION:
        raise MasterKeyUnavailableError(
            f"master.kdf at {kdf_params_path} is version {on_disk_version!r}; "
            f"the migration helper only handles version {_LEGACY_KDF_PARAMS_VERSION} -> "
            f"{_KDF_PARAMS_VERSION}.",
        )

    try:
        legacy_params = _LegacyKdfParameters.model_validate_json(raw_text)
    except Exception as exc:
        raise MasterKeyUnavailableError(
            f"failed to parse legacy master.kdf at {kdf_params_path}: {exc}",
        ) from exc
    try:
        salt = _b64decode(legacy_params.salt_b64)
    except (ValueError, binascii.Error) as exc:
        raise MasterKeyUnavailableError("legacy KDF parameters carry malformed salt.") from exc

    legacy_kek = _derive_legacy_scrypt_kek(passphrase, salt, legacy_params)
    try:
        wire = base64.b64decode(master_key_path.read_bytes(), validate=True)
        blob = EncryptedBlob.from_wire(wire)
    except Exception as exc:
        raise MasterKeyUnavailableError(
            f"failed to read wrapped master key at {master_key_path}: {exc}",
        ) from exc

    new_params = _KdfParameters(
        memory_cost=_ARGON2_MEMORY_COST_KIB,
        time_cost=_ARGON2_TIME_COST,
        parallelism=_ARGON2_PARALLELISM,
        salt_b64=_b64encode(salt),
    )
    new_kek = FileFallbackMasterKeyProvider._derive_kek_with_params(passphrase, salt, new_params)

    # Recovery for the partial-migration window: a previous run may
    # have rewritten master.key under the new Argon2id KEK but crashed
    # before flipping master.kdf to v2. Try the new KEK first; if it
    # succeeds, master.key is already migrated and we only need to
    # write master.kdf to complete the transition.
    master_key: bytes
    try:
        master_key = decrypt_record(blob, key=new_kek, associated_data=b"aeat.master-key.v1")
        _log.info(
            "master.key at %s already wrapped under Argon2id KEK; "
            "completing partial migration by rewriting master.kdf only",
            master_key_path,
        )
        # master.key is already v2; just flip master.kdf to v2.
        FileFallbackMasterKeyProvider._write_bytes_secure(
            kdf_params_path,
            new_params.model_dump_json().encode("utf-8"),
        )
        _log.info("master.kdf at %s migrated from scrypt (v1) to Argon2id (v2)", kdf_params_path)
        return MigrationResult(migrated=1, skipped=0, store_dir=store_dir)
    except Exception:  # noqa: S110 - intentional fallthrough; not a partial-migration state
        # Not a partial-migration state. Fall through to the normal
        # legacy-unwrap → re-wrap path. The next try-block performs the
        # legacy decrypt and surfaces a typed error if that fails too.
        pass

    try:
        master_key = decrypt_record(blob, key=legacy_kek, associated_data=b"aeat.master-key.v1")
    except Exception as exc:
        raise MasterKeyUnavailableError(
            "failed to decrypt master key under legacy scrypt KDF; passphrase may be wrong "
            "or the file may be tampered with. The v1 store has not been modified.",
        ) from exc

    new_blob = encrypt_record(master_key, key=new_kek, associated_data=b"aeat.master-key.v1")
    # Write order: master.key first (so a crash leaves a recoverable
    # state — see the partial-migration recovery branch above), THEN
    # master.kdf (the v2 declaration is the very last on-disk change).
    FileFallbackMasterKeyProvider._write_bytes_secure(
        master_key_path,
        base64.b64encode(new_blob.to_wire()),
    )
    FileFallbackMasterKeyProvider._write_bytes_secure(
        kdf_params_path,
        new_params.model_dump_json().encode("utf-8"),
    )
    _log.info("master.kdf at %s migrated from scrypt (v1) to Argon2id (v2)", kdf_params_path)
    return MigrationResult(migrated=1, skipped=0, store_dir=store_dir)
