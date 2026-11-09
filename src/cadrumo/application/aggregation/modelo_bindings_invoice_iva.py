"""Invoice-to-ledger IVA screening for modelo binding resolution.

The calculation-facing ledger resolver remains in ._modelo_bindings. This sibling
owns the supporting invoice evidence comparison, category and recargo diagnostics,
and candidate screening required by that resolver.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from ...core.i18n.translatable import Translatable as tr
from ...core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...domain.calculations.registry.iva_deduction_catalogue import resolve_iva_deduction_catalogue
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.invoices.enums import IvaRate, iva_rate_percentage
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.components import registry_category_projection
from ...domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ...domain.iva.flow import (
    derive_flow_for_classification,
    is_deducible_flow,
    is_inversion_sujeto_pasivo_flow,
)
from ...domain.iva.invoice_classification import classify_invoice_line_for_iva, invoice_line_to_iva_observation
from ...domain.iva.prorrata import InputClassification
from ...domain.iva.recargo_equivalencia import recargo_rate_record_for_applied_rate
from ...domain.iva.schema import InvoiceKind, IvaCategory, IvaLedgerObservationRole
from ...domain.transactions.date_partition import OutOfWindowTransactionSummary
from ...domain.transactions.models import Transaction
from .errors import AggregationValidationError
from .invoice_devengo import (
    invoice_devengo_in_period,
    resolve_invoice_devengo,
)
from .iva_ledger import IvaLedgerAggregation
from .iva_ledger_classification import bien_inversion_threshold, validate_intracom_export_counterparty
from .source_mesh import (
    CalculationSourceDiagnostic,
    out_of_window_summary_source_diagnostic,
)
from .source_resolution_operations import source_diagnostics_for


class DeductionAuthority(Protocol):
    """The deduction identity an input-side invoice line is declared under.

    A linked movement's recorded classification, a frozen ledger observation,
    or the received invoice itself as ``invoice_evidence`` all carry it.
    """

    @property
    def deduction_fact_kind(self) -> IvaDeductionFactKind | None:
        """The statutory deduction fact family, when one is recorded."""

    @property
    def deduction_provenance(self) -> IvaDeductionClassificationProvenance | None:
        """Where that deduction family was established."""

    @property
    def investment_asset_id(self) -> str | None:
        """The bienes de inversion register record the deduction belongs to."""

    @property
    def rectifies_ledger_id(self) -> str | None:
        """The ledger row a rectification corrects."""

    @property
    def input_classification(self) -> InputClassification | None:
        """The input-side classification the line is declared under."""

    @property
    def prorrata_sector_id(self) -> str | None:
        """The differentiated prorrata sector the deduction is apportioned to."""


@dataclass(frozen=True, slots=True)
class InvoiceEvidenceDeduction:
    """A received domestic invoice as its own ``domestic_current`` deduction authority.

    Fact 0085 names ``invoice_evidence`` as the authority a domestic deduction
    requires (LIVA art. 97, RIVA art. 99), and LIVA art. 108.Dos.5.º excludes
    from the bienes de inversión every acquisition below the escaso-valor
    threshold, so such a line can only be a current deduction.
    """

    deduction_fact_kind: IvaDeductionFactKind
    deduction_provenance: IvaDeductionClassificationProvenance
    investment_asset_id: None = None
    rectifies_ledger_id: None = None
    input_classification: None = None
    prorrata_sector_id: None = None


def _resolve_invoice_iva_registry_declarations(
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[object, ...]:
    """Resolve the selected M303/M390 bindings and typed IVA mapping facts."""
    modelo_303 = operation.modelo_directory("303")
    modelo_390 = operation.modelo_directory("390")
    fact_ids = (
        "iva-invoice-classification-catalogue",
        "iva-category-component-catalogue",
        "iva-deduction-applicability-catalogue",
    )
    facts = tuple(
        operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id=fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
        for fact_id in fact_ids
    )
    if not all(isinstance(fact, ResolvedMappingFact) for fact in facts):
        raise TypeError("IVA binding and applicability declarations must resolve as mapping facts")
    return (modelo_303, modelo_390, *facts)


def line_contributes_to_the_iva_screen(base_amount: Decimal, iva_amount: Decimal) -> bool:
    """Return whether one invoice line has anything the IVA screen can declare.

    A line contributes when it carries a base OR a cuota. Screening on the cuota
    alone reads as a sensible "nothing to declare" filter and is not one: an
    exempt operation (LIVA art. 20), an intra-community supply (art. 25) and an
    issued-side reverse charge all carry a real base with a cuota that is zero
    BY LAW. The component table says so outright -- both categories are
    ``base=required, cuota=zero_by_law`` -- and Modelo 303 declares those bases
    in its own base-only casillas.

    So a cuota-only filter dropped exactly the lines whose base was the only
    thing they were ever going to contribute, and the declaration understated
    the exempt base by the whole amount with nothing reporting it.

    A line carrying neither is the only shape that genuinely contributes
    nothing, and is the only one this predicate declines.

    **This predicate alone does not make an exempt base reach Modelo 303, and
    was mistakenly reported as doing so.** The loop classifies from the RATE
    SLOT, so an exempt line becomes ``domestic_exempt``/``exempt`` while casilla
    59 selects ``intra_community_supply``/``zero`` and casilla 60 the two export
    categories -- a miss on both axes. No M303 binding selects
    ``domestic_exempt`` or ``domestic_zero``, so such an observation routes
    nowhere rather than into a wrong casilla; the effect is inert, not harmful.

    Keeping the line is a PRECONDITION of the real fix, not the fix. The real
    fix is to construct the observation from the invoice's own
    ``iva_category`` the way the bank-transaction path already does
    (``_iva_ledger.py``: explicit category first, rate-derived domestic
    category only as a fallback, with the intracom/export counterparty gate).
    Two feeds populating one binding source with divergent logic is what
    ``one-aggregation-path-pull-equals-calculate`` exists to prevent.
    """
    return base_amount > Decimal("0") or iva_amount > Decimal("0")


def invoice_line_iva_observation(
    *,
    invoice: Invoice,
    line: InvoiceLine,
    line_index: int,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: DeductionAuthority | None = None,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerObservation | None:
    """Project one invoice line into the observation the screen declares from.

    Both SOPORTADO and INVERSION_SUJETO_PASIVO observations require the exact
    statutory deduction family and its provenance. They arrive as
    ``deduction_authority`` and are copied across unchanged: the agreed
    classification of the movements that pay the invoice, or, for a received
    domestic invoice whose every cuota line is below the art. 108 escaso-valor
    threshold, the invoice itself as ``invoice_evidence``. When neither
    resolves, the enclosing screen withholds the invoice and reports it rather
    than invent a domestic-current default.

    A line carrying a cuota takes the standard-case classification, which
    derives the domestic category from the line's rate slot, unless the invoice
    declares a reverse-charge category. That cuota is the one the recipient
    self-assesses (LIVA art. 84.Uno.2.º): the rate slot alone would read it as
    domestic soportado, a category its linked intra-EU or reverse-charge
    deduction cannot pair with, so the declared category governs it as it
    governs a cuota-less line.

    A line carrying NO cuota cannot be classified that way, and that is the
    defect this branch closes. An intra-community supply, an export and a
    domestic exemption all print the same exempt slot, so the rate alone
    collapses three different declarations into ``domestic_exempt`` -- which
    casilla 59 and 60 do not select, on either category or rate kind. The base
    then reached no casilla at all while the line looked handled.

    The invoice's OWN declared category is what distinguishes them, which is
    exactly how the bank-transaction path resolves the same question: explicit
    category first, rate-derived domestic category only as a fallback. Two feeds
    of one binding source reading it differently is what
    ``one-aggregation-path-pull-equals-calculate`` exists to prevent.

    Returns ``None`` when the line has no cuota and its category is not one a
    base-only casilla selects, or when the counterparty contradicts that
    category. Both cases are withheld rather than mis-routed.

    Args:
        invoice: The invoice the line belongs to, read for its declared
            category and counterparty country.
        line: The line being projected.
        line_index: Position of the line, folded into the observation id.
        devengo_date: The date the observation is declared on.
        recargo_amount: Recargo attributable to this line, already resolved.
        base_amount_eur: ``line.subtotal`` already converted to EUR via
            :meth:`~domain.invoices.models.Invoice.line_amount_eur` -- the caller
            gates on a resolvable EUR amount before this is ever invoked, so
            every downstream construction reads this instead of the line's
            own native-currency field.
        iva_amount_eur: ``line.iva_amount`` already converted to EUR, same
            shape as *base_amount_eur*.
        deduction_authority: Deduction identity resolved for a received
            invoice, or ``None`` for an issued invoice.
        operation: Generation-pinned authority the declared category and the
            counterparty gate are resolved against.

    Returns:
        The observation to declare from, or ``None`` when the line routes
        nowhere.
    """
    ledger_id = f"invoice:{invoice.invoice_id}:{line_index}"
    if iva_amount_eur > Decimal("0") and not _declares_reverse_charge(
        invoice, devengo_date=devengo_date, operation=operation
    ):
        return _standard_invoice_line_iva_observation(
            ledger_id=ledger_id,
            invoice=invoice,
            line=line,
            devengo_date=devengo_date,
            recargo_amount=recargo_amount,
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
            deduction_authority=deduction_authority,
        )
    return _invoice_line_iva_observation_by_declaration(
        ledger_id=ledger_id,
        invoice=invoice,
        line=line,
        devengo_date=devengo_date,
        recargo_amount=recargo_amount,
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
        deduction_authority=deduction_authority,
        operation=operation,
    )


def _declares_reverse_charge(invoice: Invoice, *, devengo_date: date, operation: PinnedAuthorityOperation) -> bool:
    """Whether the invoice declares a category whose cuota the recipient self-assesses."""
    category = _declared_invoice_category(invoice, devengo_date=devengo_date, operation=operation)
    return category is not None and is_inversion_sujeto_pasivo_flow(
        derive_flow_for_classification(category=category, invoice_direction=invoice.kind)
    )


def _invoice_line_iva_observation_by_declaration(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: DeductionAuthority | None,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerObservation | None:
    if invoice.iva_category is None:
        # Without a declared category, the rate slot is the only signal and the
        # generic projection remains the expression boundary.
        return _standard_invoice_line_iva_observation(
            ledger_id=ledger_id,
            invoice=invoice,
            line=line,
            devengo_date=devengo_date,
            recargo_amount=recargo_amount,
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
        )
    category = _declared_invoice_category(invoice, devengo_date=devengo_date, operation=operation)
    if category is None or _invoice_category_counterparty_contradicted(
        invoice,
        category=category,
        devengo_date=devengo_date,
        operation=operation,
    ):
        return None
    return _declared_category_line_observation(
        ledger_id=ledger_id,
        invoice=invoice,
        line=line,
        category=category,
        devengo_date=devengo_date,
        recargo_amount=recargo_amount,
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
        deduction_authority=deduction_authority,
    )


def _declared_category_line_observation(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    category: IvaCategory,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: DeductionAuthority | None,
) -> IvaLedgerObservation | None:
    # The rate slot still supplies the rate kind and the applied rate; only the
    # category, and the flow it implies, come from the invoice's declaration --
    # the order the bank-transaction feed resolves them in.
    classification = classify_invoice_line_for_iva(
        iva_rate=line.iva_rate,
        invoice_kind=invoice.kind,
        on_date=devengo_date,
    )
    if classification.rate_kind is None:
        return None
    flow_direction = derive_flow_for_classification(category=category, invoice_direction=invoice.kind)
    if is_deducible_flow(flow_direction) and deduction_authority is None:
        # An input-side fact needs the linked ledger's deduction authority; the
        # screen withholds the line rather than invent one.
        return None
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=devengo_date,
        category=category,
        rate_kind=classification.rate_kind,
        flow_direction=flow_direction,
        base_amount=base_amount_eur,
        iva_amount=iva_amount_eur,
        recargo_amount=recargo_amount,
        applied_rate=iva_rate_percentage(line.iva_rate, devengo_date),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        deduction_fact_kind=(deduction_authority.deduction_fact_kind if deduction_authority is not None else None),
        deduction_provenance=(deduction_authority.deduction_provenance if deduction_authority is not None else None),
        investment_asset_id=(deduction_authority.investment_asset_id if deduction_authority is not None else None),
        rectifies_ledger_id=(deduction_authority.rectifies_ledger_id if deduction_authority is not None else None),
        input_classification=(deduction_authority.input_classification if deduction_authority is not None else None),
        prorrata_sector_id=(deduction_authority.prorrata_sector_id if deduction_authority is not None else None),
    )


def _declared_invoice_category(
    invoice: Invoice,
    *,
    devengo_date: date,
    operation: PinnedAuthorityOperation,
) -> IvaCategory | None:
    """Return the invoice's declared category when it produces a ledger IVA observation."""
    if invoice.iva_category is None:
        return None
    category = resolve_iva_category_catalogue(effective_date=devengo_date, authority=operation).require(
        invoice.iva_category,
    )
    if category in registry_category_projection(
        "m303_base_out_of_scope",
        effective_date=devengo_date,
        authority=operation,
    ):
        return None
    return category


def _invoice_category_counterparty_contradicted(
    invoice: Invoice,
    *,
    category: IvaCategory,
    devengo_date: date,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether the counterparty contradicts the declared category, under the bank feed's gate."""
    return (
        validate_intracom_export_counterparty(
            transaction_id=f"invoice:{invoice.invoice_id}",
            category=category,
            counterparty_country=invoice.counterparty_country,
            eu_member_state=None,
            identification_state=invoice.counterparty_identification_state,
            effective_date=devengo_date,
            operation=operation,
        )
        is not None
    )


def _standard_invoice_line_iva_observation(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: DeductionAuthority | None = None,
) -> IvaLedgerObservation:
    """Project a rate-classified line, preserving linked ledger deduction facts."""
    return invoice_line_to_iva_observation(
        invoice_id=ledger_id,
        issued_at=devengo_date,
        invoice_kind=invoice.kind,
        iva_rate=line.iva_rate,
        base_amount=base_amount_eur,
        iva_amount=iva_amount_eur,
        recargo_amount=recargo_amount,
        deduction_fact_kind=(deduction_authority.deduction_fact_kind if deduction_authority is not None else None),
        deduction_provenance=(deduction_authority.deduction_provenance if deduction_authority is not None else None),
        investment_asset_id=(deduction_authority.investment_asset_id if deduction_authority is not None else None),
        rectifies_ledger_id=(deduction_authority.rectifies_ledger_id if deduction_authority is not None else None),
        input_classification=(deduction_authority.input_classification if deduction_authority is not None else None),
        prorrata_sector_id=(deduction_authority.prorrata_sector_id if deduction_authority is not None else None),
    )


def reverse_charge_cuota_not_derivable(invoice: Invoice) -> bool:
    """Whether a declared reverse charge carries no rate to self-assess against.

    A reverse charge obliges the RECIPIENT to settle the cuota (LIVA art.
    84.Uno.2 for the domestic case, art. 84.Uno.2.o for an intra-community
    acquisition), and the supplier charges nothing -- so the line legitimately
    carries no cuota. What the record must still carry is the RATE the
    self-assessment applies, and an exempt-slotted line does not.

    Refusing to invent that rate is correct: it decides how much tax is owed, and
    the invoice as recorded does not state it. Refusing SILENTLY is not, which is
    why this predicate exists -- the operator is told the self-assessment could
    not be derived instead of filing a return that is quietly short.

    Scoped to the recipient side. On the supplier side the same category carries
    no self-assessment at all, and its base already reaches its own casilla.

    Args:
        invoice: The invoice being screened.

    Returns:
        ``True`` when a self-assessment is owed and the record cannot support
        computing it.
    """
    if invoice.kind is not InvoiceKind.RECEIVED:
        return False
    if invoice.iva_category is None:
        return False
    if not is_inversion_sujeto_pasivo_flow(
        derive_flow_for_classification(
            category=invoice.iva_category,
            invoice_direction=invoice.kind,
        ),
    ):
        return False
    # A rate-bearing line supplies its own evidence. Whether a slot carries a
    # rate is the registry's answer for the invoice date, not a local tier list.
    return not any(
        (iva_rate_percentage(line.iva_rate, invoice.issued_at) or Decimal("0")) > Decimal("0") for line in invoice.lines
    )


def category_counterparty_mismatch_diagnostics(
    invoices: Sequence[Invoice],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per invoice withheld for a category the counterparty contradicts.

    Withholding the volume is correct: an intra-community supply to a third
    country is not an intra-community supply whatever it claims, and routing it
    on the category alone would declare volume the taxpayer never supplied that
    way. What was missing is the operator being told, so a real operation left a
    declaration with nothing on any surface saying so.

    The remedy names both fields, because either could be the wrong one -- the
    category may be mis-tagged, or the counterparty country may be. The record
    does not know which, and guessing would point the operator at the wrong fix.
    """
    return source_diagnostics_for(
        invoices,
        reason="invoice_category_counterparty_mismatch",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"invoice {invoice.invoice_number!r} declares "
            + (
                invoice.iva_category.value
                if invoice.iva_category is not None and invoice.iva_category
                else "no category"
            )
            + f" but its counterparty country {invoice.counterparty_country!r} cannot bear it, so its base "
            "is NOT declared on this modelo"
        ),
        remedy=lambda _invoice: (
            "Correct either the invoice's IVA category or its counterparty country so the two "
            "agree, then recalculate so the operation reaches its casilla"
        ),
    )


def reverse_charge_underivable_diagnostics(
    invoices: Sequence[Invoice],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per received reverse charge whose cuota cannot be derived.

    The operation IS declarable and the operator is liable for the cuota; what
    is missing is the rate to compute it against. Naming the invoice and the
    missing fact is what turns a silently short return into one the operator can
    correct, and it makes the population countable -- which is what a decision
    about whether an invoice line may carry a rated slot with a zero cuota needs
    in order to be made on evidence.
    """
    return source_diagnostics_for(
        invoices,
        reason="invoice_reverse_charge_cuota_not_derivable",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"invoice {invoice.invoice_number!r} declares "
            + (
                invoice.iva_category.value
                if invoice.iva_category is not None and invoice.iva_category
                else "no category"
            )
            + ", so the recipient owes the self-assessed cuota, but no line states a rated tier to compute "
            "it from -- the cuota is NOT declared on this modelo"
        ),
        remedy=lambda _invoice: (
            "Record the rate the supply bore on the invoice line, keeping its cuota at zero, "
            "then recalculate so the self-assessment reaches its casilla"
        ),
    )


@dataclass(frozen=True, slots=True)
class _RecargoRateDivergence:
    """One invoice whose recorded recargo departs from the published rate.

    Carries both figures and the rate that produced the expected one, because
    an advisory that states only "these disagree" cannot be acted on: the
    operator needs to see which of the two to go and check.
    """

    invoice: Invoice
    recorded: Decimal
    expected: Decimal
    applied_rate: Decimal
    recargo_rate: Decimal
    legal_refs: tuple[str, ...]
    provisions: tuple[str, ...]


def modelo_bindings_invoice_iva_recargo_rate_divergence(
    invoice: Invoice,
    *,
    devengo_date: date,
    operation: PinnedAuthorityOperation,
) -> _RecargoRateDivergence | None:
    """Compare the recorded recargo against the rate art. 161 publishes for that slot.

    The invoice stays authoritative: this reads the recorded figure and never
    replaces it. What it adds is the other half of that posture -- when the
    supplier's figure departs from the published pairing, say so.

    Silent in three cases, each for its own reason and none of them a pass:

    * no recargo recorded at all, which is the ordinary invoice and not this
      screen's business;
    * no line identifiable as the one bearing it, so there is no base to
      compare against and a guess would be worse than silence;
    * the authority containing no pairing for that (applied rate, date).
      An unmodelled window must NOT read as a mismatch -- that would turn a
      gap in our own data into an accusation about the supplier's invoice.
    """
    recargo_inputs = _recargo_comparison_inputs(invoice, devengo_date=devengo_date)
    if recargo_inputs is None:
        return None
    recorded, taxable_base, applied_rate = recargo_inputs
    record = recargo_rate_record_for_applied_rate(applied_rate, devengo_date, operation=operation)
    if record is None:
        return None
    expected = round_to_cents(taxable_base * record.recargo_rate)
    if round_to_cents(recorded) == expected:
        return None
    # The provision the advisory names is the pairing fact's own grounding,
    # so the message cites whatever the registry cites for that window.
    legal_refs = record.legal_refs
    provisions = tuple(
        f"art. {article}"
        for article in (operation.legal_reference(ref).article for ref in legal_refs)
        if article is not None
    )
    return _RecargoRateDivergence(
        invoice=invoice,
        recorded=round_to_cents(recorded),
        expected=expected,
        applied_rate=applied_rate,
        recargo_rate=record.recargo_rate,
        legal_refs=legal_refs,
        provisions=provisions,
    )


def _recargo_comparison_inputs(invoice: Invoice, *, devengo_date: date) -> tuple[Decimal, Decimal, Decimal] | None:
    recorded = invoice.recargo_amount
    if recorded is None or recorded == 0:
        return None
    line_index = _sole_recargo_line_index(invoice)
    if line_index is None:
        return None
    line = invoice.lines[line_index]
    # Pairing uses the same explicit devengo date as the persisted rate slot.
    applied_rate = iva_rate_percentage(line.iva_rate, devengo_date)
    if applied_rate is None:
        return None
    return recorded, line.subtotal, applied_rate


def recargo_rate_mismatch_diagnostics(
    divergences: Sequence[_RecargoRateDivergence],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per invoice whose recargo departs from the published rate.

    Advisory, never a refusal, and the filed figure is unchanged whether or not
    this fires. A legitimate invoice can carry a figure the table does not
    predict, so refusing here would block a correct filing on a correct
    invoice.

    The message names both figures and the provision. Without the provision the
    advisory reads as the application second-guessing the supplier, and an
    operator who cannot see what authority is being cited will learn to dismiss
    it -- which costs more than never having emitted it.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="invoice_recargo_departs_from_published_rate",
            source_kind="ledger_iva_aggregation",
            resolver_id=resolver_id,
            source_ref=f"invoice:{divergence.invoice.invoice_id}",
            message=(
                f"invoice {divergence.invoice.invoice_number!r} records a recargo de equivalencia of "
                f"{divergence.recorded}, while the published schedule "
                f"({', '.join(divergence.provisions) or ', '.join(divergence.legal_refs)}) pairs the "
                f"{divergence.applied_rate} IVA rate "
                f"with a recargo of {divergence.recargo_rate} on that date, which would give "
                f"{divergence.expected}. The recorded figure is the one declared -- this does not change it"
            ),
            remedy=(
                "Check the supplier invoice. Where the printed recargo is right, no action is needed and "
                "the declared figure already matches it; where it was mistyped, correct the transaction "
                "and recalculate"
            ),
            # Asserted by the advisory itself: the comparison is per invoice,
            # so no casilla carries this grounding.
            asserted_legal_refs=divergence.legal_refs,
        )
        for divergence in divergences
    )


@dataclass(frozen=True, slots=True)
class ScreenedInvoiceIva:
    """What the invoice IVA screen found, named rather than positional.

    Several fields are ``tuple[Invoice, ...]`` and one more is a tuple of ids,
    so as a positional return they would be mutually substitutable and a type
    checker could not tell a mis-ordering from correct code. That is not
    hypothetical: the tuple was widened repeatedly as findings landed, the
    annotation fell out of step with the returns on the way, and every widening
    broke unpack sites in unrelated test modules.

    Attributes:
        observations: the IVA observations the screen built.
        invoice_ids: source invoice ids behind those observations.
        compared: invoices whose IVA was compared against the ledger, so the
            caller can disclose how their period placement was arrived at.
        category_counterparty_mismatches: invoices withheld because the declared
            category and the counterparty country contradict each other.
        reverse_charge_underivable: invoices declaring a reverse charge whose
            line carries no rate slot, so no cuota can be derived without
            inventing one.
        deduction_authority_missing: received invoices whose lines contribute
            IVA evidence but whose deduction family resolves neither from the
            paying movements' agreed classification nor from the invoice itself
            under the escaso-valor threshold.
        recargo_rate_divergences: invoices whose recorded recargo departs from
            the rate art. 161 publishes for that slot. Unlike the two above,
            these are NOT withheld -- the figure is declared exactly as
            recorded and the advisory is a cross-check beside it.
        recargo_split_unresolved: issued invoices whose one recorded recargo
            spans several IVA rates and differs from the sum of each rate's
            art. 161 share. No figure says how it divides, so it is declared
            under no rate and the period is blocked until it is corrected.
    """

    observations: tuple[IvaLedgerObservation, ...] = ()
    invoice_ids: tuple[str, ...] = ()
    compared: tuple[Invoice, ...] = ()
    category_counterparty_mismatches: tuple[Invoice, ...] = ()
    reverse_charge_underivable: tuple[Invoice, ...] = ()
    deduction_authority_missing: tuple[Invoice, ...] = ()
    recargo_rate_divergences: tuple[_RecargoRateDivergence, ...] = ()
    recargo_split_unresolved: tuple[Invoice, ...] = ()


@dataclass(frozen=True, slots=True)
class _ScreenedInvoiceIvaResult:
    """One invoice's screen facts, kept separate from the aggregate result."""

    observations: tuple[IvaLedgerObservation, ...]
    reverse_charge_underivable: bool
    recargo_rate_divergence: _RecargoRateDivergence | None
    recargo_split_unresolved: bool
    deduction_authority_missing: bool
    category_counterparty_mismatch: bool


def invoice_screen_of(aggregation: IvaLedgerAggregation) -> ScreenedInvoiceIva:
    """The invoice screen the aggregation projected, or an empty one."""
    screen = aggregation.invoice_screen
    return screen if isinstance(screen, ScreenedInvoiceIva) else ScreenedInvoiceIva()


def invoice_iva_in_period(invoice: Invoice, *, bucket_id: str, period: Period) -> bool:
    """Whether ``invoice`` accrues in ``period`` for this bucket (LIVA art. 75).

    Only a POPULATED, mismatching bucket excludes: an unattributed invoice
    belongs to the store it was loaded from.
    """
    return (invoice.bucket_id is None or invoice.bucket_id == bucket_id) and invoice_devengo_in_period(
        invoice, period=period
    )


def screened_invoice_iva_observations(
    invoices: Iterable[Invoice],
    *,
    bucket_id: str,
    period: Period,
    linked_movements: Mapping[str, Transaction],
    operation: PinnedAuthorityOperation,
) -> ScreenedInvoiceIva:
    """Project the period's invoices into the IVA observations the filing declares.

    The invoice is the IVA document (LIVA art. 75 for accrual, art. 97 and RIVA
    art. 99 for deduction), so every invoice accruing in ``period`` contributes,
    linked to a payment or not. ``linked_movements`` holds the movements the
    invoices name, read only for the deduction classification one may record.
    """
    _resolve_invoice_iva_registry_declarations(effective_date=period.end_date, operation=operation)
    return _collect_screened_invoice_results(
        (invoice for invoice in invoices if invoice_iva_in_period(invoice, bucket_id=bucket_id, period=period)),
        linked_movements=linked_movements,
        operation=operation,
    )


def _collect_screened_invoice_results(
    invoices: Iterable[Invoice],
    *,
    linked_movements: Mapping[str, Transaction],
    operation: PinnedAuthorityOperation,
) -> ScreenedInvoiceIva:
    observations: list[IvaLedgerObservation] = []
    invoice_ids: set[str] = set()
    compared_invoices: list[Invoice] = []
    category_counterparty_mismatches: list[Invoice] = []
    reverse_charge_underivable: list[Invoice] = []
    deduction_authority_missing: list[Invoice] = []
    recargo_rate_divergences: list[_RecargoRateDivergence] = []
    recargo_split_unresolved: list[Invoice] = []
    for invoice in invoices:
        screened = screened_invoice_iva_result(
            invoice,
            linked_movements=tuple(
                movement
                for transaction_id in invoice.linked_transaction_ids
                if (movement := linked_movements.get(transaction_id)) is not None
            ),
            operation=operation,
        )
        if screened.reverse_charge_underivable:
            reverse_charge_underivable.append(invoice)
        if screened.recargo_rate_divergence is not None:
            recargo_rate_divergences.append(screened.recargo_rate_divergence)
        if screened.recargo_split_unresolved:
            recargo_split_unresolved.append(invoice)
        if screened.deduction_authority_missing:
            deduction_authority_missing.append(invoice)
            continue
        if screened.observations:
            observations.extend(screened.observations)
            invoice_ids.add(invoice.invoice_id)
            compared_invoices.append(invoice)
        elif screened.category_counterparty_mismatch:
            category_counterparty_mismatches.append(invoice)
    return ScreenedInvoiceIva(
        observations=tuple(observations),
        invoice_ids=tuple(sorted(invoice_ids)),
        compared=tuple(compared_invoices),
        category_counterparty_mismatches=tuple(category_counterparty_mismatches),
        reverse_charge_underivable=tuple(reverse_charge_underivable),
        deduction_authority_missing=tuple(deduction_authority_missing),
        recargo_rate_divergences=tuple(recargo_rate_divergences),
        recargo_split_unresolved=tuple(recargo_split_unresolved),
    )


def screened_invoice_iva_result(
    invoice: Invoice,
    *,
    linked_movements: Sequence[Transaction],
    operation: PinnedAuthorityOperation,
) -> _ScreenedInvoiceIvaResult:
    """Resolve one already-period-selected invoice into its IVA observations and findings."""
    reverse_charge_underivable = reverse_charge_cuota_not_derivable(invoice)
    # The date the observation carries must be the date it was SELECTED on,
    # or the record would state one quarter while being declared in another.
    devengo = resolve_invoice_devengo(invoice)
    recargo_rate_divergence = modelo_bindings_invoice_iva_recargo_rate_divergence(
        invoice,
        devengo_date=devengo.devengo_date,
        operation=operation,
    )
    deduction_authority = invoice_deduction_authority(
        invoice,
        linked_movements=linked_movements,
        devengo_date=devengo.devengo_date,
        operation=operation,
    )
    deduction_authority_missing = (
        invoice.kind is InvoiceKind.RECEIVED
        and any(line.iva_amount > Decimal("0") for line in invoice.lines)
        and deduction_authority is None
    )
    declared_category = _declared_invoice_category(invoice, devengo_date=devengo.devengo_date, operation=operation)
    category_counterparty_mismatch = declared_category is not None and _invoice_category_counterparty_contradicted(
        invoice,
        category=declared_category,
        devengo_date=devengo.devengo_date,
        operation=operation,
    )
    observations: tuple[IvaLedgerObservation, ...] = ()
    if not deduction_authority_missing and not category_counterparty_mismatch:
        observations = screened_invoice_line_observations(
            invoice,
            devengo_date=devengo.devengo_date,
            deduction_authority=deduction_authority,
            operation=operation,
        )
    return _ScreenedInvoiceIvaResult(
        observations=observations,
        reverse_charge_underivable=reverse_charge_underivable,
        recargo_rate_divergence=recargo_rate_divergence,
        # Only a recargo the filer charged reaches a casilla (the 303 recargo
        # bindings read repercutido rows alone), so only an issued invoice blocks.
        recargo_split_unresolved=(
            invoice.kind is InvoiceKind.ISSUED
            and recargo_eur_by_line_index(invoice, devengo_date=devengo.devengo_date, operation=operation) is None
        ),
        deduction_authority_missing=deduction_authority_missing,
        category_counterparty_mismatch=category_counterparty_mismatch,
    )


def line_eur_amounts_or_refuse(invoice: Invoice, line_index: int, line: InvoiceLine) -> tuple[Decimal, Decimal]:
    """Return one line's (base, cuota) in EUR, refusing when the invoice cannot convert.

    InvoiceLine carries no currency of its own: its amounts are denominated in
    ``invoice.currency``, while ledger values and casillas are EUR. Every
    consumer that weighs a line against a EUR figure converts here, so an
    invoice that resolves no EUR amount (foreign currency, no ``fx_rate``)
    refuses loudly instead of contributing a native figure to a EUR comparison.
    """
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    if base_amount_eur is None or iva_amount_eur is None:
        raise AggregationValidationError(
            tr("aggregation.modelo_bindings.errors.invoice_line_currency_unconverted"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "currency": invoice.currency,
                "line_index": str(line_index),
            },
        )
    return base_amount_eur, iva_amount_eur


def screened_invoice_line_observations(
    invoice: Invoice,
    *,
    devengo_date: date,
    deduction_authority: DeductionAuthority | None,
    operation: PinnedAuthorityOperation,
) -> tuple[IvaLedgerObservation, ...]:
    """Return the line observations eligible for one invoice comparison."""
    # An unplaceable recargo declares on no line; the screen reports the issued
    # invoice that leaves one, so the period cannot reach filing grade without it.
    recargo_by_line = recargo_eur_by_line_index(invoice, devengo_date=devengo_date, operation=operation) or {}
    observations: list[IvaLedgerObservation] = []
    for line_index, line in enumerate(invoice.lines):
        if not line_contributes_to_the_iva_screen(line.subtotal, line.iva_amount):
            continue
        if invoice.kind is InvoiceKind.RECEIVED and line.iva_amount == Decimal("0"):
            continue
        # line.subtotal / line.iva_amount are denominated in invoice.currency
        # (InvoiceLine carries no currency of its own); IvaLedgerObservation's
        # base_amount/iva_amount are EUR-denominated (they feed M303 casillas
        # directly), so this converts through the same fx_rate resolution the
        # invoice-level totals already use, rather than folding the invoice's
        # native fields straight in. A line whose invoice cannot itself resolve
        # a EUR amount (foreign currency, unconverted) REFUSES -- by operator
        # ruling ("aim for explicit red signals... until schema and api
        # converges"), a would-be-silently-dropped declarable line is a hard
        # stop, not an advisory beside a smaller-but-green figure. Fail-closed
        # AND loud, not fail-closed-and-quiet.
        # The base/iva conversion proves this invoice resolves a EUR rate, so a
        # None recargo_amount_eur behind recargo_by_line can only mean no
        # recargo was declared, the genuine-absence zero.
        base_amount_eur, iva_amount_eur = line_eur_amounts_or_refuse(invoice, line_index, line)
        observation = invoice_line_iva_observation(
            invoice=invoice,
            line=line,
            line_index=line_index,
            devengo_date=devengo_date,
            recargo_amount=recargo_by_line.get(line_index, Decimal("0")),
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
            deduction_authority=deduction_authority,
            operation=operation,
        )
        if observation is not None:
            observations.append(observation)
    return tuple(observations)


def invoice_deduction_authority(
    invoice: Invoice,
    *,
    linked_movements: Sequence[Transaction],
    devengo_date: date,
    operation: PinnedAuthorityOperation,
) -> DeductionAuthority | None:
    """Return the deduction identity a received invoice is declared under, or ``None``.

    The linked movements' recorded classification wins when they carry one and
    agree on all of it. Otherwise a domestic invoice whose every cuota line sits
    below the LIVA art. 108.Dos.5.º escaso-valor threshold is its own
    ``domestic_current`` authority (fact 0085: ``invoice_evidence``). Anything
    else -- a line that may be a bien de inversión, an import, an intra-EU
    acquisition, linked movements that disagree -- has no identity, and the
    caller reports the invoice instead of inventing one.
    """
    if invoice.kind is not InvoiceKind.RECEIVED:
        return None
    classified = tuple(
        movement
        for movement in linked_movements
        if movement.deduction_fact_kind is not None and movement.deduction_provenance is not None
    )
    if classified:
        identities = {
            (
                movement.deduction_fact_kind,
                movement.deduction_provenance,
                movement.investment_asset_id,
                movement.rectifies_ledger_id,
            )
            for movement in classified
        }
        return classified[0] if len(identities) == 1 else None
    declarations = resolve_iva_deduction_catalogue(effective_date=devengo_date, authority=operation).declarations
    domestic_categories = frozenset(
        token.strip() for token in declarations["category.domestic"].split(",") if token.strip()
    )
    if invoice.iva_category is not None and invoice.iva_category.value not in domestic_categories:
        return None
    threshold = bien_inversion_threshold(operation_date=devengo_date, operation=operation)
    for line_index, line in enumerate(invoice.lines):
        if line.iva_amount <= Decimal("0"):
            continue
        base_amount_eur, _iva_amount_eur = line_eur_amounts_or_refuse(invoice, line_index, line)
        if base_amount_eur >= threshold:
            return None
    return InvoiceEvidenceDeduction(
        deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=f"invoice:{invoice.invoice_id}",
            evidence_digest=invoice.invoice_id,
        ),
    )


def _cuota_lines_by_rate(invoice: Invoice) -> dict[IvaRate, list[int]]:
    """The indices of the invoice's cuota-bearing lines, grouped by IVA rate in line order."""
    groups: dict[IvaRate, list[int]] = {}
    for index, line in enumerate(invoice.lines):
        if line.iva_amount > Decimal("0"):
            groups.setdefault(line.iva_rate, []).append(index)
    return groups


def _sole_recargo_line_index(invoice: Invoice) -> int | None:
    """The first cuota line when every cuota line sits at one rate, the casilla the recargo names."""
    groups = _cuota_lines_by_rate(invoice)
    if len(groups) != 1:
        return None
    (indices,) = groups.values()
    return indices[0]


def _recargo_parts_by_rate(
    invoice: Invoice,
    *,
    recorded: Decimal,
    devengo_date: date,
    operation: PinnedAuthorityOperation,
) -> dict[int, Decimal] | None:
    """Each rate's share of a recargo spread over several rates, keyed by that rate's first line.

    LIVA art. 161 pairs every IVA rate with one recargo rate, so each rate's
    share is its base times that published rate. The shares stand only when
    they add up to the recorded recargo: otherwise the invoice records no
    figure that says how its recargo divides, and ``None`` keeps a share from
    being guessed into the wrong casilla.
    """
    parts: dict[int, Decimal] = {}
    for rate, indices in _cuota_lines_by_rate(invoice).items():
        applied_rate = iva_rate_percentage(rate, devengo_date)
        if applied_rate is None:
            return None
        record = recargo_rate_record_for_applied_rate(applied_rate, devengo_date, operation=operation)
        if record is None:
            return None
        base = sum((invoice.lines[index].subtotal for index in indices), Decimal("0"))
        parts[indices[0]] = round_to_cents(base * record.recargo_rate)
    if not parts or sum(parts.values(), Decimal("0")) != round_to_cents(recorded):
        return None
    return parts


def recargo_eur_by_line_index(
    invoice: Invoice,
    *,
    devengo_date: date,
    operation: PinnedAuthorityOperation,
) -> dict[int, Decimal] | None:
    """The recargo each line declares, in EUR, or ``None`` when no rate can be named for it.

    The recargo is recorded once on the invoice while the Modelo 303 recargo
    casillas are per IVA rate. Over one rate the recorded figure lands on that
    rate's first line as it stands. Over several, each rate's art. 161 share
    lands on that rate's first line, and the EUR figures are apportioned from
    the invoice's own EUR recargo so they add up to it exactly. An invoice with
    no recargo declares none on any line.
    """
    recorded = invoice.recargo_amount
    if recorded is None or recorded == Decimal("0"):
        return {}
    recargo_eur = invoice.recargo_amount_eur or Decimal("0")
    sole_index = _sole_recargo_line_index(invoice)
    if sole_index is not None:
        return {sole_index: recargo_eur}
    parts = _recargo_parts_by_rate(invoice, recorded=recorded, devengo_date=devengo_date, operation=operation)
    if parts is None:
        return None
    indices = list(parts)
    eur_parts = {index: round_to_cents(recargo_eur * parts[index] / recorded) for index in indices[:-1]}
    eur_parts[indices[-1]] = recargo_eur - sum(eur_parts.values(), Decimal("0"))
    return eur_parts


def out_of_window_summary_diagnostics(
    summary: OutOfWindowTransactionSummary | None,
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return the source diagnostics describing transactions outside the filing window, or none without a summary."""
    if summary is None:
        return ()
    return (
        out_of_window_summary_source_diagnostic(
            source_kind=source_kind,
            resolver_id=resolver_id,
            count=summary.count,
            min_filing_date=summary.min_filing_date,
            max_filing_date=summary.max_filing_date,
        ),
    )
