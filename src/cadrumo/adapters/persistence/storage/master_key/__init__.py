"""Master-key substrate: providers, sessions, and BIP-39 recovery.

Public surface for at-rest key custody. Re-exports the provider family
:class:`MasterKeyProvider` and its one surviving implementation
:class:`UnsecuredMasterKeyProvider`, and the :func:`activate_session`
context manager that binds unlocked key material to the active bucket
session. The shared-master providers, their backend resolver and its
passphrase-callback alias are deleted: the active master key is the
unlocked bucket's own data key, so a process-wide key store had no
reader. :class:`NoActiveBucketSessionError`,
:func:`close_active_bucket_session`, and :func:`suspend_active_session`
expose the same session boundary to callers, tests, and bootstrap flows.

KDF and file-custody helpers are exported through :class:`KdfParams`,
:func:`derive_kek_with_params`, the Argon2id cost constants, the
unsecured-provider safety guard
(:func:`refuse_unsecured_with_real_nif` and
:func:`looks_like_real_tax_id`).

Recovery is not exported here at all. Enrolment and restore are
per-profile custody operations owned by
:mod:`cadrumo.adapters.persistence.storage.custody`, and the
shared-master wrapping primitives that once mirrored one process-wide
key under a recovery key have been deleted rather than left standing:
nothing wrote the artefact they read, so they guarded no material this
build could produce. Importing this package does not resolve providers, acquire
keys, unwrap recovery material, or write custody files; callers must
invoke the exported operations explicitly.

The per-profile acceleration receipt that carries authenticated session state
across processes is NOT here: it belongs to
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
from .errors import MasterKeyReentrantError
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
    MasterKeyProvider,
    UnsecuredMasterKeyProvider,
    looks_like_real_tax_id,
    refuse_unsecured_bucket_with_real_profile,
    refuse_unsecured_with_real_nif,
)
from ._master_key_derivation import derive_kek_with_params

__all__ = [
    "ARGON2_VERSION",
    "MAX_MEMORY_COST_KIB",
    "MAX_PARALLELISM",
    "MAX_TIME_COST",
    "MIN_MEMORY_COST_KIB",
    "MIN_PARALLELISM",
    "MIN_TIME_COST",
    "BucketSession",
    "KdfParams",
    "LoginThrottleState",
    "MasterKeyProvider",
    "MasterKeyReentrantError",
    "NoActiveBucketSessionError",
    "ThrottleEvaluation",
    "UnsecuredMasterKeyProvider",
    "activate_session",
    "active_bucket_session_serves",
    "bind_active_bucket_session",
    "close_active_bucket_session",
    "close_all_live_bucket_sessions",
    "current_active_bucket_session",
    "derive_kek_with_params",
    "evaluate_idle",
    "evaluate_login_throttle",
    "get_active_hmac_subkey",
    "get_active_master_key",
    "has_active_bucket_session",
    "login_throttle_path",
    "looks_like_real_tax_id",
    "record_login_failure",
    "refuse_unsecured_bucket_with_real_profile",
    "refuse_unsecured_with_real_nif",
    "reset_login_throttle",
    "session_serves_bucket",
    "suspend_active_session",
]
