"""Purpose-bound automation encryption and high-entropy API-key verification."""

from __future__ import annotations

import base64
import json
import secrets
from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes, ValidationError

from .....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .....core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from ..crypto.aead import EncryptedBlob, decrypt_record, encrypt_record
from ..errors import DecryptionError, EncryptionError

MAX_CONTROL_BYTES = 1024 * 1024
API_KEY_PREFIX = "cadrumo-api-v1"


class CustodyAutomationKeyIssuer:
    """Bind the application issuer port to the canonical versioned codec."""

    @staticmethod
    def generate() -> tuple[UUID, SecretBytes]:
        """Generate through the canonical custody codec."""
        return generate_api_key()

    @staticmethod
    def verifier(secret: SecretBytes) -> tuple[UUID, str]:
        """Verify through the canonical custody codec."""
        return api_key_verifier(secret)


def canonical_record(record: BaseModel) -> bytes:
    """Canonical internal serialization; callers seal private records immediately."""
    return canonical_json_bytes(_ordered_inventory(record.model_dump(mode="json")))


def _ordered_inventory(value: object) -> object:
    # These records contain allow sets and identity inventories, not ordered work.
    if isinstance(value, dict):
        return {key: _ordered_inventory(item) for key, item in cast(dict[str, object], value).items()}
    if isinstance(value, list):
        return sorted((_ordered_inventory(item) for item in cast(list[object], value)), key=canonical_json_bytes)
    return value


def parse_record[T: BaseModel](model: type[T], raw: bytes) -> T:
    """Reject duplicates, noncanonical encodings, unknown versions and fields."""
    try:
        if not raw or len(raw) > MAX_CONTROL_BYTES:
            raise ValueError
        json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
        record = model.model_validate_json(raw)
        if canonical_record(record) != raw:
            raise ValueError
        return record
    except (ValueError, TypeError, ValidationError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None


def generate_api_key() -> tuple[UUID, SecretBytes]:
    """Mint for protected delivery; never send the returned bytes to ordinary output."""
    key_id = uuid4()
    secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=")
    return key_id, SecretBytes(API_KEY_PREFIX.encode() + b"." + str(key_id).encode() + b"." + secret)


def api_key_verifier(value: SecretBytes) -> tuple[UUID, str]:
    """Validate the current secret format and derive its domain-separated verifier."""
    try:
        raw = value.get_secret_value()
        if len(raw) != len(API_KEY_PREFIX) + 81:
            raise ValueError
        prefix, identifier, encoded = raw.split(b".")
        key_id = UUID(identifier.decode("ascii"))
        secret = base64.b64decode(encoded + b"=", altchars=b"-_", validate=True)
        if (
            prefix != API_KEY_PREFIX.encode()
            or str(key_id).encode() != identifier
            or len(secret) != 32
            or base64.urlsafe_b64encode(secret).rstrip(b"=") != encoded
        ):
            raise ValueError
        verifier = sha256_hex(
            b"cadrumo.api-key-verifier/v1\x00"
            + canonical_json_bytes({"version": 1, "key_id": str(key_id), "secret": encoded.decode("ascii")})
        )
        return key_id, verifier
    except (ValueError, UnicodeError):
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED) from None


def seal_automation(plaintext: bytes, key: SecretBytes, aad: bytes) -> str:
    """Use the canonical AES-256-GCM primitive with a fresh nonce and full tag."""
    try:
        return base64.b64encode(
            encrypt_record(plaintext, key=key.get_secret_value(), associated_data=aad).to_wire()
        ).decode("ascii")
    except (EncryptionError, ValueError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None


def open_automation(ciphertext: str, key: SecretBytes, aad: bytes) -> bytes:
    """Authenticate every routing coordinate before returning sealed contents."""
    try:
        raw = base64.b64decode(ciphertext, validate=True)
        if base64.b64encode(raw).decode("ascii") != ciphertext:
            raise ValueError
        return decrypt_record(EncryptedBlob.from_wire(raw), key=key.get_secret_value(), associated_data=aad)
    except (DecryptionError, EncryptionError, ValueError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
