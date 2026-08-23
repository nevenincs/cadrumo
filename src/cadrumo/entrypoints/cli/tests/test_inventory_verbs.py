"""CLI surface tests for `aeat app ledger inventory {list, create, movement add, valuation preview}`."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....domain.contribuyente.inventory import (
    InventoryClosingAuthority,
    InventoryClosingAuthorityDecision,
    InventoryClosingAuthorityRecord,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorAuthoritativeClosingLink,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....tests.cli_runner import invoke_cached_cli
from ._strict_cli_fixture_support import inventory_isolated_backend

__all__ = ["inventory_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ACQUISITION = json.dumps(
    {
        "consideration_excluding_iva": "55.00",
        "consideration_iva_amount": "11.55",
        "consideration_deductible_iva_ratio": "1.00",
        "attributable_cost_components": [],
        "evidence": [
            {"reference": {"reference": "invoice-secret-ref"}, "evidence_kind": "purchase_invoice", "content_digest": "a" * 64},
            {"reference": {"reference": "cost-review-secret-ref"}, "evidence_kind": "attributable_cost_review", "content_digest": "b" * 64},
            {"reference": {"reference": "iva-review-secret-ref"}, "evidence_kind": "iva_recoverability_review", "content_digest": "c" * 64},
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


def _authority_payload(*, reason: str = "Reviewed movement-derived closing.") -> str:
    continuity_evidence = (
        PriorClosingContinuityEvidence(
            reference=FilingEvidenceReference(reference="prior-secret-ref"),
            content_digest="f" * 64,
        ),
    )
    record = InventoryClosingAuthorityRecord(
        decision=InventoryClosingAuthorityDecision(
            decision_id="decision-2026",
            actividad_id="authority",
            filing_year=2026,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            reason=reason,
            actor="secret-operator",
            source_command="inventory.closing.authority.decide",
            decided_at=datetime(2027, 1, 2, tzinfo=UTC),
            evidence=(
                InventoryClosingDecisionEvidence(
                    reference=FilingEvidenceReference(reference="decision-secret-ref"),
                    role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                    content_digest="e" * 64,
                ),
            ),
        ),
        prior_closing_link=PriorAuthoritativeClosingLink(
            actividad_id="authority",
            current_filing_year=2026,
            prior_filing_year=2025,
            prior_authoritative_closing_value=Decimal("100.00"),
            current_opening_value=Decimal("100.00"),
            prior_authoritative_source_fingerprint="c" * 64,
            prior_authoritative_closing_fingerprint=fingerprint_prior_authoritative_closing(
                actividad_id="authority",
                filing_year=2025,
                authoritative_closing_value=Decimal("100.00"),
                authoritative_source_fingerprint="c" * 64,
                evidence=continuity_evidence,
            ),
            evidence=continuity_evidence,
        ),
    )
    return record.model_dump_json()


def _physical_authority_payload() -> str:
    base = InventoryClosingAuthorityRecord.model_validate_json(_authority_payload())
    observation = PhysicalClosingObservation(
        observation_id="physical-2026",
        observed_on=date(2027, 1, 1),
        as_of_date=date(2026, 12, 31),
        actividad_id="authority",
        filing_year=2026,
        closing_value=Decimal("101.00"),
        valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
        evidence=(
            PhysicalClosingEvidence(
                reference=FilingEvidenceReference(reference="physical-secret-count"),
                role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                content_digest="a" * 64,
            ),
            PhysicalClosingEvidence(
                reference=FilingEvidenceReference(reference="physical-secret-value"),
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


def test_inventory_list_starts_empty() -> None:
    result = invoke_cached_cli(["app", "ledger", "inventory", "list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_inventory_create_persists() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "100.00",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "actividad_id\tact-1" in result.output
    assert "valuation_method\tfifo" in result.output
    assert "opening_stock\t100.00" in result.output

    list_result = invoke_cached_cli(["app", "ledger", "inventory", "list"])
    assert list_result.exit_code == 0, list_result.output
    assert "act-1\t2026\tfifo" in list_result.output


def test_inventory_create_refuses_duplicate() -> None:
    invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "0",
        ],
    )
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "0",
        ],
    )
    assert result.exit_code != 0


def test_inventory_movement_add_records_against_existing_ledger() -> None:
    invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "0",
        ],
    )
    result = invoke_cached_cli(
        [
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
            "mov-1",
            "--date",
            "2026-03-15",
            "--kind",
            "purchase",
            "--quantity",
            "10",
            "--acquisition-cost-stdin",
        ],
        input=_ACQUISITION,
    )
    assert result.exit_code == 0, result.output
    assert "movements\t1" in result.output


def test_inventory_purchase_refuses_legacy_cost_authority() -> None:
    invoke_cached_cli(["app", "ledger", "inventory", "create", "legacy", "--year", "2026", "--valuation-method", "fifo"])
    result = invoke_cached_cli(
        ["app", "ledger", "inventory", "movement", "add", "--actividad-id", "legacy", "--year", "2026", "--movement-id", "legacy-1", "--date", "2026-03-15", "--kind", "purchase", "--quantity", "1", "--unit-cost", "5.50"]
    )
    assert result.exit_code != 0

    ignored_rate = invoke_cached_cli(
        ["app", "ledger", "inventory", "movement", "add", "--actividad-id", "legacy", "--year", "2026", "--movement-id", "legacy-rate", "--date", "2026-03-15", "--kind", "purchase", "--quantity", "1", "--iva-rate", "7", "--acquisition-cost-stdin"],
        input=_ACQUISITION,
    )
    assert ignored_rate.exit_code != 0


def test_inventory_invalid_stdin_does_not_echo_acquisition_payload() -> None:
    invoke_cached_cli(["app", "ledger", "inventory", "create", "invalid", "--year", "2026", "--valuation-method", "fifo"])
    malformed_payload = '{"private-evidence":"must-not-echo"}'
    result = invoke_cached_cli(
        ["app", "ledger", "inventory", "movement", "add", "--actividad-id", "invalid", "--year", "2026", "--movement-id", "invalid-1", "--date", "2026-03-15", "--kind", "purchase", "--quantity", "1", "--acquisition-cost-stdin"],
        input=malformed_payload,
    )
    assert result.exit_code != 0
    assert "must-not-echo" not in result.output


def test_inventory_json_output_withholds_acquisition_evidence_identity() -> None:
    invoke_cached_cli(["app", "ledger", "inventory", "create", "safe", "--year", "2026", "--valuation-method", "fifo"])
    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "inventory", "movement", "add", "--actividad-id", "safe", "--year", "2026", "--movement-id", "safe-1", "--date", "2026-03-15", "--kind", "purchase", "--quantity", "10", "--acquisition-cost-stdin"],
        input=_ACQUISITION,
    )
    assert result.exit_code == 0, result.output
    assert "secret-ref" not in result.output
    assert "a" * 64 not in result.output
    summary = json.loads(result.output)["result"]["period_movements"][0]["acquisition_cost"]
    assert summary == {
        "consideration_excluding_iva": "55.00",
        "directly_attributable_cost_total": "0.00",
        "nonrecoverable_iva_included": "0.00",
        "recoverable_iva_excluded": "11.55",
        "total_acquisition_cost": "55.00",
        "component_count": 0,
        "evidence_count": 3,
        "complete": True,
    }


def _create_authority_ledger() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "authority",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "100.00",
        ],
    )
    assert result.exit_code == 0, result.output


def test_inventory_closing_authority_stdin_persists_replays_and_redacts() -> None:
    _create_authority_ledger()
    arguments = [
        "--format",
        "json",
        "app",
        "ledger",
        "inventory",
        "closing-authority-record",
        "authority",
        "--year",
        "2026",
        "--authority-stdin",
    ]
    first = invoke_cached_cli(arguments, input=_authority_payload())
    replay = invoke_cached_cli(arguments, input=_authority_payload())

    assert first.exit_code == 0, first.output
    assert replay.exit_code == 0, replay.output
    for canary in ("prior-secret-ref", "decision-secret-ref", "secret-operator", "e" * 64, "f" * 64):
        assert canary not in first.output
        assert canary not in replay.output
    payload = json.loads(first.output)["result"]
    assert set(payload) == {
        "actividad_id",
        "year",
        "authority_record_fingerprint",
        "decision_fingerprint",
        "physical_observation_fingerprint",
        "prior_closing_link_fingerprint",
    }

    divergent = invoke_cached_cli(arguments, input=_authority_payload(reason="A different decision."))
    assert divergent.exit_code != 0
    assert "A different decision" not in divergent.output
    movement = invoke_cached_cli(
        [
            "--format",
            "json",
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
            "purchase",
            "--quantity",
            "1",
            "--acquisition-cost-stdin",
        ],
        input=_ACQUISITION,
    )
    assert movement.exit_code == 0, movement.output
    for canary in ("prior-secret-ref", "decision-secret-ref", "secret-operator", "e" * 64, "f" * 64):
        assert canary not in movement.output
    assert json.loads(movement.output)["result"]["closing_authority_fingerprints"]["record"]


def test_inventory_closing_authority_stdin_composes_physical_observation_without_leak() -> None:
    _create_authority_ledger()
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "inventory",
            "closing-authority-record",
            "authority",
            "--year",
            "2026",
            "--authority-stdin",
        ],
        input=_physical_authority_payload(),
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["physical_observation_fingerprint"] is not None
    assert "physical-secret" not in result.output
    assert "a" * 64 not in result.output
    assert "b" * 64 not in result.output


def test_inventory_closing_authority_fd_and_channel_refusals() -> None:
    _create_authority_ledger()
    read_fd, write_fd = os.pipe()
    os.write(write_fd, _authority_payload().encode())
    os.close(write_fd)
    base = [
        "app",
        "ledger",
        "inventory",
        "closing-authority-record",
        "authority",
        "--year",
        "2026",
    ]
    result = invoke_cached_cli([*base, "--authority-fd", str(read_fd)])
    assert result.exit_code == 0, result.output
    with pytest.raises(OSError):
        os.read(read_fd, 1)

    invalid_fd, invalid_write_fd = os.pipe()
    os.write(invalid_write_fd, b"\xffinvalid-utf8-secret-canary")
    os.close(invalid_write_fd)
    invalid_utf8 = invoke_cached_cli([*base, "--authority-fd", str(invalid_fd)])
    assert invalid_utf8.exit_code != 0
    assert "secret-canary" not in invalid_utf8.output

    absent = invoke_cached_cli(base)
    assert absent.exit_code != 0
    conflict = invoke_cached_cli([*base, "--authority-stdin", "--authority-fd", "0"], input=_authority_payload())
    assert conflict.exit_code != 0


def test_inventory_closing_authority_refuses_recursive_duplicate_and_oversize_without_echo() -> None:
    _create_authority_ledger()
    base = [
        "app",
        "ledger",
        "inventory",
        "closing-authority-record",
        "authority",
        "--year",
        "2026",
        "--authority-stdin",
    ]
    duplicate = _authority_payload().replace('"decision_id":"decision-2026"', '"decision_id":"decision-2026","decision_id":"secret-duplicate"')
    refused_duplicate = invoke_cached_cli(base, input=duplicate)
    refused_oversize = invoke_cached_cli(base, input='{"secret-oversize":"' + "x" * 9000 + '"}')
    assert refused_duplicate.exit_code != 0
    assert refused_oversize.exit_code != 0
    assert "secret-duplicate" not in refused_duplicate.output
    assert "secret-oversize" not in refused_oversize.output


@pytest.mark.parametrize(
    "malformed",
    [
        "not-json-secret-canary",
        '["non-object-secret-canary"]',
        '{"unexpected":"extra-secret-canary"}',
        '{"decision":{"decision_id":"missing-secret-canary"}}',
    ],
)
def test_inventory_closing_authority_refuses_malformed_shapes_without_echo(malformed: str) -> None:
    _create_authority_ledger()
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "closing-authority-record",
            "authority",
            "--year",
            "2026",
            "--authority-stdin",
        ],
        input=malformed,
    )
    assert result.exit_code != 0
    assert "secret-canary" not in result.output


def test_inventory_closing_authority_coordinate_refusal_does_not_log_values(caplog: pytest.LogCaptureFixture) -> None:
    _create_authority_ledger()
    mismatched = _authority_payload().replace('"actividad_id":"authority"', '"actividad_id":"other-secret"')
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "closing-authority-record",
            "authority",
            "--year",
            "2026",
            "--authority-stdin",
        ],
        input=mismatched,
    )
    assert result.exit_code != 0
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    for canary in ("other-secret", "prior-secret-ref", "decision-secret-ref", "secret-operator", "e" * 64):
        assert canary not in result.output
        assert canary not in rendered_logs
