"""``aeat config provision`` -- set up and check what Cadrumo needs on this computer.

The component verbs submit registered operations in the signed-in profile.
The native component engine decides each component's state and setup plan;
the command line words the public results and relays operation events:

* **status** -- the quick check of every component: local facts only, no
  network, no model load.
* **probe** -- the full check of every component.
* **verify** -- the full check of the named component, or of every one.
* **setup**, **browser** -- set up every component this command line can set
  up, or the browser. That is the browser alone: only the Cadrumo desktop app
  sets up or removes the local AI, so a row for it ends with a pointer to the
  desktop. Each prints the plan the role asks to approve and asks; ``--yes``
  approves exactly the printed plan. Without ``--yes`` and without a terminal
  to ask on, the plan is declined, nothing moves and the command says it needs
  your approval. A setup that finds its component already being set up
  elsewhere follows that setup instead: it asks nothing, relays its progress
  and reports its result.
* **remove** -- delete the browser from this computer. It asks first;
  ``--yes`` confirms without asking. Without ``--yes`` and without a terminal
  to ask on, nothing is removed and the command says it needs your
  confirmation.

Where this build has no Cadrumo binary, every component reads as not in this
build. The local AI's server is the runtime manager's to start and stop, so
no command here starts it. **report** is the local reader's read, submitted
as a registered operation in the signed-in profile: it reports the measured
hardware and the lane the person selected for each role.

While a setup runs, text mode draws one progress line on standard error and
JSON mode writes public operation events there as JSON objects, so
standard output carries only the closing envelope. A row's text names its
plain sentence and, when the row offers a recovery, the exact command that
performs it, or the pointer to the desktop app for the local AI.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID, uuid4

import typer
from pydantic import BaseModel, TypeAdapter, ValidationError

from cadrumo_client.commands.output import write_stderr
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_admission import require_registered_review_contract
from cadrumo_client.commands.registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationProgress,
    RegisteredOperationReviewHandler,
)
from cadrumo_client.commands.registered_operation_deadlines import (
    RegisteredOperationDeadline,
    RegisteredOperationSettlement,
)
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.commands.registered_operation_exchange import RegisteredOperationExchange
from cadrumo_client.commands.registered_operation_observations import observe_registered_operation
from cadrumo_client.commands.registered_operation_reviews import respond_registered_pending_review
from cadrumo_client.contracts.command_program import CommandProgram
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_access import (
    OperationReply,
    OperationRequest,
    OperationReviewClaim,
    OperationReviewClaimed,
)

from ....application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_REMOVE_OPERATION_ID,
    COMPONENTS_SETUP_OPERATION_ID,
    COMPONENTS_STATUS_OPERATION_ID,
    COMPONENTS_VERIFY_OPERATION_ID,
    PROVISION_RESPONSE_SCHEMA,
    PROVISION_REVIEW_SCHEMA,
    ProvisionMutationRequest,
    ProvisionOutcome,
    ProvisionPlan,
    ProvisionReadRequest,
    ProvisionResult,
    ProvisionReviewProjection,
)
from ....application.dependency_contracts import (
    DEPENDENCY_SETUP_RECOVERIES,
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencyState,
    DependencyStatusRow,
)
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_wording import (
    dependency_desktop_pointer,
    dependency_failure_key,
    dependency_row_wording,
    dependency_space_sentence,
)
from ....application.local_reader_report import (
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
    LocalReaderReportPublicResultV1,
    LocalReaderReportRequest,
)
from ....application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from ....application.operations.frontend_requests import (
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationPublicProgressEventV1,
)
from ....application.operations.models import OperationId
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_surface.action_targets import ACTION_TARGETS
from ....core.hashing import content_hash_hex
from ....core.i18n.render import tr
from ....core.json_contract import ResolvedPreconditionAction
from ....core.operations import OperationTerminalCondition
from ....core.output_rendering import OutputFormat
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from ....core.tty import stderr_is_tty, stdin_is_tty
from ..common import emit_envelope, format_of, resolve_cli_precondition_action
from ..component_recovery_text import component_status_command
from ..errors import redraw_stderr_line
from ..errors import write_stderr as draw_stderr
from .provision_payloads import (
    ProvisionBrowserResult,
    ProvisionItemPayload,
    ProvisionModelPayload,
    ProvisionProbeResult,
    ProvisionRemoveResult,
    ProvisionReportResult,
    ProvisionReviewResult,
    ProvisionSetupResult,
    ProvisionSpacePayload,
    ProvisionStatusResult,
    ProvisionVerifyResult,
)
from .status_rendering import precondition_action_lines

if TYPE_CHECKING:
    from ....application.local_reader_contracts import LocalReaderFactV1
    from ....application.operator_actions.models import PreconditionVerdict

__all__ = [
    "SetupProgressLine",
    "SetupReview",
    "emit_provision_remove",
    "emit_provision_report",
    "emit_provision_setup",
    "emit_provision_status",
    "provision_browser",
    "provision_probe",
    "provision_remove",
    "provision_report",
    "provision_setup",
    "provision_status",
    "provision_verify",
    "read_quick_setup_rows",
    "recovery_command",
    "remove_item",
    "verify_items",
]

_CALL_TIMEOUT_S: Final = 120.0
# Each settlement wait is at least the call timeout, which the client requires.
_QUICK_SETTLEMENT_S: Final = _CALL_TIMEOUT_S
_PENDING_CHECK_COMMAND: Final = "aeat config provision status"
_MIB: Final = 1024**2
_GIB: Final = 1024**3

_OUTCOME_LOCALE_KEYS: Final = {
    ProvisionOutcome.COMPLETED: "cli.config.provision.outcome.completed",
    ProvisionOutcome.NOTHING_TO_DO: "cli.config.provision.outcome.nothing_to_do",
    ProvisionOutcome.NEEDS_APPROVAL: "cli.config.provision.outcome.rejected",
    ProvisionOutcome.REJECTED: "cli.config.provision.outcome.rejected",
    ProvisionOutcome.PLAN_CHANGED: "cli.config.provision.outcome.plan_changed",
    ProvisionOutcome.CANCELLED: "cli.config.provision.outcome.cancelled",
    ProvisionOutcome.BUSY: "cli.config.provision.outcome.busy",
}
"""The summary of each setup outcome that names no failure; a refusal or failure says its category's sentence."""

_SETUP_SUCCEEDED: Final = frozenset({ProvisionOutcome.COMPLETED, ProvisionOutcome.NOTHING_TO_DO})


# ── Item selection ──────────────────────────────────────────────────────────


def _declaration(item_id: str) -> DependencyItemDeclaration:
    for declaration in dependency_item_declarations():
        if declaration.item_id == item_id:
            return declaration
    raise KeyError(item_id)


def _item_kind(
    item: str, *, param_hint: str, allowed: tuple[DependencyItemKind, ...] = tuple(DependencyItemKind)
) -> DependencyItemKind:
    named = next((kind for kind in allowed if kind.value == item), None)
    if named is None:
        known = ", ".join(kind.value for kind in allowed)
        raise typer.BadParameter(f"choose one of: {known}", param_hint=param_hint)
    return named


def verify_items(item: str | None) -> tuple[DependencyItemKind, ...]:
    """Return the items a verify checks: the named item, or every item (empty)."""
    if item is None:
        return ()
    return (_item_kind(item, param_hint="--item"),)


def remove_item(item: str) -> DependencyItemKind:
    """Return the item a removal deletes: only the browser, because only the desktop removes the local AI."""
    return _item_kind(item, param_hint="ITEM", allowed=(DependencyItemKind.BROWSER,))


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
        version=row.version,
        size_estimate_bytes=row.size_estimate_bytes,
        recovery=None if row.recovery is None else row.recovery.value,
        recovery_action_id=action_id,
        command=_row_command(row),
    )


def _row_command(row: DependencyStatusRow) -> str | None:
    if row.kind is DependencyItemKind.LOCAL_AI or row.state is DependencyState.BLOCKED:
        return None
    if row.recovery is DependencyRecoveryAction.CHECK_AGAIN:
        return component_status_command()
    if row.recovery in DEPENDENCY_SETUP_RECOVERIES and row.recovery_action_id is not None:
        return recovery_command(row.recovery_action_id)
    return None


def _row_lines(rows: Iterable[DependencyStatusRow]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        declaration = _declaration(row.item_id)
        wording = dependency_row_wording(row, declaration)
        lines.append(f"{wording.name}\t{wording.sentence}")
        if row.kind is DependencyItemKind.LOCAL_AI and row.state not in {DependencyState.READY, DependencyState.STALE}:
            lines.append("\t" + dependency_desktop_pointer())
        elif (command := _row_command(row)) is not None:
            key = (
                "cli.config.provision.check_status"
                if row.recovery is DependencyRecoveryAction.CHECK_AGAIN
                else "cli.config.provision.fix"
            )
            lines.append("\t" + tr(key, command=command))
    return lines


def _space_sentence(plan: ProvisionPlan) -> str:
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


def _plan_lines(plan: ProvisionPlan) -> list[str]:
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
        destination = _destination_line(entry.destination)
        if destination is not None:
            lines.append(destination)
        if entry.installs_outside_program:
            lines.append(tr("cli.config.provision.plan.installs_program"))
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
    """Encode a public operation event for JSON mode's standard error."""
    return json.dumps(
        line.model_dump(mode="json", exclude_unset=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


# ── Reading every item's state ──────────────────────────────────────────────


def _read(ctx: typer.Context, items: tuple[DependencyItemKind, ...] = (), *, full: bool = False) -> ProvisionResult:
    progress = SetupProgressLine(json_mode=format_of(ctx) is OutputFormat.JSON, interactive=stderr_is_tty())
    try:
        completed = run_registered_operation(
            bound_profile_client(ctx),
            ProvisionReadRequest(items=items),
            definition_id=COMPONENTS_VERIFY_OPERATION_ID if full else COMPONENTS_STATUS_OPERATION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            result_type=ProvisionResult,
            request_version=1,
            result_version=1,
            timeout=_CALL_TIMEOUT_S,
            settlement_timeout=RegisteredOperationSettlement.UNBOUNDED if full else _QUICK_SETTLEMENT_S,
            pending_check_command=_PENDING_CHECK_COMMAND,
            on_events=progress.observe if full else None,
        )
    finally:
        progress.finish()
    _require_settled(completed)
    result = completed.projection
    if result.outcome is not ProvisionOutcome.OK and result.failure_category is None:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return result


def read_quick_setup_rows(ctx: typer.Context) -> tuple[DependencyStatusRow, ...]:
    """Read component status through the invocation's signed-in profile."""
    result = _read(ctx)
    if result.outcome is not ProvisionOutcome.OK:
        raise RefusalError(RefusalCode.UNAVAILABLE, check="components_role_refused_the_check")
    return result.rows


def provision_status(ctx: typer.Context) -> None:
    """Report every setup item's state from what this computer already has; exit 2 on a refused check."""
    status = _read(ctx)
    emit_provision_status(ctx, status, command="config.provision.status", result_type=ProvisionStatusResult, full=False)
    _exit_on_refused_check(status)


def provision_probe(ctx: typer.Context) -> None:
    """Report every setup item's state from its full check; exit 2 on a refused check."""
    status = _read(ctx, full=True)
    emit_provision_status(ctx, status, command="config.provision.probe", result_type=ProvisionProbeResult, full=True)
    _exit_on_refused_check(status)


def _exit_on_refused_check(status: ProvisionResult) -> None:
    """Leave a check the engine refused itself with the status its refusal path uses.

    A reading command exits 0, but a check that could not be read is not a
    computer with nothing set up, and a scripted caller must be able to tell
    them apart by the exit code and not only by the envelope's category.
    """
    if status.failure_category is not None:
        raise typer.Exit(code=2)


def provision_verify(ctx: typer.Context, item: str | None = None) -> None:
    """Fully check the named item, or every item; exit 2 unless each is usable."""
    status = _read(ctx, verify_items(item), full=True)
    emit_provision_status(ctx, status, command="config.provision.verify", result_type=ProvisionVerifyResult, full=True)
    usable = all(row.state in {DependencyState.READY, DependencyState.STALE} for row in status.rows)
    if status.failure_category is not None or not usable:
        raise typer.Exit(code=2)


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


def _can_ask(ctx: typer.Context) -> bool:
    return format_of(ctx) is OutputFormat.TEXT and stdin_is_tty() and stderr_is_tty()


@dataclass(slots=True)
class SetupReview:
    """Print the plan the role asks to approve, then answer it: ``--yes``, a terminal answer, or decline.

    The plan is always written on standard error first: plain lines in text
    mode, the public review document in JSON mode. ``--yes`` approves exactly
    the printed plan's digest. Without ``--yes`` and without a terminal to ask on, the plan is
    declined, so nothing moves and the command says approval is needed.
    """

    yes: bool
    ask: bool
    json_mode: bool = False
    reviewed: ProvisionReviewProjection | None = None
    approved: bool = False
    needed_approval: bool = False

    def decide(self, review: ProvisionReviewProjection) -> Literal["apply", "reject"]:
        """Answer one review."""
        self.reviewed = review
        if not self.json_mode:
            for line in _plan_lines(review.plan):
                write_stderr(line)
        if self.yes or (self.ask and typer.confirm(tr("cli.config.provision.approve_prompt"), default=False, err=True)):
            self.approved = True
            return "apply"
        self.needed_approval = not self.ask
        return "reject"


def _claim_review(
    pending: OperationReviewAvailableInteractionV1,
    document: Mapping[str, object],
    profile_id: UUID,
    session_id: UUID,
    exchange: Callable[[OperationRequest], OperationReply],
) -> OperationReviewAvailableInteractionV1:
    """Claim the exact displayed review and use only its returned successor coordinates."""
    reference = pending.review_reference
    digest = content_hash_hex(document)
    reply = exchange(
        OperationReviewClaim(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            reference=reference,
            reviewed_document_digest=digest,
        )
    )
    if not isinstance(reply, OperationReviewClaimed) or reply.reviewed_document_digest != digest:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    successor = reply.reference
    if (
        successor.operation_id != reference.operation_id
        or successor.interaction_id != reference.interaction_id
        or successor.review_projection_schema != reference.review_projection_schema
        or successor.definition_contract_digest != reference.definition_contract_digest
        or successor.expires_at != reference.expires_at
        or successor.revision not in (reference.revision, reference.revision + 1)
        or not {"apply", "reject"}.issubset(reply.allowed_intents)
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return pending.model_copy(update={"revision": successor.revision, "review_reference": successor})


def _review_handler(review: SetupReview) -> RegisteredOperationReviewHandler[ProvisionReviewProjection]:
    return RegisteredOperationReviewHandler(
        review_type=ProvisionReviewProjection,
        review_schema=PROVISION_REVIEW_SCHEMA.identity,
        response_schema=PROVISION_RESPONSE_SCHEMA.identity,
        decide=review.decide,
        claim=_claim_review,
        present_document=(lambda document: write_stderr(json.dumps(document, ensure_ascii=False, sort_keys=True)))
        if review.json_mode
        else None,
    )


def provision_review(ctx: typer.Context, operation_id: str, yes: bool = False, reject: bool = False) -> None:
    """Display, claim and answer the current review of an existing setup operation."""
    if yes and reject:
        raise typer.BadParameter("--yes and --reject cannot be combined")
    if not yes and not reject and not _can_ask(ctx):
        raise typer.BadParameter("use --yes or --reject when a prompt is unavailable")
    try:
        target = TypeAdapter(OperationId).validate_python(operation_id, strict=True)
    except ValidationError:
        raise typer.BadParameter("invalid operation ID", param_hint="OPERATION_ID") from None
    client = bound_profile_client(ctx)
    budget = RegisteredOperationDeadline(None, _CALL_TIMEOUT_S, RegisteredOperationSettlement.UNBOUNDED)
    contract = client.contract(COMPONENTS_SETUP_OPERATION_ID, deadline=budget.call_deadline())
    if contract.definition_id != COMPONENTS_SETUP_OPERATION_ID:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    progress = RegisteredOperationProgress()
    exchange = RegisteredOperationExchange(
        client, client.profile_id, client.session_id, client.frontend, None, budget.call_deadline, progress
    )
    observed = observe_registered_operation(
        client,
        target,
        client.profile_id,
        client.session_id,
        COMPONENTS_SETUP_OPERATION_ID,
        COMPONENTS_OPERATION_SUBJECT,
        contract,
        None,
        None,
        progress,
        exchange,
    )
    review = SetupReview(yes=yes, ask=not reject and _can_ask(ctx), json_mode=format_of(ctx) is OutputFormat.JSON)
    handler = _review_handler(review)
    require_registered_review_contract(contract, handler)
    result = respond_registered_pending_review(
        observed.projection,
        target,
        handler,
        contract,
        client.profile_id,
        client.session_id,
        set(),
        exchange,
    )
    if result is not None or review.reviewed is None:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    decision = "apply" if review.approved else "reject"
    emit_envelope(
        ctx,
        command="config.provision.review",
        result=ProvisionReviewResult(operation_id=target, decision=decision),
        lines=[f"{target}\t{decision}"],
    )


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
        completed = run_registered_operation(
            bound_profile_client(ctx),
            ProvisionMutationRequest(),
            definition_id=COMPONENTS_SETUP_OPERATION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            result_type=ProvisionResult,
            request_version=1,
            result_version=1,
            timeout=_CALL_TIMEOUT_S,
            settlement_timeout=RegisteredOperationSettlement.UNBOUNDED,
            pending_check_command=_PENDING_CHECK_COMMAND,
            on_events=progress.observe,
            review=_review_handler(review),
        )
    finally:
        progress.finish()
    if not isinstance(completed, RegisteredOperationCompletion):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    _require_settled(completed)
    result = completed.projection
    reviewed = review.reviewed
    if (
        reviewed is not None
        and result.plan_digest is not None
        and result.outcome is ProvisionOutcome.COMPLETED
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

    def observe(self, page: OperationPublicEventPageV1) -> None:
        """Render public phase and byte progress without deciding settlement."""
        for event in page.events:
            if self.json_mode:
                write_stderr(_relayed(event))
            elif isinstance(event, OperationPublicPhaseEventV1):
                parts = event.phase_code.split(".")
                if len(parts) == 4 and parts[:2] == ["dependencies", "setup"]:
                    item, step = parts[2:]
                    text = tr(
                        "cli.config.provision.progress",
                        name=_name_of(item),
                        step=tr(f"cli.config.provision.step.{step}"),
                    )
                    if self._last.get(item) != text:
                        self._last[item] = text
                        self._draw(text, settled=not self.interactive)
            elif (
                isinstance(event, OperationPublicProgressEventV1)
                and self.interactive
                and event.subject_code is not None
            ):
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
    status: ProvisionResult,
    *,
    command: str,
    result_type: type[ProvisionStatusResult],
    full: bool = False,
) -> None:
    """Emit every reported item's row under ``command``."""
    rows = status.rows
    hardware_limited = any(row.blocked_reason is DependencyBlockedReason.HARDWARE for row in rows)
    result = result_type(
        mode=(DependencyCheckMode.FULL if full else DependencyCheckMode.QUICK).value,
        complete=status.setup_complete is True,
        hardware_limited=hardware_limited,
        failure_category=None if status.failure_category is None else status.failure_category.value,
        items=[_item_payload(row) for row in rows],
    )
    lines = _row_lines(rows)
    if hardware_limited:
        lines.append(tr("cli.config.provision.hardware_limited"))
    lines.append(tr("cli.config.provision.complete" if result.complete else "cli.config.provision.incomplete"))
    if status.failure_category is not None:
        # The engine refused the check itself, so it reported no row to word.
        lines.append(tr(dependency_failure_key(status.failure_category)))
    emit_envelope(ctx, command=command, result=result, lines=lines)


def _usable(rows: Iterable[DependencyStatusRow], items: tuple[DependencyItemKind, ...]) -> bool:
    """Whether every item the setup covers is ready or usable.

    A setup that names items covers them. One that names none covers every item
    except one only the desktop sets up, whose row points to the desktop instead.
    """
    named = {item.value for item in items}
    return all(
        row.state in {DependencyState.READY, DependencyState.STALE}
        for row in rows
        if (row.item_id in named if named else row.recovery is not DependencyRecoveryAction.SET_UP_IN_DESKTOP)
    )


def _setup_summary(result: ProvisionResult, *, needed_approval: bool, usable: bool) -> str:
    if result.outcome in {ProvisionOutcome.NEEDS_APPROVAL, ProvisionOutcome.REJECTED} and needed_approval:
        return tr("cli.config.provision.approval_needed")
    if result.outcome is ProvisionOutcome.NOTHING_TO_DO and not usable:
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
    outcome: ProvisionResult,
    *,
    command: str,
    result_type: type[ProvisionSetupResult],
    approved: bool,
    needed_approval: bool = False,
    items: tuple[DependencyItemKind, ...] = (),
) -> None:
    """Emit a settled setup of ``items``, every item when empty; exit 2 unless each of them is usable."""
    plan = outcome.plan
    rows = outcome.rows
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


# ── Removing ────────────────────────────────────────────────────────────────


def provision_remove(ctx: typer.Context, item: str, yes: bool = False) -> None:
    """Delete one component from this computer once the person confirms it; ``--yes`` confirms."""
    kind = remove_item(item)
    confirmed = yes or (
        _can_ask(ctx)
        and typer.confirm(
            tr("cli.config.provision.remove.confirm_prompt", name=_name_of(kind.value)), default=False, err=True
        )
    )
    if not confirmed:
        emit_provision_remove(ctx, None, item=kind)
        return
    progress = SetupProgressLine(json_mode=format_of(ctx) is OutputFormat.JSON, interactive=stderr_is_tty())
    try:
        completed = run_registered_operation(
            bound_profile_client(ctx),
            ProvisionMutationRequest(),
            definition_id=COMPONENTS_REMOVE_OPERATION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            result_type=ProvisionResult,
            request_version=1,
            result_version=1,
            timeout=_CALL_TIMEOUT_S,
            settlement_timeout=_QUICK_SETTLEMENT_S,
            pending_check_command=_PENDING_CHECK_COMMAND,
            on_events=progress.observe,
        )
        _require_settled(completed)
        result = completed.projection
    finally:
        progress.finish()
    emit_provision_remove(ctx, result, item=kind)


def _remove_summary(result: ProvisionResult, item: DependencyItemKind) -> str:
    if result.outcome is ProvisionOutcome.REMOVED:
        return tr("cli.config.provision.remove.removed", name=_name_of(item.value))
    if result.outcome is ProvisionOutcome.BUSY:
        return tr("cli.config.provision.outcome.busy")
    category = result.failure_category
    sentence = tr(dependency_failure_key(category)) if category is not None else tr("cli.config.provision.incomplete")
    return f"{_name_of(result.item_id or item.value)}: {sentence}"


def emit_provision_remove(ctx: typer.Context, outcome: ProvisionResult | None, *, item: DependencyItemKind) -> None:
    """Emit the removal of ``item``, ``None`` when it was not confirmed; exit 2 unless the role removed it."""
    if outcome is None:
        unconfirmed = ProvisionRemoveResult(item=item.value, confirmed=False)
        emit_envelope(
            ctx,
            command="config.provision.remove",
            result=unconfirmed,
            lines=[tr("cli.config.provision.remove.needs_confirmation", name=_name_of(item.value))],
        )
        raise typer.Exit(code=2)
    rows = outcome.rows
    result = ProvisionRemoveResult(
        item=item.value,
        confirmed=True,
        outcome=outcome.outcome.value,
        removed=list(outcome.items or ()),
        item_id=outcome.item_id,
        failure_category=None if outcome.failure_category is None else outcome.failure_category.value,
        items=[_item_payload(row) for row in rows],
    )
    emit_envelope(
        ctx,
        command="config.provision.remove",
        result=result,
        lines=[*_row_lines(rows), _remove_summary(outcome, item)],
    )
    if outcome.outcome is not ProvisionOutcome.REMOVED:
        raise typer.Exit(code=2)


# ── Running the local reader's operations ───────────────────────────────────


def _require_settled[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> None:
    if completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED or completed.refusal_code is not None:
        raise invalid_completion_error(completed)


def provision_report(ctx: typer.Context) -> None:
    """Report the measured hardware and each role's selected lane."""
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


def emit_provision_report(ctx: typer.Context, report: LocalReaderReportPublicResultV1) -> None:
    """Emit the measured hardware and each role's selected lane."""
    result = ProvisionReportResult(
        accelerator=report.accelerator.value,
        total_vram_bytes=report.total_vram_bytes,
        free_vram_bytes=report.free_vram_bytes,
        total_system_memory_bytes=report.total_system_memory_bytes,
        free_system_memory_bytes=report.free_system_memory_bytes,
        models=[
            ProvisionModelPayload(
                role=row.role.value,
                model=row.model,
                selected=row.selected,
                facts=_reader_facts(row.facts),
                precondition_action=_reader_action(row.verdict_condition_id, row.verdict_facts),
            )
            for row in report.models
        ],
    )
    emit_envelope(ctx, command="config.provision.report", result=result, lines=_provision_result_lines(result))
