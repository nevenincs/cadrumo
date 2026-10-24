"""``aeat config provision`` -- set up and check what Cadrumo needs on this computer.

The component verbs run one command of the native component engine, the
Cadrumo binary's ``components`` role, which alone decides each component's
state, plans its setup and performs it. This command line starts the role,
words its codes from the canonical catalogues and relays its events; it holds
no state of its own and needs no signed-in profile:

* **status** -- the quick check of every component: local facts only, no
  network, no model load.
* **probe** -- the full check of every component.
* **verify** -- the full check of the named component, or of every one.
* **setup**, **browser**, **pull** -- set up every component that offers it,
  the browser, or the local AI (its program and every role's model, as one
  item). Each prints the plan the role asks to approve and asks; ``--yes``
  approves exactly the printed plan. Without ``--yes`` and without a terminal
  to ask on, the plan is declined, nothing moves and the command says it needs
  your approval.

Where this build has no Cadrumo binary, every component reads as not in this
build. **report**, **start**, **load** and **remove** are the local reader's
actions, submitted as registered operations in the signed-in profile.

While a setup runs, text mode draws one progress line on standard error and
JSON mode writes each line the role sends there as one JSON object, so
standard output carries only the closing envelope. A row's text names its
plain sentence and, when the row offers a recovery, the exact command that
performs it.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import typer
from pydantic import BaseModel

from cadrumo_client.commands.output import write_stderr
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.contracts.command_program import CommandProgram
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_ids import LOCAL_READER_OPERATION_DEFINITION_ID

from ....adapters.outbound.components.client import ComponentsRequest, run_components_role
from ....adapters.outbound.components.protocol import (
    ComponentsAnswer,
    ComponentsApprove,
    ComponentsCommand,
    ComponentsDecline,
    ComponentsEvent,
    ComponentsNoticeCode,
    ComponentsNoticeLine,
    ComponentsOutcome,
    ComponentsPhaseLine,
    ComponentsPlan,
    ComponentsPlanPart,
    ComponentsProgressLine,
    ComponentsResultLine,
    ComponentsReviewLine,
)
from ....application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyItemKind,
    DependencyState,
    DependencyStatusRow,
)
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_wording import (
    dependency_failure_key,
    dependency_part_name,
    dependency_retry_sentence,
    dependency_row_wording,
    dependency_space_sentence,
)
from ....application.local_reader_contracts import (
    LocalReaderProvisionPublicResultV3,
    build_local_reader_load_request,
    build_local_reader_remove_request,
    build_local_reader_start_request,
)
from ....application.local_reader_report import (
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
    LocalReaderReportPublicResultV1,
    LocalReaderReportRequest,
)
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_surface.action_targets import ACTION_TARGETS
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity, ResolvedPreconditionAction
from ....core.model_catalogue import ModelRole, ModelSelectionAdvisory
from ....core.operations import OperationTerminalCondition
from ....core.output_rendering import OutputFormat
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from ....core.tty import stderr_is_tty, stdin_is_tty
from ..common import emit_envelope, format_of, resolve_cli_precondition_action
from ..errors import redraw_stderr_line
from ..errors import write_stderr as draw_stderr
from .provision_payloads import (
    ProvisionBrowserResult,
    ProvisionContentionPayload,
    ProvisionItemPayload,
    ProvisionLoadItemPayload,
    ProvisionLoadResult,
    ProvisionModelPayload,
    ProvisionProbeResult,
    ProvisionPullResult,
    ProvisionRemoveItemPayload,
    ProvisionRemoveResult,
    ProvisionReportResult,
    ProvisionSetupResult,
    ProvisionSpacePayload,
    ProvisionStartResult,
    ProvisionStatusResult,
    ProvisionVerifyResult,
)
from .status_rendering import precondition_action_lines

if TYPE_CHECKING:
    from ....application.local_reader_contracts import (
        LocalReaderContentionV1,
        LocalReaderFactV1,
        LocalReaderModelOutcomeV3,
        LocalReaderProvisionRequest,
    )
    from ....application.operations.models import OperationRequest
    from ....application.operator_actions.models import PreconditionVerdict

__all__ = [
    "SetupProgressLine",
    "SetupReview",
    "emit_provision_load",
    "emit_provision_remove",
    "emit_provision_report",
    "emit_provision_setup",
    "emit_provision_start",
    "emit_provision_status",
    "provision_browser",
    "provision_load",
    "provision_probe",
    "provision_pull",
    "provision_remove",
    "provision_report",
    "provision_setup",
    "provision_start",
    "provision_status",
    "provision_verify",
    "read_quick_setup_rows",
    "recovery_command",
    "verify_items",
]

_CALL_TIMEOUT_S: Final = 120.0
# Each settlement wait is at least the call timeout, which the client requires.
_QUICK_SETTLEMENT_S: Final = _CALL_TIMEOUT_S
_LOCAL_READER_SETTLEMENT_S: Final = 900.0
_PENDING_CHECK_COMMAND: Final = "aeat config provision status"
_QUICK_STATUS_TIMEOUT_S: Final = 30.0
"""A quick check answers within its 2 s bound; this only stops a role that hangs."""
_MIB: Final = 1024**2
_GIB: Final = 1024**3

_OUTCOME_LOCALE_KEYS: Final = {
    ComponentsOutcome.COMPLETED: "cli.config.provision.outcome.completed",
    ComponentsOutcome.NOTHING_TO_DO: "cli.config.provision.outcome.nothing_to_do",
    ComponentsOutcome.NEEDS_APPROVAL: "cli.config.provision.outcome.rejected",
    ComponentsOutcome.PLAN_CHANGED: "cli.config.provision.outcome.plan_changed",
    ComponentsOutcome.CANCELLED: "cli.config.provision.outcome.cancelled",
    ComponentsOutcome.BUSY: "cli.config.provision.outcome.busy",
}
"""The summary of each setup outcome that names no failure; a refusal or failure says its category's sentence."""

_SETUP_SUCCEEDED: Final = frozenset({ComponentsOutcome.COMPLETED, ComponentsOutcome.NOTHING_TO_DO})


# ── Item selection ──────────────────────────────────────────────────────────


def _declaration(item_id: str) -> DependencyItemDeclaration:
    for declaration in dependency_item_declarations():
        if declaration.item_id == item_id:
            return declaration
    raise KeyError(item_id)


def verify_items(item: str | None) -> tuple[DependencyItemKind, ...]:
    """Return the items a verify checks: the named item, or every item (empty)."""
    if item is None:
        return ()
    try:
        return (DependencyItemKind(item),)
    except ValueError:
        known = ", ".join(kind.value for kind in DependencyItemKind)
        raise typer.BadParameter(f"choose one of: {known}", param_hint="--item") from None


# ── Wording ─────────────────────────────────────────────────────────────────


def _name_of(item_id: str) -> str:
    return tr(f"application.{_declaration(item_id).display_key}")


def recovery_command(action_id: str) -> str:
    """Return the exact command that performs the operator action ``action_id``."""
    command_key = lookup_action(action_id).target_command_key
    target = next(row for row in ACTION_TARGETS if row.command_key == command_key)
    program: CommandProgram = target.program
    return " ".join((program.executable_name, *target.cli_path))


def _size(value: int) -> str:
    if value >= _GIB:
        return tr("cli.config.provision.size.gigabytes", value=f"{value / _GIB:.1f}")
    return tr("cli.config.provision.size.megabytes", value=f"{max(1, round(value / _MIB))}")


def _item_payload(row: DependencyStatusRow) -> ProvisionItemPayload:
    action_id = row.recovery_action_id
    return ProvisionItemPayload(
        item_id=row.item_id,
        state=row.state.value,
        stale_reason=None if row.stale_reason is None else row.stale_reason.value,
        blocked_reason=None if row.blocked_reason is None else row.blocked_reason.value,
        failure_category=None if row.failure_category is None else row.failure_category.value,
        note=None if row.note is None else row.note.value,
        version=row.version,
        size_estimate_bytes=row.size_estimate_bytes,
        recovery=None if row.recovery is None else row.recovery.value,
        recovery_action_id=action_id,
        command=None if action_id is None else recovery_command(action_id),
    )


def _row_lines(rows: Iterable[DependencyStatusRow]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        declaration = _declaration(row.item_id)
        wording = dependency_row_wording(row, declaration)
        sentence = wording.sentence if wording.note is None else f"{wording.sentence} {wording.note}"
        lines.append(f"{wording.name}\t{sentence}")
        if row.recovery_action_id is not None:
            lines.append("\t" + tr("cli.config.provision.fix", command=recovery_command(row.recovery_action_id)))
    return lines


def _space_sentence(plan: ComponentsPlan) -> str:
    free = "?" if plan.space.free_bytes is None else _size(plan.space.free_bytes)
    return dependency_space_sentence(required=_size(plan.space.required_bytes), free=free)


def _destination_line(destination: str | None) -> str | None:
    """Say where a plan stores what it downloads, for the destinations that are storage locations."""
    if destination is None:
        return None
    try:
        category = StorageCategory(destination)
    except ValueError:
        return None
    return tr("cli.config.provision.plan.destination", path=str(storage_path(category)))


def _licence_notice(part: ComponentsPlanPart) -> str | None:
    """Word the notice of a planned model whose licence bars commercial use, naming the licence by its title."""
    if part.licence is None or ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED not in part.advisories:
        return None
    model = part.part_id if part.target_version is None else part.target_version.split("@", 1)[0]
    return tr("provisioning.model.licence.plan_non_commercial", model=model, licence=part.licence.name)


def _plan_lines(plan: ComponentsPlan) -> list[str]:
    unknown = tr("cli.config.provision.plan.size_unknown")
    lines = [tr("cli.config.provision.plan.heading")]
    for entry in plan.entries:
        size = unknown if entry.download_bytes is None else _size(entry.download_bytes)
        lines.append(
            tr(
                "cli.config.provision.plan.entry",
                name=_name_of(entry.item_id),
                size=size,
                hosts=", ".join(entry.source_hosts),
            )
        )
        first_by_download: dict[tuple[str, str], str] = {}
        notices: list[str] = []
        for part in entry.parts:
            name = dependency_part_name(part.part_id)
            part_size = unknown if part.download_bytes is None else _size(part.download_bytes)
            lines.append(tr("cli.config.provision.plan.part", name=name, size=part_size))
            if part.destination is not None and part.target_version is not None:
                download = (part.destination.value, part.target_version)
                shared = first_by_download.setdefault(download, name)
                if shared != name:
                    lines.append("  " + tr("cli.config.provision.plan.shared", name=shared))
            notice = _licence_notice(part)
            if notice is not None and notice not in notices:
                notices.append(notice)
        destination = _destination_line(None if entry.destination is None else entry.destination.value)
        if destination is not None:
            lines.append(destination)
        if entry.installs_outside_program:
            lines.append(tr("cli.config.provision.plan.installs_program"))
        lines.extend(f"  {notice}" for notice in notices)
    total = _size(plan.known_download_bytes)
    lines.append(
        tr(
            "cli.config.provision.plan.total_unknown" if plan.has_unknown_size else "cli.config.provision.plan.total",
            size=total,
        )
    )
    if not plan.space.sufficient:
        lines.append(_space_sentence(plan))
    return lines


def _relayed(line: BaseModel) -> str:
    """Spell one line the role sent as the JSON object it was, for JSON mode's standard error."""
    return json.dumps(
        line.model_dump(mode="json", exclude_unset=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


# ── Reading every item's state ──────────────────────────────────────────────


def _status(request: ComponentsRequest, *, timeout: float | None) -> ComponentsResultLine:
    result = run_components_role(request, timeout=timeout)
    if result.outcome is not ComponentsOutcome.OK:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return result


def read_quick_setup_rows() -> tuple[DependencyStatusRow, ...]:
    """Read every setup item's row from the components role's quick check.

    Raises:
        RefusalError: The role could not be started, broke its protocol, or did not answer in time.
    """
    return _status(ComponentsRequest(ComponentsCommand.STATUS), timeout=_QUICK_STATUS_TIMEOUT_S).status_rows()


def provision_status(ctx: typer.Context) -> None:
    """Report every setup item's state from what this computer already has."""
    status = _status(ComponentsRequest(ComponentsCommand.STATUS), timeout=_QUICK_STATUS_TIMEOUT_S)
    emit_provision_status(ctx, status, command="config.provision.status", result_type=ProvisionStatusResult)


def provision_probe(ctx: typer.Context) -> None:
    """Report every setup item's state from its full check."""
    status = _checked(ctx, ComponentsRequest(ComponentsCommand.STATUS, full=True))
    emit_provision_status(ctx, status, command="config.provision.probe", result_type=ProvisionProbeResult)


def provision_verify(ctx: typer.Context, item: str | None = None) -> None:
    """Fully check the named item, or every item; exit 2 unless each is usable."""
    status = _checked(ctx, ComponentsRequest(ComponentsCommand.VERIFY, items=verify_items(item)))
    emit_provision_status(ctx, status, command="config.provision.verify", result_type=ProvisionVerifyResult)
    if not all(row.state in {DependencyState.READY, DependencyState.STALE} for row in status.status_rows()):
        raise typer.Exit(code=2)


def _checked(ctx: typer.Context, request: ComponentsRequest) -> ComponentsResultLine:
    """Run a full check, relaying its progress as a setup's is relayed."""
    progress = SetupProgressLine(json_mode=format_of(ctx) is OutputFormat.JSON, interactive=stderr_is_tty())
    try:
        result = run_components_role(request, on_event=progress.observe)
    finally:
        progress.finish()
    if result.outcome is not ComponentsOutcome.OK:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return result


# ── Setting up ──────────────────────────────────────────────────────────────


def provision_setup(ctx: typer.Context, yes: bool = False) -> None:
    """Set up every item that is not ready, after the person approves the printed plan."""
    _setup(ctx, (), yes=yes, command="config.provision.setup", result_type=ProvisionSetupResult)


def provision_browser(ctx: typer.Context, yes: bool = False) -> None:
    """Set up the browser Cadrumo uses for the tax agency website."""
    _setup(
        ctx,
        (DependencyItemKind.BROWSER,),
        yes=yes,
        command="config.provision.browser",
        result_type=ProvisionBrowserResult,
    )


def provision_pull(ctx: typer.Context, yes: bool = False) -> None:
    """Set up the local AI: its program when missing, then every role's model."""
    _setup(
        ctx, (DependencyItemKind.LOCAL_AI,), yes=yes, command="config.provision.pull", result_type=ProvisionPullResult
    )


def _can_ask(ctx: typer.Context) -> bool:
    return format_of(ctx) is OutputFormat.TEXT and stdin_is_tty() and stderr_is_tty()


@dataclass(slots=True)
class SetupReview:
    """Print the plan the role asks to approve, then answer it: ``--yes``, a terminal answer, or decline.

    The plan, with any licence notice of a model it would download, is always
    written on standard error first: plain lines in text mode, the role's own
    review line in JSON mode. ``--yes`` approves exactly the printed plan's
    digest. Without ``--yes`` and without a terminal to ask on, the plan is
    declined, so nothing moves and the command says approval is needed.
    """

    yes: bool
    ask: bool
    json_mode: bool = False
    reviewed: ComponentsReviewLine | None = None
    approved: bool = False
    needed_approval: bool = False

    def __call__(self, review: ComponentsReviewLine) -> ComponentsAnswer:
        """Answer one review."""
        self.reviewed = review
        if self.json_mode:
            write_stderr(_relayed(review))
        else:
            for line in _plan_lines(review.plan):
                write_stderr(line)
        if self.yes or (self.ask and typer.confirm(tr("cli.config.provision.approve_prompt"), default=False, err=True)):
            self.approved = True
            return ComponentsApprove(plan_digest=review.plan_digest)
        self.needed_approval = not self.ask
        return ComponentsDecline()


def _setup(
    ctx: typer.Context,
    items: tuple[DependencyItemKind, ...],
    *,
    yes: bool,
    command: str,
    result_type: type[ProvisionSetupResult],
) -> None:
    json_mode = format_of(ctx) is OutputFormat.JSON
    review = SetupReview(yes=yes, ask=_can_ask(ctx), json_mode=json_mode)
    progress = SetupProgressLine(json_mode=json_mode, interactive=stderr_is_tty())
    try:
        result = run_components_role(
            ComponentsRequest(ComponentsCommand.SETUP, items=items),
            on_event=progress.observe,
            review=review,
        )
    finally:
        progress.finish()
    reviewed = review.reviewed
    if (
        reviewed is not None
        and result.plan_digest is not None
        and result.outcome is ComponentsOutcome.COMPLETED
        and result.plan_digest != reviewed.plan_digest
    ):
        # A completed setup ran exactly the plan approved here, or the exchange is broken.
        raise RefusalError(RefusalCode.INVALID_FRAME)
    emit_provision_setup(
        ctx,
        result,
        command=command,
        result_type=result_type,
        approved=review.approved,
        needed_approval=review.needed_approval,
        items=items,
    )


# ── Progress ────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class SetupProgressLine:
    """Draw a setup's or check's progress on standard error from the events the role sends.

    On a terminal the line is redrawn in place; otherwise a line is written
    when an item enters a step. JSON mode writes each event as the role sent
    it, one JSON object per line, instead. Nothing here decides anything.
    """

    json_mode: bool
    interactive: bool
    _drawn: bool = False
    _last: dict[str, str] = field(default_factory=dict)

    def observe(self, event: ComponentsEvent) -> None:
        """Render one event."""
        if self.json_mode:
            write_stderr(_relayed(event))
            return
        if isinstance(event, ComponentsPhaseLine):
            self._step(event)
        elif isinstance(event, ComponentsProgressLine):
            self._bytes(event)
        else:
            self._notice(event)

    def _step(self, event: ComponentsPhaseLine) -> None:
        text = tr(
            "cli.config.provision.progress",
            name=_name_of(event.item_id),
            step=tr(f"cli.config.provision.step.{event.step.value}"),
        )
        if self._last.get(event.item_id) == text:
            return
        self._last[event.item_id] = text
        self._draw(text, settled=not self.interactive)

    def _bytes(self, event: ComponentsProgressLine) -> None:
        if not self.interactive:
            return
        self._draw(
            tr(
                "cli.config.provision.progress_bytes",
                name=_name_of(event.subject_code),
                done=_size(event.completed),
                total=_size(event.total),
                percent=min(100, event.completed * 100 // event.total),
            ),
            settled=False,
        )

    def _notice(self, event: ComponentsNoticeLine) -> None:
        if event.notice_code is ComponentsNoticeCode.RETRYING and event.subject_code is not None:
            seconds = math.ceil((event.delay_ms or 0) / 1000)
            sentence = dependency_retry_sentence(attempt=event.attempt or 1, delay_s=seconds)
            self._draw(f"{_name_of(event.subject_code)}: {sentence}", settled=True)
        elif event.notice_code is ComponentsNoticeCode.WAITING_FOR_SERVER and event.subject_code is not None:
            self._draw(tr("cli.config.provision.waiting_for_program", name=_name_of(event.subject_code)), settled=True)
        elif event.notice_code is ComponentsNoticeCode.CANCEL_REQUESTED:
            self._draw(tr("cli.config.provision.stopping"), settled=True)

    def _draw(self, text: str, *, settled: bool) -> None:
        if not self.interactive:
            write_stderr(text)
            return
        redraw_stderr_line(text)
        self._drawn = True
        if settled:
            self.finish()

    def finish(self) -> None:
        """End a line drawn in place, so later output starts on a fresh line."""
        if self._drawn:
            draw_stderr("\n")
            self._drawn = False


# ── Status and setup envelopes ──────────────────────────────────────────────


def emit_provision_status(
    ctx: typer.Context,
    status: ComponentsResultLine,
    *,
    command: str,
    result_type: type[ProvisionStatusResult],
) -> None:
    """Emit every reported item's row under ``command``."""
    rows = status.status_rows()
    hardware_limited = any(row.blocked_reason is DependencyBlockedReason.HARDWARE for row in rows)
    result = result_type(
        mode=(status.mode or DependencyCheckMode.QUICK).value,
        complete=status.setup_complete is True,
        hardware_limited=hardware_limited,
        items=[_item_payload(row) for row in rows],
    )
    lines = _row_lines(rows)
    if hardware_limited:
        lines.append(tr("cli.config.provision.hardware_limited"))
    lines.append(tr("cli.config.provision.complete" if result.complete else "cli.config.provision.incomplete"))
    emit_envelope(ctx, command=command, result=result, lines=lines)


def _usable(rows: Iterable[DependencyStatusRow], items: tuple[DependencyItemKind, ...]) -> bool:
    """Whether every requested item, every item when none is named, is ready or usable."""
    named = {item.value for item in items}
    return all(
        row.state in {DependencyState.READY, DependencyState.STALE} for row in rows if not named or row.item_id in named
    )


def _setup_summary(result: ComponentsResultLine, *, needed_approval: bool, usable: bool) -> str:
    if result.outcome is ComponentsOutcome.NEEDS_APPROVAL and needed_approval:
        return tr("cli.config.provision.approval_needed")
    if result.outcome is ComponentsOutcome.NOTHING_TO_DO and not usable:
        # Nothing could be set up, so the rows above say what holds each item.
        return tr("cli.config.provision.incomplete")
    key = _OUTCOME_LOCALE_KEYS.get(result.outcome)
    if key is not None:
        return tr(key)
    category = result.failure_category
    sentence = tr(dependency_failure_key(category)) if category is not None else tr("cli.config.provision.incomplete")
    if result.item_id is not None:
        sentence = f"{_name_of(result.item_id)}: {sentence}"
    if category is DependencyFailureCategory.DISK_FULL and result.plan is not None:
        sentence = f"{sentence} {_space_sentence(result.plan)}"
    return sentence


def emit_provision_setup(
    ctx: typer.Context,
    outcome: ComponentsResultLine,
    *,
    command: str,
    result_type: type[ProvisionSetupResult],
    approved: bool,
    needed_approval: bool = False,
    items: tuple[DependencyItemKind, ...] = (),
) -> None:
    """Emit a settled setup of ``items``, every item when empty; exit 2 unless each of them is usable."""
    plan = outcome.plan
    rows = outcome.status_rows()
    result = result_type(
        outcome=outcome.outcome.value,
        approved=approved,
        plan_digest=outcome.plan_digest,
        space=(
            None
            if plan is None
            else ProvisionSpacePayload(
                free_bytes=plan.space.free_bytes,
                required_bytes=plan.space.required_bytes,
                sufficient=plan.space.sufficient,
            )
        ),
        item_id=outcome.item_id,
        failure_category=None if outcome.failure_category is None else outcome.failure_category.value,
        complete=outcome.setup_complete is True,
        items=[_item_payload(row) for row in rows],
    )
    usable = _usable(rows, items)
    summary = _setup_summary(outcome, needed_approval=needed_approval, usable=usable)
    emit_envelope(ctx, command=command, result=result, lines=[*_row_lines(rows), summary])
    if outcome.outcome not in _SETUP_SUCCEEDED or not usable:
        raise typer.Exit(code=2)


# ── Running the local reader's operations ───────────────────────────────────


def _require_settled[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> None:
    if completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED or completed.refusal_code is not None:
        raise invalid_completion_error(completed)


# ── Local reader actions that download nothing ──────────────────────────────


def _local_reader(
    ctx: typer.Context, request: OperationRequest[LocalReaderProvisionRequest]
) -> LocalReaderProvisionPublicResultV3:
    completed = run_registered_operation(
        bound_profile_client(ctx),
        request.payload,
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        subject_ref=request.subject_ref,
        result_type=LocalReaderProvisionPublicResultV3,
        request_version=2,
        result_version=2,
        timeout=_CALL_TIMEOUT_S,
        settlement_timeout=_LOCAL_READER_SETTLEMENT_S,
        pending_check_command=_PENDING_CHECK_COMMAND,
    )
    _require_settled(completed)
    return completed.projection


def provision_start(ctx: typer.Context) -> None:
    """Start the installed local AI program when it is not already answering."""
    emit_provision_start(ctx, _local_reader(ctx, build_local_reader_start_request()))


def provision_remove(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Remove the named model, or the named role's model, from this computer."""
    if model is None and role is None:
        raise typer.BadParameter("--model or --role is required", param_hint="--model/--role")
    emit_provision_remove(ctx, _local_reader(ctx, build_local_reader_remove_request(role, model)))


def provision_load(
    ctx: typer.Context,
    model: str | None = None,
    role: ModelRole | None = None,
) -> None:
    """Load downloaded models into memory, refusing before the load when it is not admitted."""
    emit_provision_load(ctx, _local_reader(ctx, build_local_reader_load_request(role, model)))


def provision_report(ctx: typer.Context) -> None:
    """Report the measured hardware, the per-role model selection, and admission."""
    from ....application.local_reader_contracts import LOCAL_READER_OPERATION_SUBJECT

    completed = run_registered_operation(
        bound_profile_client(ctx),
        LocalReaderReportRequest(),
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        result_type=LocalReaderReportPublicResultV1,
        request_version=1,
        result_version=1,
        timeout=_CALL_TIMEOUT_S,
        settlement_timeout=_QUICK_SETTLEMENT_S,
        pending_check_command=_PENDING_CHECK_COMMAND,
    )
    _require_settled(completed)
    emit_provision_report(ctx, completed.projection)


def _licence_notices(result: LocalReaderProvisionPublicResultV3) -> tuple[Notice, ...]:
    advisories = (message for item in result.models for message in item.licence_advisories)
    return tuple(
        Notice(severity=NoticeSeverity.WARNING, code="provisioning.model.licence.non_commercial", message=message)
        for message in dict.fromkeys(advisories)
    )


def _action(verdict: PreconditionVerdict | None) -> ResolvedPreconditionAction | None:
    """Resolve an optional verdict through the shared action resolver."""
    return resolve_cli_precondition_action(verdict) if verdict is not None else None


def _reader_action(
    condition_id: str | None, verdict_facts: tuple[LocalReaderFactV1, ...]
) -> ResolvedPreconditionAction | None:
    """Resolve the refusal a reader result names by its condition and evidence facts."""
    from ....application.local_reader_contracts import local_reader_public_verdict

    return _action(local_reader_public_verdict(condition_id, verdict_facts))


def _reader_facts(facts: tuple[LocalReaderFactV1, ...]) -> dict[str, str | int | bool]:
    from ....application.local_reader_contracts import local_reader_fact_mapping

    return local_reader_fact_mapping(facts)


def _contention_payload(contention: LocalReaderContentionV1 | None) -> ProvisionContentionPayload | None:
    """Project a contention verdict onto its payload, preserving the cause set."""
    if contention is None:
        return None
    return ProvisionContentionPayload(
        model=contention.model,
        admitted=contention.admitted,
        causes=list(contention.causes),
        required_bytes=contention.required_bytes,
        free_vram_bytes=contention.free_vram_bytes,
        free_system_memory_bytes=contention.free_system_memory_bytes,
        shortfall_bytes=contention.shortfall_bytes,
        unloadable_models=list(contention.unloadable_models),
        facts=_reader_facts(contention.facts),
        precondition_action=_reader_action(contention.verdict_condition_id, contention.verdict_facts),
    )


def _roles(item: LocalReaderModelOutcomeV3) -> list[str]:
    return [role.value for role in item.roles]


def _item_action(item: LocalReaderModelOutcomeV3) -> ResolvedPreconditionAction | None:
    return _reader_action(item.verdict_condition_id, item.verdict_facts)


def _provision_result_lines(result: object) -> tuple[str, ...]:
    """Render the exact graph-resolved result DTO without recovery prose.

    The field names are schema identities, not human-authored guidance. Every
    value comes from the exact object emitted in JSON, so the text path cannot
    retain a second English detail or command hint.
    """
    from ....core.json_contract import OutputSchema

    if not isinstance(result, OutputSchema):  # pragma: no cover - defensive boundary guard
        raise TypeError("provisioning text rendering requires a graph-declared output schema")
    document = result.model_dump(mode="json")
    lines: list[str] = []
    for field_name, value in document.items():
        if field_name != "precondition_action":
            lines.append(
                f"{field_name}\t{json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}",
            )
            continue
        if value is not None:
            action = getattr(result, "precondition_action", None)
            if not isinstance(action, ResolvedPreconditionAction):  # pragma: no cover - defensive boundary guard
                raise TypeError("provisioning precondition action does not match the graph-resolved result DTO")
            lines.extend(precondition_action_lines(action))
    return tuple(lines)


def emit_provision_load(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV3) -> None:
    """Emit the load envelope, exiting 2 unless every resolved model is loaded."""
    items = [
        ProvisionLoadItemPayload(
            model=item.model,
            roles=_roles(item),
            loaded=item.succeeded,
            already_loaded=item.already_satisfied,
            elapsed_ms=item.elapsed_ms,
            facts=_reader_facts(item.facts),
            precondition_action=_item_action(item),
        )
        for item in outcome.models
    ]
    result = ProvisionLoadResult(loaded=outcome.succeeded, models=items)
    emit_envelope(
        ctx,
        command="config.provision.load",
        result=result,
        lines=_provision_result_lines(result),
        notices=_licence_notices(outcome),
    )
    if not result.loaded:
        raise typer.Exit(code=2)


def emit_provision_report(ctx: typer.Context, report: LocalReaderReportPublicResultV1) -> None:
    """Emit the measured hardware, the per-role model selection and the admission verdict."""
    result = ProvisionReportResult(
        accelerator=report.accelerator.value,
        total_vram_bytes=report.total_vram_bytes,
        free_vram_bytes=report.free_vram_bytes,
        total_system_memory_bytes=report.total_system_memory_bytes,
        free_system_memory_bytes=report.free_system_memory_bytes,
        runtime_reachable=report.runtime_reachable,
        residents=list(report.residents),
        models=[
            ProvisionModelPayload(
                role=row.role.value,
                model=row.model,
                selected=row.selected,
                resident=row.resident,
                facts=_reader_facts(row.facts),
                precondition_action=_reader_action(row.verdict_condition_id, row.verdict_facts),
            )
            for row in report.models
        ],
        contention=_contention_payload(report.contention),
    )
    emit_envelope(ctx, command="config.provision.report", result=result, lines=_provision_result_lines(result))


def emit_provision_start(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV3) -> None:
    """Emit the start envelope, exiting 2 unless the local AI program answers."""
    result = ProvisionStartResult(
        running=outcome.succeeded,
        already_running=outcome.already_running,
        started_pid=outcome.started_pid,
        facts=_reader_facts(outcome.facts),
        precondition_action=_reader_action(outcome.verdict_condition_id, outcome.verdict_facts),
    )
    emit_envelope(ctx, command="config.provision.start", result=result, lines=_provision_result_lines(result))
    if not result.running:
        raise typer.Exit(code=2)


def emit_provision_remove(ctx: typer.Context, outcome: LocalReaderProvisionPublicResultV3) -> None:
    """Emit the remove envelope, exiting 2 unless every removal was confirmed."""
    items = [
        ProvisionRemoveItemPayload(
            model=item.model,
            roles=_roles(item),
            removed=item.succeeded,
            was_installed=item.was_installed,
            freed_bytes=item.freed_bytes,
            facts=_reader_facts(item.facts),
            precondition_action=_item_action(item),
        )
        for item in outcome.models
    ]
    result = ProvisionRemoveResult(removed=outcome.succeeded, models=items)
    emit_envelope(ctx, command="config.provision.remove", result=result, lines=_provision_result_lines(result))
    if not result.removed:
        raise typer.Exit(code=2)
