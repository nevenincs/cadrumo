"""Native profile proof for the five worker-owned evidence follow-up reads."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceAttachmentViewRequest,
)
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import unwrap_cli_result
from ...tests.evidence_followup_operation_test_support import prepare_evidence_followup_conformance_case
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Followup",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "contact.postcode": "28013",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}
_DRIVE_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_native_profile_reads_all_evidence_followup_surfaces(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Queue, attachment, consent, and full review projections cross the profile worker."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-evidence-followup", facts=_PROFILE_FACTS)

        assert profile.label is not None
        login_profile(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        bucket_id = UUID(resolve_login_target(profile.label).bucket_id)
        case = prepare_evidence_followup_conformance_case(
            LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
            profile_id=bucket_id,
            operation=authority_operation,
        )
        assert isinstance(case.request, LedgerEvidenceAttachmentViewRequest)
        attachment_id = case.request.attachment_id
        close_active_bucket_session()
        queue = _invoke(profile, "app", "ledger", "evidence", "attachment-queue")
        assert queue.exit_code == 0, (queue.output, failures)
        queued = unwrap_cli_result(queue)
        assert queued["count"] == 1
        assert queued["rows"][0]["attachment_id"] == attachment_id
        assert queued["rows"][0]["source"] == "GOOGLE_DRIVE"
        assert queued["rows"][0]["pending_review"] is True

        viewed_attachment = _invoke(profile, "app", "ledger", "evidence", "attachment-view", attachment_id)
        assert viewed_attachment.exit_code == 0, (viewed_attachment.output, failures)
        attachment = unwrap_cli_result(viewed_attachment)
        assert attachment["bucket_id"] == queued["bucket_id"]
        assert attachment["attachment_id"] == attachment_id
        assert attachment["sha256"] == attachment_id
        assert attachment["provider_locator"] == _DRIVE_FILE_ID
        assert attachment["pending_review"] is True
        assert not {"metadata", "notes"}.intersection(attachment)

        consent = _invoke(profile, "app", "ledger", "evidence", "consent", "list")
        assert consent.exit_code == 0, (consent.output, failures)
        survey = unwrap_cli_result(consent)
        assert survey["bucket_id"] == queued["bucket_id"]
        assert survey["transmitted_bytes_are_unrecallable"] is True
        assert len(survey["consented_dispatches"]) == 1
        dispatch = survey["consented_dispatches"][0]
        assert dispatch["provider"] == "openai"
        assert dispatch["surface"] == "app.ledger.evidence.extract"
        assert "profile_bucket_id" not in dispatch
        derived = survey["cloud_derived_artefacts"]
        assert len(derived) == 1
        assert derived[0]["provenance_stamp"]

        review_queue = _invoke(profile, "app", "ledger", "evidence", "review", "list")
        assert review_queue.exit_code == 0, (review_queue.output, failures)
        review = unwrap_cli_result(review_queue)
        assert review["bucket_id"] == queued["bucket_id"]
        assert review["filters"] == []
        assert len(review["rows"]) == 1
        evidence_id = review["rows"][0]["evidence_reference"]
        assert derived[0]["evidence_reference"] == evidence_id

        review_view = _invoke(profile, "app", "ledger", "evidence", "review", "view", evidence_id)
        assert review_view.exit_code == 0, (review_view.output, failures)
        reviewed = unwrap_cli_result(review_view)
        assert reviewed["bucket_id"] == queued["bucket_id"]
        assert reviewed["evidence_reference"] == evidence_id
        fields = {row["field"]: row for row in reviewed["fields"]}
        assert fields["invoice_number"]["value"] == "FAC-2024-0007"
        assert fields["invoice_number"]["origin"] == "exact_structured"
        assert fields["invoice_number"]["anchor"] == "FAC-2024-0007"
        assert fields["taxable_base"]["value"] == "100.00"
        assert isinstance(reviewed["discrepancies"], list)
        assert isinstance(reviewed["blockers"], list)
