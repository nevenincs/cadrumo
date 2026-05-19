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

__all__ = [
    "EphemeralMasterKeyProvider",
    "FileFallbackMasterKeyProvider",
    "KeyringMasterKeyProvider",
    "MasterKeyProvider",
    "RecoveryKey",
    "UnsecuredMasterKeyProvider",
    "WrappedMasterKey",
    "activate_master_key_provider",
    "atomic_write_secure_bytes",
    "decode_mnemonic",
    "encode_mnemonic",
    "generate_recovery_key",
    "get_master_key_provider",
    "load_wrapped_master_key",
    "looks_like_real_tax_id",
    "refuse_unsecured_with_real_nif",
    "save_wrapped_master_key",
    "unwrap_master_key",
    "wrap_master_key",
]
