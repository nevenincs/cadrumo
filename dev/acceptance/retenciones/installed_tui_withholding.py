"""Installed-TUI withholding journeys for the professional and urban-rent families.

Every child drives only rendered Textual controls of an installed product:
Ledger creates two synthetic received invoices and Withholding records
professional and urban-rent evidence. The capture, mutation and reopen modes
pair that TUI evidence with public CLI continuations. The ``tui-only`` mode
instead creates every source and annual declaration through Declarations and
calculates, verifies, files locally and exports them in the TUI, and
``tui-only-reopen`` reads the result back in a fresh process. No mode submits
anything to AEAT.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets
import time
from collections.abc import Callable, Sequence
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
    wait_for_any_public_selector,
    write_installed_tui_failure_receipt,
)
from dev.acceptance.income_tax.installed_tui_financial_child import required_profile_facts
from dev.acceptance.income_tax.scenario import build_scenario

_SCHEMA_VERSION: Final = "retenciones-01-installed-tui-withholding-v5"
_TUI_ONLY_SCHEMA_VERSION: Final = "retenciones-01-installed-tui-only-v1"
_YEAR: Final = 2025
# Wall-clock budget for one visible TUI state to settle in an installed child.
_TUI_WAIT_SECONDS: Final = 240.0
_ADMISSION_POLLS: Final = 60000
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
_TUI_ONLY_UNEXERCISED: Final[tuple[str, ...]] = (
    "modelo_123_counting",
    "later_year_modelo_193_export",
)
# Every source quarter the annual returns consume: 111 2T carries the professional
# allocation, 115 needs a local record for each quarter, attested or not.
_TUI_ONLY_SOURCE_ADDRESSES: Final[tuple[tuple[str, str], ...]] = (
    ("111", "2T"),
    ("115", "1T"),
    ("115", "2T"),
    ("115", "3T"),
    ("115", "4T"),
)
_TUI_ONLY_EXPORTED_PERIODIC: Final[tuple[tuple[str, str], ...]] = (("111", "2T"), ("115", "2T"))
_TUI_ONLY_ANNUAL_ADDRESSES: Final[tuple[tuple[str, str], ...]] = (("180", "0A"), ("190", "0A"))
_TUI_ONLY_NO_ACTIVITY_QUARTERS: Final[tuple[str, ...]] = ("1T", "3T", "4T")
_TUI_ONLY_NO_ACTIVITY_FIELDS: Final[tuple[str, ...]] = (
    "withholding.modelo_111_no_retenciones_periods",
    "withholding.modelo_115_no_relevant_payment_periods",
)
_TUI_ONLY_WITHHOLDING_PROFILE_CHOICES: Final[tuple[tuple[str, int], ...]] = (
    ("withholding.colegio_concertado", 1),
    ("withholding.pays_professionals_with_retencion", 0),
    ("withholding.pays_rent_with_retencion", 0),
    ("withholding.pays_capital_income_with_retencion", 1),
)


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
    rendered = str(notice.render()).strip()
    return f"root_navigation_refused:{rendered[:300]}" if rendered else "root_navigation_notice_empty"


async def _settle(pilot: Any) -> None:
    """Yield one Textual cycle plus a little wall-clock time between polls."""
    await pilot.pause()
    await asyncio.sleep(0.05)


def _deadline(seconds: float = _TUI_WAIT_SECONDS) -> float:
    """Return the monotonic instant a wall-clock wait gives up at."""
    return time.monotonic() + seconds


async def _wait_for_selector(pilot: Any, selector: str, *, seconds: float = _TUI_WAIT_SECONDS) -> None:
    """Wait on a wall-clock budget for a public control on the active screen.

    Poll counts measure nothing on a loaded machine: an installed root that
    rebuilds its catalogue on a worker thread can outlast any fixed number of
    Textual cycles.
    """
    from textual.css.query import NoMatches

    until = _deadline(seconds)
    while time.monotonic() < until:
        try:
            query_public_selector(pilot, selector)
        except NoMatches:
            await _settle(pilot)
        else:
            return
    raise RetencionesInstalledTuiError(f"installed TUI did not expose {selector}:{_public_screen_identity(pilot)}")


async def _wait_for_active_screen(pilot: Any, *, screen_id: str) -> None:
    """Wait for a routed screen that is itself the public selector target."""
    until = _deadline()
    while time.monotonic() < until:
        if getattr(pilot.app.screen, "id", None) == screen_id:
            return
        await _settle(pilot)
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


@dataclass(frozen=True, slots=True)
class WithholdingTuiOnlyArtifactEvidence:
    """A value-free fingerprint of one locally exported TUI artifact."""

    modelo: str
    period: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class WithholdingTuiOnlyReceipt:
    """Sanitized evidence of the full professional/rent installed TUI path."""

    schema_version: str
    status: Literal["proven"]
    product_origin: str
    product_init_sha256: str
    year: int
    profile_setup: Literal["completed"]
    required_detail_refusal: Literal["observed"]
    work_route: tuple[str, ...]
    periodic_lifecycle: tuple[str, ...]
    annual_lifecycle: tuple[str, ...]
    artifacts: tuple[WithholdingTuiOnlyArtifactEvidence, ...]
    fresh_readback: tuple[str, ...]
    fresh_filing_history: tuple[str, ...]
    historical_profile_context: Literal["current_profile_at_run"]
    unexercised: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only public lifecycle and artifact evidence."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class WithholdingTuiOnlyExportValidation:
    """Value-free result of checking every TUI export against the served official layouts."""

    schema_version: str
    status: Literal["proven"]
    authority_generation: str
    artifacts: tuple[WithholdingTuiOnlyArtifactEvidence, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the generation and artifact fingerprints the validation covered."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class WithholdingTuiOnlyReopenReceipt:
    """Value-free fresh-process persistence readback for the TUI-only path."""

    schema_version: str
    status: Literal["proven"]
    product_origin: str
    product_init_sha256: str
    year: int
    reopened_work: tuple[str, ...]
    filing_history: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only the persisted public identities read after restart."""
        return cast(dict[str, object], asdict(self))


def _require_empty_directory(path: Path, *, label: str) -> Path:
    """Accept only a fresh, caller-owned run directory."""
    if path.exists() and any(path.iterdir()):
        raise RetencionesInstalledTuiError(f"{label} must be empty before an installed TUI run")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


async def _activate_button(pilot: Any, selector: str) -> None:
    """Activate a visible button through normal keyboard interaction."""
    from textual.css.query import NoMatches
    from textual.widgets import Button

    # A disabled button cannot take focus, so Enter would reach whichever
    # control held it before; refuse instead of activating something else.
    for _ in range(40):
        await pilot.app.workers.wait_for_complete()
        if not query_public_selector(pilot, selector, Button).disabled:
            break
        await pilot.pause()
    else:
        raise RetencionesInstalledTuiError(f"{selector}_disabled:{_visible_manager_status(pilot)}")

    def resolve() -> Any:
        try:
            return pilot.app.screen.query_one(selector, Button)
        except NoMatches:
            return None

    await _focus_resolved(pilot, resolve, label=selector)
    await pilot.press("enter")
    await pilot.pause()


def _visible_manager_status(pilot: Any) -> str:
    """Return the Profile Manager's visible status line, when that page is mounted."""
    from textual.css.query import NoMatches

    try:
        status = pilot.app.screen.query_one("#manager-status")
    except NoMatches:
        return _public_screen_identity(pilot)
    return str(status.render()).strip()[:400]


async def _activate_palette_destination(pilot: Any, *, query: str, label: str) -> None:
    """Open the command palette, search ``query`` and activate the option labelled ``label``.

    The palette is recognised by its Textual type, never as "whichever screen
    has an Input": a Modelo workspace has inputs of its own. A ``ctrl+p``
    that lands while the screen is still settling is pressed again, and the
    whole wait runs on the wall-clock budget rather than a cycle count.
    """
    from textual.command import CommandPalette
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    until = _deadline()
    pressed_at = 0.0
    while time.monotonic() < until:
        screen = pilot.app.screen
        if not isinstance(screen, CommandPalette):
            if time.monotonic() - pressed_at > 5.0:
                await pilot.app.workers.wait_for_complete()
                await pilot.press("ctrl+p")
                pressed_at = time.monotonic()
            await _settle(pilot)
            continue
        try:
            search = screen.query_one(Input)
            options = screen.query_one(OptionList)
        except NoMatches:
            await _settle(pilot)
            continue
        if search.value != query:
            search.value = query
        for index in range(options.option_count):
            hit = getattr(options.get_option_at_index(index), "hit", None)
            if getattr(hit, "text", None) == label:
                options.highlighted = index
                options.focus()
                await _settle(pilot)
                await pilot.press("enter")
                await _settle(pilot)
                return
        await _settle(pilot)
    raise RetencionesInstalledTuiError(f"installed command palette did not offer the {query} destination")


async def _open_destination(pilot: Any, *, query: str, expected_selector: str) -> None:
    """Use the visible command palette to enter an admitted workspace."""
    from cadrumo.core.i18n.render import tr

    if query not in {"home", "ledger", "withholding", "declarations"}:
        raise RetencionesInstalledTuiError("withholding journey requested an unknown workbench destination")
    stage = "palette_offer"
    try:
        await _activate_palette_destination(pilot, query=query, label=tr(f"tui.search.destination.{query}"))
        stage = "destination_activation"
        await _wait_for_selector(pilot, expected_selector)
    except RetencionesInstalledTuiError as error:
        raise RetencionesInstalledTuiError(
            f"destination_{query}_{stage}_failed:{_public_screen_identity(pilot)}:{_public_navigation_state(pilot)}:{error}"
        ) from error
    except InstalledTuiChildError as error:
        raise RetencionesInstalledTuiError(
            f"destination_{query}_{stage}_failed:{_public_screen_identity(pilot)}:{_public_navigation_state(pilot)}"
        ) from error


async def _focus_resolved(pilot: Any, resolve: Callable[[], Any], *, label: str) -> Any:
    """Focus the control ``resolve`` finds, re-resolving until one laid-out instance holds focus.

    Textual applies ``focus()`` on a later message cycle, and a Profile
    Manager write redraws its section tables one loop turn at a time, so a
    table found a moment ago may already be a detached, undisplayed copy.
    Pressing Enter before focus is confirmed can activate whichever control
    held it instead, such as the document-reader card.
    """
    widget: Any = None
    until = _deadline()
    while time.monotonic() < until:
        await pilot.app.workers.wait_for_complete()
        await _settle(pilot)
        widget = resolve()
        if widget is None or not widget.display or not widget.region.area:
            continue
        widget.focus()
        for _ in range(10):
            await pilot.pause()
            if pilot.app.focused is widget:
                return widget
    focused = pilot.app.focused
    state = (
        "unresolved"
        if widget is None
        else f"display={widget.display}:region={widget.region}:disabled={widget.disabled}"
    )
    raise RetencionesInstalledTuiError(
        f"{label}_did_not_take_focus:{_public_screen_identity(pilot)}:"
        f"focused={type(focused).__name__}#{getattr(focused, 'id', None)}:{state}"
    )


async def _select_table_row(*, pilot: Any, table_selector: str, row_key: str) -> None:
    """Select one visible DataTable row by its stable key, once the table holds focus."""
    from textual.css.query import NoMatches
    from textual.widgets import DataTable

    await _wait_for_selector(pilot, table_selector)

    def resolve() -> Any:
        try:
            table = pilot.app.screen.query_one(table_selector, DataTable)
        except NoMatches:
            return None
        return table if any(str(candidate.value) == row_key for candidate in table.rows) else None

    table = await _focus_resolved(pilot, resolve, label=f"{table_selector}_row_{row_key}")
    target = next(candidate for candidate in table.rows if str(candidate.value) == row_key)
    table.move_cursor(row=table.get_row_index(target))
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


async def _set_profile_field(
    *, pilot: Any, path: str, value: str | None = None, option_index: int | None = None
) -> None:
    """Persist one Profile Manager fact through its visible editor, confirming focus first."""
    from textual.widgets import DataTable, Input, OptionList

    def resolve() -> Any:
        return next(
            (
                candidate
                for candidate in pilot.app.screen.query(DataTable)
                if any(str(row_key.value) == path for row_key in candidate.rows)
            ),
            None,
        )

    table = await _focus_resolved(pilot, resolve, label=f"profile_field_{path}")
    row_key = next(row_key for row_key in table.rows if str(row_key.value) == path)
    table.move_cursor(row=table.get_row_index(row_key))
    await pilot.pause()
    await pilot.press("enter")
    editor = await wait_for_any_public_selector(pilot, ("#edit-input", "#edit-options"))
    if editor == "#edit-input":
        if value is None or option_index is not None:
            raise RetencionesInstalledTuiError(f"profile_field_{path}_requires_text")
        query_public_selector(pilot, editor, Input).value = value
    else:
        if option_index is None or value is not None:
            raise RetencionesInstalledTuiError(f"profile_field_{path}_requires_an_option")
        options = query_public_selector(pilot, editor, OptionList)
        if not 0 <= option_index < options.option_count:
            raise RetencionesInstalledTuiError(f"profile_field_{path}_option_outside_list")
        options.highlighted = option_index
    await _activate_button(pilot, "#btn-edit-save")
    await pilot.app.workers.wait_for_complete()
    await _wait_for_selector(pilot, "#manager-status")


async def _configure_profile(pilot: Any, *, year: int, no_activity_attestations: bool = False) -> None:
    """Set withholding applicability facts and complete setup through Profile Manager.

    ``no_activity_attestations`` also records the quarters with no payment
    subject to withholding, which the annual returns need as explicit
    taxpayer facts rather than inferred zeros.
    """
    from textual.widgets import Input

    await pilot.press("f4")
    await _wait_for_selector(pilot, "#manager-status")
    await _activate_button(pilot, "#manager-add-row-activities")
    await _wait_for_selector(pilot, "#row-input-0")
    query_public_selector(pilot, "#row-input-0", Input).value = "withholding acceptance activity"
    await _activate_button(pilot, "#btn-row-save")
    await pilot.app.workers.wait_for_complete()
    await _wait_for_selector(pilot, "#manager-status")
    for fact in required_profile_facts(build_scenario(year)):
        await _set_profile_field(
            pilot=pilot,
            path=fact.path,
            value=fact.value,
            option_index=fact.option_index,
        )
    # The shared income fixture makes these optional payer facts false.  This
    # journey must set its own professional/rent applicability through the
    # public profile surface rather than correcting it with the CLI later.
    for path, option_index in _TUI_ONLY_WITHHOLDING_PROFILE_CHOICES:
        await _set_profile_field(pilot=pilot, path=path, option_index=option_index)
    if no_activity_attestations:
        quarters = ",".join(f"{year}:{quarter}" for quarter in _TUI_ONLY_NO_ACTIVITY_QUARTERS)
        for path in _TUI_ONLY_NO_ACTIVITY_FIELDS:
            await _set_profile_field(pilot=pilot, path=path, value=quarters)
    await _complete_profile_setup(pilot)
    await pilot.press("escape")
    await _wait_for_refreshed_home(pilot)


async def _complete_profile_setup(pilot: Any) -> None:
    """Use the visible completion act and require it to settle as complete."""
    from textual.css.query import NoMatches

    await _wait_for_selector(pilot, "#manager-complete-setup")
    await _activate_button(pilot, "#manager-complete-setup")
    await pilot.app.workers.wait_for_complete()
    until = _deadline()
    while time.monotonic() < until:
        try:
            query_public_selector(pilot, "#manager-status")
        except NoMatches:
            await _settle(pilot)
            continue
        try:
            query_public_selector(pilot, "#manager-complete-setup")
        except NoMatches:
            return
        await _settle(pilot)
    raise RetencionesInstalledTuiError(
        f"installed Profile Manager did not complete setup:{_visible_manager_status(pilot)}"
    )


async def _wait_for_refreshed_home(pilot: Any) -> None:
    """Wait for the profile write to rebuild the installed destination catalogue."""
    from textual.css.query import NoMatches
    from textual.widgets import Static

    until = _deadline()
    while time.monotonic() < until:
        try:
            updating = query_public_selector(pilot, "#root-updating", Static)
            pilot.app.screen.query_one("#home-agenda")
        except NoMatches:
            pass
        else:
            if not updating.display:
                return
        await _settle(pilot)
    raise RetencionesInstalledTuiError(
        f"installed TUI did not complete its public Home refresh:{_public_screen_identity(pilot)}"
    )


async def _create_received_invoice(pilot: Any, *, number: str, base: str, withholding: str, year: int) -> None:
    """Create one invoice through the normal visible Ledger review flow."""
    from textual.widgets import Input, Select, Static

    stage = "open_ledger"
    try:
        await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
        stage = "open_invoice_form"
        await _select_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="overview")
        await _wait_for_selector(pilot, "#ledger-add-invoice")
        await _activate_button(pilot, "#ledger-add-invoice")
        await _wait_for_selector(pilot, "#ledger-invoice-review")
        stage = "review_invoice"
        query_public_selector(pilot, "#ledger-invoice-kind", Select).value = "received"
        query_public_selector(pilot, "#ledger-invoice-class", Select).value = "ordinaria"
        values = _ledger_invoice_form_values(number=number, base=base, withholding=withholding, year=year)
        for selector, value in values.items():
            query_public_selector(pilot, selector, Input).value = value
        await _activate_button(pilot, "#ledger-invoice-review")
        await _wait_for_selector(pilot, "#ledger-invoice-confirm")
        stage = "persist_invoice"
        await _activate_button(pilot, "#ledger-invoice-confirm")
        await pilot.app.workers.wait_for_complete()
        await _wait_for_selector(pilot, "#ledger-invoice-again")
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
    from textual.widgets import Input

    from cadrumo.core.i18n.render import tr

    stage = "palette_offer"
    try:
        await _activate_palette_destination(pilot, query="withholding", label=tr("tui.search.destination.withholding"))
        stage = "filing_year_selector"
        # The routed screen is the selector target itself, so it is
        # not a descendant returned by Textual's ``query_one``.
        await _wait_for_active_screen(pilot, screen_id="filing-year-route-screen")
        query_public_selector(pilot, "#filing-year-route-year", Input).value = str(year)
        stage = "mounted_withholding_screen"
        await _activate_button(pilot, "#filing-year-route-open")
        await _wait_for_active_screen(pilot, screen_id="withholding-evidence-screen")
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
    from textual.widgets import Static

    await _populate_capture_form(pilot, invoice_number=invoice_number, kind=kind, year=year, mode=mode)
    await _activate_button(pilot, "#withholding-capture")
    if str(query_public_selector(pilot, "#withholding-status", Static).render()).strip() != "captured":
        raise RetencionesInstalledTuiError(f"installed {kind} capture did not report captured")


async def _assert_professional_required_detail_refusal(pilot: Any, *, invoice_number: str, year: int) -> None:
    """Prove the visible form refuses a missing required Modelo 190 detail."""
    from textual.widgets import Input, Static

    await _populate_capture_form(
        pilot,
        invoice_number=invoice_number,
        kind="professional",
        year=year,
        mode="append",
    )
    query_public_selector(pilot, "#withholding-territorial-deduction", Input).value = ""
    await _activate_button(pilot, "#withholding-capture")
    status = str(query_public_selector(pilot, "#withholding-status", Static).render()).strip()
    if status != "refused: invalid_withholding_evidence":
        raise RetencionesInstalledTuiError(
            "installed professional capture did not refuse missing required annual detail"
        )


async def _populate_capture_form(
    pilot: Any,
    *,
    invoice_number: str,
    kind: Literal["professional", "urban_rent"],
    year: int,
    mode: Literal["append", "replace"],
) -> None:
    """Set one complete public capture form without submitting it."""
    from textual.widgets import Input, Select

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
        return
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
        # The installed root opens on a worker thread; on a loaded machine the
        # shared helper's default admission budget expires before Home appears.
        auto_pilot=admitted_session_autopilot(
            passphrase=passphrase, drive_after_home=observed_drive, polls=_ADMISSION_POLLS
        ),
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
            await _wait_for_selector(pilot, "#field-passphrase")
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
        or document.get("cli_periodic_lifecycle") != []
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
    if rent_reference.modelo_180_property is None:
        raise RetencionesInstalledTuiError("tui_annual_oracle_rent_property_missing")
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
        return frozenset[str]()
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
    readback: _ReplacementReadback | None = None
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
                    "readback": asdict(readback) if readback is not None else None,
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


def _natural_address(*, modelo: str, year: int, period: str) -> str:
    """Render one work address exactly as the installed Declarations screen does."""
    from cadrumo.core.period import Period
    from cadrumo.entrypoints.tui.declarations.controller import natural_address

    return natural_address(modelo, year, Period.from_year_and_code(year, period))


def _address_token(*, modelo: str, year: int, period: str) -> str:
    """Return the value-free receipt token for one Modelo/year/period address."""
    return f"{modelo}|{year}|{period}"


async def _return_home(pilot: Any) -> None:
    """Return to Home through the palette's Home destination; not every workspace binds Back."""
    if not pilot.app.screen.query("#home-agenda"):
        await _open_destination(pilot, query="home", expected_selector="#home-agenda")
    await _wait_for_refreshed_home(pilot)


async def _open_fresh_declarations(pilot: Any, *, expected_selector: str) -> None:
    """Enter Declarations from Home so the screen is built from the latest refreshed generation."""
    await _return_home(pilot)
    await _open_destination(pilot, query="declarations", expected_selector=expected_selector)


async def _submit_declarations_work(
    pilot: Any, *, modelo: str, year: int, period: str
) -> Literal["created", "reused", "refused"]:
    """Select one Modelo/year/period in Declarations and classify the visible outcome."""
    from textual.widgets import Input, Static

    from cadrumo.core.i18n.render import tr

    await _open_fresh_declarations(pilot, expected_selector="#declarations-work-create")
    query_public_selector(pilot, "#declarations-work-modelo", Input).value = modelo
    query_public_selector(pilot, "#declarations-work-year", Input).value = str(year)
    query_public_selector(pilot, "#declarations-work-period", Input).value = period
    await _activate_button(pilot, "#declarations-work-create")
    address = _natural_address(modelo=modelo, year=year, period=period)
    outcomes: dict[str, Literal["created", "reused"]] = {
        tr("tui.declarations.work_create.created", address=address): "created",
        tr("tui.declarations.work_create.reused", address=address): "reused",
    }
    progress = tr("tui.declarations.work_create.progress")
    until = _deadline()
    while time.monotonic() < until:
        await pilot.app.workers.wait_for_complete()
        notice = str(query_public_selector(pilot, "#declarations-work-create-notice", Static).render()).strip()
        if notice and notice != progress:
            return outcomes.get(notice, "refused")
        await _settle(pilot)
    raise RetencionesInstalledTuiError(f"declarations_work_create_did_not_settle:{modelo}|{year}|{period}")


async def _create_declarations_work(pilot: Any, *, modelo: str, year: int, period: str) -> None:
    """Create one work unit through the public Declarations selection and require creation."""
    outcome = await _submit_declarations_work(pilot, modelo=modelo, year=year, period=period)
    if outcome != "created":
        raise RetencionesInstalledTuiError(f"declarations_work_create_{outcome}:{modelo}|{year}|{period}")


async def _open_work_address(pilot: Any, *, modelo: str, year: int, period: str) -> None:
    """Open one declaration by its displayed natural address in a freshly built list."""
    from textual.widgets import DataTable

    await _open_fresh_declarations(pilot, expected_selector="#declarations-list")
    table = query_public_selector(pilot, "#declarations-list", DataTable)
    address = _natural_address(modelo=modelo, year=year, period=period)
    matches = [row_key for row_key in table.rows if str(table.get_row(row_key)[0]) == address]
    if len(matches) != 1:
        raise RetencionesInstalledTuiError(f"declarations_list_rows_{len(matches)}:{modelo}|{year}|{period}")
    await _select_table_row(pilot=pilot, table_selector="#declarations-list", row_key=str(matches[0].value))
    await _wait_for_selector(pilot, "#modelo-lifecycle-calculate")


async def _run_work_operation(
    pilot: Any,
    *,
    modelo: str,
    year: int,
    period: str,
    operation: Literal["calculate", "verify", "file", "export"],
    export_path: Path | None = None,
) -> str:
    """Run one lifecycle control on one addressed declaration and require a succeeded terminal."""
    from textual.widgets import Input, Static

    from dev.acceptance.income_tax.tui_journey import (
        activate_tui_operation,
        installed_lifecycle_contract,
        wait_for_tui_refresh,
    )

    contract = installed_lifecycle_contract(work_create_id="#declarations-work-create")
    binding = {
        "calculate": contract.calculate,
        "verify": contract.verify,
        "file": contract.local_file,
        "export": contract.export,
    }[operation]
    await _open_work_address(pilot, modelo=modelo, year=year, period=period)
    if operation == "export":
        if export_path is None:
            raise RetencionesInstalledTuiError("tui_only_export_requires_a_destination")
        query_public_selector(pilot, "#modelo-lifecycle-export-path", Input).value = str(export_path)
    terminal = await activate_tui_operation(pilot, binding=binding, maximum_polls=20000)
    token = _address_token(modelo=modelo, year=year, period=period)
    if terminal.outcome.value != "proven":
        notice = str(query_public_selector(pilot, "#modelo-lifecycle-notice", Static).render()).strip()
        raise RetencionesInstalledTuiError(
            f"{token}:{binding.operation_id}:{terminal.terminal_condition}:{notice[:240]}"
        )
    if operation == "export":
        if export_path is None or not export_path.is_file() or export_path.stat().st_size == 0:
            raise RetencionesInstalledTuiError(f"{token}:modelo.export:artifact_missing")
    else:
        await wait_for_tui_refresh(pilot, binding=binding, maximum_polls=20000)
    return f"{token}:{binding.operation_id}"


def _tui_only_export_path(scratch: Path, *, modelo: str, year: int, period: str) -> Path:
    """Return the deterministic local export destination the parent validates."""
    return scratch / f"tui-only-modelo-{modelo}-{year}-{period}.boe"


def _artifact_evidence(path: Path, *, modelo: str, period: str) -> WithholdingTuiOnlyArtifactEvidence:
    """Fingerprint one exported artifact without retaining its financial payload."""
    payload = path.read_bytes()
    return WithholdingTuiOnlyArtifactEvidence(
        modelo=modelo,
        period=period,
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )


async def _read_filing_history(pilot: Any) -> tuple[str, ...]:
    """Read the natural addresses of the local filing records Declarations lists."""
    from textual.widgets import DataTable

    await _open_fresh_declarations(pilot, expected_selector="#declarations-navigation")
    await _select_table_row(
        pilot=pilot, table_selector="#declarations-navigation", row_key="declarations.filing_history"
    )
    await _wait_for_selector(pilot, "#declarations-filings")
    table = query_public_selector(pilot, "#declarations-filings", DataTable)
    return tuple(
        sorted(str(table.get_row(row_key)[0]) for row_key in table.rows if str(row_key.value).startswith("filing:"))
    )


async def _read_declaration_addresses(pilot: Any) -> tuple[str, ...]:
    """Read the natural addresses of every declaration the fresh list shows."""
    from textual.widgets import DataTable

    await _open_fresh_declarations(pilot, expected_selector="#declarations-list")
    table = query_public_selector(pilot, "#declarations-list", DataTable)
    return tuple(sorted(str(table.get_row(row_key)[0]) for row_key in table.rows))


def _tui_only_expected_addresses(year: int) -> tuple[str, ...]:
    """Return every declaration address the TUI-only journey must create."""
    return tuple(
        sorted(
            _natural_address(modelo=modelo, year=year, period=period)
            for modelo, period in (*_TUI_ONLY_SOURCE_ADDRESSES, *_TUI_ONLY_ANNUAL_ADDRESSES)
        )
    )


def _tui_only_expected_filings(year: int) -> tuple[str, ...]:
    """Return the addresses whose local filing record the annual returns consume."""
    return tuple(
        sorted(
            _natural_address(modelo=modelo, year=year, period=period) for modelo, period in _TUI_ONLY_SOURCE_ADDRESSES
        )
    )


def run_tui_only_child(
    *, workspace_root: Path, profile_label: str, passphrase: str, year: int, scratch: Path
) -> WithholdingTuiOnlyReceipt:
    """Drive the whole professional/urban-rent filing year through installed TUI controls only."""
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))

    stage = "profile_configuration"
    periodic: list[str] = []
    annual: list[str] = []
    route: list[str] = []
    artifacts: list[WithholdingTuiOnlyArtifactEvidence] = []

    async def drive(pilot: Any) -> None:
        nonlocal stage
        try:
            await _configure_profile(pilot, year=year, no_activity_attestations=True)
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
            stage = "required_detail_refusal"
            await _assert_professional_required_detail_refusal(pilot, invoice_number="RET-PRO-2025-001", year=year)
            stage = "professional_capture"
            await _set_capture(pilot, invoice_number="RET-PRO-2025-001", kind="professional", year=year)
            await _inspect_scope(pilot, modelo="111", expected_entries=2, year=year)
            stage = "urban_rent_capture"
            await _set_capture(pilot, invoice_number="RET-RENT-2025-001", kind="urban_rent", year=year)
            await _inspect_scope(pilot, modelo="115", expected_entries=1, year=year)
            for modelo, period in _TUI_ONLY_SOURCE_ADDRESSES:
                stage = f"work_create:{modelo}|{period}"
                await _create_declarations_work(pilot, modelo=modelo, year=year, period=period)
                route.append(f"created:{_address_token(modelo=modelo, year=year, period=period)}")
            # The same address again must reopen the existing work, never a second unit.
            stage = "work_reuse"
            reused = await _submit_declarations_work(pilot, modelo="111", year=year, period="2T")
            if reused != "reused":
                raise RetencionesInstalledTuiError(f"declarations_work_reuse_{reused}")
            route.append(f"reused:{_address_token(modelo='111', year=year, period='2T')}")
            # Modelo 111 declares no annual period; the application refusal must reach the screen.
            stage = "work_refusal"
            refused = await _submit_declarations_work(pilot, modelo="111", year=year, period="0A")
            if refused != "refused":
                raise RetencionesInstalledTuiError(f"declarations_undeclared_period_{refused}")
            route.append(f"refused:{_address_token(modelo='111', year=year, period='0A')}")
            for modelo, period in _TUI_ONLY_SOURCE_ADDRESSES:
                for operation in ("calculate", "verify"):
                    stage = f"{operation}:{modelo}|{period}"
                    periodic.append(
                        await _run_work_operation(pilot, modelo=modelo, year=year, period=period, operation=operation)
                    )
                if (modelo, period) in _TUI_ONLY_EXPORTED_PERIODIC:
                    stage = f"export:{modelo}|{period}"
                    target = _tui_only_export_path(scratch, modelo=modelo, year=year, period=period)
                    periodic.append(
                        await _run_work_operation(
                            pilot, modelo=modelo, year=year, period=period, operation="export", export_path=target
                        )
                    )
                    artifacts.append(_artifact_evidence(target, modelo=modelo, period=period))
                stage = f"file:{modelo}|{period}"
                periodic.append(
                    await _run_work_operation(pilot, modelo=modelo, year=year, period=period, operation="file")
                )
            for modelo, period in _TUI_ONLY_ANNUAL_ADDRESSES:
                stage = f"work_create:{modelo}|{period}"
                await _create_declarations_work(pilot, modelo=modelo, year=year, period=period)
                route.append(f"created:{_address_token(modelo=modelo, year=year, period=period)}")
                for operation in ("calculate", "verify"):
                    stage = f"{operation}:{modelo}|{period}"
                    annual.append(
                        await _run_work_operation(pilot, modelo=modelo, year=year, period=period, operation=operation)
                    )
                stage = f"export:{modelo}|{period}"
                target = _tui_only_export_path(scratch, modelo=modelo, year=year, period=period)
                annual.append(
                    await _run_work_operation(
                        pilot, modelo=modelo, year=year, period=period, operation="export", export_path=target
                    )
                )
                artifacts.append(_artifact_evidence(target, modelo=modelo, period=period))
        except RetencionesInstalledTuiError as error:
            raise RetencionesInstalledTuiError(f"tui_only_{stage}_failed:{error}") from error
        except InstalledTuiChildError as error:
            raise RetencionesInstalledTuiError(
                f"tui_only_{stage}_failed:{_public_screen_identity(pilot)}:{error}"
            ) from error
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    product = installed_product_evidence(workspace_root=workspace_root)
    return WithholdingTuiOnlyReceipt(
        schema_version=_TUI_ONLY_SCHEMA_VERSION,
        status="proven",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        year=year,
        profile_setup="completed",
        required_detail_refusal="observed",
        work_route=tuple(route),
        periodic_lifecycle=tuple(periodic),
        annual_lifecycle=tuple(annual),
        artifacts=tuple(artifacts),
        fresh_readback=(),
        fresh_filing_history=(),
        historical_profile_context="current_profile_at_run",
        unexercised=_TUI_ONLY_UNEXERCISED,
    )


def run_tui_only_reopen_child(*, workspace_root: Path, passphrase: str, year: int) -> WithholdingTuiOnlyReopenReceipt:
    """Read evidence, declarations and local filing history through a fresh installed process."""
    _admit_cli_created_profile(passphrase=passphrase)
    stage = "withholding_route"
    reopened: tuple[str, ...] = ()
    history: tuple[str, ...] = ()

    async def drive(pilot: Any) -> None:
        nonlocal history, reopened, stage
        try:
            await _open_withholding(pilot, year=year)
            stage = "professional_inspection"
            await _inspect_scope(pilot, modelo="111", expected_entries=2, year=year)
            stage = "urban_rent_inspection"
            await _inspect_scope(pilot, modelo="115", expected_entries=1, year=year)
            stage = "declarations"
            reopened = await _read_declaration_addresses(pilot)
            stage = "filing_history"
            history = await _read_filing_history(pilot)
        except RetencionesInstalledTuiError as error:
            raise RetencionesInstalledTuiError(f"tui_only_reopen_{stage}_failed:{error}") from error
        except InstalledTuiChildError as error:
            raise RetencionesInstalledTuiError(
                f"tui_only_reopen_{stage}_failed:{_public_screen_identity(pilot)}"
            ) from error
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    product = installed_product_evidence(workspace_root=workspace_root)
    return WithholdingTuiOnlyReopenReceipt(
        schema_version=_TUI_ONLY_SCHEMA_VERSION,
        status="proven",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        year=year,
        reopened_work=reopened,
        filing_history=history,
    )


def _string_tuple(value: object, *, label: str) -> tuple[str, ...]:
    """Require a JSON list of strings from a child receipt."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RetencionesInstalledTuiError(f"tui_only_receipt_{label}_invalid")
    return tuple(cast(list[str], value))


def _tui_only_receipt(document: dict[str, object], *, year: int) -> WithholdingTuiOnlyReceipt:
    """Validate the TUI-only child's public shape before trusting any of it."""
    expected = {
        "schema_version": _TUI_ONLY_SCHEMA_VERSION,
        "status": "proven",
        "year": year,
        "profile_setup": "completed",
        "required_detail_refusal": "observed",
        "historical_profile_context": "current_profile_at_run",
    }
    if any(document.get(key) != value for key, value in expected.items()):
        raise RetencionesInstalledTuiError("tui_only_child_did_not_prove_the_expected_journey")
    origin = document.get("product_origin")
    initializer = document.get("product_init_sha256")
    if not isinstance(origin, str) or not origin or not isinstance(initializer, str) or len(initializer) != 64:
        raise RetencionesInstalledTuiError("tui_only_child_product_identity_invalid")
    raw_artifacts = document.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise RetencionesInstalledTuiError("tui_only_receipt_artifacts_invalid")
    artifacts: list[WithholdingTuiOnlyArtifactEvidence] = []
    for raw in cast(list[object], raw_artifacts):
        if not isinstance(raw, dict):
            raise RetencionesInstalledTuiError("tui_only_receipt_artifacts_invalid")
        item = cast(dict[str, object], raw)
        modelo, period, digest, size = item.get("modelo"), item.get("period"), item.get("sha256"), item.get("size")
        if (
            not isinstance(modelo, str)
            or not isinstance(period, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size <= 0
        ):
            raise RetencionesInstalledTuiError("tui_only_receipt_artifacts_invalid")
        artifacts.append(WithholdingTuiOnlyArtifactEvidence(modelo=modelo, period=period, sha256=digest, size=size))
    exported = tuple((artifact.modelo, artifact.period) for artifact in artifacts)
    if exported != (*_TUI_ONLY_EXPORTED_PERIODIC, *_TUI_ONLY_ANNUAL_ADDRESSES):
        raise RetencionesInstalledTuiError("tui_only_receipt_artifact_set_mismatch")
    route = _string_tuple(document.get("work_route"), label="work_route")
    expected_route = (
        *(f"created:{_address_token(modelo=m, year=year, period=p)}" for m, p in _TUI_ONLY_SOURCE_ADDRESSES),
        f"reused:{_address_token(modelo='111', year=year, period='2T')}",
        f"refused:{_address_token(modelo='111', year=year, period='0A')}",
        *(f"created:{_address_token(modelo=m, year=year, period=p)}" for m, p in _TUI_ONLY_ANNUAL_ADDRESSES),
    )
    if route != expected_route:
        raise RetencionesInstalledTuiError("tui_only_receipt_work_route_mismatch")
    periodic = _string_tuple(document.get("periodic_lifecycle"), label="periodic_lifecycle")
    annual = _string_tuple(document.get("annual_lifecycle"), label="annual_lifecycle")
    if len(periodic) != 3 * len(_TUI_ONLY_SOURCE_ADDRESSES) + len(_TUI_ONLY_EXPORTED_PERIODIC):
        raise RetencionesInstalledTuiError("tui_only_receipt_periodic_lifecycle_incomplete")
    if len(annual) != 3 * len(_TUI_ONLY_ANNUAL_ADDRESSES):
        raise RetencionesInstalledTuiError("tui_only_receipt_annual_lifecycle_incomplete")
    if _string_tuple(document.get("unexercised"), label="unexercised") != _TUI_ONLY_UNEXERCISED:
        raise RetencionesInstalledTuiError("tui_only_receipt_unexercised_mismatch")
    return WithholdingTuiOnlyReceipt(
        schema_version=_TUI_ONLY_SCHEMA_VERSION,
        status="proven",
        product_origin=origin,
        product_init_sha256=initializer,
        year=year,
        profile_setup="completed",
        required_detail_refusal="observed",
        work_route=route,
        periodic_lifecycle=periodic,
        annual_lifecycle=annual,
        artifacts=tuple(artifacts),
        fresh_readback=(),
        fresh_filing_history=(),
        historical_profile_context="current_profile_at_run",
        unexercised=_TUI_ONLY_UNEXERCISED,
    )


def _tui_only_reopen_receipt(document: dict[str, object], *, year: int) -> WithholdingTuiOnlyReopenReceipt:
    """Validate the fresh-process readback against the addresses the journey created."""
    if any(
        document.get(key) != value
        for key, value in {"schema_version": _TUI_ONLY_SCHEMA_VERSION, "status": "proven", "year": year}.items()
    ):
        raise RetencionesInstalledTuiError("tui_only_reopen_did_not_prove_the_expected_readback")
    origin = document.get("product_origin")
    initializer = document.get("product_init_sha256")
    if not isinstance(origin, str) or not origin or not isinstance(initializer, str) or len(initializer) != 64:
        raise RetencionesInstalledTuiError("tui_only_reopen_product_identity_invalid")
    reopened = _string_tuple(document.get("reopened_work"), label="reopened_work")
    history = _string_tuple(document.get("filing_history"), label="filing_history")
    if reopened != _tui_only_expected_addresses(year):
        raise RetencionesInstalledTuiError("tui_only_reopen_declarations_mismatch")
    if history != _tui_only_expected_filings(year):
        raise RetencionesInstalledTuiError("tui_only_reopen_filing_history_mismatch")
    return WithholdingTuiOnlyReopenReceipt(
        schema_version=_TUI_ONLY_SCHEMA_VERSION,
        status="proven",
        product_origin=origin,
        product_init_sha256=initializer,
        year=year,
        reopened_work=reopened,
        filing_history=history,
    )


def _validate_tui_only_exports(
    *, receipt: WithholdingTuiOnlyReceipt, scratch: Path, authority_root: Path, year: int
) -> str:
    """Check every TUI export against the official layout and the independent oracle.

    Returns the authority logical generation the layouts were selected from.
    """
    from dev.acceptance.retenciones.cli_journey import (
        _selected_annual_layouts,
        _selected_layouts,
        _validate_annual_export,
        _validate_export,
    )
    from dev.acceptance.retenciones.scenario import build_installed_periodic_cli_slices

    payloads: dict[tuple[str, str], bytes] = {}
    for artifact in receipt.artifacts:
        payload = _tui_only_export_path(scratch, modelo=artifact.modelo, year=year, period=artifact.period).read_bytes()
        if hashlib.sha256(payload).hexdigest() != artifact.sha256 or len(payload) != artifact.size:
            raise RetencionesInstalledTuiError(f"tui_only_artifact_changed_after_export:{artifact.modelo}")
        payloads[(artifact.modelo, artifact.period)] = payload
    periodic_slices = build_installed_periodic_cli_slices(year)
    annual_slices = _tui_captured_annual_slices(year)
    periodic_generation, periodic_layouts = _selected_layouts(
        authority_root=authority_root, slices=periodic_slices, year=year
    )
    annual_generation, annual_layouts = _selected_annual_layouts(
        authority_root=authority_root, slices=annual_slices, year=year
    )
    if periodic_generation != annual_generation:
        raise RetencionesInstalledTuiError("tui_only_layout_generations_differ")
    for artifact in receipt.artifacts:
        payload = payloads[(artifact.modelo, artifact.period)]
        stage = f"tui_only_{artifact.modelo}_{artifact.period}_export"
        periodic_slice = next((slice_ for slice_ in periodic_slices if slice_.modelo == artifact.modelo), None)
        if periodic_slice is not None:
            _validate_export(
                layout=periodic_layouts[periodic_slice.slice_id],
                payload=payload,
                expected=periodic_slice.expected_casillas,
                stage=stage,
            )
            continue
        annual_slice = next(slice_ for slice_ in annual_slices if slice_.modelo == artifact.modelo)
        _validate_annual_export(
            layout=annual_layouts[annual_slice.slice_id],
            payload=payload,
            expected_header=annual_slice.expected_header_fields,
            expected_type2_rows=annual_slice.expected_type2_rows,
            stage=stage,
        )
    return str(periodic_generation)


def run_tui_only_validation_child(
    *, journey_receipt: Path, scratch: Path, year: int
) -> WithholdingTuiOnlyExportValidation:
    """Validate the journey's exports inside the installed interpreter.

    The served authority's store format belongs to the installed product, so
    only its own reader is guaranteed to open it; a development tree may
    already read a newer format. The layouts come from the authority the
    journey itself served, named by ``CADRUMO_AUTHORITY_ROOT``.
    """
    import os

    authority_root = os.environ.get("CADRUMO_AUTHORITY_ROOT")
    if not authority_root:
        raise RetencionesInstalledTuiError("tui_only_validation_requires_the_served_authority_root")
    journey = _tui_only_receipt(_child_document(journey_receipt), year=year)
    generation = _validate_tui_only_exports(
        receipt=journey, scratch=scratch, authority_root=Path(authority_root), year=year
    )
    return WithholdingTuiOnlyExportValidation(
        schema_version=_TUI_ONLY_SCHEMA_VERSION,
        status="proven",
        authority_generation=generation,
        artifacts=journey.artifacts,
    )


def _tui_only_validation(document: dict[str, object], *, journey: WithholdingTuiOnlyReceipt) -> str:
    """Require a proven validation of exactly the journey's artifacts; return its generation."""
    generation = document.get("authority_generation")
    artifacts = document.get("artifacts")
    if (
        document.get("schema_version") != _TUI_ONLY_SCHEMA_VERSION
        or document.get("status") != "proven"
        or not isinstance(generation, str)
        or len(generation) != 64
        or not isinstance(artifacts, list)
        or artifacts != [asdict(artifact) for artifact in journey.artifacts]
    ):
        raise RetencionesInstalledTuiError("tui_only_export_validation_not_proven_for_the_journey_artifacts")
    return generation


def _child_failure(path: Path) -> str:
    """Return the failure a child recorded in its receipt, for the parent's refusal."""
    try:
        error = _child_document(path).get("error")
    except RetencionesInstalledTuiError as unreadable:
        return str(unreadable)
    return error if isinstance(error, str) else "no recorded failure"


def run_installed_tui_only_journey(
    *,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int = _YEAR,
) -> WithholdingTuiOnlyReceipt:
    """Prove the professional/urban-rent filing year through installed TUI processes only.

    The parent never runs a product command. It launches two installed TUI
    children over one fresh encrypted store, then checks the exported bytes
    against the official layouts and the independent oracle.
    """
    root = _require_empty_directory(output_root, label="RETENCIONES TUI-only output root")
    workspace = workspace_root.resolve(strict=True)
    authority = authority_root.resolve(strict=True)
    store = _require_empty_directory(root / "secure-store", label="RETENCIONES TUI-only secure store")
    scratch = _require_empty_directory(root / "transient", label="RETENCIONES TUI-only transient directory")
    passphrase = secrets.token_urlsafe(32)
    common = {
        "python_executable": python_executable.resolve(strict=True),
        "workspace_root": workspace,
        "child_module": "dev.acceptance.retenciones.installed_tui_withholding",
        "storage_root": store,
        "authority_root": authority,
        "passphrase": passphrase,
        "timeout_seconds": 5400,
    }
    journey_path = root / "tui-only.json"
    journey_child = run_installed_tui_child_process(
        **common,
        child_args=(
            "--child-mode",
            "tui-only",
            "--workspace-root",
            str(workspace),
            "--year",
            str(year),
            "--scratch",
            str(scratch),
            "--receipt",
            str(journey_path),
        ),
        receipt_path=journey_path,
    )
    if journey_child.returncode != 0:
        raise RetencionesInstalledTuiError(f"installed TUI-only journey child failed:{_child_failure(journey_path)}")
    journey = _tui_only_receipt(_child_document(journey_path), year=year)
    validation_path = root / "export-validation.json"
    validation_child = run_installed_tui_child_process(
        **common,
        child_args=(
            "--child-mode",
            "tui-only-validate",
            "--workspace-root",
            str(workspace),
            "--year",
            str(year),
            "--scratch",
            str(scratch),
            "--journey-receipt",
            str(journey_path),
            "--receipt",
            str(validation_path),
        ),
        receipt_path=validation_path,
    )
    if validation_child.returncode != 0:
        raise RetencionesInstalledTuiError(
            f"installed TUI-only exports failed independent validation:{_child_failure(validation_path)}"
        )
    _tui_only_validation(_child_document(validation_path), journey=journey)
    reopen_path = root / "reopen.json"
    reopen_child = run_installed_tui_child_process(
        **common,
        child_args=(
            "--child-mode",
            "tui-only-reopen",
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
    if reopen_child.returncode != 0:
        raise RetencionesInstalledTuiError(f"installed TUI-only reopen child failed:{_child_failure(reopen_path)}")
    reopened = _tui_only_reopen_receipt(_child_document(reopen_path), year=year)
    if (journey.product_origin, journey.product_init_sha256) != (reopened.product_origin, reopened.product_init_sha256):
        raise RetencionesInstalledTuiError("installed TUI-only processes did not identify the same product")
    return replace(
        journey,
        fresh_readback=("modelo-111", "modelo-115"),
        fresh_filing_history=reopened.filing_history,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--child-mode",
        choices=("capture", "mutate", "reopen", "tui-only", "tui-only-reopen", "tui-only-validate"),
        required=True,
    )
    parser.add_argument("--journey-receipt", type=Path)
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
        receipt: (
            WithholdingJourneyReceipt
            | WithholdingTuiOnlyReceipt
            | WithholdingTuiOnlyReopenReceipt
            | WithholdingTuiOnlyExportValidation
        )
        if args.child_mode == "tui-only-validate":
            if args.journey_receipt is None:
                raise RetencionesInstalledTuiError("tui_only_validation_requires_the_journey_receipt")
            receipt = run_tui_only_validation_child(
                journey_receipt=args.journey_receipt, scratch=args.scratch.resolve(strict=True), year=args.year
            )
        elif args.child_mode == "tui-only":
            receipt = run_tui_only_child(
                workspace_root=args.workspace_root,
                profile_label=args.profile_label,
                passphrase=passphrase,
                year=args.year,
                scratch=args.scratch.resolve(strict=True),
            )
        elif args.child_mode == "tui-only-reopen":
            receipt = run_tui_only_reopen_child(
                workspace_root=args.workspace_root, passphrase=passphrase, year=args.year
            )
        elif args.child_mode == "capture":
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
    except Exception as error:
        # The parent discards the child's stderr, so an unexpected failure
        # must still leave a receipt naming it, or the run has no evidence.
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(
                f"installed withholding journey crashed: {type(error).__name__}: {str(error)[:600]}"
            ),
        )
        return 3
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - installed child entry point
    raise SystemExit(main())
