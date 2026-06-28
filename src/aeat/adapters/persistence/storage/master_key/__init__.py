"""Master-key substrate: providers and BIP-39 recovery.

Public surface for the at-rest master-key plumbing. Re-exports the
provider hierarchy (:class:`MasterKeyProvider`,
:class:`KeyringMasterKeyProvider`, :class:`FileFallbackMasterKeyProvider`,
:class:`UnsecuredMasterKeyProvider`, :class:`EphemeralMasterKeyProvider`),
the :func:`get_master_key_provider` resolver, the unsecured-provider safety guard
(:func:`refuse_unsecured_with_real_nif`,
:func:`looks_like_real_tax_id`), the :func:`atomic_write_secure_bytes`
helper, and the BIP-39 recovery primitives
(:class:`RecoveryKey`, :class:`WrappedMasterKey`,
:func:`generate_recovery_key`, :func:`encode_mnemonic`,
:func:`decode_mnemonic`, :func:`wrap_master_key`,
:func:`unwrap_master_key`, :func:`save_wrapped_master_key`,
:func:`load_wrapped_master_key`).
"""

from __future__ import annotations

from ._active_session import NoActiveBucketSessionError, activate_session, suspend_active_session
from ._kdf_params import KdfParams
from ._master_key import (
    EphemeralMasterKeyProvider,
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
from ._master_key_derivation import (
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    derive_kek_with_params,
)
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
    load_recovery_envelope,
    mint_recovery_envelope,
    open_session_from_recovery,
    save_recovery_envelope,
    unwrap_recovery_envelope,
    verify_recovery_mnemonic,
)
from ._recovery_record import RecoveryRecord

__all__ = [
    "ARGON2_MEMORY_COST_KIB",
    "ARGON2_PARALLELISM",
    "ARGON2_TIME_COST",
    "EphemeralMasterKeyProvider",
    "FileFallbackMasterKeyProvider",
    "KdfParams",
    "KeyringMasterKeyProvider",
    "MasterKeyProvider",
    "MintedRecovery",
    "NoActiveBucketSessionError",
    "RecoveryKey",
    "RecoveryRecord",
    "UnsecuredMasterKeyProvider",
    "WrappedMasterKey",
    "activate_master_key_provider",
    "activate_session",
    "atomic_write_secure_bytes",
    "decode_mnemonic",
    "derive_kek_with_params",
    "encode_mnemonic",
    "generate_recovery_key",
    "get_master_key_provider",
    "load_recovery_envelope",
    "load_wrapped_master_key",
    "looks_like_real_tax_id",
    "mint_recovery_envelope",
    "open_session_from_recovery",
    "refuse_unsecured_with_real_nif",
    "save_recovery_envelope",
    "save_wrapped_master_key",
    "suspend_active_session",
    "unwrap_master_key",
    "unwrap_recovery_envelope",
    "verify_recovery_mnemonic",
    "wrap_master_key",
]
