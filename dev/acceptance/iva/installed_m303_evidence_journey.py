"""Installed-wheel proof of ordinary Modelo 303 filing evidence through the TUI.

DP30301 asks the joint-return election in every period and the Modelo 390
exemption only in the last settlement period of the year (4T, or 12 for a
monthly filer), so only those periods carry a secure attestation.  Four isolated
synthetic stores exercise the one ``modelo.work.calculate`` operation from an
installed wheel, all in the one filing year given by ``--year``:

* ``tui_led`` (4T): the installed CLI captures the ledger and creates the
  work unit.  Installed CLI and TUI refusals come first (no answers, no
  attestation, mismatched attachment pair, another period's attestation) and
  must leave no revision.  The TUI then admits a new attestation from an
  explicit observation instant, calculates and verifies.  A fresh TUI process
  must list that revision as current and verified; the installed CLI reads its
  values.
* ``continuation`` (4T): the installed CLI attests and hands the attachment
  pair to the TUI, which calculates (CLI to TUI).  The installed CLI then
  recalculates with the same answers; revision identity is content-addressed
  over the typed filing evidence, so the same revision id proves equivalent
  persisted evidence.  The CLI verifies (TUI to CLI) and a fresh TUI process
  reads the verified revision.  A changed joint-return answer must produce a
  different revision id.
* ``monthly`` (12): a REDEME-registered profile, which settles monthly;
  the installed CLI attests the last month, calculates and verifies, and a
  fresh TUI process lists the verified revision.
* ``first_quarter`` (1T): the installed CLI refuses attestation flags the
  period does not ask for; the TUI form offers only the joint-return question,
  calculates and verifies without any attestation.

Each fresh TUI process also opens the declaration's workbench.  Its
``iva.resultado`` casilla must read as calculated and equal the independent
oracle; a casilla the workbench does not show, or shows with any other origin,
fails the readback.

Receipts carry identities, outcomes and oracle verdicts only: no passphrase,
amount or synthetic document content.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admit_installed_session,
    installed_product_evidence,
    public_surface_diagnostic,
    query_public_selector,
    read_passphrase_from_stdin,
    run_installed_tui_child_process,
    select_public_data_table_row,
    write_installed_tui_failure_receipt,
)
from dev.acceptance.income_tax.tui_journey import (
    WORKBENCH_AT_RISK_PROCEED,
    WORKBENCH_LIST,
    WORKBENCH_NOTICE,
    TuiJourneyError,
    TuiOperationBinding,
    TuiTerminalEvidence,
    acknowledge_export_result,
    activate_tui_operation,
    confirm_assumed_values,
    installed_lifecycle_contract,
    open_workbench_export,
    wait_for_tui_refresh,
    wait_for_workbench,
)
from dev.acceptance.installed_cli import InstalledCli, InstalledCliError
from dev.packaging.installed_wheel_binding import environment_interpreter

from .filing_year import IvaJourneyYear, require_journey_year, require_m303_developer_header_positions

if TYPE_CHECKING:
    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen

_SCHEMA_VERSION: Final = "iva-01-installed-m303-evidence-journey-v2"
_CHILD_MODULE: Final = "dev.acceptance.iva.installed_m303_evidence_journey"
_PERIOD: Final = "4T"
_PRIOR_PERIOD: Final = "3T"
_WRONG_PERIOD: Final = "12"
_MONTH: Final = "12"
_PRIOR_MONTH: Final = "11"
_FIRST_QUARTER: Final = "1T"
_COORDINATES: Final = tuple(
    ("303", period) for period in (_PERIOD, _PRIOR_PERIOD, _MONTH, _PRIOR_MONTH, _FIRST_QUARTER)
)
_ORACLE_RESULTADO: Final = Decimal("21.00") - Decimal("10.50")
_RESULTADO_CASILLA: Final = "iva.resultado"
_OUTSIDE_LAST_PERIOD: Final = "exonerado_390_attestation_outside_last_period"
# Month and day of the sale and purchase inside each scenario's period.
_LAST_PERIOD_DAYS: Final = ((12, 15), (12, 18))
_FIRST_QUARTER_DAYS: Final = ((2, 15), (2, 18))
_MISMATCHED_ATTACHMENT_ID: Final = "a" * 64
_MISMATCHED_SHA256: Final = "b" * 64
_DEVELOPMENT_MOCK_HEADER: Final = {"program": b"0000", "developer": b"00000000T"}
_EVIDENCE_SUBMIT_ID: Final = "#m303-evidence-submit"
_ATTESTATION_REFUSAL_KEY: Final = "errors.refused.refused_modelo_m303_exonerado_390_attestation_unadmissible"

type ChildMode = Literal["tui-led-calculate", "tui-continue-calculate", "tui-joint-only-calculate", "tui-reopen"]


class IvaInstalledM303Error(RuntimeError):
    """The installed evidence journey could not prove a required outcome."""


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """One fresh installed CLI process, reduced to its public outcome."""

    command: str
    returncode: int
    status: str
    error_code: str | None


@dataclass(frozen=True, slots=True)
class TuiOutcome:
    """One installed TUI interaction, reduced to its public outcome."""

    step: str
    terminal_condition: str
    visible_notice_key: str | None


@dataclass(frozen=True, slots=True)
class ReopenReadback:
    """What a fresh installed TUI session shows for the calculated declaration.

    ``resultado_origin`` is the origin the workbench gives the ``iva.resultado``
    casilla (``None`` when it shows no such casilla), and
    ``resultado_matches_oracle`` whether the value it holds equals the oracle.
    """

    revision_listed_current: bool
    revision_state: str | None
    resultado_origin: str | None
    resultado_matches_oracle: bool


@dataclass(frozen=True, slots=True)
class ChildReceipt:
    """Value-free result of one installed TUI child process."""

    schema_version: str
    status: Literal["proven"]
    mode: str
    product_origin: str
    product_init_sha256: str
    outcomes: tuple[TuiOutcome, ...]
    reopen: ReopenReadback | None

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe receipt."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class ChildHandle:
    """Value-free handle for one installed TUI child process."""

    mode: str
    returncode: int
    receipt_status: str
    receipt_sha256: str
    stdout_sha256: str
    stderr_sha256: str


@dataclass(frozen=True, slots=True)
class StoreEvidence:
    """Outcome of one isolated synthetic store."""

    scenario: Literal["tui_led", "continuation", "monthly", "first_quarter"]
    work_unit_id: str
    calculation_revision_id: str
    revision_count: int
    cli_resultado_matches_oracle: bool
    cli_revision_verified: bool
    cli_recalculated_same_revision: bool | None
    changed_evidence_produced_distinct_revision: bool | None
    tui_reopen: ReopenReadback
    commands: tuple[CommandOutcome, ...]
    children: tuple[ChildHandle, ...]
    child_outcomes: tuple[TuiOutcome, ...]


@dataclass(frozen=True, slots=True)
class JourneyReceipt:
    """Sanitized installed evidence for the ordinary M303 evidence contract."""

    schema_version: str
    status: Literal["proven"]
    filing_year: int
    periods: tuple[str, ...]
    source_commit: str
    wheel_filename: str
    wheel_sha256: str
    package_version: str
    installed_init_path: str
    installed_init_sha256: str
    authority_generation: str
    authority_descriptor_sha256: str
    bundled_authority_generation: str
    stores: tuple[StoreEvidence, ...]
    unexercised: tuple[str, ...]
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe receipt."""
        return cast(dict[str, object], asdict(self))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise IvaInstalledM303Error(f"{label} returned no object")
    return cast(Mapping[str, object], value)


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise IvaInstalledM303Error(f"{label} returned no text")
    return value


def _year_end_observed_at(year: int) -> str:
    """The attestation observation instant: noon UTC on the last day of the filing year."""
    return f"{year}-12-31T12:00:00+00:00"


def resultado_matches_oracle(raw: object) -> bool:
    """Compare one public ``iva.resultado`` rendering with the independent 21.00 - 10.50 oracle."""
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01")) == _ORACLE_RESULTADO
    except (InvalidOperation, ValueError):
        return False


class _Cli:
    """Installed CLI calls that retain only public outcomes."""

    def __init__(self, cli: InstalledCli) -> None:
        self.cli = cli
        self.outcomes: list[CommandOutcome] = []

    def run(self, args: tuple[str, ...], *, expect_refusal: bool = False) -> Mapping[str, object]:
        document = self.cli.run(args, allow_error=True)
        evidence = self.cli.commands[-1]
        error = document.get("error")
        code = cast("Mapping[str, object]", error).get("code") if isinstance(error, Mapping) else None
        self.outcomes.append(
            CommandOutcome(
                command=evidence.command,
                returncode=evidence.returncode,
                status=evidence.status,
                error_code=code if isinstance(code, str) else None,
            )
        )
        if expect_refusal:
            if evidence.returncode == 0:
                raise IvaInstalledM303Error(f"installed CLI accepted a request it must refuse: {evidence.command}")
            return document
        if evidence.returncode != 0:
            raise IvaInstalledM303Error(f"installed CLI refused {evidence.command}: {code}")
        return _mapping(document.get("result"), label=evidence.command)


def _cli_capture_and_create_work(
    cli: _Cli, *, artifact: Path, year: int, period: str, wallet_period: str, dates: tuple[str, str]
) -> str:
    """Capture one ordinary ``year`` sale and purchase inside ``period`` and create its M303 work unit."""
    sale_date, purchase_date = dates
    evidence_id = _text(
        cli.run(("app", "ledger", "evidence", "add", str(artifact), "--supplier", "Synthetic supplier SL")).get(
            "evidence_id"
        ),
        label="evidence add",
    )
    sale = _text(
        cli.run(
            (
                *("app", "ledger", "add", "--date", sale_date, "--amount", "121.00", "--direction", "INCOMING"),
                *("--description", "Synthetic ordinary IVA sale", "--classification", "BUSINESS"),
                *("--taxable-base", "100.00", "--iva-rate", "0.21", "--iva-amount", "21.00"),
                *("--iva-category", "domestic_general", "--source-jurisdiction", "ES"),
                *("--idempotency-key", f"iva-m303-evidence-sale-{year}-{period.lower()}"),
            )
        ).get("transaction_id"),
        label="sale add",
    )
    sale_invoice = _text(
        cli.run(
            _invoice_args(kind="issued", number="IVA-M303-ISS", subtotal="100.00", iva_amount="21.00", date=sale_date)
        ).get("invoice_id"),
        label="sale invoice add",
    )
    cli.run(("app", "ledger", "link", sale, "--invoice-id", sale_invoice))
    purchase = _text(
        cli.run(
            (
                *("app", "ledger", "add", "--date", purchase_date, "--amount", "60.50", "--direction", "OUTGOING"),
                *("--description", "Synthetic ordinary IVA purchase", "--classification", "BUSINESS"),
                *("--category-id", "material_oficina", "--taxable-base", "50.00", "--iva-rate", "0.21"),
                *("--iva-amount", "10.50", "--iva-category", "domestic_general"),
                *("--purchase-invoice-evidence-id", evidence_id, "--source-jurisdiction", "ES"),
                *("--idempotency-key", f"iva-m303-evidence-purchase-{year}-{period.lower()}"),
            )
        ).get("transaction_id"),
        label="purchase add",
    )
    cli.run(
        (
            *("app", "ledger", "classify", purchase, "--classification", "BUSINESS"),
            *("--deduction-kind", "domestic_current", "--counterparty-country", "ES", "--reaffirm"),
        )
    )
    purchase_invoice = _text(
        cli.run(
            _invoice_args(kind="received", number="IVA-M303-REC", subtotal="50.00", iva_amount="10.50", date=sale_date)
        ).get("invoice_id"),
        label="purchase invoice add",
    )
    cli.run(("app", "ledger", "link", purchase, "--invoice-id", purchase_invoice))
    cli.run(
        (
            *("app", "modelo", "iva-wallet", "seed", "--filing-year", str(year), "--period", wallet_period),
            *("--amount", "0.00", "--confirm"),
        )
    )
    created = cli.run(("app", "modelo", "work", "create", "--modelo", "303", "--year", str(year), "--period", period))
    return _text(created.get("work_unit_id"), label="work create")


def _invoice_args(*, kind: str, number: str, subtotal: str, iva_amount: str, date: str) -> tuple[str, ...]:
    line = json.dumps(
        {
            "description": f"Synthetic {kind} line",
            "quantity": "1",
            "unit_price": subtotal,
            "subtotal": subtotal,
            "iva_rate": "RATE_21",
            "iva_amount": iva_amount,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        *("app", "ledger", "invoice", "add", "--kind", kind, "--counterparty-name", "Synthetic party SL"),
        *("--counterparty-nif", "A58818501", "--invoice-number", number, "--invoice-date", date),
        *("--country-code", "ES", "--iva-category", "domestic_general", "--line", line),
    )


def _attest(cli: _Cli, *, year: int, period: str, observed_at: str) -> tuple[str, str]:
    attested = cli.run(
        (
            *("app", "modelo", "work", "attest-m303-exonerado-390", "--year", str(year)),
            *("--period", period, "--observed-at", observed_at),
        )
    )
    return _text(attested.get("attachment_id"), label="attest"), _text(attested.get("sha256"), label="attest")


def _calculate_args(
    work_unit_id: str, *, attestation: tuple[str, str] | None, joint_return_elected: bool = False
) -> tuple[str, ...]:
    """Answer the joint-return question, and supply the attestation pair only when given."""
    return (
        *("app", "modelo", "work", "calculate", work_unit_id),
        "--joint-return-elected" if joint_return_elected else "--no-joint-return-elected",
        *(
            ()
            if attestation is None
            else ("--m303-exonerado-390-attachment-id", attestation[0], "--m303-exonerado-390-sha256", attestation[1])
        ),
    )


def _revision_ids(cli: _Cli, work_unit_id: str) -> tuple[str, ...]:
    listed = cli.run(("app", "modelo", "work", "revisions", work_unit_id))
    rows = listed.get("revisions")
    if not isinstance(rows, list):
        raise IvaInstalledM303Error("installed revisions listing returned no rows")
    return tuple(
        _text(_mapping(row, label="revision row").get("calculation_revision_id"), label="revision row")
        for row in cast(list[object], rows)
    )


def _read_revision(cli: _Cli, revision_id: str) -> tuple[bool, bool]:
    """Return (resultado matches oracle, revision verified) from the public revision readback."""
    revision = cli.run(("app", "modelo", "work", "revision", revision_id))
    casillas = _mapping(revision.get("casilla_values"), label="revision casillas")
    return resultado_matches_oracle(casillas.get("iva.resultado")), revision.get("verified_at") is not None


# --------------------------------------------------------------------------- installed TUI child


async def _await_selector(pilot: Any, selector: str, *, seconds: float = 120.0) -> None:
    """Wait on wall-clock time, not a poll count: installed composition speed varies between runs."""
    import time

    from textual.css.query import NoMatches

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            pilot.app.screen.query_one(selector)
        except NoMatches:
            await pilot.pause(0.2)
        else:
            return
    raise InstalledTuiChildError(
        f"installed TUI did not expose {selector} within {seconds:.0f}s", diagnostic=public_surface_diagnostic(pilot)
    )


async def _open_declarations(pilot: Any) -> None:
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    label = tr("tui.search.destination.declarations")
    await pilot.press("ctrl+p")
    for _ in range(180):
        await pilot.pause()
        try:
            search = pilot.app.screen.query_one(Input)
            results = pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        search.value = "declarations"
        for _ in range(180):
            await pilot.pause()
            for index in range(results.option_count):
                if getattr(getattr(results.get_option_at_index(index), "hit", None), "text", None) == label:
                    results.highlighted = index
                    await pilot.press("enter")
                    await _await_selector(pilot, "#declarations-list")
                    return
        break
    raise InstalledTuiChildError(
        "installed command palette did not offer Declarations", diagnostic=public_surface_diagnostic(pilot)
    )


async def _close_modals(pilot: Any) -> None:
    from cadrumo.entrypoints.tui.operations.modal import OperationModal

    for _ in range(60):
        if not isinstance(pilot.app.screen, OperationModal):
            return
        await pilot.press("escape")
        await pilot.pause()
    raise InstalledTuiChildError("installed operation modal did not close after its terminal result")


async def _await_workbench_refresh(pilot: Any, *, binding: TuiOperationBinding) -> None:
    """After a succeeded write, wait for the workbench to come back on top and read the declaration again."""
    await _close_modals(pilot)
    try:
        await wait_for_tui_refresh(pilot, binding=binding, maximum_polls=6000)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(str(error), diagnostic=public_surface_diagnostic(pilot)) from error


async def _open_work(pilot: Any, *, work_unit_id: str) -> ModeloWorkbenchScreen:
    """Open the selected declaration in a fresh workbench, whose notice starts empty, once it has read its form."""
    await _close_modals(pilot)
    await _open_declarations(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#declarations-list", row_key=work_unit_id)
    try:
        return await wait_for_workbench(pilot, seconds=300)
    except TuiJourneyError as error:
        exception = getattr(pilot.app, "_exception", None)
        raise InstalledTuiChildError(
            f"installed declaration workbench did not open: {error} "
            f"app_exception={type(exception).__name__ if exception else None}:{exception!s:.300}",
            diagnostic=public_surface_diagnostic(pilot),
        ) from error


async def _open_evidence_form(pilot: Any, *, work_unit_id: str) -> None:
    """Calculate from the workbench, which first asks the Modelo 303 filing evidence.

    The workbench may ask, before recalculating, to confirm a declaration last
    calculated elsewhere; that confirmation is accepted only while it is the
    top screen.
    """
    import time

    from textual.css.query import NoMatches

    await _open_work(pilot, work_unit_id=work_unit_id)
    await pilot.press("c")
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        screen = pilot.app.screen
        if screen.query(_EVIDENCE_SUBMIT_ID):
            return
        try:
            proceed = screen.query_one(WORKBENCH_AT_RISK_PROCEED)
        except NoMatches:
            pass
        else:
            proceed.focus()
            await pilot.press("enter")
        await pilot.pause(0.2)
    raise InstalledTuiChildError(
        f"installed workbench did not ask the Modelo 303 filing evidence: {_visible_refusal(pilot)}",
        diagnostic=public_surface_diagnostic(pilot),
    )


def _fill_evidence_form(
    pilot: Any,
    *,
    attachment_id: str = "",
    sha256: str = "",
    observed_at: str = "",
    answer: bool = True,
    asks_modelo_390: bool = True,
) -> None:
    from textual.widgets import Input, Select

    if answer:
        cast(Any, query_public_selector(pilot, "#m303-evidence-joint-return-elected", Select)).value = "false"
    if not asks_modelo_390:
        return
    query_public_selector(pilot, "#m303-evidence-attachment-id", Input).value = attachment_id
    query_public_selector(pilot, "#m303-evidence-sha256", Input).value = sha256
    query_public_selector(pilot, "#m303-evidence-observed-at", Input).value = observed_at


def _rendered(widget: object) -> str:
    render = getattr(widget, "render", None)
    return str(render()).strip() if callable(render) else ""


def _notice_key(pilot: Any, selector: str, candidates: Sequence[str]) -> str | None:
    """Name the catalogue key whose rendering is the visible notice, never the text itself."""
    from textual.widgets import Static

    from cadrumo.core.i18n.render import tr

    text = _rendered(query_public_selector(pilot, selector, Static))
    return next((key for key in candidates if tr(key) == text), None if not text else "unrecognised")


_EVIDENCE_SUBMIT: Final = TuiOperationBinding(
    "modelo.work.calculate",
    activation_id=_EVIDENCE_SUBMIT_ID,
    at_risk_proceed_id=WORKBENCH_AT_RISK_PROCEED,
    terminal_result_id="#operation-modal-status",
    refresh_result_id=WORKBENCH_LIST,
    refusal_notice_id=WORKBENCH_NOTICE,
)


async def _settle_expected_refusal(pilot: Any, *, activation_id: str, step: str, refusal_key: str) -> TuiOutcome:
    """Drive one operation the product must refuse and read the refusal where the product leaves it.

    The operation modal dismisses itself as soon as the operation is terminal, so
    a refusal settled after Apply is observed on the workbench notice: the
    sentence saying the operation did not complete, followed by the registry's
    public explanation.
    """
    import time

    from textual.css.query import NoMatches
    from textual.widgets import Button, Static

    from cadrumo.core.i18n.render import tr
    from cadrumo.entrypoints.tui.operations.modal import OperationModal

    not_done = tr("tui.modelo.workbench.operation.not_done")
    query_public_selector(pilot, activation_id, Button).focus()
    await pilot.press("enter")
    applied = False
    modal_seen = False
    notice = ""
    deadline = time.monotonic() + 300.0
    while time.monotonic() < deadline:
        screen = pilot.app.screen
        if isinstance(screen, OperationModal):
            modal_seen = True
            if not applied:
                try:
                    apply = screen.query_one("#btn-operation-apply", Button)
                except NoMatches:
                    apply = None
                if apply is not None and not apply.disabled:
                    apply.focus()
                    await pilot.press("enter")
                    applied = True
        else:
            try:
                notice = _rendered(screen.query_one(WORKBENCH_NOTICE, Static))
            except NoMatches:
                notice = ""
            if notice:
                break
        await pilot.pause(0.2)
    if not notice:
        # Which screen held which notice, and whether the modal was ever seen,
        # separates "the operation never started" from "its notice landed on a
        # screen below the top one" -- the two causes need opposite fixes.
        stack: list[str] = []
        for layer in pilot.app.screen_stack:
            try:
                layer_notice = _rendered(layer.query_one(WORKBENCH_NOTICE, Static))
            except NoMatches:
                layer_notice = None
            stack.append(f"{type(layer).__name__}:{layer_notice!r}")
        raise InstalledTuiChildError(
            f"installed TUI {step} left no workbench notice (modal_seen={modal_seen}, applied={applied}, "
            f"stack={stack})",
            diagnostic=public_surface_diagnostic(pilot),
        )
    if notice != f"{not_done} {tr(refusal_key)}":
        # The notice is the only place the product explains a non-refusal; a
        # bare sentence would send the reader to the operation journal.
        raise InstalledTuiChildError(
            f"installed TUI {step} expected refusal {refusal_key}, workbench notice was {notice[:400]!r}",
            diagnostic=public_surface_diagnostic(pilot),
        )
    return TuiOutcome(step=step, terminal_condition="refused", visible_notice_key=refusal_key)


async def _submit_evidence(pilot: Any, *, step: str) -> TuiOutcome:
    terminal: TuiTerminalEvidence = await activate_tui_operation(pilot, binding=_EVIDENCE_SUBMIT)
    return TuiOutcome(step=step, terminal_condition=terminal.terminal_condition, visible_notice_key=None)


async def _form_refusals(pilot: Any, *, work_unit_id: str, observed_at: str) -> list[TuiOutcome]:
    """Missing answers stay on the form; cancelling is reported without a request."""
    from textual.widgets import Button

    outcomes: list[TuiOutcome] = []
    await _open_evidence_form(pilot, work_unit_id=work_unit_id)
    _fill_evidence_form(pilot, answer=False, observed_at=observed_at)
    query_public_selector(pilot, _EVIDENCE_SUBMIT_ID, Button).focus()
    await pilot.press("enter")
    await pilot.pause()
    await _await_selector(pilot, _EVIDENCE_SUBMIT_ID)
    outcomes.append(
        TuiOutcome(
            step="missing_booleans",
            terminal_condition="form_refused",
            visible_notice_key=_notice_key(pilot, "#m303-evidence-notice", ("tui.modelo.m303_evidence.required",)),
        )
    )
    query_public_selector(pilot, "#m303-evidence-cancel", Button).focus()
    await pilot.press("enter")
    await _await_selector(pilot, WORKBENCH_NOTICE)
    await pilot.pause()
    outcomes.append(
        TuiOutcome(
            step="cancelled",
            terminal_condition="cancelled_without_request",
            visible_notice_key=_notice_key(pilot, WORKBENCH_NOTICE, ("tui.modelo.m303_evidence.cancelled",)),
        )
    )
    return outcomes


async def _calculate_and_verify(
    pilot: Any, *, work_unit_id: str, form: Mapping[str, str], asks_modelo_390: bool = True
) -> list[TuiOutcome]:
    outcomes: list[TuiOutcome] = []
    await _open_evidence_form(pilot, work_unit_id=work_unit_id)
    _fill_evidence_form(
        pilot,
        attachment_id=form.get("attachment_id", ""),
        sha256=form.get("sha256", ""),
        observed_at=form.get("observed_at", ""),
        asks_modelo_390=asks_modelo_390,
    )
    calculated = await _submit_evidence(pilot, step="calculate")
    outcomes.append(calculated)
    if calculated.terminal_condition != "succeeded":
        raise InstalledTuiChildError(
            f"installed TUI M303 calculation ended {calculated.terminal_condition}: {_visible_refusal(pilot)}"
        )
    await _await_workbench_refresh(pilot, binding=_EVIDENCE_SUBMIT)
    return outcomes


def _visible_refusal(pilot: Any) -> str:
    """Name what the operator can see after a non-succeeded operation: the modal receipt or the workbench notice."""
    from textual.css.query import NoMatches

    for selector in ("#operation-modal-receipt", WORKBENCH_NOTICE):
        try:
            text = _rendered(pilot.app.screen.query_one(selector))
        except NoMatches:
            continue
        if text:
            return f"{selector}={text[:400]!r}"
    return "no visible reason"


async def _verify(pilot: Any, *, work_unit_id: str) -> TuiOutcome:
    """Verify from the workbench, first confirming, reviewing and applying any assumed values it offers to confirm."""
    contract = installed_lifecycle_contract()
    verify = contract.verify
    await _open_work(pilot, work_unit_id=work_unit_id)
    try:
        confirmed = await confirm_assumed_values(pilot, binding=contract.apply, maximum_polls=6000)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(str(error), diagnostic=public_surface_diagnostic(pilot)) from error
    if confirmed is not None:
        if confirmed.terminal_condition != "succeeded":
            raise InstalledTuiChildError(
                f"installed TUI M303 confirmation of assumed values ended {confirmed.terminal_condition}: "
                f"{_visible_refusal(pilot)}"
            )
        await _open_work(pilot, work_unit_id=work_unit_id)
    terminal = await activate_tui_operation(pilot, binding=verify)
    if terminal.terminal_condition != "succeeded":
        raise InstalledTuiChildError(
            f"installed TUI M303 verification ended {terminal.terminal_condition}: {_visible_refusal(pilot)}"
        )
    await _await_workbench_refresh(pilot, binding=verify)
    return TuiOutcome(step="verify", terminal_condition=terminal.terminal_condition, visible_notice_key=None)


async def _workbench_resultado(pilot: Any, *, work_unit_id: str) -> tuple[str | None, bool]:
    """Read ``iva.resultado`` off the workbench's form: its origin, and whether its value equals the oracle."""
    from cadrumo.application.modelo.work_form_models import address_key

    form = (await _open_work(pilot, work_unit_id=work_unit_id)).form
    if form is None:
        raise InstalledTuiChildError("installed workbench lost its form", diagnostic=public_surface_diagnostic(pilot))
    field = next((item for item in form.fields() if address_key(item.address) == ("casilla", _RESULTADO_CASILLA)), None)
    if field is None:
        return None, False
    return field.origin.value, resultado_matches_oracle(field.value)


async def _listed_revision(pilot: Any, *, calculation_revision_id: str) -> tuple[bool, str | None]:
    """Return whether Declarations lists the revision as current, and its lifecycle state as shown."""
    from textual.widgets import DataTable

    from cadrumo.core.i18n.render import tr
    from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState

    await _close_modals(pilot)
    await _open_declarations(pilot)
    await select_public_data_table_row(
        pilot=pilot, table_selector="#declarations-navigation", row_key="declarations.revisions"
    )
    await _await_selector(pilot, "#declarations-revisions")
    table = cast("DataTable[Any]", query_public_selector(pilot, "#declarations-revisions", DataTable))
    for row_key in table.rows:
        if row_key.value != calculation_revision_id:
            continue
        cells = table.get_row(row_key)
        state = next(
            (
                member.value
                for member in CalculationRevisionState
                if tr(f"tui.declarations.revision_state.{member.value}") == str(cells[2])
            ),
            None,
        )
        return str(cells[3]) == tr("tui.declarations.value.yes"), state
    return False, None


async def _attempt_export(pilot: Any, *, work_unit_id: str, output_path: str) -> TuiOutcome:
    """Run the official export through the workbench's export dialog and classify its public terminal result."""
    binding = installed_lifecycle_contract().export
    await _open_work(pilot, work_unit_id=work_unit_id)
    try:
        await open_workbench_export(pilot, output_path=output_path)
    except TuiJourneyError as error:
        raise InstalledTuiChildError(str(error), diagnostic=public_surface_diagnostic(pilot)) from error
    terminal = await activate_tui_operation(pilot, binding=binding)
    if terminal.terminal_condition == "succeeded":
        await acknowledge_export_result(pilot)
    return TuiOutcome(step="export", terminal_condition=terminal.terminal_condition, visible_notice_key=None)


def _require_development_developer_header(payload: bytes, positions: tuple[str, str, str]) -> None:
    """Refuse unless the official developer-header bytes carry the all-zero development identity."""
    record, program_span, developer_span = positions
    envelope_start = payload.find(b"<T303")
    if envelope_start < 0:
        raise IvaInstalledM303Error(f"Modelo 303 export carries no {record} envelope prefix")
    for span, expected in (
        (program_span, _DEVELOPMENT_MOCK_HEADER["program"]),
        (developer_span, _DEVELOPMENT_MOCK_HEADER["developer"]),
    ):
        first, last = (int(bound) for bound in span.split("-"))
        if payload[envelope_start + first - 1 : envelope_start + last] != expected:
            raise IvaInstalledM303Error(f"{record} bytes {span} do not carry the development identity")


async def _admit_session(pilot: Any, *, passphrase: str, seconds: float = 300.0) -> bool:
    """Drive runtime admission within the existing slow-composition bound."""
    return await admit_installed_session(
        pilot=pilot, passphrase=passphrase, deadline=asyncio.get_running_loop().time() + seconds
    )


def _run_child(args: argparse.Namespace, *, passphrase: str) -> ChildReceipt:
    product = installed_product_evidence(workspace_root=args.workspace_root)
    mode = cast(ChildMode, args.child)
    work_unit_id = cast(str, args.work_unit_id)
    observed_at = _year_end_observed_at(cast(int, args.year))
    outcomes: list[TuiOutcome] = []
    reopen: list[ReopenReadback] = []
    failure: list[InstalledTuiChildError] = []

    from cadrumo.entrypoints.tui.launcher import main as launch

    async def drive(pilot: Any) -> None:
        try:
            if mode == "tui-led-calculate":
                outcomes.extend(await _form_refusals(pilot, work_unit_id=work_unit_id, observed_at=observed_at))
                for step, attachment_id, sha256 in (
                    ("mismatched_pair", _MISMATCHED_ATTACHMENT_ID, _MISMATCHED_SHA256),
                    ("wrong_filing_context", args.wrong_attachment_id, args.wrong_sha256),
                ):
                    await _open_evidence_form(pilot, work_unit_id=work_unit_id)
                    _fill_evidence_form(pilot, attachment_id=attachment_id, sha256=sha256)
                    outcomes.append(
                        await _settle_expected_refusal(
                            pilot,
                            activation_id=_EVIDENCE_SUBMIT_ID,
                            step=step,
                            refusal_key=_ATTESTATION_REFUSAL_KEY,
                        )
                    )
                outcomes.extend(
                    await _calculate_and_verify(pilot, work_unit_id=work_unit_id, form={"observed_at": observed_at})
                )
                outcomes.append(await _verify(pilot, work_unit_id=work_unit_id))
            elif mode == "tui-joint-only-calculate":
                outcomes.extend(
                    await _calculate_and_verify(pilot, work_unit_id=work_unit_id, form={}, asks_modelo_390=False)
                )
                outcomes.append(await _verify(pilot, work_unit_id=work_unit_id))
            elif mode == "tui-continue-calculate":
                outcomes.extend(
                    await _calculate_and_verify(
                        pilot,
                        work_unit_id=work_unit_id,
                        form={"attachment_id": args.existing_attachment_id, "sha256": args.existing_sha256},
                    )
                )
            else:
                listed_current, state = await _listed_revision(
                    pilot, calculation_revision_id=cast(str, args.calculation_revision_id)
                )
                origin, matches_oracle = await _workbench_resultado(pilot, work_unit_id=work_unit_id)
                reopen.append(
                    ReopenReadback(
                        revision_listed_current=listed_current,
                        revision_state=state,
                        resultado_origin=origin,
                        resultado_matches_oracle=matches_oracle,
                    )
                )
                if args.export_path:
                    outcomes.append(
                        await _attempt_export(pilot, work_unit_id=work_unit_id, output_path=args.export_path)
                    )
        except InstalledTuiChildError as error:
            failure.append(error)
        finally:
            pilot.app.exit()

    async def autopilot(pilot: Any) -> None:
        try:
            if not await _admit_session(pilot, passphrase=passphrase):
                return
        except InstalledTuiChildError as error:
            failure.append(error)
            pilot.app.exit()
            return
        await drive(pilot)

    exit_code = launch(headless=True, auto_pilot=autopilot)
    if failure:
        raise failure[0]
    if exit_code != 0:
        raise InstalledTuiChildError(f"installed TUI {mode} child exited {exit_code}")
    return ChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        mode=mode,
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        outcomes=tuple(outcomes),
        reopen=reopen[0] if reopen else None,
    )


# --------------------------------------------------------------------------- outer driver


def _child(
    *,
    args: argparse.Namespace,
    store: Path,
    passphrase: str,
    mode: ChildMode,
    work_unit_id: str,
    extra: Sequence[str] = (),
) -> tuple[ChildHandle, tuple[TuiOutcome, ...], ReopenReadback | None]:
    receipt_path = args.output_root / f"{store.name}-{mode}.json"
    process = run_installed_tui_child_process(
        python_executable=args.python,
        workspace_root=args.workspace_root,
        child_module=_CHILD_MODULE,
        child_args=(
            *("--child", mode, "--workspace-root", str(args.workspace_root), "--receipt", str(receipt_path)),
            *("--year", str(args.year), "--work-unit-id", work_unit_id, *extra),
        ),
        storage_root=store,
        authority_root=args.authority_root,
        receipt_path=receipt_path,
        passphrase=passphrase,
        timeout_seconds=900,
    )
    document = _mapping(json.loads(receipt_path.read_text(encoding="utf-8")), label=f"{mode} receipt")
    if process.returncode != 0 or process.receipt_status != "proven":
        raise IvaInstalledM303Error(f"installed TUI {mode} child failed: {document.get('error')}")
    if document.get("product_origin") != "site-packages":
        raise IvaInstalledM303Error(f"installed TUI {mode} child did not run the site-packages product")
    outcomes = tuple(
        TuiOutcome(**cast(dict[str, Any], item)) for item in cast(list[object], document.get("outcomes") or [])
    )
    handle = ChildHandle(
        mode=mode,
        returncode=process.returncode,
        receipt_status=process.receipt_status,
        receipt_sha256=process.receipt_sha256,
        stdout_sha256=process.stdout_sha256,
        stderr_sha256=process.stderr_sha256,
    )
    reopen = document.get("reopen")
    readback = ReopenReadback(**cast(dict[str, Any], reopen)) if isinstance(reopen, dict) else None
    return handle, outcomes, readback


def _fresh_cli(args: argparse.Namespace, store: Path, passphrase: str) -> _Cli:
    return _Cli(InstalledCli(args.cli, storage_root=store, authority_root=args.authority_root, passphrase=passphrase))


def _setup_store(
    args: argparse.Namespace,
    journey_year: IvaJourneyYear,
    name: str,
    *,
    period: str = _PERIOD,
    wallet_period: str = _PRIOR_PERIOD,
    days: tuple[tuple[int, int], tuple[int, int]] = _LAST_PERIOD_DAYS,
    monthly_filer: bool = False,
) -> tuple[Path, str, _Cli, str]:
    store = cast(Path, args.output_root) / name
    store.mkdir(parents=True)
    artifact = args.output_root / f"{name}-synthetic-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic acceptance purchase evidence\n")
    passphrase = secrets.token_urlsafe(32)
    cli = _fresh_cli(args, store, passphrase)
    try:
        cli.cli.create_profile(year=journey_year.year)
    except InstalledCliError as error:
        raise IvaInstalledM303Error("installed CLI profile creation refused") from error
    if monthly_filer:
        # RD 1624/1992 art. 71: a REDEME-registered taxpayer settles Modelo 303 monthly.
        cli.run(("config", "profile", "edit", f"income-{journey_year.year}", "--quiet", "--iva-redeme-enrolled"))
    (sale_month, sale_day), (purchase_month, purchase_day) = days
    work_unit_id = _cli_capture_and_create_work(
        cli,
        artifact=artifact,
        year=journey_year.year,
        period=period,
        wallet_period=wallet_period,
        dates=(journey_year.iso_date(sale_month, sale_day), journey_year.iso_date(purchase_month, purchase_day)),
    )
    artifact.unlink()
    return store, passphrase, cli, work_unit_id


def require_reopen(readback: ReopenReadback | None, *, scenario: str) -> ReopenReadback:
    """Require the fresh TUI to list the verified revision as current and its workbench to show the oracle's result."""
    if readback is None or not readback.revision_listed_current or readback.revision_state != "verificado_completo":
        raise IvaInstalledM303Error(f"fresh installed TUI did not list the {scenario} revision as current and verified")
    if readback.resultado_origin != "calculated" or readback.resultado_matches_oracle is not True:
        raise IvaInstalledM303Error(
            f"fresh installed TUI workbench for {scenario} did not show a calculated iva.resultado equal to the oracle"
        )
    return readback


def require_outcomes(outcomes: Sequence[TuiOutcome], expected: Mapping[str, tuple[str, str | None]]) -> None:
    """Require each named step to have reached the expected terminal and, when named, visible notice."""
    observed = {item.step: (item.terminal_condition, item.visible_notice_key) for item in outcomes}
    for step, (condition, notice) in expected.items():
        actual = observed.get(step)
        if actual is None or actual[0] != condition or (notice is not None and actual[1] != notice):
            raise IvaInstalledM303Error(f"installed TUI step {step} observed {actual}, expected {(condition, notice)}")


def _tui_led_store(
    args: argparse.Namespace, journey_year: IvaJourneyYear, export_positions: tuple[str, str, str]
) -> StoreEvidence:
    store, passphrase, cli, work_unit_id = _setup_store(args, journey_year, "tui-led")
    wrong_id, wrong_sha = _attest(
        cli, year=journey_year.year, period=_WRONG_PERIOD, observed_at=_year_end_observed_at(journey_year.year)
    )
    cli.run(("app", "modelo", "work", "calculate", work_unit_id), expect_refusal=True)
    cli.run(_calculate_args(work_unit_id, attestation=None), expect_refusal=True)
    cli.run(
        _calculate_args(work_unit_id, attestation=(_MISMATCHED_ATTACHMENT_ID, _MISMATCHED_SHA256)),
        expect_refusal=True,
    )
    cli.run(_calculate_args(work_unit_id, attestation=(wrong_id, wrong_sha)), expect_refusal=True)
    if _revision_ids(cli, work_unit_id):
        raise IvaInstalledM303Error("an installed CLI refusal persisted a calculation revision")

    calculate_handle, calculate_outcomes, _ = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-led-calculate",
        work_unit_id=work_unit_id,
        extra=("--wrong-attachment-id", wrong_id, "--wrong-sha256", wrong_sha),
    )
    require_outcomes(
        calculate_outcomes,
        {
            "missing_booleans": ("form_refused", "tui.modelo.m303_evidence.required"),
            "cancelled": ("cancelled_without_request", "tui.modelo.m303_evidence.cancelled"),
            "mismatched_pair": ("refused", _ATTESTATION_REFUSAL_KEY),
            "wrong_filing_context": ("refused", _ATTESTATION_REFUSAL_KEY),
            "calculate": ("succeeded", None),
            "verify": ("succeeded", None),
        },
    )

    revisions = _revision_ids(cli, work_unit_id)
    if len(revisions) != 1:
        raise IvaInstalledM303Error(f"TUI refusals or calculation left {len(revisions)} revisions, expected one")
    tui_export_path = args.output_root / "tui-led-tui-export.boe"
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revisions[0], "--export-path", str(tui_export_path)),
    )
    tui_reopen = require_reopen(readback, scenario="tui_led")
    require_outcomes(reopen_outcomes, {"export": ("succeeded", None)})
    matches, verified = _read_revision(cli, revisions[0])
    if not (matches and verified):
        raise IvaInstalledM303Error("installed CLI readback of the TUI revision failed the oracle or verification")
    cli_export_path = args.output_root / "tui-led-cli-export.boe"
    cli.run(("app", "modelo", "export", work_unit_id, "--output", str(cli_export_path)))
    tui_bytes = tui_export_path.read_bytes()
    if cli_export_path.read_bytes() != tui_bytes:
        raise IvaInstalledM303Error("installed CLI and TUI exports of one revision wrote different bytes")
    _require_development_developer_header(tui_bytes, export_positions)
    return StoreEvidence(
        scenario="tui_led",
        work_unit_id=work_unit_id,
        calculation_revision_id=revisions[0],
        revision_count=len(revisions),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=None,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )


def _continuation_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    store, passphrase, cli, work_unit_id = _setup_store(args, journey_year, "continuation")
    attachment_id, sha256 = _attest(
        cli, year=journey_year.year, period=_PERIOD, observed_at=_year_end_observed_at(journey_year.year)
    )
    calculate_handle, calculate_outcomes, _ = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-continue-calculate",
        work_unit_id=work_unit_id,
        extra=("--existing-attachment-id", attachment_id, "--existing-sha256", sha256),
    )
    require_outcomes(calculate_outcomes, {"calculate": ("succeeded", None)})
    tui_revisions = _revision_ids(cli, work_unit_id)
    if len(tui_revisions) != 1:
        raise IvaInstalledM303Error("TUI continuation did not persist exactly one revision")
    recalculated = cli.run(_calculate_args(work_unit_id, attestation=(attachment_id, sha256)))
    same_revision = recalculated.get("calculation_revision_id") == tui_revisions[0]
    if not same_revision or _revision_ids(cli, work_unit_id) != tui_revisions:
        raise IvaInstalledM303Error("installed CLI recalculation with the same evidence produced another revision")
    verification = cli.run(("app", "modelo", "work", "verify", tui_revisions[0]))
    if verification.get("granted_verificado_completo") is not True:
        raise IvaInstalledM303Error("installed CLI verification of the TUI revision was not granted")
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", tui_revisions[0]),
    )
    tui_reopen = require_reopen(readback, scenario="continuation")
    matches, verified = _read_revision(cli, tui_revisions[0])
    changed = cli.run(_calculate_args(work_unit_id, attestation=(attachment_id, sha256), joint_return_elected=True))
    distinct = changed.get("calculation_revision_id") not in {None, tui_revisions[0]}
    if not (matches and verified and distinct):
        raise IvaInstalledM303Error("continuation readback, verification or evidence-identity control failed")
    return StoreEvidence(
        scenario="continuation",
        work_unit_id=work_unit_id,
        calculation_revision_id=tui_revisions[0],
        revision_count=len(_revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=same_revision,
        changed_evidence_produced_distinct_revision=distinct,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )


def _monthly_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    """A REDEME-registered filer settles monthly and answers the Modelo 390 exemption in 12, as others do in 4T."""
    store, passphrase, cli, work_unit_id = _setup_store(
        args, journey_year, "monthly", period=_MONTH, wallet_period=_PRIOR_MONTH, monthly_filer=True
    )
    attestation = _attest(
        cli, year=journey_year.year, period=_MONTH, observed_at=_year_end_observed_at(journey_year.year)
    )
    calculated = cli.run(_calculate_args(work_unit_id, attestation=attestation))
    revision_id = _text(calculated.get("calculation_revision_id"), label="monthly calculate")
    verification = cli.run(("app", "modelo", "work", "verify", revision_id))
    if verification.get("granted_verificado_completo") is not True:
        raise IvaInstalledM303Error("installed CLI verification of the monthly revision was not granted")
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revision_id),
    )
    tui_reopen = require_reopen(readback, scenario="monthly")
    matches, verified = _read_revision(cli, revision_id)
    if not (matches and verified):
        raise IvaInstalledM303Error("installed CLI readback of the monthly revision failed the oracle or verification")
    return StoreEvidence(
        scenario="monthly",
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        revision_count=len(_revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=None,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(reopen_handle,),
        child_outcomes=tuple(reopen_outcomes),
    )


def _first_quarter_store(args: argparse.Namespace, journey_year: IvaJourneyYear) -> StoreEvidence:
    """1T asks only the joint-return election: attestation flags are refused and the TUI form asks one question."""
    store, passphrase, cli, work_unit_id = _setup_store(
        args,
        journey_year,
        "first-quarter",
        period=_FIRST_QUARTER,
        wallet_period=_FIRST_QUARTER,
        days=_FIRST_QUARTER_DAYS,
    )
    refused = cli.run(
        _calculate_args(work_unit_id, attestation=(_MISMATCHED_ATTACHMENT_ID, _MISMATCHED_ATTACHMENT_ID)),
        expect_refusal=True,
    )
    if _OUTSIDE_LAST_PERIOD not in json.dumps(refused, sort_keys=True):
        raise IvaInstalledM303Error("installed CLI did not refuse an attestation the 1T return does not ask for")
    if _revision_ids(cli, work_unit_id):
        raise IvaInstalledM303Error("an installed CLI refusal persisted a calculation revision")
    calculate_handle, calculate_outcomes, _ = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-joint-only-calculate",
        work_unit_id=work_unit_id,
    )
    require_outcomes(calculate_outcomes, {"calculate": ("succeeded", None), "verify": ("succeeded", None)})
    revisions = _revision_ids(cli, work_unit_id)
    if len(revisions) != 1:
        raise IvaInstalledM303Error("the 1T TUI calculation did not persist exactly one revision")
    recalculated = cli.run(_calculate_args(work_unit_id, attestation=None))
    same_revision = recalculated.get("calculation_revision_id") == revisions[0]
    reopen_handle, reopen_outcomes, readback = _child(
        args=args,
        store=store,
        passphrase=passphrase,
        mode="tui-reopen",
        work_unit_id=work_unit_id,
        extra=("--calculation-revision-id", revisions[0]),
    )
    tui_reopen = require_reopen(readback, scenario="first_quarter")
    matches, verified = _read_revision(cli, revisions[0])
    if not (matches and verified and same_revision):
        raise IvaInstalledM303Error("1T readback, verification or CLI recalculation identity failed")
    return StoreEvidence(
        scenario="first_quarter",
        work_unit_id=work_unit_id,
        calculation_revision_id=revisions[0],
        revision_count=len(_revision_ids(cli, work_unit_id)),
        cli_resultado_matches_oracle=matches,
        cli_revision_verified=verified,
        cli_recalculated_same_revision=same_revision,
        changed_evidence_produced_distinct_revision=None,
        tui_reopen=tui_reopen,
        commands=tuple(cli.outcomes),
        children=(calculate_handle, reopen_handle),
        child_outcomes=(*calculate_outcomes, *reopen_outcomes),
    )


def _installed_identity(python: Path) -> tuple[str, str, str, str]:
    """Return (package version, __init__ path, __init__ sha256, bundled authority generation)."""
    probe = (
        "import json, importlib.metadata as m, importlib.resources as r, cadrumo;"
        "d=r.files('cadrumo').joinpath('_data','registry','authority','authority.current.json');"
        "print(json.dumps({'v': m.version('cadrumo'), 'init': cadrumo.__file__,"
        " 'gen': json.loads(d.read_bytes())['logical_generation']}))"
    )
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(  # noqa: S603 - explicit acceptance interpreter
        [str(python), "-c", probe], check=True, capture_output=True, text=True, cwd=python.parent, env=environment
    )
    payload = cast(dict[str, str], json.loads(completed.stdout))
    init_path = Path(payload["init"]).resolve(strict=True)
    if "site-packages" not in init_path.parts:
        raise IvaInstalledM303Error("installed interpreter did not import cadrumo from site-packages")
    return payload["v"], str(init_path), _sha256_bytes(init_path.read_bytes()), payload["gen"]


def _authority(authority_root: Path) -> tuple[str, str]:
    descriptor = (authority_root / "authority.current.json").read_bytes()
    return _text(json.loads(descriptor).get("logical_generation"), label="authority"), _sha256_bytes(descriptor)


def run_journey(args: argparse.Namespace) -> JourneyReceipt:
    """Run every isolated store for ``args.year`` against one installed wheel and pinned authority.

    Raises:
        IvaFilingYearUnsupportedError: Before the output root is created, when the
            published authority lacks a Modelo 303 revision authored for the year
            in any exercised period, or the year's 4T record design is not one
            whose developer-header positions the journey holds.
    """
    journey_year = require_journey_year(authority_root=args.authority_root, year=args.year, coordinates=_COORDINATES)
    export_positions = require_m303_developer_header_positions(journey_year, period=_PERIOD)
    args.output_root.mkdir(parents=True, exist_ok=True)
    if any(args.output_root.iterdir()):
        raise IvaInstalledM303Error("output root must be empty")
    version, init_path, init_sha256, bundled_generation = _installed_identity(args.python)
    generation, descriptor_sha256 = _authority(args.authority_root)
    if generation != bundled_generation:
        raise IvaInstalledM303Error("supplied authority generation differs from the one the installed wheel bundles")
    stores = (
        _tui_led_store(args, journey_year, export_positions),
        _continuation_store(args, journey_year),
        _monthly_store(args, journey_year),
        _first_quarter_store(args, journey_year),
    )
    return JourneyReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        filing_year=journey_year.year,
        periods=(_PERIOD, _MONTH, _FIRST_QUARTER),
        source_commit=args.source_commit,
        wheel_filename=args.wheel.name,
        wheel_sha256=_sha256_bytes(args.wheel.read_bytes()),
        package_version=version,
        installed_init_path=init_path,
        installed_init_sha256=init_sha256,
        authority_generation=generation,
        authority_descriptor_sha256=descriptor_sha256,
        bundled_authority_generation=bundled_generation,
        stores=stores,
        unexercised=(
            "official_m303_export_blocked_by_unavailable_eedd_header_identity",
            "tui_invoice_capture_multi_line",
            "aeat_submission",
        ),
        retention=(
            "synthetic encrypted stores and child receipts retained under the output root; "
            "no transient plaintext input remains; removal needs the coordinator's cleanup authorization"
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--child", choices=("tui-led-calculate", "tui-continue-calculate", "tui-joint-only-calculate", "tui-reopen")
    )
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--work-unit-id")
    parser.add_argument("--wrong-attachment-id", default="")
    parser.add_argument("--wrong-sha256", default="")
    parser.add_argument("--existing-attachment-id", default="")
    parser.add_argument("--existing-sha256", default="")
    parser.add_argument("--calculation-revision-id", default="")
    parser.add_argument("--export-path", default="")
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-commit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run either the outer installed journey or one credentialed TUI child."""
    args = _parser().parse_args(argv)
    args.workspace_root = args.workspace_root.resolve(strict=True)
    if args.child is not None:
        import faulthandler

        # A native crash writes no Python receipt; this bounded trace is the only evidence it leaves.
        fault_log = args.receipt.with_suffix(".fault.txt").open("w", encoding="utf-8")
        faulthandler.enable(fault_log)
        try:
            receipt = _run_child(args, passphrase=read_passphrase_from_stdin())
        except InstalledTuiChildError as error:
            write_installed_tui_failure_receipt(path=args.receipt, schema_version=_SCHEMA_VERSION, error=error)
            return 2
        except KeyboardInterrupt:
            raise
        except BaseException as error:
            import traceback

            frames = [
                f"{Path(frame.filename).name}:{frame.lineno}" for frame in traceback.extract_tb(error.__traceback__)
            ]
            write_installed_tui_failure_receipt(
                path=args.receipt,
                schema_version=_SCHEMA_VERSION,
                error=InstalledTuiChildError(f"{type(error).__name__}: {error!s:.300} at {frames[-6:]}"),
            )
            return 3
        args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    for name in ("cli", "python", "wheel", "authority_root", "output_root", "source_commit"):
        if getattr(args, name) is None:
            raise SystemExit(f"--{name.replace('_', '-')} is required for the outer journey")
    args.cli = args.cli.resolve(strict=True)
    args.python = environment_interpreter(args.python)
    args.wheel = args.wheel.resolve(strict=True)
    args.authority_root = args.authority_root.resolve(strict=True)
    args.output_root = args.output_root.resolve()
    receipt = run_journey(args)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt.status, "receipt": str(args.receipt)}))
    return 0


if __name__ == "__main__":  # pragma: no cover - installed execution is integration-owned
    raise SystemExit(main())
