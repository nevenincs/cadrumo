"""Invoice entry form: type one invoice, review it, and record it through the catalogue writer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, Input, Select, Static

from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....domain.iva.classification import InvoiceKind
from .controller import LedgerInvoiceEntryRequested, LedgerWorkspaceController, ledger_copy
from .models import LedgerFlowState, LedgerInvoiceClassChoice, LedgerInvoiceEntryV1
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

#: Text fields in form order, each with whether the writer requires it.
_TEXT_FIELDS: Final[tuple[tuple[str, bool], ...]] = (
    ("counterparty_name", True),
    ("counterparty_nif", False),
    ("country_code", True),
    ("invoice_number", True),
    ("invoice_date", True),
    ("taxable_base", True),
    ("iva_rate", False),
    ("currency", True),
    ("retention_rate", False),
    ("retention_amount", False),
    ("series", False),
    ("notes", False),
)
_DEFAULTS: Final[dict[str, str]] = {"country_code": "ES", "currency": "EUR"}


_FIELD_LOCALE_KEYS: Final[dict[str, str]] = {
    "kind": "tui.ledger.invoice.field.kind",
    "counterparty_name": "tui.ledger.invoice.field.counterparty_name",
    "counterparty_nif": "tui.ledger.invoice.field.counterparty_nif",
    "country_code": "tui.ledger.invoice.field.country_code",
    "invoice_number": "tui.ledger.invoice.field.invoice_number",
    "invoice_date": "tui.ledger.invoice.field.invoice_date",
    "taxable_base": "tui.ledger.invoice.field.taxable_base",
    "iva_rate": "tui.ledger.invoice.field.iva_rate",
    "currency": "tui.ledger.invoice.field.currency",
    "retention_rate": "tui.ledger.invoice.field.retention_rate",
    "retention_amount": "tui.ledger.invoice.field.retention_amount",
    "invoice_class": "tui.ledger.invoice.field.invoice_class",
    "series": "tui.ledger.invoice.field.series",
    "notes": "tui.ledger.invoice.field.notes",
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
        """Start with an empty form."""
        super().__init__(controller, id="ledger-invoice-entry-screen")
        self.entry: LedgerInvoiceEntryV1 | None = None

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
            yield Static(_field_label("invoice_class"), markup=False)
            yield Select[str](
                tuple((ledger_copy(_CLASS_LOCALE_KEYS[choice]), choice.value) for choice in LedgerInvoiceClassChoice),
                value=LedgerInvoiceClassChoice.ORDINARIA.value,
                allow_blank=False,
                id="ledger-invoice-class",
            )
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

    def _read_entry(self) -> tuple[LedgerInvoiceEntryV1 | None, tuple[str, ...]]:
        """Parse the form, naming every field that cannot be read rather than only the first."""
        problems: list[str] = []
        values = {name: self._text(name) for name, _required in _TEXT_FIELDS}
        for name, required in _TEXT_FIELDS:
            if required and not values[name]:
                problems.append(ledger_copy("tui.ledger.invoice.problem.required", field=_field_label(name)))

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

        issued: date | None = None
        if values["invoice_date"]:
            try:
                issued = date.fromisoformat(values["invoice_date"])
            except ValueError:
                problems.append(ledger_copy("tui.ledger.invoice.problem.date", field=_field_label("invoice_date")))
        base = amount("taxable_base")
        iva_rate = amount("iva_rate")
        retention_rate = amount("retention_rate")
        retention_amount = amount("retention_amount")
        if problems or issued is None or base is None:
            return None, tuple(problems)
        kind = InvoiceKind(str(cast("Select[str]", self.query_one("#ledger-invoice-kind", Select)).value))
        invoice_class = LedgerInvoiceClassChoice(
            str(cast("Select[str]", self.query_one("#ledger-invoice-class", Select)).value)
        )
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
                currency=values["currency"].upper(),
                retention_rate=retention_rate,
                retention_amount=retention_amount,
                invoice_class=invoice_class,
                series=values["series"] or None,
                notes=values["notes"],
            )
        except ValidationError as error:
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
            ledger_copy(
                "tui.ledger.invoice.summary.amounts",
                base=format(entry.taxable_base, "f"),
                rate="-" if entry.iva_rate is None else format(entry.iva_rate, "f"),
                currency=entry.currency,
            ),
        ]
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
                self.refresh_after_write()
                self.post_message(LedgerInvoiceEntryRequested())
            case _:
                return

    def _lock_form(self) -> None:
        for widget in self.query(Input):
            widget.disabled = True
        for widget in self.query(Select):
            widget.disabled = True
        self.query_one("#ledger-invoice-review", Button).disabled = True

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
            status.update(
                ledger_copy(
                    "tui.ledger.invoice.success",
                    number=result.invoice_number,
                    base=format(result.base_total, "f"),
                    iva=format(result.iva_total, "f"),
                    total=format(result.grand_total, "f"),
                    currency=result.currency,
                )
            )
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


__all__ = ["LedgerInvoiceEntryScreen"]
