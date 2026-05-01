"""Master-key substrate: providers, KDF migration, BIP-39 recovery.

Bucket boundary established by audit-4 in the aeat-restructure ADR.
"""

from __future__ import annotations

from ._master_key import (
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    MigrationResult,
    UnsecuredMasterKeyProvider,
    atomic_write_secure_bytes,
    get_master_key_provider,
    looks_like_real_tax_id,
    migrate_master_key_kdf,
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
    "MigrationResult",
    "RecoveryKey",
    "UnsecuredMasterKeyProvider",
    "WrappedMasterKey",
    "atomic_write_secure_bytes",
    "decode_mnemonic",
    "encode_mnemonic",
    "generate_recovery_key",
    "get_master_key_provider",
    "load_wrapped_master_key",
    "looks_like_real_tax_id",
    "migrate_master_key_kdf",
    "refuse_unsecured_with_real_nif",
    "save_wrapped_master_key",
    "unwrap_master_key",
    "wrap_master_key",
]
