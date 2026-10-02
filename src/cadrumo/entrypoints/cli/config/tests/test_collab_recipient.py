"""Closed public CLI payloads for trusted collaboration recipients."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pydantic import ValidationError

from ..collab_payloads import ConfigCollabRecipientListResult, RecipientFingerprintRowPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _fresh_public_key_hex() -> str:
    return X25519PrivateKey.generate().public_key().public_bytes_raw().hex()


def test_recipient_payload_preserves_every_public_record_field() -> None:
    key = _fresh_public_key_hex()
    fingerprint = sha256(bytes.fromhex(key)).hexdigest()
    added_at = datetime(2026, 8, 1, tzinfo=UTC)
    row = RecipientFingerprintRowPayload(
        recipient_id="my-accountant",
        label="My accountant",
        public_key_hex=key,
        fingerprint_sha256=fingerprint,
        added_at=added_at,
    )
    result = ConfigCollabRecipientListResult(recipients=[row], count=1)

    assert result.model_dump(mode="json") == {
        "recipients": [
            {
                "recipient_id": "my-accountant",
                "label": "My accountant",
                "public_key_hex": key,
                "fingerprint_sha256": fingerprint,
                "added_at": added_at.isoformat().replace("+00:00", "Z"),
            }
        ],
        "count": 1,
    }


def test_recipient_payload_rejects_an_arbitrary_fingerprint() -> None:
    with pytest.raises(ValidationError, match="fingerprint_sha256"):
        RecipientFingerprintRowPayload(
            recipient_id="my-accountant",
            label="My accountant",
            public_key_hex=_fresh_public_key_hex(),
            fingerprint_sha256="0" * 64,
            added_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
