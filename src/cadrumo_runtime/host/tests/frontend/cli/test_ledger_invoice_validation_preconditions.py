"""Contracts for the ledger invoice-validation terminal projection."""

from __future__ import annotations

import json
from datetime import date

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .cli_runner import invoke_cached_cli
from .runtime_profile_backend import runtime_profile_backend_fixture

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_isolated_backend = runtime_profile_backend_fixture()

_EXPECTED_ACTION = {
    "failed_condition_id": "cli.ledger.invoice.valid",
    "evidence": [
        {
            "condition_id": "cli.ledger.invoice.valid",
            "evidence_id": "cli.ledger.invoice.valid.observation",
            "provenance": "runtime_observation",
            "values": {"invoice_valid": False},
        },
    ],
    "action": None,
    "argument_bindings": [],
    "missing_argument_names": [],
    "conditionality": "not_applicable",
    "no_recovery_outcome": "operator_decision",
}


def test_invoice_add_pydantic_invoice_validation_emits_the_canonical_terminal_action() -> None:
    """The real ledger command preserves the nested invoice condition in JSON."""
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--counterparty-name",
            "Contraparte S.L.",
            "--invoice-number",
            "S130-NESTED-001",
            "--invoice-date",
            date(_YEAR, 3, 15).isoformat(),
            "--taxable-base",
            "100.00",
            "--country-code",
            "ES",
            "--retention-rate",
            "0.15",
        ],
    )

    assert result.exit_code != 0, result.output
    envelope = json.loads(result.output)
    assert envelope["error"]["action"] == _EXPECTED_ACTION
