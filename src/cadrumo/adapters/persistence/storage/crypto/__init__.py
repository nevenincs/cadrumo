"""Crypto substrate: AEAD primitives plus encrypted SQLAlchemy helpers.

Inert namespace. Import directly from the owning module:
:mod:`~cadrumo.adapters.persistence.storage.crypto.aead` for the AEAD
primitives (:func:`encrypt_record`, :func:`decrypt_record`,
:func:`derive_key`, :class:`EncryptedBlob`, and the
:data:`KEY_SIZE` / :data:`NONCE_SIZE` / :data:`GCM_TAG_SIZE` constants), or
:mod:`~cadrumo.adapters.persistence.storage.crypto.encrypted_columns` for
the SQLAlchemy ``TypeDecorator`` set (:class:`EncryptedString`,
:class:`EncryptedBytes`, :class:`EncryptedJSON`, :class:`HashedLookup`),
the :class:`EncryptedPayload` JSON guard, and
:func:`secure_object_key_digest` / :func:`secure_object_payload_aad` /
:func:`encrypt_secure_object_payload` / :func:`decrypt_secure_object_payload`
/ :func:`decrypt_encrypted_bytes_column` for secure-object row handling.

This package previously carried a PEP 562 lazy re-export map so an AEAD-only
caller did not pay for importing SQLAlchemy and reaching back into
``master_key``. That map is retired: every consumer now imports the owning
submodule directly, so the package itself does nothing at import time and
carries no re-export cost to avoid.
"""

from __future__ import annotations
