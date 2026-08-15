"""Master-key substrate: providers, sessions, and BIP-39 recovery.

Public surface for at-rest key custody. Re-exports the provider family
(:class:`MasterKeyProvider`, :class:`KeyringMasterKeyProvider`,
:class:`FileFallbackMasterKeyProvider`, and
:class:`UnsecuredMasterKeyProvider`), the
:func:`get_master_key_provider` resolver together with the
:obj:`PassphraseCallback` alias naming its passphrase-resolver
parameter, and the
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

Recovery exports include the master-key wrapping primitives
(:class:`WrappedMasterKey`, :func:`wrap_master_key`,
:func:`unwrap_master_key`, :func:`save_wrapped_master_key`, and
:func:`load_wrapped_master_key`) plus the on-disk envelope record
:class:`RecoveryRecord`. Recovery ENROLMENT and RESTORE are per-profile
custody operations owned by
:mod:`cadrumo.adapters.persistence.storage.custody`; the global
recovery facade that once mirrored a single shared master key is
retired. Importing this package does not resolve providers, acquire
keys, unwrap recovery material, or write custody files; callers must
invoke the exported operations explicitly.

The per-profile acceleration receipt that carries the ``aeat config login``
state across processes is NOT here: it belongs to
:mod:`cadrumo.adapters.persistence.storage.custody`, which owns per-profile
password custody. What remains is the shared-master surface plus the live
key-holding session machinery both surfaces use — :class:`BucketSession` and
its activation context, which the providers own — and the failed-login
throttle (:class:`LoginThrottleState`, :func:`evaluate_login_throttle`).
"""

from __future__ import annotations

from ._active_session import (
    NoActiveBucketSessionError,
    activate_session,
    active_bucket_session_serves,
    bind_active_bucket_session,
    close_active_bucket_session,
    close_all_live_bucket_sessions,
    current_active_bucket_session,
    get_active_hmac_subkey,
    get_active_master_key,
    has_active_bucket_session,
    session_serves_bucket,
    suspend_active_session,
)
from ._bucket_session import BucketSession
from ._errors import MasterKeyReentrantError
from ._idle_timeout import evaluate_idle
from ._kdf_params import (
    ARGON2_VERSION,
    MAX_MEMORY_COST_KIB,
    MAX_PARALLELISM,
    MAX_TIME_COST,
    MIN_MEMORY_COST_KIB,
    MIN_PARALLELISM,
    MIN_TIME_COST,
    KdfParams,
)
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
    refuse_unsecured_bucket_with_real_profile,
    refuse_unsecured_with_real_nif,
)
from ._master_key_derivation import (
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    derive_kek_with_params,
)
from ._master_key_io import PassphraseCallback
from ._provider_session import exit_provider_session
from ._recovery import (
    WrappedMasterKey,
    load_wrapped_master_key,
    save_wrapped_master_key,
    unwrap_master_key,
    wrap_master_key,
)
from ._recovery_record import RecoveryRecord

__all__ = [
    "ARGON2_MEMORY_COST_KIB",
    "ARGON2_PARALLELISM",
    "ARGON2_TIME_COST",
    "ARGON2_VERSION",
    "MAX_MEMORY_COST_KIB",
    "MAX_PARALLELISM",
    "MAX_TIME_COST",
    "MIN_MEMORY_COST_KIB",
    "MIN_PARALLELISM",
    "MIN_TIME_COST",
    "BucketSession",
    "FileFallbackMasterKeyProvider",
    "KdfParams",
    "KeyringMasterKeyProvider",
    "LoginThrottleState",
    "MasterKeyProvider",
    "MasterKeyReentrantError",
    "NoActiveBucketSessionError",
    "PassphraseCallback",
    "RecoveryRecord",
    "ThrottleEvaluation",
    "UnsecuredMasterKeyProvider",
    "WrappedMasterKey",
    "activate_master_key_provider",
    "activate_session",
    "active_bucket_session_serves",
    "atomic_write_secure_bytes",
    "bind_active_bucket_session",
    "close_active_bucket_session",
    "close_all_live_bucket_sessions",
    "current_active_bucket_session",
    "derive_kek_with_params",
    "evaluate_idle",
    "evaluate_login_throttle",
    "exit_provider_session",
    "get_active_hmac_subkey",
    "get_active_master_key",
    "get_master_key_provider",
    "has_active_bucket_session",
    "load_wrapped_master_key",
    "login_throttle_path",
    "looks_like_real_tax_id",
    "record_login_failure",
    "refuse_unsecured_bucket_with_real_profile",
    "refuse_unsecured_with_real_nif",
    "reset_login_throttle",
    "save_wrapped_master_key",
    "session_serves_bucket",
    "suspend_active_session",
    "unwrap_master_key",
    "wrap_master_key",
]
