"""Invoice-to-ledger IVA screening for modelo binding resolution.

The calculation-facing ledger resolver remains in ._modelo_bindings. This sibling
owns the supporting invoice evidence comparison, category and recargo diagnostics,
and candidate screening required by that resolver.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core.i18n.translatable import Translatable as t
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.invoices.enums import iva_rate_percentage
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.flow import IvaFlowDirection, derive_flow_for_classification
from ...domain.iva.invoice_classification import invoice_line_to_iva_observation
from ...domain.iva.recargo_equivalencia import recargo_rate_for_applied_rate
from ...domain.transactions.models import OutOfWindowTransactionSummary
from ._modelo_bindings_support import STORAGE_DEGRADATION_ERRORS
from .errors import AggregationValidationError
from .invoice_devengo import (
    invoice_devengo_in_period,
    resolve_invoice_devengo,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    out_of_window_summary_source_diagnostic,
)
from .source_resolution_operations import source_diagnostics_for as _diagnostics_for

M303_INVOICE_EVIDENCE_SAMPLE_LIMIT = 5


def _resolve_invoice_iva_registry_declarations(*, effective_date: date) -> tuple[object, ...]:
    """Resolve the selected M303/M390 bindings and typed IVA mapping facts."""
    authority = bundled_authority()
    query_service = RegistryQueryService(authority)
    modelo_303 = query_service.describe_modelo("303")
    modelo_390 = query_service.describe_modelo("390")
    fact_ids = (
        "iva-invoice-classification-catalogue",
        "iva-category-component-catalogue",
        "iva-deduction-applicability-catalogue",
    )
    facts = tuple(
        authority.resolve_governed_fact(
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


def _invoice_line_iva_observation(
    *,
    invoice: Invoice,
    line: InvoiceLine,
    line_index: int,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: IvaLedgerObservation | None = None,
) -> IvaLedgerObservation | None:
    """Project one invoice line into the observation the screen declares from.

    Received invoice evidence never supplies its own deduction identity. Both
    SOPORTADO and INVERSION_SUJETO_PASIVO observations require the exact
    statutory deduction family and immutable classification provenance, and an
    invoice aggregate owns neither. They arrive as ``deduction_authority`` --
    the frozen transaction-ledger observation the invoice is linked to -- and
    are copied across unchanged. When no such authority is linked, or the
    linked ones disagree, the enclosing screen withholds the invoice entirely
    rather than invite an invented domestic-current default.

    A line carrying a cuota takes the standard-case classification, which
    derives the domestic category from the line's rate slot.

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
            :meth:`~domain.invoices.Invoice.line_amount_eur` -- the caller
            gates on a resolvable EUR amount before this is ever invoked, so
            every downstream construction reads this instead of the line's
            own native-currency field.
        iva_amount_eur: ``line.iva_amount`` already converted to EUR, same
            shape as *base_amount_eur*.
        deduction_authority: Exact frozen transaction-ledger authority linked
            to a received invoice, or ``None`` for an issued invoice.

    Returns:
        The observation to declare from, or ``None`` when the line routes
        nowhere.
    """
    ledger_id = f"invoice:{invoice.invoice_id}:{line_index}"
    if iva_amount_eur > Decimal("0"):
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
    return _invoice_line_iva_observation_without_iva(
        ledger_id=ledger_id,
        invoice=invoice,
        line=line,
        devengo_date=devengo_date,
        recargo_amount=recargo_amount,
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
        deduction_authority=deduction_authority,
    )


def _invoice_line_iva_observation_without_iva(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: IvaLedgerObservation | None,
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
    # A declared category is registry-owned. Until the selected revision is
    # supplied at this seam, refuse to invent a base-only route or flow.
    return None


def _standard_invoice_line_iva_observation(
    *,
    ledger_id: str,
    invoice: Invoice,
    line: InvoiceLine,
    devengo_date: date,
    recargo_amount: Decimal,
    base_amount_eur: Decimal,
    iva_amount_eur: Decimal,
    deduction_authority: IvaLedgerObservation | None = None,
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
    )


def _reverse_charge_cuota_not_derivable(invoice: Invoice) -> bool:
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
    if (
        derive_flow_for_classification(
            category=invoice.iva_category,
            invoice_direction=invoice.kind,
        )
        is not IvaFlowDirection.INVERSION_SUJETO_PASIVO
    ):
        return False
    # A rate-bearing line supplies its own evidence. No local tier catalogue is
    # retained here; an unresolved selected revision must refuse the gate.
    return all(getattr(line.iva_rate, "value", None) is None for line in invoice.lines)


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
    return _diagnostics_for(
        invoices,
        reason="invoice_category_counterparty_mismatch",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"invoice {invoice.invoice_number!r} declares "
            f"{invoice.iva_category.value if invoice.iva_category else 'no category'} but its "
            f"counterparty country {invoice.counterparty_country!r} cannot bear it, so its base "
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
    return _diagnostics_for(
        invoices,
        reason="invoice_reverse_charge_cuota_not_derivable",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"invoice {invoice.invoice_number!r} declares "
            f"{invoice.iva_category.value if invoice.iva_category else 'no category'}, so the "
            "recipient owes the self-assessed cuota, but no line states a rated tier to compute "
            "it from -- the cuota is NOT declared on this modelo"
        ),
        remedy=lambda _invoice: (
            "Record the rate the supply bore on the invoice line, keeping its cuota at zero, "
            "then recalculate so the self-assessment reaches its casilla"
        ),
    )


def missing_invoice_deduction_authority_diagnostics(
    invoices: Sequence[Invoice],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report received invoice evidence that reached no IVA input row.

    An invoice has an amount and a direction, but not the statutory deduction
    fact family nor the immutable evidence provenance that distinguishes a
    domestic current expense from an investment, import, acquisition, or
    rectification. Treating every received invoice as domestic-current would
    invent that authority, so the invoice is withheld instead.

    Non-blocking by the time it reaches here: the enclosing guard has already
    established that the transaction ledger carries this cuota, so the filing's
    totals are correct and only the invoice-to-transaction link is absent. Where
    the ledger does NOT carry it the guard refuses outright and this diagnostic
    is never reached.
    """
    return _diagnostics_for(
        invoices,
        reason="source_issue",
        source_kind="ledger_iva_aggregation",
        resolver_id=resolver_id,
        source_ref=lambda invoice: f"invoice:{invoice.invoice_id}",
        message=lambda invoice: (
            f"received invoice {invoice.invoice_number!r} carries IVA input evidence but no exact "
            "deduction fact kind or immutable evidence provenance, so it is declared from the "
            "transaction ledger rather than from the invoice"
        ),
        remedy=lambda _invoice: (
            "Link this invoice to its classified ledger transaction, so its deduction family and "
            "evidence provenance are recorded against the operation"
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


def _recargo_rate_divergence(invoice: Invoice, *, devengo_date: date) -> _RecargoRateDivergence | None:
    """Compare the recorded recargo against the rate art. 161 publishes for that slot.

    The invoice stays authoritative: this reads the recorded figure and never
    replaces it. What it adds is the other half of that posture -- when the
    supplier's figure departs from the published pairing, say so.

    Silent in three cases, each for its own reason and none of them a pass:

    * no recargo recorded at all, which is the ordinary invoice and not this
      screen's business;
    * no line identifiable as the one bearing it, so there is no base to
      compare against and a guess would be worse than silence;
    * the table resolving no rate for that (applied rate, date) pairing. An
      unmodelled window must NOT read as a mismatch -- that would turn a gap in
      our own data into an accusation about the supplier's invoice.
    """
    recorded = invoice.recargo_amount
    if recorded is None or recorded == 0:
        return None
    line_index = _sole_recargo_bearing_line_index(invoice)
    if line_index is None:
        return None
    line = invoice.lines[line_index]
    # The diagnostic has the same explicit devengo date as the recargo fact,
    # so it resolves the persisted slot through the exact IVA authority fact.
    applied_rate = iva_rate_percentage(line.iva_rate, devengo_date)
    if applied_rate is None:
        # Exempt and not-subject slots name no percentage, so there is no
        # pairing to look up and nothing to disagree with.
        return None
    recargo_rate = recargo_rate_for_applied_rate(applied_rate, devengo_date)
    if recargo_rate is None:
        return None
    expected = round_to_cents(line.subtotal * recargo_rate)
    if round_to_cents(recorded) == expected:
        return None
    return _RecargoRateDivergence(
        invoice=invoice,
        recorded=round_to_cents(recorded),
        expected=expected,
        applied_rate=applied_rate,
        recargo_rate=recargo_rate,
    )


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
                f"{divergence.recorded}, while the published schedule pairs the {divergence.applied_rate} IVA rate "
                f"with a recargo of {divergence.recargo_rate} on that date, which would give "
                f"{divergence.expected}. The recorded figure is the one declared -- this does not change it"
            ),
            remedy=(
                "Check the supplier invoice. Where the printed recargo is right, no action is needed and "
                "the declared figure already matches it; where it was mistyped, correct the transaction "
                "and recalculate"
            ),
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

    Fields:
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
            IVA evidence but which are linked to no frozen transaction-ledger
            observation carrying the exact deduction family and immutable
            evidence provenance an input row requires, or whose linked
            observations disagree about it.
        recargo_rate_divergences: invoices whose recorded recargo departs from
            the rate art. 161 publishes for that slot. Unlike the two above,
            these are NOT withheld -- the figure is declared exactly as
            recorded and the advisory is a cross-check beside it.
    """

    observations: tuple[IvaLedgerObservation, ...] = ()
    invoice_ids: tuple[str, ...] = ()
    compared: tuple[Invoice, ...] = ()
    category_counterparty_mismatches: tuple[Invoice, ...] = ()
    reverse_charge_underivable: tuple[Invoice, ...] = ()
    deduction_authority_missing: tuple[Invoice, ...] = ()
    recargo_rate_divergences: tuple[_RecargoRateDivergence, ...] = ()
    #: The catalogue could not be READ, as distinct from holding no invoices.
    #: Without this the two are the same value downstream, and the silence guard
    #: returns as though it had compared a catalogue it never saw.
    storage_degraded: bool = False


@dataclass(frozen=True, slots=True)
class InvoiceIvaSilenceReport:
    """The advisory surfaces the silence screen hands back to the resolver.

    Same reasoning as :class:`ScreenedInvoiceIva`: all three fields are
    ``tuple[Invoice, ...]``, so positionally they were interchangeable. The
    annotation on the previous tuple form had already drifted to two slots while
    the code returned three, which is what an unchecked positional widening
    looks like just before it goes wrong.
    """

    compared: tuple[Invoice, ...] = ()
    category_counterparty_mismatches: tuple[Invoice, ...] = ()
    reverse_charge_underivable: tuple[Invoice, ...] = ()
    #: Received invoices withheld for want of a linked ledger deduction
    #: authority, whose cuota the transaction ledger nonetheless already carries.
    #: Not a refusal -- the filing's totals are right -- but the operator still
    #: needs telling, or the unlinked invoice looks reconciled when it is not.
    deduction_authority_missing: tuple[Invoice, ...] = ()
    #: Carried on every return path, including the two early ones. A divergence
    #: is a fact about the recorded figure, not about whether the screen went on
    #: to build an observation, so dropping it when the screen returns early
    #: would silence the advisory exactly when the invoice is least examined.
    recargo_rate_divergences: tuple[_RecargoRateDivergence, ...] = ()
    #: The screen could not read the invoice catalogue, so it reached NO verdict
    #: about whether invoice IVA is absent from the ledger totals. Distinct from
    #: a clean pass, which is what a silent empty return looked like.
    storage_degraded: bool = False


@dataclass(frozen=True, slots=True)
class _ScreenedInvoiceIvaResult:
    """One invoice's screen facts, kept separate from the aggregate result."""

    observations: tuple[IvaLedgerObservation, ...]
    reverse_charge_underivable: bool
    recargo_rate_divergence: _RecargoRateDivergence | None
    deduction_authority_missing: bool
    category_counterparty_mismatch: bool


def screened_invoice_iva_observations(
    *,
    context: CalculationSourceContext,
    period: Period,
    ledger_observations: Sequence[IvaLedgerObservation] = (),
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> ScreenedInvoiceIva:
    try:
        repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=context.bucket_id)
        catalogue = repository.load()
    except STORAGE_DEGRADATION_ERRORS:
        # Degrading is right: a bucket whose invoice catalogue is temporarily
        # unreadable should not hard-fail every calculation, and the five
        # sibling catches in this module degrade too. What they also do, and
        # this one did not, is SAY SO -- they bind the error and return a
        # resolution carrying a storage_degraded diagnostic. Returning an empty
        # result here made an unreadable catalogue indistinguishable from an
        # empty one, which switched the silence guard off without a signal.
        return ScreenedInvoiceIva(storage_degraded=True)
    _resolve_invoice_iva_registry_declarations(effective_date=period.end_date)
    observations: list[IvaLedgerObservation] = []
    invoice_ids: set[str] = set()
    compared_invoices: list[Invoice] = []
    category_counterparty_mismatches: list[Invoice] = []
    reverse_charge_underivable: list[Invoice] = []
    deduction_authority_missing: list[Invoice] = []
    recargo_rate_divergences: list[_RecargoRateDivergence] = []
    for invoice in catalogue.values():
        if not _screened_invoice_in_period(invoice, context=context, period=period):
            continue
        screened = _screened_invoice_iva_result(
            invoice,
            ledger_observations=ledger_observations,
        )
        if screened.reverse_charge_underivable:
            reverse_charge_underivable.append(invoice)
        if screened.recargo_rate_divergence is not None:
            recargo_rate_divergences.append(screened.recargo_rate_divergence)
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
        invoice_ids=tuple(invoice_ids),
        compared=tuple(compared_invoices),
        category_counterparty_mismatches=tuple(category_counterparty_mismatches),
        reverse_charge_underivable=tuple(reverse_charge_underivable),
        deduction_authority_missing=tuple(deduction_authority_missing),
        recargo_rate_divergences=tuple(recargo_rate_divergences),
    )


def _screened_invoice_iva_result(
    invoice: Invoice,
    *,
    ledger_observations: Sequence[IvaLedgerObservation],
) -> _ScreenedInvoiceIvaResult:
    """Resolve one already-period-selected invoice into its IVA screen facts."""
    reverse_charge_underivable = _reverse_charge_cuota_not_derivable(invoice)
    # The date the observation carries must be the date it was SELECTED on,
    # or the record would state one quarter while being declared in another.
    devengo = resolve_invoice_devengo(invoice)
    # Read independently of the line projection: comparison is about the
    # recorded figure, not whether a line goes on to contribute an observation.
    recargo_rate_divergence = _recargo_rate_divergence(invoice, devengo_date=devengo.devengo_date)
    deduction_authority = _linked_invoice_deduction_authority(
        invoice,
        ledger_observations=ledger_observations,
    )
    deduction_authority_missing = (
        invoice.kind is InvoiceKind.RECEIVED
        and any(line.iva_amount > Decimal("0") for line in invoice.lines)
        and deduction_authority is None
    )
    observations: tuple[IvaLedgerObservation, ...] = ()
    if not deduction_authority_missing:
        observations = _screened_invoice_line_observations(
            invoice,
            devengo_date=devengo.devengo_date,
            deduction_authority=deduction_authority,
        )
    return _ScreenedInvoiceIvaResult(
        observations=observations,
        reverse_charge_underivable=reverse_charge_underivable,
        recargo_rate_divergence=recargo_rate_divergence,
        deduction_authority_missing=deduction_authority_missing,
        category_counterparty_mismatch=False,
    )


def _screened_invoice_line_observations(
    invoice: Invoice,
    *,
    devengo_date: date,
    deduction_authority: IvaLedgerObservation | None,
) -> tuple[IvaLedgerObservation, ...]:
    """Return the line observations eligible for one invoice comparison."""
    recargo_line_index = _sole_recargo_bearing_line_index(invoice)
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
        base_amount_eur = invoice.line_amount_eur(line.subtotal)
        iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
        if base_amount_eur is None or iva_amount_eur is None:
            raise AggregationValidationError(
                t("aggregation.modelo_bindings.errors.invoice_line_currency_unconverted"),
                context={
                    "invoice_id": invoice.invoice_id,
                    "invoice_number": invoice.invoice_number,
                    "currency": invoice.currency,
                    "line_index": str(line_index),
                },
            )
        # recargo_amount_eur is None both for "no recargo declared" and for
        # "unconverted" (same shape as the six sibling _eur properties), but
        # the base/iva check above already proved this invoice resolves a EUR
        # rate, so a None here can only mean the former -- defaulting to zero
        # is the genuine-absence case, not a silently dropped recargo.
        recargo_amount_eur = invoice.recargo_amount_eur or Decimal("0")
        observation = _invoice_line_iva_observation(
            invoice=invoice,
            line=line,
            line_index=line_index,
            devengo_date=devengo_date,
            recargo_amount=(recargo_amount_eur if line_index == recargo_line_index else Decimal("0")),
            base_amount_eur=base_amount_eur,
            iva_amount_eur=iva_amount_eur,
            deduction_authority=deduction_authority,
        )
        if observation is not None:
            observations.append(observation)
    return tuple(observations)


def _linked_invoice_deduction_authority(
    invoice: Invoice,
    *,
    ledger_observations: Sequence[IvaLedgerObservation],
) -> IvaLedgerObservation | None:
    """Return one exact linked ledger authority for a received invoice.

    Invoice amounts are evidence for the silence comparison, but the invoice
    aggregate does not own the current/investment/import/rectification decision.
    That authority lives on the frozen transaction-ledger observation. Every
    linked observation must therefore agree on the complete deduction identity;
    absence or disagreement is ambiguity and remains unprojected.
    """
    if invoice.kind is not InvoiceKind.RECEIVED:
        return None
    linked_ids = frozenset(invoice.linked_transaction_ids)
    authorities = tuple(
        observation
        for observation in ledger_observations
        if observation.ledger_id in linked_ids
        and observation.deduction_fact_kind is not None
        and observation.deduction_provenance is not None
    )
    if not authorities:
        return None
    first = authorities[0]
    identity = (
        first.deduction_fact_kind,
        first.deduction_provenance,
        first.investment_asset_id,
        first.rectifies_ledger_id,
    )
    if any(
        (
            observation.deduction_fact_kind,
            observation.deduction_provenance,
            observation.investment_asset_id,
            observation.rectifies_ledger_id,
        )
        != identity
        for observation in authorities[1:]
    ):
        return None
    return first


def _sole_recargo_bearing_line_index(invoice: Invoice) -> int | None:
    """Which line the invoice-level recargo belongs to, or ``None`` if unknowable.

    The recargo is recorded once on the invoice while the M303 recargo casillas
    are per rate TIER, so attributing it needs a tier. When every cuota-bearing
    line sits at the same rate the tier is unambiguous and the recargo lands
    there.

    When the invoice spans several tiers the invoice-level field cannot say how
    the surcharge divides, and this returns ``None`` rather than guessing.
    Picking a tier would place a real amount in the wrong casilla, which is
    worse than the screen not seeing it: a mis-tiered recargo is a wrong figure
    declared confidently, where an unscreened one is only an unscreened one.
    That gap is a limit of the invoice-level field, not of this screen.
    """
    if not invoice.recargo_amount:
        return None
    cuota_lines = [index for index, line in enumerate(invoice.lines) if line.iva_amount > Decimal("0")]
    if not cuota_lines:
        return None
    tiers = {invoice.lines[index].iva_rate for index in cuota_lines}
    if len(tiers) != 1:
        return None
    return cuota_lines[0]


def _screened_invoice_in_period(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
    period: Period,
) -> bool:
    """Whether this invoice's IVA belongs in the screen's ledger comparison.

    The counterparty's COUNTRY is deliberately not consulted. It was serving as
    a proxy for "carries Spanish IVA", and it is a poor one in both directions:
    an invoice to a foreign customer can carry ordinary Spanish cuota -- goods
    that never leave the país, a service localised here, a non-established
    consumer -- and those were silently exempt from the screen, which is the
    under-declaration it exists to catch. Meanwhile an exempt entrega
    intracomunitaria to an EU customer carries no cuota at all, so including it
    costs nothing.

    The property the screen actually needs is "does this line carry a positive
    cuota", and the caller already tests exactly that per line. Removing the
    country proxy therefore widens the screen without widening what it
    compares: a zero-cuota invoice contributes no observation whatever its
    counterparty's country, so no false refusal is introduced.

    Bucket attribution follows the same rule the invoice source resolver uses:
    only a POPULATED, mismatching bucket excludes. An unattributed invoice
    belongs to the store it was loaded from, and comparing on the bucket id
    alone dropped it from the screen silently -- the same shape, in the guard
    rather than in the projection.
    """
    return (invoice.bucket_id is None or invoice.bucket_id == context.bucket_id) and invoice_devengo_in_period(
        invoice, period=period
    )


def out_of_window_summary_diagnostics(
    summary: OutOfWindowTransactionSummary | None,
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
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
