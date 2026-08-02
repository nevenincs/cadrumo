"""Provider-neutral integrity guards for outbound storage payload metadata."""

from __future__ import annotations

import pytest

from .. import OutboundStorageIntegrityError
from .._integrity import require_full_sha256_content_hash, verify_payload_byte_length

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize("provider", ("local sidecar", "Google Drive"))
def test_payload_byte_length_guard_refuses_provider_metadata_drift(provider: str) -> None:
    """The shared guard makes the same refusal for either provider metadata source."""

    with pytest.raises(OutboundStorageIntegrityError) as raised:
        verify_payload_byte_length(
            b"exact bytes",
            1,
            message=f"{provider} byte_length mismatch",
            context={"provider": provider},
            translated_message="adapters.outbound.storage.local.errors.content_hash_mismatch",
        )

    assert raised.value.context == {
        "provider": provider,
        "stored_byte_length": "1",
        "actual_byte_length": "11",
    }


@pytest.mark.parametrize("stored_hash", ("", "md5-deadbeef", "sha256-unverified", "sha256-" + "g" * 64))
def test_full_sha256_guard_refuses_unverified_or_malformed_provider_hashes(stored_hash: str) -> None:
    with pytest.raises(OutboundStorageIntegrityError, match="full SHA-256") as raised:
        require_full_sha256_content_hash(
            stored_hash,
            message="full SHA-256 content hash required",
            context={"provider": "Google Drive"},
            translated_message="adapters.outbound.storage.google_drive.errors.content_hash_mismatch",
        )

    assert raised.value.context == {"provider": "Google Drive", "stored_hash": stored_hash}
