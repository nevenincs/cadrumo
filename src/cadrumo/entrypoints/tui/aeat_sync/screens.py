"""Six safe, host-neutral AEAT Sync projection screens."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar, Final, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Button, DataTable, Static

from ....application.aeat_sync.workspace import (
    AeatSyncNotificationReadState,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceZone,
)
from ....application.operations.access_facts import operation_access_facts
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....core.i18n.render import tr
from ....core.operations import OperationTerminalCondition
from ..components.account_chrome import AccountChromeScreen
from ..components.language import localized, repaint_tables
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..components.workspace_host import replace_workspace_body
from ..operations.controller_port import OperationControllerPort
from ..operations.modal import OperationModal, OperationModalOutcomeV1, OperationModalSettledOutcomeV1
from ..profile.aeat_auth_setup import AeatAuthSetupScreen, readiness_text
from .controller import AeatSyncWorkspaceController
from .models import AeatSyncOperationRequestV1, AeatSyncRouteTargetV1
from .operation_results import read_notifications_summary
from .screen_presentation import (
    status_label,
)
from .screen_rows import OperationRow
from .workspace_rendering import closed_zone_copy, render_navigation

if TYPE_CHECKING:
    pass

_OPERATION_LABEL_LOCALE_KEYS: Final = {
    ("operator.profile.edit", "user-profile.censo-review"): "tui.aeat_sync.action.review_census",
    ("operator.live.filed.pull_all", "live.filed-history.pull"): "tui.aeat_sync.action.pull_filed_all",
    ("operator.live.notifications.list", "live.notifications.list"): "tui.search.action.list_notifications",
}


class AeatSyncRouteRequested(Message):
    """Ask the owning host to replace this active internal workspace body."""

    def __init__(self, target: AeatSyncRouteTargetV1) -> None:
        """Retain the prevalidated internal target."""
        super().__init__()
        self.target = target


class AeatSyncWorkspaceScreen(AccountChromeScreen):
    """Common one-scroll shell; it reads only the injected immutable projection."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        #aeat-sync-page { width: 100%; height: 1fr; overflow-x: hidden; }
        #aeat-sync-navigation, #aeat-sync-rows { width: 100%; }
        #aeat-sync-status {
            width: 100%;
            height: auto;
            padding: $cadrumo-space-0 $cadrumo-space-1;
            color: $warning;
        }
        .aeat-sync-operation { width: 100%; max-width: $cadrumo-control-max-width; }
        """
    )

    zone: AeatSyncWorkspaceZone
    HEADING_LOCALE_KEY: str

    def __init__(self, controller: AeatSyncWorkspaceController, *, id: str) -> None:
        """Retain the controller and initially empty local button catalogue."""
        super().__init__(id=id)
        self.controller = controller
        self._requests: dict[str, AeatSyncOperationRequestV1] = {}
        self._unoffered_operations: set[str] = set()
        self._active_operation_request: AeatSyncOperationRequestV1 | None = None
        self._active_operation_controller: OperationControllerPort | None = None
        self._operation_button_epoch = 0
        self._consumed_request_ids: set[str] = set()
        self._consumed_notification_ids: set[str] = set()
        self._in_flight_id: str | None = None
        self._selected_row_key: str | None = None
        self._notification_rows: dict[str, AeatSyncWorkspaceNotificationRowV1] = {}

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr(self.HEADING_LOCALE_KEY), classes="cadrumo-banner", markup=False), self.HEADING_LOCALE_KEY
        )
        with ContentScroll(id="aeat-sync-page", classes="cadrumo-scroll"):
            if self.controller.aeat_auth_setup is not None:
                yield Static(
                    readiness_text(self.controller.auth_readiness), id="aeat-sync-auth-readiness", markup=False
                )
                yield localized(Button(tr("tui.aeat_auth.edit"), id="aeat-sync-auth-edit"), "tui.aeat_auth.edit")
            yield localized(
                Static(
                    tr("tui.aeat_sync.section.areas"),
                    classes="cadrumo-heading",
                    markup=False,
                ),
                "tui.aeat_sync.section.areas",
            )
            yield ContentDataTable[str](id="aeat-sync-navigation", cursor_type="row", zebra_stripes=True)
            yield localized(
                Static(
                    tr("tui.aeat_sync.section.detail"),
                    classes="cadrumo-heading",
                    markup=False,
                ),
                "tui.aeat_sync.section.detail",
            )
            yield ContentDataTable[str](id="aeat-sync-rows", cursor_type="row", zebra_stripes=True)
            yield Static(id="aeat-sync-status", markup=False)
            yield from self.compose_evidence()

    def compose_evidence(self) -> ComposeResult:
        """Allow a zone to render its existing captured evidence below comparison rows."""
        return ()

    def on_mount(self) -> None:
        """Render all six independent source states and this screen's safe rows."""
        navigation = cast("DataTable[str]", self.query_one("#aeat-sync-navigation", DataTable))
        navigation.add_column(tr("tui.aeat_sync.column.area"), width=16)
        navigation.add_column(tr("tui.aeat_sync.column.availability"), width=12)
        navigation.add_column(tr("tui.aeat_sync.column.sources"), width=38)
        render_navigation(navigation, self.controller)
        rows = cast("DataTable[str]", self.query_one("#aeat-sync-rows", DataTable))
        self.populate_rows(rows)
        self._render_operation_refusal()
        self._render_zone_status(rows)
        self._restore_focus(
            navigation,
            rows,
        )
        if self.controller.aeat_auth_setup is not None:
            self.run_worker(self._refresh_auth(), group="aeat-sync-auth-readiness", exclusive=True)

    async def _refresh_auth(self) -> bool:
        door = self.controller.aeat_auth_setup
        if door is None:
            return True
        try:
            self.controller.auth_readiness = await door.read_readiness()
        except Exception:
            self.controller.auth_readiness = None
        if self.is_attached:
            self.query_one("#aeat-sync-auth-readiness", Static).update(readiness_text(self.controller.auth_readiness))
            self._set_operation_buttons_disabled(self._in_flight_id is not None)
        return self.controller.auth_readiness is not None and self.controller.auth_readiness.ready

    async def _auth_edited(self, _outcome: object) -> None:
        await self._refresh_auth()

    def _render_zone_status(self, rows: DataTable[str]) -> None:
        """State known-empty and unobservable zones in non-colour text."""
        state = self.controller.state_for(self.zone)
        count = state.item_count
        rendered_count = count
        if self.zone is AeatSyncWorkspaceZone.RECONCILIATION:
            rendered_count = sum(max(1, len(row.diffs)) for row in self.controller.projection.reconciliation)
        if count is not None and rendered_count != rows.row_count:
            raise ValueError("AEAT Sync zone count and rendered rows disagree")
        status = self.query_one("#aeat-sync-status", Static)
        if str(status.render()).strip():
            return
        rendered_count = (
            tr("tui.aeat_sync.status.items", count=count) if count is not None else tr("tui.aeat_sync.value.none")
        )
        status.update(f"{status_label(self.zone)} · {status_label(state.availability)} · {rendered_count}")

    def _restore_focus(self, navigation: DataTable[str], rows: DataTable[str]) -> None:
        """Restore the stable selected row after refresh or child return."""
        focus = self.controller.context.focus
        if focus is not None and focus.semantic_key.startswith(f"aeat_sync.{self.zone.value}") and rows.row_count:
            rows.focus()
            return
        if self._selected_row_key is not None:
            for index, item in enumerate(rows.ordered_rows):
                if str(item.key.value) == self._selected_row_key:
                    rows.move_cursor(row=index)
                    rows.focus()
                    return
        navigation.focus()

    @override
    async def refresh_language(self) -> None:
        """Reword held rows without renewing requests or resetting consumed operations."""
        await super().refresh_language()

        def paint() -> None:
            navigation = cast("DataTable[str]", self.query_one("#aeat-sync-navigation", DataTable))
            navigation.add_column(tr("tui.aeat_sync.column.area"), width=16)
            navigation.add_column(tr("tui.aeat_sync.column.availability"), width=12)
            navigation.add_column(tr("tui.aeat_sync.column.sources"), width=38)
            render_navigation(navigation, self.controller)
            rows = cast("DataTable[str]", self.query_one("#aeat-sync-rows", DataTable))
            self.populate_rows(rows)
            self._render_zone_status(rows)
            self.reword_evidence()

        repaint_tables(self, paint)
        readiness = self.query("#aeat-sync-auth-readiness")
        if readiness:
            self.query_one("#aeat-sync-auth-readiness", Static).update(readiness_text(self.controller.auth_readiness))
        self._render_operation_refusal()

    def refresh_projection(self, projection: AeatSyncWorkspaceProjectionV1) -> None:
        """Apply one explicit preloaded snapshot and retain semantic focus."""
        self.controller.replace_projection(projection)
        navigation = cast("DataTable[str]", self.query_one("#aeat-sync-navigation", DataTable))
        rows = cast("DataTable[str]", self.query_one("#aeat-sync-rows", DataTable))
        for button in tuple(self.query(".aeat-sync-operation")):
            button.remove()
        self._operation_button_epoch += 1
        self._requests.clear()
        self._unoffered_operations.clear()
        self._consumed_request_ids.clear()
        self._consumed_notification_ids.clear()
        self._notification_rows.clear()
        navigation.clear(columns=False)
        rows.clear(columns=True)
        self.query_one("#aeat-sync-status", Static).update("")
        render_navigation(navigation, self.controller)
        self.populate_rows(rows)
        self._render_operation_refusal()
        self._render_zone_status(rows)
        self._restore_focus(navigation, rows)
        if self.controller.aeat_auth_setup is not None:
            self.run_worker(self._refresh_auth(), group="aeat-sync-auth-readiness", exclusive=True)

    def reword_evidence(self) -> None:
        """Reword an optional evidence table, without recapturing remote data."""

    def populate_rows(self, table: DataTable[str]) -> None:
        """Populate one safe public zone body in subclasses."""
        raise NotImplementedError

    def add_operation(self, row: OperationRow) -> None:
        """Render an explicit mutation button only for a closed admitted pair.

        One admitted operation gets one door however many areas declare it.
        An operation no door offers is recorded, and the refusal is stated
        once the screen's rows are in; catalogue actions that start no
        operation are not handoff candidates and refuse nothing.
        """
        request = self.controller.admitted_operation(row.supported_actions, row.supported_operations)
        label_key = (
            None
            if request is None
            else _OPERATION_LABEL_LOCALE_KEYS.get((str(request.action.action_id), str(request.operation)))
        )
        # Without a host door the button could only refuse; say so once instead.
        if request is None or label_key is None or self.controller.operation_handoff is None:
            self._unoffered_operations.update(str(operation) for operation in row.supported_operations)
            return
        if request in self._requests.values():
            return
        button_id = (
            f"aeat-sync-operation-{len(self._requests)}"
            if self._operation_button_epoch == 0
            else f"aeat-sync-operation-{self._operation_button_epoch}-{len(self._requests)}"
        )
        self._requests[button_id] = request
        self.query_one("#aeat-sync-page", ContentScroll).mount(
            localized(
                Button(
                    tr(label_key),
                    id=button_id,
                    classes="aeat-sync-operation",
                    disabled=self._authentication_blocks(request),
                ),
                label_key,
            )
        )

    def _render_operation_refusal(self) -> None:
        """State the handoff refusal only for an operation no rendered door offers."""
        offered = {str(request.operation) for request in self._requests.values()}
        if self._unoffered_operations - offered:
            self.query_one("#aeat-sync-status", Static).update(tr("tui.aeat_sync.refusal.operation_handoff"))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Hand the exact admitted request to the optional owning host door."""
        request_id = event.button.id or ""
        if request_id == "aeat-sync-auth-edit":
            self._edit_auth()
            return
        request = self._requests.get(request_id)
        if request is None:
            return
        handoff = self.controller.operation_handoff
        status = self.query_one("#aeat-sync-status", Static)
        if not self._operation_can_start(request_id, status):
            return
        if operation_access_facts(str(request.operation)).reaches_network and not await self._refresh_auth():
            status.update(readiness_text(self.controller.auth_readiness))
            return
        self._consumed_request_ids.add(request_id)
        if handoff is None:
            status.update(tr("tui.aeat_sync.refusal.operation_handoff"))
            return
        self._in_flight_id = request_id
        self._set_operation_buttons_disabled(True)
        status.update(tr("tui.aeat_sync.operation.in_flight"))
        try:
            controller = await handoff(request)
            self._active_operation_request = request
            self._active_operation_controller = controller
            self._show_operation_modal(controller)
        except Exception:  # host boundary must not disclose protected diagnostics
            self._active_operation_request = None
            self._active_operation_controller = None
            status.update(tr("tui.aeat_sync.operation.failed"))
        else:
            status.update(tr("tui.aeat_sync.operation.handed_off"))
        finally:
            self._in_flight_id = None
            self._set_operation_buttons_disabled(False)
            event.button.disabled = True

    def _edit_auth(self) -> None:
        if self.controller.aeat_auth_setup is not None and self._in_flight_id is None:
            self.app.push_screen(AeatAuthSetupScreen(self.controller.aeat_auth_setup), self._auth_edited)

    def _operation_can_start(self, request_id: str, status: Static) -> bool:
        if request_id in self._consumed_request_ids:
            status.update(tr("tui.aeat_sync.operation.already_handled"))
            return False
        if self._in_flight_id is not None:
            status.update(tr("tui.aeat_sync.operation.in_flight"))
            return False
        return True

    def _show_operation_modal(self, controller: OperationControllerPort) -> None:
        """Mount the canonical progress surface for a host-started operation."""
        self.app.push_screen(OperationModal(controller), self._on_operation_settled)

    def _on_operation_settled(self, outcome: OperationModalOutcomeV1 | None) -> None:
        """Project an exact notifications-list result and refresh after success."""
        request, operation_controller = self._active_operation_request, self._active_operation_controller
        self._active_operation_request = None
        self._active_operation_controller = None
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            return
        projection = outcome.view_model.projection
        if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            return
        self.run_worker(
            self._refresh_after_success(
                projection,
                request=request,
                operation_controller=operation_controller,
            ),
            group="aeat-sync-refresh",
            exclusive=True,
        )

    async def _refresh_after_success(
        self,
        operation_projection: OperationPublicProjectionV1,
        *,
        request: AeatSyncOperationRequestV1 | None,
        operation_controller: OperationControllerPort | None,
    ) -> None:
        """Read the safe list summaries before rebuilding the workspace snapshot."""
        refresh = self.controller.refresh_snapshot
        notification_summary, result_failed = await read_notifications_summary(
            request, operation_controller, operation_projection
        )

        if refresh is not None:
            try:
                refreshed = await asyncio.to_thread(refresh)
                self.refresh_projection(refreshed)
            except Exception:  # The installed host may lose the bound session during refresh.
                self.query_one("#aeat-sync-status", Static).update(tr("tui.aeat_sync.operation.failed"))
                return
        if result_failed:
            self.query_one("#aeat-sync-status", Static).update(tr("tui.aeat_sync.operation.failed"))
        elif notification_summary is not None:
            self.query_one("#aeat-sync-status", Static).update(notification_summary)

    def _set_operation_buttons_disabled(self, disabled: bool) -> None:
        """Make the one-shot operation guard visible during a host handoff."""
        for button in self.query(".aeat-sync-operation"):
            button.disabled = (
                disabled
                or (button.id in self._consumed_request_ids)
                or self._authentication_blocks(self._requests.get(button.id or ""))
            )

    def _authentication_blocks(self, request: AeatSyncOperationRequestV1 | None) -> bool:
        """Require AEAT credentials only for operations that reach the network."""
        return (
            request is not None
            and operation_access_facts(str(request.operation)).reaches_network
            and self.controller.aeat_auth_setup is not None
            and (self.controller.auth_readiness is None or not self.controller.auth_readiness.ready)
        )

    async def _select_notification(self, row_key: str) -> None:
        """Open only a row AEAT has explicitly marked read."""
        row = self._notification_rows.get(row_key)
        status = self.query_one("#aeat-sync-status", Static)
        if row is None:
            return
        if row.read_state is not AeatSyncNotificationReadState.READ:
            status.update(tr("tui.aeat_sync.refusal.unread_notification"))
            return
        if self._in_flight_id is not None:
            status.update(tr("tui.aeat_sync.operation.in_flight"))
            return
        if row_key in self._consumed_notification_ids:
            status.update(tr("tui.aeat_sync.notification.already_handled"))
            return
        self._consumed_notification_ids.add(row_key)
        if self.controller.notification_document_handoff is None:
            status.update(tr("tui.aeat_sync.refusal.notification_handoff"))
            return
        self._in_flight_id = row_key
        status.update(tr("tui.aeat_sync.operation.in_flight"))
        try:
            opened = await self.controller.retrieve_notification_document(row)
        except Exception:  # host boundary must not disclose protected diagnostics
            status.update(tr("tui.aeat_sync.operation.failed"))
        else:
            status.update(
                tr("tui.aeat_sync.notification.document_handed_off")
                if opened
                else tr("tui.aeat_sync.refusal.notification_handoff")
            )
        finally:
            self._in_flight_id = None

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Request a host-owned internal route only for an observable zone."""
        table = cast("DataTable[str]", event.data_table)
        if table.id == "aeat-sync-rows" and self.zone is AeatSyncWorkspaceZone.NOTIFICATIONS:
            await self._select_notification(str(event.row_key.value))
            return
        if table.id != "aeat-sync-navigation":
            return
        zone = AeatSyncWorkspaceZone(event.row_key.value)
        if not self.controller.can_open(zone):
            self.query_one("#aeat-sync-status", Static).update(closed_zone_copy(self.controller.state_for(zone)))
            return
        self.post_message(AeatSyncRouteRequested(self.controller.target(zone)))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track semantic identity instead of a mutable row position."""
        table = cast("DataTable[str]", event.data_table)
        if table.id == "aeat-sync-rows":
            self._selected_row_key = str(event.row_key.value)

    def action_back(self) -> None:
        """Return a zone to the AEAT Sync overview; leave the workspace only from the overview."""
        # An overview that cannot open would bounce Back straight back here.
        if self.zone is AeatSyncWorkspaceZone.OVERVIEW or not self.controller.can_open(AeatSyncWorkspaceZone.OVERVIEW):
            self.dismiss(None)
            return
        self.post_message(AeatSyncRouteRequested(self.controller.target(AeatSyncWorkspaceZone.OVERVIEW)))

    def on_aeat_sync_route_requested(self, event: AeatSyncRouteRequested) -> None:
        """Resolve the requested zone here and hand the finished body to the host."""
        # Imported at call time: the route catalogue imports this module for the
        # concrete screens, so a module-scope import would form a cycle.
        from .routes import resolve_aeat_sync_screen

        replace_workspace_body(self.app, resolve_aeat_sync_screen(self.controller, event.target))


__all__ = [
    "AeatSyncRouteRequested",
    "AeatSyncWorkspaceScreen",
]
