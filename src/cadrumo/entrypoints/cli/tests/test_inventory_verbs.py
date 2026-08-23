"""CLI surface tests for `aeat app ledger inventory {list, create, movement add, valuation preview}`."""

from __future__ import annotations

import json

import pytest

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
