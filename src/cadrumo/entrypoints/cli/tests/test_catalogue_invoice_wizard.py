"""Portable command grammar and result-schema contracts for invoice wizard."""

from __future__ import annotations

import pytest

from ....entrypoints.cli._ledger_catalogue_invoice_payloads import CatalogueInvoiceWizardResult
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_wizard_help_keeps_the_complete_noninteractive_field_surface() -> None:
    result = invoke_cached_cli(["app", "ledger", "invoice", "wizard", "--help"])
    assert result.exit_code == 0, result.output
    for option in (
        "--counterparty-nif",
        "--counterparty-name",
        "--invoice-number",
        "--invoice-date",
        "--taxable-base",
        "--iva-rate",
        "--country-code",
        "--operation-date",
        "--retention-rate",
        "--retention-amount",
        "--iva-category",
        "--recargo",
    ):
        assert option in result.output


def test_wizard_without_required_inputs_returns_usage_without_prompting() -> None:
    result = invoke_cached_cli(["app", "ledger", "invoice", "wizard"], input="")
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "--counterparty-nif" in result.output


def test_wizard_output_schema_keeps_noop_and_extended_record_fields() -> None:
    assert {
        "already_existed",
        "invoice_id",
        "counterparty_tax_id",
        "operation_date",
        "retention_rate",
        "retention_amount",
        "recargo_amount",
        "source_sha256",
        "source_row_index",
    }.issubset(CatalogueInvoiceWizardResult.model_fields)
