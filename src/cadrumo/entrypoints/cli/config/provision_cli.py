"""``aeat config provision`` -- set up and check what Cadrumo needs on this computer.

Every verb submits a registered operation through the runtime, in the
signed-in profile's session, so the command line, the terminal interface and
MCP make the same decision and get the same result:

* **status** -- the quick check of every setup item (``dependencies.status``,
  quick): local facts only, no network, no model load.
* **probe** -- the full check of every item (``dependencies.status``, full).
* **verify** -- the full check of the named item, or of every item
  (``dependencies.verify``).
* **setup**, **browser**, **pull** -- ``dependencies.setup`` for every item
  that is not ready, the browser, or the local AI (its program and every
  role's model, as one item). Each prints the plan the operation raises for
  review and asks; ``--yes`` approves the printed plan. Without ``--yes`` and
  without a terminal to ask on, the plan is rejected and nothing moves.
* **report** -- the measured machine and model selection (``local-reader.report``).
* **start**, **load**, **remove** -- the local reader's actions that download
  nothing (``local-reader.provision``).

While a setup runs, text mode draws one progress line on standard error and
JSON mode writes each relayed event there as one JSON line, so standard output
carries only the closing envelope. A row's text names its plain sentence and,
when the row offers a recovery, the exact command that performs it.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal

import typer
from pydantic import BaseModel

from cadrumo_client.commands.output import write_stderr
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationReviewHandler,
)
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.contracts.command_program import CommandProgram
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_ids import (
    DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
    LOCAL_READER_OPERATION_DEFINITION_ID,
)

from ....application.dependency_contracts import (
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyItemKind,
    DependencySetupStep,
    DependencyState,
    DependencyStatusRow,
    dependency_item_kind,
    parse_dependency_retry_notice,
)
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DEPENDENCIES_SETUP_RESPONSE_SCHEMA,
    DEPENDENCIES_SETUP_REVIEW_SCHEMA,
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
    DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID,
    DependencySetupOutcome,
    DependencySetupRequest,
    DependencySetupResultV1,
    DependencySetupReviewV2,
    DependencyStatusRequest,
    DependencyStatusResultV1,
    DependencyVerifyRequest,
)
from ....application.dependency_wording import (
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
from ....application.operations.frontend_requests import (
    OperationPublicEventPageV1,
    OperationPublicNoticeEventV1,
    OperationPublicPhaseEventV1,
    OperationPublicProgressEventV1,
)
from ....application.operations.persistence.replay import OperationReplayStatus
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_surface.action_targets import ACTION_TARGETS
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity, ResolvedPreconditionAction
from ....core.model_catalogue import ModelRole
from ....core.operations import OperationTerminalCondition
from ....core.output_rendering import OutputFormat
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
    ProvisionSetupItemPayload,
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
    from ....application.operations.frontend_projection import OperationReviewProjectionReferenceV1
    from ....application.operations.models import OperationRequest
    from ....application.operator_actions.models import PreconditionVerdict

__all__ = [
    "SetupProgressLine",
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
    "recovery_command",
    "setup_review_handler",
    "verify_item_ids",
]

_CALL_TIMEOUT_S: Final = 120.0
# Each settlement wait is at least the call timeout, which the client requires.
_QUICK_SETTLEMENT_S: Final = _CALL_TIMEOUT_S
_FULL_SETTLEMENT_S: Final = 900.0
_SETUP_SETTLEMENT_S: Final = 3600.0
_LOCAL_READER_SETTLEMENT_S: Final = 900.0
_PENDING_CHECK_COMMAND: Final = "aeat config provision status"
_SETUP_PHASE_PREFIX: Final = "dependencies.setup."
_MIB: Final = 1024**2
_GIB: Final = 1024**3


# ── Item selection ──────────────────────────────────────────────────────────


def _declaration(item_id: str) -> DependencyItemDeclaration:
    for declaration in dependency_item_declarations():
        if declaration.item_id == item_id:
            return declaration
    raise KeyError(item_id)


def _declaration_of(kind: DependencyItemKind) -> DependencyItemDeclaration:
    return next(declaration for declaration in dependency_item_declarations() if declaration.kind is kind)


def verify_item_ids(item: str | None) -> tuple[str, ...] | None:
    """Return the items a verify checks: the named item, or every item (``None``)."""
    if item is None:
        return None
    known = {declaration.item_id for declaration in dependency_item_declarations()}
    if item not in known:
        raise typer.BadParameter(f"choose one of: {', '.join(sorted(known))}", param_hint="--item")
    return (item,)


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


# ── Running the operations ──────────────────────────────────────────────────


def _require_settled[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> None:
    if completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED or completed.refusal_code is not None:
        raise invalid_completion_error(completed)


def _status(ctx: typer.Context, request: DependencyStatusRequest | DependencyVerifyRequest) -> DependencyStatusResultV1:
    verify = isinstance(request, DependencyVerifyRequest)
    quick = isinstance(request, DependencyStatusRequest) and request.mode is DependencyCheckMode.QUICK
    completed = run_registered_operation(
        bound_profile_client(ctx),
        request,
        definition_id=DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID
        if verify
        else DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        result_type=DependencyStatusResultV1,
        request_version=1,
        result_version=1,
        timeout=_CALL_TIMEOUT_S,
        settlement_timeout=_QUICK_SETTLEMENT_S if quick else _FULL_SETTLEMENT_S,
        pending_check_command=_PENDING_CHECK_COMMAND,
    )
    _require_settled(completed)
    return completed.projection


def provision_status(ctx: typer.Context) -> None:
    """Report every setup item's state from what this computer already has."""
    status = _status(ctx, DependencyStatusRequest(mode=DependencyCheckMode.QUICK))
    emit_provision_status(ctx, status, command="config.provision.status", result_type=ProvisionStatusResult)


def provision_probe(ctx: typer.Context) -> None:
    """Report every setup item's state from its full check."""
    status = _status(ctx, DependencyStatusRequest(mode=DependencyCheckMode.FULL))
    emit_provision_status(ctx, status, command="config.provision.probe", result_type=ProvisionProbeResult)


def provision_verify(ctx: typer.Context, item: str | None = None) -> None:
    """Fully check the named item, or every item; exit 2 unless each is usable."""
    status = _status(ctx, DependencyVerifyRequest(item_ids=verify_item_ids(item)))
    emit_provision_status(ctx, status, command="config.provision.verify", result_type=ProvisionVerifyResult)
    if not all(row.state in {DependencyState.READY, DependencyState.STALE} for row in status.rows):
        raise typer.Exit(code=2)


def provision_setup(ctx: typer.Context, yes: bool = False) -> None:
    """Set up every item that is not ready, after the person approves the printed plan."""
    _setup(ctx, DependencySetupRequest(), yes=yes, command="config.provision.setup", result_type=ProvisionSetupResult)


def provision_browser(ctx: typer.Context, yes: bool = False) -> None:
    """Set up the browser Cadrumo uses for the tax agency website."""
    request = DependencySetupRequest(item_ids=(_declaration_of(DependencyItemKind.BROWSER).item_id,))
    _setup(ctx, request, yes=yes, command="config.provision.browser", result_type=ProvisionBrowserResult)


def provision_pull(ctx: typer.Context, model: str | None = None, yes: bool = False) -> None:
    """Set up the local AI: its program when missing, then every role's model, optionally naming the model."""
    local_ai = _declaration_of(DependencyItemKind.LOCAL_AI).item_id
    request = DependencySetupRequest(item_ids=(local_ai,), model_name=model)
    _setup(ctx, request, yes=yes, command="config.provision.pull", result_type=ProvisionPullResult)


@dataclass(slots=True)
class _SetupDecision:
    """What the review handler saw and decided, kept for correlating the settled result."""

    review: DependencySetupReviewV2 | None = None
    approved: bool = False
    needed_approval: bool = False


def _can_ask(ctx: typer.Context) -> bool:
    return format_of(ctx) is OutputFormat.TEXT and stdin_is_tty() and stderr_is_tty()


def _plan_lines(review: DependencySetupReviewV2) -> list[str]:
    lines = [tr("cli.config.provision.plan.heading")]
    for view in review.entries:
        entry = view.entry
        size = (
            tr("cli.config.provision.plan.size_unknown")
            if entry.download_bytes is None
            else _size(entry.download_bytes)
        )
        lines.append(
            tr(
                "cli.config.provision.plan.entry",
                name=_name_of(entry.item_id),
                size=size,
                hosts=", ".join(entry.source_hosts),
            )
        )
        for part in view.parts:
            part_size = (
                tr("cli.config.provision.plan.size_unknown")
                if part.download_bytes is None
                else _size(part.download_bytes)
            )
            lines.append(tr("cli.config.provision.plan.part", name=part.name, size=part_size))
        if view.shares_download_with is not None:
            lines.append(tr("cli.config.provision.plan.shared", name=_name_of(view.shares_download_with)))
        if view.destination_path is not None:
            lines.append(tr("cli.config.provision.plan.destination", path=view.destination_path))
        if entry.installs_outside_program:
            lines.append(tr("cli.config.provision.plan.installs_program"))
        if view.licence_notice is not None:
            lines.append(f"  {view.licence_notice}")
    total = _size(review.known_download_bytes)
    lines.append(
        tr(
            "cli.config.provision.plan.total_unknown" if review.has_unknown_size else "cli.config.provision.plan.total",
            size=total,
        )
    )
    if not review.space_sufficient:
        free = "?" if review.space.free_bytes is None else _size(review.space.free_bytes)
        lines.append(dependency_space_sentence(required=_size(review.space.required_bytes), free=free))
    return lines


def _plan_document(review: DependencySetupReviewV2) -> str:
    """Return the plan as one JSON line, the shape JSON mode writes on standard error."""
    document = {
        "event": "plan",
        "plan_digest": review.plan_digest,
        "entries": [
            {
                "item_id": view.entry.item_id,
                "download_bytes": view.entry.download_bytes,
                "source_hosts": list(view.entry.source_hosts),
                "destination_path": view.destination_path,
                "installs_outside_program": view.entry.installs_outside_program,
                "shares_download_with": view.shares_download_with,
                "licence_notice": view.licence_notice,
            }
            for view in review.entries
        ],
        "known_download_bytes": review.known_download_bytes,
        "has_unknown_size": review.has_unknown_size,
        "free_bytes": review.space.free_bytes,
        "required_bytes": review.space.required_bytes,
        "space_sufficient": review.space_sufficient,
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def setup_review_handler(
    *, yes: bool, ask: bool, json_mode: bool = False, decision: _SetupDecision | None = None
) -> RegisteredOperationReviewHandler[DependencySetupReviewV2]:
    """Return the handler that prints the plan and answers it: ``--yes``, a terminal answer, or reject.

    The plan, with any licence notice of a model it would download, is always
    written on standard error first: plain lines in text mode, one JSON line
    in JSON mode. ``--yes`` approves exactly that plan, notices included.
    Without ``--yes`` and without a terminal to ask on, the plan is rejected,
    so the operation settles with nothing downloaded and the command says
    approval is needed.
    """
    seen = _SetupDecision() if decision is None else decision

    def decide(review: DependencySetupReviewV2) -> Literal["apply", "reject"]:
        if review.identity.definition_id != DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        seen.review = review
        if json_mode:
            write_stderr(_plan_document(review))
        else:
            for line in _plan_lines(review):
                write_stderr(line)
        if yes or (ask and typer.confirm(tr("cli.config.provision.approve_prompt"), default=False, err=True)):
            seen.approved = True
            return "apply"
        seen.needed_approval = not ask
        return "reject"

    def validate_reference(review: DependencySetupReviewV2, reference: OperationReviewProjectionReferenceV1) -> None:
        if review.identity.operation_id != reference.operation_id or review.revision != reference.revision:
            raise RefusalError(RefusalCode.INVALID_FRAME)

    return RegisteredOperationReviewHandler(
        review_type=DependencySetupReviewV2,
        review_schema=DEPENDENCIES_SETUP_REVIEW_SCHEMA.identity,
        response_schema=DEPENDENCIES_SETUP_RESPONSE_SCHEMA.identity,
        decide=decide,
        validate_reference=validate_reference,
    )


def _setup(
    ctx: typer.Context,
    request: DependencySetupRequest,
    *,
    yes: bool,
    command: str,
    result_type: type[ProvisionSetupResult],
) -> None:
    decision = _SetupDecision()
    progress = SetupProgressLine(json_mode=format_of(ctx) is OutputFormat.JSON, interactive=stderr_is_tty())
    try:
        completed = run_registered_operation(
            bound_profile_client(ctx),
            request,
            definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
            subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
            result_type=DependencySetupResultV1,
            request_version=1,
            result_version=1,
            timeout=_CALL_TIMEOUT_S,
            settlement_timeout=_SETUP_SETTLEMENT_S,
            pending_check_command=_PENDING_CHECK_COMMAND,
            review=setup_review_handler(
                yes=yes, ask=_can_ask(ctx), json_mode=format_of(ctx) is OutputFormat.JSON, decision=decision
            ),
            on_events=progress.observe,
        )
    finally:
        progress.finish()
    if not isinstance(completed, RegisteredOperationCompletion):
        # The handler always decides, so a detached review is a broken exchange.
        raise RefusalError(RefusalCode.INVALID_FRAME)
    _require_settled(completed)
    result = completed.projection
    reviewed = decision.review
    correlated = {DependencySetupOutcome.COMPLETED, DependencySetupOutcome.REJECTED}
    if (
        reviewed is not None
        and result.plan_digest is not None
        and result.outcome in correlated
        and (result.plan_digest != reviewed.plan_digest or completed.operation_id != reviewed.identity.operation_id)
    ):
        raise invalid_completion_error(completed)
    emit_provision_setup(
        ctx,
        result,
        command=command,
        result_type=result_type,
        approved=decision.approved,
        needed_approval=decision.needed_approval,
    )


# ── Progress ────────────────────────────────────────────────────────────────


def _setup_phase(phase_code: str) -> tuple[str, DependencySetupStep] | None:
    if not phase_code.startswith(_SETUP_PHASE_PREFIX):
        return None
    item_id, _, step = phase_code.removeprefix(_SETUP_PHASE_PREFIX).rpartition(".")
    try:
        dependency_item_kind(item_id)
        return item_id, DependencySetupStep(step)
    except ValueError:
        return None


@dataclass(slots=True)
class SetupProgressLine:
    """Draw a setup's progress on standard error from the events the operation publishes.

    On a terminal the line is redrawn in place; otherwise a line is written
    when an item enters a step. JSON mode writes each relayed event as one JSON
    object per line instead. Nothing here decides settlement.
    """

    json_mode: bool
    interactive: bool
    _drawn: bool = False
    _last: dict[str, str] = field(default_factory=dict)

    def observe(self, page: OperationPublicEventPageV1) -> None:
        """Render every setup event of one observed page."""
        if page.status is not OperationReplayStatus.PAGE:
            return
        for event in page.events:
            if isinstance(event, OperationPublicPhaseEventV1):
                phase = _setup_phase(event.phase_code)
                if phase is not None:
                    self._step(*phase)
            elif isinstance(event, OperationPublicProgressEventV1) and event.subject_code is not None:
                self._bytes(event.subject_code, event.completed, event.total)
            elif isinstance(event, OperationPublicNoticeEventV1):
                retry = parse_dependency_retry_notice(event.notice_code)
                if retry is not None:
                    self._retry(*retry)

    def _step(self, item_id: str, step: DependencySetupStep) -> None:
        if self.json_mode:
            self._json({"event": "step", "item_id": item_id, "step": step.value})
            return
        text = tr(
            "cli.config.provision.progress", name=_name_of(item_id), step=tr(f"cli.config.provision.step.{step.value}")
        )
        if self._last.get(item_id) == text:
            return
        self._last[item_id] = text
        self._draw(text, settled=not self.interactive)

    def _bytes(self, item_id: str, completed: int, total: int) -> None:
        if self.json_mode:
            self._json({"event": "progress", "item_id": item_id, "completed": completed, "total": total})
            return
        if not self.interactive:
            return
        percent = min(100, completed * 100 // total)
        self._draw(
            tr(
                "cli.config.provision.progress_bytes",
                name=_name_of(item_id),
                done=_size(completed),
                total=_size(total),
                percent=percent,
            ),
            settled=False,
        )

    def _retry(self, item_id: str, attempt: int, delay_s: int) -> None:
        if self.json_mode:
            self._json({"event": "retry", "item_id": item_id, "attempt": attempt, "delay_s": delay_s})
            return
        self._draw(
            f"{_name_of(item_id)}: {dependency_retry_sentence(attempt=attempt, delay_s=delay_s)}",
            settled=True,
        )

    def _json(self, document: dict[str, object]) -> None:
        write_stderr(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

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
    status: DependencyStatusResultV1,
    *,
    command: str,
    result_type: type[ProvisionStatusResult],
) -> None:
    """Emit every requested item's row under ``command``."""
    result = result_type(
        mode=status.mode.value,
        complete=status.complete,
        hardware_limited=status.hardware_limited,
        items=[_item_payload(row) for row in status.rows],
    )
    lines = _row_lines(status.rows)
    if status.hardware_limited:
        lines.append(tr("cli.config.provision.hardware_limited"))
    lines.append(tr("cli.config.provision.complete" if status.complete else "cli.config.provision.incomplete"))
    emit_envelope(ctx, command=command, result=result, lines=lines)


_SUCCESSFUL_OUTCOMES: Final = frozenset({DependencySetupOutcome.COMPLETED, DependencySetupOutcome.NOTHING_TO_DO})


def emit_provision_setup(
    ctx: typer.Context,
    outcome: DependencySetupResultV1,
    *,
    command: str,
    result_type: type[ProvisionSetupResult],
    approved: bool,
    needed_approval: bool = False,
) -> None:
    """Emit a settled setup, exiting 2 unless it completed with every item usable."""
    space = outcome.space
    result = result_type(
        outcome=outcome.outcome.value,
        approved=approved,
        plan_digest=outcome.plan_digest,
        space=(
            None
            if space is None
            else ProvisionSpacePayload(
                free_bytes=space.free_bytes, required_bytes=space.required_bytes, sufficient=space.sufficient
            )
        ),
        results=[
            ProvisionSetupItemPayload(
                item_id=item.item_id,
                changed=item.changed,
                failure_category=None if item.failure_category is None else item.failure_category.value,
                transferred_bytes=item.transferred_bytes,
            )
            for item in outcome.items
        ],
        complete=outcome.complete,
        items=[_item_payload(row) for row in outcome.rows],
    )
    if needed_approval and outcome.outcome is DependencySetupOutcome.REJECTED:
        summary = tr("cli.config.provision.approval_needed")
    else:
        summary = tr(f"cli.config.provision.outcome.{outcome.outcome.value}")
    if outcome.outcome is DependencySetupOutcome.NOT_ENOUGH_SPACE and space is not None:
        free = "?" if space.free_bytes is None else _size(space.free_bytes)
        summary = f"{summary} {dependency_space_sentence(required=_size(space.required_bytes), free=free)}"
    emit_envelope(ctx, command=command, result=result, lines=[*_row_lines(outcome.rows), summary])
    failed = any(item.failure_category is not None for item in outcome.items)
    if outcome.outcome not in _SUCCESSFUL_OUTCOMES or failed:
        raise typer.Exit(code=2)


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
