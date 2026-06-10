"""Master-key acquisition for the at-rest crypto stack.

Three concrete providers implement the :class:`MasterKeyProvider`
protocol:

- :class:`KeyringMasterKeyProvider` — backed by the ``keyring`` package
  (Windows Credential Manager, macOS Keychain, Linux Secret Service via
  libsecret). The master key is stored under a fixed service name and
  account; explicit enrollment mints a 32-byte random key and persists
  it.
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
:func:`getpass.getpass`.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import os
import secrets
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from pydantic import ValidationError

from .....core.time import now

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from types import TracebackType

    from .....core.config import Settings
    from ._bucket_session import BucketSession

from .....core import resolve_active_bucket_id
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.locks import exclusive_file_lock
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
    PassphraseTooShortError,
    SecretAlreadyExistsError,
    SecretStoreError,
    UnsecuredModeRefusedError,
)
from ._master_key_bucket_dek import idle_minutes_for_bucket, load_or_mint_bucket_dek
from ._master_key_derivation import (
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    KDF_PARAMS_VERSION,
    SALT_SIZE,
    derive_kek_with_params,
)
from ._master_key_ephemeral import EphemeralMasterKeyProvider as EphemeralMasterKeyProvider
from ._master_key_io import (
    PASSPHRASE_ENV_VAR,
    PassphraseCallback,
    _b64decode,
    _b64encode,
    _default_passphrase_callback,
    atomic_write_secure_bytes,
)
from ._master_key_records import (
    EnvelopeDocument,
    _KdfParameters,
    _KdfVersionEnvelope,
)
from ._master_key_tax_id import looks_like_real_tax_id as looks_like_real_tax_id

NIST_PASSPHRASE_MIN_LENGTH: Final[int] = 8
"""NIST SP 800-63B §5.1.1.1 verifier-side minimum passphrase length."""

_log = get_logger(__name__)


KEYRING_SERVICE: Final[str] = "aeat:secure-persistence"
"""Stable service identifier under which the keyring backend stores the key."""

KEYRING_USERNAME: Final[str] = "master"
"""Account identifier for the master-key entry in the OS keychain."""

_MASTER_KEY_UNAVAILABLE_MESSAGE_KEY: Final[str] = "errors.auth.auth_storage_master_key_unavailable"
_MASTER_KEY_PASSPHRASE_MISMATCH_MESSAGE_KEY: Final[str] = "errors.auth.auth_storage_master_key_passphrase_mismatch"


def _master_key_unavailable_error(message: str) -> MasterKeyUnavailableError:
    return MasterKeyUnavailableError(message, translated_message=_MASTER_KEY_UNAVAILABLE_MESSAGE_KEY)


def _master_key_passphrase_mismatch_error(message: str) -> MasterKeyPassphraseMismatchError:
    return MasterKeyPassphraseMismatchError(
        message,
        translated_message=_MASTER_KEY_PASSPHRASE_MISMATCH_MESSAGE_KEY,
    )


@runtime_checkable
class MasterKeyProvider(Protocol):
    """Source of the master key used by every at-rest crypto consumer.

    Providers are context managers: entering activates the backend's
    session (idle-timeout guard, in-memory key cache) and exiting tears
    it down. Every concrete provider implements the protocol verbatim.

    The ``_session`` / ``_activation_cm`` slots are the bookkeeping the
    shared enter/exit machinery binds onto: entering stores the opened
    :class:`BucketSession` and its activation context manager, exiting
    tears both down. Every concrete provider declares them in
    ``__init__``.
    """

    _session: BucketSession | None
    _activation_cm: AbstractContextManager[None] | None

    def get_master_key(self) -> bytes:
        """Return the 32-byte AES-256 master key.

        Returns:
            The 32-byte AES-256 master key for the active session.
        """
        ...

    def provision_master_key(self) -> bytes:
        """Mint and persist the 32-byte AES-256 master key during explicit enrollment."""
        ...

    def __enter__(self) -> object:
        """Activate the provider's backend session for the ``with`` block."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Tear down the provider's backend session on block exit."""
        ...


@runtime_checkable
class KeyringClient(Protocol):
    """Injection seam for the OS-keychain operations the master-key provider depends on.

    The real implementation wraps the third-party :mod:`keyring`
    module's ``get_password`` / ``set_password`` calls plus the
    backend probe that rejects ``fail.Keyring`` and ``null.Keyring``.
    Tests inject a real in-memory implementation rather than mutating
    the third-party module at runtime.
    """

    def probe_backend(self) -> None:
        """Raise :class:`KeyringUnavailableError` when the active backend cannot persist a master key.

        No-op fail / null backends trigger this error.
        """

    def get_password(self, service: str, username: str) -> str | None:
        """Return the persisted password for ``(service, username)``, or ``None`` when absent."""

    def set_password(self, service: str, username: str, password: str) -> None:
        """Persist ``password`` under ``(service, username)``."""


class _RealKeyringClient:
    """Default :class:`KeyringClient` backed by the third-party ``keyring`` module."""

    def probe_backend(self) -> None:
        try:
            import keyring
        except ImportError as exc:
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        try:
            from keyring.backends import fail as _fail_backend

            backend = keyring.get_keyring()
        except Exception as exc:
            _log.debug("keyring backend probe failed error_type=%s", type(exc).__name__)
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
        except ImportError as exc:
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        return keyring.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        try:
            import keyring
        except ImportError as exc:
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

    Older builds kept an in-process key cache keyed by ``(service,
    username)``. That cache has retired in favour of
    :class:`BucketSession`; this provider resolves through the keyring
    on each call.

    The optional ``client`` argument injects a :class:`KeyringClient`
    implementation so tests exercise the provider's contract against a
    real in-memory implementation rather than mutating the third-party
    ``keyring`` module at runtime.
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
        self._session: BucketSession | None = None
        self._activation_cm: AbstractContextManager[None] | None = None

    def __enter__(self) -> object:
        return _provider_enter(self)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _provider_exit(self, exc_type, exc, tb)

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
        """Fetch the master key via the OS keychain.

        Resolves on every call: process-global caching has retired in
        favour of :class:`BucketSession` instance state. Production
        consumers should activate a session via :func:`activate_session`
        and read through :func:`get_active_master_key` rather than call
        this method in a tight loop.

        Absent key material is a provisioning error, not permission to
        create storage implicitly. Explicit enrollment calls
        :meth:`provision_master_key`.
        """
        try:
            from keyring.errors import KeyringError
        except ImportError as exc:
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        self._probe_backend()
        stored = self._read_stored_master_key(KeyringError)
        if stored is not None:
            return self._decode_stored_master_key(stored)
        raise MasterKeyMaterialMissingError(
            "OS keychain master key is not provisioned; run "
            "`aeat config profile create NAME` to create and unlock a profile, "
            "or `aeat config switch NAME` for an existing profile.",
        )

    def provision_master_key(self) -> bytes:
        """Mint and persist a new keychain master key for explicit enrollment."""
        try:
            from keyring.errors import KeyringError
        except ImportError as exc:
            raise KeyringUnavailableError(f"keyring package not importable: {exc}") from exc
        from .....core.config import load_settings

        settings = load_settings()
        lock_target = Path(settings.aeat_secret_store_dir) / "keyring.lock"
        lock_target.parent.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(lock_target):
            self._probe_backend()
            stored = self._read_stored_master_key(KeyringError)
            if stored is not None:
                raise SecretAlreadyExistsError(
                    "OS keychain master key is already provisioned; use `aeat config recover` "
                    "or `aeat config rekey` for custody changes.",
                )
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
        except Exception as exc:
            _log.debug("keyring get_password failed unexpectedly error_type=%s", type(exc).__name__)
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
        except Exception as exc:
            _log.debug("keyring set_password failed unexpectedly error_type=%s", type(exc).__name__)
            raise KeyringUnavailableError(f"OS keychain raised unexpectedly: {exc}") from exc
        try:
            roundtrip = self._client.get_password(self._service, self._username)
        except keyring_error_cls as exc:
            raise KeyringUnavailableError(f"OS keychain refused round-trip read: {exc}") from exc
        if roundtrip is None:
            raise KeyringUnavailableError(
                "OS keychain accepted set_password but the round-trip read was empty; "
                "the backend may be a silent dropper.",
            )
        if self._decode_stored_master_key(roundtrip) != new_key:
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
        self._session: BucketSession | None = None
        self._activation_cm: AbstractContextManager[None] | None = None

    def __enter__(self) -> object:
        return _provider_enter(self)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _provider_exit(self, exc_type, exc, tb)

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
        if len(value) < NIST_PASSPHRASE_MIN_LENGTH:
            raise PassphraseTooShortError(
                "secret-store passphrase is shorter than the NIST SP 800-63B "
                f"§5.1.1.1 verifier minimum of {NIST_PASSPHRASE_MIN_LENGTH} "
                "characters; supply a longer passphrase via "
                f"{PASSPHRASE_ENV_VAR} or at the prompt.",
            )
        return value.encode(_UTF_8_ENCODING)

    def get_master_key(self) -> bytes:
        """Unwrap and return the 32-byte master key from the encrypted file store.

        Resolves the operator passphrase, then serialises the
        unwrap-or-refuse decision under an exclusive ``master.lock`` so two
        first-time callers cannot race-mint conflicting ``master.key`` /
        ``master.kdf`` pairs. When all three artefacts (``master.key``,
        ``master.kdf``, ``salt``) are present, derives the Argon2id
        key-encryption key (KEK) from the passphrase and uses it to unwrap
        the wrapped master key. A partial artefact set is a torn install -- a
        prior mint or recovery crashed mid-write -- and is refused rather
        than silently re-minted, which would orphan records encrypted under
        the lost key.

        Returns:
            The 32-byte AES-256 master key.

        Raises:
            MasterKeyMaterialMissingError: When the store is unprovisioned
                or in a torn state.
            MasterKeyPassphraseMismatchError: When the passphrase fails to
                unwrap the stored key.
            MasterKeyKdfVersionError: When ``master.kdf`` carries an
                unsupported parameter version.
            MasterKeyUnavailableError: When an artefact is malformed or
                unreadable.
            PassphraseTooShortError: When the resolved passphrase is shorter
                than the NIST verifier minimum.
        """
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
                # must finish recovery with `aeat config recover`,
                # or, if the substrate was never used and no records
                # exist yet, move the torn directory aside and create a
                # new profile.
                missing = [p.name for p in artefacts if not p.exists()]
                raise MasterKeyMaterialMissingError(
                    f"file-fallback at {self._store_dir} is in a torn state — "
                    f"present={[p.name for p in present]} missing={missing}. "
                    "A previous mint or recovery crashed between writes. Run "
                    "`aeat config recover --recovery-key <WORDS>` with the 24-word recovery key "
                    "to finish recovery, or move the torn secret-store directory "
                    "aside and run `aeat config profile create NAME` "
                    "only if no records were ever written under the prior key.",
                )
            else:
                raise MasterKeyMaterialMissingError(
                    f"file-fallback at {self._store_dir} is not provisioned; run "
                    "`aeat config profile create NAME` to create and unlock a profile "
                    "before invoking commands that decrypt or persist stored records.",
                )
        return key

    def provision_master_key(self, *, force: bool = False) -> bytes:
        """Mint the file-fallback master key for explicit enrollment.

        Args:
            force: When True, replace complete existing material. Reserved for
                explicit re-provision flows; normal enrollment leaves it False.

        Returns:
            The newly minted 32-byte master key.

        Raises:
            SecretAlreadyExistsError: When the store is already provisioned and ``force`` is False.
            MasterKeyMaterialMissingError: When the store is in a torn state.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        passphrase = self._resolve_passphrase()
        lock_target = self._store_dir / "master.lock"
        with exclusive_file_lock(lock_target):
            artefacts = (self._master_key_path, self._kdf_params_path, self._salt_path)
            present = [p for p in artefacts if p.exists()]
            if present and not force:
                raise SecretAlreadyExistsError(
                    f"file-fallback at {self._store_dir} is already provisioned; use "
                    "`aeat config recover` or `aeat config rekey` for custody changes.",
                )
            if present and len(present) != len(artefacts):
                missing = [p.name for p in artefacts if not p.exists()]
                raise MasterKeyMaterialMissingError(
                    f"file-fallback at {self._store_dir} is in a torn state - "
                    f"present={[p.name for p in present]} missing={missing}. Run "
                    "`aeat config recover --recovery-key <WORDS>` with the 24-word recovery key to "
                    "finish recovery, or move the torn secret-store directory aside "
                    "only if no records were ever written under the prior key.",
                )
            return self._mint_new(passphrase)

    def _unwrap_existing(self, passphrase: bytes) -> bytes:
        raw_text = self._kdf_params_path.read_text(encoding=_UTF_8_ENCODING)
        # Version-gate before strict pydantic parsing so a v1 file
        # produces a typed runbook-pointing error instead of a raw
        # ValidationError.
        try:
            preview = _KdfVersionEnvelope.model_validate_json(raw_text)
        except ValidationError as exc:
            raise _master_key_unavailable_error("master.kdf must be a JSON object.") from exc
        on_disk_version = preview.version
        if on_disk_version != KDF_PARAMS_VERSION:
            raise MasterKeyKdfVersionError(
                f"master.kdf at {self._kdf_params_path} is version {on_disk_version!r}; "
                f"this build expects version {KDF_PARAMS_VERSION}.",
            )
        try:
            params = _KdfParameters.model_validate_json(raw_text)
        except (ValueError, ValidationError) as exc:
            raise _master_key_unavailable_error("failed to parse KDF parameters.") from exc
        try:
            salt = _b64decode(params.salt_b64)
        except (ValueError, binascii.Error) as exc:
            raise _master_key_unavailable_error("KDF parameters carry malformed salt.") from exc
        kek = self._derive_kek_with_params(passphrase, salt, params)
        try:
            wire = base64.b64decode(self._master_key_path.read_bytes(), validate=True)
            blob = EncryptedBlob.from_wire(wire)
        except (OSError, ValueError, binascii.Error) as exc:
            raise _master_key_unavailable_error("failed to read wrapped master key.") from exc
        try:
            return decrypt_record(blob, key=kek, associated_data=b"aeat.master-key.v1")
        except (DecryptionError, EncryptionError) as exc:
            # Distinguish passphrase-mismatch from material-missing so
            # the CLI can render an actionable hint
            # (`aeat config recover` for forgotten
            # passphrase vs `aeat config profile create NAME` for absent
            # material).
            raise _master_key_passphrase_mismatch_error(
                "passphrase did not unlock the master key; verify the passphrase or run "
                "`aeat config recover --recovery-key <WORDS>`.",
            ) from exc

    def _mint_new(self, passphrase: bytes) -> bytes:
        salt = secrets.token_bytes(SALT_SIZE)
        params = _KdfParameters(
            memory_cost=ARGON2_MEMORY_COST_KIB,
            time_cost=ARGON2_TIME_COST,
            parallelism=ARGON2_PARALLELISM,
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
            params.model_dump_json().encode(_UTF_8_ENCODING),
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
        salt = secrets.token_bytes(SALT_SIZE)
        params = _KdfParameters(
            memory_cost=ARGON2_MEMORY_COST_KIB,
            time_cost=ARGON2_TIME_COST,
            parallelism=ARGON2_PARALLELISM,
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
            # can re-run `aeat config recover` to complete the
            # recovery.
            atomic_write_secure_bytes(
                self._master_key_path,
                base64.b64encode(blob.to_wire()),
            )
            atomic_write_secure_bytes(
                self._kdf_params_path,
                params.model_dump_json().encode(_UTF_8_ENCODING),
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
                # Private directory mode; Semgrep's generic file-mode rule is inverted here.
                os.chmod(target, 0o700)  # nosemgrep
            except OSError:
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
        return derive_kek_with_params(
            passphrase,
            salt,
            memory_cost=params.memory_cost,
            time_cost=params.time_cost,
            parallelism=params.parallelism,
        )


def _extract_profile_tax_ids(envelope_payload: bytes) -> tuple[str, ...] | None:
    """Extract profile tax-id facts from a decrypted user-profile envelope."""
    try:
        doc = EnvelopeDocument.model_validate_json(envelope_payload)
    except (UnicodeDecodeError, ValueError):
        return None
    if doc.payload is None:
        return None
    tax_ids: list[str] = [
        str(fact.value) for fact in doc.payload.facts if fact.path == "identity.tax_id" and isinstance(fact.value, str)
    ]
    return tuple(tax_ids) if tax_ids else None


def _refuse_unsecured_active_bucket_with_real_profile(session: BucketSession) -> None:
    """Refuse unsecured activation when the active bucket carries a real profile."""
    from .....core.config import load_settings
    from .._namespace_registry import BUCKET_DB_DIRNAME, BUCKETS_DIRNAME, USER_PROFILE_VALUE_NAMESPACE
    from ..crypto._encrypted_columns import decrypt_encrypted_bytes_column

    if session.bucket_id == "unsecured":
        return
    db_path = (
        load_settings().aeat_local_storage_root / BUCKETS_DIRNAME / session.bucket_id / BUCKET_DB_DIRNAME / "aeat.db"
    )
    if not db_path.is_file():
        return
    try:
        with sqlite3.connect(db_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM secure_objects WHERE namespace = ?",
                (USER_PROFILE_VALUE_NAMESPACE.namespace,),
            ).fetchall()
    except sqlite3.Error as exc:
        # Fail closed: a malformed, locked, or corrupted bucket DB means
        # we cannot prove the profile is synthetic, so the deterministic
        # unsecured backend must be refused. Returning here previously
        # downgraded the check silently and admitted the published key
        # on profiles that may have held real tax IDs.
        raise UnsecuredModeRefusedError(
            "unsecured master-key backend cannot read the active profile bucket DB "
            "to prove the profile is synthetic; "
            "use the file or keyring backend before decrypting or persisting records.",
        ) from exc
    for (payload_wire,) in rows:
        try:
            payload_plain = decrypt_encrypted_bytes_column(bytes(payload_wire))
        except (DecryptionError, TypeError, ValueError) as exc:
            raise UnsecuredModeRefusedError(
                "unsecured master-key backend cannot prove the active profile is synthetic; "
                "use the file or keyring backend before decrypting or persisting records.",
            ) from exc
        tax_ids = _extract_profile_tax_ids(payload_plain)
        if tax_ids is None:
            raise UnsecuredModeRefusedError(
                "unsecured master-key backend cannot prove the active profile is synthetic; "
                "use the file or keyring backend before decrypting or persisting records.",
            )
        for tax_id in tax_ids:
            refuse_unsecured_with_real_nif(tax_id, provider=UnsecuredMasterKeyProvider())


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


def _provider_enter(
    provider: MasterKeyProvider,
    *,
    fallback_bucket_id: str | None = None,
    allow_bucket_dek_enrollment: bool = False,
) -> BucketSession:
    """Open and activate a :class:`BucketSession` for ``provider``.

    Resolves the active bucket id via the canonical precedence chain
    (env override > pointer file). When the chain yields no active
    profile, falls back to ``fallback_bucket_id`` if supplied (the
    Unsecured provider uses ``"unsecured"`` as a stable label so the
    engine cache keys consistently). When neither resolves, raises
    :class:`NoActiveProfileError` so the CLI root callback can refuse
    the verb with a translated message.

    Stores the opened session and the activation context manager on
    ``provider._session`` and ``provider._activation_cm`` so the
    matching ``_provider_exit`` can tear them down.
    """
    from .....core.config import load_settings
    from ..bucket._errors import NoActiveBucketError
    from ._active_session import activate_session
    from ._bucket_session import BucketSession

    if provider._session is not None:
        from ._errors import MasterKeyReentrantError

        raise MasterKeyReentrantError(type(provider).__name__)

    bucket_id = resolve_active_bucket_id() or fallback_bucket_id
    if not bucket_id:
        raise NoActiveBucketError(
            "no active profile resolves; run `aeat config profile create NAME` "
            "or `aeat config switch NAME` before invoking commands that "
            "decrypt stored records.",
        )

    key_bytes = provider.get_master_key()
    settings = load_settings()
    if isinstance(provider, UnsecuredMasterKeyProvider):
        dek_bytes = key_bytes
    else:
        dek_bytes = load_or_mint_bucket_dek(
            kek=key_bytes,
            storage_root=settings.aeat_local_storage_root,
            bucket_id=bucket_id,
            allow_bootstrap_mint=allow_bucket_dek_enrollment,
        )
    idle_minutes = idle_minutes_for_bucket(
        storage_root=settings.aeat_local_storage_root,
        bucket_id=bucket_id,
        default_minutes=settings.aeat_bucket_default_idle_lock_minutes,
    )
    session = BucketSession.open(
        bucket_id=bucket_id,
        kek=key_bytes,
        dek=dek_bytes,
        idle_minutes=idle_minutes,
        opened_at=now(),
        unsecured_backend=isinstance(provider, UnsecuredMasterKeyProvider),
    )
    activation = activate_session(session)
    activation.__enter__()
    provider._session = session
    provider._activation_cm = activation
    try:
        if session.unsecured_backend:
            _refuse_unsecured_active_bucket_with_real_profile(session)
    except BaseException:
        provider._activation_cm = None
        provider._session = None
        activation.__exit__(None, None, None)
        session.close()
        raise
    return session


def _provider_exit(
    provider: MasterKeyProvider,
    exc_type: type[BaseException] | None,
    exc: BaseException | None,
    tb: TracebackType | None,
) -> None:
    """Tear down the activation + session opened by :func:`_provider_enter`.

    Idempotent on the provider's bookkeeping attributes; tolerant of
    the case where ``_provider_enter`` raised before fully populating
    them.
    """
    activation = provider._activation_cm
    session = provider._session
    provider._activation_cm = None
    provider._session = None
    if activation is not None:
        activation.__exit__(exc_type, exc, tb)
    if session is not None:
        session.close()


@contextlib.contextmanager
def activate_master_key_provider(
    provider: MasterKeyProvider,
    *,
    fallback_bucket_id: str | None = None,
    allow_bucket_dek_enrollment: bool = False,
) -> Iterator[object]:
    """Activate ``provider`` for encrypted storage within the current block.

    ``fallback_bucket_id`` is used by bootstrap flows such as profile
    creation, where the command knows the bucket being provisioned but
    the active-profile pointer does not exist until the transaction
    completes.

    Args:
        provider: The :class:`MasterKeyProvider` to activate.
        fallback_bucket_id: Optional bucket identifier used when no active
            profile pointer is present (bootstrap flows only).
        allow_bucket_dek_enrollment: When ``True``, a missing per-bucket DEK
            file is minted on first activation rather than raising.
    """
    _provider_enter(
        provider,
        fallback_bucket_id=fallback_bucket_id,
        allow_bucket_dek_enrollment=allow_bucket_dek_enrollment,
    )
    try:
        yield provider
    finally:
        _provider_exit(provider, None, None, None)


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

    def __init__(self) -> None:
        self._session: BucketSession | None = None
        self._activation_cm: AbstractContextManager[None] | None = None

    def get_master_key(self) -> bytes:
        """Return the published deterministic master key for unsecured mode.

        The returned bytes are publicly known by design, so the wrapping
        key provides **ZERO confidentiality**; the substrate's encryption
        pipeline is otherwise intact. Intended only for testing, tutorial,
        and throwaway scenarios that are fenced off from real tax data by
        the NIF-canary at the profile-load boundary.

        Returns:
            The 32-byte published deterministic master key.
        """
        return _UNSECURED_PUBLISHED_KEY

    def provision_master_key(self) -> bytes:
        """Return the published deterministic key without minting material.

        There is nothing to provision for the unsecured backend: the key is
        a fixed published constant, so enrollment and retrieval return the
        same bytes. Provides **ZERO confidentiality** -- see
        ``get_master_key``.

        Returns:
            The 32-byte published deterministic master key.
        """
        return _UNSECURED_PUBLISHED_KEY

    def __enter__(self) -> object:
        return _provider_enter(self, fallback_bucket_id="unsecured")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _provider_exit(self, exc_type, exc, tb)


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
        provider: The active :class:`MasterKeyProvider`. The check is a
            no-op for any provider that is not :class:`UnsecuredMasterKeyProvider`.

    Raises:
        UnsecuredModeRefusedError: When the unsecured backend is active
            and the tax id is real.
    """
    if not isinstance(provider, UnsecuredMasterKeyProvider):
        return
    if looks_like_real_tax_id(tax_id):
        raise UnsecuredModeRefusedError(
            "unsecured master-key backend is incompatible with a real tax id; either remove "
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
        SecretStoreError: When ``backend`` is not a known value.
        UnsecuredModeRefusedError: When the unsecured backend is selected with a real tax id.
        MasterKeyKeychainLockedError: When the keyring backend detects no usable keychain.
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
        # Probe early so callers see unusable keychains at construction
        # without turning absent key material into an implicit mint.
        provider._probe_backend()
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
            "and provision a file-fallback master key with `aeat config profile create NAME`.",
        ) from exc
    except MasterKeyMaterialMissingError:
        file_fallback_exists = (
            (store_dir / "master.key").exists()
            and (store_dir / "master.kdf").exists()
            and (store_dir / "salt").exists()
        )
        if file_fallback_exists:
            _log.info(
                "OS keychain unprovisioned; routing through pre-existing file-fallback at %s",
                store_dir,
            )
            return FileFallbackMasterKeyProvider(
                store_dir=store_dir,
                passphrase_callback=passphrase_callback,
            )
        return keyring_provider
