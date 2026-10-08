"""Invoice entry form: type one invoice, review it, and record it through the catalogue writer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, Input, Select, Static

from ....core.aggregation import IntracomOperationType
from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.i18n.render import tr
from ....core.parsing.dates import require_iso8601_date_unless_blank
from ....domain.invoices.business_premises import SituacionInmueble, require_situacion_inmueble
from ....domain.invoices.models import InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ..account import AccountSessionExpiredError
from .controller import LedgerInvoiceEntryRequested, LedgerWorkspaceController
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
    ("referencia_catastral", False),
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
    "arrendamiento_local_negocio": "tui.ledger.invoice.field.arrendamiento_local_negocio",
    "situacion_inmueble": "tui.ledger.invoice.field.situacion_inmueble",
    "referencia_catastral": "tui.ledger.invoice.field.referencia_catastral",
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
#: The business-premises lease choice, whose "yes" states the lessor's fact of RD 1065/2007 art. 34.1.d.
_LEASE_CHOICES: Final[tuple[tuple[str, bool], ...]] = (
    ("tui.ledger.invoice.lease.no", False),
    ("tui.ledger.invoice.lease.yes", True),
)
#: The record design's SITUACIÓN DEL INMUEBLE codes, each offered with its meaning.
_SITUACION_LOCALE_KEYS: Final[dict[SituacionInmueble, str]] = {
    SituacionInmueble.SPAIN_OTHER_THAN_BASQUE_NAVARRE: "tui.ledger.invoice.situacion.1",
    SituacionInmueble.BASQUE_COUNTRY_OR_NAVARRE: "tui.ledger.invoice.situacion.2",
    SituacionInmueble.SPAIN_WITHOUT_CATASTRAL_REFERENCE: "tui.ledger.invoice.situacion.3",
    SituacionInmueble.ABROAD: "tui.ledger.invoice.situacion.4",
}
_CLASS_LOCALE_KEYS: Final[dict[LedgerInvoiceClassChoice, str]] = {
    LedgerInvoiceClassChoice.ORDINARIA: "tui.ledger.invoice.class.ordinaria",
    LedgerInvoiceClassChoice.SIMPLIFICADA: "tui.ledger.invoice.class.simplificada",
    LedgerInvoiceClassChoice.RECTIFICATIVA: "tui.ledger.invoice.class.rectificativa",
}


def _field_label(name: str) -> str:
    return tr(_FIELD_LOCALE_KEYS[name])


def _line_field_label(name: str) -> str:
    return tr(_LINE_FIELD_LOCALE_KEYS[name])


def _line_input_id(name: str) -> str:
    return f"ledger-invoice-line-{name.replace('_', '-')}"


def _line_required_problems(values: dict[str, str]) -> list[str]:
    return [
        tr("tui.ledger.invoice.problem.required", field=_line_field_label(name))
        for name, required in _LINE_FIELDS
        if required and not values[name]
    ]


def _line_amounts(values: dict[str, str]) -> tuple[dict[str, Decimal], list[str]]:
    numbers: dict[str, Decimal] = {}
    problems: list[str] = []
    for name in ("quantity", "unit_price", "subtotal", "iva_amount"):
        if not values[name]:
            continue
        # Unit price and quantity may carry sub-cent precision.
        parsed = try_parse_canonical_decimal(values[name])
        if parsed is None:
            problems.append(tr("tui.ledger.invoice.problem.amount", field=_line_field_label(name)))
        else:
            numbers[name] = parsed
    return numbers, problems


def _parsed_invoice_line(values: dict[str, str]) -> tuple[LedgerInvoiceLineEntryV1 | None, tuple[str, ...]]:
    problems = _line_required_problems(values)
    numbers, amount_problems = _line_amounts(values)
    problems.extend(amount_problems)
    if problems:
        return None, tuple(problems)
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
        return None, (door_refusal_text(error),)
    return line, ()


def _required_entry_problems(values: dict[str, str], lines: list[LedgerInvoiceLineEntryV1]) -> list[str]:
    problems = [
        tr("tui.ledger.invoice.problem.required", field=_field_label(name))
        for name, required in _TEXT_FIELDS
        if required and not values[name]
    ]
    if lines and (values["taxable_base"] or values["iva_rate"]):
        problems.append(tr("tui.ledger.invoice.problem.lines_and_base"))
    if not lines and not values["taxable_base"]:
        problems.append(tr("tui.ledger.invoice.problem.base_or_lines"))
    return problems


def _entry_day(values: dict[str, str], name: str) -> tuple[date | None, str | None]:
    try:
        return require_iso8601_date_unless_blank(values[name]), None
    except ValueError:
        return None, tr("tui.ledger.invoice.problem.date", field=_field_label(name))


def _entry_dates(values: dict[str, str]) -> tuple[date | None, date | None, list[str]]:
    issued, issued_problem = _entry_day(values, "invoice_date")
    operation_date, operation_problem = _entry_day(values, "operation_date")
    problems = [problem for problem in (issued_problem, operation_problem) if problem is not None]
    return issued, operation_date, problems


def _entry_amount(values: dict[str, str], name: str) -> tuple[Decimal | None, str | None]:
    raw = values[name]
    if not raw:
        return None, None
    parsed = try_parse_canonical_decimal(raw, max_fraction_digits=2)
    if parsed is None:
        return None, tr("tui.ledger.invoice.problem.amount", field=_field_label(name))
    return parsed, None


def _entry_amounts(values: dict[str, str]) -> tuple[dict[str, Decimal | None], list[str]]:
    parsed: dict[str, Decimal | None] = {}
    problems: list[str] = []
    for name in ("taxable_base", "iva_rate", "retention_rate", "retention_amount", "recargo_amount"):
        parsed[name], problem = _entry_amount(values, name)
        if problem is not None:
            problems.append(problem)
    return parsed, problems


def _situacion_choice(value: object) -> SituacionInmueble | None:
    return require_situacion_inmueble(value) if isinstance(value, str) else None


def _build_invoice_entry(
    values: dict[str, str],
    lines: list[LedgerInvoiceLineEntryV1],
    issued: date,
    operation_date: date | None,
    amounts: dict[str, Decimal | None],
    kind: InvoiceKind,
    invoice_class: LedgerInvoiceClassChoice,
    operation_type_value: object,
    lease: bool,
    situacion_value: object,
) -> LedgerInvoiceEntryV1:
    return LedgerInvoiceEntryV1(
        kind=kind,
        counterparty_name=values["counterparty_name"],
        counterparty_nif=values["counterparty_nif"] or None,
        country_code=values["country_code"].upper(),
        invoice_number=values["invoice_number"],
        invoice_date=issued,
        taxable_base=amounts["taxable_base"],
        iva_rate=amounts["iva_rate"],
        lines=tuple(lines),
        operation_type=IntracomOperationType(operation_type_value) if isinstance(operation_type_value, str) else None,
        operation_date=operation_date,
        recargo_amount=amounts["recargo_amount"],
        rectifies_invoice_number=values["rectifies_invoice_number"] or None,
        iva_category=IvaCategory(values["iva_category"]) if values["iva_category"] else None,
        currency=values["currency"].upper(),
        retention_rate=amounts["retention_rate"],
        retention_amount=amounts["retention_amount"],
        invoice_class=invoice_class,
        series=values["series"] or None,
        arrendamiento_local_negocio=lease,
        situacion_inmueble=_situacion_choice(situacion_value),
        referencia_catastral=values["referencia_catastral"] or None,
        notes=values["notes"],
    )


def invoice_line_row(index: int, line: InvoiceLine | LedgerInvoiceLineEntryV1) -> str:
    """Render one invoice line as its numbered row, for entry review and the detail view alike."""
    return tr(
        "tui.ledger.invoice.line.row",
        index=str(index),
        description=line.description,
        quantity=format(line.quantity, "f"),
        unit_price=format(line.unit_price, "f"),
        subtotal=format(line.subtotal, "f"),
        rate=str(line.iva_rate),
        amount=format(line.iva_amount, "f"),
    )


def _operation_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.operation_type is not None or entry.operation_date is not None:
        return tr(
            "tui.ledger.invoice.summary.operation",
            code="-" if entry.operation_type is None else entry.operation_type.value,
            date="-" if entry.operation_date is None else entry.operation_date.isoformat(),
        )
    return None


def _recargo_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.recargo_amount is not None:
        return tr(
            "tui.ledger.invoice.summary.recargo",
            amount=format(entry.recargo_amount, "f"),
            currency=entry.currency,
        )
    return None


def _rectifies_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.rectifies_invoice_number is not None:
        return tr("tui.ledger.invoice.summary.rectifies", number=entry.rectifies_invoice_number)
    return None


def _retention_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.retention_rate is not None or entry.retention_amount is not None:
        return tr(
            "tui.ledger.invoice.summary.retention",
            rate="-" if entry.retention_rate is None else format(entry.retention_rate, "f"),
            amount="-" if entry.retention_amount is None else format(entry.retention_amount, "f"),
        )
    return None


def _lease_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.arrendamiento_local_negocio:
        return tr(
            "tui.ledger.invoice.summary.lease",
            situacion=entry.situacion_inmueble or "-",
            referencia=entry.referencia_catastral or "-",
        )
    return None


def _supplemental_summary_lines(entry: LedgerInvoiceEntryV1) -> list[str]:
    lines: list[str] = []
    for render_line in (
        _operation_summary_line,
        _recargo_summary_line,
        _rectifies_summary_line,
        _retention_summary_line,
        _lease_summary_line,
    ):
        line = render_line(entry)
        if line is not None:
            lines.append(line)
    return lines


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
        yield Static(tr("tui.ledger.invoice.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(tr("tui.ledger.invoice.prompt"), markup=False)
            yield Static(_field_label("kind"), markup=False)
            yield Select[str](
                tuple((tr(_KIND_LOCALE_KEYS[kind]), kind.value) for kind in InvoiceKind),
                value=InvoiceKind.RECEIVED.value,
                allow_blank=False,
                id="ledger-invoice-kind",
            )
            for name, required in _TEXT_FIELDS:
                label = _field_label(name)
                yield Static(label if required else tr("tui.ledger.invoice.optional", label=label), markup=False)
                yield Input(value=_DEFAULTS.get(name, ""), id=f"ledger-invoice-{name.replace('_', '-')}")
            yield Static(tr("tui.ledger.invoice.optional", label=_field_label("operation_type")), markup=False)
            yield Select[str](
                tuple((key.value, key.value) for key in IntracomOperationType),
                prompt=tr("tui.ledger.invoice.operation_type_none"),
                allow_blank=True,
                id="ledger-invoice-operation-type",
            )
            yield Static(_field_label("invoice_class"), markup=False)
            yield Select[str](
                tuple((tr(_CLASS_LOCALE_KEYS[choice]), choice.value) for choice in LedgerInvoiceClassChoice),
                value=LedgerInvoiceClassChoice.ORDINARIA.value,
                allow_blank=False,
                id="ledger-invoice-class",
            )
            yield Static(_field_label("arrendamiento_local_negocio"), markup=False)
            yield Select[str](
                tuple((tr(key), str(choice)) for key, choice in _LEASE_CHOICES),
                value=str(False),
                allow_blank=False,
                id="ledger-invoice-lease",
            )
            yield Static(tr("tui.ledger.invoice.optional", label=_field_label("situacion_inmueble")), markup=False)
            yield Select[str](
                tuple((tr(key), code.value) for code, key in _SITUACION_LOCALE_KEYS.items()),
                prompt=tr("tui.ledger.invoice.situacion_none"),
                allow_blank=True,
                id="ledger-invoice-situacion-inmueble",
            )
            yield Static(tr("tui.ledger.invoice.line.heading"), markup=False)
            for name, required in _LINE_FIELDS:
                label = _line_field_label(name)
                yield Static(label if required else tr("tui.ledger.invoice.optional", label=label), markup=False)
                yield Input(id=_line_input_id(name))
            yield Button(tr("tui.ledger.invoice.line.add"), id="ledger-invoice-line-add")
            yield Button(tr("tui.ledger.invoice.line.remove"), id="ledger-invoice-line-remove", disabled=True)
            yield Static(tr("tui.ledger.invoice.line.none"), id="ledger-invoice-lines", markup=False)
            yield Button(tr("tui.ledger.invoice.review"), id="ledger-invoice-review", variant="primary")
            yield Static("", id="ledger-invoice-summary", markup=False)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Button(tr("tui.ledger.invoice.confirm"), id="ledger-invoice-confirm", disabled=True)
            yield Button(tr("tui.ledger.invoice.cancel"), id="ledger-invoice-cancel")
            yield Button(tr("tui.ledger.invoice.again"), id="ledger-invoice-again")
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
            listing.update(tr("tui.ledger.invoice.line.none"))
        else:
            listing.update("\n".join(invoice_line_row(index, line) for index, line in enumerate(self.lines, start=1)))
        self.query_one("#ledger-invoice-line-remove", Button).disabled = not self.lines

    def _add_line(self) -> tuple[str, ...]:
        """Append the typed line with its numbers parsed, or name every field that cannot be read."""
        values = {name: self.query_one(f"#{_line_input_id(name)}", Input).value.strip() for name, _ in _LINE_FIELDS}
        line, problems = _parsed_invoice_line(values)
        if line is None:
            return problems
        self.lines.append(line)
        for name, _required in _LINE_FIELDS:
            self.query_one(f"#{_line_input_id(name)}", Input).value = ""
        self._render_lines()
        return ()

    def _read_entry(self) -> tuple[LedgerInvoiceEntryV1 | None, tuple[str, ...]]:
        """Parse the form, naming every field that cannot be read rather than only the first."""
        values = {name: self._text(name) for name, _required in _TEXT_FIELDS}
        problems = _required_entry_problems(values, self.lines)
        issued, operation_date, date_problems = _entry_dates(values)
        problems.extend(date_problems)
        amounts, amount_problems = _entry_amounts(values)
        problems.extend(amount_problems)
        if problems or issued is None:
            return None, tuple(problems)
        kind = InvoiceKind(str(cast("Select[str]", self.query_one("#ledger-invoice-kind", Select)).value))
        invoice_class = LedgerInvoiceClassChoice(
            str(cast("Select[str]", self.query_one("#ledger-invoice-class", Select)).value)
        )
        operation_type_value = cast("Select[str]", self.query_one("#ledger-invoice-operation-type", Select)).value
        lease = str(cast("Select[str]", self.query_one("#ledger-invoice-lease", Select)).value) == str(True)
        situacion_value = cast("Select[str]", self.query_one("#ledger-invoice-situacion-inmueble", Select)).value
        try:
            entry = _build_invoice_entry(
                values,
                self.lines,
                issued,
                operation_date,
                amounts,
                kind,
                invoice_class,
                operation_type_value,
                lease,
                situacion_value,
            )
        except (CadrumoError, ValidationError) as error:
            return None, (door_refusal_text(error),)
        return entry, ()

    def _summary(self, entry: LedgerInvoiceEntryV1) -> str:
        lines = [
            tr(
                "tui.ledger.invoice.summary.identity",
                kind=tr(_KIND_LOCALE_KEYS[entry.kind]),
                number=entry.invoice_number,
                date=entry.invoice_date.isoformat(),
            ),
            tr(
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
                tr(
                    "tui.ledger.invoice.summary.amounts",
                    base="-" if entry.taxable_base is None else format(entry.taxable_base, "f"),
                    rate="-" if entry.iva_rate is None else format(entry.iva_rate, "f"),
                    currency=entry.currency,
                )
            )
        lines.extend(_supplemental_summary_lines(entry))
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
                self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoice.confirming"))
                confirm = self.query_one("#ledger-invoice-confirm", Button)
                confirm.disabled = False
                confirm.focus()
            case "ledger-invoice-cancel" if self.flow_state in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
                self._cancel_flow()
            case "ledger-invoice-confirm" if self.flow_state is LedgerFlowState.CONFIRMING:
                self._transition(LedgerFlowState.SUBMITTING)
                event.button.disabled = True
                self.query_one("#ledger-invoice-cancel", Button).disabled = True
                self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoice.progress"))
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
        for widget in self.query(Select[str]):
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
        except AccountSessionExpiredError as error:
            self._clear_private_form()
            self._transition(LedgerFlowState.FAILED)
            status.update(tr("tui.ledger.invoice.failure"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        except (CadrumoError, ValidationError) as error:
            self._transition(LedgerFlowState.FAILED)
            status.update(tr("tui.ledger.invoice.failure"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self._transition(LedgerFlowState.SUCCEEDED)
            recorded = tr(
                "tui.ledger.invoice.success",
                number=result.invoice_number,
                base=format(result.base_total, "f"),
                iva=format(result.iva_total, "f"),
                total=format(result.grand_total, "f"),
                currency=result.currency,
            )
            if result.euro_value_pending:
                recorded = "\n".join(
                    (recorded, tr("tui.ledger.invoice.euro_rate_unavailable", currency=result.currency))
                )
            status.update(recorded)
        again = self.query_one("#ledger-invoice-again", Button)
        again.add_class("-open")
        again.focus()

    def _clear_private_form(self) -> None:
        """Discard the reviewed invoice and entered values when the session is lost."""
        self.entry = None
        self.lines.clear()
        for field in self.query(Input):
            field.value = ""
        self.query_one("#ledger-invoice-summary", Static).update("")
        self._render_lines()

    @override
    def _cancel_flow(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self.entry = None
        self._transition(LedgerFlowState.CANCELLED)
        self._lock_form()
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoice.cancelled"))
        self.query_one("#ledger-invoice-confirm", Button).disabled = True
        self.query_one("#ledger-invoice-cancel", Button).disabled = True
        again = self.query_one("#ledger-invoice-again", Button)
        again.add_class("-open")
        again.focus()


__all__ = ["LedgerInvoiceEntryScreen", "invoice_line_row"]
