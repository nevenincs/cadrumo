"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from .....application.user_profile.custody_ports import (
    ProfilePassphraseKdfParameters,
    ProfileRecordCryptoError,
    ProfileRecordEncryptedBlob,
)
from ..crypto.aead import EncryptedBlob, decrypt_record
from ..master_key.master_key_derivation import derive_kek_with_params
from ..profile_custody import _PersistenceProfileRecordCrypto


def open_with_passphrase(
    self: object,
    blob: ProfileRecordEncryptedBlob,
    *,
    passphrase: bytes,
    parameters: ProfilePassphraseKdfParameters,
    associated_data: bytes,
) -> bytes:
    if not isinstance(self, _PersistenceProfileRecordCrypto):
        raise TypeError("fixture requires the persistence record crypto adapter")
    policy = self.passphrase_kdf_policy()
    if parameters.version != policy.version or not self.passphrase_kdf_window_accepts(
        memory_cost=parameters.memory_cost,
        time_cost=parameters.time_cost,
        parallelism=parameters.parallelism,
        salt=parameters.salt,
    ):
        raise ProfileRecordCryptoError("profile passphrase KDF parameters are unsupported")
    try:
        sealing_key = derive_kek_with_params(
            passphrase,
            parameters.salt,
            memory_cost=parameters.memory_cost,
            time_cost=parameters.time_cost,
            parallelism=parameters.parallelism,
        )
        return decrypt_record(
            EncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext),
            key=sealing_key,
            associated_data=associated_data,
        )
    except Exception as exc:
        raise ProfileRecordCryptoError("profile passphrase record decryption failed") from exc
