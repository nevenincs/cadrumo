"""Fresh-wheel installed TUI financial child for the INCOME-01 M130 baseline.

The child drives only visible Textual controls.  It writes financial source data
through the normal import and invoice forms, and persists only value-free
receipt evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from .installed_tui_child import (
    InstalledTuiChildError,
    admitted_session_autopilot,
    installed_product_evidence,
    public_surface_diagnostic,
    query_public_selector,
    read_passphrase_from_stdin,
    register_profile_through_installed_tui,
    select_public_data_table_row,
    set_profile_manager_field,
    wait_for_public_selector,
    write_installed_tui_failure_receipt,
)
from .scenario import ExpenseInvoice, IncomeTaxScenario, IssuedInvoice, QuarterlyOracle, build_scenario
from .tui_journey import (
    activate_tui_operation,
    canonical_financial_value_fingerprint,
    installed_lifecycle_contract,
    wait_for_tui_refresh,
)

_SCHEMA_VERSION = "income-01-installed-tui-financial-v1"
_N26_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"
_SYNTHETIC_COUNTERPARTY_NIF = "A58818501"


@dataclass(frozen=True, slots=True)
class ProfileFactEntry:
    """One public Profile Manager edit, addressed by row and visible choice."""

    path: str
    value: str | None = None
    option_index: int | None = None


@dataclass(frozen=True, slots=True)
class FinancialChildReceipt:
    """Sanitized installed-TUI financial-run evidence."""

    schema_version: str
    status: Literal["proven"]
    product_origin: str
    product_init_sha256: str
    year: int
    transaction_imports: int
    invoice_forms: int
    reconciliation_links: int
    calendar_work: tuple[str, ...]
    lifecycle_operations: tuple[str, ...]
    canonical_value_fingerprint: str
    artifact_sha256s: tuple[str, ...]
    fresh_session_readback: str

    def to_dict(self) -> dict[str, object]:
        """Return the value-free receipt representation."""
        return asdict(self)


def required_profile_facts(scenario: IncomeTaxScenario) -> tuple[ProfileFactEntry, ...]:
    """Return the canonical profile paths required by this income scenario."""
    return (
        ProfileFactEntry("identity.tax_id", value=scenario.taxpayer.tax_id),
        ProfileFactEntry("identity.name", value="Income"),
        ProfileFactEntry("identity.surnames", value="Acceptance"),
        ProfileFactEntry("contact.postcode", value="28001"),
        ProfileFactEntry("tax_residence.ccaa", option_index=13),
        ProfileFactEntry("tax_residence.jurisdiction_scope", option_index=0),
        ProfileFactEntry("censo.activity_start_date", value=scenario.taxpayer.activity_start.isoformat()),
        ProfileFactEntry("taxpayer_type.entity_type", option_index=0),
        ProfileFactEntry("taxpayer_type.fiscal_residency", option_index=0),
        ProfileFactEntry("taxpayer_type.irpf_income_categories", value="actividad_economica"),
        ProfileFactEntry("renta_taxpayer.sex", option_index=1),
        ProfileFactEntry("renta_taxpayer.marital_status", option_index=0),
        ProfileFactEntry("renta_taxpayer.birth_date", value=scenario.taxpayer.birth_date.isoformat()),
        ProfileFactEntry("renta_family.situacion_familiar", option_index=3),
        ProfileFactEntry("irpf.estimation_regime", option_index=0),
        ProfileFactEntry("irpf.special_regime", option_index=0),
        ProfileFactEntry("iva.regime", option_index=0),
        ProfileFactEntry("iva.m303_regime_composition", option_index=0),
        ProfileFactEntry("iva.redeme_enrolled", option_index=1),
        ProfileFactEntry("iva.cash_accounting_regime_enrolled", option_index=1),
        ProfileFactEntry("iva.voluntary_sii_enrolled", option_index=1),
        ProfileFactEntry("iva.hydrocarbon_deposit_advance_payment_deduction_entitled", option_index=1),
        ProfileFactEntry("withholding.has_employees", option_index=1),
        ProfileFactEntry("withholding.pays_professionals_with_retencion", option_index=1),
        ProfileFactEntry("withholding.pays_rent_with_retencion", option_index=1),
        ProfileFactEntry("withholding.pays_capital_income_with_retencion", option_index=1),
        ProfileFactEntry("iva.does_intracomunitario", option_index=1),
        ProfileFactEntry("obligations.third_party_transactions_above_347_threshold", option_index=1),
        ProfileFactEntry("obligations.bienes_extranjero_above_threshold", option_index=1),
        ProfileFactEntry("obligations.monedas_virtuales_extranjero_above_threshold", option_index=1),
    )


def _transaction_csv(*, scenario: IncomeTaxScenario, directory: Path) -> Path:
    """Build one transient N26-compatible statement from the independent scenario."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "income-m130-transactions.csv"
    rows = [_N26_HEADER]
    for item in (*scenario.income, *scenario.expenses):
        amount = item.net_receipt if isinstance(item, IssuedInvoice) else -item.bank_payment
        rows.append(
            ",".join(
                (
                    item.transaction_date.isoformat(),
                    item.transaction_id,
                    item.invoice_id,
                    format(amount, "f"),
                    "EUR",
                    item.transaction_id,
                )
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return path


async def _open_destination(pilot: Any, *, query: str, expected_selector: str) -> None:
    """Open a workbench destination with the normal command-palette keyboard path."""
    from textual.widgets import Input, OptionList

    await pilot.press("ctrl+p")
    await pilot.pause()
    pilot.app.screen.query_one(Input).value = query
    for _ in range(180):
        results = pilot.app.screen.query_one(OptionList)
        if results.option_count > 0:
            results.highlighted = 0
            break
        await pilot.pause()
    else:
        raise InstalledTuiChildError(f"command palette returned no visible result for {query}")
    await pilot.press("enter")
    await wait_for_public_selector(pilot, expected_selector, polls=180)


async def _activate_button(pilot: Any, selector: str) -> None:
    """Activate a visible button by focus so compact terminals remain operable."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    button.focus()
    await pilot.press("enter")


async def _wait_for_refreshed_home(pilot: Any, *, polls: int = 360) -> None:
    """Wait until child dismissal has rebuilt the public workbench generation."""
    from textual.css.query import NoMatches
    from textual.widgets import Static

    for _ in range(polls):
        updating = query_public_selector(pilot, "#root-updating", Static)
        try:
            pilot.app.screen.query_one("#home-agenda")
        except NoMatches:
            pass
        else:
            if not updating.display:
                return
        await pilot.pause()
    raise InstalledTuiChildError(
        "installed TUI did not complete its public Home refresh",
        diagnostic=public_surface_diagnostic(pilot),
    )


async def _configure_profile(pilot: Any, *, scenario: IncomeTaxScenario) -> None:
    """Set the required income facts through Profile Manager row-key edits."""
    from textual.widgets import Input

    await pilot.press("f4")
    await wait_for_public_selector(pilot, "#manager-status", polls=180)
    await _activate_button(pilot, "#manager-add-row-activities")
    await wait_for_public_selector(pilot, "#row-input-0")
    query_public_selector(pilot, "#row-input-0", Input).value = "income-tax acceptance activity"
    await _activate_button(pilot, "#btn-row-save")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#manager-status", polls=180)
    for fact in required_profile_facts(scenario):
        await set_profile_manager_field(
            pilot=pilot,
            path=fact.path,
            value=fact.value,
            option_index=fact.option_index,
        )
    await pilot.press("f8")
    await pilot.app.workers.wait_for_complete()
    await pilot.press("escape")
    await _wait_for_refreshed_home(pilot)


async def _import_transactions(pilot: Any, *, csv_path: Path) -> None:
    """Use the visible bank-statement import preview and confirmation flow."""
    from textual.widgets import Input, Select

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="import")
    await wait_for_public_selector(pilot, "#ledger-import-path")
    query_public_selector(pilot, "#ledger-import-kind", Select).value = "bank_statement"
    query_public_selector(pilot, "#ledger-import-provider", Select).value = "csv"
    query_public_selector(pilot, "#ledger-import-path", Input).value = str(csv_path)
    await _activate_button(pilot, "#ledger-import-preview-button")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-confirm")
    from textual.widgets import Button, Static

    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    confirm = query_public_selector(pilot, "#ledger-import-confirm", Button)
    if refusal or confirm.disabled:
        raise InstalledTuiChildError("installed transaction import preview did not reach confirmation")
    await _activate_button(pilot, "#ledger-import-confirm")
    await pilot.app.workers.wait_for_complete()
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    if refusal:
        raise InstalledTuiChildError("installed transaction import reported a visible persistence refusal")
    await _activate_button(pilot, "#ledger-import-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-preview-button")


async def _open_invoice_form(pilot: Any) -> None:
    """Open the normal invoice entry form from Ledger overview."""
    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="overview")
    await wait_for_public_selector(pilot, "#ledger-add-invoice")
    await _activate_button(pilot, "#ledger-add-invoice")
    await wait_for_public_selector(pilot, "#ledger-invoice-review")


async def _capture_invoice(pilot: Any, *, item: IssuedInvoice | ExpenseInvoice) -> None:
    """Persist one invoice through its visible review/confirmation form."""
    from textual.widgets import Input, Select

    await _open_invoice_form(pilot)
    issued = isinstance(item, IssuedInvoice)
    query_public_selector(pilot, "#ledger-invoice-kind", Select).value = "issued" if issued else "received"
    query_public_selector(pilot, "#ledger-invoice-class", Select).value = "ordinaria"
    values = {
        "#ledger-invoice-counterparty-name": item.transaction_id,
        "#ledger-invoice-counterparty-nif": _SYNTHETIC_COUNTERPARTY_NIF,
        "#ledger-invoice-invoice-number": item.invoice_id,
        "#ledger-invoice-invoice-date": item.invoice_date.isoformat(),
        "#ledger-invoice-taxable-base": format(item.taxable_base, "f"),
        "#ledger-invoice-iva-rate": format(item.iva_rate * 100, "f"),
        "#ledger-invoice-currency": "EUR",
        "#ledger-invoice-retention-rate": format(item.withholding_rate, "f") if issued else "",
        "#ledger-invoice-retention-amount": format(item.withholding, "f") if issued else "",
    }
    for selector, value in values.items():
        query_public_selector(pilot, selector, Input).value = value
    await _activate_button(pilot, "#ledger-invoice-review")
    await wait_for_public_selector(pilot, "#ledger-invoice-confirm")
    await _activate_button(pilot, "#ledger-invoice-confirm")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-again")
    from textual.widgets import Static

    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    if refusal:
        raise InstalledTuiChildError("installed invoice form reported a visible persistence refusal")
    await _activate_button(pilot, "#ledger-invoice-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-review")


async def _reconcile_invoice(pilot: Any, *, transaction_id: str, invoice_id: str) -> None:
    """Create one persisted link from the visible row naming the synthetic counterparty."""
    from textual.widgets import DataTable

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="reconciliation")
    await wait_for_public_selector(pilot, "#ledger-suggestions")
    table = query_public_selector(pilot, "#ledger-suggestions", DataTable)
    matching = [
        row_key
        for row_key in table.rows
        if transaction_id in " ".join(str(cell) for cell in table.get_row(row_key))
    ]
    if len(matching) != 1:
        raise InstalledTuiChildError(
            "installed reconciliation did not expose exactly one visible match "
            f"for {invoice_id} (visible rows: {table.row_count}, matches: {len(matching)})"
        )
    table.focus()
    table.move_cursor(row=table.get_row_index(matching[0]))
    await pilot.press("enter")
    await wait_for_public_selector(pilot, "#ledger-reconciliation-confirm")
    await _activate_button(pilot, "#ledger-reconciliation-confirm")
    await pilot.app.workers.wait_for_complete()


async def _create_calendar_work(pilot: Any, *, modelo: str, year: int, period: str) -> None:
    """Create one filing-period work unit through Calendar confirmation."""
    from textual.widgets import Static

    await _open_destination(pilot, query="declarations", expected_selector="#declarations-navigation")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#declarations-navigation",
        row_key="declarations.calendar",
    )
    await wait_for_public_selector(pilot, "#declarations-calendar-agenda")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#declarations-calendar-agenda",
        row_key=f"{modelo}|{year}|{period}",
    )
    await wait_for_public_selector(pilot, "#btn-confirm-accept")
    await _activate_button(pilot, "#btn-confirm-accept")
    await pilot.app.workers.wait_for_complete()
    notice = str(query_public_selector(pilot, "#declarations-calendar-notice", Static).render()).strip()
    if notice.startswith("Created ") is False:
        if "setup complete" in notice:
            outcome = "setup-incomplete"
        elif "could not be completed" in notice:
            outcome = "recovery-failed"
        else:
            outcome = "unexpected-notice"
        raise InstalledTuiChildError(f"calendar creation did not report success ({outcome})")
    await pilot.press("escape")
    await _wait_for_refreshed_home(pilot)


async def _open_work(pilot: Any, *, work_unit_id: str) -> None:
    """Open the created work using its public work-unit row key."""
    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    await select_public_data_table_row(pilot=pilot, table_selector="#declarations-list", row_key=work_unit_id)
    await wait_for_public_selector(pilot, "#modelo-lifecycle-calculate")


def _m130_expected(oracle: QuarterlyOracle) -> dict[str, str]:
    """Return independently computed M130 casillas in rendered money form."""
    return {
        "01": f"{oracle.cumulative_income:.2f}",
        "02": f"{oracle.cumulative_expenses:.2f}",
        "03": f"{oracle.cumulative_net:.2f}",
        "04": f"{oracle.twenty_percent:.2f}",
        "05": f"{oracle.prior_positive_results:.2f}",
        "06": f"{oracle.cumulative_withholding:.2f}",
        "07": f"{oracle.partial_result:.2f}",
        "13": f"{oracle.low_income_reduction:.2f}",
        "19": f"{oracle.payment:.2f}",
    }


async def _read_calculated_values(
    pilot: Any,
    *,
    work_unit_id: str,
    expected: dict[str, str],
) -> dict[str, str]:
    """Read computed values from the installed Results destination and check the oracle."""
    from decimal import Decimal

    from textual.widgets import DataTable

    await _open_work(pilot, work_unit_id=work_unit_id)
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#workspace-overview-destinations",
        row_key="modelo.workspace.results",
    )
    await wait_for_public_selector(pilot, "#workspace-results-table", polls=360)
    table = query_public_selector(pilot, "#workspace-results-table", DataTable)
    actual: dict[str, str] = {}
    for casilla in expected:
        row_key = next((candidate for candidate in table.rows if str(candidate.value) == casilla), None)
        if row_key is None:
            raise InstalledTuiChildError(f"installed Results did not expose expected casilla {casilla}")
        row = table.get_row(row_key)
        if len(row) < 2:
            raise InstalledTuiChildError(f"installed Results row {casilla} did not expose a value column")
        actual[casilla] = f"{Decimal(str(row[1])):.2f}"
    if actual != expected:
        raise InstalledTuiChildError("installed Results did not match the independent M130 oracle")
    await pilot.press("escape")
    await pilot.press("escape")
    return actual


async def _run_lifecycle(
    pilot: Any,
    *,
    export_path: Path,
    work_unit_id: str,
    expected: dict[str, str],
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Run calculate, inspect, verify, local filing and export through the TUI."""
    contract = installed_lifecycle_contract(
        profile_selection_id="#manager-status",
        ledger_capture_id="#ledger-import-confirm",
        invoice_link_id="#ledger-reconciliation-confirm",
        work_create_id="#declarations-calendar-agenda",
    )
    completed: list[str] = []
    await _open_work(pilot, work_unit_id=work_unit_id)
    terminal = await activate_tui_operation(pilot, binding=contract.calculate)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("modelo.work.calculate did not reach a succeeded terminal")
    await wait_for_tui_refresh(pilot, binding=contract.calculate)
    completed.append(contract.calculate.operation_id)
    observed = await _read_calculated_values(pilot, work_unit_id=work_unit_id, expected=expected)
    for binding in (contract.verify, contract.local_file):
        await _open_work(pilot, work_unit_id=work_unit_id)
        terminal = await activate_tui_operation(pilot, binding=binding)
        if terminal.outcome.value != "proven":
            raise InstalledTuiChildError(f"{binding.operation_id} did not reach a succeeded terminal")
        await wait_for_tui_refresh(pilot, binding=binding)
        completed.append(binding.operation_id)
    await _open_work(pilot, work_unit_id=work_unit_id)
    from textual.widgets import Input

    query_public_selector(pilot, "#modelo-lifecycle-export-path", Input).value = str(export_path)
    terminal = await activate_tui_operation(pilot, binding=contract.export)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("modelo.export did not reach a succeeded terminal")
    completed.append(contract.export.operation_id)
    return tuple(completed), observed


async def _work_ids_by_period(pilot: Any, *, year: int) -> dict[str, str]:
    """Resolve opaque work ids from the visible natural-address rows."""
    from textual.widgets import DataTable

    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    table = query_public_selector(pilot, "#declarations-list", DataTable)
    found: dict[str, str] = {}
    for row_key in table.rows:
        rendered = " ".join(str(cell) for cell in table.get_row(row_key))
        for period in ("1T", "2T", "3T", "4T", "0A"):
            modelo = "100" if period == "0A" else "130"
            if modelo in rendered and str(year) in rendered and period in rendered:
                found[period] = str(row_key.value)
    return found


def run_financial_child(
    *,
    workspace_root: Path,
    profile_label: str,
    passphrase: str,
    year: int,
    scratch: Path,
) -> FinancialChildReceipt:
    """Run visible setup, capture, lifecycle actions, then a fresh-session readback."""
    scenario = build_scenario(year)
    product = installed_product_evidence(workspace_root=workspace_root)
    csv_path = _transaction_csv(scenario=scenario, directory=scratch)
    work_unit_ids: dict[str, str] = {}
    operations: list[str] = []
    financial_values: dict[str, str] = {}
    artifact_hashes: list[str] = []

    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition
    from cadrumo.entrypoints.tui.launcher import main

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))

    async def drive(pilot: Any) -> None:
        await _configure_profile(pilot, scenario=scenario)
        for period in ("1T", "2T", "3T", "4T"):
            await _create_calendar_work(pilot, modelo="130", year=year, period=period)
        await _import_transactions(pilot, csv_path=csv_path)
        for item in (*scenario.income, *scenario.expenses):
            await _capture_invoice(pilot, item=item)
        for item in (*scenario.income, *scenario.expenses):
            await _reconcile_invoice(pilot, transaction_id=item.transaction_id, invoice_id=item.invoice_id)
        work_unit_ids.update(await _work_ids_by_period(pilot, year=year))
        if set(work_unit_ids) != {"1T", "2T", "3T", "4T"}:
            raise InstalledTuiChildError("calendar creation did not expose all four quarterly declaration rows")
        for oracle in scenario.quarter_oracle:
            export_path = scratch / f"modelo-130-{year}-{oracle.period}.boe"
            completed, observed = await _run_lifecycle(
                pilot,
                export_path=export_path,
                work_unit_id=work_unit_ids[oracle.period],
                expected=_m130_expected(oracle),
            )
            operations.extend(completed)
            financial_values.update({f"130.{oracle.period}.{key}": value for key, value in observed.items()})
            artifact_hashes.append(hashlib.sha256(export_path.read_bytes()).hexdigest())
        pilot.app.exit()

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=drive),
    )
    if exit_code != 0:
        raise InstalledTuiChildError(f"installed financial launcher returned {exit_code}")
    if set(work_unit_ids) != {"1T", "2T", "3T", "4T"}:
        raise InstalledTuiChildError("installed financial run did not retain all quarterly work identities")

    observed: list[str] = []

    async def readback(pilot: Any) -> None:
        await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
        await select_public_data_table_row(
            pilot=pilot,
            table_selector="#declarations-list",
            row_key=work_unit_ids["4T"],
        )
        await wait_for_public_selector(pilot, "#modelo-lifecycle-export")
        observed.append("modelo-workspace-reopened")
        pilot.app.exit()

    readback_exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=readback),
    )
    if readback_exit_code != 0 or observed != ["modelo-workspace-reopened"]:
        raise InstalledTuiChildError("fresh installed session did not reopen the persisted M130 work")
    return FinancialChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        year=year,
        transaction_imports=1,
        invoice_forms=len(scenario.income) + len(scenario.expenses),
        reconciliation_links=len(scenario.income) + len(scenario.expenses),
        calendar_work=("m130-1t", "m130-2t", "m130-3t", "m130-4t"),
        lifecycle_operations=tuple(operations),
        canonical_value_fingerprint=canonical_financial_value_fingerprint(values=financial_values),
        artifact_sha256s=tuple(artifact_hashes),
        fresh_session_readback=hashlib.sha256("|".join(observed).encode("utf-8")).hexdigest(),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the installed INCOME-01 TUI financial child.")
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--profile-label", default="income-tui-financial")
    parser.add_argument("--year", type=int, default=date.today().year - 1)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the child and write only its sanitized receipt."""
    args = _parser().parse_args(argv)
    try:
        receipt = run_financial_child(
            workspace_root=args.workspace_root,
            profile_label=args.profile_label,
            passphrase=read_passphrase_from_stdin(),
            year=args.year,
            scratch=args.scratch,
        )
    except InstalledTuiChildError as error:
        write_installed_tui_failure_receipt(path=args.receipt, schema_version=_SCHEMA_VERSION, error=error)
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

