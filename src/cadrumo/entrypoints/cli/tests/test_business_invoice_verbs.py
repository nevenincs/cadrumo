"""CLI surface tests for the unified ``invoice`` noun-group (--kind issued|received).

Every verb here drives the sole invoice aggregate (the ``Invoice`` records in
the ``InvoiceCatalogue``). ``--kind`` remains the operator's issued/received
discriminator on ``add`` and ``list``; the single-subject verbs address the
content-addressed ``invoice_id`` directly, which is unique across both kinds and
so needs no kind gate.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from ....tests.cli_envelope import require_schema_envelope
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoice_directory_settings(tmp_path: Path) -> dict[str, Path]:
    """Provision the explicit test-only invoice state target before use."""
    invoice_directory = tmp_path / "invoices"
    invoice_directory.mkdir()
    return {"cadrumo_invoices_dir": invoice_directory}


_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="00000000-0000-4000-8000-000000000000",
    settings_overrides=_invoice_directory_settings,
)


def _invoke_invoice(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "ledger", "invoice", *args])


def _add_args(
    *,
    kind: str,
    nif: str,
    number: str,
    base: str,
    iva_rate: str | None = None,
    name: str = "Contraparte S.L.",
) -> list[str]:
    args = [
        "add",
        "--kind",
        kind,
        "--counterparty-nif",
        nif,
        "--counterparty-name",
        name,
        "--invoice-number",
        number,
        "--invoice-date",
        "2026-03-15",
        "--taxable-base",
        base,
        "--country-code",
        "ES",
    ]
    if iva_rate is not None:
        args += ["--iva-rate", iva_rate]
    return args


def _full_id_from_add(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("invoice_id\t"):
            return line.split("\t", 1)[1]
    raise AssertionError(f"no invoice_id in output:\n{output}")


def test_invoice_received_add_and_list_round_trip() -> None:
    add_result = _invoke_invoice(
        _add_args(kind="received", nif="12345678Z", number="INV-001", base="100.00", iva_rate="21.00"),
    )
    assert add_result.exit_code == 0, add_result.output
    assert "kind\treceived" in add_result.output

    list_result = _invoke_invoice(["list", "--kind", "received"])
    assert list_result.exit_code == 0, list_result.output
    assert "count\t1" in list_result.output
    assert "INV-001" in list_result.output


def test_invoice_issued_add_reports_issued_kind() -> None:
    add_result = _invoke_invoice(
        _add_args(kind="issued", nif="87654321X", number="COL-001", base="0"),
    )
    assert add_result.exit_code == 0, add_result.output
    assert "kind\tissued" in add_result.output


def test_invoice_view_by_prefix_received() -> None:
    add_result = _invoke_invoice(
        _add_args(kind="received", nif="12345678Z", number="INV-001", base="0"),
    )
    full_id = _full_id_from_add(add_result.output)
    result = _invoke_invoice(["view", full_id[:8]])
    assert result.exit_code == 0, result.output
    assert "invoice_number\tINV-001" in result.output


def test_invoice_update_changes_fields_received() -> None:
    add_result = _invoke_invoice(
        _add_args(kind="received", nif="12345678Z", number="INV-001", base="0"),
    )
    full_id = _full_id_from_add(add_result.output)
    result = _invoke_invoice(["update", full_id, "--counterparty-name", "Acme S.L."])
    assert result.exit_code == 0, result.output
    assert "counterparty_name\tAcme S.L." in result.output


def test_invoice_remove_requires_yes_received() -> None:
    add_result = _invoke_invoice(
        _add_args(kind="received", nif="12345678Z", number="INV-001", base="0"),
    )
    full_id = _full_id_from_add(add_result.output)
    refused = _invoke_invoice(["remove", full_id])
    assert refused.exit_code != 0
    confirmed = _invoke_invoice(["remove", full_id, "--yes"])
    assert confirmed.exit_code == 0, confirmed.output


def test_invoice_add_refuses_missing_taxable_base() -> None:
    # Prevents the CLI silently defaulting an operator-omitted amount to zero,
    # which would drop the counterparty from a Modelo 347 threshold check
    # (RD 1065/2007 art. 31) without any operator-visible signal. The canonical
    # aggregate derives the grand total from the base, so refusing the base is
    # what closes that silent-zero path.
    result = _invoke_invoice(
        [
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--counterparty-name",
            "Contraparte S.L.",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
            "--country-code",
            "ES",
        ],
    )
    assert result.exit_code != 0
    assert "--taxable-base" in result.output, result.output


def test_invoice_add_accepts_ordered_json_lines_and_reads_back_canonical_document_facts() -> None:
    first_line = json.dumps(
        {
            "description": "first line",
            "quantity": "1",
            "unit_price": "10.00",
            "subtotal": "10.00",
            "iva_rate": "RATE_21",
            "iva_amount": "2.10",
        },
    )
    second_line = json.dumps(
        {
            "description": "second line",
            "quantity": "1",
            "unit_price": "5.00",
            "subtotal": "5.00",
            "iva_rate": "RATE_10",
            "iva_amount": "0.50",
        },
    )

    added = invoke_cached_cli(
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
            "A58818501",
            "--counterparty-name",
            "Papeleria Sol SL",
            "--invoice-number",
            "LINES-001",
            "--invoice-date",
            "2026-03-15",
            "--operation-date",
            "2026-03-14",
            "--country-code",
            "ES",
            "--series",
            "L",
            "--line",
            first_line,
            "--line",
            second_line,
        ],
    )
    assert added.exit_code == 0, added.output
    add_payload = require_schema_envelope(added.output)
    invoice_id = add_payload["invoice_id"]
    assert isinstance(invoice_id, str)
    assert [entry["description"] for entry in add_payload["lines"]] == ["first line", "second line"]
    assert add_payload["base_total"] == "15.00"
    assert add_payload["iva_total"] == "2.60"
    assert add_payload["grand_total"] == "17.60"

    viewed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "view", invoice_id],
    )
    assert viewed.exit_code == 0, viewed.output
    view_payload = require_schema_envelope(viewed.output)
    assert [entry["description"] for entry in view_payload["lines"]] == ["first line", "second line"]
    assert view_payload["series"] == "L"
    assert view_payload["operation_date"] == "2026-03-14"
    assert view_payload["operation_date_role"] == "OPERATION_PERFORMED"
    assert {"invoice_class", "iva_category", "rectifies_invoice_number"}.issubset(view_payload)


@pytest.mark.parametrize(
    "line",
    (
        '{"description":"missing required fields"}',
        '{"description":"unknown field","quantity":"1","unit_price":"1","subtotal":"1","iva_rate":"RATE_21","iva_amount":"0.21","unexpected":true}',
        "[]",
    ),
)
def test_invoice_add_refuses_invalid_structured_line_without_mutation(line: str) -> None:
    refused = invoke_cached_cli(
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
            "A58818501",
            "--counterparty-name",
            "Papeleria Sol SL",
            "--invoice-number",
            "LINES-REFUSED",
            "--invoice-date",
            "2026-03-15",
            "--country-code",
            "ES",
            "--line",
            line,
        ],
    )
    assert refused.exit_code != 0

    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    assert require_schema_envelope(listed.output)["count"] == 0


def test_invoice_add_refuses_mixed_scalar_and_structured_input_before_mutation() -> None:
    line = json.dumps(
        {
            "description": "line",
            "quantity": "1",
            "unit_price": "10.00",
            "subtotal": "10.00",
            "iva_rate": "RATE_21",
            "iva_amount": "2.10",
        },
    )
    refused = invoke_cached_cli(
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
            "A58818501",
            "--counterparty-name",
            "Papeleria Sol SL",
            "--invoice-number",
            "LINES-MIXED",
            "--invoice-date",
            "2026-03-15",
            "--country-code",
            "ES",
            "--taxable-base",
            "10.00",
            "--line",
            line,
        ],
    )
    assert refused.exit_code != 0

    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    assert require_schema_envelope(listed.output)["count"] == 0


def test_invoice_add_derives_grand_total_from_base_and_rate() -> None:
    # The total is derived, never operator-asserted, so it cannot disagree with
    # the base/cuota it is built from.
    result = _invoke_invoice(
        _add_args(kind="received", nif="12345678Z", number="INV-002", base="6000.00", iva_rate="21.00"),
    )
    assert result.exit_code == 0, result.output
    assert "base_total\t6000.00" in result.output
    assert "grand_total\t7260.00" in result.output


def test_invoice_kind_is_required_on_add() -> None:
    result = _invoke_invoice(
        [
            "add",
            "--counterparty-nif",
            "12345678Z",
            "--counterparty-name",
            "Contraparte S.L.",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
            "--taxable-base",
            "0",
            "--country-code",
            "ES",
        ],
    )
    assert result.exit_code != 0


def test_invoice_kind_rejects_unknown_value() -> None:
    result = _invoke_invoice(
        [
            "add",
            "--kind",
            "owed",
            "--counterparty-nif",
            "12345678Z",
            "--counterparty-name",
            "Contraparte S.L.",
            "--invoice-number",
            "INV-001",
            "--invoice-date",
            "2026-03-15",
            "--taxable-base",
            "0",
            "--country-code",
            "ES",
        ],
    )
    assert result.exit_code != 0
    # Typer/click renders the accepted Choice set on parse failure.
    assert "issued" in result.output
    assert "received" in result.output


def test_invoice_list_filters_by_kind() -> None:
    _invoke_invoice(_add_args(kind="received", nif="12345678Z", number="PAY-001", base="0"))
    _invoke_invoice(_add_args(kind="issued", nif="87654321X", number="COL-001", base="0"))
    received_list = _invoke_invoice(["list", "--kind", "received"])
    issued_list = _invoke_invoice(["list", "--kind", "issued"])
    assert "PAY-001" in received_list.output
    assert "COL-001" not in received_list.output
    assert "COL-001" in issued_list.output
    assert "PAY-001" not in issued_list.output


def test_invoice_list_without_kind_returns_both_kinds() -> None:
    # no-silent-under-declaration guard: bare ``invoice list`` must return BOTH
    # kinds so an operator never silently loses half their records.
    _invoke_invoice(_add_args(kind="received", nif="12345678Z", number="PAY-001", base="0"))
    _invoke_invoice(_add_args(kind="issued", nif="87654321X", number="COL-001", base="0"))
    both = _invoke_invoice(["list"])
    assert both.exit_code == 0, both.output
    assert "count\t2" in both.output
    assert "received" in both.output
    assert "issued" in both.output
    assert "PAY-001" in both.output
    assert "COL-001" in both.output
