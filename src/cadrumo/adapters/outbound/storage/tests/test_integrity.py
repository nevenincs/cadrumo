"""Provider-neutral integrity guards for outbound storage payload metadata."""

from __future__ import annotations

import pytest

from .....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .. import OutboundStorageIntegrityError
from .._integrity import require_full_sha256_content_hash, verify_content_hash, verify_payload_byte_length

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _assert_safety(verdict, condition_id: str, facts: dict[str, object]) -> None:
    assert verdict.failed_condition_id == condition_id
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.evidence_id == f"{condition_id}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert dict(evidence.values) == facts


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
    _assert_safety(raised.value.terminal_precondition_verdict, "storage.integrity.payload_byte_length_matches", {
        "provider": provider, "stored_byte_length": "1", "actual_byte_length": "11",
    })


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
    _assert_safety(raised.value.terminal_precondition_verdict, "storage.integrity.sha256_digest_valid", {
        "provider": "Google Drive", "stored_hash": stored_hash,
    })


def test_content_hash_mismatch_carries_exact_safety_verdict() -> None:
    with pytest.raises(OutboundStorageIntegrityError) as raised:
        verify_content_hash("actual", "stored", message="mismatch", context={"provider": "local"}, translated_message="x")
    _assert_safety(raised.value.terminal_precondition_verdict, "storage.integrity.content_hash_matches", {"provider": "local"})
