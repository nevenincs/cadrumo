"""CLI surface tests for the unified ``invoice`` noun-group (--kind issued|received).

Every verb here drives the sole invoice aggregate (the ``Invoice`` records in
the ``InvoiceCatalogue``). ``--kind`` remains the operator's issued/received
discriminator on ``add`` and ``list``; the single-subject verbs address the
content-addressed ``invoice_id`` directly, which is unique across both kinds and
so needs no kind gate.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(cadrumo_invoices_dir=tmp_path / "invoices"),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
        )
        yield


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
