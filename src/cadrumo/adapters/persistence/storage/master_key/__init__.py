"""Master-key substrate: providers, sessions, and BIP-39 recovery.

Public surface for at-rest key custody. Re-exports the provider family
(:class:`MasterKeyProvider`, :class:`KeyringMasterKeyProvider`,
:class:`FileFallbackMasterKeyProvider`, and
:class:`UnsecuredMasterKeyProvider`), the
:func:`get_master_key_provider` resolver, and the
:func:`activate_master_key_provider` / :func:`activate_session`
context managers that bind unlocked key material to the active bucket
session. :class:`NoActiveBucketSessionError`,
:func:`close_active_bucket_session`, and :func:`suspend_active_session`
expose the same session boundary to callers, tests, and bootstrap flows.

KDF and file-custody helpers are exported through :class:`KdfParams`,
:func:`derive_kek_with_params`, the Argon2id cost constants, the
unsecured-provider safety guard
(:func:`refuse_unsecured_with_real_nif` and
:func:`looks_like_real_tax_id`), and
:func:`atomic_write_secure_bytes`.

Recovery exports include the low-level BIP-39 primitives
(:class:`RecoveryKey`, :class:`WrappedMasterKey`,
:func:`generate_recovery_key`, :func:`encode_mnemonic`,
:func:`decode_mnemonic`, :func:`wrap_master_key`,
:func:`unwrap_master_key`, :func:`save_wrapped_master_key`, and
:func:`load_wrapped_master_key`) plus the typed recovery-envelope
facade (:class:`MintedRecovery`, :class:`RecoveryRecord`,
:func:`mint_recovery_envelope`, :func:`load_recovery_envelope`,
:func:`save_recovery_envelope`, :func:`unwrap_recovery_envelope`,
:func:`verify_recovery_mnemonic`, and
:func:`open_session_from_recovery`). Importing this package does not
resolve providers, acquire keys, unwrap recovery material, or write
custody files; callers must invoke the exported operations explicitly.
"""

from __future__ import annotations

from ._active_session import (
    NoActiveBucketSessionError,
    activate_session,
    close_active_bucket_session,
    current_active_bucket_session,
    get_active_master_key,
    has_active_bucket_session,
    suspend_active_session,
)
from ._bucket_session import BucketSession
from ._dek_wrap import WrappedDek, unwrap_dek, wrap_dek
from ._errors import MasterKeyReentrantError
from ._idle_timeout import evaluate_idle
from ._kdf_params import KdfParams
from ._login_throttle import (
    LoginThrottleState,
    ThrottleEvaluation,
    evaluate_login_throttle,
    login_throttle_path,
    record_login_failure,
    reset_login_throttle,
)
from ._master_key import (
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    UnsecuredMasterKeyProvider,
    activate_master_key_provider,
    atomic_write_secure_bytes,
    get_master_key_provider,
    looks_like_real_tax_id,
    refuse_unsecured_with_real_nif,
)
from ._master_key_bucket_dek import (
    bucket_dek_path,
    load_or_mint_bucket_dek,
    read_wrapped_bucket_dek,
    write_wrapped_bucket_dek,
)
from ._master_key_derivation import (
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    derive_kek_with_params,
)
from ._provider_session import exit_provider_session
from ._recovery import (
    RecoveryKey,
    WrappedMasterKey,
    decode_mnemonic,
    encode_mnemonic,
    generate_recovery_key,
    load_wrapped_master_key,
    save_wrapped_master_key,
    unwrap_master_key,
    wrap_master_key,
)
from ._recovery_facade import (
    MintedRecovery,
    RecoveryEnrollmentMode,
    RecoveryEnrollmentOutcome,
    RecoveryLifecycleStatus,
    RecoveryRecoverOutcome,
    RecoveryVerifyOutcome,
    load_recovery_envelope,
    mint_recovery_envelope,
    open_session_from_recovery,
    recovery_create,
    recovery_recover,
    recovery_rotate,
    recovery_status,
    recovery_verify,
    save_recovery_envelope,
    unwrap_recovery_envelope,
    verify_recovery_mnemonic,
)
from ._recovery_record import RecoveryRecord

__all__ = [
    "ARGON2_MEMORY_COST_KIB",
    "ARGON2_PARALLELISM",
    "ARGON2_TIME_COST",
    "BucketSession",
    "FileFallbackMasterKeyProvider",
    "KdfParams",
    "KeyringMasterKeyProvider",
    "LoginThrottleState",
    "MasterKeyProvider",
    "MasterKeyReentrantError",
    "MintedRecovery",
    "NoActiveBucketSessionError",
    "RecoveryEnrollmentMode",
    "RecoveryEnrollmentOutcome",
    "RecoveryKey",
    "RecoveryLifecycleStatus",
    "RecoveryRecord",
    "RecoveryRecoverOutcome",
    "RecoveryVerifyOutcome",
    "ThrottleEvaluation",
    "UnsecuredMasterKeyProvider",
    "WrappedDek",
    "WrappedMasterKey",
    "activate_master_key_provider",
    "activate_session",
    "atomic_write_secure_bytes",
    "bucket_dek_path",
    "close_active_bucket_session",
    "current_active_bucket_session",
    "decode_mnemonic",
    "derive_kek_with_params",
    "encode_mnemonic",
    "evaluate_idle",
    "evaluate_login_throttle",
    "exit_provider_session",
    "generate_recovery_key",
    "get_active_master_key",
    "get_master_key_provider",
    "has_active_bucket_session",
    "load_or_mint_bucket_dek",
    "load_recovery_envelope",
    "load_wrapped_master_key",
    "login_throttle_path",
    "looks_like_real_tax_id",
    "mint_recovery_envelope",
    "open_session_from_recovery",
    "read_wrapped_bucket_dek",
    "record_login_failure",
    "recovery_create",
    "recovery_recover",
    "recovery_rotate",
    "recovery_status",
    "recovery_verify",
    "refuse_unsecured_with_real_nif",
    "reset_login_throttle",
    "save_recovery_envelope",
    "save_wrapped_master_key",
    "suspend_active_session",
    "unwrap_dek",
    "unwrap_master_key",
    "unwrap_recovery_envelope",
    "verify_recovery_mnemonic",
    "wrap_dek",
    "wrap_master_key",
    "write_wrapped_bucket_dek",
]
