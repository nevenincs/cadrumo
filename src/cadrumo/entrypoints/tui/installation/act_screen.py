"""One installation act: its form, its secret, its confirmation and how it settled.

The form is built from the act's request model. A changing act is first sent
without confirmation, so the person reads what it would do, and is sent
confirmed only after they say so once. A passphrase leaves its field as bytes
and is wiped whether or not the act was ever sent.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from threading import Event
from typing import ClassVar, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select, Static, TextArea
from textual.worker import Worker, WorkerCancelled, WorkerError, WorkerFailed

from ....adapters.local_runtime.installation_client import InstallationSecretHolder
from ....application.runtime.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActContract,
    RuntimeInstallationActRequest,
    installation_request_facts,
)
from ....core.async_cleanup import await_cancellation_complete
from ....core.i18n.render import tr
from ..components.account_chrome import AccountChromeScreen
from ..components.dialogs import ConfirmScreen
from ..components.status import PinnedStatusBar
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..secret.credentials import CREDENTIAL_PANEL_CSS
from .acts import ActField, ActFieldKind, ActInputError, OfferedAct, offered_act, supplied_member
from .door import (
    ActCompleted,
    ActFailed,
    ActOutcome,
    ActRefused,
    ActUnreachable,
    InstallationClientOpener,
    perform_act,
)
from .recovery_handover import RecoveryCodeHandover
from .rendering import ActPresentation, present_outcome
from .texts import act_label, act_summary, field_label, worded_in

_ENCODING = "utf-8"
_WORKER_GROUP = "tui-installation-act"


def _field_id(name: str) -> str:
    return f"installation-field-{name}"


class InstallationActScreen(AccountChromeScreen):
    """Ask for one act's inputs, run it through the runtime, and show the answer."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    CSS = (
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + tokenised(
            """
        /* In the page's flow: docked, it would lie over the account bar and this act's own title. */
        #installation-act-status { dock: none; }
        #installation-act-page { width: 100%; height: 1fr; padding: $cadrumo-space-0 $cadrumo-gutter; }
        #installation-act-summary { height: auto; margin: $cadrumo-stack $cadrumo-space-0; }
        .installation-json { height: auto; max-height: $cadrumo-log-max-height; }
        #installation-act-actions Button {
            margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap;
        }
        #installation-act-result { height: auto; margin: $cadrumo-stack $cadrumo-space-0; }
        #installation-act-table { width: 100%; }
        """
        )
    )

    def __init__(
        self,
        offered: OfferedAct,
        *,
        open_client: InstallationClientOpener,
        on_records_changed: Callable[[], None] | None = None,
        locale: str | None = None,
    ) -> None:
        """Bind one offered act to the door it is sent through, in the language of the area that lists it."""
        super().__init__()
        self._offered = offered
        self._open_client = open_client
        self._on_records_changed = on_records_changed
        self._locale = locale
        self._busy = False
        self._live = True
        self._act_worker: Worker[None] | None = None
        self._pending_passphrase: bytearray | None = None
        self._pending_handovers: set[Event] = set()
        self._outcome_read_by: InstallationAct | None = None

    @override
    def compose(self) -> ComposeResult:
        act = self._offered.act
        with worded_in(self._locale):
            title, summary = act_label(act), act_summary(act)
            worded_fields = [
                (field, field_label(field.name), self._field_hint(field)) for field in self._offered.fields
            ]
            passphrase_label = tr("tui.installation.passphrase.label")
            close_label, run_label = tr("tui.installation.action.close"), tr("tui.installation.action.run")
        yield Static(title, classes="cadrumo-banner", markup=False)
        yield PinnedStatusBar(id="installation-act-status")
        with ContentScroll(id="installation-act-page", classes="cadrumo-scroll"):
            yield Static(summary, id="installation-act-summary", classes="cadrumo-subtle", markup=False)
            for field, label, hint in worded_fields:
                yield from self._compose_field(field, label, hint)
            if self._offered.contract.takes_secret:
                yield Label(passphrase_label, classes="field-label")
                yield Input(password=True, id="installation-passphrase")
            with Horizontal(id="installation-act-actions", classes="credential-actions"):
                yield Button(close_label, id="installation-act-close")
                yield Button(run_label, id="installation-act-run", classes="-primary")
            yield Button(id="installation-act-outcome")
            table = ContentDataTable[str](id="installation-act-table", cursor_type="row", zebra_stripes=True)
            # Every column keeps its whole text; a row wider than the terminal scrolls sideways.
            table.fill_column = None
            yield table
            yield Static(id="installation-act-result", markup=False)

    @staticmethod
    def _compose_field(field: ActField, label: str, hint: str) -> ComposeResult:
        widget_id = _field_id(field.name)
        if field.kind is ActFieldKind.BOOLEAN:
            yield Checkbox(label, value=bool(field.default), id=widget_id)
            return
        yield Label(label, classes="field-label")
        if hint:
            yield Static(hint, classes="field-hint", markup=False)
        if field.kind is ActFieldKind.CHOICE:
            yield Select[str]([(choice, choice) for choice in field.choices], prompt=label, id=widget_id)
        elif field.kind is ActFieldKind.JSON:
            yield TextArea(id=widget_id, classes="installation-json")
        else:
            yield Input(
                value="" if field.default is None else str(field.default),
                type="integer" if field.kind is ActFieldKind.INTEGER else "text",
                id=widget_id,
            )

    @staticmethod
    def _field_hint(field: ActField) -> str:
        if field.supplied_by is not None:
            return tr("tui.installation.hint.supplied")
        if field.kind is ActFieldKind.PATH:
            return tr("tui.installation.hint.path")
        if field.kind is ActFieldKind.JSON:
            return tr("tui.installation.hint.json")
        if not field.required:
            return tr("tui.installation.hint.optional")
        return ""

    def on_mount(self) -> None:
        """Hide the empty result table, and answer at once a read that needs nothing from the person.

        A command that reads and has only optional arguments answers as soon
        as it is typed. The same read answers here as soon as it is opened,
        and its optional members stay on screen to narrow it afterwards.
        """
        self.query_one("#installation-act-table", DataTable).display = False
        self.query_one("#installation-act-outcome", Button).display = False
        needs_input = self._offered.contract.takes_secret or any(field.required for field in self._offered.fields)
        if self._offered.reads_only and not needs_input:
            self.call_after_refresh(self._start)
            return
        inputs = self.query("Input, Select, Checkbox, TextArea")
        (inputs.first() if inputs else self.query_one("#installation-act-run", Button)).focus()

    async def on_unmount(self) -> None:
        """Release an open code handover, wait for a running act, and wipe what it held."""
        self._live = False
        for secret_field in self.query("#installation-passphrase").results(Input):
            secret_field.value = ""
        for pending in tuple(self._pending_handovers):
            pending.set()
        worker = self._act_worker
        try:
            if worker is not None:
                worker.cancel()
                with suppress(WorkerCancelled, WorkerError, WorkerFailed):
                    await await_cancellation_complete(worker.wait(), task_name="tui-installation-act-drain")
        finally:
            self._wipe_pending_passphrase()

    def _active(self) -> bool:
        return self._live and self.is_mounted

    def _wipe_pending_passphrase(self) -> None:
        buffer = self._pending_passphrase
        if buffer is not None:
            buffer[:] = bytes(len(buffer))
        self._pending_passphrase = None

    def _controls(self) -> None:
        if not self._active():
            return
        for widget in self.query("Input, Select, Checkbox, TextArea, Button"):
            widget.disabled = self._busy

    def _form_values(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for field in self._offered.fields:
            selector = f"#{_field_id(field.name)}"
            if field.kind is ActFieldKind.BOOLEAN:
                values[field.name] = self.query_one(selector, Checkbox).value
            elif field.kind is ActFieldKind.CHOICE:
                chosen = cast("Select[str]", self.query_one(selector, Select)).value
                values[field.name] = chosen if isinstance(chosen, str) else ""
            elif field.kind is ActFieldKind.JSON:
                values[field.name] = self.query_one(selector, TextArea).text
            else:
                values[field.name] = self.query_one(selector, Input).value
        return values

    def _take_passphrase(self) -> bytearray | None:
        """Move the masked field's content into a buffer and empty the field at once."""
        field = self.query_one("#installation-passphrase", Input)
        buffer = bytearray(field.value, _ENCODING)
        field.value = ""
        return buffer

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Run the act or leave; nothing else on this screen acts."""
        if event.button.id == "installation-act-close":
            self.action_close()
        elif event.button.id == "installation-act-run":
            self._start()
        elif event.button.id == "installation-act-outcome" and self._outcome_read_by is not None:
            # The act is never sent again to find out: the read the table names says how it ended.
            self.app.push_screen(
                InstallationActScreen(
                    offered_act(self._outcome_read_by),
                    open_client=self._open_client,
                    on_records_changed=self._on_records_changed,
                    locale=self._locale,
                )
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the passphrase field runs the act, as it does at sign-in."""
        if event.input.id == "installation-passphrase":
            self._start()

    def _start(self) -> None:
        """Freeze the form's values and the passphrase, then run off the event loop's turn."""
        if self._busy or not self._active():
            return
        status = self.query_one("#installation-act-status", PinnedStatusBar)
        values = self._form_values()
        passphrase: bytearray | None = None
        if self._offered.contract.takes_secret:
            passphrase = self._take_passphrase()
            if not passphrase:
                with worded_in(self._locale):
                    status.show_error(tr("tui.installation.passphrase.required"))
                self.query_one("#installation-passphrase", Input).focus()
                return
        self._wipe_pending_passphrase()
        self._pending_passphrase = passphrase
        self._busy = True
        self._controls()
        self._show_progress()
        self._act_worker = self.run_worker(
            self._run(values, passphrase), name=_WORKER_GROUP, group=_WORKER_GROUP, exclusive=True, exit_on_error=False
        )

    def _show_progress(self) -> None:
        with worded_in(self._locale):
            self.query_one("#installation-act-status", PinnedStatusBar).show_progress(
                tr("tui.installation.status.progress")
            )

    async def _run(self, values: dict[str, object], passphrase: bytearray | None) -> None:
        try:
            await self._perform(values, passphrase)
        finally:
            # Every path ends here, so a passphrase the act never reached is wiped too.
            self._wipe_pending_passphrase()
            self._busy = False
            self._controls()

    async def _perform(self, values: dict[str, object], passphrase: bytearray | None) -> None:
        offered = self._offered
        try:
            supplied = await self._with_supplied_members(values)
            if supplied is None:
                return
            request = offered.request(supplied)
            confirmed = offered.request(supplied, confirmed=True) if offered.asks_confirmation else None
        except ActInputError as error:
            self._show_invalid(error)
            return
        if confirmed is None or not offered.changes_records(confirmed):
            self._show(await self._send(request, offered.contract, passphrase))
            return
        preview = await self._send(request, offered.contract, None if passphrase is None else bytearray(passphrase))
        self._show(preview, preview=True)
        if not isinstance(preview, ActCompleted | ActRefused) or not self._active():
            return
        with worded_in(self._locale):
            previewed = present_outcome(preview, offered.contract, preview=True)
        if not await self._confirmed(previewed):
            return
        self._show_progress()
        self._show(await self._send(confirmed, offered.contract, passphrase))

    async def _with_supplied_members(self, values: dict[str, object]) -> dict[str, object] | None:
        """Read a member the person left empty from the act that supplies it.

        Returns ``None`` when that read did not complete; its outcome is then
        what the screen shows.
        """
        prerequisite = self._offered.prerequisite
        if prerequisite is None or str(values.get(prerequisite.request_member) or "").strip():
            return values
        supplier = offered_act(prerequisite.act)
        request = supplier.request({field.name: values.get(field.name) for field in supplier.fields})
        outcome = await self._send(request, INSTALLATION_ACT_CONTRACTS[prerequisite.act], None)
        if not isinstance(outcome, ActCompleted):
            self._show(outcome)
            return None
        return {**values, prerequisite.request_member: supplied_member(prerequisite, outcome.reply)}

    async def _send(
        self,
        request: RuntimeInstallationActRequest,
        contract: InstallationActContract,
        passphrase: bytearray | None,
    ) -> ActOutcome:
        handover: InstallationSecretHolder | None = (
            RecoveryCodeHandover(self.app, pending=self._pending_handovers, locale=self._locale)
            if contract.delivers_secret
            else None
        )
        outcome = await perform_act(self._open_client, request, contract, passphrase=passphrase, hold_secret=handover)
        # A completed act changed records; a fault or a lost answer may have.
        may_have_changed = isinstance(outcome, ActCompleted | ActFailed) or (
            isinstance(outcome, ActUnreachable) and outcome.effect_unknown
        )
        if (
            may_have_changed
            and installation_request_facts(request).changes_records
            and self._on_records_changed is not None
        ):
            self._on_records_changed()
        return outcome

    async def _confirmed(self, preview: ActPresentation) -> bool:
        """Ask once, after the person has seen what the act would do."""
        with worded_in(self._locale):
            question = ConfirmScreen(
                title=tr("tui.installation.confirm.title", act=act_label(self._offered.act)),
                message="\n".join((*preview.lines, "", tr("tui.installation.confirm.question"))),
                confirm_label=tr("tui.installation.confirm.accept"),
                cancel_label=tr("tui.installation.confirm.cancel"),
            )
        answer = await self.app.push_screen_wait(question)
        return bool(answer) and self._active()

    def _show_invalid(self, error: ActInputError) -> None:
        if not self._active():
            return
        with worded_in(self._locale):
            named = ", ".join(field_label(name) for name in error.fields)
            self.query_one("#installation-act-status", PinnedStatusBar).show_error(
                tr("tui.installation.status.invalid_fields", fields=named)
            )
        with suppress(Exception):
            self.query_one(f"#{_field_id(error.fields[0])}").focus()

    def _show(self, outcome: ActOutcome, *, preview: bool = False) -> None:
        if not self._active():
            return
        status = self.query_one("#installation-act-status", PinnedStatusBar)
        with worded_in(self._locale):
            presentation = present_outcome(outcome, self._offered.contract, preview=preview)
            read_outcome = (
                ""
                if presentation.outcome_read_by is None
                else tr("tui.installation.action.read_outcome", act=act_label(presentation.outcome_read_by))
            )
        if presentation.tone == "success":
            status.show_success(presentation.status)
        elif presentation.tone == "warning":
            status.show_warning(presentation.status)
        else:
            status.show_error(presentation.status)
        self.query_one("#installation-act-result", Static).update("\n".join(presentation.lines))
        self._outcome_read_by = presentation.outcome_read_by
        offer = self.query_one("#installation-act-outcome", Button)
        offer.display = presentation.outcome_read_by is not None
        offer.label = read_outcome
        table = cast("DataTable[str]", self.query_one("#installation-act-table", DataTable))
        table.clear(columns=True)
        rows = presentation.table
        table.display = rows is not None
        if rows is not None:
            for column in rows.columns:
                table.add_column(column)
            for row in rows.rows:
                table.add_row(*row)
            cast("ContentDataTable[str]", table).absorb_surplus_width()

    def action_close(self) -> None:
        """Leave only while no act is in flight, so its answer is never lost unseen."""
        if not self._busy:
            self.dismiss(None)


__all__ = ["InstallationActScreen"]
