"""Crypto substrate: AEAD primitives plus encrypted SQLAlchemy helpers.

Public surface for the at-rest crypto stack. Re-exports the AEAD
primitives (:func:`~cadrumo.adapters.persistence.storage.crypto.encrypt_record`,
:func:`~cadrumo.adapters.persistence.storage.crypto.decrypt_record`,
:func:`derive_key`, :class:`EncryptedBlob`, and the
:data:`KEY_SIZE` / :data:`NONCE_SIZE` / :data:`GCM_TAG_SIZE`
constants) alongside the SQLAlchemy ``TypeDecorator`` set
(:class:`EncryptedString`, :class:`EncryptedBytes`,
:class:`EncryptedJSON`, :class:`HashedLookup`), the
:class:`EncryptedPayload` JSON guard, and
:func:`secure_object_key_digest` for secure-object row AAD binding.

Column-level decrypt and encrypt operations resolve key bytes through
:func:`adapters.persistence.storage.master_key._active_session.get_active_master_key`
on the active
:class:`adapters.persistence.storage.master_key._bucket_session.BucketSession`.
This facade only re-exports crypto objects; it does not acquire key
material or activate a session at import time.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._crypto import (
        GCM_TAG_SIZE,
        KEY_SIZE,
        NONCE_SIZE,
        EncryptedBlob,
        decrypt_record,
        derive_key,
        encrypt_record,
    )
    from ._encrypted_columns import (
        EncryptedBytes,
        EncryptedJSON,
        EncryptedPayload,
        EncryptedString,
        HashedLookup,
        decrypt_encrypted_bytes_column,
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        hkdf_hmac_digest,
        secure_object_key_digest,
        secure_object_payload_aad,
    )


# Name -> the one submodule that owns it. The two halves of this facade have
# very different costs: ``_crypto`` is AEAD primitives over ``cryptography``,
# while ``_encrypted_columns`` pulls SQLAlchemy and reaches back into
# ``master_key`` for active-session key bytes. Binding them eagerly meant any
# caller of the AEAD primitives -- including the supervised key-derivation
# child, which performs one Argon2id hash and one AEAD operation -- paid for
# the ORM stack. It also made ``custody`` -> ``crypto`` -> ``master_key`` ->
# ``custody`` a real import cycle that only the parent facade's import order
# was hiding. Ownership is unchanged; only WHEN each submodule executes moved.
_LAZY_EXPORTS: dict[str, str] = {
    "EncryptedBlob": "._crypto",
    "GCM_TAG_SIZE": "._crypto",
    "KEY_SIZE": "._crypto",
    "NONCE_SIZE": "._crypto",
    "decrypt_record": "._crypto",
    "derive_key": "._crypto",
    "encrypt_record": "._crypto",
    "EncryptedBytes": "._encrypted_columns",
    "EncryptedJSON": "._encrypted_columns",
    "EncryptedPayload": "._encrypted_columns",
    "EncryptedString": "._encrypted_columns",
    "HashedLookup": "._encrypted_columns",
    "decrypt_encrypted_bytes_column": "._encrypted_columns",
    "decrypt_secure_object_payload": "._encrypted_columns",
    "encrypt_secure_object_payload": "._encrypted_columns",
    "hkdf_hmac_digest": "._encrypted_columns",
    "secure_object_key_digest": "._encrypted_columns",
    "secure_object_payload_aad": "._encrypted_columns",
}


# Every loader target is a closed literal from the map above.  The attribute
# name selects one of these pre-bound loaders; it never becomes an import path.
_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str) -> object:
    """Resolve one public name by importing only the submodule that owns it.

    The resolved value is written into module globals, so only the first
    access to a name goes through this hook; every later one is an ordinary
    global lookup with no import machinery in the path.
    """
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    loader = _LAZY_MODULE_LOADERS.get(module_name)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_name!r}")
    value = getattr(loader(), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "GCM_TAG_SIZE",
    "KEY_SIZE",
    "NONCE_SIZE",
    "EncryptedBlob",
    "EncryptedBytes",
    "EncryptedJSON",
    "EncryptedPayload",
    "EncryptedString",
    "HashedLookup",
    "decrypt_encrypted_bytes_column",
    "decrypt_record",
    "decrypt_secure_object_payload",
    "derive_key",
    "encrypt_record",
    "encrypt_secure_object_payload",
    "hkdf_hmac_digest",
    "secure_object_key_digest",
    "secure_object_payload_aad",
]
