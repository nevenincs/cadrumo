"""One exact-profile TUI automation request over the protected native channel."""

from __future__ import annotations

import asyncio
import math
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, cast, override
from uuid import UUID

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, SelectionList, Static

from ....adapters.local_runtime.automation_requester import (
    AutomationRequesterCompletion,
    AutomationRequesterJourney,
    AutomationRequesterUncertainError,
)
from ....adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ....application.runtime.deadline_budget import remaining_budget
from ....application.user_profile.access_contracts import (
    GRANT_DEFAULT_VALIDITY,
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.automation_custody_port import AutomationSecretStore
from ....application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from ....core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from ....core.i18n.render import tr
from ....core.period import Period
from ....core.time.clock import now

type RequesterClientOpener = Callable[[UUID], Awaitable[RuntimeFrontendClient]]
type FreshCredentialClientOpener = Callable[[UUID, UUID, float], RuntimeFrontendClient]

_KIND_LOCALE_KEYS = {
    EnrollmentKind.ENROLL: "tui.automation_request.enroll",
    EnrollmentKind.ROTATE: "tui.automation_request.rotate",
    EnrollmentKind.RENEW: "tui.automation_request.renew",
    EnrollmentKind.CHANGE_SCOPE: "tui.automation_request.change_scope",
}
_PERIOD_LOCALE_KEYS = {
    "none": "tui.automation_inventory.no_periods",
    "all": "tui.automation_inventory.all_periods",
    "selected": "tui.automation_request.period_selected",
}
_OUTCOME_LOCALE_KEYS = {
    "uncertain": "tui.automation_request.uncertain",
    "complete": "tui.automation_request.complete",
    "declined": "tui.automation_request.declined",
    "invalid": "tui.automation_request.invalid",
}


@dataclass(frozen=True, slots=True)
class AutomationRequestOutcome:
    """Safe receipt identity after a completed or uncertain request."""

    request_id: UUID | None
    review_digest: str | None
    stage: EnrollmentStage | None
    credential_reference: UUID | None
    uncertain: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class _ProposalDraft:
    kind: EnrollmentKind
    operations: frozenset[str]
    actions: frozenset[AccessAction]
    disclosures: frozenset[tuple[str, DisclosureCategory]]
    periods: frozenset[Period] | None
    period_independent: bool
    delegation: bool
    expires_at: datetime
    key_expires_at: datetime | None
    unattended: bool
    os_lock: bool
    target_grant_id: UUID | None
    target_key_id: UUID | None
    credential_reference: UUID | None

    def proposal(self, destination_id: UUID) -> EnrollmentProposal:
        """Bind disclosed schemas to the server-minted destination, not UI input."""
        scope = AccessScope(
            operations=frozenset(self.operations),
            actions=self.actions,
            disclosures=frozenset(
                DisclosurePermission(destination_id=destination_id, projection_id=schema, category=category)
                for schema, category in self.disclosures
            ),
            periods=self.periods,
            allow_period_independent=self.period_independent,
            allow_delegation=self.delegation,
        )
        return EnrollmentProposal(
            kind=self.kind,
            scope=scope,
            expires_at=self.expires_at,
            key_expires_at=self.key_expires_at,
            unattended=self.unattended,
            allow_os_lock=self.os_lock,
            target_grant_id=self.target_grant_id,
            target_key_id=self.target_key_id,
        )


class _RequesterCleanup:
    """Keep failed cleanup owned until a cancellation-complete retry succeeds."""

    def __init__(self, close: Callable[[], Awaitable[None]], *, released: Callable[[], None]) -> None:
        self._close = close
        self._released = released

    async def close(self) -> None:
        await self._close()
        self._released()


class RuntimeAutomationRequesterScreen(ModalScreen[AutomationRequestOutcome | None]):
    """Present explicit scope consent and retain one submitted delivery until settled."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    DEFAULT_CSS = """
    RuntimeAutomationRequesterScreen { align: center middle; }
    #automation-request-body { width: 100%; height: 42; border: round $accent; padding: 1 2; background: $surface; }
    #automation-request-form { height: 1fr; }
    #automation-request-operations, #automation-request-actions, #automation-request-disclosures { height: 7; }
    """

    def __init__(
        self,
        *,
        profile_id: UUID,
        contracts: OperationPublicContractSetV1,
        secrets_store: AutomationSecretStore,
        client: RuntimeFrontendClient | None = None,
        open_client: RequesterClientOpener | None = None,
        fresh_credential_client: FreshCredentialClientOpener | None = None,
        reviewer_client: RuntimeFrontendClient | None = None,
        journey_timeout: float = 300,
    ) -> None:
        """Pin requester and optional reviewer; decisions keep their own runtime proof."""
        super().__init__()
        if (client is None) == (open_client is None):
            raise ValueError("requester needs exactly one client source")
        if client is not None and (
            client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.TUI
        ):
            raise ValueError("requester client must be the exact TUI profile")
        if reviewer_client is not None and (
            reviewer_client.profile_id != profile_id or reviewer_client.frontend is not OperationFrontendProjection.TUI
        ):
            raise ValueError("reviewer must be the exact TUI profile")
        if not math.isfinite(journey_timeout) or not 0 < journey_timeout <= 300:
            raise ValueError("requester journey timeout must be finite and at most five minutes")
        self._profile_id = profile_id
        self._client = client
        self._session_id = client.session_id if client is not None else None
        self._owned_client: RuntimeFrontendClient | None = None
        self._open_client = open_client
        self._fresh_credential_client = fresh_credential_client
        self._reviewer_client = reviewer_client
        self._reviewer_session_id = reviewer_client.session_id if reviewer_client is not None else None
        self._reviewer_access_lost = False
        self._secrets_store = secrets_store
        self._journey_timeout = journey_timeout
        self._operation_choices = tuple(
            str(row.definition_id)
            for row in contracts.definitions
            if OperationFrontendProjection.TUI in row.permitted_frontends
        )
        self._disclosure_choices = tuple(
            sorted(
                {
                    (str(schema.schema_id), category)
                    for row in contracts.definitions
                    if OperationFrontendProjection.TUI in row.permitted_frontends
                    for schema in (
                        row.result_schema,
                        row.review_projection_schema,
                        row.interaction_response_schema,
                        row.workspace_refresh_target_schema,
                    )
                    if schema is not None
                    for category in DisclosureCategory
                }
                | {(OPERATION_OBSERVATION_PROJECTION_ID, DisclosureCategory.OPERATION_METADATA)}
            )
        )
        self._periods: set[Period] = set()
        self._request_task: asyncio.Task[None] | None = None
        self._busy = False
        self._live = True
        self._outcome: AutomationRequestOutcome | None = None
        self._submitted: AutomationReceiptProjection | None = None
        self._cleanup_owners: dict[int, _RequesterCleanup] = {}

    @property
    def safe_outcome(self) -> AutomationRequestOutcome | None:
        """Retain the request ID even if this presentation is dismissed."""
        return self._outcome

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="automation-request-body"):
            yield Static(tr("tui.automation_request.title"), markup=False)
            yield Static(tr("tui.automation_request.capability_note"), markup=False)
            with VerticalScroll(id="automation-request-form"):
                yield Label(tr("tui.automation_request.kind"))
                kinds = (
                    (EnrollmentKind.ENROLL,)
                    if self._client is None
                    else (EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE)
                )
                yield Select[EnrollmentKind](
                    [(tr(_KIND_LOCALE_KEYS[kind]), kind) for kind in kinds],
                    value=kinds[0],
                    allow_blank=False,
                    id="automation-request-kind",
                )
                yield Label(tr("tui.automation_request.operations"))
                yield SelectionList[str](
                    *((item, item, False) for item in self._operation_choices), id="automation-request-operations"
                )
                yield Label(tr("tui.automation_request.actions"))
                yield SelectionList[str](
                    *((item.value, item.value, False) for item in AccessAction),
                    id="automation-request-actions",
                )
                yield Label(tr("tui.automation_request.disclosures"))
                yield SelectionList[str](
                    *(
                        (f"{schema} / {category.value}", f"{schema}|{category.value}", False)
                        for schema, category in self._disclosure_choices
                    ),
                    id="automation-request-disclosures",
                )
                yield Label(tr("tui.automation_request.period_mode"))
                yield Select[str](
                    [(tr(_PERIOD_LOCALE_KEYS[mode]), mode) for mode in ("none", "all", "selected")],
                    value="none",
                    allow_blank=False,
                    id="automation-request-period-mode",
                )
                with Horizontal():
                    yield Input(placeholder=tr("tui.automation_request.period_year"), id="automation-request-year")
                    yield Input(placeholder=tr("tui.automation_request.period_code"), id="automation-request-code")
                    yield Button(tr("tui.automation_request.period_add"), id="automation-request-period-add")
                yield Static("", id="automation-request-periods", markup=False)
                yield Checkbox(tr("tui.automation_request.period_independent"), id="automation-request-independent")
                yield Checkbox(tr("tui.automation_request.delegation"), id="automation-request-delegation")
                yield Input(placeholder=tr("tui.automation_request.grant_expiry"), id="automation-request-expiry")
                yield Input(placeholder=tr("tui.automation_request.key_expiry"), id="automation-request-key-expiry")
                yield Checkbox(tr("tui.automation_request.unattended"), id="automation-request-unattended")
                yield Static(tr("tui.automation_inventory.unattended_notice"), markup=False)
                yield Checkbox(tr("tui.automation_request.os_lock"), id="automation-request-os-lock")
                yield Input(placeholder=tr("tui.automation_request.target_grant"), id="automation-request-grant")
                yield Input(placeholder=tr("tui.automation_request.target_key"), id="automation-request-key")
                yield Input(
                    placeholder=tr("tui.automation_request.credential_reference"),
                    id="automation-request-reference",
                )
            yield Static("", id="automation-request-status", markup=False)
            with Horizontal():
                yield Button(tr("tui.automation_request.submit"), id="automation-request-submit")
                if self._reviewer_client is not None:
                    yield Button(
                        tr("tui.runtime_access.view_automation"), id="automation-request-review", disabled=True
                    )
                yield Button(tr("tui.runtime_access.close"), id="automation-request-close")

    async def on_unmount(self) -> None:
        """Finish the task before closing its owned requester connection."""
        self._live = False
        task = self._request_task
        try:
            if task is not None:

                async def settle_request() -> None:
                    try:
                        await task
                    except (Exception, asyncio.CancelledError) as error:
                        self._retain_cleanup_errors(error)

                await await_cancellation_complete(settle_request(), task_name="tui-automation-request-settle")
        finally:
            self._request_task = None
            owned = self._owned_client
            self._owned_client = None
            if owned is not None:

                async def close_owned() -> None:
                    await asyncio.to_thread(owned.close)

                self._retain_cleanup_owner(id(owned), close_owned)
            try:
                await close_async_resources(
                    *tuple(self._cleanup_owners.values()), task_name="tui-automation-request-close"
                )
            finally:
                self._periods.clear()
                self._submitted = None
                for field in self.query(Input):
                    field.value = ""

    def _retain_cleanup_owner(self, identity: int, close: Callable[[], Awaitable[None]]) -> None:
        if identity not in self._cleanup_owners:

            def released() -> None:
                self._cleanup_owners.pop(identity, None)

            self._cleanup_owners[identity] = _RequesterCleanup(close, released=released)

    def _retain_cleanup_errors(self, error: BaseException) -> None:
        """Adopt canonical failure attachments after the wire task returns to the UI."""
        pending = [error]
        seen: set[int] = set()
        while pending:
            current = pending.pop()
            identity = id(current)
            if identity in seen:
                continue
            seen.add(identity)
            if isinstance(current, AsyncResourceCleanupError):
                self._retain_cleanup_owner(identity, current.retry_cleanup)
            for name in ("async_cleanup_error", "cleanup_error", "body_error"):
                attached = current.__dict__.get(name)
                if isinstance(attached, BaseException):
                    pending.append(attached)
            if isinstance(current, AutomationRequesterUncertainError) and current.__cause__ is not None:
                pending.append(current.__cause__)

    def on_mount(self) -> None:
        """Show only fields relevant to the initial requested change."""
        selected = cast("Select[EnrollmentKind]", self.query_one("#automation-request-kind", Select)).value
        if isinstance(selected, EnrollmentKind):
            self._show_kind(selected)
            if selected is EnrollmentKind.ENROLL:
                self.query_one("#automation-request-expiry", Input).value = (now() + GRANT_DEFAULT_VALIDITY).isoformat()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Clear fields that no longer belong to the selected proposal kind."""
        if event.select.id == "automation-request-kind" and not self._busy and isinstance(event.value, EnrollmentKind):
            self._show_kind(event.value)

    def _show_kind(self, kind: EnrollmentKind) -> None:
        visible = {
            "key-expiry": kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE},
            "grant": kind is not EnrollmentKind.ENROLL,
            "key": kind is EnrollmentKind.ROTATE,
            "reference": kind is not EnrollmentKind.ENROLL,
        }
        for suffix, enabled in visible.items():
            field = self.query_one(f"#automation-request-{suffix}", Input)
            field.display = enabled
            field.disabled = not enabled
            if not enabled:
                field.value = ""

    def _bound(self, client: RuntimeFrontendClient) -> bool:
        return (
            client.frontend is OperationFrontendProjection.TUI
            and client.profile_id == self._profile_id
            and (self._session_id is None or client.session_id == self._session_id)
        )

    @staticmethod
    def _optional_uuid(value: str) -> UUID | None:
        stripped = value.strip()
        if not stripped:
            return None
        parsed = UUID(stripped)
        if str(parsed) != stripped:
            raise ValueError("noncanonical UUID")
        return parsed

    def _draft(self) -> _ProposalDraft:
        kind = cast("Select[EnrollmentKind]", self.query_one("#automation-request-kind", Select)).value
        if not isinstance(kind, EnrollmentKind):
            raise ValueError("no request kind")
        if (self._client is None) != (kind is EnrollmentKind.ENROLL):
            raise ValueError("request kind does not match client admission")
        selected_operations = frozenset(
            cast("SelectionList[str]", self.query_one("#automation-request-operations", SelectionList)).selected
        )
        if not selected_operations.issubset(self._operation_choices):
            raise ValueError("undeclared operation")
        action_list = cast("SelectionList[str]", self.query_one("#automation-request-actions", SelectionList))
        selected_actions = frozenset(AccessAction(value) for value in action_list.selected)
        available = {f"{schema}|{category.value}" for schema, category in self._disclosure_choices}
        raw_disclosures = frozenset(
            cast("SelectionList[str]", self.query_one("#automation-request-disclosures", SelectionList)).selected
        )
        if not raw_disclosures.issubset(available):
            raise ValueError("undeclared disclosure")
        disclosures = frozenset(
            (schema, DisclosureCategory(category))
            for schema, category in (value.split("|", 1) for value in raw_disclosures)
        )
        period_mode = cast("Select[str]", self.query_one("#automation-request-period-mode", Select)).value
        if period_mode not in {"all", "none", "selected"}:
            raise ValueError("invalid period choice")
        periods = None if period_mode == "all" else frozenset(self._periods if period_mode == "selected" else ())
        expiry = datetime.fromisoformat(self.query_one("#automation-request-expiry", Input).value.strip())
        key_raw = self.query_one("#automation-request-key-expiry", Input).value.strip()
        key_expiry = datetime.fromisoformat(key_raw) if key_raw else None
        reference = self._optional_uuid(self.query_one("#automation-request-reference", Input).value)
        if (self._client is None and reference is not None) or (self._client is not None and reference is None):
            raise ValueError("protected credential reference does not match request kind")
        return _ProposalDraft(
            kind=kind,
            operations=selected_operations,
            actions=selected_actions,
            disclosures=disclosures,
            periods=periods,
            period_independent=self.query_one("#automation-request-independent", Checkbox).value,
            delegation=self.query_one("#automation-request-delegation", Checkbox).value,
            expires_at=expiry,
            key_expires_at=key_expiry,
            unattended=self.query_one("#automation-request-unattended", Checkbox).value,
            os_lock=self.query_one("#automation-request-os-lock", Checkbox).value,
            target_grant_id=self._optional_uuid(self.query_one("#automation-request-grant", Input).value),
            target_key_id=self._optional_uuid(self.query_one("#automation-request-key", Input).value),
            credential_reference=reference,
        )

    def _reconcile(
        self, enrollment: NativeEnrollmentClient, draft: _ProposalDraft
    ) -> Callable[..., AutomationReceiptProjection]:
        fresh_opener = self._fresh_credential_client
        if fresh_opener is None or draft.credential_reference is None:
            raise ValueError("fresh protected credential reference required")

        def reconcile(submitted: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
            deadline = time.monotonic() + timeout
            if draft.kind is EnrollmentKind.ROTATE:
                reference = enrollment.delivered_credential_metadata().credential_reference
            else:
                reference = draft.credential_reference
            if reference is None:
                raise ValueError("missing protected credential reference")
            remaining = remaining_budget(deadline)
            fresh = fresh_opener(self._profile_id, reference, remaining)
            try:
                remaining = remaining_budget(deadline)
                return fresh.reconcile_enrollment(submitted.request_id, timeout=remaining)
            finally:
                primary_error = sys.exception()

                async def close_fresh() -> None:
                    await asyncio.to_thread(fresh.close)

                cleanup = _RequesterCleanup(close_fresh, released=lambda: None)
                asyncio.run(
                    close_async_resources(
                        cleanup, task_name="tui-requester-reconcile-close", primary_error=primary_error
                    )
                )

        return reconcile

    async def _execute(self, draft: _ProposalDraft) -> None:
        client = self._client
        request_id: UUID | None = None
        submitted_attempted = False
        try:
            if client is None:
                opener = self._open_client
                if opener is None:
                    raise ValueError("requester opener absent")

                async def open_bound() -> RuntimeFrontendClient:
                    return await opener(self._profile_id)

                opening = asyncio.create_task(open_bound(), name="tui-requester-open")
                interrupted: asyncio.CancelledError | None = None
                while not opening.done():
                    try:
                        await asyncio.shield(opening)
                    except asyncio.CancelledError as caught:
                        interrupted = caught
                    except BaseException:
                        break
                client = opening.result()
                self._owned_client = client
                if interrupted is not None:
                    raise interrupted
            if not self._bound(client):
                raise ValueError("requester client binding changed")
            enrollment = await await_cancellation_complete(
                asyncio.to_thread(
                    client.prepare_enrollment if draft.kind is EnrollmentKind.ENROLL else client.prepare_grant_change,
                    self._secrets_store,
                ),
                task_name="tui-requester-prepare",
            )
            request_id = enrollment.prepared.enrollment_request_id
            proposal = draft.proposal(enrollment.prepared.destination_id)
            reconcile = None if draft.kind is EnrollmentKind.ENROLL else self._reconcile(enrollment, draft)
            journey = AutomationRequesterJourney(enrollment, timeout=self._journey_timeout, reconcile=reconcile)
            submitted_attempted = True
            submitted = await await_cancellation_complete(
                asyncio.to_thread(journey.submit, proposal), task_name="tui-requester-submit"
            )
            self._submitted = submitted
            if self._live and self.is_mounted:
                if self._reviewer_client is not None:
                    self.query_one("#automation-request-review", Button).disabled = not self._reviewer_bound()
                self.query_one("#automation-request-status", Static).update(
                    f"{tr('tui.automation_request.requested')} · "
                    f"{tr('tui.automation_request.request_id')}: {submitted.request_id} · "
                    f"{tr('tui.automation_request.review_digest')}: {submitted.review_digest}"
                )
            completed = await await_cancellation_complete(
                asyncio.to_thread(journey.wait_for_terminal), task_name="tui-requester-delivery"
            )
            self._outcome = self._completed_outcome(completed)
        except AutomationRequesterUncertainError as error:
            self._retain_cleanup_errors(error)
            self._outcome = AutomationRequestOutcome(
                error.request_id,
                str(self._submitted.review_digest) if self._submitted is not None else None,
                None,
                None,
                True,
                error.reason,
            )
        except asyncio.CancelledError as error:
            self._retain_cleanup_errors(error)
            self._outcome = AutomationRequestOutcome(
                request_id if submitted_attempted else None,
                str(self._submitted.review_digest) if self._submitted is not None else None,
                None,
                None,
                submitted_attempted,
                None,
            )
            raise
        except Exception as error:
            self._retain_cleanup_errors(error)
            self._outcome = AutomationRequestOutcome(
                request_id if submitted_attempted else None,
                str(self._submitted.review_digest) if self._submitted is not None else None,
                None,
                None,
                submitted_attempted,
                None,
            )
        finally:
            self._busy = False
            self._render_outcome()

    @staticmethod
    def _completed_outcome(completed: AutomationRequesterCompletion) -> AutomationRequestOutcome:
        terminal = completed.terminal
        return AutomationRequestOutcome(
            terminal.request_id,
            str(terminal.review_digest),
            terminal.stage,
            None if completed.credential is None else completed.credential.credential_reference,
            False,
            None,
        )

    def _render_outcome(self) -> None:
        if not self._live or not self.is_mounted:
            return
        outcome = self._outcome
        if outcome is None:
            return
        label = (
            "uncertain"
            if outcome.uncertain
            else "complete"
            if outcome.stage is EnrollmentStage.COMPLETE
            else "declined"
            if outcome.stage is EnrollmentStage.DECLINED
            else "invalid"
        )
        parts = [tr(_OUTCOME_LOCALE_KEYS[label])]
        if outcome.request_id is not None:
            parts.append(f"{tr('tui.automation_request.request_id')}: {outcome.request_id}")
        if outcome.review_digest is not None:
            parts.append(f"{tr('tui.automation_request.review_digest')}: {outcome.review_digest}")
        if outcome.credential_reference is not None:
            parts.append(f"{tr('tui.automation_request.reference')}: {outcome.credential_reference}")
        self.query_one("#automation-request-status", Static).update(" · ".join(parts))
        self.query_one("#automation-request-close", Button).disabled = False

    def _reviewer_bound(self) -> bool:
        reviewer = self._reviewer_client
        try:
            return (
                reviewer is not None
                and not self._reviewer_access_lost
                and reviewer.frontend is OperationFrontendProjection.TUI
                and reviewer.profile_id == self._profile_id
                and reviewer.session_id == self._reviewer_session_id
            )
        except Exception:
            return False

    def _open_review(self) -> None:
        """Let the human inspect and decide separately while delivery remains owned."""
        from ..profile.automation_inventory import RuntimeAutomationInventoryScreen

        reviewer = self._reviewer_client
        if not self._live or self._submitted is None or reviewer is None or not self._reviewer_bound():
            return
        screen = RuntimeAutomationInventoryScreen(reviewer)

        def closed(lost: bool | None) -> None:
            if lost or screen.access_lost:
                self._reviewer_access_lost = True
            if self._live and self.is_mounted:
                self.query_one("#automation-request-review", Button).disabled = not self._reviewer_bound()

        cast("App[object]", self.app).push_screen(screen, closed)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Add one typed period, submit once, or close after settlement."""
        if event.button.id == "automation-request-review":
            self._open_review()
            return
        if event.button.id == "automation-request-period-add" and not self._busy:
            try:
                period = Period.from_year_and_code(
                    int(self.query_one("#automation-request-year", Input).value),
                    self.query_one("#automation-request-code", Input).value.strip(),
                )
            except Exception:
                self.query_one("#automation-request-status", Static).update(tr("tui.automation_request.invalid"))
                return
            self._periods.add(period)
            self.query_one("#automation-request-periods", Static).update(
                ", ".join(str(item) for item in sorted(self._periods, key=str))
            )
            return
        if event.button.id == "automation-request-close":
            self.action_close()
            return
        if event.button.id != "automation-request-submit" or self._busy or self._outcome is not None:
            return
        try:
            draft = self._draft()
        except Exception:
            self.query_one("#automation-request-status", Static).update(tr("tui.automation_request.invalid"))
            return
        self._busy = True
        self.query_one("#automation-request-submit", Button).disabled = True
        self.query_one("#automation-request-close", Button).disabled = True
        self.query_one("#automation-request-status", Static).update(tr("tui.automation_request.waiting"))
        self._request_task = asyncio.create_task(self._execute(draft), name="tui-automation-request")

    def action_close(self) -> None:
        """A submitted request remains owned until terminal or uncertainty."""
        if not self._busy:
            self.dismiss(self._outcome)


type HumanAutomationRequesterFactory = Callable[[RuntimeFrontendClient], RuntimeAutomationRequesterScreen]


__all__ = [
    "AutomationRequestOutcome",
    "FreshCredentialClientOpener",
    "HumanAutomationRequesterFactory",
    "RequesterClientOpener",
    "RuntimeAutomationRequesterScreen",
]
