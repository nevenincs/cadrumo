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
- ``master.kdf`` — a small JSON document carrying the Argon2id
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
import contextlib
import getpass
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, Protocol, runtime_checkable

from argon2.low_level import Type as _Argon2Type
from argon2.low_level import hash_secret_raw as _argon2_hash_secret_raw
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from .....core.config import Settings

from .....core.locks import exclusive_file_lock, fsync_parent_dir
from .....core.logging import get_logger
from ..crypto._crypto import KEY_SIZE, EncryptedBlob, decrypt_record, encrypt_record
from ..errors import (
    DecryptionError,
    EncryptionError,
    KeyringUnavailableError,
    MasterKeyKdfVersionError,
    MasterKeyKeychainLockedError,
    MasterKeyMaterialMissingError,
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

PASSPHRASE_ENV_VAR: Final[str] = "AEAT_SECRET_PASSPHRASE"
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

* v2: Argon2id (memory_cost=19 MiB, time_cost=2, parallelism=1).
"""

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
    """On-disk record of the Argon2id parameters used to derive the KEK."""

    model_config = _STRICT_FROZEN

    version: int = Field(default=_KDF_PARAMS_VERSION)
    algorithm: Literal["argon2id"] = Field(default="argon2id")
    memory_cost: int
    time_cost: int
    parallelism: int
    salt_b64: str


class _KdfVersionEnvelope(BaseModel):
    """Minimal version-gate model for the master.kdf preflight check.

    Reads only the ``version`` field and tolerates the rest of the
    document so a v1 file does not trigger a strict-pydantic
    ValidationError before the version-mismatch runbook can fire.
    """

    model_config = ConfigDict(extra="allow")

    version: int | str | None = None


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
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    fd = os.open(tmp_path, flags, 0o600)
    try:
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, target)
        # Flush the parent directory entry to disk on POSIX so the
        # rename is durable across power loss (file fsync does not
        # imply directory fsync on ext4 / xfs / etc.).
        fsync_parent_dir(target)
    except BaseException:
        _log.error("master_key: atomic write failed target=%s", target, exc_info=True)
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


PassphraseCallback = Callable[[], str]
"""Pluggable hook for tests — callable returning the passphrase as a str."""


def _default_passphrase_callback() -> str:
    """Resolve the operator's passphrase from env or stdin.

    The env var is read but NOT popped from ``os.environ``. Earlier
    revisions popped on first read with the rationale that child
    processes spawned later would not inherit the value, but the
    in-process cache is reset under several legitimate flows
    (``aeat security recover`` calls ``_reset_for_tests`` then
    ``_resolve_passphrase`` again; long-running test sessions cycle
    the cache between sub-tests). After the pop, those second reads
    block on ``getpass.getpass`` in non-TTY contexts (CI, batch
    jobs, subprocess pipes), surfacing as opaque
    ``MasterKeyPassphraseMismatchError`` once the cached operator
    cancels and the substrate re-prompts. Keeping the env var lets
    every cache-miss read resolve consistently; subprocesses that
    inherit the parent's env always had access to the passphrase
    anyway (env-var inheritance is a cooperative-isolation property,
    not a confidentiality boundary the substrate can defend
    on its own).

    Trailing CRLF is stripped (some shells append it via
    ``$(cat .secret)``), but interior whitespace is preserved (some
    passphrase policies require it).
    """
    from .....core.config import load_settings

    configured = load_settings().aeat_secret_passphrase
    if configured is not None:
        # Strip trailing CRLF only — the shell often appends it.
        normalized = configured.get_secret_value().rstrip("\r\n")
        if not normalized:
            raise SecretStoreError(
                f"{PASSPHRASE_ENV_VAR} is set to whitespace-only; supply a non-empty passphrase.",
            )
        return normalized
    return getpass.getpass(prompt="AEAT secret-store passphrase: ")


@runtime_checkable
class KeyringClient(Protocol):
    """Injection seam for the OS-keychain operations the master-key
    provider depends on.

    The real implementation wraps the third-party :mod:`keyring`
    module's ``get_password`` / ``set_password`` calls plus the
    backend probe that rejects ``fail.Keyring`` and ``null.Keyring``.
    Tests inject a real fake implementation rather than patching the
    third-party module at runtime.
    """

    def probe_backend(self) -> None:
        """Raise :class:`KeyringUnavailableError` when the active
        backend cannot persist a master key (no-op fail / null
        backends)."""

    def get_password(self, service: str, username: str) -> str | None:
        """Return the persisted password for ``(service, username)``
        or ``None`` when the entry is absent."""

    def set_password(self, service: str, username: str, password: str) -> None:
        """Persist ``password`` under ``(service, username)``."""


class _RealKeyringClient:
    """Default :class:`KeyringClient` backed by the third-party
    ``keyring`` module."""

    def probe_backend(self) -> None:
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
        if type(backend).__name__ == "Keyring" and type(backend).__module__.endswith(".null"):
            raise KeyringUnavailableError(
                "OS keychain backend is the no-op null.Keyring; "
                "install a usable backend or set AEAT_SECRET_STORE_BACKEND=file.",
            )

    def get_password(self, service: str, username: str) -> str | None:
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - keyring is a hard dep
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        return keyring.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - keyring is a hard dep
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        keyring.set_password(service, username, password)


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

    The optional ``client`` argument injects a :class:`KeyringClient`
    implementation so tests exercise the provider's contract against a
    real fake type rather than monkeypatching the third-party
    ``keyring`` module.
    """

    def __init__(
        self,
        *,
        service: str = KEYRING_SERVICE,
        username: str = KEYRING_USERNAME,
        client: KeyringClient | None = None,
    ) -> None:
        """Bind the provider to a keyring service and account.

        Args:
            service: Service identifier under which the master key is
                stored. Defaults to :data:`KEYRING_SERVICE`.
            username: Account identifier within that service. Defaults
                to :data:`KEYRING_USERNAME`.
            client: Optional :class:`KeyringClient` implementation;
                defaults to the production
                :class:`_RealKeyringClient` wrapping the ``keyring``
                module. Tests inject a real fake type via this seam.
        """
        self._service = service
        self._username = username
        self._client: KeyringClient = client or _RealKeyringClient()

    def _probe_backend(self) -> None:
        """Refuse no-op keyring backends up-front, via the injected client.

        ``keyring.backends.fail.Keyring`` and ``keyring.backends.null.Keyring``
        are placeholder backends installed when the platform has no
        usable keychain. ``set_password`` on these silently succeeds
        (or raises ``NoKeyringError``) but never persists the value, so
        the master key would be lost on the next process restart.
        """

        self._client.probe_backend()

    def get_master_key(self) -> bytes:
        """Fetch (or mint and store) the master key via the OS keychain.

        Resolves on every call: process-global caching has retired in
        favour of :class:`BucketSession` instance state. Production
        consumers should activate a session via :func:`activate_session`
        and read through :func:`get_active_master_key` rather than call
        this method in a tight loop.
        """

        try:
            from keyring.errors import KeyringError
        except ImportError as exc:  # pragma: no cover - keyring is a hard dep
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        self._probe_backend()
        stored = self._read_stored_master_key(KeyringError)
        if stored is not None:
            return self._decode_stored_master_key(stored)
        new_key = self._mint_and_verify_master_key(KeyringError)
        _log.info("master key minted in OS keychain (service=%s)", self._service)
        return new_key

    def _read_stored_master_key(self, keyring_error_cls: type[Exception]) -> str | None:
        """Fetch the encoded master-key string from the keychain, or ``None`` if absent.

        The probe above already excluded the no-op backends; reaching
        a ``KeyringError`` here means the backend is usable but the
        keychain entry is currently inaccessible (macOS Keychain
        locked, Windows Hello prompt cancelled, Secret Service not
        unlocked). That maps to :class:`MasterKeyKeychainLockedError`
        with operator-facing remediation guidance; any other
        unexpected exception maps to
        :class:`KeyringUnavailableError`.
        """
        try:
            return self._client.get_password(self._service, self._username)
        except keyring_error_cls as exc:
            raise MasterKeyKeychainLockedError(
                f"OS keychain refused get_password: {exc}; "
                "unlock the OS keychain (Touch ID / Hello / libsecret) and retry, "
                "or set AEAT_SECRET_STORE_BACKEND=file to use the passphrase backend.",
            ) from exc
        except KeyringUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise KeyringUnavailableError(f"OS keychain raised unexpectedly: {exc}") from exc

    @staticmethod
    def _decode_stored_master_key(stored: str) -> bytes:
        """Decode the base64-encoded master-key string and validate the byte length."""
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
        return key

    def _mint_and_verify_master_key(self, keyring_error_cls: type[Exception]) -> bytes:
        """Mint a fresh master key, persist it, and verify the backend actually retains it.

        Some keyring backends silently drop ``set_password`` writes
        (e.g. fail-closed fallback adapters); the round-trip read
        below catches that class of failure before the dropped key
        reaches a downstream encryption call.
        """
        new_key = secrets.token_bytes(KEY_SIZE)
        try:
            self._client.set_password(self._service, self._username, _b64encode(new_key))
        except keyring_error_cls as exc:
            raise KeyringUnavailableError(f"OS keychain refused set_password: {exc}") from exc
        except KeyringUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise KeyringUnavailableError(f"OS keychain raised unexpectedly: {exc}") from exc
        try:
            roundtrip = self._client.get_password(self._service, self._username)
        except keyring_error_cls as exc:
            raise KeyringUnavailableError(f"OS keychain refused round-trip read: {exc}") from exc
        if roundtrip is None or _b64decode(roundtrip) != new_key:
            raise KeyringUnavailableError(
                "OS keychain accepted set_password but the round-trip read disagreed; "
                "the backend may be a silent dropper.",
            )
        return new_key

class FileFallbackMasterKeyProvider:
    """Encrypted-file-backed master-key provider.

    Persists ``salt`` and ``master.key`` (plus a human-readable
    ``master.kdf`` parameters document) under
    :attr:`Settings.aeat_secret_store_dir`. The KEK is derived from a
    passphrase via Argon2id and wraps the master key with AES-256-GCM.
    """

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
                callback that returns a deterministic value.
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
        value = self._passphrase_callback()
        if not value:
            raise SecretStoreError(
                "secret-store passphrase resolved to empty string; set "
                f"{PASSPHRASE_ENV_VAR} or supply a non-empty value at the prompt.",
            )
        return value.encode("utf-8")

    def get_master_key(self) -> bytes:
        self._store_dir.mkdir(parents=True, exist_ok=True)
        passphrase = self._resolve_passphrase()
        # Serialise the unwrap-or-mint decision under the on-disk lock
        # so two first-time callers cannot both decide to mint and then
        # race-write conflicting master.key + master.kdf pairs. Re-check
        # file existence inside the lock; the second caller will see
        # the artefacts the first caller wrote and route to unwrap.
        lock_target = self._store_dir / "master.lock"
        with exclusive_file_lock(lock_target):
            artefacts = (self._master_key_path, self._kdf_params_path, self._salt_path)
            present = [p for p in artefacts if p.exists()]
            if len(present) == len(artefacts):
                key = self._unwrap_existing(passphrase)
            elif present:
                # Torn install: a previous mint or recovery crashed
                # between the per-artefact atomic writes. Refuse to
                # silently re-mint (which would overwrite the
                # half-written ``master.key`` and destroy any record
                # encrypted under the recovered key). The operator
                # must finish recovery (``aeat security recover
                # --recovery-key "<24 words>"``) or, if the substrate
                # was never used and no records exist yet, run
                # ``aeat security provision --force`` to start fresh.
                missing = [p.name for p in artefacts if not p.exists()]
                raise MasterKeyMaterialMissingError(
                    f"file-fallback at {self._store_dir} is in a torn state — "
                    f"present={[p.name for p in present]} missing={missing}. "
                    "A previous mint or recovery crashed between writes. Run "
                    '`aeat security recover --recovery-key "<24 words>"` to '
                    "finish recovery, or `aeat security provision --force` to "
                    "wipe and re-provision (only if no records were ever "
                    "written under the prior key — that operation is "
                    "irreversible).",
                )
            else:
                key = self._mint_new(passphrase)
        return key

    def _unwrap_existing(self, passphrase: bytes) -> bytes:
        raw_text = self._kdf_params_path.read_text(encoding="utf-8")
        # Version-gate before strict pydantic parsing so a v1 file
        # produces a typed runbook-pointing error instead of a raw
        # ValidationError.
        try:
            preview = _KdfVersionEnvelope.model_validate_json(raw_text)
        except ValidationError as exc:
            raise MasterKeyUnavailableError(
                f"master.kdf at {self._kdf_params_path} must be a JSON object: {exc}",
            ) from exc
        on_disk_version = preview.version
        if on_disk_version != _KDF_PARAMS_VERSION:
            raise MasterKeyKdfVersionError(
                f"master.kdf at {self._kdf_params_path} is version {on_disk_version!r}; "
                f"this build expects version {_KDF_PARAMS_VERSION}.",
            )
        try:
            params = _KdfParameters.model_validate_json(raw_text)
        except (ValueError, ValidationError) as exc:
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
        except (OSError, ValueError, binascii.Error) as exc:
            raise MasterKeyUnavailableError(
                f"failed to read wrapped master key at {self._master_key_path}: {exc}",
            ) from exc
        try:
            return decrypt_record(blob, key=kek, associated_data=b"aeat.master-key.v1")
        except (DecryptionError, EncryptionError) as exc:
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
        # Use the durable atomic-write helper so a power-loss between
        # the three artefact writes does not leave a torn install
        # (truncated master.key under fresh master.kdf, etc.).
        # Same write order as ``complete_recovery``: master.key first
        # (under the new KEK), then master.kdf (the parameters that
        # derive the KEK), then salt (informational — the canonical
        # salt also lives in master.kdf.salt_b64).
        atomic_write_secure_bytes(
            self._master_key_path,
            base64.b64encode(blob.to_wire()),
        )
        atomic_write_secure_bytes(
            self._kdf_params_path,
            params.model_dump_json().encode("utf-8"),
        )
        atomic_write_secure_bytes(self._salt_path, salt)
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
        # Serialise the rewrite under the same on-disk lock that
        # ``get_master_key`` acquires for first-time mint / unwrap
        # decisions. Without this, a concurrent ``get_master_key`` in
        # another process could read a half-rewritten triple
        # (e.g. fresh ``master.kdf`` + stale ``master.key``) and
        # surface as ``MasterKeyPassphraseMismatchError`` even though
        # the operator's passphrase is correct.
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._restrict_dir_permissions(self._store_dir)
        with exclusive_file_lock(self._store_dir / "master.lock"):
            # Write order: ``master.key`` first (under the new KEK),
            # then ``master.kdf`` (the parameters that derive the new
            # KEK), then ``salt`` (informational — the canonical salt
            # also lives in ``master.kdf.salt_b64``). A crash between
            # the first and second write leaves a state where the new
            # ``master.key`` cannot decrypt under the OLD KDF — and
            # the OLD ``master.key`` content has already been
            # overwritten — but the recovery-key wrapping at
            # ``master.recovery.key`` is untouched, so the operator
            # can re-run ``aeat security recover`` to complete the
            # recovery.
            atomic_write_secure_bytes(
                self._master_key_path,
                base64.b64encode(blob.to_wire()),
            )
            atomic_write_secure_bytes(
                self._kdf_params_path,
                params.model_dump_json().encode("utf-8"),
            )
            atomic_write_secure_bytes(self._salt_path, salt)
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
        flags |= getattr(os, "O_NOINHERIT", 0)
        flags |= getattr(os, "O_CLOEXEC", 0)
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

class EphemeralMasterKeyProvider:
    """In-memory master-key provider used exclusively by tests.

    The key is generated once per provider instance and never persisted.
    Doubles as a context manager: ``with EphemeralMasterKeyProvider():
    ...`` opens a :class:`BucketSession` bound to the provider's key
    bytes and activates it via :func:`activate_session` so column-
    level decrypt and encrypt operations inside the block resolve
    through :func:`get_active_master_key`. On exit the session is
    closed (zeroising its buffers) and the ContextVar is restored.

    The provider remains a plain :class:`MasterKeyProvider`
    (``get_master_key()`` returns the same bytes) so blob-store,
    secret-store, and envelope code paths that take an injected
    ``master_key_provider`` continue to work unchanged inside the
    ``with`` block.
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
        self._session: object | None = None
        self._activation_cm: object | None = None

    def get_master_key(self) -> bytes:
        return self._key

    def __enter__(self) -> object:
        if self._session is not None:
            raise RuntimeError(
                "EphemeralMasterKeyProvider context manager is not re-entrant",
            )
        from datetime import UTC, datetime

        from ._active_session import activate_session
        from ._bucket_session import BucketSession

        session = BucketSession.open(
            bucket_id="ephemeral",
            kek=self._key,
            dek=self._key,
            idle_minutes=60,
            opened_at=datetime.now(UTC),
        )
        activation = activate_session(session)
        activation.__enter__()
        self._session = session
        self._activation_cm = activation
        return session

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        activation = self._activation_cm
        session = self._session
        self._activation_cm = None
        self._session = None
        if activation is not None:
            activation.__exit__(exc_type, exc, tb)
        if session is not None:
            session.close()


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
    from .....core.identity import validate_spanish_tax_id
    from .....core.identity._documents import IdentityError

    try:
        canonical = validate_spanish_tax_id(value)
    except (ValueError, IdentityError):
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
    keyring_client: KeyringClient | None = None,
) -> MasterKeyProvider:
    """Resolve the active :class:`MasterKeyProvider` per project settings.

    Args:
        backend: Optional explicit backend selector (``auto`` /
            ``keyring`` / ``file``). Overrides the value resolved from
            settings.
        settings_override: Optional pre-built settings instance. Tests
            inject a settings object bound to ``tmp_path`` so the file
            backend writes inside the test sandbox.
        passphrase_callback: Optional override for passphrase
            resolution; only consulted by the file backend.
        keyring_client: Optional :class:`KeyringClient` implementation
            threaded into any constructed
            :class:`KeyringMasterKeyProvider`. Tests inject a real
            fake type rather than patching the third-party ``keyring``
            module.

    Returns:
        A live provider instance honouring the resolved backend.

    Raises:
        KeyringUnavailableError: When the resolved backend is
            ``keyring`` and no usable keychain is detected.
        SecretStoreError: When ``backend`` is not a known value.
    """
    from .....core.config import SecretStoreBackend, load_settings  # local import to avoid cycles

    settings = settings_override if settings_override is not None else load_settings()
    backend_value = settings.aeat_secret_store_backend.value if backend is None else backend
    try:
        resolved = SecretStoreBackend(backend_value)
    except ValueError as exc:
        raise SecretStoreError(f"unknown secret-store backend: {backend_value!r}") from exc
    store_dir = Path(settings.aeat_secret_store_dir)
    if resolved is SecretStoreBackend.UNSECURED:
        # Hostile-named opt-out gate: the unsecured backend requires the
        # operator to explicitly set AEAT_ALLOW_UNENCRYPTED=1 (strict
        # string match, not Pydantic bool coercion — see the Settings
        # field's inline rationale). Refuse otherwise. The NIF-canary
        # that fences off real tax data lives at the profile-load
        # boundary (see consumer modules).
        if settings.aeat_allow_unencrypted != "1":
            raise UnsecuredModeRefusedError(
                "aeat_secret_store_backend='unsecured' requires "
                "AEAT_ALLOW_UNENCRYPTED=1. The unsecured backend uses a "
                "published deterministic master key and provides ZERO "
                "confidentiality; intended for testing / throwaway data only.",
            )
        return UnsecuredMasterKeyProvider()
    if resolved is SecretStoreBackend.KEYRING:
        provider = KeyringMasterKeyProvider(client=keyring_client)
        # Probe early so callers see the failure at construction.
        provider.get_master_key()
        return provider
    if resolved is SecretStoreBackend.FILE:
        return FileFallbackMasterKeyProvider(
            store_dir=store_dir,
            passphrase_callback=passphrase_callback,
        )
    keyring_provider = KeyringMasterKeyProvider(client=keyring_client)
    try:
        keyring_provider.get_master_key()
        return keyring_provider
    except KeyringUnavailableError as exc:
        # Backend itself is unusable (no-op fail/null backend, package
        # missing). Falling back to file is safe: there is no
        # keychain-backed master key that file-fallback could diverge
        # from.
        _log.info("OS keychain backend unavailable (%s); falling back to encrypted-file backend", exc)
        return FileFallbackMasterKeyProvider(
            store_dir=store_dir,
            passphrase_callback=passphrase_callback,
        )
    except MasterKeyKeychainLockedError as exc:
        # Backend works, but the entry is currently inaccessible
        # (Touch ID / Hello prompt cancelled, libsecret locked, etc.).
        # If file-fallback artefacts already exist, the operator has
        # previously chosen the file backend — route through it
        # safely (no divergence; the operator's existing file-fallback
        # state is the canonical master key for the next call). If
        # NO file-fallback artefacts exist, RAISE the locked error
        # rather than minting a fresh K2 that would diverge from the
        # K1 sitting in the locked keychain. The operator must either
        # unlock the keychain or set ``AEAT_SECRET_STORE_BACKEND=file``
        # explicitly to acknowledge the file-only path.
        file_fallback_exists = (
            (store_dir / "master.key").exists()
            and (store_dir / "master.kdf").exists()
            and (store_dir / "salt").exists()
        )
        if file_fallback_exists:
            _log.info(
                "OS keychain locked (%s); routing through pre-existing file-fallback at %s",
                exc,
                store_dir,
            )
            return FileFallbackMasterKeyProvider(
                store_dir=store_dir,
                passphrase_callback=passphrase_callback,
            )
        raise MasterKeyKeychainLockedError(
            f"OS keychain is locked AND no file-fallback artefacts exist at {store_dir}. "
            "auto-mode refuses to mint a fresh file-fallback master key while the keychain "
            "may already hold a different one — the resulting two master keys would render "
            "any record encrypted under either key unreadable when the other backend is "
            "active. Either unlock the OS keychain (Touch ID / Hello / libsecret) and retry, "
            "or set AEAT_SECRET_STORE_BACKEND=file to explicitly choose the passphrase backend "
            "and provision a file-fallback master key with `aeat security provision`.",
        ) from exc
