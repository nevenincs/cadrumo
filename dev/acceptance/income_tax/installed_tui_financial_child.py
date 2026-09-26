"""Fresh-wheel installed TUI financial child for the INCOME-01 baseline.

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
from typing import Any, Literal, cast

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
    TuiOperationBinding,
    activate_tui_operation,
    canonical_financial_value_fingerprint,
    installed_lifecycle_contract,
    validate_modelo_100_xsd,
    wait_for_tui_refresh,
)

_SCHEMA_VERSION = "income-01-installed-tui-financial-v2"
_N26_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"
_SYNTHETIC_COUNTERPARTY_NIF = "A58818501"


def _record_stage(scratch: Path, stage: str) -> None:
    """Leave a value-free progress marker inside the isolated temporary run."""
    (scratch / "tui-stage.txt").write_text(stage + "\n", encoding="ascii")


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
    annual_xsd_validation: dict[str, object]
    fresh_session_readback: str

    def to_dict(self) -> dict[str, object]:
        """Return the value-free receipt representation."""
        return cast("dict[str, object]", asdict(self))


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
        ProfileFactEntry("obligations.premio_loteria_gravamen_especial_sin_retencion", option_index=1),
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
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    destination_key = {"ledger": "ledger", "declarations": "declarations"}.get(query)
    if destination_key is None:
        raise InstalledTuiChildError("installed journey requested an unknown workbench destination")
    destination_label = tr(f"tui.search.destination.{destination_key}")

    await pilot.press("ctrl+p")
    for _ in range(180):
        await pilot.pause()
        try:
            search = pilot.app.screen.query_one(Input)
            pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        search.value = query
        break
    else:
        raise InstalledTuiChildError("installed command palette did not expose its search controls")
    for _ in range(180):
        await pilot.pause()
        try:
            results = pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        for index in range(results.option_count):
            option = results.get_option_at_index(index)
            hit = getattr(option, "hit", None)
            if getattr(hit, "text", None) == destination_label:
                results.highlighted = index
                break
        else:
            await pilot.pause()
            continue
        break
    else:
        raise InstalledTuiChildError(f"command palette did not offer the {query} destination command")
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
        try:
            updating = query_public_selector(pilot, "#root-updating", Static)
            pilot.app.screen.query_one("#home-agenda")
        except NoMatches:
            pass
        else:
            if not updating.display:
                return
        await pilot.pause()
    raise InstalledTuiChildError(
        "installed TUI did not complete its public Home refresh",
        diagnostic={
            **public_surface_diagnostic(pilot),
            "worker_states": sorted(
                f"{worker.name}:{worker.state.value}:{type(worker.error).__name__ if worker.error else 'none'}"
                for worker in pilot.app.workers
            ),
        },
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
        try:
            await set_profile_manager_field(
                pilot=pilot,
                path=fact.path,
                value=fact.value,
                option_index=fact.option_index,
            )
        except InstalledTuiChildError as exc:
            raise InstalledTuiChildError(
                f"installed Profile Manager failed to persist {fact.path}: {exc}",
                diagnostic=public_surface_diagnostic(pilot),
            ) from exc
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


async def _transaction_row_ids(
    pilot: Any,
    *,
    scenario: IncomeTaxScenario,
) -> dict[str, str]:
    """Resolve imported rows by the scenario's unique visible transaction dates."""
    from textual.widgets import DataTable

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries")
    table = query_public_selector(pilot, "#ledger-entries", DataTable)
    resolved: dict[str, str] = {}
    for item in (*scenario.income, *scenario.expenses):
        matches = [
            row_key
            for row_key in table.rows
            if item.transaction_date.isoformat() in " ".join(str(cell) for cell in table.get_row(row_key))
        ]
        if len(matches) != 1:
            date_hits = sum(
                item.transaction_date.isoformat() in " ".join(str(cell) for cell in table.get_row(row_key))
                for row_key in table.rows
            )
            raise InstalledTuiChildError(
                "installed Entries did not expose one unambiguous scenario row "
                f"(date_matches={date_hits}, combined={len(matches)})"
            )
        resolved[item.transaction_id] = str(matches[0].value)
    return resolved


async def _classify_transaction(
    pilot: Any,
    *,
    transaction_id: str,
    item: IssuedInvoice | ExpenseInvoice,
) -> None:
    """Classify one visible row and capture the tax facts needed by Renta."""
    from textual.widgets import Input, Static

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries")
    from textual.widgets import DataTable

    table = query_public_selector(pilot, "#ledger-entries", DataTable)
    row_key = next((candidate for candidate in table.rows if str(candidate.value) == transaction_id), None)
    if row_key is None:
        raise InstalledTuiChildError("installed entries lost a transaction before classification")
    table.focus()
    table.move_cursor(row=table.get_row_index(row_key))
    await pilot.press("enter")
    await pilot.pause()
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-navigation",
        row_key="classification",
    )
    await wait_for_public_selector(pilot, "#ledger-classifications")
    values = {
        "#ledger-classification-taxable-base": format(item.taxable_base, "f"),
        "#ledger-classification-iva-rate": format(item.iva_rate, "f"),
        "#ledger-classification-iva-amount": format(item.iva, "f"),
        "#ledger-classification-iva-category": "domestic_general",
        "#ledger-classification-irpf-category": ("actividad_economica" if isinstance(item, IssuedInvoice) else ""),
    }
    for selector, value in values.items():
        query_public_selector(pilot, selector, Input).value = value
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-classifications",
        row_key="BUSINESS",
    )
    await _activate_button(pilot, "#ledger-classification-confirm")
    await pilot.app.workers.wait_for_complete()
    status = str(query_public_selector(pilot, "#ledger-flow-status", Static).render()).strip()
    if not status:
        raise InstalledTuiChildError("installed classification did not expose a terminal status")
    await pilot.press("escape")
    await pilot.app.workers.wait_for_complete()


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
        "#ledger-invoice-iva-category": "domestic_general",
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
    from textual.widgets import DataTable, Static

    from cadrumo.core.i18n.render import tr

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="reconciliation")
    await wait_for_public_selector(pilot, "#ledger-suggestions")
    table = query_public_selector(pilot, "#ledger-suggestions", DataTable)
    matching = [
        row_key for row_key in table.rows if transaction_id in " ".join(str(cell) for cell in table.get_row(row_key))
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
    status = str(query_public_selector(pilot, "#ledger-flow-status", Static).render()).strip()
    if status != tr("tui.ledger.reconciliation.success"):
        raise InstalledTuiChildError("installed reconciliation did not confirm a persisted link")


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


async def _run_lifecycle(
    pilot: Any,
    *,
    export_path: Path,
    work_unit_id: str,
    calculate: bool = True,
) -> tuple[str, ...]:
    """Run calculate, verify, local filing and export through the TUI."""
    contract = installed_lifecycle_contract(
        profile_selection_id="#manager-status",
        ledger_capture_id="#ledger-import-confirm",
        invoice_link_id="#ledger-reconciliation-confirm",
        work_create_id="#declarations-calendar-agenda",
    )
    completed: list[str] = []
    if calculate:
        await _open_work(pilot, work_unit_id=work_unit_id)
        terminal = await activate_tui_operation(pilot, binding=contract.calculate)
        if terminal.outcome.value != "proven":
            raise InstalledTuiChildError("modelo.work.calculate did not reach a succeeded terminal")
        await wait_for_tui_refresh(pilot, binding=contract.calculate)
        completed.append(contract.calculate.operation_id)
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
    return tuple(completed)


def _parse_m130_artifact(*, path: Path, year: int, period: str, expected: dict[str, str]) -> dict[str, str]:
    """Independently parse one TUI export through its installed registry layout."""
    from decimal import Decimal

    from cadrumo.core.export_layout_format import ExportLayoutFormat
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.domain.calculations.registry.export_parse import parse_export_payload

    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot("130", filing_year=year, period=period).revision
        layout = next(item for item in revision.export_layouts if item.format is ExportLayoutFormat.FIXED_WIDTH)
        parsed = parse_export_payload(layout, path.read_bytes())
    by_casilla = {str(item.casilla_id): item.value for item in parsed.casillas}
    actual = {casilla: f"{Decimal(str(by_casilla.get(casilla))):.2f}" for casilla in expected}
    if actual != expected:
        raise InstalledTuiChildError("installed Modelo 130 artifact did not match the independent oracle")
    return actual


async def _apply_annual_edits(pilot: Any, *, work_unit_id: str) -> None:
    """Set explicit annual-only facts through the admitted public edit surface."""
    from textual.css.query import NoMatches
    from textual.widgets import Input

    await _open_work(pilot, work_unit_id=work_unit_id)
    values = {
        "#modelo-edit-scalar-0001": "declarante",
        "#modelo-edit-scalar-0165": "declarante",
        "#modelo-edit-scalar-0166": "A05",
        "#modelo-edit-binding-renta-modelo-100-estimacion-directa-es-normal": "1",
        "#modelo-edit-binding-renta-certificado-trabajo-retenciones": "0",
    }
    for selector, value in values.items():
        try:
            query_public_selector(pilot, selector, Input).value = value
        except NoMatches as error:
            raise InstalledTuiChildError(f"annual edit did not expose public input {selector}") from error
    binding = TuiOperationBinding(
        "modelo.edit.apply",
        activation_id="#modelo-edit-apply",
        terminal_result_id="#operation-modal-status",
        refresh_result_id="#declarations-list",
        refusal_notice_id="#modelo-lifecycle-notice",
    )
    terminal = await activate_tui_operation(pilot, binding=binding)
    if terminal.outcome.value != "proven":
        import re

        from textual.widgets import Static

        log = query_public_selector(pilot, "#operation-modal-log", Static)
        public_codes = sorted(set(re.findall(r"\b(?:modelo|operation|calculation)\.[a-z0-9_.-]+\b", str(log.render()))))
        raise InstalledTuiChildError(
            f"modelo.edit.apply terminal={terminal.terminal_condition}, "
            f"receipt_present={terminal.receipt_present}, diagnostic_present={terminal.diagnostic_present}, "
            f"public_event_codes={public_codes}"
        )
    await wait_for_tui_refresh(pilot, binding=binding)


def _validate_annual_artifact(
    *, xml_path: Path, xsd_path: Path, scenario: IncomeTaxScenario
) -> tuple[dict[str, str], dict[str, object]]:
    """Read financial XML meaning independently, then validate the official structure."""
    from decimal import Decimal

    from lxml import etree

    document = etree.parse(str(xml_path), parser=etree.XMLParser(resolve_entities=False, no_network=True)).getroot()
    expected = {
        "E1INGRESO": scenario.annual_oracle.activity_income,
        "E1NGD": scenario.annual_oracle.deductible_expenses,
        "E1RN": scenario.annual_oracle.activity_net_income,
        "PAGOS": scenario.annual_oracle.m130_payments,
    }
    observed: dict[str, str] = {}
    for tag, amount in expected.items():
        nodes = document.findall(f".//{tag}")
        if len(nodes) != 1 or nodes[0].text is None or Decimal(nodes[0].text) != amount:
            raise InstalledTuiChildError(f"installed Modelo 100 artifact mismatched annual oracle at {tag}")
        observed[tag] = f"{amount:.2f}"
    validation = validate_modelo_100_xsd(xml_path=xml_path, xsd_path=xsd_path)
    if not validation.xsd_valid or validation.error_identities:
        raise InstalledTuiChildError("installed Modelo 100 artifact failed local official-XSD validation")
    return observed, cast("dict[str, object]", asdict(validation))


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
    annual_xsd_validation: dict[str, object] = {}

    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition
    from cadrumo.entrypoints.tui.launcher import main

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))

    async def drive(pilot: Any) -> None:
        _record_stage(scratch, "profile")
        await _configure_profile(pilot, scenario=scenario)
        _record_stage(scratch, "calendar-quarterly")
        for period in ("1T", "2T", "3T", "4T"):
            await _create_calendar_work(pilot, modelo="130", year=year, period=period)
        _record_stage(scratch, "import")
        await _import_transactions(pilot, csv_path=csv_path)
        _record_stage(scratch, "entries")
        transaction_row_ids = await _transaction_row_ids(pilot, scenario=scenario)
        if len(transaction_row_ids) != len(scenario.income) + len(scenario.expenses):
            raise InstalledTuiChildError("installed Entries count did not match the imported scenario")
        for index, item in enumerate((*scenario.income, *scenario.expenses), start=1):
            _record_stage(scratch, f"classify-{index}")
            await _classify_transaction(
                pilot,
                transaction_id=transaction_row_ids[item.transaction_id],
                item=item,
            )
        for index, item in enumerate((*scenario.income, *scenario.expenses), start=1):
            _record_stage(scratch, f"invoice-{index}")
            await _capture_invoice(pilot, item=item)
        for index, item in enumerate((*scenario.income, *scenario.expenses), start=1):
            _record_stage(scratch, f"reconcile-{index}")
            await _reconcile_invoice(pilot, transaction_id=item.transaction_id, invoice_id=item.invoice_id)
        work_unit_ids.update(await _work_ids_by_period(pilot, year=year))
        if set(work_unit_ids) != {"1T", "2T", "3T", "4T"}:
            raise InstalledTuiChildError("calendar creation did not expose all four quarterly declaration rows")
        for oracle in scenario.quarter_oracle:
            _record_stage(scratch, f"quarter-{oracle.period}")
            export_path = scratch / f"modelo-130-{year}-{oracle.period}.boe"
            expected = _m130_expected(oracle)
            completed = await _run_lifecycle(
                pilot,
                export_path=export_path,
                work_unit_id=work_unit_ids[oracle.period],
            )
            operations.extend(completed)
            observed = _parse_m130_artifact(
                path=export_path,
                year=year,
                period=oracle.period,
                expected=expected,
            )
            financial_values.update({f"130.{oracle.period}.{key}": value for key, value in observed.items()})
            artifact_hashes.append(hashlib.sha256(export_path.read_bytes()).hexdigest())
        _record_stage(scratch, "annual-calendar")
        await _create_calendar_work(pilot, modelo="100", year=year, period="0A")
        annual_ids = await _work_ids_by_period(pilot, year=year)
        annual_work_id = annual_ids.get("0A")
        if annual_work_id is None:
            raise InstalledTuiChildError("calendar creation did not expose annual Modelo 100 work")
        work_unit_ids["0A"] = annual_work_id
        _record_stage(scratch, "annual-edit")
        await _apply_annual_edits(pilot, work_unit_id=annual_work_id)
        operations.append("modelo.edit.apply")
        annual_export = scratch / f"modelo-100-{year}-0A.xml"
        _record_stage(scratch, "annual-lifecycle")
        operations.extend(
            await _run_lifecycle(pilot, export_path=annual_export, work_unit_id=annual_work_id, calculate=False)
        )
        schema_candidates = tuple(
            (workspace_root / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files").glob(
                f"*-100-esquema-xsd-ejercicio-{year}-*.xsd"
            )
        )
        if len(schema_candidates) != 1:
            raise InstalledTuiChildError("the selected annual revision has no unambiguous official XSD")
        _record_stage(scratch, "annual-validation")
        annual_values, validation = _validate_annual_artifact(
            xml_path=annual_export, xsd_path=schema_candidates[0], scenario=scenario
        )
        financial_values.update({f"100.0A.{key}": value for key, value in annual_values.items()})
        annual_xsd_validation.update(validation)
        artifact_hashes.append(hashlib.sha256(annual_export.read_bytes()).hexdigest())
        pilot.app.exit()

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=drive),
    )
    if exit_code != 0:
        raise InstalledTuiChildError(f"installed financial launcher returned {exit_code}")
    if set(work_unit_ids) != {"1T", "2T", "3T", "4T", "0A"}:
        raise InstalledTuiChildError("installed financial run did not retain quarterly and annual work identities")

    observed: list[str] = []

    async def readback(pilot: Any) -> None:
        rows = await _transaction_row_ids(pilot, scenario=scenario)
        if len(rows) != 8:
            raise InstalledTuiChildError("fresh installed TUI session lost imported transaction rows")
        await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
        await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="reconciliation")
        from textual.widgets import DataTable

        suggestions = query_public_selector(pilot, "#ledger-suggestions", DataTable)
        inconsistencies = query_public_selector(pilot, "#ledger-inconsistencies", DataTable)
        if suggestions.row_count or inconsistencies.row_count:
            raise InstalledTuiChildError("fresh installed TUI session did not preserve the invoice links")
        reopened = await _work_ids_by_period(pilot, year=year)
        if reopened != work_unit_ids:
            raise InstalledTuiChildError("fresh installed TUI session did not preserve annual and quarterly work")
        await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
        await select_public_data_table_row(
            pilot=pilot,
            table_selector="#declarations-list",
            row_key=work_unit_ids["4T"],
        )
        await wait_for_public_selector(pilot, "#modelo-lifecycle-export")
        await _open_work(pilot, work_unit_id=work_unit_ids["0A"])
        observed.append("financial-work-and-links-reopened")
        pilot.app.exit()

    readback_exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=readback),
    )
    if readback_exit_code != 0 or observed != ["financial-work-and-links-reopened"]:
        raise InstalledTuiChildError("fresh installed session did not reopen the persisted income work")
    return FinancialChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        year=year,
        transaction_imports=1,
        invoice_forms=len(scenario.income) + len(scenario.expenses),
        reconciliation_links=len(scenario.income) + len(scenario.expenses),
        calendar_work=("m130-1t", "m130-2t", "m130-3t", "m130-4t", "m100-0a"),
        lifecycle_operations=tuple(operations),
        canonical_value_fingerprint=canonical_financial_value_fingerprint(values=financial_values),
        artifact_sha256s=tuple(artifact_hashes),
        annual_xsd_validation=annual_xsd_validation,
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
    except Exception as error:
        trace = error.__traceback__
        frames: list[str] = []
        while trace is not None:
            if Path(trace.tb_frame.f_code.co_filename).name in {
                "installed_tui_financial_child.py",
                "installed_tui_child.py",
            }:
                frames.append(trace.tb_frame.f_code.co_name)
            trace = trace.tb_next
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(
                f"unexpected installed TUI failure: {type(error).__name__} at {','.join(frames[-4:])}"
            ),
        )
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
