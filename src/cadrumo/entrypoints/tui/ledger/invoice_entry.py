"""Invoice entry form: type one invoice, review it, and record it through the catalogue writer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, Input, Select, Static

from ....core.aggregation import IntracomOperationType
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....domain.invoices.models import InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from .controller import LedgerInvoiceEntryRequested, LedgerWorkspaceController, ledger_copy
from .models import LedgerFlowState, LedgerInvoiceClassChoice, LedgerInvoiceEntryV1, LedgerInvoiceLineEntryV1
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

#: Text fields in form order, each with whether the writer requires it. The
#: taxable base is required only when no line is entered, which the reader
#: checks separately.
_TEXT_FIELDS: Final[tuple[tuple[str, bool], ...]] = (
    ("counterparty_name", True),
    ("counterparty_nif", False),
    ("country_code", True),
    ("invoice_number", True),
    ("invoice_date", True),
    ("operation_date", False),
    ("taxable_base", False),
    ("iva_rate", False),
    ("iva_category", False),
    ("currency", True),
    ("retention_rate", False),
    ("retention_amount", False),
    ("recargo_amount", False),
    ("series", False),
    ("rectifies_invoice_number", False),
    ("notes", False),
)
_DEFAULTS: Final[dict[str, str]] = {"country_code": "ES", "currency": "EUR"}

#: One invoice line's inputs in form order, each with whether the line model
#: requires it. They are the domain line's own fields; the writer validates the
#: typed line as that domain line against the pinned authority.
_LINE_FIELDS: Final[tuple[tuple[str, bool], ...]] = (
    ("description", True),
    ("quantity", True),
    ("unit_price", True),
    ("subtotal", True),
    ("iva_rate", True),
    ("iva_amount", True),
    ("spending_category_id", False),
    ("oss_rate_kind", False),
)


_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "kind": "tui.ledger.invoice.field.kind",
    "counterparty_name": "tui.ledger.invoice.field.counterparty_name",
    "counterparty_nif": "tui.ledger.invoice.field.counterparty_nif",
    "country_code": "tui.ledger.invoice.field.country_code",
    "invoice_number": "tui.ledger.invoice.field.invoice_number",
    "invoice_date": "tui.ledger.invoice.field.invoice_date",
    "operation_date": "tui.ledger.invoice.field.operation_date",
    "operation_type": "tui.ledger.invoice.field.operation_type",
    "taxable_base": "tui.ledger.invoice.field.taxable_base",
    "iva_rate": "tui.ledger.invoice.field.iva_rate",
    "iva_category": "tui.ledger.invoice.field.iva_category",
    "currency": "tui.ledger.invoice.field.currency",
    "retention_rate": "tui.ledger.invoice.field.retention_rate",
    "retention_amount": "tui.ledger.invoice.field.retention_amount",
    "recargo_amount": "tui.ledger.invoice.field.recargo_amount",
    "invoice_class": "tui.ledger.invoice.field.invoice_class",
    "series": "tui.ledger.invoice.field.series",
    "rectifies_invoice_number": "tui.ledger.invoice.field.rectifies_invoice_number",
    "notes": "tui.ledger.invoice.field.notes",
}
_LINE_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "description": "tui.ledger.invoice.line.field.description",
    "quantity": "tui.ledger.invoice.line.field.quantity",
    "unit_price": "tui.ledger.invoice.line.field.unit_price",
    "subtotal": "tui.ledger.invoice.line.field.subtotal",
    "iva_rate": "tui.ledger.invoice.line.field.iva_rate",
    "iva_amount": "tui.ledger.invoice.line.field.iva_amount",
    "spending_category_id": "tui.ledger.invoice.line.field.spending_category_id",
    "oss_rate_kind": "tui.ledger.invoice.line.field.oss_rate_kind",
}
_KIND_LOCALE_KEYS: Final[dict[InvoiceKind, str]] = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}
_CLASS_LOCALE_KEYS: Final[dict[LedgerInvoiceClassChoice, str]] = {
    LedgerInvoiceClassChoice.ORDINARIA: "tui.ledger.invoice.class.ordinaria",
    LedgerInvoiceClassChoice.SIMPLIFICADA: "tui.ledger.invoice.class.simplificada",
    LedgerInvoiceClassChoice.RECTIFICATIVA: "tui.ledger.invoice.class.rectificativa",
}


def _field_label(name: str) -> str:
    return ledger_copy(_FIELD_LOCALE_KEYS[name])


def _line_field_label(name: str) -> str:
    return ledger_copy(_LINE_FIELD_LOCALE_KEYS[name])


def _line_input_id(name: str) -> str:
    return f"ledger-invoice-line-{name.replace('_', '-')}"


def invoice_line_row(index: int, line: InvoiceLine | LedgerInvoiceLineEntryV1) -> str:
    """Render one invoice line as its numbered row, for entry review and the detail view alike."""
    return ledger_copy(
        "tui.ledger.invoice.line.row",
        index=str(index),
        description=line.description,
        quantity=format(line.quantity, "f"),
        unit_price=format(line.unit_price, "f"),
        subtotal=format(line.subtotal, "f"),
        rate=str(line.iva_rate),
        amount=format(line.iva_amount, "f"),
    )


class LedgerInvoiceEntryScreen(LedgerConfirmationFlowScreen):
    """Collect every field ``invoice add`` takes, then write only after review."""

    FLOW_NAME = "invoice_entry"
    CSS: ClassVar[str] = (
        LedgerConfirmationFlowScreen.CSS
        + """
    #ledger-invoice-again { display: none; }
    #ledger-invoice-again.-open { display: block; }
    """
    )

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Start with an empty form and no lines."""
        super().__init__(controller, id="ledger-invoice-entry-screen")
        self.entry: LedgerInvoiceEntryV1 | None = None
        self.lines: list[LedgerInvoiceLineEntryV1] = []

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.invoice.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(ledger_copy("tui.ledger.invoice.prompt"), markup=False)
            yield Static(_field_label("kind"), markup=False)
            yield Select[str](
                tuple((ledger_copy(_KIND_LOCALE_KEYS[kind]), kind.value) for kind in InvoiceKind),
                value=InvoiceKind.RECEIVED.value,
                allow_blank=False,
                id="ledger-invoice-kind",
            )
            for name, required in _TEXT_FIELDS:
                label = _field_label(name)
                yield Static(
                    label if required else ledger_copy("tui.ledger.invoice.optional", label=label), markup=False
                )
                yield Input(value=_DEFAULTS.get(name, ""), id=f"ledger-invoice-{name.replace('_', '-')}")
            yield Static(ledger_copy("tui.ledger.invoice.optional", label=_field_label("operation_type")), markup=False)
            yield Select[str](
                tuple((key.value, key.value) for key in IntracomOperationType),
                prompt=ledger_copy("tui.ledger.invoice.operation_type_none"),
                allow_blank=True,
                id="ledger-invoice-operation-type",
            )
            yield Static(_field_label("invoice_class"), markup=False)
            yield Select[str](
                tuple((ledger_copy(_CLASS_LOCALE_KEYS[choice]), choice.value) for choice in LedgerInvoiceClassChoice),
                value=LedgerInvoiceClassChoice.ORDINARIA.value,
                allow_blank=False,
                id="ledger-invoice-class",
            )
            yield Static(ledger_copy("tui.ledger.invoice.line.heading"), markup=False)
            for name, required in _LINE_FIELDS:
                label = _line_field_label(name)
                yield Static(
                    label if required else ledger_copy("tui.ledger.invoice.optional", label=label), markup=False
                )
                yield Input(id=_line_input_id(name))
            yield Button(ledger_copy("tui.ledger.invoice.line.add"), id="ledger-invoice-line-add")
            yield Button(ledger_copy("tui.ledger.invoice.line.remove"), id="ledger-invoice-line-remove", disabled=True)
            yield Static(ledger_copy("tui.ledger.invoice.line.none"), id="ledger-invoice-lines", markup=False)
            yield Button(ledger_copy("tui.ledger.invoice.review"), id="ledger-invoice-review", variant="primary")
            yield Static("", id="ledger-invoice-summary", markup=False)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Button(ledger_copy("tui.ledger.invoice.confirm"), id="ledger-invoice-confirm", disabled=True)
            yield Button(ledger_copy("tui.ledger.invoice.cancel"), id="ledger-invoice-cancel")
            yield Button(ledger_copy("tui.ledger.invoice.again"), id="ledger-invoice-again")
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Start at the first field the operator types."""
        self.populate_navigation()
        self.query_one("#ledger-invoice-counterparty-name", Input).focus()

    def _text(self, name: str) -> str:
        return self.query_one(f"#ledger-invoice-{name.replace('_', '-')}", Input).value.strip()

    def _render_lines(self) -> None:
        listing = self.query_one("#ledger-invoice-lines", Static)
        if not self.lines:
            listing.update(ledger_copy("tui.ledger.invoice.line.none"))
        else:
            listing.update("\n".join(invoice_line_row(index, line) for index, line in enumerate(self.lines, start=1)))
        self.query_one("#ledger-invoice-line-remove", Button).disabled = not self.lines

    def _add_line(self) -> tuple[str, ...]:
        """Append the typed line with its numbers parsed, or name every field that cannot be read."""
        values = {name: self.query_one(f"#{_line_input_id(name)}", Input).value.strip() for name, _ in _LINE_FIELDS}
        problems = [
            ledger_copy("tui.ledger.invoice.problem.required", field=_line_field_label(name))
            for name, required in _LINE_FIELDS
            if required and not values[name]
        ]
        numbers: dict[str, Decimal] = {}
        for name in ("quantity", "unit_price", "subtotal", "iva_amount"):
            if not values[name]:
                continue
            try:
                parsed = Decimal(values[name])
            except InvalidOperation:
                parsed = None
            if parsed is None or not parsed.is_finite():
                problems.append(ledger_copy("tui.ledger.invoice.problem.amount", field=_line_field_label(name)))
            else:
                numbers[name] = parsed
        if problems:
            return tuple(problems)
        try:
            line = LedgerInvoiceLineEntryV1(
                description=values["description"],
                quantity=numbers["quantity"],
                unit_price=numbers["unit_price"],
                subtotal=numbers["subtotal"],
                iva_rate=values["iva_rate"],
                iva_amount=numbers["iva_amount"],
                spending_category_id=values["spending_category_id"] or None,
                oss_rate_kind=values["oss_rate_kind"] or None,
            )
        except (CadrumoError, ValidationError) as error:
            return (door_refusal_text(error),)
        self.lines.append(line)
        for name, _required in _LINE_FIELDS:
            self.query_one(f"#{_line_input_id(name)}", Input).value = ""
        self._render_lines()
        return ()

    def _read_entry(self) -> tuple[LedgerInvoiceEntryV1 | None, tuple[str, ...]]:
        """Parse the form, naming every field that cannot be read rather than only the first."""
        problems: list[str] = []
        values = {name: self._text(name) for name, _required in _TEXT_FIELDS}
        for name, required in _TEXT_FIELDS:
            if required and not values[name]:
                problems.append(ledger_copy("tui.ledger.invoice.problem.required", field=_field_label(name)))
        # An invoice is entered either by its lines or by one base and rate,
        # never both: the writer would refuse the pair as two truths for one
        # line set, and neither would be the one printed on the invoice.
        if self.lines and (values["taxable_base"] or values["iva_rate"]):
            problems.append(ledger_copy("tui.ledger.invoice.problem.lines_and_base"))
        if not self.lines and not values["taxable_base"]:
            problems.append(ledger_copy("tui.ledger.invoice.problem.base_or_lines"))

        def amount(name: str) -> Decimal | None:
            raw = values[name]
            if not raw:
                return None
            try:
                parsed = Decimal(raw)
            except InvalidOperation:
                problems.append(ledger_copy("tui.ledger.invoice.problem.amount", field=_field_label(name)))
                return None
            if not parsed.is_finite():
                problems.append(ledger_copy("tui.ledger.invoice.problem.amount", field=_field_label(name)))
                return None
            return parsed

        def day(name: str) -> date | None:
            if not values[name]:
                return None
            try:
                return date.fromisoformat(values[name])
            except ValueError:
                problems.append(ledger_copy("tui.ledger.invoice.problem.date", field=_field_label(name)))
                return None

        issued = day("invoice_date")
        operation_date = day("operation_date")
        base = amount("taxable_base")
        iva_rate = amount("iva_rate")
        retention_rate = amount("retention_rate")
        retention_amount = amount("retention_amount")
        recargo_amount = amount("recargo_amount")
        if problems or issued is None:
            return None, tuple(problems)
        kind = InvoiceKind(str(cast("Select[str]", self.query_one("#ledger-invoice-kind", Select)).value))
        invoice_class = LedgerInvoiceClassChoice(
            str(cast("Select[str]", self.query_one("#ledger-invoice-class", Select)).value)
        )
        operation_type_value = cast("Select[str]", self.query_one("#ledger-invoice-operation-type", Select)).value
        try:
            entry = LedgerInvoiceEntryV1(
                kind=kind,
                counterparty_name=values["counterparty_name"],
                counterparty_nif=values["counterparty_nif"] or None,
                country_code=values["country_code"].upper(),
                invoice_number=values["invoice_number"],
                invoice_date=issued,
                taxable_base=base,
                iva_rate=iva_rate,
                lines=tuple(self.lines),
                operation_type=(
                    IntracomOperationType(operation_type_value) if isinstance(operation_type_value, str) else None
                ),
                operation_date=operation_date,
                recargo_amount=recargo_amount,
                rectifies_invoice_number=values["rectifies_invoice_number"] or None,
                iva_category=IvaCategory(values["iva_category"]) if values["iva_category"] else None,
                currency=values["currency"].upper(),
                retention_rate=retention_rate,
                retention_amount=retention_amount,
                invoice_class=invoice_class,
                series=values["series"] or None,
                notes=values["notes"],
            )
        except (CadrumoError, ValidationError) as error:
            return None, (door_refusal_text(error),)
        return entry, ()

    def _summary(self, entry: LedgerInvoiceEntryV1) -> str:
        lines = [
            ledger_copy(
                "tui.ledger.invoice.summary.identity",
                kind=ledger_copy(_KIND_LOCALE_KEYS[entry.kind]),
                number=entry.invoice_number,
                date=entry.invoice_date.isoformat(),
            ),
            ledger_copy(
                "tui.ledger.invoice.summary.counterparty",
                name=entry.counterparty_name,
                nif=entry.counterparty_nif or "-",
                country=entry.country_code,
            ),
        ]
        if entry.lines:
            lines.extend(invoice_line_row(index, line) for index, line in enumerate(entry.lines, start=1))
        else:
            lines.append(
                ledger_copy(
                    "tui.ledger.invoice.summary.amounts",
                    base="-" if entry.taxable_base is None else format(entry.taxable_base, "f"),
                    rate="-" if entry.iva_rate is None else format(entry.iva_rate, "f"),
                    currency=entry.currency,
                )
            )
        if entry.operation_type is not None or entry.operation_date is not None:
            lines.append(
                ledger_copy(
                    "tui.ledger.invoice.summary.operation",
                    code="-" if entry.operation_type is None else entry.operation_type.value,
                    date="-" if entry.operation_date is None else entry.operation_date.isoformat(),
                )
            )
        if entry.recargo_amount is not None:
            lines.append(
                ledger_copy(
                    "tui.ledger.invoice.summary.recargo",
                    amount=format(entry.recargo_amount, "f"),
                    currency=entry.currency,
                )
            )
        if entry.rectifies_invoice_number is not None:
            lines.append(ledger_copy("tui.ledger.invoice.summary.rectifies", number=entry.rectifies_invoice_number))
        if entry.retention_rate is not None or entry.retention_amount is not None:
            lines.append(
                ledger_copy(
                    "tui.ledger.invoice.summary.retention",
                    rate="-" if entry.retention_rate is None else format(entry.retention_rate, "f"),
                    amount="-" if entry.retention_amount is None else format(entry.retention_amount, "f"),
                )
            )
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route each control through the flow's guarded transitions."""
        notice = self.query_one("#ledger-refusal", Static)
        match event.button.id:
            case "ledger-invoice-line-add" if self.flow_state is LedgerFlowState.EDITING:
                notice.update("\n".join(self._add_line()))
            case "ledger-invoice-line-remove" if self.flow_state is LedgerFlowState.EDITING and self.lines:
                self.lines.pop()
                self._render_lines()
            case "ledger-invoice-review" if self.flow_state is LedgerFlowState.EDITING:
                entry, problems = self._read_entry()
                if entry is None:
                    notice.update("\n".join(problems))
                    return
                notice.update("")
                self.entry = entry
                self.query_one("#ledger-invoice-summary", Static).update(self._summary(entry))
                self._lock_form()
                self._transition(LedgerFlowState.CONFIRMING)
                self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.invoice.confirming"))
                confirm = self.query_one("#ledger-invoice-confirm", Button)
                confirm.disabled = False
                confirm.focus()
            case "ledger-invoice-cancel" if self.flow_state in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
                self._cancel_flow()
            case "ledger-invoice-confirm" if self.flow_state is LedgerFlowState.CONFIRMING:
                self._transition(LedgerFlowState.SUBMITTING)
                event.button.disabled = True
                self.query_one("#ledger-invoice-cancel", Button).disabled = True
                self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.invoice.progress"))
                self.run_worker(self._submit(), exclusive=True)
            case "ledger-invoice-again" if self.flow_state in {
                LedgerFlowState.SUCCEEDED,
                LedgerFlowState.FAILED,
                LedgerFlowState.CANCELLED,
            }:
                self.refresh_after_write(lambda: self.post_message(LedgerInvoiceEntryRequested()))
            case _:
                return

    def _lock_form(self) -> None:
        for widget in self.query(Input):
            widget.disabled = True
        for widget in self.query(Select):
            widget.disabled = True
        for button_id in ("#ledger-invoice-review", "#ledger-invoice-line-add", "#ledger-invoice-line-remove"):
            self.query_one(button_id, Button).disabled = True

    async def _submit(self) -> None:
        """Record exactly the reviewed entry."""
        status = self.query_one("#ledger-flow-status", Static)
        entry = self.entry
        if entry is None:  # pragma: no cover - guarded before worker creation
            raise InternalInvariantError("reviewed invoice disappeared before submission")
        try:
            result = await self.controller.add_invoice(entry)
        except (CadrumoError, ValidationError) as error:
            self._transition(LedgerFlowState.FAILED)
            status.update(ledger_copy("tui.ledger.invoice.failure"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self._transition(LedgerFlowState.SUCCEEDED)
            recorded = ledger_copy(
                "tui.ledger.invoice.success",
                number=result.invoice_number,
                base=format(result.base_total, "f"),
                iva=format(result.iva_total, "f"),
                total=format(result.grand_total, "f"),
                currency=result.currency,
            )
            if result.euro_value_pending:
                recorded = "\n".join(
                    (recorded, ledger_copy("tui.ledger.invoice.euro_rate_unavailable", currency=result.currency))
                )
            status.update(recorded)
        again = self.query_one("#ledger-invoice-again", Button)
        again.add_class("-open")
        again.focus()

    @override
    def _cancel_flow(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self.entry = None
        self._transition(LedgerFlowState.CANCELLED)
        self._lock_form()
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.invoice.cancelled"))
        self.query_one("#ledger-invoice-confirm", Button).disabled = True
        self.query_one("#ledger-invoice-cancel", Button).disabled = True
        again = self.query_one("#ledger-invoice-again", Button)
        again.add_class("-open")
        again.focus()


__all__ = ["LedgerInvoiceEntryScreen", "invoice_line_row"]
