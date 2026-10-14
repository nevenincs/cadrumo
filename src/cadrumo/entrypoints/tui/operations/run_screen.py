"""Run one registered operation: its request form, its secret, and its settled result.

The form is derived from the operation's public request contract. Its request
is validated by the operation's own request model before anything is sent, and
is submitted the way every other frontend submits it: the registered payload,
the subject its contract declares, and any one-shot secret on the protected
frame. Nothing is retried; a submission whose reply was lost stays unknown.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import ClassVar, cast, override

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ItemGrid, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static, TextArea

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....core.async_cleanup import await_cancellation_complete
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.operations import OperationTerminalCondition
from ....core.request_faults import request_fault_line
from ..components.theme import BASE_CSS, tokenised
from .catalogue import OperationCatalogueEntryV1
from .modal import (
    OperationModal,
    OperationModalDetachedOutcomeV1,
    OperationModalOutcomeV1,
    OperationModalSettledOutcomeV1,
)
from .refusal_explanation import public_refusal_explanation
from .request_form import (
    RequestFieldKind,
    RequestFieldProblem,
    RequestFieldV1,
    derived_subject,
    field_texts,
    request_document,
    request_fields,
    subject_is_entered,
    validate_request,
)
from .run_result import receipt_text, result_pages, stopped_operation_text
from .runtime_controller import RuntimeOperationController

_CONTRACT_READ_SECONDS = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
_ACTION_MIN_COLUMN_WIDTH = 16
_REPLAY_KEY_MAX_LENGTH = 256
"""The longest replay key the operation request model accepts."""
_UNKNOWN_OUTCOME_CODES = frozenset({RefusalCode.DEADLINE_EXCEEDED, RefusalCode.CONNECTION_CLOSED})
"""Transport outcomes that leave unknown whether the runtime recorded the submission."""


def _kind_hint(kind: RequestFieldKind) -> str:
    """Say how one kind of value is entered, as the field's placeholder."""
    if kind is RequestFieldKind.INTEGER:
        return tr("tui.operations.form.hint.integer")
    if kind is RequestFieldKind.NUMBER:
        return tr("tui.operations.form.hint.number")
    if kind is RequestFieldKind.DECIMAL:
        return tr("tui.operations.form.hint.decimal")
    if kind is RequestFieldKind.DATE:
        return tr("tui.operations.form.hint.date")
    if kind is RequestFieldKind.DATETIME:
        return tr("tui.operations.form.hint.datetime")
    if kind is RequestFieldKind.UUID:
        return tr("tui.operations.form.hint.uuid")
    if kind is RequestFieldKind.PATH:
        return tr("tui.operations.form.hint.path")
    return tr("tui.operations.form.hint.text")


def _problem_text(problem: RequestFieldProblem) -> str:
    """Word why a field's text could not be read."""
    if problem is RequestFieldProblem.INTEGER:
        return tr("tui.operations.form.error.integer")
    if problem is RequestFieldProblem.NUMBER:
        return tr("tui.operations.form.error.number")
    if problem is RequestFieldProblem.JSON:
        return tr("tui.operations.form.error.json")
    return tr("tui.operations.form.error.choice")


class OperationRunScreen(Screen[None]):
    """Enter, validate and submit one operation's request, then show how it settled."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    CSS = BASE_CSS + tokenised("""
    #operation-run-page { width: 100%; height: 1fr; padding: $cadrumo-space-0 $cadrumo-gutter; }
    #operation-fields { width: 100%; height: auto; }
    .operation-field-label { margin: $cadrumo-stack $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0; }
    .operation-field-error, #operation-run-notice { color: $warning; height: auto; }
    .operation-json { height: auto; max-height: $cadrumo-log-max-height; }
    #operation-result-receipt, #operation-result-stopped { height: auto; margin: $cadrumo-stack $cadrumo-space-0; }
    #operation-run-actions {
        height: auto;
        grid-gutter: $cadrumo-space-0 $cadrumo-control-gap;
        padding: $cadrumo-space-0 $cadrumo-gutter;
    }
    #operation-run-actions Button { width: 1fr; margin: $cadrumo-space-0; }
    """)

    def __init__(self, client: FrontendClient, entry: OperationCatalogueEntryV1) -> None:
        """Bind the form to one admitted session and one registered operation."""
        super().__init__()
        self._client = client
        self._entry = entry
        self._fields: tuple[RequestFieldV1, ...] = request_fields(entry.input_json_schema, profile_id=client.profile_id)
        self._subject_entered = subject_is_entered(
            entry.contract.subject_reference, typed_operator_input=entry.typed_operator_input
        )
        self._json_mode = False
        self._submitting = False
        self._pages: tuple[str, ...] = ()
        self._page = 0

    @override
    def compose(self) -> ComposeResult:
        entry = self._entry
        yield Static(entry.definition_id, id="operation-run-title", classes="cadrumo-banner", markup=False)
        with VerticalScroll(id="operation-run-page"):
            yield Static(entry.summary, id="operation-run-summary", markup=False)
            yield Static(
                f"{tr('tui.operations.form.profile')}: {self._client.profile_id}\n"
                f"{tr('tui.operations.form.session')}: {self._client.session_id}",
                id="operation-run-session",
                markup=False,
            )
            yield Static("", id="operation-run-subject", markup=False)
            if self._subject_entered:
                yield Static(tr("tui.operations.form.subject_entry"), classes="operation-field-label", markup=False)
                yield Input(id="operation-subject-entry")
            if entry.contract.ephemeral_secret_required:
                yield Static(tr("tui.operations.form.secret"), classes="operation-field-label", markup=False)
                yield Input(password=True, id="operation-secret")
            with Vertical(id="operation-fields"):
                for index, field in enumerate(self._fields):
                    yield Static(
                        self._field_label(field),
                        id=f"operation-field-label-{index}",
                        classes="operation-field-label",
                        markup=False,
                    )
                    yield self._field_widget(index, field)
                    yield Static("", id=f"operation-field-error-{index}", classes="operation-field-error", markup=False)
            whole_request = TextArea("", id="operation-json", classes="operation-json")
            whole_request.display = False
            yield whole_request
            if entry.accepts_replay_key:
                yield Static(
                    f"{tr('tui.operations.form.replay_key')}\n{tr('tui.operations.form.replay_key_hint')}",
                    classes="operation-field-label",
                    markup=False,
                )
                yield Input(max_length=_REPLAY_KEY_MAX_LENGTH, id="operation-replay-key")
            yield Static("", id="operation-run-notice", markup=False)
            yield Static("", id="operation-result-receipt", markup=False)
            yield Static("", id="operation-result-stopped", markup=False)
            yield Static("", id="operation-result-page", markup=False)
            yield Static("", id="operation-result-body", markup=False)
        with ItemGrid(id="operation-run-actions", min_column_width=_ACTION_MIN_COLUMN_WIDTH):
            yield Button(tr("tui.operations.action.run"), id="operation-run", classes="-primary")
            yield Button(tr("tui.operations.action.edit_json"), id="operation-toggle-json")
            yield Button(tr("tui.operations.action.previous_page"), id="operation-result-previous", disabled=True)
            yield Button(tr("tui.operations.action.next_page"), id="operation-result-next", disabled=True)
            yield Button(tr("tui.operations.action.close"), id="operation-close")

    def on_mount(self) -> None:
        """Show the subject the untouched form already determines."""
        self._show_subject(request_document(self._fields, self._texts())[0])

    @staticmethod
    def _field_label(field: RequestFieldV1) -> str:
        heading = field.name
        if field.required:
            heading = f"{heading} ({tr('tui.operations.form.required')})"
        if field.session_fixed:
            heading = f"{heading} ({tr('tui.operations.form.fixed')})"
        return heading if not field.description else f"{heading}\n{field.description}"

    @staticmethod
    def _field_widget(index: int, field: RequestFieldV1) -> Static | Select[str] | TextArea | Input:
        widget_id = f"operation-field-{index}"
        if field.session_fixed:
            return Static(field.initial, id=widget_id, markup=False)
        if field.kind in {RequestFieldKind.BOOLEAN, RequestFieldKind.ENUM}:
            labels = ("true", "false") if field.kind is RequestFieldKind.BOOLEAN else field.choice_labels
            return Select[str](
                [(label, label) for label in labels],
                prompt=tr("tui.operations.form.choose"),
                value=field.initial if field.initial in labels else Select.NULL,
                id=widget_id,
            )
        if field.kind is RequestFieldKind.JSON:
            return TextArea(field.initial, id=widget_id, classes="operation-json")
        return Input(value=field.initial, placeholder=_kind_hint(field.kind), id=widget_id)

    def _texts(self) -> dict[str, str]:
        """Read every field's current text; a field the session fixes reads as its fixed value."""
        texts: dict[str, str] = {}
        for index, field in enumerate(self._fields):
            if field.session_fixed:
                texts[field.name] = field.initial
                continue
            widget = self.query_one(f"#operation-field-{index}")
            if isinstance(widget, Select):
                value = cast("Select[str]", widget).value
                texts[field.name] = value if isinstance(value, str) else ""
            elif isinstance(widget, TextArea):
                texts[field.name] = widget.text
            elif isinstance(widget, Input):
                texts[field.name] = widget.value
        return texts

    def _show_texts(self, texts: dict[str, str]) -> None:
        for index, field in enumerate(self._fields):
            if field.session_fixed:
                continue
            text = texts.get(field.name, "")
            widget = self.query_one(f"#operation-field-{index}")
            if isinstance(widget, Select):
                select = cast("Select[str]", widget)
                labels = ("true", "false") if field.kind is RequestFieldKind.BOOLEAN else field.choice_labels
                select.value = text if text in labels else Select.NULL
            elif isinstance(widget, TextArea):
                widget.load_text(text)
            elif isinstance(widget, Input):
                widget.value = text

    def _notice(self, text: str) -> None:
        self.query_one("#operation-run-notice", Static).update(text)

    def _clear_errors(self) -> None:
        self._notice("")
        for index in range(len(self._fields)):
            self.query_one(f"#operation-field-error-{index}", Static).update("")

    def _show_field_errors(self, errors: dict[str, tuple[str, ...]]) -> list[str]:
        """Write each error under its field and return the lines no field could take."""
        indexes = {field.name: index for index, field in enumerate(self._fields)}
        unplaced: list[str] = []
        for name, messages in errors.items():
            index = indexes.get(name)
            if index is None or self._json_mode:
                unplaced.extend(f"{name}: {message}" for message in messages)
                continue
            self.query_one(f"#operation-field-error-{index}", Static).update("\n".join(messages))
        return unplaced

    def _show_subject(self, document: dict[str, object]) -> str | None:
        entered = self.query_one("#operation-subject-entry", Input).value if self._subject_entered else None
        subject = derived_subject(
            self._entry.contract.subject_reference,
            profile_id=self._client.profile_id,
            document=document,
            entered=entered,
            typed_operator_input=self._entry.typed_operator_input,
        )
        shown = subject if subject is not None else tr("tui.operations.form.subject_pending")
        self.query_one("#operation-run-subject", Static).update(f"{tr('tui.operations.form.subject')}: {shown}")
        return subject

    def _document(self) -> dict[str, object] | None:
        """Read the request document from the fields, or from the whole-request editor."""
        if not self._json_mode:
            document, problems = request_document(self._fields, self._texts())
            unplaced = self._show_field_errors({name: (_problem_text(problem),) for name, problem in problems.items()})
            if problems:
                self._notice("\n".join((tr("tui.operations.form.invalid"), *unplaced)))
                return None
            return document
        try:
            parsed = json.loads(self.query_one("#operation-json", TextArea).text)
        except ValueError:
            parsed = None
        if not isinstance(parsed, dict):
            self._notice(tr("tui.operations.form.error.json_object"))
            return None
        return {str(name): value for name, value in cast("dict[object, object]", parsed).items()}

    def _prepared(self) -> tuple[BaseModel, str] | None:
        """Validate the entered request and derive its subject, showing what is wrong."""
        self._clear_errors()
        document = self._document()
        if document is None:
            return None
        subject = self._show_subject(document)
        validation = validate_request(self._entry.input_type, document)
        if validation.payload is None:
            unplaced = self._show_field_errors(dict(validation.field_errors))
            self._notice("\n".join((tr("tui.operations.form.invalid"), *validation.general_errors, *unplaced)))
            return None
        if subject is None:
            self._notice(tr("tui.operations.form.subject_missing"))
            return None
        return validation.payload, subject

    def _take_secret(self) -> bytearray | None:
        """Move the entered secret into a buffer and clear its field at once."""
        field = self.query_one("#operation-secret", Input)
        secret = bytearray(field.value, "utf-8")
        field.value = ""
        return secret

    def _replay_key(self) -> str | None:
        """Read the replay key the person entered; an empty field submits without one."""
        if not self._entry.accepts_replay_key:
            return None
        return self.query_one("#operation-replay-key", Input).value.strip() or None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch the form's own controls."""
        button_id = event.button.id
        if button_id == "operation-close":
            self.action_close()
        elif button_id == "operation-toggle-json":
            self._toggle_json()
        elif button_id == "operation-result-previous":
            self._show_page(self._page - 1)
        elif button_id == "operation-result-next":
            self._show_page(self._page + 1)
        elif button_id == "operation-run":
            self._run()

    def action_close(self) -> None:
        """Return to the list of operations."""
        self.dismiss(None)

    def _toggle_json(self) -> None:
        """Swap between the typed fields and the whole request as JSON, keeping what was entered."""
        self._clear_errors()
        whole_request = self.query_one("#operation-json", TextArea)
        if not self._json_mode:
            document, _problems = request_document(self._fields, self._texts())
            whole_request.load_text(json.dumps(document, ensure_ascii=False, indent=2))
        else:
            document_or_none = self._document()
            if document_or_none is None:
                return
            known = {field.name for field in self._fields}
            if not set(document_or_none) <= known:
                self._notice(tr("tui.operations.form.error.json_unknown_fields"))
                return
            self._show_texts(field_texts(self._fields, document_or_none))
        self._json_mode = not self._json_mode
        whole_request.display = self._json_mode
        self.query_one("#operation-fields", Vertical).display = not self._json_mode
        self.query_one("#operation-toggle-json", Button).label = (
            tr("tui.operations.action.edit_fields") if self._json_mode else tr("tui.operations.action.edit_json")
        )

    def _run(self) -> None:
        if self._submitting:
            return
        prepared = self._prepared()
        if prepared is None:
            return
        payload, subject = prepared
        secret: bytearray | None = None
        if self._entry.contract.ephemeral_secret_required:
            secret = self._take_secret()
            if not (secret is not None and secret):
                self._notice(tr("tui.operations.form.secret_required"))
                return
        self._submitting = True
        self.query_one("#operation-run", Button).disabled = True
        self._clear_result()
        self.run_worker(self._submit(payload, subject, secret, self._replay_key()), group="operation-run-submission")

    async def _submit(self, payload: BaseModel, subject: str, secret: bytearray | None, replay_key: str | None) -> None:
        client, entry = self._client, self._entry
        try:
            controller = await self._submitted(client, entry, payload, subject, secret, replay_key)
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))
            self._submitting = False
            self.query_one("#operation-run", Button).disabled = False
        if controller is None:
            return
        try:
            await controller.start()
        except CadrumoError as error:
            # The submission is recorded; only its start is unconfirmed.
            self._show_receipt(
                f"{tr('tui.operations.receipt.operation')}: {controller.operation_id}\n"
                f"{tr('tui.operations.run.start_unconfirmed')}\n{self._failure_text(error)}"
            )
            return

        def settled(outcome: OperationModalOutcomeV1 | None) -> None:
            self._settled(controller, outcome)

        self.app.push_screen(OperationModal(controller), settled)

    async def _submitted(
        self,
        client: FrontendClient,
        entry: OperationCatalogueEntryV1,
        payload: BaseModel,
        subject: str,
        secret: bytearray | None,
        replay_key: str | None,
    ) -> RuntimeOperationController | None:
        try:
            live = await await_cancellation_complete(
                asyncio.to_thread(
                    client.contract, entry.definition_id, deadline=time.monotonic() + _CONTRACT_READ_SECONDS
                ),
                task_name="tui-operation-run-contract",
            )
            if live != entry.contract:
                # The form was built from another contract than the runtime now serves.
                self._notice(tr("tui.operations.run.contract_changed"))
                return None
            return await RuntimeOperationController.submit(
                client,
                definition_id=entry.definition_id,
                subject_ref=subject,
                payload=payload,
                expected_session_id=client.session_id,
                financial_input=entry.typed_operator_input,
                secret=secret,
                idempotency_key=replay_key,
            )
        except CadrumoError as error:
            self._notice(self._failure_text(error))
            return None

    @staticmethod
    def _failure_text(error: CadrumoError) -> str:
        message = resolve_error_message(error)
        if isinstance(error, RefusalError) and error.reason in _UNKNOWN_OUTCOME_CODES:
            return f"{tr('tui.operations.run.unknown')}\n{message}"
        if isinstance(error, FrontendRefusedError) and error.request_faults:
            # The runtime's request model refused a payload the form's own check let through.
            return "\n".join((message, *(request_fault_line(fault) for fault in error.request_faults)))
        if isinstance(error, FrontendRefusedError) and error.holder_operation_id is not None:
            # A busy subject names the unsettled operation holding it, so the person can follow it.
            return f"{message}\n{tr('tui.operations.run.busy_holder', operation_id=error.holder_operation_id)}"
        return message

    def _show_receipt(self, text: str) -> None:
        self.query_one("#operation-result-receipt", Static).update(text)

    def _clear_result(self) -> None:
        self._show_receipt("")
        self.query_one("#operation-result-stopped", Static).update("")
        self._pages = ()
        self._show_page(0)

    def _settled(self, controller: RuntimeOperationController, outcome: OperationModalOutcomeV1 | None) -> None:
        if isinstance(outcome, OperationModalSettledOutcomeV1):
            self.run_worker(self._show_result(controller, outcome), group="operation-run-result")
        elif isinstance(outcome, OperationModalDetachedOutcomeV1):
            self._show_receipt(
                f"{tr('tui.operations.receipt.operation')}: {outcome.operation_id}\n{tr('tui.operations.run.detached')}"
            )
        else:
            self._show_receipt(
                f"{tr('tui.operations.receipt.operation')}: {controller.operation_id}\n"
                f"{tr('tui.operations.run.unobserved')}"
            )

    async def _show_result(
        self, controller: RuntimeOperationController, outcome: OperationModalSettledOutcomeV1
    ) -> None:
        projection = outcome.view_model.projection
        contract = projection.definition_contract
        self._show_receipt(receipt_text(projection))
        condition = projection.terminal_condition
        if condition in {OperationTerminalCondition.REFUSED, OperationTerminalCondition.FAILED}:
            stopped = stopped_operation_text(await controller.settled_error_detail(projection))
            fallback = outcome.error_explanation or public_refusal_explanation(projection.refusal_ref) or ""
            self.query_one("#operation-result-stopped", Static).update(stopped or fallback)
        readable = (condition is OperationTerminalCondition.SUCCEEDED and projection.result_ref is not None) or (
            condition is OperationTerminalCondition.REFUSED and projection.refusal_ref in contract.refusal_detail_codes
        )
        result_type = self._entry.result_type
        if not readable or result_type is None:
            return
        try:
            result = await controller.read_registered_result(projection, result_type, allow_refusal_detail=True)
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return
        self._pages = result_pages(result)
        self._show_page(0)

    def _show_page(self, page: int) -> None:
        """Show one bounded page of the formatted result and enable the pages beside it."""
        pages = self._pages
        self._page = min(max(page, 0), max(len(pages) - 1, 0))
        self.query_one("#operation-result-body", Static).update(pages[self._page] if pages else "")
        self.query_one("#operation-result-page", Static).update(
            tr("tui.operations.result.page", page=self._page + 1, pages=len(pages)) if pages else ""
        )
        self.query_one("#operation-result-previous", Button).disabled = self._page <= 0
        self.query_one("#operation-result-next", Button).disabled = self._page >= len(pages) - 1


__all__ = ["OperationRunScreen"]
