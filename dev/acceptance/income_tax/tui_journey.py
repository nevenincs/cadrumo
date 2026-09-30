"""Installed-TUI and cross-frontend evidence for INCOME-01.

This development-only module deliberately contains no tax calculation, filing,
or persistence implementation.  It records the independent scenario/oracle
coordinate and the real TUI interaction contract that an installed journey
must exercise.  Until the installed composition exposes every required
control, callers receive a blocked receipt rather than a synthetic success.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

from dev.registry.record_design_xsd_support import repair_xsd_regex_escapes

from .authority import IncomeTaxAuthorityResolution
from .scenario import BRIEF_ID, BRIEF_REVISION, SCENARIO_VERSION, AcceptanceOutcome

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.widget import Widget

    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen

_XML_DECLARATION_ENCODING: Final = re.compile(r'encoding="[^"]+"')
_SHA256_HEX: Final = re.compile(r"[0-9a-f]{64}")
_XSD_NORMALIZATION: Final = (
    "canonical record-design preparation replaces the XML declaration encoding "
    "with UTF-8 and removes only illegal escapes from xs:pattern values"
)

#: The workbench line where its refusals and settled operations are reported.
WORKBENCH_NOTICE: Final = "#wb-notice"
#: The workbench's casilla list, present whenever the workbench is the top screen.
WORKBENCH_LIST: Final = "#wb-list"
#: The workbench's line naming the next step its F8 key runs.
WORKBENCH_NEXT: Final = "#wb-next"
#: The accept control of the shared confirmation dialog, which the workbench shows
#: before recalculating a declaration last calculated elsewhere that holds values
#: nobody is recorded as having entered.
WORKBENCH_AT_RISK_PROCEED: Final = "#btn-confirm-accept"
_EXPORT_PATH: Final = "#export-path"
_EXPORT_RESULT_CLOSE: Final = "#modelo-export-result-close"
#: The close control of the statement of which boxes a recalculation changed.
_RESULT_STATEMENT_CLOSE: Final = "#result-close"

type TerminalCondition = Literal["succeeded", "succeeded_partial", "refused", "failed", "cancelled", "not_completed"]


class TuiJourneyError(RuntimeError):
    """Raised when an acceptance receipt cannot identify a valid run coordinate."""


class _TuiScreen(Protocol):
    """The public Textual screen operation used by the installed adapter."""

    def query_one(self, selector: str) -> object: ...


@dataclass(frozen=True, slots=True)
class TuiOperationBinding:
    """One installed-TUI operation and the controls needed to prove it.

    ``operation_id`` names the shared registered application operation.  The
    remaining values are deliberately absent until the installed composition
    supplies stable controls; an operation definition alone cannot prove that
    a TUI user can activate it, confirm it, or observe its terminal result.

    An operation starts either from a workbench key (``activation_key``) or
    from a button on a dialog the journey has already opened
    (``activation_id``), never both.  A key that runs whatever step the
    workbench offers next names that step in ``offered_step`` (``verify``,
    ``file``), and the driver refuses to press it while the workbench offers
    another one.  ``at_risk_proceed_id`` is pressed only while the
    workbench's pre-recalculation confirmation is the top screen.
    """

    operation_id: str
    activation_key: str | None = None
    activation_id: str | None = None
    offered_step: str | None = None
    at_risk_proceed_id: str | None = None
    confirmation_id: str | None = None
    confirmation_required: bool = False
    terminal_result_id: str | None = None
    refresh_result_id: str | None = None
    refusal_notice_id: str | None = None

    def missing(self, *, label: str) -> tuple[str, ...]:
        """Name required installed controls that are not available yet."""
        values = {
            "activation": self.activation_key or self.activation_id,
            "terminal_result": self.terminal_result_id,
            "refresh_result": self.refresh_result_id,
            "refusal_notice": self.refusal_notice_id,
        }
        missing = [f"{label}.{name}" for name, value in values.items() if value is None]
        if self.confirmation_required and self.confirmation_id is None:
            missing.append(f"{label}.confirmation")
        return tuple(missing)


@dataclass(frozen=True, slots=True)
class InstalledTuiContract:
    """Stable installed controls required by the income journey.

    The contract intentionally captures user-reachable controls rather than
    application services.  It prevents a test from quietly replacing an
    unavailable screen action with a private repository invocation.
    """

    profile_selection_id: str | None = None
    ledger_capture_id: str | None = None
    invoice_link_id: str | None = None
    work_create_id: str | None = None
    work_open_id: str | None = None
    calculate: TuiOperationBinding = TuiOperationBinding("modelo.work.calculate")
    verify: TuiOperationBinding = TuiOperationBinding("modelo.work.verify")
    local_file: TuiOperationBinding = TuiOperationBinding("modelo.work.file")
    export: TuiOperationBinding = TuiOperationBinding("modelo.export")

    def missing_controls(self) -> tuple[str, ...]:
        """Return every missing user-facing control in deterministic order."""
        missing = tuple(
            name
            for name, value in (
                ("profile_selection", self.profile_selection_id),
                ("ledger_capture", self.ledger_capture_id),
                ("invoice_link", self.invoice_link_id),
                ("work_create", self.work_create_id),
                ("work_open", self.work_open_id),
            )
            if value is None
        )
        return (
            *missing,
            *self.calculate.missing(label="calculate"),
            *self.verify.missing(label="verify"),
            *self.local_file.missing(label="local_file"),
            *self.export.missing(label="export"),
        )


@dataclass(frozen=True, slots=True)
class LifecycleEvidence:
    """Keep local lifecycle outcomes distinct in every frontend receipt."""

    calculation: AcceptanceOutcome
    verification: AcceptanceOutcome
    export_readiness: AcceptanceOutcome
    export_execution: AcceptanceOutcome
    local_filing: AcceptanceOutcome
    submission: AcceptanceOutcome


@dataclass(frozen=True, slots=True)
class TuiTerminalEvidence:
    """One terminal result observed through the public operation modal."""

    operation_id: str
    terminal_condition: TerminalCondition
    outcome: AcceptanceOutcome
    receipt_present: bool
    diagnostic_present: bool


@dataclass(frozen=True, slots=True)
class AcceptanceCaseEvidence:
    """One A1-A10 result with its local lifecycle state preserved."""

    acceptance_id: str
    outcome: AcceptanceOutcome
    lifecycle: LifecycleEvidence
    source_state: str
    diagnostic_code: str | None = None


@dataclass(frozen=True, slots=True)
class LocalXsdValidationEvidence:
    """Sanitized local XSD validation evidence for a Modelo 100 XML export.

    A true ``xsd_valid`` means only that the XML validates against the named
    local schema preparation.  It never represents AEAT transmission or an
    AEAT acceptance result.
    """

    xml_sha256: str
    xml_size: int
    original_schema_sha256: str
    original_schema_size: int
    normalization: str
    normalization_count: int
    effective_validation_schema_sha256: str
    effective_validation_schema_size: int
    xsd_valid: bool
    error_identities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContinuationStateEvidence:
    """Value-free public readback at a frontend continuation boundary.

    The financial values themselves stay in the isolated store.  Each driver
    independently canonicalizes its public readback and records only its
    SHA-256 fingerprint, preventing a durable receipt from becoming a copy of
    taxpayer or invoice payloads.
    """

    authority_generation: str
    profile_complete: bool
    transactions: int
    invoices: int
    links: int
    work_periods: tuple[str, ...]
    calculated_periods: tuple[str, ...]
    verified_periods: tuple[str, ...]
    locally_filed_periods: tuple[str, ...]
    export_ready_modelos: tuple[str, ...]
    exported_modelos: tuple[str, ...]
    canonical_value_fingerprint: str

    def state_sha256(self) -> str:
        """Fingerprint the public continuation state without exposing values."""
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ContinuationCheckpoint:
    """A meaningful persisted-state boundary for a second frontend."""

    frontend_path: Literal["cli_to_tui", "tui_to_cli"]
    handoff_frontend: Literal["cli", "tui"]
    resume_frontend: Literal["cli", "tui"]
    state: ContinuationStateEvidence
    state_sha256: str


@dataclass(frozen=True, slots=True)
class ContinuationEvidence:
    """Proof that both frontends used and advanced one persisted workflow."""

    frontend_path: Literal["cli_to_tui", "tui_to_cli"]
    checkpoint: ContinuationCheckpoint
    resumed_state_sha256: str
    completion_state: ContinuationStateEvidence
    outcome: AcceptanceOutcome


@dataclass(frozen=True, slots=True)
class TuiJourneyEvidence:
    """Receipt for one installed-TUI or sequential continuation scenario."""

    brief_id: str
    brief_revision: str
    scenario: str
    frontend_path: Literal["tui", "cli_to_tui", "tui_to_cli"]
    year: int
    authority_generation: str
    modelo_130_revisions: tuple[str, ...]
    modelo_100_revision: str
    source_state: str
    contract_missing_controls: tuple[str, ...]
    cases: tuple[AcceptanceCaseEvidence, ...]
    xsd_validation: LocalXsdValidationEvidence | None = None
    continuation: ContinuationEvidence | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the stable, JSON-safe receipt payload."""
        return dict[str, object](asdict(self))


def installed_lifecycle_contract(
    *,
    profile_selection_id: str | None = None,
    ledger_capture_id: str | None = None,
    invoice_link_id: str | None = None,
    work_create_id: str | None = None,
) -> InstalledTuiContract:
    """Return the current public lifecycle controls plus unresolved entry controls.

    The caller must still supply actual profile, ledger, and calendar controls.
    Leaving them absent causes a blocked receipt, which prevents lifecycle
    wiring from being misreported as a complete TUI-only journey.

    Every lifecycle action runs in the declaration's workbench, opened from
    the Declarations list: ``c`` calculates, ``F8`` runs the verification or
    the local filing the stepper offers next (filing through its
    confirmation dialog), and the export dialog opened with ``e`` submits the
    export.
    """
    modal_terminal = "#operation-modal-status"
    return InstalledTuiContract(
        profile_selection_id=profile_selection_id,
        ledger_capture_id=ledger_capture_id,
        invoice_link_id=invoice_link_id,
        work_create_id=work_create_id,
        work_open_id="#declarations-list",
        calculate=TuiOperationBinding(
            "modelo.work.calculate",
            activation_key="c",
            at_risk_proceed_id=WORKBENCH_AT_RISK_PROCEED,
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
        verify=TuiOperationBinding(
            "modelo.work.verify",
            activation_key="f8",
            offered_step="verify",
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
        local_file=TuiOperationBinding(
            "modelo.work.file",
            activation_key="f8",
            offered_step="file",
            confirmation_id="#btn-confirm-accept",
            confirmation_required=True,
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
        export=TuiOperationBinding(
            "modelo.export",
            activation_id="#export-submit",
            terminal_result_id=modal_terminal,
            refresh_result_id=WORKBENCH_LIST,
            refusal_notice_id=WORKBENCH_NOTICE,
        ),
    )


async def wait_for_workbench(pilot: Pilot[Any], *, seconds: float = 300.0) -> ModeloWorkbenchScreen:
    """Wait until the declaration's workbench is the top screen and has read its form.

    The workbench reads its form off the event loop, so the screen appears
    before it can be acted on.  A read the workbench itself reports as failed
    is refused at once rather than waited out.
    """
    from textual.css.query import NoMatches

    from cadrumo.core.i18n.render import tr
    from cadrumo.entrypoints.tui.modelo.workbench import screen as workbench_screen

    read_failed = tr("tui.modelo.workbench.read_failed")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        # The top of the stack is the screen on display; unlike ``app.screen`` it is
        # typed ``Screen[Any]``, which a workbench screen can narrow.
        screen = pilot.app.screen_stack[-1]
        if isinstance(screen, workbench_screen.ModeloWorkbenchScreen):
            if screen.form is not None:
                return screen
            try:
                loading = _rendered_text(screen.query_one("#wb-loading"))
            except NoMatches:
                loading = ""
            if loading == read_failed:
                raise TuiJourneyError("the declaration's workbench could not read its form")
        await pilot.pause(0.2)
    raise TuiJourneyError(
        f"the declaration's workbench did not read its form within {seconds:.0f}s "
        f"(top screen {type(pilot.app.screen).__name__})"
    )


async def open_workbench_export(pilot: Pilot[Any], *, output_path: str, maximum_polls: int = 600) -> None:
    """Open the workbench's export dialog with its own key and name the destination.

    The dialog is only offered for a verified declaration; the workbench's
    own refusal is reported instead of being waited out.
    """
    from textual.css.query import NoMatches
    from textual.widgets import Input

    _require_fresh_notice(pilot, label="modelo.export")
    await pilot.press("e")
    for _ in range(maximum_polls):
        try:
            destination = pilot.app.screen.query_one(_EXPORT_PATH, Input)
        except NoMatches:
            notice = _stack_text(pilot, WORKBENCH_NOTICE)
            if notice:
                raise TuiJourneyError(f"the workbench did not open its export dialog: {notice[:240]}") from None
            await pilot.pause()
            continue
        destination.value = output_path
        return
    raise TuiJourneyError("the workbench did not open its export dialog")


async def acknowledge_export_result(pilot: Pilot[Any], *, maximum_polls: int = 600) -> None:
    """Close the statement a finished export shows before the workbench moves on."""
    from textual.css.query import NoMatches

    for _ in range(maximum_polls):
        try:
            close = pilot.app.screen.query_one(_EXPORT_RESULT_CLOSE)
        except NoMatches:
            await pilot.pause()
            continue
        close.focus()
        await pilot.press("enter")
        for _ in range(maximum_polls):
            if not pilot.app.screen.query(_EXPORT_RESULT_CLOSE):
                return
            await pilot.pause()
        raise TuiJourneyError("the export statement did not close")
    raise TuiJourneyError("the finished export did not show its statement")


async def activate_tui_operation(
    pilot: Pilot[Any],
    *,
    binding: TuiOperationBinding,
    maximum_polls: int = 600,
) -> TuiTerminalEvidence:
    """Activate one real TUI control and classify its public terminal result.

    This adapter reads only the modal's rendered status, receipt and diagnostic
    widgets and the workbench's notice.  It intentionally does not call an
    operation controller or inspect a private journal, and it cannot turn a
    refreshed screen into success.  The workbench's notice must be empty
    before activation, so a notice left by an earlier operation can never be
    read as this operation's result.
    """
    _require_operation_binding(binding)
    _require_fresh_notice(pilot, label=binding.operation_id, selector=binding.refusal_notice_id)
    if binding.activation_key is not None:
        if binding.offered_step is not None:
            _require_offered_step(pilot, step=binding.offered_step, key=binding.activation_key)
        await pilot.press(binding.activation_key)
    elif binding.activation_id is not None:
        activation = _query_visible_tui_control(pilot, binding.activation_id)
        activation.focus()
        await pilot.press("enter")
    await pilot.pause()
    if binding.confirmation_id is not None:
        confirmation = await _wait_for_visible_tui_control(pilot, binding.confirmation_id, maximum_polls=maximum_polls)
        confirmation.focus()
        await pilot.press("enter")
        await pilot.pause()
    modal = await _wait_for_operation_modal_or_refusal(
        pilot,
        binding=binding,
        maximum_polls=maximum_polls,
    )
    if modal is None:
        notice = _stack_text(pilot, binding.refusal_notice_id or "")
        settled = settled_notice_terminal(notice)
        if settled is not None:
            condition, outcome = settled
            return TuiTerminalEvidence(
                operation_id=binding.operation_id,
                terminal_condition=condition,
                outcome=outcome,
                receipt_present=False,
                diagnostic_present=False,
            )
        return TuiTerminalEvidence(
            operation_id=binding.operation_id,
            terminal_condition="refused",
            outcome=AcceptanceOutcome.BLOCKED,
            receipt_present=False,
            diagnostic_present=True,
        )
    return await _observe_operation_terminal(
        pilot,
        modal=modal,
        binding=binding,
        maximum_polls=maximum_polls,
    )


async def wait_for_tui_refresh(
    pilot: Pilot[Any],
    *,
    binding: TuiOperationBinding,
    maximum_polls: int = 600,
) -> None:
    """Require the workbench back on top after a succeeded lifecycle action, with its re-read settled.

    The workbench stays open after an operation and reads the declaration
    again; the wait ends only once that read, and any other work the screen
    started, has finished.  After a recalculation the workbench states which
    boxes now read differently; that statement is closed as a filer closes it.
    """
    from textual.css.query import NoMatches

    if binding.refresh_result_id is None:
        raise TuiJourneyError(f"{binding.operation_id} has no installed refresh target")
    for _ in range(maximum_polls):
        try:
            close = pilot.app.screen.query_one(_RESULT_STATEMENT_CLOSE)
        except NoMatches:
            pass
        else:
            close.focus()
            await pilot.press("enter")
            await pilot.pause()
            continue
        try:
            pilot.app.screen.query_one(binding.refresh_result_id)
        except NoMatches:
            await pilot.pause()
            continue
        if all(worker.is_finished for worker in pilot.app.workers):
            return
        await pilot.pause()
    raise TuiJourneyError(f"{binding.operation_id} did not reach its refreshed TUI destination")


def canonical_financial_value_fingerprint(*, values: Mapping[str, str]) -> str:
    """Fingerprint independently normalized financial readback without retaining it.

    Callers must supply canonical, value-only strings such as normalized
    casilla amounts.  The resulting digest is safe to place in the durable
    receipt and lets the CLI and TUI demonstrate equal financial meaning
    without copying their financial readback into a checkpoint.
    """
    normalized: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise TuiJourneyError("canonical financial fingerprint requires non-empty string keys and string values")
        normalized[key] = value
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_tui_journey_evidence(
    *,
    contract: InstalledTuiContract,
    resolution: IncomeTaxAuthorityResolution,
    frontend_path: Literal["tui", "cli_to_tui", "tui_to_cli"],
    source_state: str,
    cases: tuple[AcceptanceCaseEvidence, ...],
    xsd_validation: LocalXsdValidationEvidence | None = None,
    continuation: ContinuationEvidence | None = None,
) -> TuiJourneyEvidence:
    """Assemble a truthful final receipt from real installed-driver evidence.

    This validates receipt integrity.  It does not turn failed or blocked case
    evidence into a passing campaign; the driver still reports each public
    action's actual outcome.
    """
    missing = contract.missing_controls()
    if missing:
        raise TuiJourneyError(f"cannot assemble an installed TUI receipt with missing controls: {', '.join(missing)}")
    year, m130_revisions, m100_revision = _required_coordinate(resolution)
    if not isinstance(source_state, str) or not source_state:
        raise TuiJourneyError("installed TUI receipt needs a non-empty source-state identity")
    expected_ids = {f"A{number}" for number in range(1, 11)}
    actual_ids = {case.acceptance_id for case in cases}
    if len(cases) != len(actual_ids) or actual_ids != expected_ids:
        raise TuiJourneyError("installed TUI receipt must contain every A1-A10 case exactly once")
    if any(case.lifecycle.submission is not AcceptanceOutcome.NOT_EXERCISED for case in cases):
        raise TuiJourneyError("income acceptance has no authorized AEAT submission outcome")
    a9 = next(case for case in cases if case.acceptance_id == "A9")
    if a9.outcome is AcceptanceOutcome.PROVEN and (xsd_validation is None or not xsd_validation.xsd_valid):
        raise TuiJourneyError("a proven export case requires a successful local Modelo 100 XSD validation")
    if frontend_path == "tui":
        if continuation is not None:
            raise TuiJourneyError("a TUI-only journey cannot carry continuation evidence")
    elif continuation is not None and continuation.frontend_path != frontend_path:
        raise TuiJourneyError("continuation evidence frontend path does not match its receipt")
    elif next(case for case in cases if case.acceptance_id == "A8").outcome is AcceptanceOutcome.PROVEN:
        raise TuiJourneyError("a proven continuation case requires a persisted-state continuation receipt")
    return TuiJourneyEvidence(
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=f"{SCENARIO_VERSION}:{year}:{frontend_path}",
        frontend_path=frontend_path,
        year=year,
        authority_generation=resolution.authority_generation,
        modelo_130_revisions=m130_revisions,
        modelo_100_revision=m100_revision,
        source_state=source_state,
        contract_missing_controls=(),
        cases=cases,
        xsd_validation=xsd_validation,
        continuation=continuation,
    )


def blocked_tui_journey_evidence(
    *,
    contract: InstalledTuiContract,
    resolution: IncomeTaxAuthorityResolution,
    frontend_path: Literal["tui", "cli_to_tui", "tui_to_cli"],
) -> TuiJourneyEvidence:
    """Build a truthful receipt when installed controls are incomplete.

    This is a capability report, not a passing journey.  It preserves the
    existing CLI proof by leaving controls owned by that completed evidence as
    ``not_exercised`` in this TUI receipt.
    """
    year, m130_revisions, m100_revision = _required_coordinate(resolution)
    missing = contract.missing_controls()
    lifecycle = LifecycleEvidence(
        calculation=AcceptanceOutcome.BLOCKED,
        verification=AcceptanceOutcome.BLOCKED,
        export_readiness=AcceptanceOutcome.BLOCKED,
        export_execution=AcceptanceOutcome.BLOCKED,
        local_filing=AcceptanceOutcome.BLOCKED,
        # This campaign has no AEAT submission authority even after the TUI
        # controls exist.
        submission=AcceptanceOutcome.NOT_EXERCISED,
    )
    blocked_cases = {
        "A1",
        "A3",
        "A6",
        "A7",
        "A9",
        "A10",
    }
    if frontend_path in {"cli_to_tui", "tui_to_cli"}:
        blocked_cases.add("A8")
    cases = tuple(
        AcceptanceCaseEvidence(
            acceptance_id=f"A{number}",
            outcome=AcceptanceOutcome.BLOCKED if f"A{number}" in blocked_cases else AcceptanceOutcome.NOT_EXERCISED,
            lifecycle=lifecycle
            if f"A{number}" in blocked_cases
            else LifecycleEvidence(
                calculation=AcceptanceOutcome.NOT_EXERCISED,
                verification=AcceptanceOutcome.NOT_EXERCISED,
                export_readiness=AcceptanceOutcome.NOT_EXERCISED,
                export_execution=AcceptanceOutcome.NOT_EXERCISED,
                local_filing=AcceptanceOutcome.NOT_EXERCISED,
                submission=AcceptanceOutcome.NOT_EXERCISED,
            ),
            source_state="installed_tui_contract_unavailable"
            if f"A{number}" in blocked_cases
            else "not_exercised_by_tui_driver",
            diagnostic_code="acceptance.installed_tui.contract_unavailable" if f"A{number}" in blocked_cases else None,
        )
        for number in range(1, 11)
    )
    return TuiJourneyEvidence(
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=f"{SCENARIO_VERSION}:{year}:{frontend_path}",
        frontend_path=frontend_path,
        year=year,
        authority_generation=resolution.authority_generation,
        modelo_130_revisions=m130_revisions,
        modelo_100_revision=m100_revision,
        source_state="installed_tui_contract_unavailable",
        contract_missing_controls=missing,
        cases=cases,
    )


def create_continuation_checkpoint(
    *,
    frontend_path: Literal["cli_to_tui", "tui_to_cli"],
    state: ContinuationStateEvidence,
) -> ContinuationCheckpoint:
    """Record a non-final workflow that the other frontend must reopen.

    Empty records, a mere screen open, and a fully completed export are not
    useful continuation starts.  This gate makes the first frontend leave
    real persisted financial work for the second frontend without allowing a
    private-store handoff assertion to stand in for public readback.
    """
    _validate_continuation_state(state)
    handoff_frontend, resume_frontend = _continuation_frontends(frontend_path)
    if not state.profile_complete or not all((state.transactions, state.invoices, state.links)):
        raise TuiJourneyError("continuation handoff has no meaningful persisted financial capture")
    if not state.work_periods:
        raise TuiJourneyError("continuation handoff has no persisted declaration work")
    if _is_completion_state(state):
        raise TuiJourneyError("continuation handoff is already complete")
    return ContinuationCheckpoint(
        frontend_path=frontend_path,
        handoff_frontend=handoff_frontend,
        resume_frontend=resume_frontend,
        state=state,
        state_sha256=state.state_sha256(),
    )


def validate_continuation_readback(
    *,
    checkpoint: ContinuationCheckpoint,
    frontend: Literal["cli", "tui"],
    state: ContinuationStateEvidence,
) -> str:
    """Require the receiving frontend to reproduce the exact handoff state."""
    if frontend != checkpoint.resume_frontend:
        raise TuiJourneyError(
            f"continuation {checkpoint.frontend_path} must resume through {checkpoint.resume_frontend}"
        )
    _validate_continuation_state(state)
    if state != checkpoint.state or state.state_sha256() != checkpoint.state_sha256:
        raise TuiJourneyError("receiving frontend did not reproduce the persisted continuation state")
    return checkpoint.state_sha256


def prove_continuation(
    *,
    checkpoint: ContinuationCheckpoint,
    frontend: Literal["cli", "tui"],
    resumed_state: ContinuationStateEvidence,
    completion_state: ContinuationStateEvidence,
) -> ContinuationEvidence:
    """Validate readback and completion without treating an already-done run as a handoff."""
    resumed_state_sha256 = validate_continuation_readback(
        checkpoint=checkpoint,
        frontend=frontend,
        state=resumed_state,
    )
    _validate_continuation_state(completion_state)
    if completion_state.authority_generation != checkpoint.state.authority_generation:
        raise TuiJourneyError("continuation completion used a different authority generation")
    if completion_state.canonical_value_fingerprint != checkpoint.state.canonical_value_fingerprint:
        raise TuiJourneyError("continuation completion changed canonical financial meaning")
    if completion_state.state_sha256() == checkpoint.state_sha256:
        raise TuiJourneyError("receiving frontend did not advance the persisted workflow")
    if not _is_completion_state(completion_state):
        raise TuiJourneyError("continuation completion lacks required four-period local lifecycle and annual export")
    return ContinuationEvidence(
        frontend_path=checkpoint.frontend_path,
        checkpoint=checkpoint,
        resumed_state_sha256=resumed_state_sha256,
        completion_state=completion_state,
        outcome=AcceptanceOutcome.PROVEN,
    )


def validate_modelo_100_xsd(*, xml_path: Path, xsd_path: Path) -> LocalXsdValidationEvidence:
    """Validate XML with the shared AEAT record-design schema preparation.

    The schema's original bytes and the exact effective prepared bytes are
    both fingerprinted.  The only semantic transformation is delegated to
    the existing record-design repair helper; it removes invalid XSD-regex
    escapes and never rewrites declaration data.
    """
    from lxml import etree

    xml_bytes = xml_path.read_bytes()
    xsd_bytes = xsd_path.read_bytes()
    source_text = xsd_bytes.decode("iso-8859-1")
    prepared_text = _XML_DECLARATION_ENCODING.sub('encoding="UTF-8"', source_text, count=1)
    repaired_text, repair_count = repair_xsd_regex_escapes(prepared_text)
    effective_bytes = repaired_text.encode("utf-8")
    try:
        schema = etree.XMLSchema(etree.fromstring(effective_bytes))
        document = etree.fromstring(xml_bytes)
        xsd_valid = schema.validate(document)
        errors = tuple(
            _schema_error_identity(error.domain_name, error.type_name, error.line) for error in schema.error_log
        )
    except etree.LxmlError as exc:
        # The textual parser message can contain document values.  Keep only
        # the stable exception class in the durable receipt.
        xsd_valid = False
        errors = (f"xsd_validation.{type(exc).__name__}",)
    return LocalXsdValidationEvidence(
        xml_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        xml_size=len(xml_bytes),
        original_schema_sha256=hashlib.sha256(xsd_bytes).hexdigest(),
        original_schema_size=len(xsd_bytes),
        normalization=_XSD_NORMALIZATION,
        normalization_count=repair_count,
        effective_validation_schema_sha256=hashlib.sha256(effective_bytes).hexdigest(),
        effective_validation_schema_size=len(effective_bytes),
        xsd_valid=xsd_valid,
        error_identities=errors,
    )


def write_tui_journey_receipt(*, evidence: TuiJourneyEvidence, path: Path) -> None:
    """Persist one sanitized receipt after its caller owns the output path."""
    rendered = json.dumps(evidence.to_dict(), indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{rendered}\n", encoding="utf-8", newline="\n")


def settled_notice_terminal(notice: str) -> tuple[TerminalCondition, AcceptanceOutcome] | None:
    """Classify the notice the workbench leaves after its operation modal dismissed itself.

    The modal closes as soon as the operation is terminal.  The workbench then
    says the declaration was updated -- or, once it has read a recalculated
    declaration again, that no box changed -- or that the operation did not
    complete, alone or followed by one space and the registry's public
    explanation of a settled refusal.  An explanation is only ever given for a
    refusal, so that shape is a refusal; the bare sentence cannot say which
    non-success it was and stays ``not_completed``.  Any other text is not a
    terminal.
    """
    from cadrumo.core.i18n.render import tr

    succeeded = {tr("tui.modelo.workbench.operation.done"), tr("tui.modelo.workbench.result_diff.nothing_changed")}
    not_done = tr("tui.modelo.workbench.operation.not_done")
    if notice in succeeded:
        return "succeeded", AcceptanceOutcome.PROVEN
    if notice == not_done:
        return "not_completed", AcceptanceOutcome.FAILED
    if notice.startswith(f"{not_done} ") and notice[len(not_done) + 1 :].strip():
        return "refused", AcceptanceOutcome.BLOCKED
    return None


def _require_operation_binding(binding: TuiOperationBinding) -> None:
    """Refuse to drive an incomplete or ambiguous public control contract."""
    missing = binding.missing(label=binding.operation_id)
    if missing:
        raise TuiJourneyError(f"installed TUI operation contract is incomplete: {', '.join(missing)}")
    if binding.activation_key is not None and binding.activation_id is not None:
        raise TuiJourneyError(f"{binding.operation_id} names both a key and a control to activate it")


def _require_fresh_notice(pilot: Pilot[Any], *, label: str, selector: str | None = WORKBENCH_NOTICE) -> None:
    """Refuse to start an operation while the workbench still shows an earlier notice."""
    if selector is None:
        return
    notice = _stack_text(pilot, selector)
    if notice:
        raise TuiJourneyError(
            f"{label} would start under an earlier workbench notice; open the declaration afresh first "
            f"(notice {notice[:120]!r})"
        )


def _require_offered_step(pilot: Pilot[Any], *, step: str, key: str) -> None:
    """Require the workbench to offer ``step`` as the one its next-step key runs."""
    from textual.css.query import NoMatches

    from cadrumo.core.i18n.render import tr

    expected = tr(
        "tui.modelo.workbench.next_line",
        action=tr(f"tui.modelo.workbench.next.{step}", count=0),
        key=key.upper(),
    )
    try:
        offered = _rendered_text(pilot.app.screen.query_one(WORKBENCH_NEXT))
    except NoMatches:
        offered = ""
    if not offered.startswith(expected):
        raise TuiJourneyError(f"the workbench does not offer {step} as its next step (it offers {offered[:200]!r})")


async def _wait_for_visible_tui_control(pilot: Pilot[Any], selector: str, *, maximum_polls: int) -> Widget:
    """Wait until a control is on the top screen."""
    from textual.css.query import NoMatches

    for _ in range(maximum_polls):
        try:
            return _query_visible_tui_control(pilot, selector)
        except NoMatches:
            await pilot.pause()
    raise TuiJourneyError(f"installed TUI did not show {selector}")


async def _proceed_past_at_risk_confirmation(pilot: Pilot[Any], selector: str | None) -> bool:
    """Press the pre-recalculation confirmation's proceed control, only while it is the top screen."""
    from textual.css.query import NoMatches

    if selector is None:
        return False
    try:
        proceed = _query_visible_tui_control(pilot, selector)
    except NoMatches:
        return False
    proceed.focus()
    await pilot.press("enter")
    await pilot.pause()
    return True


async def _wait_for_operation_modal_or_refusal(
    pilot: Pilot[Any],
    *,
    binding: TuiOperationBinding,
    maximum_polls: int,
) -> _TuiScreen | None:
    """Wait for the standard modal or a visible typed pre-submit refusal."""
    from cadrumo.entrypoints.tui.operations.modal import OperationModal

    refusal_notice_id = binding.refusal_notice_id
    if refusal_notice_id is None:
        raise TuiJourneyError(f"{binding.operation_id} has no visible refusal control")
    for _ in range(maximum_polls):
        current = pilot.app.screen
        if isinstance(current, OperationModal):
            return current
        if await _proceed_past_at_risk_confirmation(pilot, binding.at_risk_proceed_id):
            continue
        if _stack_text(pilot, refusal_notice_id):
            return None
        await pilot.pause()
    raise TuiJourneyError(f"{binding.operation_id} did not open an operation modal or visible refusal")


async def _observe_operation_terminal(
    pilot: Pilot[Any],
    *,
    modal: _TuiScreen,
    binding: TuiOperationBinding,
    maximum_polls: int,
) -> TuiTerminalEvidence:
    """Read the terminal widgets retained by the actual modal instance.

    A shared operation may pause at its public REVIEW phase before it can
    settle.  The installed driver answers that phase through the modal's
    ordinary Apply button once.  It never calls an operation controller or
    assumes that opening the modal executed the action.  Once the modal has
    dismissed itself, the workbench's notice carries the settled result.
    """
    from textual.css.query import NoMatches
    from textual.widget import Widget

    from cadrumo.core.i18n.render import tr

    expected: dict[str, tuple[TerminalCondition, AcceptanceOutcome]] = {
        tr("operation.modal.terminal.succeeded"): ("succeeded", AcceptanceOutcome.PROVEN),
        tr("operation.modal.terminal.succeeded_partial"): ("succeeded_partial", AcceptanceOutcome.FAILED),
        tr("operation.modal.terminal.refused"): ("refused", AcceptanceOutcome.BLOCKED),
        tr("operation.modal.terminal.failed"): ("failed", AcceptanceOutcome.FAILED),
        tr("operation.modal.terminal.cancelled"): ("cancelled", AcceptanceOutcome.FAILED),
    }
    terminal_result_id = binding.terminal_result_id
    if terminal_result_id is None:
        raise TuiJourneyError(f"{binding.operation_id} has no terminal result control")
    review_applied = False
    status: str | None = None
    for _ in range(maximum_polls):
        try:
            status = _rendered_text(modal.query_one(terminal_result_id))
            receipt = _rendered_text(modal.query_one("#operation-modal-receipt"))
            diagnostic = _rendered_text(modal.query_one("#operation-modal-diagnostic"))
        except NoMatches:
            terminal = _settled_terminal(pilot, binding)
            if terminal is not None:
                condition, outcome = terminal
                return TuiTerminalEvidence(
                    operation_id=binding.operation_id,
                    terminal_condition=condition,
                    outcome=outcome,
                    receipt_present=False,
                    diagnostic_present=False,
                )
            await pilot.pause()
            continue
        terminal = expected.get(status)
        if terminal is not None:
            condition, outcome = terminal
            return TuiTerminalEvidence(
                operation_id=binding.operation_id,
                terminal_condition=condition,
                outcome=outcome,
                receipt_present=bool(receipt),
                diagnostic_present=bool(diagnostic),
            )
        if not getattr(modal, "is_mounted", True):
            terminal = _settled_terminal(pilot, binding)
            if terminal is not None:
                condition, outcome = terminal
                return TuiTerminalEvidence(
                    operation_id=binding.operation_id,
                    terminal_condition=condition,
                    outcome=outcome,
                    receipt_present=bool(receipt),
                    diagnostic_present=bool(diagnostic),
                )
        # The generic modal keeps Apply disabled unless its public projection
        # has reached REVIEW.  A single click is the same operator act as the
        # visible button; repeating it while the projected revision catches up
        # would create noisy duplicate attempts rather than exercising the
        # lifecycle once.
        if not review_applied:
            try:
                apply = modal.query_one("#btn-operation-apply")
            except NoMatches:
                apply = None
            if apply is not None and not isinstance(apply, Widget):
                raise TuiJourneyError(
                    f"{binding.operation_id} operation modal Apply control is not a Textual widget "
                    f"({type(apply).__name__})"
                )
            if apply is not None and not apply.disabled:
                apply.focus()
                await pilot.press("enter")
                review_applied = True
        await pilot.pause()
    try:
        apply = modal.query_one("#btn-operation-apply")
        phase = _rendered_text(modal.query_one("#operation-modal-phase"))
        detail = (
            f"status={status!r}, phase={phase!r}, apply_disabled={getattr(apply, 'disabled', None)!r}, "
            f"apply_attempted={review_applied!r}"
        )
    except NoMatches:
        detail = f"modal_unmounted=True, apply_attempted={review_applied!r}"
    raise TuiJourneyError(f"{binding.operation_id} did not expose a terminal operation status ({detail})")


def _settled_terminal(
    pilot: Pilot[Any], binding: TuiOperationBinding
) -> tuple[TerminalCondition, AcceptanceOutcome] | None:
    """Classify the notice the workbench shows once the operation modal has gone."""
    refusal_notice_id = binding.refusal_notice_id
    if refusal_notice_id is None:
        return None
    return settled_notice_terminal(_stack_text(pilot, refusal_notice_id))


def _rendered_text(widget: object) -> str:
    """Read a widget's public rendered content without serializing raw data."""
    render = getattr(widget, "render", None)
    if not callable(render):
        raise TuiJourneyError("installed TUI control exposes no rendered text")
    return str(render()).strip()


def _query_visible_tui_control(pilot: Pilot[Any], selector: str) -> Widget:
    """Resolve a public control on the top screen, the only one an operator can act on."""
    return pilot.app.screen.query_one(selector)


def workbench_notice(pilot: Pilot[Any]) -> str:
    """Read the workbench's notice, even while a dialog it opened sits above it."""
    return _stack_text(pilot, WORKBENCH_NOTICE)


def _stack_text(pilot: Pilot[Any], selector: str) -> str:
    """Read the rendered text of the top-most screen that shows ``selector``, or nothing.

    The workbench's notice stays on the workbench while a dialog it opened
    sits above it, so it is read from the nearest screen down the stack that
    has it.
    """
    from textual.css.query import NoMatches

    for screen in reversed(pilot.app.screen_stack):
        try:
            return _rendered_text(screen.query_one(selector))
        except NoMatches:
            continue
    return ""


def _required_coordinate(resolution: IncomeTaxAuthorityResolution) -> tuple[int, tuple[str, ...], str]:
    """Return the pinned coordinate or refuse to manufacture one for a receipt."""
    if resolution.selected_year is None or resolution.modelo_100 is None or not resolution.modelo_130:
        raise TuiJourneyError("income acceptance requires a selected M130/M100 authority coordinate")
    return (
        resolution.selected_year,
        tuple(item.revision for item in resolution.modelo_130),
        resolution.modelo_100.revision,
    )


def _continuation_frontends(
    frontend_path: Literal["cli_to_tui", "tui_to_cli"],
) -> tuple[Literal["cli", "tui"], Literal["cli", "tui"]]:
    """Return the only valid writer/readback order for a continuation path."""
    if frontend_path == "cli_to_tui":
        return "cli", "tui"
    if frontend_path == "tui_to_cli":
        return "tui", "cli"
    raise TuiJourneyError(f"unsupported continuation path: {frontend_path}")


def _validate_continuation_state(state: ContinuationStateEvidence) -> None:
    """Reject ambiguous, unordered, or value-carrying boundary descriptions."""
    if not _SHA256_HEX.fullmatch(state.authority_generation):
        raise TuiJourneyError("continuation state has no SHA-256 authority generation")
    if not _SHA256_HEX.fullmatch(state.canonical_value_fingerprint):
        raise TuiJourneyError("continuation state has no SHA-256 canonical value fingerprint")
    for label, value in (
        ("transactions", state.transactions),
        ("invoices", state.invoices),
        ("links", state.links),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TuiJourneyError(f"continuation state has invalid {label} count")
    for label, values in (
        ("work_periods", state.work_periods),
        ("calculated_periods", state.calculated_periods),
        ("verified_periods", state.verified_periods),
        ("locally_filed_periods", state.locally_filed_periods),
        ("export_ready_modelos", state.export_ready_modelos),
        ("exported_modelos", state.exported_modelos),
    ):
        if any(not value for value in values):
            raise TuiJourneyError(f"continuation state has invalid {label}")
        if values != tuple(sorted(set(values))):
            raise TuiJourneyError(f"continuation state must use sorted unique {label}")
    work_periods = set(state.work_periods)
    if not set(state.calculated_periods).issubset(work_periods):
        raise TuiJourneyError("continuation state calculates a declaration with no persisted work")
    if not set(state.verified_periods).issubset(state.calculated_periods):
        raise TuiJourneyError("continuation state verifies a declaration that was not calculated")
    if not set(state.locally_filed_periods).issubset(state.verified_periods):
        raise TuiJourneyError("continuation state files a declaration that was not verified")


def _is_completion_state(state: ContinuationStateEvidence) -> bool:
    """Recognize the campaign's four-period local lifecycle plus M100 export."""
    quarters = {"1T", "2T", "3T", "4T"}
    return (
        quarters.issubset(state.work_periods)
        and quarters.issubset(state.calculated_periods)
        and quarters.issubset(state.verified_periods)
        and quarters.issubset(state.locally_filed_periods)
        and "100" in state.export_ready_modelos
        and "100" in state.exported_modelos
    )


def _schema_error_identity(domain: str | None, type_name: str | None, line: int) -> str:
    """Return a value-free validation error identity suitable for a receipt."""
    return ":".join((domain or "unknown_domain", type_name or "unknown_type", str(line)))


__all__ = [
    "WORKBENCH_AT_RISK_PROCEED",
    "WORKBENCH_LIST",
    "WORKBENCH_NEXT",
    "WORKBENCH_NOTICE",
    "AcceptanceCaseEvidence",
    "ContinuationCheckpoint",
    "ContinuationEvidence",
    "ContinuationStateEvidence",
    "InstalledTuiContract",
    "LifecycleEvidence",
    "LocalXsdValidationEvidence",
    "TerminalCondition",
    "TuiJourneyError",
    "TuiJourneyEvidence",
    "TuiOperationBinding",
    "TuiTerminalEvidence",
    "acknowledge_export_result",
    "activate_tui_operation",
    "blocked_tui_journey_evidence",
    "build_tui_journey_evidence",
    "canonical_financial_value_fingerprint",
    "create_continuation_checkpoint",
    "installed_lifecycle_contract",
    "open_workbench_export",
    "prove_continuation",
    "settled_notice_terminal",
    "validate_continuation_readback",
    "validate_modelo_100_xsd",
    "wait_for_tui_refresh",
    "wait_for_workbench",
    "workbench_notice",
    "write_tui_journey_receipt",
]
