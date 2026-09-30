"""Native profile proof for reviewed structured-invoice confirmation."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ._runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)
from .cli_runner import invoke_cached_cli

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
    "identity.surnames": "Evidence",
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
_STRUCTURED_INVOICE = (
    Path(__file__).resolve().parents[3]
    / "application"
    / "ledger"
    / "tests"
    / "_evidence_corpus"
    / "facturae_32_recargo_invoice.xml"
)


def _invoke(
    profile: NativeCliProfileFixture,
    *command: str,
    env: Mapping[str, str | None] | None = None,
) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
        env=env,
    )
    assert profile.passphrase not in result.output
    return result


def _confirm_args(
    evidence_id: str,
    *,
    source_sha256: str,
    draft_review_sha256: str,
) -> tuple[str, ...]:
    return (
        "app",
        "ledger",
        "evidence",
        "confirm",
        "--country-code",
        "ES",
        "--evidence-id",
        evidence_id,
        "--kind",
        "received",
        "--expected-source-sha256",
        source_sha256,
        "--expected-draft-review-sha256",
        draft_review_sha256,
    )


def test_native_structured_extract_confirm_readback_and_stale_digest_refusal(tmp_path: Path) -> None:
    """The operator can confirm exactly the XML draft reviewed, and stale review writes nothing."""
    staged = tmp_path / "facturae-recargo.xml"
    staged.write_bytes(_STRUCTURED_INVOICE.read_bytes())

    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-invoice-evidence", facts=_PROFILE_FACTS)

        added = _invoke(profile, "app", "ledger", "evidence", "add", str(staged), "--supplier", "Mayorista SL")
        assert added.exit_code == 0, (added.output, failures)
        evidence_id = unwrap_cli_result(added)["evidence_id"]
        assert isinstance(evidence_id, str) and len(evidence_id) == 16

        off_host_refusal = _invoke(
            profile,
            "app",
            "ledger",
            "evidence",
            "extract",
            "--evidence-id",
            evidence_id,
            "--off-host-provider",
            "OPENAI",
            "--acknowledge-off-host",
            env={"CADRUMO_EVIDENCE_CLOUD_UPLOAD_PERMITTED": "false"},
        )
        assert off_host_refusal.exit_code != 0, off_host_refusal.output
        refusal_error = require_error_document(off_host_refusal.output)["error"]
        refusal_context = refusal_error["context"]
        assert refusal_context["reason"] == "REFUSED_LLM_CONSENT"
        assert refusal_context["refusal_code"] == "REFUSED_LLM_CONSENT"
        assert refusal_context["terminal_condition"] == "refused"
        assert refusal_context["effect"] == "none"
        assert isinstance(refusal_context["operation_id"], str)
        assert len(refusal_context["operation_id"]) == 64
        assert refusal_error["action"]["failed_condition_id"] == "cli.refusal.completed"
        assert refusal_error["action"]["no_recovery_outcome"] == "operator_decision"
        assert any(
            item.stage == "profile_operation_returned" and item.definition_id == "ledger.evidence.extract"
            for item in failures
        )

        extracted = _invoke(profile, "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id)
        assert extracted.exit_code == 0, (extracted.output, failures)
        draft = unwrap_cli_result(extracted)
        source_sha256 = draft["source_sha256"]
        draft_review_sha256 = draft["draft_review_sha256"]
        assert isinstance(source_sha256, str) and len(source_sha256) == 64
        assert isinstance(draft_review_sha256, str) and len(draft_review_sha256) == 64
        assert draft["consent_audit_effect"] == "none"
        assert draft["supplier_name"] == "Mayorista Ejemplo SL"
        assert draft["invoice_number"] == "FAC-2024-0007"
        assert draft["taxable_base"] == "100.00"
        assert draft["iva_amount"] == "21.00"
        assert draft["recargo_amount"] == "5.20"
        assert draft["lines"] and draft["iva_breakdown"]
        assert draft["provenance"]
        assert draft["facturae_invoice_class"] == {"source_code": "OO", "kind": "ordinary"}

        unconfirmed = _invoke(profile, "app", "ledger", "invoice", "list")
        assert unconfirmed.exit_code == 0, (unconfirmed.output, failures)
        assert unwrap_cli_result(unconfirmed)["count"] == 0

        confirmed = _invoke(
            profile,
            *_confirm_args(
                evidence_id,
                source_sha256=source_sha256,
                draft_review_sha256=draft_review_sha256,
            ),
            "--invoice-number",
            "OPERATOR-FAC-2024-0007",
        )
        assert confirmed.exit_code == 0, (confirmed.output, failures)
        invoice = unwrap_cli_result(confirmed)
        assert invoice["created"] is True
        assert invoice["source_sha256"] == source_sha256
        assert invoice["reviewed_draft_sha256"] == draft_review_sha256
        assert invoice["invoice_number"] == "OPERATOR-FAC-2024-0007"
        assert invoice["grand_total"] == "126.20"
        assert invoice["confirmation_id"]
        extracted_provenance = {item["field"]: item for item in invoice["provenance"]}
        confirmed_provenance = {item["field"]: item for item in invoice["confirmed_provenance"]}
        assert extracted_provenance["invoice_number"]["anchor"] == "FAC-2024-0007"
        stamped_number = confirmed_provenance["invoice_number"]
        assert stamped_number["origin"] == "operator"
        assert stamped_number["grounding"] == "unanchored"
        assert stamped_number["anchor"] is None
        assert "FAC-2024-0007" in stamped_number["note"]
        assert confirmed_provenance["taxable_base"]["origin"] != "operator"

        viewed = _invoke(profile, "app", "ledger", "evidence", "view", evidence_id)
        assert viewed.exit_code == 0, (viewed.output, failures)
        before_refusal = unwrap_cli_result(viewed)
        assert before_refusal["invoice_number"] == "OPERATOR-FAC-2024-0007"
        assert before_refusal["taxable_base"] == "100.00"
        assert before_refusal["iva_amount"] == "21.00"

        listed = _invoke(profile, "app", "ledger", "invoice", "list")
        assert listed.exit_code == 0, (listed.output, failures)
        catalogue_before = unwrap_cli_result(listed)
        assert catalogue_before["count"] == 1
        catalogue_rows_before = catalogue_before["rows"]

        stale_digest = "0" * 64 if draft_review_sha256 != "0" * 64 else "1" * 64
        refused = _invoke(
            profile,
            *_confirm_args(
                evidence_id,
                source_sha256=source_sha256,
                draft_review_sha256=stale_digest,
            ),
        )
        assert refused.exit_code != 0, refused.output
        error = require_error_document(refused.output)["error"]
        context = error["context"]
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert context["refusal_code"] == "REFUSED_INVOICE_EVIDENCE_REVIEW_CHANGED"
        assert isinstance(context["reason"], str) and context["reason"]
        assert isinstance(context["operation_id"], str) and len(context["operation_id"]) == 64

        viewed_after = _invoke(profile, "app", "ledger", "evidence", "view", evidence_id)
        assert viewed_after.exit_code == 0, (viewed_after.output, failures)
        after_refusal = unwrap_cli_result(viewed_after)
        assert after_refusal == before_refusal

        listed_after = _invoke(profile, "app", "ledger", "invoice", "list")
        assert listed_after.exit_code == 0, (listed_after.output, failures)
        catalogue_after = unwrap_cli_result(listed_after)
        assert catalogue_after["count"] == catalogue_before["count"] == 1
        assert catalogue_after["rows"] == catalogue_rows_before
        assert catalogue_after["rows"][0]["invoice_id"] == invoice["invoice_id"]
