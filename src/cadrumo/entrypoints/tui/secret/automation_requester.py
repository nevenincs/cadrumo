"""One exact-profile TUI automation request over the protected native channel."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import ClassVar, cast, override
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, SelectionList, Static

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import OperationPublicContractSetV1
from ....application.user_profile.access_contracts import GRANT_DEFAULT_VALIDITY, AccessAction
from ....application.user_profile.automation_custody_port import AutomationSecretStore
from ....application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
)
from ....core.async_cleanup import await_cancellation_complete, close_async_resources
from ....core.i18n.render import tr
from ....core.period import Period
from ....core.time.clock import now
from ..components.theme import tokenised
from . import automation_requester_cleanup as _requester_cleanup
from . import automation_requester_contracts as _requester_contracts
from . import automation_requester_setup as _requester_setup
from .automation_requester_delivery import RequesterDeliveryMixin
from .automation_requester_draft import RequesterDraftMixin
from .automation_requester_presentation import RequesterPresentationMixin

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


class RuntimeAutomationRequesterScreen(
    RequesterDraftMixin,
    RequesterDeliveryMixin,
    RequesterPresentationMixin,
    ModalScreen[_requester_contracts.AutomationRequestOutcome | None],
):
    """Present explicit scope consent and retain one submitted delivery until settled."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    DEFAULT_CSS = tokenised("""
    RuntimeAutomationRequesterScreen { align: center middle; }
    #automation-request-body {
        width: $cadrumo-modal-width;
        height: $cadrumo-modal-height;
        border: $cadrumo-radius-overlay $accent;
        padding: $cadrumo-gutter-y $cadrumo-gutter;
        background: $surface;
    }
    #automation-request-form { height: 1fr; }
    #automation-request-operations, #automation-request-actions, #automation-request-disclosures {
        height: auto;
        max-height: $cadrumo-log-max-height;
    }
    """)

    def __init__(
        self,
        *,
        profile_id: UUID,
        contracts: OperationPublicContractSetV1,
        secrets_store: AutomationSecretStore,
        client: RuntimeFrontendClient | None = None,
        open_client: _requester_contracts.RequesterClientOpener | None = None,
        fresh_credential_client: _requester_contracts.FreshCredentialClientOpener | None = None,
        reviewer_client: RuntimeFrontendClient | None = None,
        journey_timeout: float = 300,
    ) -> None:
        """Pin requester and optional reviewer; decisions keep their own runtime proof."""
        super().__init__()
        _requester_setup.validate_client_admission(profile_id, client, open_client, reviewer_client, journey_timeout)
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
        self._operation_choices = _requester_setup.operation_choices(contracts)
        self._disclosure_choices = _requester_setup.disclosure_choices(contracts)
        self._periods: set[Period] = set()
        self._request_task: asyncio.Task[None] | None = None
        self._busy = False
        self._live = True
        self._outcome: _requester_contracts.AutomationRequestOutcome | None = None
        self._submitted: AutomationReceiptProjection | None = None
        self._cleanup_owners: dict[int, _requester_cleanup.RequesterCleanup] = {}

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Add one typed period, submit once, or close after settlement."""
        if event.button.id == "automation-request-review":
            self._open_review()
        elif event.button.id == "automation-request-period-add":
            self._add_period()
        elif event.button.id == "automation-request-close":
            self.action_close()
        elif event.button.id == "automation-request-submit":
            self._begin_submit()

    def _add_period(self) -> None:
        if self._busy:
            return
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

    def _begin_submit(self) -> None:
        if self._busy or self._outcome is not None:
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
    "HumanAutomationRequesterFactory",
    "RuntimeAutomationRequesterScreen",
]
