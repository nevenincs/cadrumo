"""Step-by-step invoice entry through the registered invoice wizard.

The wizard's request states every field at once and its owner validates them
all together, so the steps here only group the fields; nothing is checked or
sent until the last step's review. A refusal lists each field the owner
refused, and the operator corrects them in a fresh form that keeps what they
typed.
"""

from __future__ import annotations

from typing import ClassVar, Final, Protocol, cast, override
from uuid import UUID

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static

from ....application.invoices.catalogue_intake_contracts import InvoiceWizardOutcome, InvoiceWizardRequest
from ....core.aggregation import IntracomOperationType
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.iva.schema import InvoiceKind
from ..components.language import localized
from ..components.theme import tokenised
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

_STEPS: Final[tuple[tuple[str, tuple[tuple[str, bool], ...]], ...]] = (
    (
        "counterparty",
        (("counterparty_name", True), ("counterparty_nif", True), ("country_code", True)),
    ),
    (
        "invoice",
        (
            ("invoice_number", True),
            ("series", False),
            ("invoice_date", True),
            ("operation_date", False),
            ("invoice_class", False),
            ("rectifies_invoice_number", False),
        ),
    ),
    (
        "amounts",
        (
            ("taxable_base", True),
            ("iva_rate", False),
            ("currency", True),
            ("iva_category", False),
            ("retention_rate", False),
            ("retention_amount", False),
            ("recargo_amount", False),
        ),
    ),
    ("notes", (("notes", False),)),
)
"""Each step's name and its text fields, each with whether the owner requires it."""
_KIND_LOCALE_KEYS: Final = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}
_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "counterparty_name": "tui.ledger.invoice.field.counterparty_name",
    "counterparty_nif": "tui.ledger.invoice.field.counterparty_nif",
    "country_code": "tui.ledger.invoice.field.country_code",
    "invoice_number": "tui.ledger.invoice.field.invoice_number",
    "series": "tui.ledger.invoice.field.series",
    "invoice_date": "tui.ledger.invoice.field.invoice_date",
    "operation_date": "tui.ledger.invoice.field.operation_date",
    "invoice_class": "tui.ledger.invoice.field.invoice_class",
    "rectifies_invoice_number": "tui.ledger.invoice.field.rectifies_invoice_number",
    "taxable_base": "tui.ledger.invoice.field.taxable_base",
    "iva_rate": "tui.ledger.invoice.field.iva_rate",
    "currency": "tui.ledger.invoice.field.currency",
    "iva_category": "tui.ledger.invoice.field.iva_category",
    "retention_rate": "tui.ledger.invoice.field.retention_rate",
    "retention_amount": "tui.ledger.invoice.field.retention_amount",
    "recargo_amount": "tui.ledger.invoice.field.recargo_amount",
    "notes": "tui.ledger.invoice.field.notes",
    "operation_type": "tui.ledger.invoice.field.operation_type",
}
"""Each wizard field's label key: every text field of the steps, and the intra-EU operation type."""
_STEP_NAME_LOCALE_KEYS: Final[dict[str, str]] = {
    "counterparty": "tui.ledger.invoices.wizard.step_name.counterparty",
    "invoice": "tui.ledger.invoices.wizard.step_name.invoice",
    "amounts": "tui.ledger.invoices.wizard.step_name.amounts",
    "notes": "tui.ledger.invoices.wizard.step_name.notes",
}
_DEFAULTS: Final = {"currency": "EUR"}
_TEXT_FIELD_NAMES: Final = tuple(name for _step, fields in _STEPS for name, _required in fields)
_STEP_OF_FIELD: Final = {name: index for index, (_step, fields) in enumerate(_STEPS) for name, _required in fields}


class LedgerInvoiceWizardDoorV1(Protocol):
    """Injected door to ``ledger.invoice.wizard`` for one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def __call__(self, request: InvoiceWizardRequest) -> InvoiceWizardOutcome:
        """Record the invoice, or return the owner's field refusals with nothing written."""
        ...


def _field_label(name: str) -> str:
    """Name a wizard field; a field the owner names that the form does not show keeps its own name."""
    key = _FIELD_LOCALE_KEYS.get(name)
    return name if key is None else tr(key)


def _label_widget(name: str, *, required: bool) -> Static:
    key = _FIELD_LOCALE_KEYS[name]
    if required:
        return localized(Static(tr(key), markup=False), key)
    label = tr(key)
    return localized(
        Static(tr("tui.ledger.invoice.optional", label=label), markup=False), "tui.ledger.invoice.optional", label=label
    )


def _input_id(name: str) -> str:
    return f"ledger-invoices-wizard-{name.replace('_', '-')}"


class LedgerInvoiceWizardScreen(LedgerConfirmationFlowScreen):
    """Collect the wizard's fields a step at a time, review them, then record the invoice once."""

    FLOW_NAME: ClassVar[str] = "invoice_wizard"
    DEFAULT_CSS = tokenised(
        """
        .ledger-invoices-actions { height: auto; margin-bottom: $cadrumo-stack; }
        .ledger-invoices-actions Button { margin-right: $cadrumo-space-1; }
        .ledger-invoices-step { height: auto; }
        #ledger-invoices-wizard-summary { height: auto; }
        """
    )

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        door: LedgerInvoiceWizardDoorV1,
        *,
        values: dict[str, str] | None = None,
        step: int = 0,
    ) -> None:
        """Keep the injected door and the values a previous attempt left, opening at ``step``."""
        super().__init__(controller, id="ledger-invoices-wizard-screen")
        self.door = door
        self.values = dict(values or {})
        self.step = step
        self.request: InvoiceWizardRequest | None = None
        self.outcome: InvoiceWizardOutcome | None = None

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.invoices.wizard.title"), classes="cadrumo-banner"), "tui.ledger.invoices.wizard.title"
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="ledger-invoices-wizard-step", classes="cadrumo-heading", markup=False)
            for index, (name, fields) in enumerate(_STEPS):
                with Vertical(id=f"ledger-invoices-wizard-step-{name}", classes="ledger-invoices-step"):
                    if index == 0:
                        yield localized(
                            Static(tr("tui.ledger.invoice.field.kind"), markup=False), "tui.ledger.invoice.field.kind"
                        )
                        yield Select[str](
                            tuple((tr(_KIND_LOCALE_KEYS[kind]), kind.value) for kind in InvoiceKind),
                            value=self.values.get("kind", InvoiceKind.RECEIVED.value),
                            allow_blank=False,
                            id="ledger-invoices-wizard-kind",
                        )
                    for field, required in fields:
                        yield _label_widget(field, required=required)
                        yield Input(value=self.values.get(field, _DEFAULTS.get(field, "")), id=_input_id(field))
                    if name == "amounts":
                        yield _label_widget("operation_type", required=False)
                        yield Select[str](
                            tuple((key.value, key.value) for key in IntracomOperationType),
                            prompt=tr("tui.ledger.invoice.operation_type_none"),
                            allow_blank=True,
                            id="ledger-invoices-wizard-operation-type",
                        )
            with Horizontal(id="ledger-invoices-wizard-steps", classes="ledger-invoices-actions"):
                yield localized(
                    Button(tr("tui.ledger.invoices.wizard.previous"), id="ledger-invoices-wizard-previous"),
                    "tui.ledger.invoices.wizard.previous",
                )
                yield localized(
                    Button(tr("tui.ledger.invoices.wizard.next"), id="ledger-invoices-wizard-next"),
                    "tui.ledger.invoices.wizard.next",
                )
                yield localized(
                    Button(tr("tui.ledger.invoice.review"), id="ledger-invoices-wizard-review", variant="primary"),
                    "tui.ledger.invoice.review",
                )
            yield Static("", id="ledger-invoices-wizard-summary", markup=False)
            with Horizontal(id="ledger-invoices-wizard-decision", classes="ledger-invoices-actions"):
                yield localized(
                    Button(
                        tr("tui.ledger.invoices.wizard.confirm"),
                        id="ledger-invoices-wizard-confirm",
                        variant="primary",
                        disabled=True,
                    ),
                    "tui.ledger.invoices.wizard.confirm",
                )
                yield localized(
                    Button(tr("tui.ledger.records.cancel"), id="ledger-invoices-wizard-cancel", disabled=True),
                    "tui.ledger.records.cancel",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield localized(
                Button(tr("tui.ledger.invoices.wizard.again"), id="ledger-invoices-wizard-again"),
                "tui.ledger.invoices.wizard.again",
            )

    def on_mount(self) -> None:
        """Open at the chosen step with its first field focused."""
        self.populate_navigation()
        operation_type = self.values.get("operation_type")
        if operation_type is not None and operation_type:
            cast("Select[str]", self.query_one("#ledger-invoices-wizard-operation-type", Select)).value = operation_type
        self.query_one("#ledger-invoices-wizard-decision", Horizontal).display = False
        self.query_one("#ledger-invoices-wizard-again", Button).display = False
        self._show_step()

    @override
    async def refresh_language(self) -> None:
        """Reword the step heading after the shared copy."""
        await super().refresh_language()
        self._show_step()

    def _show_step(self) -> None:
        """Show only the current step's fields and the moves it allows."""
        editing = self.flow_state is LedgerFlowState.EDITING
        for index, (name, _fields) in enumerate(_STEPS):
            self.query_one(f"#ledger-invoices-wizard-step-{name}", Vertical).display = editing and index == self.step
        name = _STEPS[self.step][0]
        self.query_one("#ledger-invoices-wizard-step", Static).update(
            tr(
                "tui.ledger.invoices.wizard.step",
                index=str(self.step + 1),
                total=str(len(_STEPS)),
                name=tr(_STEP_NAME_LOCALE_KEYS[name]),
            )
        )
        self.query_one("#ledger-invoices-wizard-steps", Horizontal).display = editing
        self.query_one("#ledger-invoices-wizard-previous", Button).disabled = self.step == 0
        last = self.step == len(_STEPS) - 1
        self.query_one("#ledger-invoices-wizard-next", Button).display = not last
        self.query_one("#ledger-invoices-wizard-review", Button).display = last
        if editing:
            first = _STEPS[self.step][1][0][0]
            self.query_one(f"#{_input_id(first)}", Input).focus()

    def _collect(self) -> dict[str, str]:
        values = {name: self.query_one(f"#{_input_id(name)}", Input).value for name in _TEXT_FIELD_NAMES}
        values["kind"] = str(cast("Select[str]", self.query_one("#ledger-invoices-wizard-kind", Select)).value)
        operation_type = cast("Select[str]", self.query_one("#ledger-invoices-wizard-operation-type", Select)).value
        values["operation_type"] = operation_type if isinstance(operation_type, str) else ""
        return values

    def _build(self, values: dict[str, str]) -> InvoiceWizardRequest:
        def optional(name: str) -> str | None:
            return values[name].strip() or None

        return InvoiceWizardRequest(
            profile_id=self.door.profile_id,
            kind=InvoiceKind(values["kind"]),
            counterparty_nif=values["counterparty_nif"].strip(),
            counterparty_name=values["counterparty_name"].strip(),
            invoice_number=values["invoice_number"].strip(),
            invoice_date=values["invoice_date"].strip(),
            taxable_base=values["taxable_base"].strip(),
            iva_rate=optional("iva_rate"),
            currency=values["currency"].strip(),
            country_code=values["country_code"].strip(),
            operation_date=optional("operation_date"),
            notes=values["notes"],
            iva_category=optional("iva_category"),
            operation_type=IntracomOperationType(values["operation_type"]) if values["operation_type"] else None,
            retention_rate=optional("retention_rate"),
            retention_amount=optional("retention_amount"),
            invoice_class=optional("invoice_class"),
            series=optional("series"),
            rectifies_invoice_number=optional("rectifies_invoice_number"),
            recargo_amount=optional("recargo_amount"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Move between steps, review, record the reviewed invoice, cancel, or correct and retry."""
        button_id = event.button.id
        editing = self.flow_state is LedgerFlowState.EDITING
        if button_id == "ledger-invoices-wizard-previous" and editing and self.step > 0:
            self.step -= 1
            self._show_step()
        elif button_id == "ledger-invoices-wizard-next" and editing and self.step < len(_STEPS) - 1:
            self.step += 1
            self._show_step()
        elif button_id == "ledger-invoices-wizard-review" and editing:
            self._review()
        elif button_id == "ledger-invoices-wizard-cancel" and self.flow_state is LedgerFlowState.CONFIRMING:
            self._cancel_flow()
        elif button_id == "ledger-invoices-wizard-confirm" and self.flow_state is LedgerFlowState.CONFIRMING:
            self._confirm()
        elif button_id == "ledger-invoices-wizard-again":
            self._start_again()

    def _review(self) -> None:
        refusal = self.query_one("#ledger-refusal", Static)
        refusal.update("")
        self.values = self._collect()
        try:
            request = self._build(self.values)
        except ValidationError as error:
            refusal.update(door_refusal_text(error))
            return
        self.request = request
        self._transition(LedgerFlowState.CONFIRMING)
        lines = [
            tr("tui.ledger.invoices.wizard.summary_heading"),
            f"{tr('tui.ledger.invoice.field.kind')}: {tr(_KIND_LOCALE_KEYS[request.kind])}",
        ]
        for name in _TEXT_FIELD_NAMES:
            value = self.values[name].strip()
            if value:
                lines.append(f"{_field_label(name)}: {value}")
        if request.operation_type is not None:
            lines.append(f"{_field_label('operation_type')}: {request.operation_type.value}")
        self.query_one("#ledger-invoices-wizard-summary", Static).update("\n".join(lines))
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoices.wizard.confirming"))
        self._show_step()
        self.query_one("#ledger-invoices-wizard-decision", Horizontal).display = True
        self.query_one("#ledger-invoices-wizard-confirm", Button).disabled = False
        self.query_one("#ledger-invoices-wizard-cancel", Button).disabled = False
        self.query_one("#ledger-invoices-wizard-confirm", Button).focus()

    def _confirm(self) -> None:
        request = self.request
        if request is None:
            return
        self._transition(LedgerFlowState.SUBMITTING)
        self.query_one("#ledger-invoices-wizard-confirm", Button).disabled = True
        self.query_one("#ledger-invoices-wizard-cancel", Button).disabled = True
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoices.wizard.recording"))
        self.run_worker(self._submit(request), exclusive=True)

    async def _submit(self, request: InvoiceWizardRequest) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        refusal = self.query_one("#ledger-refusal", Static)
        try:
            outcome = await self.door(request)
        except CadrumoError as error:
            self._transition(LedgerFlowState.FAILED)
            refusal.update(door_refusal_text(error))
            status.update(self.failed_write_status(error, "tui.ledger.invoices.wizard.failed"))
            self._settled()
            return
        self.outcome = outcome
        if outcome.refusal is not None:
            self._transition(LedgerFlowState.FAILED)
            status.update(tr("tui.ledger.invoices.wizard.refused"))
            refusal.update(
                "\n".join(f"{_field_label(row.field)}: {row.reason}" for row in outcome.refusal.field_errors)
            )
            self._settled()
            return
        if outcome.result is None:
            self._transition(LedgerFlowState.FAILED)
            status.update(tr("tui.ledger.invoices.wizard.failed"))
            self._settled()
            return
        self._transition(LedgerFlowState.SUCCEEDED)
        invoice = outcome.result.invoice
        lines = [
            tr(
                "tui.ledger.invoices.wizard.recorded",
                number=invoice.invoice_number,
                total=f"{invoice.grand_total.decimal} {invoice.currency}",
            )
        ]
        if outcome.result.already_existed:
            lines.append(tr("tui.ledger.invoices.wizard.already_existed"))
        if outcome.result.euro_value_pending:
            lines.append(tr("tui.ledger.invoices.wizard.euro_value_pending"))
        status.update("\n".join(lines))
        self._settled()

    def _settled(self) -> None:
        self.query_one("#ledger-invoices-wizard-decision", Horizontal).display = False
        again = self.query_one("#ledger-invoices-wizard-again", Button)
        again.label = tr(
            "tui.ledger.invoices.wizard.correct"
            if self.flow_state is LedgerFlowState.FAILED
            else "tui.ledger.invoices.wizard.again"
        )
        again.display = True
        again.focus()

    @override
    def _cancel_flow(self) -> None:
        """Cancel before anything is submitted; nothing has been written."""
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self._transition(LedgerFlowState.CANCELLED)
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoices.wizard.cancelled"))
        self._settled()

    def _start_again(self) -> None:
        """Open a fresh wizard: after a refusal it keeps the values and opens at the first refused field."""
        state = self.flow_state
        if state not in {LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED, LedgerFlowState.CANCELLED}:
            return
        values = {} if state is LedgerFlowState.SUCCEEDED else self.values
        refusal = None if self.outcome is None else self.outcome.refusal
        step = 0 if refusal is None else min(_STEP_OF_FIELD.get(row.field, 0) for row in refusal.field_errors)

        def reopen() -> None:
            screen = LedgerInvoiceWizardScreen(self.controller, self.door, values=values, step=step)
            screen.back_area = self.back_area
            replace_workspace_body(self.app, screen)

        self.refresh_after_write(reopen)


__all__ = ["LedgerInvoiceWizardDoorV1", "LedgerInvoiceWizardScreen"]
