"""Inventory CLI verbs exercise one authenticated profile-worker journey."""

from __future__ import annotations

import json
import os
import sys
from contextlib import suppress
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....domain.contribuyente.inventory.records import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....tests.cli_envelope import unwrap_cli_result
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
    "identity.surnames": "Inventory",
    "activities.description": "synthetic inventory profile",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}

_ACQUISITION = json.dumps(
    {
        "consideration_excluding_iva": "55.00",
        "consideration_iva_amount": "11.55",
        "consideration_deductible_iva_ratio": "1.00",
        "attributable_cost_components": [],
        "evidence": [
            {
                "reference": {"reference": "invoice-secret-ref"},
                "evidence_kind": "purchase_invoice",
                "content_digest": "a" * 64,
            },
            {
                "reference": {"reference": "cost-review-secret-ref"},
                "evidence_kind": "attributable_cost_review",
                "content_digest": "b" * 64,
            },
            {
                "reference": {"reference": "iva-review-secret-ref"},
                "evidence_kind": "iva_recoverability_review",
                "content_digest": "c" * 64,
            },
        ],
        "completeness": {
            "consideration_evidence": {"reference": "invoice-secret-ref"},
            "attributable_cost_review_evidence": {"reference": "cost-review-secret-ref"},
            "iva_recoverability_review_evidence": {"reference": "iva-review-secret-ref"},
        },
        "directly_attributable_cost_total": "0.00",
        "nonrecoverable_iva_included": "0.00",
        "recoverable_iva_excluded": "11.55",
        "total_acquisition_cost": "55.00",
    }
)


def _invoke(
    profile: NativeCliProfileFixture,
    *command: str,
    input_text: str | None = None,
) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    arguments = ["--language", "en", "--format", "json", "--profile", profile.label]
    profile_secret = json.dumps({"profile_passphrase": profile.passphrase}).encode("utf-8")
    if input_text is None:
        arguments.append("--profile-secrets-stdin")
        cli_input = profile_secret.decode("utf-8")
        result = invoke_cached_cli((*arguments, *command), input=cli_input)
    else:
        profile_secrets_read_fd, profile_secrets_write_fd = os.pipe()
        try:
            os.write(profile_secrets_write_fd, profile_secret)
            os.close(profile_secrets_write_fd)
            arguments.extend(("--profile-secrets-fd", str(profile_secrets_read_fd)))
            result = invoke_cached_cli((*arguments, *command), input=input_text)
        finally:
            for descriptor in (profile_secrets_write_fd, profile_secrets_read_fd):
                with suppress(OSError):
                    os.close(descriptor)
    assert profile.passphrase not in result.output
    return result


def _create_ledger(
    profile: NativeCliProfileFixture,
    actividad_id: str,
    *,
    opening_stock: str = "0",
) -> Result:
    return _invoke(
        profile,
        "app",
        "ledger",
        "inventory",
        "create",
        actividad_id,
        "--year",
        "2026",
        "--valuation-method",
        "fifo",
        "--opening-stock",
        opening_stock,
    )


def _authority_payload(actividad_id: str, *, reason: str = "Reviewed movement-derived closing.") -> str:
    from ....domain.contribuyente.inventory.closing_authority_records import (
        InventoryClosingAuthorityDecision,
        InventoryClosingAuthorityRecord,
        PriorAuthoritativeClosingLink,
    )

    continuity_evidence = (
        PriorClosingContinuityEvidence(
            reference=FilingEvidenceReference(reference=f"{actividad_id}-prior-secret-ref"),
            content_digest="f" * 64,
        ),
    )
    record = InventoryClosingAuthorityRecord(
        decision=InventoryClosingAuthorityDecision(
            decision_id=f"decision-{actividad_id}-2026",
            actividad_id=actividad_id,
            filing_year=2026,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            reason=reason,
            actor="secret-operator",
            source_command="inventory.closing.authority.decide",
            decided_at=datetime(2027, 1, 2, tzinfo=UTC),
            evidence=(
                InventoryClosingDecisionEvidence(
                    reference=FilingEvidenceReference(reference=f"{actividad_id}-decision-secret-ref"),
                    role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                    content_digest="e" * 64,
                ),
            ),
        ),
        prior_closing_link=PriorAuthoritativeClosingLink(
            actividad_id=actividad_id,
            current_filing_year=2026,
            prior_filing_year=2025,
            prior_authoritative_closing_value=Decimal("100.00"),
            current_opening_value=Decimal("100.00"),
            prior_authoritative_source_fingerprint="c" * 64,
            prior_authoritative_closing_fingerprint=fingerprint_prior_authoritative_closing(
                actividad_id=actividad_id,
                filing_year=2025,
                authoritative_closing_value=Decimal("100.00"),
                authoritative_source_fingerprint="c" * 64,
                evidence=continuity_evidence,
            ),
            evidence=continuity_evidence,
        ),
    )
    return record.model_dump_json()


def _physical_authority_payload(actividad_id: str) -> str:
    from ....domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord

    base = InventoryClosingAuthorityRecord.model_validate_json(_authority_payload(actividad_id))
    observation = PhysicalClosingObservation(
        observation_id=f"physical-{actividad_id}-2026",
        observed_on=date(2027, 1, 1),
        as_of_date=date(2026, 12, 31),
        actividad_id=actividad_id,
        filing_year=2026,
        closing_value=Decimal("101.00"),
        valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
        evidence=(
            PhysicalClosingEvidence(
                reference=FilingEvidenceReference(reference=f"{actividad_id}-physical-secret-count"),
                role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                content_digest="a" * 64,
            ),
            PhysicalClosingEvidence(
                reference=FilingEvidenceReference(reference=f"{actividad_id}-physical-secret-value"),
                role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
                content_digest="b" * 64,
            ),
        ),
    )
    return InventoryClosingAuthorityRecord(
        decision=base.decision.model_copy(
            update={
                "authority": InventoryClosingAuthority.PHYSICAL_OBSERVATION,
                "physical_observation_id": observation.observation_id,
                "physical_observation_fingerprint": observation.fingerprint,
            },
        ),
        physical_observation=observation,
        prior_closing_link=base.prior_closing_link,
    ).model_dump_json()


def test_native_inventory_create_list_movement_and_preview_use_profile_worker(
    tmp_path: Path,
) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-inventory", facts=_PROFILE_FACTS)

        created = _create_ledger(profile, "act-1", opening_stock="100.00")
        assert created.exit_code == 0, (created.output, failures)
        create_payload = unwrap_cli_result(created)
        assert create_payload["actividad_id"] == "act-1"
        assert create_payload["valuation_method"] == "fifo"
        assert create_payload["opening_stock"] == "100.00"
        assert len(create_payload["bucket_event_ids"]) == 1

        purchase = _invoke(
            profile,
            "app",
            "ledger",
            "inventory",
            "movement",
            "add",
            "--actividad-id",
            "act-1",
            "--year",
            "2026",
            "--movement-id",
            "purchase-1",
            "--date",
            "2026-03-15",
            "--kind",
            "purchase",
            "--quantity",
            "10",
            "--acquisition-cost-stdin",
            input_text=_ACQUISITION,
        )
        assert purchase.exit_code == 0, purchase.output
        assert "secret-ref" not in purchase.output
        assert "a" * 64 not in purchase.output
        acquisition_summary = unwrap_cli_result(purchase)["period_movements"][0]["acquisition_cost"]
        assert acquisition_summary == {
            "consideration_excluding_iva": "55.00",
            "directly_attributable_cost_total": "0.00",
            "nonrecoverable_iva_included": "0.00",
            "recoverable_iva_excluded": "11.55",
            "total_acquisition_cost": "55.00",
            "component_count": 0,
            "evidence_count": 3,
            "complete": True,
        }

        duplicate = _create_ledger(profile, "act-1", opening_stock="999.00")
        assert duplicate.exit_code != 0
        duplicate_error = json.loads(duplicate.output)["error"]
        assert duplicate_error["code"] == "REFUSED_CLI_BOUNDARY"
        assert duplicate_error["context"]["reason"] == "activity_conflict"
        assert duplicate_error["context"]["refusal_code"] == "REFUSED_INVENTORY_ACTIVIDAD_CONFLICT"

        listed = _invoke(profile, "app", "ledger", "inventory", "list")
        assert listed.exit_code == 0, listed.output
        listed_payload = unwrap_cli_result(listed)
        assert listed_payload["count"] == 1
        assert listed_payload["rows"][0]["actividad_id"] == "act-1"
        assert listed_payload["rows"][0]["year"] == 2026
        assert listed_payload["rows"][0]["valuation_method"] == "fifo"
        assert listed_payload["rows"][0]["opening_stock"] == "100.00"
        assert listed_payload["rows"][0]["movement_count"] == 1

        legacy_purchase = _invoke(
            profile,
            "app",
            "ledger",
            "inventory",
            "movement",
            "add",
            "--actividad-id",
            "act-1",
            "--year",
            "2026",
            "--movement-id",
            "legacy-1",
            "--date",
            "2026-03-15",
            "--kind",
            "purchase",
            "--quantity",
            "1",
            "--unit-cost",
            "5.50",
        )
        assert legacy_purchase.exit_code != 0
        legacy_error = json.loads(legacy_purchase.output)["error"]
        assert legacy_error["code"] == "REFUSED_CLI_BOUNDARY"
        assert legacy_error["context"]["reason"] == "inventory_validation"
        assert legacy_error["context"]["refusal_code"] == "REFUSED_PROFILE_INVENTORY_VALIDATION"
        assert legacy_error["context"]["movement_id"] == "legacy-1"
        assert "5.50" not in legacy_purchase.output

        preview = _invoke(
            profile,
            "app",
            "ledger",
            "inventory",
            "valuation",
            "preview",
            "--actividad-id",
            "act-1",
            "--year",
            "2026",
        )
        assert preview.exit_code == 0, preview.output
        preview_payload = unwrap_cli_result(preview)
        assert preview_payload["derived_closing_value"] == "155.00"
        assert preview_payload["cogs"] == "0.00"
        assert len(preview_payload["bucket_event_ids"]) == 1


def test_native_inventory_closing_authority_replay_and_divergence(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-inventory-closing", facts=_PROFILE_FACTS)

        created = _create_ledger(profile, "authority", opening_stock="100.00")
        assert created.exit_code == 0, created.output
        authority_file = tmp_path / "authority.json"
        authority_file.write_text(_authority_payload("authority"), encoding="utf-8")
        authority_command = (
            "app",
            "ledger",
            "inventory",
            "closing-authority-record",
            "authority",
            "--year",
            "2026",
            "--file",
            str(authority_file),
        )
        first = _invoke(profile, *authority_command)
        replay = _invoke(profile, *authority_command)
        assert first.exit_code == replay.exit_code == 0, (first.output, replay.output)
        for canary in ("prior-secret-ref", "decision-secret-ref", "secret-operator", "e" * 64, "f" * 64):
            assert canary not in first.output
            assert canary not in replay.output
        first_authority = unwrap_cli_result(first)
        repeated_authority = unwrap_cli_result(replay)
        assert first_authority["authority_record_fingerprint"] == repeated_authority["authority_record_fingerprint"]
        assert set(first_authority) == {
            "actividad_id",
            "year",
            "authority_record_fingerprint",
            "decision_fingerprint",
            "physical_observation_fingerprint",
            "prior_closing_link_fingerprint",
        }

        authority_file.write_text(_authority_payload("authority", reason="A different decision."), encoding="utf-8")
        divergent = _invoke(profile, *authority_command)
        assert divergent.exit_code != 0
        divergent_error = json.loads(divergent.output)["error"]
        assert divergent_error["code"] == "REFUSED_CLI_BOUNDARY"
        assert divergent_error["context"]["reason"] == "closing_authority_conflict"
        assert divergent_error["context"]["refusal_code"] == "REFUSED_INVENTORY_SERVICE_INPUT"
        assert "A different decision" not in divergent.output

        physical_created = _create_ledger(profile, "authority-physical", opening_stock="100.00")
        assert physical_created.exit_code == 0, physical_created.output
        physical_file = tmp_path / "physical-authority.json"
        physical_file.write_text(_physical_authority_payload("authority-physical"), encoding="utf-8")
        physical_result = _invoke(
            profile,
            "app",
            "ledger",
            "inventory",
            "closing-authority-record",
            "authority-physical",
            "--year",
            "2026",
            "--file",
            str(physical_file),
        )
        assert physical_result.exit_code == 0, physical_result.output
        physical_payload = unwrap_cli_result(physical_result)
        assert physical_payload["physical_observation_fingerprint"] is not None
        assert "physical-secret" not in physical_result.output
        assert "a" * 64 not in physical_result.output
        assert "b" * 64 not in physical_result.output

        after_authority = _invoke(
            profile,
            "app",
            "ledger",
            "inventory",
            "movement",
            "add",
            "--actividad-id",
            "authority",
            "--year",
            "2026",
            "--movement-id",
            "post-authority",
            "--date",
            "2026-03-15",
            "--kind",
            "cogs",
            "--quantity",
            "1",
        )
        assert after_authority.exit_code == 0, after_authority.output
        post_authority_payload = unwrap_cli_result(after_authority)
        assert (
            post_authority_payload["closing_authority_fingerprints"]["record"]
            == first_authority["authority_record_fingerprint"]
        )
        for canary in ("prior-secret-ref", "decision-secret-ref", "secret-operator", "e" * 64, "f" * 64):
            assert canary not in after_authority.output
