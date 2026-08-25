"""Master-key protocol and the unsecured-backend safety refusal.

The :class:`MasterKeyProvider` protocol every at-rest crypto consumer types
against, the one provider that still implements it, and the NIF-canary that
fences that provider off from real tax data.

The shared-master providers are gone. A keychain-backed provider and a
passphrase-derived file-backed provider once implemented this protocol over a
single process-wide key persisted as ``master.key`` / ``master.kdf``, selected
by a backend setting. Nothing in production read those artefacts by the time
they were removed: the active master key is the unlocked bucket's own data
key, minted and wrapped per profile by the custody package, and every
encrypt and decrypt path resolves it from the active bucket session. The file
store guarded no material this build could produce, so it was deleted rather
than left standing as a second, unreachable custody route.

What remains is deliberately small. :class:`UnsecuredMasterKeyProvider`
returns a PUBLISHED deterministic key and provides zero confidentiality; it
exists so testing and tutorial scenarios keep the substrate's encryption
pipeline intact without key management. It is fenced by
:func:`refuse_unsecured_with_real_nif` and
:func:`refuse_unsecured_bucket_with_real_profile`, which refuse the moment a
bucket's profile carries a real NIF, NIE or CIF, and which fail CLOSED when
they cannot prove the profile is synthetic.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from .....core.time import now

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from types import TracebackType

    from ._bucket_session import BucketSession

from .....core import StorageCategory
from .....core.bucket_pointer import resolve_active_bucket_id
from .....core.logging import get_logger
from ..crypto import (
    KEY_SIZE,
)
from ..errors import (
    DecryptionError,
    MasterKeyMaterialMissingError,
    UnsecuredModeRefusedError,
)
from ._master_key_records import (
    EnvelopeDocument,
)
from ._master_key_tax_id import looks_like_real_tax_id as looks_like_real_tax_id
from ._provider_session import exit_provider_session

_log = get_logger(__name__)


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

        Immutable by contract, and deliberately so. The DEK unwraps return
        wipeable ``bytearray`` buffers because an unwrapped DEK is minted for
        one caller and handed over outright, so wiping it is that caller's
        business. Master-key material is not owned that way: a provider may
        return the SAME object to every consumer -- the unsecured provider
        returns a module-level constant -- so a mutable contract would let one
        consumer's wipe zero the key for every later caller, silently and
        unattributably.

        A holder that needs to clear its own copy makes one and wipes that.
        ``BucketSession`` does exactly this, and its copy is correct rather
        than redundant precisely because the session does not own the key it
        was handed.

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


def refuse_unsecured_bucket_with_real_profile(session: BucketSession) -> None:
    """Refuse unsecured activation when the bucket carries a real profile.

    The NIF-canary gate for a session opened against the published
    deterministic key. Public because every path that opens a session
    outside :func:`_provider_enter` — notably the unscoped profile-login
    open — must run exactly this guard rather than re-deriving it.

    Args:
        session: The freshly-opened unsecured :class:`BucketSession`.

    Raises:
        UnsecuredModeRefusedError: When the bucket's profile cannot be
            proven synthetic, or carries a real NIF / NIE / CIF.
    """
    from .....core import bucket_scoped_storage_path
    from .....core.config import load_settings
    from .._namespace_registry import USER_PROFILE_VALUE_NAMESPACE
    from ..crypto import decrypt_encrypted_bytes_column

    if session.bucket_id == "unsecured":
        return
    db_path = bucket_scoped_storage_path(
        StorageCategory.BUCKET_DATABASE_FILE,
        session.bucket_id,
        settings=load_settings(),
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
            "unsecured storage backend cannot read the active profile bucket DB "
            "to prove the profile is synthetic; "
            "it is not safe for real data, so open the profile through its own password.",
        ) from exc
    for (payload_wire,) in rows:
        try:
            payload_plain = decrypt_encrypted_bytes_column(bytes(payload_wire))
        except (DecryptionError, TypeError, ValueError) as exc:
            raise UnsecuredModeRefusedError(
                "unsecured storage backend cannot prove the active profile is synthetic; "
                "it is not safe for real data, so open the profile through its own password.",
            ) from exc
        tax_ids = _extract_profile_tax_ids(payload_plain)
        if tax_ids is None:
            raise UnsecuredModeRefusedError(
                "unsecured storage backend cannot prove the active profile is synthetic; "
                "it is not safe for real data, so open the profile through its own password.",
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
) -> BucketSession:
    """Open and activate a :class:`BucketSession` for ``provider``.

    Resolves the active bucket id via the canonical precedence chain
    (env override > pointer file). When the chain yields no active
    profile, falls back to ``fallback_bucket_id`` if supplied (the
    Unsecured provider uses ``"unsecured"`` as a stable label so the
    engine cache keys consistently). When neither resolves, raises
    :class:`~adapters.persistence.storage.bucket.NoActiveBucketError`
    with the failed storage-selection observation.

    Stores the opened session and activation context manager on the provider so
    :func:`exit_provider_session` can tear them down. Provider activation is a
    custody/read boundary, not a mutation lock: application mutation spans own
    canonical bucket locking so read-only sessions remain concurrent and the
    pointer-first lock order remains intact.
    """
    from .....core.config import load_settings
    from ..bucket import NoActiveBucketError
    from ._active_session import activate_session
    from ._bucket_session import BucketSession

    if provider._session is not None:
        from ._errors import MasterKeyReentrantError

        raise MasterKeyReentrantError(type(provider).__name__)

    bucket_id = resolve_active_bucket_id() or fallback_bucket_id
    if not bucket_id:
        raise NoActiveBucketError()

    settings = load_settings()
    key_bytes = provider.get_master_key()
    if not isinstance(provider, UnsecuredMasterKeyProvider):
        # A secured provider yields a key-encryption key, never the bucket's
        # data key. The bucket DEK lives in the profile's own password custody
        # and is unwrapped by the profile-login boundary, which then binds the
        # session this function would otherwise be opening blind.
        raise MasterKeyMaterialMissingError(
            context={
                "active_bucket_selected": True,
                "master_key_material_available": False,
            },
        )
    dek_bytes = key_bytes
    idle_minutes = settings.cadrumo_bucket_default_idle_lock_minutes
    absolute_minutes = settings.cadrumo_bucket_default_session_absolute_minutes
    session = BucketSession.open(
        bucket_id=bucket_id,
        kek=key_bytes,
        dek=dek_bytes,
        idle_minutes=idle_minutes,
        absolute_minutes=absolute_minutes,
        opened_at=now(),
        unsecured_backend=isinstance(provider, UnsecuredMasterKeyProvider),
        storage_root=settings.cadrumo_local_storage_root,
    )
    activation = activate_session(session)
    activation.__enter__()
    provider._session = session
    provider._activation_cm = activation
    try:
        if session.unsecured_backend:
            refuse_unsecured_bucket_with_real_profile(session)
    except BaseException:
        exit_provider_session(provider, None, None, None)
        raise
    return session


class UnsecuredMasterKeyProvider:
    """Master-key provider for testing / throwaway scenarios.

    Returns a published deterministic 32-byte master key. The substrate's
    encryption pipeline is unchanged; only the wrapping key is publicly
    known. Provides **ZERO confidentiality**.

    Activation requires both signals:

    - ``CADRUMO_ALLOW_UNENCRYPTED=1`` environment variable (the hostile-
      named opt-out gate).
    - ``cadrumo_secret_store_backend=unsecured`` setting (or equivalent
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
        exit_provider_session(self, exc_type, exc, tb)


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
            "unsecured storage backend is incompatible with a real tax id; either remove "
            "CADRUMO_ALLOW_UNENCRYPTED=1 / cadrumo_secret_store_backend=unsecured, "
            "or use a synthetic placeholder (e.g. '00000000T').",
        )
