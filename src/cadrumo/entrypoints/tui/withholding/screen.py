"""A narrow Textual surface for the established withholding evidence door.

The host supplies invoice and ledger-payment lookups over its encrypted
catalogues and the already composed :class:`TuiWithholdingDoor`.  This screen
deliberately never reads a repository or calculates a recognition date: it only
collects declared evidence and hands it to the common application command.
Work income is anchored to the ledger transaction that paid it; professional
and urban-rent income to the invoice they settle.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, ClassVar, cast, override

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static

from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ....application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from ....application.aggregation.withholding_observation_service import (
    WithholdingMutationMode,
    WithholdingObservationMutationError,
    WithholdingWindowScope,
)
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....core.aggregation import RetencionClave, RetencionScheme
from ....core.period import Period
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ..components.theme import BASE_CSS, tokenised
from .door import (
    TuiInvoiceWithholdingCaptureRequest,
    TuiLedgerPaymentWithholdingCaptureRequest,
    TuiWithholdingCaptureOutcome,
    TuiWithholdingDoor,
)

if TYPE_CHECKING:
    from ....domain.invoices.models import Invoice
    from ....domain.transactions.models import TransactionCatalogue


type InvoiceLookup = Callable[[str], tuple["Invoice", str] | None]
type LedgerPaymentLookup = Callable[[str], tuple["TransactionCatalogue", str | None]]
"""Addressed ledger read for one transaction id and its consistent catalogue revision.

The revision is ``None`` when the host could not state one stable revision
across the read; an id the ledger does not hold yields an empty catalogue.
"""


class WithholdingEvidenceScreen(Screen[None]):
    """Capture or inspect an invoice or payroll allocation through the shared TUI door."""

    CSS: ClassVar[str] = BASE_CSS + tokenised(
        """
        WithholdingEvidenceScreen { overflow-y: auto; }
        #withholding-page { overflow-y: auto; height: 1fr; padding: 1 2; }
        #withholding-status, #withholding-inspection { height: auto; margin-top: 1; }
        .withholding-field { width: 100%; max-width: $cadrumo-control-max-width; }
        .withholding-label { margin-top: 1; }
        """
    )

    def __init__(
        self,
        *,
        door: TuiWithholdingDoor,
        invoice_lookup: InvoiceLookup,
        ledger_payment_lookup: LedgerPaymentLookup,
        filing_year: int,
    ) -> None:
        """Bind the screen to host-owned catalogue reads and shared mutations."""
        super().__init__(id="withholding-evidence-screen")
        self._door = door
        self._invoice_lookup = invoice_lookup
        self._ledger_payment_lookup = ledger_payment_lookup
        self._filing_year = filing_year
        self._baseline = None
        self._inspected_scope: WithholdingWindowScope | None = None

    @override
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="withholding-page"):
            yield from self._form()

    def _form(self) -> ComposeResult:
        """Keep the deliberately complete evidence form reachable on small terminals."""
        yield Static("Withholding evidence", classes="cadrumo-banner")
        yield Static("Invoice id or exact number (professional and rent income)", classes="withholding-label")
        yield Input(id="withholding-invoice-id", classes="withholding-field")
        yield Static("Paying ledger transaction id (work income)", classes="withholding-label")
        yield Input(id="withholding-transaction-id", classes="withholding-field")
        yield Static("Income family", classes="withholding-label")
        yield Select[str](
            (
                ("Professional (111/190)", "professional"),
                ("Work income / payroll (111/190)", "work"),
                ("Urban rent (115/180)", "urban_rent"),
            ),
            value="professional",
            allow_blank=False,
            id="withholding-income-kind",
            classes="withholding-field",
        )
        yield Static("Scheme", classes="withholding-label")
        # Payer facts are never prefilled: a value the operator did not enter
        # would be stored as if they had declared it.
        yield Input(id="withholding-scheme", classes="withholding-field")
        yield Static("Recipient tax status / regime", classes="withholding-label")
        yield Select[str](
            (("Resident", "resident"),),
            value="resident",
            allow_blank=False,
            id="withholding-tax-status",
            classes="withholding-field",
        )
        yield Select[str](
            (("IRPF", "irpf"),),
            value="irpf",
            allow_blank=False,
            id="withholding-tax-regime",
            classes="withholding-field",
        )
        for label, field, default in (
            ("Payment event id", "payment-id", ""),
            ("Payment date (YYYY-MM-DD; work income: the ledger booking date)", "payment-date", ""),
            ("Allocation id", "allocation-id", ""),
            ("Allocated base (work income: declared gross remuneration)", "allocated-base", ""),
            ("Allocated withholding (work income: declared IRPF withheld)", "allocated-withholding", ""),
            ("Allocated settlement (work income: declared net paid)", "allocated-settlement", ""),
            ("Idempotency key", "idempotency-key", ""),
            ("Work income perceptor NIF (supplied evidence)", "perceptor-nif", ""),
            ("Work income perceptor legal name (supplied evidence)", "perceptor-name", ""),
            ("Modelo 190 clave", "clave", ""),
            ("Modelo 190 subclave", "subclave", ""),
            ("Modelo 190 province", "province", ""),
            ("Modelo 190 territorial deduction clave (0, 1 or 2; supplied evidence)", "territorial-deduction", ""),
            ("Annual withholding percentage (supplied evidence)", "annual-percentage", ""),
            (
                "Modelo 190 deductible expenses (work income: employee Social Security; supplied evidence)",
                "deductible-expenses",
                "",
            ),
            ("Modelo 180 property key", "property-key", ""),
            ("Modelo 180 situation", "property-situation", ""),
            ("Modelo 180 cadastral reference", "cadastral-reference", ""),
            ("Modelo 180 municipality code", "municipality-code", ""),
            ("Modelo 180 municipality", "municipality", ""),
            ("Modelo 180 postal code", "postal-code", ""),
            ("Modelo 180 street name", "street-name", ""),
            ("Modelo 180 modality", "property-modality", ""),
            ("Clear/replace reason", "reason", ""),
            ("Inspection modelo", "inspect-modelo", "111"),
            ("Inspection period", "inspect-period", "2025-2T"),
        ):
            yield Static(label, classes="withholding-label")
            yield Input(value=default, id=f"withholding-{field}", classes="withholding-field")
        yield Static("Mutation", classes="withholding-label")
        yield Select[str](
            (("Append", "append"), ("Replace inspected scope", "replace"), ("Clear inspected scope", "clear")),
            value="append",
            allow_blank=False,
            id="withholding-mode",
            classes="withholding-field",
        )
        yield Button("Inspect current evidence", id="withholding-inspect")
        yield Button("Capture evidence", id="withholding-capture", variant="primary")
        yield Static("", id="withholding-inspection", markup=False)
        yield Static("", id="withholding-status", markup=False)

    def _text(self, field: str) -> str:
        return self.query_one(f"#withholding-{field}", Input).value.strip()

    def _select(self, field: str) -> str:
        selected = cast("Select[str]", self.query_one(f"#withholding-{field}", Select)).value
        if not isinstance(selected, str):
            raise ValueError("missing selection")
        return selected

    def _set_status(self, value: str) -> None:
        self.query_one("#withholding-status", Static).update(value)

    def _inspect(self) -> None:
        try:
            year_text, period_code = self._text("inspect-period").split("-", maxsplit=1)
            scope = WithholdingWindowScope(
                modelo=self._text("inspect-modelo"),
                period=Period.from_year_and_code(int(year_text), period_code),
            )
            state = self._door.read_window(scope)
        except (WithholdingObservationMutationError, ValueError):
            self._baseline = None
            self._inspected_scope = None
            self._set_status("refused: invalid_inspection_scope")
            return
        self._baseline = state.baseline
        self._inspected_scope = scope
        self.query_one("#withholding-inspection", Static).update(
            f"{scope.modelo} {scope.period.registry_token}: {len(state.entries)} active projections; "
            f"baseline {state.baseline.generation_id[:12]}"
        )
        self._set_status("inspection ready")

    def _mode(self) -> WithholdingMutationMode:
        """Refuse a destructive mode unless the operator inspected its baseline first."""
        mode = WithholdingMutationMode(self._select("mode"))
        if mode is not WithholdingMutationMode.APPEND and self._baseline is None:
            raise ValueError("baseline_required")
        return mode

    def _request(self, kind: WithholdingIncomeKind) -> TuiInvoiceWithholdingCaptureRequest:
        invoice_id = self._text("invoice-id")
        resolved = self._invoice_lookup(invoice_id)
        if resolved is None:
            raise ValueError("unknown_invoice")
        invoice, catalogue_revision_id = resolved
        mode = self._mode()
        annual_detail = (
            self._annual_detail(
                source_id=invoice.invoice_id,
                perceptor_tax_id=invoice.counterparty_tax_id or "",
                perceptor_legal_name=invoice.counterparty_name,
            )
            if kind is WithholdingIncomeKind.PROFESSIONAL
            else None
        )
        property_detail = self._property_detail() if kind is WithholdingIncomeKind.URBAN_RENT else None
        payment_date = date.fromisoformat(self._text("payment-date"))
        evidence = InvoiceWithholdingEvidenceRequest(
            invoice_id=invoice.invoice_id,
            income_kind=kind,
            scheme=RetencionScheme(self._text("scheme")),
            recipient_tax_status=WithholdingRecipientTaxStatus(self._select("tax-status")),
            recipient_tax_regime=WithholdingRecipientTaxRegime(self._select("tax-regime")),
            payment_event_id=self._text("payment-id"),
            payment_occurred_on=payment_date,
            allocation_id=self._text("allocation-id"),
            allocated_base=Decimal(self._text("allocated-base")),
            allocated_withholding=Decimal(self._text("allocated-withholding")),
            allocated_settlement=Decimal(self._text("allocated-settlement")),
            idempotency_key=self._text("idempotency-key"),
            mode=mode,
            baseline=self._baseline if mode is not WithholdingMutationMode.APPEND else None,
            reason=self._text("reason") or None,
            modelo_180_property=property_detail,
            modelo_190_detail=annual_detail,
        )
        return TuiInvoiceWithholdingCaptureRequest(
            invoice=invoice,
            catalogue_revision_id=catalogue_revision_id,
            evidence=evidence,
            filing_year=self._filing_year,
        )

    def _ledger_payment_request(self) -> TuiLedgerPaymentWithholdingCaptureRequest:
        """Collect declared payroll terms; the ledger read supplies date, amount and currency.

        The perceptor is a fact of the employment relationship that no bank
        movement states, so it is required input rather than a default.
        """
        mode = self._mode()
        transaction_id = self._text("transaction-id")
        perceptor_legal_name = self._text("perceptor-name")
        if not perceptor_legal_name:
            raise ValueError("perceptor_legal_name_required")
        evidence = LedgerPaymentWithholdingEvidenceRequest(
            transaction_id=transaction_id,
            income_kind=WithholdingIncomeKind.WORK,
            scheme=RetencionScheme(self._text("scheme")),
            recipient_tax_status=WithholdingRecipientTaxStatus(self._select("tax-status")),
            recipient_tax_regime=WithholdingRecipientTaxRegime(self._select("tax-regime")),
            payment_event_id=self._text("payment-id"),
            allocation_id=self._text("allocation-id"),
            gross_base=Decimal(self._text("allocated-base")),
            withholding_amount=Decimal(self._text("allocated-withholding")),
            net_settlement=Decimal(self._text("allocated-settlement")),
            idempotency_key=self._text("idempotency-key"),
            mode=mode,
            baseline=self._baseline if mode is not WithholdingMutationMode.APPEND else None,
            reason=self._text("reason") or None,
            modelo_190_detail=self._annual_detail(
                source_id=transaction_id,
                perceptor_tax_id=self._text("perceptor-nif"),
                perceptor_legal_name=perceptor_legal_name,
            ),
        )
        transactions, catalogue_revision_id = self._ledger_payment_lookup(evidence.transaction_id)
        return TuiLedgerPaymentWithholdingCaptureRequest(
            transactions=transactions,
            catalogue_revision_id=catalogue_revision_id,
            evidence=evidence,
            filing_year=self._filing_year,
        )

    def _annual_detail(
        self,
        *,
        source_id: str,
        perceptor_tax_id: str,
        perceptor_legal_name: str,
    ) -> WithholdingObservation:
        payment_date = date.fromisoformat(self._text("payment-date"))
        return WithholdingObservation(
            source_id=source_id,
            source_allocation_id=self._text("allocation-id"),
            perceptor_tax_id=perceptor_tax_id,
            perceptor_legal_name=perceptor_legal_name,
            transaction_date=payment_date,
            clave=RetencionClave.from_registry(self._text("clave")),
            subclave=self._text("subclave"),
            province_code=self._text("province") or None,
            territorial_deduction_clave=int(self._text("territorial-deduction")),
            percibido_dinerario=Decimal(self._text("allocated-base")),
            retencion_practicada=Decimal(self._text("allocated-withholding")),
            incapacity_cash_perception=Decimal("0"),
            incapacity_cash_withholding=Decimal("0"),
            incapacity_kind_value=Decimal("0"),
            incapacity_kind_ingreso_a_cuenta=Decimal("0"),
            incapacity_kind_repercutido=Decimal("0"),
            foral_retention_estatal=Decimal("0"),
            foral_retention_navarra=Decimal("0"),
            foral_retention_araba=Decimal("0"),
            foral_retention_gipuzkoa=Decimal("0"),
            foral_retention_bizkaia=Decimal("0"),
            base_retenciones=Decimal(self._text("allocated-base")),
            porcentaje_retencion=Decimal(self._text("annual-percentage")),
            gastos_deducibles=self._deductible_expenses(),
        )

    def _deductible_expenses(self) -> Decimal:
        """Return the declared Modelo 190 deductible expenses for this allocation.

        Work income must declare them (the employee's Social Security share,
        possibly zero); a blank field is not a zero. Professional income has
        none, so a value entered there is refused rather than stored.
        """
        entered = self._text("deductible-expenses")
        if self._select("income-kind") == "work":
            return Decimal(entered)
        if entered:
            raise ValueError("deductible expenses apply to work income only")
        return Decimal("0")

    def _property_detail(self) -> Modelo180PropertyEvidence:
        situation = self._text("property-situation")
        if situation not in {"1", "2", "3", "4"}:
            raise ValueError("invalid property situation")
        modality = self._text("property-modality")
        if modality not in {"1", "2"}:
            raise ValueError("invalid property modality")
        return Modelo180PropertyEvidence(
            property_key=self._text("property-key"),
            situation=situation,
            cadastral_reference=self._text("cadastral-reference") or None,
            address=Modelo180StructuredAddress(
                province_code=self._text("province"),
                municipality_code=self._text("municipality-code"),
                municipality=self._text("municipality"),
                locality=self._text("municipality"),
                postal_code=self._text("postal-code"),
                street_type="CL",
                street_name=self._text("street-name"),
                number_type="NUM",
                house_number="1",
            ),
            recipient_province_code=self._text("province"),
            modality=modality,
            accrual_year=self._filing_year,
            withholding_percentage=Decimal(self._text("annual-percentage")),
        )

    def _submit(self) -> TuiWithholdingCaptureOutcome:
        """Route the selected income family to the evidence that proves it."""
        kind = WithholdingIncomeKind(self._select("income-kind"))
        if kind is WithholdingIncomeKind.WORK:
            return self._door.capture_ledger_payment(self._ledger_payment_request())
        return self._door.capture(self._request(kind))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Keep every mutation explicitly initiated by the operator."""
        if event.button.id == "withholding-inspect":
            self._inspect()
            return
        if event.button.id != "withholding-capture":
            return
        try:
            outcome = self._submit()
        except (InvalidOperation, ValueError):
            self._set_status("refused: invalid_withholding_evidence")
            return
        if outcome.status == "refused":
            self._set_status(f"refused: {outcome.refusal_code or 'invalid_withholding_evidence'}")
            return
        if outcome.scope is not None:
            self._inspected_scope = outcome.scope
        self._set_status(outcome.status)


__all__ = ["InvoiceLookup", "LedgerPaymentLookup", "WithholdingEvidenceScreen"]
