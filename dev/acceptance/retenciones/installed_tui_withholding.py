"""Installed-TUI withholding evidence journey for RETENCIONES-01.

The driver uses only rendered Textual controls: Ledger creates two synthetic
received invoices, Withholding records professional and urban-rent evidence,
and a new installed process reads both scopes back. It deliberately stops at
that persisted-evidence vertical slice; declaration lifecycle and cross-client
continuations remain separate, unexercised work.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Final, Literal, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admitted_session_autopilot,
    installed_product_evidence,
    query_public_selector,
    read_passphrase_from_stdin,
    register_profile_through_installed_tui,
    run_installed_tui_child_process,
    select_public_data_table_row,
    set_profile_manager_field,
    wait_for_public_selector,
    write_installed_tui_failure_receipt,
)
from dev.acceptance.income_tax.installed_tui_financial_child import required_profile_facts
from dev.acceptance.income_tax.scenario import build_scenario

_SCHEMA_VERSION: Final = "retenciones-01-installed-tui-withholding-v5"
_YEAR: Final = 2025
_UNEXERCISED: Final[tuple[str, ...]] = (
    "tui_only_historical_work_creation",
    "tui_only_periodic_lifecycle",
)
_CLI_PERIODIC_LIFECYCLE: Final[tuple[str, ...]] = (
    "modelo.work.calculate",
    "modelo.work.verify",
    "modelo.export",
)
_CLI_ANNUAL_LIFECYCLE: Final[tuple[str, ...]] = (
    "modelo-180.work.create.calculate.verify.export",
    "modelo-190.work.create.calculate.verify.export",
)
_COUNTERPARTY_NIF: Final = "B12345674"
_LEDGER_RETENTION_RATE: Final = "0.19"
_TUI_COUNTERPARTY_NAME: Final = "Synthetic withholding recipient"
_TUI_PROPERTY_REFERENCE: Final = "1234567VK4713S0001AA"


class RetencionesInstalledTuiError(RuntimeError):
    """Raised when the installed withholding journey cannot prove its public slice."""


class AnnualVerificationRefusalError(RetencionesInstalledTuiError):
    """A verification refusal retaining only public, value-free identifiers."""

    def __init__(self, *, modelo: str, findings: tuple[str, ...], missing_casilla_ids: tuple[str, ...]) -> None:
        """Bind only the public identifiers from one refused annual verification."""
        self.stage = "annual_continuation"
        self.diagnostic_code = f"tui-{modelo}-annual_verification_not_complete"
        self.findings = findings
        self.missing_casilla_ids = missing_casilla_ids
        super().__init__(self.diagnostic_code)


def _annual_verification_refusal(*, modelo: str, verified: object) -> AnnualVerificationRefusalError:
    """Redact a public verify response to its non-financial finding identifiers."""
    if not isinstance(verified, dict):
        return AnnualVerificationRefusalError(modelo=modelo, findings=(), missing_casilla_ids=())
    missing_raw = verified.get("missing_required_casilla_ids")
    missing = (
        tuple(sorted({value for value in missing_raw if isinstance(value, str)}))
        if isinstance(missing_raw, list)
        else ()
    )
    findings_raw = verified.get("findings")
    finding_ids: set[str] = set()
    if isinstance(findings_raw, list):
        for finding in findings_raw:
            if not isinstance(finding, dict):
                continue
            for key in ("kind", "casilla_id", "expectation_id"):
                value = finding.get(key)
                if isinstance(value, str):
                    finding_ids.add(f"{key}:{value}")
    return AnnualVerificationRefusalError(
        modelo=modelo,
        findings=tuple(sorted(finding_ids)),
        missing_casilla_ids=missing,
    )


def _public_screen_identity(pilot: Any) -> str:
    """Return only the mounted screen's public class and id for a safe receipt."""
    screen = pilot.app.screen
    screen_id = getattr(screen, "id", None)
    if not isinstance(screen_id, str):
        screen_id = "none"
    return f"{type(screen).__name__}:{screen_id}"


def _public_navigation_state(pilot: Any) -> str:
    """Classify the root's rendered navigation notice without retaining its text."""
    from textual.css.query import NoMatches
    from textual.widgets import Static

    try:
        notice = pilot.app.query_one("#root-navigation-refusal", Static)
    except NoMatches:
        return "root_navigation_notice_unavailable"
    return "root_navigation_refused" if str(notice.render()).strip() else "root_navigation_notice_empty"


async def _wait_for_active_screen(pilot: Any, *, screen_id: str, polls: int = 180) -> None:
    """Wait for a routed screen that is itself the public selector target."""
    for _ in range(polls):
        if getattr(pilot.app.screen, "id", None) == screen_id:
            return
        await pilot.pause()
    raise RetencionesInstalledTuiError(f"installed TUI did not mount {screen_id}")


@dataclass(frozen=True, slots=True)
class WithholdingJourneyReceipt:
    """Value-free evidence of the two installed TUI processes."""

    schema_version: str
    status: Literal["proven"]
    product_origin: str
    product_init_sha256: str
    year: int
    professional_capture: Literal["captured"]
    urban_rent_capture: Literal["captured"]
    cli_periodic_lifecycle: tuple[str, ...]
    cli_seeded_scopes: tuple[str, str]
    tui_mutation: Literal["not_yet_mutated", "professional_replace"]
    fresh_readback: tuple[str, str]
    unexercised: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only non-financial journey evidence."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class WithholdingAnnualContinuationReceipt:
    """Value-free installed TUI-capture to annual-CLI continuation evidence."""

    schema_version: str
    status: Literal["proven"]
    product_origin: str
    product_init_sha256: str
    year: int
    annual_cli_lifecycle: tuple[str, ...]
    fresh_readback: tuple[str, str]
    unexercised: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only non-financial annual-continuation evidence."""
        return cast(dict[str, object], asdict(self))


def _require_empty_directory(path: Path, *, label: str) -> Path:
    """Accept only a fresh, caller-owned run directory."""
    if path.exists() and any(path.iterdir()):
        raise RetencionesInstalledTuiError(f"{label} must be empty before an installed TUI run")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


async def _activate_button(pilot: Any, selector: str) -> None:
    """Activate a visible button through normal keyboard interaction."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    button.focus()
    await pilot.press("enter")
    await pilot.pause()


async def _open_destination(pilot: Any, *, query: str, expected_selector: str) -> None:
    """Use the visible command palette to enter an admitted workspace."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    if query not in {"ledger", "withholding", "declarations"}:
        raise RetencionesInstalledTuiError("withholding journey requested an unknown workbench destination")
    stage = "palette_offer"
    try:
        label = tr(f"tui.search.destination.{query}")
        await pilot.press("ctrl+p")
        for _ in range(180):
            await pilot.pause()
            try:
                palette = pilot.app.screen
                search = palette.query_one(Input)
                options = palette.query_one(OptionList)
            except NoMatches:
                continue
            search.value = query
            for index in range(options.option_count):
                hit = getattr(options.get_option_at_index(index), "hit", None)
                if getattr(hit, "text", None) == label:
                    options.highlighted = index
                    stage = "destination_activation"
                    await pilot.press("enter")
                    await wait_for_public_selector(pilot, expected_selector, polls=180)
                    return
        raise RetencionesInstalledTuiError(f"installed command palette did not offer the {query} destination")
    except RetencionesInstalledTuiError as error:
        raise RetencionesInstalledTuiError(
            f"destination_{query}_{stage}_failed:{_public_screen_identity(pilot)}:{_public_navigation_state(pilot)}:{error}"
        ) from error
    except InstalledTuiChildError as error:
        raise RetencionesInstalledTuiError(
            f"destination_{query}_{stage}_failed:{_public_screen_identity(pilot)}:{_public_navigation_state(pilot)}"
        ) from error


async def _configure_profile(pilot: Any, *, year: int) -> None:
    """Answer through Profile Manager so the installed Ledger admission is real."""
    from textual.widgets import Input

    await pilot.press("f4")
    await wait_for_public_selector(pilot, "#manager-status", polls=180)
    await _activate_button(pilot, "#manager-add-row-activities")
    await wait_for_public_selector(pilot, "#row-input-0")
    query_public_selector(pilot, "#row-input-0", Input).value = "withholding acceptance activity"
    await _activate_button(pilot, "#btn-row-save")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#manager-status", polls=180)
    for fact in required_profile_facts(build_scenario(year)):
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


async def _wait_for_refreshed_home(pilot: Any, *, polls: int = 360) -> None:
    """Wait for the profile write to rebuild the installed destination catalogue."""
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
    raise RetencionesInstalledTuiError("installed TUI did not complete its public Home refresh")


async def _create_received_invoice(pilot: Any, *, number: str, base: str, withholding: str, year: int) -> None:
    """Create one invoice through the normal visible Ledger review flow."""
    from textual.widgets import Input, Select, Static

    stage = "open_ledger"
    try:
        await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
        stage = "open_invoice_form"
        await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="overview")
        await wait_for_public_selector(pilot, "#ledger-add-invoice")
        await _activate_button(pilot, "#ledger-add-invoice")
        await wait_for_public_selector(pilot, "#ledger-invoice-review")
        stage = "review_invoice"
        query_public_selector(pilot, "#ledger-invoice-kind", Select).value = "received"
        query_public_selector(pilot, "#ledger-invoice-class", Select).value = "ordinaria"
        values = _ledger_invoice_form_values(number=number, base=base, withholding=withholding, year=year)
        for selector, value in values.items():
            query_public_selector(pilot, selector, Input).value = value
        await _activate_button(pilot, "#ledger-invoice-review")
        await wait_for_public_selector(pilot, "#ledger-invoice-confirm")
        stage = "persist_invoice"
        await _activate_button(pilot, "#ledger-invoice-confirm")
        await pilot.app.workers.wait_for_complete()
        await wait_for_public_selector(pilot, "#ledger-invoice-again")
        if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
            raise RetencionesInstalledTuiError("invoice_persistence_refused")
        stage = "reset_invoice_form"
        await _activate_button(pilot, "#ledger-invoice-again")
        await pilot.app.workers.wait_for_complete()
    except (InstalledTuiChildError, RetencionesInstalledTuiError) as error:
        if isinstance(error, RetencionesInstalledTuiError):
            raise RetencionesInstalledTuiError(f"invoice_{stage}_failed:{error}") from error
        raise RetencionesInstalledTuiError(f"invoice_{stage}_failed:{_public_screen_identity(pilot)}") from error


def _ledger_invoice_form_values(*, number: str, base: str, withholding: str, year: int) -> dict[str, str]:
    """Return Ledger's percent/fraction input values for one received invoice."""
    return {
        "#ledger-invoice-counterparty-name": _TUI_COUNTERPARTY_NAME,
        "#ledger-invoice-counterparty-nif": _COUNTERPARTY_NIF,
        "#ledger-invoice-invoice-number": number,
        "#ledger-invoice-invoice-date": f"{year}-04-02",
        "#ledger-invoice-taxable-base": base,
        "#ledger-invoice-iva-rate": "21",
        "#ledger-invoice-iva-category": "domestic_general",
        "#ledger-invoice-currency": "EUR",
        "#ledger-invoice-retention-rate": _LEDGER_RETENTION_RATE,
        "#ledger-invoice-retention-amount": withholding,
    }


async def _open_withholding(pilot: Any, *, year: int) -> None:
    """Open the routed screen after its visible filing-year step."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    stage = "palette_offer"
    try:
        await pilot.press("ctrl+p")
        label = tr("tui.search.destination.withholding")
        for _ in range(180):
            await pilot.pause()
            try:
                palette = pilot.app.screen
                search = palette.query_one(Input)
                options = palette.query_one(OptionList)
            except NoMatches:
                continue
            search.value = "withholding"
            for index in range(options.option_count):
                hit = getattr(options.get_option_at_index(index), "hit", None)
                if getattr(hit, "text", None) == label:
                    options.highlighted = index
                    options.focus()
                    stage = "destination_activation"
                    await pilot.press("enter")
                    await pilot.pause()
                    stage = "filing_year_selector"
                    # The routed screen is the selector target itself, so it is
                    # not a descendant returned by Textual's ``query_one``.
                    await _wait_for_active_screen(pilot, screen_id="filing-year-route-screen", polls=180)
                    query_public_selector(pilot, "#filing-year-route-year", Input).value = str(year)
                    stage = "mounted_withholding_screen"
                    await _activate_button(pilot, "#filing-year-route-open")
                    await _wait_for_active_screen(pilot, screen_id="withholding-evidence-screen", polls=180)
                    return
            await pilot.pause()
        raise RetencionesInstalledTuiError("withholding_palette_offer_unavailable")
    except RetencionesInstalledTuiError as error:
        raise RetencionesInstalledTuiError(
            f"withholding_{stage}_failed:{_public_screen_identity(pilot)}:{error}"
        ) from error
    except InstalledTuiChildError as error:
        raise RetencionesInstalledTuiError(f"withholding_{stage}_failed:{_public_screen_identity(pilot)}") from error


async def _set_capture(
    pilot: Any,
    *,
    invoice_number: str,
    kind: Literal["professional", "urban_rent"],
    year: int,
    mode: Literal["append", "replace"] = "append",
) -> None:
    """Enter and capture one complete visible withholding allocation."""
    from textual.widgets import Input, Select, Static

    values = _withholding_capture_form_values(invoice_number=invoice_number, kind=kind, year=year)
    for field, value in values.items():
        query_public_selector(pilot, f"#withholding-{field}", Input).value = value
    query_public_selector(pilot, "#withholding-income-kind", Select).value = kind
    query_public_selector(pilot, "#withholding-mode", Select).value = mode
    if mode == "replace":
        query_public_selector(pilot, "#withholding-reason", Input).value = "acceptance correction"
    if kind == "professional":
        query_public_selector(pilot, "#withholding-scheme", Input).value = "actividades_profesionales"
        query_public_selector(pilot, "#withholding-inspect-modelo", Input).value = "111"
    else:
        query_public_selector(pilot, "#withholding-scheme", Input).value = "arrendamiento_urbano"
        query_public_selector(pilot, "#withholding-property-key", Input).value = "synthetic-office-a"
        query_public_selector(pilot, "#withholding-property-situation", Input).value = "1"
        query_public_selector(pilot, "#withholding-cadastral-reference", Input).value = _TUI_PROPERTY_REFERENCE
        query_public_selector(pilot, "#withholding-municipality-code", Input).value = "079"
        query_public_selector(pilot, "#withholding-municipality", Input).value = "Madrid"
        query_public_selector(pilot, "#withholding-postal-code", Input).value = "28001"
        query_public_selector(pilot, "#withholding-street-name", Input).value = "Synthetic"
        query_public_selector(pilot, "#withholding-property-modality", Input).value = "1"
        query_public_selector(pilot, "#withholding-inspect-modelo", Input).value = "115"
    await _activate_button(pilot, "#withholding-capture")
    if str(query_public_selector(pilot, "#withholding-status", Static).render()).strip() != "captured":
        raise RetencionesInstalledTuiError(f"installed {kind} capture did not report captured")


def _withholding_capture_form_values(
    *, invoice_number: str, kind: Literal["professional", "urban_rent"], year: int
) -> dict[str, str]:
    """Return the explicit visible allocation facts for the synthetic TUI capture."""
    return {
        "invoice-id": invoice_number,
        "payment-id": f"payment-{kind}",
        "payment-date": f"{year}-04-02",
        "allocation-id": f"allocation-{kind}",
        "allocated-base": "500.00" if kind == "professional" else "3000.00",
        "allocated-withholding": "95.00" if kind == "professional" else "570.00",
        "allocated-settlement": "500.00" if kind == "professional" else "3000.00",
        "idempotency-key": f"retenciones-installed-{kind}",
        "annual-percentage": "19.00",
        "clave": "G",
        "subclave": "01",
        "province": "28",
        # This payer-supplied annual detail is deliberately explicit rather
        # than inferred from province or a retention amount.
        "territorial-deduction": "0",
    }


async def _inspect_scope(pilot: Any, *, modelo: Literal["111", "115"], expected_entries: int, year: int) -> None:
    """Inspect one persisted scope through the screen's real read control.

    Modelo 111 professional allocations produce both RETENCION and PERCEPCION
    projections, while the CLI aggregate counter reports the RETENCION role.
    The visible screen therefore asserts window entries rather than CLI rows.
    """
    from textual.widgets import Input, Static

    query_public_selector(pilot, "#withholding-inspect-modelo", Input).value = modelo
    query_public_selector(pilot, "#withholding-inspect-period", Input).value = f"{year}-2T"
    await _activate_button(pilot, "#withholding-inspect")
    visible = str(query_public_selector(pilot, "#withholding-inspection", Static).render())
    if f"{expected_entries} active projections" not in visible:
        raise RetencionesInstalledTuiError(f"installed withholding inspection did not read back Modelo {modelo}")


async def _create_calendar_work(pilot: Any, *, modelo: str, year: int, period: str) -> None:
    """Create one periodic work unit through the public Calendar confirmation."""
    from textual.widgets import DataTable, Static

    stage = "open_declarations"
    try:
        await _open_destination(pilot, query="declarations", expected_selector="#declarations-navigation")
        stage = "open_calendar"
        await select_public_data_table_row(
            pilot=pilot, table_selector="#declarations-navigation", row_key="declarations.calendar"
        )
        await wait_for_public_selector(pilot, "#declarations-calendar-agenda")
        stage = "select_periodic_row"
        target = f"{modelo}|{year}|{period}"
        agenda = query_public_selector(pilot, "#declarations-calendar-agenda", DataTable)
        visible_periods = sorted(
            row_key.split("|", maxsplit=2)[2]
            for row_key in (str(item.value) for item in agenda.rows)
            if row_key.startswith(f"{modelo}|{year}|") and row_key.count("|") == 2
        )
        if target not in {str(item.value) for item in agenda.rows}:
            state = "none" if not visible_periods else "other"
            raise RetencionesInstalledTuiError(f"calendar_target_period_{state}")
        await select_public_data_table_row(pilot=pilot, table_selector="#declarations-calendar-agenda", row_key=target)
        stage = "confirm_creation"
        await wait_for_public_selector(pilot, "#btn-confirm-accept")
        await _activate_button(pilot, "#btn-confirm-accept")
        await pilot.app.workers.wait_for_complete()
        stage = "creation_notice"
        notice = str(query_public_selector(pilot, "#declarations-calendar-notice", Static).render()).strip()
        if not notice.startswith("Created "):
            category = "setup_incomplete" if "setup complete" in notice else "recovery_refused"
            raise RetencionesInstalledTuiError(f"calendar_work_create_{category}")
        stage = "return_home"
        await pilot.press("escape")
        await _wait_for_refreshed_home(pilot)
    except RetencionesInstalledTuiError as error:
        raise RetencionesInstalledTuiError(
            f"calendar_{stage}_failed:{_public_screen_identity(pilot)}:{error}"
        ) from error
    except InstalledTuiChildError as error:
        raise RetencionesInstalledTuiError(f"calendar_{stage}_failed:{_public_screen_identity(pilot)}") from error


async def _work_id_for_address(pilot: Any, *, modelo: str, year: int, period: str) -> str:
    """Resolve the opaque public row key for one displayed natural address."""
    from textual.widgets import DataTable

    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    table = query_public_selector(pilot, "#declarations-list", DataTable)
    matches = [
        row_key
        for row_key in table.rows
        if modelo in " ".join(str(cell) for cell in table.get_row(row_key))
        and str(year) in " ".join(str(cell) for cell in table.get_row(row_key))
        and period in " ".join(str(cell) for cell in table.get_row(row_key))
    ]
    if len(matches) != 1:
        raise RetencionesInstalledTuiError("declarations_did_not_expose_one_periodic_work_row")
    return str(matches[0].value)


async def _open_work(pilot: Any, *, work_unit_id: str) -> None:
    """Open one work unit using its rendered declaration-list row key."""
    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    await select_public_data_table_row(pilot=pilot, table_selector="#declarations-list", row_key=work_unit_id)
    await wait_for_public_selector(pilot, "#modelo-lifecycle-calculate")


async def _run_periodic_lifecycle(pilot: Any, *, work_unit_id: str, export_path: Path) -> tuple[str, ...]:
    """Calculate, verify, and export an existing work through visible controls."""
    from textual.widgets import Input

    from dev.acceptance.income_tax.tui_journey import (
        activate_tui_operation,
        installed_lifecycle_contract,
        wait_for_tui_refresh,
    )

    contract = installed_lifecycle_contract(work_create_id="#declarations-calendar-agenda")
    completed: list[str] = []
    for binding in (contract.calculate, contract.verify):
        await _open_work(pilot, work_unit_id=work_unit_id)
        terminal = await activate_tui_operation(pilot, binding=binding)
        if terminal.outcome.value != "proven":
            raise RetencionesInstalledTuiError(f"{binding.operation_id}_did_not_reach_succeeded_terminal")
        await wait_for_tui_refresh(pilot, binding=binding)
        completed.append(binding.operation_id)
    await _open_work(pilot, work_unit_id=work_unit_id)
    query_public_selector(pilot, "#modelo-lifecycle-export-path", Input).value = str(export_path)
    terminal = await activate_tui_operation(pilot, binding=contract.export)
    if terminal.outcome.value != "proven" or not export_path.is_file() or export_path.stat().st_size == 0:
        raise RetencionesInstalledTuiError("modelo_export_did_not_reach_succeeded_terminal")
    completed.append(contract.export.operation_id)
    return tuple(completed)


def _run_launcher(*, passphrase: str, drive_after_home: Any) -> None:
    """Run and prove that the headless launcher executed its public callback."""
    from cadrumo.entrypoints.tui.launcher import main

    callback_entered = False
    callback_completed = False

    async def observed_drive(pilot: Any) -> None:
        nonlocal callback_completed, callback_entered
        callback_entered = True
        await drive_after_home(pilot)
        callback_completed = True

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=observed_drive),
    )
    if exit_code != 0:
        raise RetencionesInstalledTuiError("installed withholding launcher did not exit cleanly")
    if not callback_entered:
        raise RetencionesInstalledTuiError("installed withholding launcher did not enter public callback")
    if not callback_completed:
        raise RetencionesInstalledTuiError("installed withholding launcher did not complete public callback")


async def _login_existing_profile_through_tui(*, passphrase: str) -> None:
    """Use the visible Login screen to admit the CLI-created profile."""
    from textual.widgets import Input

    from cadrumo.application.user_profile.login_interaction import (
        ProfileLoginInventoryState,
        attempt_profile_login,
        observe_profile_login_inventory,
    )
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.login import LoginScreen

    inventory = observe_profile_login_inventory()
    if inventory.state is not ProfileLoginInventoryState.RECOGNIZED:
        raise InstalledTuiChildError("installed TUI login did not recognize the CLI-created profile")
    with bundled_indexed_authority().operation() as operation:
        screen = LoginScreen(
            choices=inventory.choices,
            authenticate=lambda profile_id, secret: attempt_profile_login(
                profile_id, secret, profile_decode_context=operation.profile_decode_context()
            ),
            preselected=inventory.preselected_profile_id,
        )
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await wait_for_public_selector(pilot, "#field-passphrase")
            query_public_selector(pilot, "#field-passphrase", Input).value = passphrase
            await pilot.click("#btn-unlock")
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
    if screen.outcome is None:
        raise InstalledTuiChildError("installed TUI Login screen did not admit the CLI-created profile")


def _admit_cli_created_profile(*, passphrase: str) -> None:
    """Admit a CLI-seeded profile before a fresh installed launcher starts."""
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(_login_existing_profile_through_tui(passphrase=passphrase))


def _receipt(
    *,
    workspace_root: Path,
    year: int,
    fresh_readback: tuple[str, str],
    cli_periodic_lifecycle: tuple[str, ...] = (),
    cli_seeded_scopes: tuple[str, str] = ("not_yet_seeded", "not_yet_seeded"),
    tui_mutation: Literal["not_yet_mutated", "professional_replace"] = "not_yet_mutated",
) -> WithholdingJourneyReceipt:
    product = installed_product_evidence(workspace_root=workspace_root)
    return WithholdingJourneyReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        year=year,
        professional_capture="captured",
        urban_rent_capture="captured",
        cli_periodic_lifecycle=cli_periodic_lifecycle,
        cli_seeded_scopes=cli_seeded_scopes,
        tui_mutation=tui_mutation,
        fresh_readback=fresh_readback,
        unexercised=_UNEXERCISED,
    )


def run_capture_child(
    *, workspace_root: Path, profile_label: str, passphrase: str, year: int, scratch: Path
) -> WithholdingJourneyReceipt:
    """Register and write professional plus urban-rent evidence through installed TUI."""
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))

    stage = "profile_configuration"

    async def drive(pilot: Any) -> None:
        nonlocal stage
        try:
            await _configure_profile(pilot, year=year)
            stage = "professional_invoice"
            await _create_received_invoice(
                pilot, number="RET-PRO-2025-001", base="500.00", withholding="95.00", year=year
            )
            stage = "urban_rent_invoice"
            await _create_received_invoice(
                pilot, number="RET-RENT-2025-001", base="3000.00", withholding="570.00", year=year
            )
            stage = "withholding_route"
            await _open_withholding(pilot, year=year)
            stage = "professional_capture"
            await _set_capture(pilot, invoice_number="RET-PRO-2025-001", kind="professional", year=year)
            stage = "professional_inspection"
            await _inspect_scope(pilot, modelo="111", expected_entries=2, year=year)
            stage = "urban_rent_capture"
            await _set_capture(pilot, invoice_number="RET-RENT-2025-001", kind="urban_rent", year=year)
            stage = "urban_rent_inspection"
            await _inspect_scope(pilot, modelo="115", expected_entries=1, year=year)
        except RetencionesInstalledTuiError as error:
            raise RetencionesInstalledTuiError(f"capture_{stage}_failed:{error}") from error
        except InstalledTuiChildError as error:
            raise RetencionesInstalledTuiError(f"capture_{stage}_failed") from error
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    return _receipt(workspace_root=workspace_root, year=year, fresh_readback=("not_yet_reopened", "not_yet_reopened"))


def run_reopen_child(*, workspace_root: Path, passphrase: str, year: int) -> WithholdingJourneyReceipt:
    """Read the two scopes through a fresh installed-TUI process."""
    _admit_cli_created_profile(passphrase=passphrase)
    stage = "withholding_route"

    async def drive(pilot: Any) -> None:
        nonlocal stage
        try:
            await _open_withholding(pilot, year=year)
            stage = "professional_inspection"
            await _inspect_scope(pilot, modelo="111", expected_entries=2, year=year)
            stage = "urban_rent_inspection"
            await _inspect_scope(pilot, modelo="115", expected_entries=1, year=year)
        except RetencionesInstalledTuiError as error:
            raise RetencionesInstalledTuiError(f"reopen_{stage}_failed:{error}") from error
        except InstalledTuiChildError as error:
            raise RetencionesInstalledTuiError(f"reopen_{stage}_failed") from error
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    return _receipt(workspace_root=workspace_root, year=year, fresh_readback=("modelo-111", "modelo-115"))


def run_mutation_child(*, workspace_root: Path, passphrase: str, year: int) -> WithholdingJourneyReceipt:
    """Inspect public CLI evidence, then replace it through the visible form."""
    _admit_cli_created_profile(passphrase=passphrase)
    stage = "withholding_route"
    post_replace_inspected = False

    async def drive(pilot: Any) -> None:
        nonlocal post_replace_inspected, stage
        try:
            await _open_withholding(pilot, year=year)
            stage = "urban_rent_baseline_inspection"
            await _inspect_scope(pilot, modelo="115", expected_entries=1, year=year)
            # Replace consumes the screen's latest visible baseline, so inspect
            # its Modelo 111 target last rather than carrying another scope's token.
            stage = "professional_baseline_inspection"
            await _inspect_scope(pilot, modelo="111", expected_entries=4, year=year)
            stage = "professional_replace"
            await _set_capture(
                pilot,
                invoice_number="RET-PROF-2025-001",
                kind="professional",
                year=year,
                mode="replace",
            )
            stage = "professional_replacement_inspection"
            await _inspect_scope(pilot, modelo="111", expected_entries=2, year=year)
            post_replace_inspected = True
        except RetencionesInstalledTuiError as error:
            raise RetencionesInstalledTuiError(f"mutation_{stage}_failed:{error}") from error
        except InstalledTuiChildError as error:
            raise RetencionesInstalledTuiError(f"mutation_{stage}_failed") from error
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    if not post_replace_inspected:
        raise RetencionesInstalledTuiError("mutation_post_replace_inspection_not_proven")
    return _receipt(
        workspace_root=workspace_root,
        year=year,
        cli_seeded_scopes=("modelo-111", "modelo-115"),
        tui_mutation="professional_replace",
        fresh_readback=("not_yet_reopened", "not_yet_reopened"),
    )


def _child_document(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RetencionesInstalledTuiError("installed withholding receipt is not readable JSON") from error
    if not isinstance(document, dict):
        raise RetencionesInstalledTuiError("installed withholding receipt is not an object")
    return cast(dict[str, object], document)


def _proven_receipt(
    document: dict[str, object], *, year: int, require_fresh_readback: bool, require_tui_mutation: bool = False
) -> WithholdingJourneyReceipt:
    expected = {"schema_version": _SCHEMA_VERSION, "status": "proven", "year": year}
    if any(document.get(key) != value for key, value in expected.items()):
        raise RetencionesInstalledTuiError("installed withholding child did not prove the expected journey")
    origin = document.get("product_origin")
    initializer = document.get("product_init_sha256")
    fresh = document.get("fresh_readback")
    unexercised = document.get("unexercised")
    seeded_scopes = document.get("cli_seeded_scopes")
    tui_mutation = document.get("tui_mutation")
    if (
        not isinstance(origin, str)
        or not origin
        or not isinstance(initializer, str)
        or len(initializer) != 64
        or document.get("professional_capture") != "captured"
        or document.get("urban_rent_capture") != "captured"
        or tuple(document.get("cli_periodic_lifecycle", ())) != ()
        or (
            (seeded_scopes != ["modelo-111", "modelo-115"] or tui_mutation != "professional_replace")
            if require_tui_mutation
            else (seeded_scopes != ["not_yet_seeded", "not_yet_seeded"] or tui_mutation != "not_yet_mutated")
        )
        or not isinstance(fresh, list)
        or not all(isinstance(value, str) for value in fresh)
        or not isinstance(unexercised, list)
        or tuple(unexercised) != _UNEXERCISED
    ):
        raise RetencionesInstalledTuiError("installed withholding child receipt has an invalid public shape")
    readback = cast(tuple[str, str], tuple(fresh))
    if len(readback) != 2 or (require_fresh_readback and readback != ("modelo-111", "modelo-115")):
        raise RetencionesInstalledTuiError("installed withholding child did not prove fresh scope readback")
    return WithholdingJourneyReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        product_origin=origin,
        product_init_sha256=initializer,
        year=year,
        professional_capture="captured",
        urban_rent_capture="captured",
        cli_periodic_lifecycle=(),
        cli_seeded_scopes=(
            ("modelo-111", "modelo-115") if require_tui_mutation else ("not_yet_seeded", "not_yet_seeded")
        ),
        tui_mutation="professional_replace" if require_tui_mutation else "not_yet_mutated",
        fresh_readback=readback,
        unexercised=_UNEXERCISED,
    )


def _run_tui_to_cli_periodic_lifecycle(
    *, cli_executable: Path, store: Path, authority_root: Path, passphrase: str, scratch: Path, year: int
) -> tuple[str, ...]:
    """Use only installed public CLI commands over the TUI-created encrypted store."""
    from dev.acceptance.installed_cli import InstalledCli
    from dev.acceptance.retenciones.cli_journey import (
        _expected_casillas_from_result,
        _require_result,
        _required_nonnegative_int,
        _required_text,
        _selected_layouts,
        _validate_export,
    )
    from dev.acceptance.retenciones.scenario import build_installed_periodic_cli_slices

    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    _require_result(
        cli,
        (
            "config",
            "profile",
            "edit",
            "retenciones-installed-tui",
            "--quiet",
            "--accept-defaults",
            "--pays-professionals-with-retencion",
            "--pays-rent-with-retencion",
            "--no-pays-capital-income-with-retencion",
            "--no-colegio-concertado",
        ),
        stage="tui_to_cli_profile_enable_withholding_duties",
    )
    _require_result(cli, ("config", "profile", "complete-setup"), stage="tui_to_cli_profile_complete_setup")
    slices = build_installed_periodic_cli_slices(year)
    _generation, layouts = _selected_layouts(authority_root=authority_root, slices=slices, year=year)
    for slice_ in slices:
        aggregate = _require_result(
            cli,
            ("app", "modelo", "aggregate", "--modelo", slice_.modelo, "--year", str(year), "--period", slice_.period),
            stage=f"tui_to_cli_{slice_.modelo}_aggregate",
        )
        aggregate_stage = f"tui_to_cli_{slice_.modelo}_aggregate"
        observations = _required_nonnegative_int(aggregate, key="observation_count", stage=aggregate_stage)
        if observations < 1:
            raise RetencionesInstalledTuiError("tui_to_cli_aggregate_did_not_read_tui_evidence")
        work = _require_result(
            cli,
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                slice_.modelo,
                "--year",
                str(year),
                "--period",
                slice_.period,
                "--revision",
                slice_.revision,
                "--by",
                "retenciones-tui-continuation",
            ),
            stage=f"tui_to_cli_{slice_.modelo}_work_create",
        )
        work_stage = f"tui_to_cli_{slice_.modelo}_work_create"
        work_id = _required_text(work, key="work_unit_id", stage=work_stage)
        calculation_stage = f"tui_to_cli_{slice_.modelo}_calculate"
        calculated = _require_result(
            cli,
            ("app", "modelo", "work", "calculate", work_id, "--by", "retenciones-tui-continuation"),
            stage=calculation_stage,
        )
        _expected_casillas_from_result(calculated, expected=slice_.expected_casillas, stage=calculation_stage)
        revision = _required_text(calculated, key="calculation_revision_id", stage=calculation_stage)
        verification_stage = f"tui_to_cli_{slice_.modelo}_verify"
        verified = _require_result(
            cli,
            ("app", "modelo", "work", "verify", revision, "--by", "retenciones-tui-continuation"),
            stage=verification_stage,
        )
        if verified.get("granted_verificado_completo") is not True:
            raise RetencionesInstalledTuiError("tui_to_cli_verification_not_complete")
        target = scratch / f"tui-to-cli-modelo-{slice_.modelo}-{year}-{slice_.period}.boe"
        export_stage = f"tui_to_cli_{slice_.modelo}_export"
        _require_result(
            cli,
            ("app", "modelo", "export", work_id, "--output", str(target), "--by", "retenciones-tui-continuation"),
            stage=export_stage,
        )
        if not target.is_file():
            raise RetencionesInstalledTuiError("tui_to_cli_export_artifact_missing")
        _validate_export(
            layout=layouts[slice_.slice_id],
            payload=target.read_bytes(),
            expected=slice_.expected_casillas,
            stage=export_stage,
        )
    return _CLI_PERIODIC_LIFECYCLE


def _tui_captured_annual_slices(year: int) -> tuple[Any, ...]:
    """Return an independent annual oracle for the two visible TUI captures.

    These records describe only the two allocations entered by ``_set_capture``.
    They are used to validate public CLI outputs, never sent to a capture
    command, so this continuation does not add CLI-authored financial evidence.
    """
    from dataclasses import replace as dataclass_replace
    from datetime import date
    from decimal import Decimal

    from dev.acceptance.retenciones.scenario import (
        AnnualExportRecordExpectation,
        AnnualSourcePeriodInput,
        EvidenceState,
        InstalledAnnualCliSlice,
        PaymentAllocation,
        build_installed_periodic_cli_slices,
    )

    professional_reference, rent_reference = build_installed_periodic_cli_slices(year)
    professional = dataclass_replace(
        professional_reference,
        counterparty_name=_TUI_COUNTERPARTY_NAME,
        invoice_date=date(year, 4, 2),
        allocations=(
            PaymentAllocation(
                allocation_id="allocation-professional",
                payment_event_id="payment-professional",
                paid_on=date(year, 4, 2),
                allocated_base=Decimal("500.00"),
                allocated_withholding=Decimal("95.00"),
                allocated_settlement=Decimal("500.00"),
            ),
        ),
    )
    rent = dataclass_replace(
        rent_reference,
        counterparty_name=_TUI_COUNTERPARTY_NAME,
        invoice_date=date(year, 4, 2),
        property_reference=_TUI_PROPERTY_REFERENCE,
        modelo_180_property=dataclass_replace(
            rent_reference.modelo_180_property,
            cadastral_reference=_TUI_PROPERTY_REFERENCE,
        ),
        allocations=(
            PaymentAllocation(
                allocation_id="allocation-urban_rent",
                payment_event_id="payment-urban_rent",
                paid_on=date(year, 4, 2),
                allocated_base=Decimal("3000.00"),
                allocated_withholding=Decimal("570.00"),
                allocated_settlement=Decimal("3000.00"),
            ),
        ),
    )

    def source_periods(*, modelo: str) -> tuple[Any, ...]:
        casillas = professional.expected_casillas if modelo == "111" else rent.expected_casillas
        no_activity = EvidenceState.NO_RELEVANT_PAYMENT
        return (
            AnnualSourcePeriodInput("1T", no_activity, 0, tuple((key, value * 0) for key, value in casillas)),
            AnnualSourcePeriodInput("2T", EvidenceState.AVAILABLE, 1, casillas),
            AnnualSourcePeriodInput("3T", no_activity, 0, tuple((key, value * 0) for key, value in casillas)),
            AnnualSourcePeriodInput("4T", no_activity, 0, tuple((key, value * 0) for key, value in casillas)),
        )

    return (
        InstalledAnnualCliSlice(
            slice_id="tui-urban-rent-180-annual",
            modelo="180",
            revision="2023-y-siguientes",
            layout_id="modelo-180-fichero-boe",
            source_modelo="115",
            captures=(rent,),
            source_periods=source_periods(modelo="115"),
            expected_header_fields=(
                ("modelo-180-decl-total-perceptores", "1"),
                ("modelo-180-decl-base-total", "3000"),
                ("modelo-180-decl-retenciones-total", "570"),
            ),
            expected_type2_rows=(
                AnnualExportRecordExpectation(
                    values=(
                        ("modelo-180-perc-nif", _COUNTERPARTY_NIF),
                        ("modelo-180-perc-nombre", _TUI_COUNTERPARTY_NAME),
                        ("modelo-180-perc-provincia", "28"),
                        ("modelo-180-perc-modalidad", "1"),
                        ("modelo-180-perc-base", "3000"),
                        ("modelo-180-perc-porcentaje-retencion", "19"),
                        ("modelo-180-perc-retenciones", "570"),
                        ("modelo-180-perc-ejercicio-devengo", str(year)),
                        ("modelo-180-perc-situacion-inmueble", "1"),
                        ("modelo-180-perc-referencia-catastral", _TUI_PROPERTY_REFERENCE),
                    )
                ),
            ),
        ),
        InstalledAnnualCliSlice(
            slice_id="tui-professional-190-annual",
            modelo="190",
            revision="2025-y-siguientes",
            layout_id="modelo-190-fichero-boe",
            source_modelo="111",
            captures=(professional,),
            source_periods=source_periods(modelo="111"),
            expected_header_fields=(
                ("modelo-190-decl-total-percepciones", "1"),
                ("modelo-190-decl-percepciones-total", "500"),
                ("modelo-190-decl-retenciones-total", "95"),
            ),
            expected_type2_rows=(
                AnnualExportRecordExpectation(
                    values=(
                        ("modelo-190-perc-nif", _COUNTERPARTY_NIF),
                        ("modelo-190-perc-nombre", _TUI_COUNTERPARTY_NAME),
                        ("modelo-190-perc-codigo-provincia", "28"),
                        ("modelo-190-perc-ceuta-melilla", "0"),
                        ("modelo-190-perc-clave", "G"),
                        ("modelo-190-perc-subclave", "01"),
                        ("modelo-190-perc-percepcion-dineraria", "500"),
                        ("modelo-190-perc-retenciones-practicadas", "95"),
                    )
                ),
            ),
        ),
    )


def _attest_tui_captured_no_activity_periods(
    *, cli: Any, slice_: Any, captures_by_period: dict[str, list[Any]], year: int
) -> frozenset[str]:
    """Use public CLI profile facts for the TUI profile's genuinely empty quarters."""
    from dev.acceptance.retenciones.cli_journey import _assert_source_period_evidence, _require_result

    option_by_modelo = {
        "111": "--modelo-111-no-retenciones-periods",
        "115": "--modelo-115-no-relevant-payment-periods",
    }
    option = option_by_modelo.get(slice_.source_modelo)
    if option is None:
        raise RetencionesInstalledTuiError("tui_annual_source_modelo_unsupported")
    tokens: list[str] = []
    for source_period in slice_.source_periods:
        captures = tuple(captures_by_period.get(source_period.period, ()))
        _assert_source_period_evidence(
            source_period=source_period,
            captures=captures,
            stage=f"{slice_.slice_id}:{slice_.source_modelo}_tui_no_activity_preflight:{source_period.period}",
        )
        if not captures:
            tokens.append(f"{year}:{source_period.period}")
    if not tokens:
        return frozenset()
    _require_result(
        cli,
        (
            "config",
            "profile",
            "edit",
            "retenciones-installed-tui",
            "--quiet",
            option,
            ",".join(tokens),
        ),
        stage=f"{slice_.slice_id}:{slice_.source_modelo}_tui_no_activity_attestation",
    )
    return frozenset(tokens)


def _run_tui_to_cli_annual_lifecycle(
    *, cli_executable: Path, store: Path, authority_root: Path, passphrase: str, scratch: Path, year: int
) -> tuple[str, ...]:
    """Materialize and validate annual returns from TUI-captured evidence only."""
    from dev.acceptance.installed_cli import InstalledCli
    from dev.acceptance.retenciones.cli_journey import (
        _annual_source_revision,
        _materialize_annual_source_period,
        _require_result,
        _required_nonnegative_int,
        _required_text,
        _selected_annual_layouts,
        _validate_annual_export,
    )

    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    _require_result(
        cli,
        (
            "config",
            "profile",
            "edit",
            "retenciones-installed-tui",
            "--quiet",
            "--accept-defaults",
            "--pays-professionals-with-retencion",
            "--pays-rent-with-retencion",
            "--no-pays-capital-income-with-retencion",
            "--no-colegio-concertado",
        ),
        stage="tui_to_cli_annual_profile_enable_withholding_duties",
    )
    _require_result(cli, ("config", "profile", "complete-setup"), stage="tui_to_cli_annual_profile_complete_setup")
    slices = _tui_captured_annual_slices(year)
    _generation, layouts = _selected_annual_layouts(authority_root=authority_root, slices=slices, year=year)
    for slice_ in slices:
        captures_by_period: dict[str, list[Any]] = {}
        for capture in slice_.captures:
            captures_by_period.setdefault(capture.period, []).append(capture)
        for source_period in slice_.source_periods:
            aggregate = _require_result(
                cli,
                (
                    "app",
                    "modelo",
                    "aggregate",
                    "--modelo",
                    slice_.source_modelo,
                    "--year",
                    str(year),
                    "--period",
                    source_period.period,
                ),
                stage=f"{slice_.slice_id}:fresh_reopen:{source_period.period}",
            )
            observed = _required_nonnegative_int(
                aggregate, key="observation_count", stage=f"{slice_.slice_id}:fresh_reopen:{source_period.period}"
            )
            if observed != source_period.expected_observation_count:
                raise RetencionesInstalledTuiError(f"{slice_.slice_id}_annual_observation_count_mismatch")
        attestations = _attest_tui_captured_no_activity_periods(
            cli=cli, slice_=slice_, captures_by_period=captures_by_period, year=year
        )
        source_revision = _annual_source_revision(slice_, stage=f"{slice_.slice_id}:source_preflight")
        for source_period in slice_.source_periods:
            _materialize_annual_source_period(
                cli=cli,
                source_modelo=slice_.source_modelo,
                source_revision=source_revision,
                source_period=source_period,
                captures=tuple(captures_by_period.get(source_period.period, ())),
                year=year,
                no_activity_attestations=attestations,
            )
        work = _require_result(
            cli,
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                slice_.modelo,
                "--year",
                str(year),
                "--period",
                slice_.period,
                "--revision",
                slice_.revision,
                "--by",
                "retenciones-tui-annual-continuation",
            ),
            stage=f"{slice_.slice_id}:work_create",
        )
        work_id = _required_text(work, key="work_unit_id", stage=f"{slice_.slice_id}:work_create")
        calculated = _require_result(
            cli,
            ("app", "modelo", "work", "calculate", work_id, "--by", "retenciones-tui-annual-continuation"),
            stage=f"{slice_.slice_id}:work_calculate",
        )
        revision_id = _required_text(
            calculated,
            key="calculation_revision_id",
            stage=f"{slice_.slice_id}:work_calculate",
        )
        verified = _require_result(
            cli,
            ("app", "modelo", "work", "verify", revision_id, "--by", "retenciones-tui-annual-continuation"),
            stage=f"{slice_.slice_id}:work_verify",
        )
        if verified.get("granted_verificado_completo") is not True:
            raise _annual_verification_refusal(modelo=slice_.modelo, verified=verified)
        target = scratch / f"tui-to-cli-annual-modelo-{slice_.modelo}-{year}-{slice_.period}.boe"
        _require_result(
            cli,
            (
                "app",
                "modelo",
                "export",
                work_id,
                "--output",
                str(target),
                "--by",
                "retenciones-tui-annual-continuation",
            ),
            stage=f"{slice_.slice_id}:export",
        )
        if not target.is_file():
            raise RetencionesInstalledTuiError(f"{slice_.slice_id}_annual_export_artifact_missing")
        _validate_annual_export(
            layout=layouts[slice_.slice_id],
            payload=target.read_bytes(),
            expected_header=slice_.expected_header_fields,
            expected_type2_rows=slice_.expected_type2_rows,
            stage=f"{slice_.slice_id}:export_parse",
        )
    return _CLI_ANNUAL_LIFECYCLE


@dataclass(frozen=True, slots=True)
class _WindowReadback:
    """Payload-free public metadata for one persisted withholding window."""

    modelo: str
    observation_count: int
    scope_token: str
    generation_id: str
    generation: int
    parent_generation_id: str | None
    mode: str | None


@dataclass(frozen=True, slots=True)
class _ReplacementReadback:
    """Value-free comparison of CLI windows around a visible TUI replacement."""

    generation_changed: bool
    parent_matches: bool
    mode_replace: bool
    count_matches: bool
    urban_rent_unchanged: bool


def _read_window(
    *,
    cli: Any,
    modelo: Literal["111", "115"],
    year: int,
    stage: str,
) -> _WindowReadback:
    """Read one public aggregate window without exposing its encrypted rows."""
    from dev.acceptance.retenciones.cli_journey import _require_result

    document = _require_result(
        cli,
        ("app", "modelo", "aggregate", "--modelo", modelo, "--year", str(year), "--period", "2T"),
        stage=stage,
    )
    observations = document.get("observation_count")
    window = document.get("withholding_window")
    if isinstance(observations, bool) or not isinstance(observations, int):
        raise RetencionesInstalledTuiError(f"{stage}_observation_count_invalid")
    if not isinstance(window, dict):
        raise RetencionesInstalledTuiError(f"{stage}_window_metadata_missing")
    baseline = window.get("baseline")
    audit = window.get("generation_audit")
    generation = window.get("generation")
    if (
        not isinstance(baseline, dict)
        or not isinstance(baseline.get("scope_token"), str)
        or not isinstance(baseline.get("generation_id"), str)
        or len(baseline["generation_id"]) != 64
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 0
    ):
        raise RetencionesInstalledTuiError(f"{stage}_window_metadata_invalid")
    if audit is None:
        parent_generation_id = None
        mode = None
    elif (
        isinstance(audit, dict)
        and isinstance(audit.get("parent_generation_id"), str)
        and isinstance(audit.get("mode"), str)
    ):
        parent_generation_id = audit["parent_generation_id"]
        mode = audit["mode"]
    else:
        raise RetencionesInstalledTuiError(f"{stage}_window_audit_invalid")
    return _WindowReadback(
        modelo=modelo,
        observation_count=observations,
        scope_token=baseline["scope_token"],
        generation_id=baseline["generation_id"],
        generation=generation,
        parent_generation_id=parent_generation_id,
        mode=mode,
    )


def _seed_cli_evidence(
    *, cli_executable: Path, store: Path, authority_root: Path, passphrase: str, year: int
) -> tuple[_WindowReadback, _WindowReadback]:
    """Create the professional and urban-rent evidence through installed CLI only."""
    from dev.acceptance.installed_cli import InstalledCli
    from dev.acceptance.retenciones.cli_journey import _capture_invoice_withholding, _create_withholding_profile
    from dev.acceptance.retenciones.scenario import build_installed_periodic_cli_slices

    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    _create_withholding_profile(cli, year=year)
    slices = build_installed_periodic_cli_slices(year)
    for slice_ in slices:
        _capture_invoice_withholding(cli=cli, slice_=slice_, year=year)
    professional = _read_window(
        cli=cli,
        modelo="111",
        year=year,
        stage="cli_seed_professional_readback",
    )
    urban_rent = _read_window(
        cli=cli,
        modelo="115",
        year=year,
        stage="cli_seed_urban_rent_readback",
    )
    return professional, urban_rent


def _assert_tui_replacement(
    *,
    cli_executable: Path,
    store: Path,
    authority_root: Path,
    passphrase: str,
    year: int,
    seeded: tuple[_WindowReadback, _WindowReadback],
) -> _ReplacementReadback:
    """Read both post-mutation windows before evaluating their public metadata."""
    from dev.acceptance.installed_cli import InstalledCli

    professional_before, urban_rent_before = seeded
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    professional_after = _read_window(
        cli=cli,
        modelo="111",
        year=year,
        stage="cli_after_tui_professional_readback",
    )
    urban_rent_after = _read_window(
        cli=cli,
        modelo="115",
        year=year,
        stage="cli_after_tui_urban_rent_readback",
    )
    return _ReplacementReadback(
        generation_changed=(
            professional_after.scope_token == professional_before.scope_token
            and professional_after.generation == professional_before.generation + 1
            and professional_after.generation_id != professional_before.generation_id
        ),
        parent_matches=professional_after.parent_generation_id == professional_before.generation_id,
        mode_replace=professional_after.mode == "replace",
        count_matches=professional_after.observation_count == 1,
        urban_rent_unchanged=urban_rent_after == urban_rent_before,
    )


def run_installed_tui_withholding_journey(
    *,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int = _YEAR,
) -> WithholdingJourneyReceipt:
    """Prove an installed CLI-to-TUI correction in one encrypted store."""
    root = _require_empty_directory(output_root, label="RETENCIONES installed-TUI output root")
    workspace = workspace_root.resolve(strict=True)
    store = _require_empty_directory(root / "secure-store", label="RETENCIONES installed-TUI secure store")
    scratch = _require_empty_directory(root / "transient", label="RETENCIONES installed-TUI transient directory")
    passphrase = secrets.token_urlsafe(32)
    common = {
        "python_executable": python_executable.resolve(strict=True),
        "workspace_root": workspace,
        "child_module": "dev.acceptance.retenciones.installed_tui_withholding",
        "storage_root": store,
        "authority_root": authority_root.resolve(strict=True),
        "passphrase": passphrase,
        "timeout_seconds": 1200,
    }
    cli_executable = python_executable.resolve(strict=True).with_name("aeat.exe")
    continuation_path = root / "cli-to-tui.json"
    try:
        seeded = _seed_cli_evidence(
            cli_executable=cli_executable,
            store=store,
            authority_root=authority_root.resolve(strict=True),
            passphrase=passphrase,
            year=year,
        )
    except Exception as error:
        stage = getattr(error, "stage", "runner")
        code = getattr(error, "diagnostic_code", type(error).__name__)
        continuation_path.write_text(
            json.dumps({"status": "failed", "stage": str(stage), "code": str(code)}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise RetencionesInstalledTuiError(f"cli_seed_{stage}_{code}") from error
    mutation_path = root / "mutation.json"
    mutation = run_installed_tui_child_process(
        **common,
        child_args=(
            "--child-mode",
            "mutate",
            "--workspace-root",
            str(workspace),
            "--year",
            str(year),
            "--scratch",
            str(scratch),
            "--receipt",
            str(mutation_path),
        ),
        receipt_path=mutation_path,
    )
    if mutation.returncode != 0:
        raise RetencionesInstalledTuiError("installed withholding mutation child did not exit cleanly")
    _proven_receipt(_child_document(mutation_path), year=year, require_fresh_readback=False, require_tui_mutation=True)
    try:
        readback = _assert_tui_replacement(
            cli_executable=cli_executable,
            store=store,
            authority_root=authority_root.resolve(strict=True),
            passphrase=passphrase,
            year=year,
            seeded=seeded,
        )
        failure_code = next(
            (
                code
                for passed, code in (
                    (readback.generation_changed, "cli_after_tui_generation_not_changed"),
                    (readback.parent_matches, "cli_after_tui_parent_generation_mismatch"),
                    (readback.mode_replace, "cli_after_tui_mode_not_replace"),
                    (readback.urban_rent_unchanged, "cli_after_tui_urban_rent_window_changed"),
                    (readback.count_matches, "cli_after_tui_aggregate_observation_count_diverges_from_tui_window"),
                )
                if not passed
            ),
            None,
        )
        if failure_code is not None:
            raise RetencionesInstalledTuiError(failure_code)
    except RetencionesInstalledTuiError as error:
        continuation_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "stage": "assertion",
                    "code": str(error),
                    "readback": asdict(readback) if "readback" in locals() else None,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise
    except Exception as error:
        stage = getattr(error, "stage", "runner")
        code = getattr(error, "diagnostic_code", type(error).__name__)
        continuation_path.write_text(
            json.dumps({"status": "failed", "stage": str(stage), "code": str(code)}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise RetencionesInstalledTuiError(f"cli_to_tui_{stage}_{code}") from error
    continuation_path.write_text(
        json.dumps(
            {
                "status": "proven",
                "operations": ["cli_seed", "tui_replace", "cli_readback"],
                "readback": asdict(readback),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reopen_path = root / "reopen.json"
    reopened = run_installed_tui_child_process(
        **common,
        child_args=(
            "--child-mode",
            "reopen",
            "--workspace-root",
            str(workspace),
            "--year",
            str(year),
            "--scratch",
            str(scratch),
            "--receipt",
            str(reopen_path),
        ),
        receipt_path=reopen_path,
    )
    if reopened.returncode != 0:
        raise RetencionesInstalledTuiError("installed withholding reopen child did not exit cleanly")
    fresh = _proven_receipt(_child_document(reopen_path), year=year, require_fresh_readback=True)
    return replace(
        fresh,
        cli_seeded_scopes=("modelo-111", "modelo-115"),
        tui_mutation="professional_replace",
    )


def run_installed_tui_to_cli_annual_journey(
    *,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int = _YEAR,
) -> WithholdingAnnualContinuationReceipt:
    """Continue two visible TUI captures into local annual CLI exports.

    The only financial evidence comes from the installed TUI child.  The
    installed CLI may create local source-history and annual work records, but
    no live submission is requested.
    """
    root = _require_empty_directory(output_root, label="RETENCIONES TUI-to-CLI annual output root")
    workspace = workspace_root.resolve(strict=True)
    authority = authority_root.resolve(strict=True)
    store = _require_empty_directory(root / "secure-store", label="RETENCIONES TUI-to-CLI annual secure store")
    scratch = _require_empty_directory(root / "transient", label="RETENCIONES TUI-to-CLI annual transient directory")
    passphrase = secrets.token_urlsafe(32)
    common = {
        "python_executable": python_executable.resolve(strict=True),
        "workspace_root": workspace,
        "child_module": "dev.acceptance.retenciones.installed_tui_withholding",
        "storage_root": store,
        "authority_root": authority,
        "passphrase": passphrase,
        "timeout_seconds": 1200,
    }
    capture_path = root / "capture.json"
    captured_child = run_installed_tui_child_process(
        **common,
        child_args=(
            "--child-mode",
            "capture",
            "--workspace-root",
            str(workspace),
            "--year",
            str(year),
            "--scratch",
            str(scratch),
            "--receipt",
            str(capture_path),
        ),
        receipt_path=capture_path,
    )
    if captured_child.returncode != 0:
        raise RetencionesInstalledTuiError("installed withholding annual capture child did not exit cleanly")
    captured = _proven_receipt(_child_document(capture_path), year=year, require_fresh_readback=False)
    annual_path = root / "tui-to-cli-annual.json"
    try:
        annual_lifecycle = _run_tui_to_cli_annual_lifecycle(
            cli_executable=python_executable.resolve(strict=True).with_name("aeat.exe"),
            store=store,
            authority_root=authority,
            passphrase=passphrase,
            scratch=scratch,
            year=year,
        )
    except Exception as error:
        verification = None
        if isinstance(error, AnnualVerificationRefusalError):
            stage = error.stage
            code = error.diagnostic_code
            verification = {
                "finding_ids": list(error.findings),
                "missing_casilla_ids": list(error.missing_casilla_ids),
            }
        elif isinstance(error, RetencionesInstalledTuiError):
            stage = "annual_continuation"
            code = str(error)
        else:
            stage = str(getattr(error, "stage", "annual_continuation"))
            code = str(getattr(error, "diagnostic_code", type(error).__name__))
        annual_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "stage": stage,
                    "code": code,
                    "verification": verification,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise RetencionesInstalledTuiError("installed TUI-to-CLI annual continuation refused") from error
    annual_path.write_text(
        json.dumps(
            {
                "status": "proven",
                "annual_models": ["180", "190"],
                "annual_lifecycle": list(annual_lifecycle),
                "source_history": "local_only",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reopen_path = root / "reopen.json"
    reopened_child = run_installed_tui_child_process(
        **common,
        child_args=(
            "--child-mode",
            "reopen",
            "--workspace-root",
            str(workspace),
            "--year",
            str(year),
            "--scratch",
            str(scratch),
            "--receipt",
            str(reopen_path),
        ),
        receipt_path=reopen_path,
    )
    if reopened_child.returncode != 0:
        raise RetencionesInstalledTuiError("installed withholding annual reopen child did not exit cleanly")
    fresh = _proven_receipt(_child_document(reopen_path), year=year, require_fresh_readback=True)
    if (captured.product_origin, captured.product_init_sha256) != (fresh.product_origin, fresh.product_init_sha256):
        raise RetencionesInstalledTuiError("installed withholding annual processes did not identify the same product")
    return WithholdingAnnualContinuationReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        product_origin=fresh.product_origin,
        product_init_sha256=fresh.product_init_sha256,
        year=year,
        annual_cli_lifecycle=annual_lifecycle,
        fresh_readback=fresh.fresh_readback,
        unexercised=_UNEXERCISED,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child-mode", choices=("capture", "mutate", "reopen"), required=True)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--profile-label", default="retenciones-installed-tui")
    parser.add_argument("--year", type=int, default=_YEAR)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one stdin-credentialed installed-TUI child and write a safe receipt."""
    args = _parser().parse_args(argv)
    try:
        passphrase = read_passphrase_from_stdin()
        if args.child_mode == "capture":
            receipt = run_capture_child(
                workspace_root=args.workspace_root,
                profile_label=args.profile_label,
                passphrase=passphrase,
                year=args.year,
                scratch=args.scratch.resolve(strict=True),
            )
        elif args.child_mode == "mutate":
            receipt = run_mutation_child(workspace_root=args.workspace_root, passphrase=passphrase, year=args.year)
        else:
            receipt = run_reopen_child(workspace_root=args.workspace_root, passphrase=passphrase, year=args.year)
    except (InstalledTuiChildError, RetencionesInstalledTuiError) as error:
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(f"installed withholding journey failed: {error}"),
        )
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - installed child entry point
    raise SystemExit(main())
