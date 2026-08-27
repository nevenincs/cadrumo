"""Source-mesh resolver for governed invoice records.

:class:`InvoiceCatalogueSourceResolver` reads the
:class:`~domain.invoices.InvoiceCatalogue` selected by
:attr:`~application.aggregation.CalculationSourceContext.bucket_id` through
:class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository`. It projects those records
into the calculation mesh as
:class:`~application.aggregation.CalculationSourceResolution` values for
:attr:`~core.BindingSourceKind.COLLECTIBLE_INVOICE`,
:attr:`~core.BindingSourceKind.PAYABLE_INVOICE`, and the combined-direction
:attr:`~core.BindingSourceKind.M347_THIRD_PARTY_OPERATION`.

The :class:`~domain.invoices.Invoice` aggregate is the sole invoice record and
the reconciliation and link authority. Records reach the mesh only once they can
be represented as registry
:class:`~domain.calculations.registry.InvoiceObservation` facts, with Modelo 349
summary bindings, detail rows, transaction ids, and source provenance emitted
through one resolver envelope.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import ClassVar

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
)
from ...core import BindingSourceKind, CalculationSourceLineageRole, IntracomOperationType, Modelo, Period
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import sha256_hex
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    is_m347_declarante_summary_invoice_binding,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogueRepositoryProtocol,
    InvoiceDecomposition,
    InvoiceDecompositionDefect,
    decompose_invoice,
)
from ...domain.iva import InvoiceKind, IvaCategory
from ...domain.modelos import Modelo349OperadorRow, validate_m349_country_prefix_context
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)

_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (
    BindingSourceKind.COLLECTIBLE_INVOICE,
    BindingSourceKind.PAYABLE_INVOICE,
    BindingSourceKind.M347_THIRD_PARTY_OPERATION,
)
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)
_M349_PAYABLE_SUMMARY_BINDING_MIRRORS: dict[str, str] = {
    "iva-349-declarante-numero-operadores-adquisicion": "iva-349-declarante-numero-operadores",
    "iva-349-declarante-importe-operaciones-adquisicion": "iva-349-declarante-importe-operaciones",
    "iva-349-declarante-numero-rectificaciones-adquisicion": "iva-349-declarante-numero-rectificaciones",
    "iva-349-declarante-importe-rectificaciones-adquisicion": "iva-349-declarante-importe-rectificaciones",
}
_M349_OPERADOR_ROW_BINDINGS: dict[BindingId, str] = {
    "iva-349-operador-row-codigo-pais": "codigo_pais",
    "iva-349-operador-row-nif": "nif_comunitario",
    "iva-349-operador-row-apellidos": "razon_social",
    "iva-349-operador-row-clave": "clave_operacion",
    "iva-349-operador-row-base": "importe",
}
_COLLECTIBLE_M349_OPERATION_TYPES: frozenset[IntracomOperationType] = frozenset(
    {
        IntracomOperationType.E,
        IntracomOperationType.H,
        IntracomOperationType.M,
        IntracomOperationType.S,
        IntracomOperationType.T,
        IntracomOperationType.R,
        IntracomOperationType.D,
        IntracomOperationType.C,
    },
)
_PAYABLE_M349_OPERATION_TYPES: frozenset[IntracomOperationType] = frozenset(
    {
        IntracomOperationType.A,
        IntracomOperationType.ADQUISICION_SERVICIOS,
        IntracomOperationType.T,
    },
)

#: The claves an invoice's IVA category alone determines, keyed by side.
#:
#: Values are :class:`~cadrumo.core.IntracomOperationType` MEMBERS, never the
#: clave letters, because the member's ``value`` IS the letter the diseño de
#: registro defines: a literal beside the enum is a copy that can drift from
#: the thing it copies with nothing to catch it. The mismatch that makes this
#: concrete is the services acquisition, whose member is named
#: ``ADQUISICION_SERVICIOS`` while its clave is ``I`` -- a literal ``"I"`` here
#: would be reachable from neither the member name nor the letter by search.
#:
#: Membership is deliberately the FOUR entries a category identifies
#: unambiguously, plus triangulation handled separately because it is
#: kind-independent. It is NOT the full ten-clave set, and widening it here
#: would change what gets declared rather than how it is expressed:
#:
#: - ``M``/``H`` (supplies following an exempt importation, LIVA art. 27.12)
#:   share the intra-community supply category with ``E``, so no category
#:   predicate can separate them; the operator states them via the operation
#:   type, and the resolver discloses the ambiguity rather than guessing.
#: - ``R``/``D``/``C`` (the call-off stock claves) report movements that carry
#:   no invoice at all, so no invoice-sourced path can reach them.
_CLAVE_BY_KIND_AND_CATEGORY: dict[tuple[InvoiceKind, IvaCategory], IntracomOperationType] = {
    (InvoiceKind.ISSUED, IvaCategory.INTRA_COMMUNITY_SUPPLY): IntracomOperationType.E,
    # Goods and services stay separate rather than folding into E/A: Modelo 349
    # reports them under distinct claves, so a service declared as E would be
    # filed as an entrega de bienes.
    (InvoiceKind.ISSUED, IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY): IntracomOperationType.S,
    (
        InvoiceKind.RECEIVED,
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    ): IntracomOperationType.ADQUISICION_SERVICIOS,
    (
        InvoiceKind.RECEIVED,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    ): IntracomOperationType.A,
}


def invoice_direction_to_source_kind(kind: InvoiceKind) -> BindingSourceKind:
    """Map an invoice direction to its settlement source kind.

    The single contractual home for the direction<->settlement relationship,
    consumed by both :class:`InvoiceCatalogueSourceResolver` and the operator
    ``aeat app ledger invoice`` CLI. An *issued* invoice (we billed a customer)
    is *collectible*; a *received* invoice (a vendor billed us) is *payable*.

    Returns the canonical :class:`~core.BindingSourceKind` member rather than a
    locally-declared direction enum: the settlement taxonomy has exactly one
    home per ``aeat-registry-bindings``.

    Returns:
        The :class:`BindingSourceKind` settling ``kind``.
    """
    if kind is InvoiceKind.ISSUED:
        return BindingSourceKind.COLLECTIBLE_INVOICE
    return BindingSourceKind.PAYABLE_INVOICE


class InvoiceCatalogueSourceResolver:
    """Resolve invoice-source bindings and detail rows from persisted invoice records.

    The resolver owns both invoice source kinds in the calculation mesh. It
    filters records by :class:`CalculationSourceContext`, turns declarable
    intracommunity entries into :class:`InvoiceObservation` facts, and returns a
    :class:`CalculationSourceResolution` carrying binding values, Modelo 349
    detail rows, linked transaction ids, and stable source provenance.
    """

    resolver_id: ClassVar[str] = "invoice_catalogue"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = _OWNED_SOURCES

    def __init__(
        self,
        *,
        invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    ) -> None:
        self._invoice_repository = invoice_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        active_sources = _invoice_sources_for_revision(context)
        if not active_sources:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        repository = self._invoice_repository or InvoiceCatalogueRepository(bucket_id=context.bucket_id)
        try:
            catalogue = repository.load()
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=tuple(active_sources),
                error=exc,
            )
        source_invoices = tuple(
            invoice
            for invoice in catalogue.values()
            if _invoice_in_context(invoice, context) and _invoice_source_kind(invoice) in active_sources
        )
        catalogue_observed_items: list[tuple[Invoice, InvoiceObservation]] = []
        incoherent: list[tuple[Invoice, InvoiceDecomposition]] = []
        withheld_for_conversion: list[Invoice] = []
        for invoice in source_invoices:
            if _is_unconverted_foreign_invoice(invoice):
                withheld_for_conversion.append(invoice)
            observation = _invoice_observation(invoice, context=context)
            if observation is None:
                continue
            verdict = _m349_incoherent_verdict(invoice, context=context)
            if verdict is not None:
                incoherent.append((invoice, verdict))
                continue
            catalogue_observed_items.append((invoice, observation))
        catalogue_observed = tuple(catalogue_observed_items)
        observations = tuple(observation for _, observation in catalogue_observed)
        binding_values = resolve_invoice_binding_values(context.revision, observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=_m349_declarante_summary_union(context=context, binding_values=binding_values),
            detail_rows=_m349_operador_rows_from_observations(context=context, observations=observations),
            source_transaction_ids=tuple(
                sorted(
                    {
                        transaction_id
                        for invoice, _ in catalogue_observed
                        for transaction_id in invoice.linked_transaction_ids
                    },
                ),
            ),
            diagnostics=_m349_incoherence_diagnostics(incoherent, resolver_id=self.resolver_id)
            + _unconverted_foreign_diagnostics(
                withheld_for_conversion,
                context=context,
                resolver_id=self.resolver_id,
            )
            + (
                _m349_inferred_clave_diagnostics(
                    [invoice for invoice, _ in catalogue_observed],
                    bucket_invoices=tuple(catalogue.values()),
                    resolver_id=self.resolver_id,
                )
                if context.modelo == Modelo.M349.value
                else ()
            ),
            provenance=tuple(_invoice_provenance(invoice, observation) for invoice, observation in catalogue_observed),
        )


_M349_SELF_CONTRADICTION_DEFECTS: frozenset[InvoiceDecompositionDefect] = frozenset(
    {
        InvoiceDecompositionDefect.CUOTA_CONTRADICTS_CATEGORY,
        InvoiceDecompositionDefect.CATEGORY_IMPOSSIBLE_ON_THIS_KIND,
    },
)
"""Decomposition defects where two declarations on one record disagree.

Both members describe a record whose operator made two assertions that cannot
both be true -- an entrega exenta under LIVA art. 25 carrying a repercuted
cuota, or a one-directional category recorded on its impossible side. The
remaining members describe something ABSENT, which on this surface is a gap in
what the record can express rather than evidence that its figures are wrong.
"""


def _m349_incoherent_verdict(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
) -> InvoiceDecomposition | None:
    """Return the decomposition verdict when it disqualifies an M349 record.

    Scoped to Modelo 349 deliberately, and only after the clave is settled.

    Modelo 349 is the one invoice-sourced surface whose declared figure is
    conditioned on the declared IVA treatment: the clave is CHOSEN from
    :attr:`~cadrumo.domain.invoices.Invoice.iva_category`, and the base
    declared under it is the base imponible of an operation the record asserts
    is exenta under LIVA art. 25. A record simultaneously claiming that
    exemption and carrying a repercuted cuota contradicts itself, and the
    contract cannot tell which of the two declarations is the mistake, so it
    grounds neither.

    Modelo 347 asks a different question and is deliberately NOT checked here.
    Its declared figure is the total contraprestacion of operations with one
    third party (RD 1065/2007 art. 34), which the invoice's own totals identity
    already bounds and which no IVA category conditions. Running the contract
    there would drop real above-threshold operations out of an informativa on
    the strength of an unrelated missing field. The OSS/IOSS path is excluded
    for the same reason plus a stronger one: no
    :class:`~cadrumo.domain.iva.IvaCategory` member names an OSS operation at
    all -- the OSS axis is the regime and transaction kind -- so every
    legitimate OSS invoice would come back ungrounded, and that path already
    runs the coherence check that does apply to it, cross-checking the
    persisted cuota against the destination Member State's published rate.

    Within Modelo 349 the check is narrowed again, to the defects where the
    record CONTRADICTS ITSELF. Absence is deliberately not disqualifying, and
    the reason is structural: **an absent category does not mean the operation
    was inexpressible, it usually means the clave came from somewhere else.**
    :func:`_intracommunity_clave` consults an explicit
    :attr:`~cadrumo.domain.invoices.Invoice.operation_type` FIRST and returns
    without ever reading ``iva_category``, so a record carrying a directly
    declared clave legitimately carries no category at all. Since this check
    runs only after the clave is settled, treating absence as disqualifying
    would drop exactly the records whose clave the operator stated most
    explicitly -- the least ambiguous rows in the store.

    That reasoning is deliberately independent of what the category enum
    happens to contain, because the previous justification was not and went
    stale. It asserted that an ordinary prestacion or adquisicion de servicios
    intracomunitaria "maps to no :class:`~cadrumo.domain.iva.IvaCategory`
    member at all, because the enum names goods, acquisitions and triangulation
    but not services". The enum has since gained
    ``INTRA_COMMUNITY_SERVICE_SUPPLY`` and
    ``INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE``, and
    :func:`_intracommunity_clave` maps both to their claves a hundred-odd lines
    below -- so the stated ground for weakening a filing-path guard was refuted
    by the same module that stated it.

    The behaviour is unchanged, and that is a decision rather than an
    omission: making absence disqualifying would alter filed M349 output, which
    needs its own evidence and its own ruling, not a docstring correction.
    Services now being expressible only strengthens the conclusion -- a
    services invoice can reach its clave through either route, so absence is
    even weaker evidence of an unrepresentable operation than before.

    ``FX_UNRESOLVED`` is likewise excluded here because the unconverted-foreign
    gate upstream already withholds those records.
    """
    if context.modelo != Modelo.M349.value:
        return None
    verdict = decompose_invoice(invoice)
    contradictions = tuple(defect for defect in verdict.defects if defect in _M349_SELF_CONTRADICTION_DEFECTS)
    if not contradictions:
        return None
    return verdict.model_copy(update={"defects": contradictions})


#: Diagnostic ``reason`` for a Modelo 349 clave the resolver inferred from the
#: invoice's IVA category because the record carried no explicit operation type.
M349_CLAVE_INFERRED_REASON = "m349_clave_inferred_from_category"


def _clave_was_inferred_as_entrega(invoice: Invoice) -> bool:
    """Return whether this invoice's clave E was a guess rather than a statement.

    True only for the one ambiguous case: an issued exempt intra-community
    supply carrying no operation type, which ``_intracommunity_clave`` resolves
    to E. Every other fallback branch maps a category that identifies its clave
    unambiguously, and a record carrying an operation type stated its clave
    outright.
    """
    return (
        invoice.operation_type is None
        and invoice.kind is InvoiceKind.ISSUED
        and invoice.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    )


def _m349_inferred_clave_diagnostics(
    declared: Sequence[Invoice],
    *,
    bucket_invoices: Sequence[Invoice],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return at most ONE advisory disclosing that claves were inferred, not read.

    Aggregated rather than per-invoice, and that is the whole design. The
    ambiguity this discloses is not separable at this layer -- the prior
    importation that distinguishes an art. 27.12 supply from an ordinary art. 25
    one appears nowhere on the invoice -- so a per-record advisory would fire on
    every ordinary intra-community supply a taxpayer makes. Firing on the correct
    majority is what trains an operator to ignore a channel, and it would forfeit
    this disclosure exactly when it matters.

    One line per calculation states an assumption; N lines per calculation is an
    alarm about nothing. The count and the invoice numbers are carried so the
    operator can find the records without the advisory having to accuse each one.
    """
    inferred = [invoice for invoice in declared if _clave_was_inferred_as_entrega(invoice)]
    if not inferred:
        return ()
    # The discriminator, and the reason this is a disclosure rather than noise.
    # Clave M or H requires a PRIOR exempt importation by this same taxpayer
    # (LIVA art. 27.12 exempts the importation only because the onward supply is
    # art. 25 exempt). A bucket holding no importation at all therefore cannot
    # contain a post-importation supply, so the inferred E is not merely likely
    # correct there -- it is the only clave available, and saying so would be an
    # alarm about nothing on every Modelo 349 an ordinary EU-trading taxpayer
    # ever files.
    # Read across the whole bucket, not the declared set: an importation is a
    # RECEIVED record that produces no Modelo 349 row of its own, so it is absent
    # from ``declared`` by construction and invisible to a scan of it.
    if not any(invoice.iva_category is IvaCategory.IMPORT_THIRD_COUNTRY for invoice in bucket_invoices):
        return ()
    numbers = ", ".join(sorted(invoice.invoice_number for invoice in inferred))
    return (
        CalculationSourceDiagnostic(
            reason=M349_CLAVE_INFERRED_REASON,
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
            resolver_id=resolver_id,
            message=(
                f"{len(inferred)} intra-community supplies carry no operation type, so their Modelo 349 "
                f"clave was inferred as 'E' from the IVA category ({numbers}). That is correct for an "
                "ordinary exempt supply under LIVA art. 25, but a supply following an exempt importation "
                "(art. 27.12) reports under clave 'M', or 'H' when made through a representante fiscal, "
                "and the invoice records no fact that distinguishes the two."
            ),
            remedy=(
                "If any of these supplies followed an exempt importation, set its operation type to M or H "
                "and recalculate; otherwise the inferred clave is correct and no action is needed."
            ),
            # Advisory-asserted: this module holds no revision, snapshot or
            # casilla definition anywhere -- the claim spans two provisions
            # (the ordinary art. 25 exemption and the art. 27.12 post-importation
            # carve-out) about the invoice catalogue as a whole, not about one
            # M349 casilla.
            asserted_legal_refs=("ley-37-1992:art-25", "ley-37-1992:art-27"),
        ),
    )


def _m349_incoherence_diagnostics(
    incoherent: Sequence[tuple[Invoice, InvoiceDecomposition]],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per record the decomposition contract disqualified.

    Excluded-but-VISIBLE. The record stays in the catalogue and stays editable;
    what it must not do is disappear from the recapitulativa without the
    operator being told, because a missing intracomunitaria is an
    under-declaration whether it was dropped by a contradiction or by silence.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="ungrounded_income_substrate",
            source_kind=str(_invoice_source_kind(invoice)),
            resolver_id=resolver_id,
            source_ref=f"invoice:{invoice.invoice_id}",
            message=(
                f"invoice {invoice.invoice_number!r} declares an intracommunity operation "
                f"the decomposition contract could not ground "
                f"({', '.join(defect.value for defect in verdict.defects)}), so its base is "
                "NOT declared on this Modelo 349"
            ),
            remedy=(
                "Reconcile the invoice's declared IVA treatment with the amounts recorded on "
                "it, then recalculate so the operation reaches the recapitulativa"
            ),
        )
        for invoice, verdict in incoherent
    )


def _unconverted_foreign_diagnostics(
    invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per invoice withheld for want of a euro conversion.

    Excluding the AMOUNT is settled and correct: a foreign invoice with no
    resolved rate has an unknown euro value, and declaring its face value as
    euro would be a mis-declaration rather than a conservative one.

    Excluding it in SILENCE is the defect. The operation is real and declarable
    -- the euro figure is what is missing, not the operation -- so an
    informativa that simply omits it leaves the operator filing an incomplete
    return with nothing on any surface saying so. This is the same principle
    :func:`_m349_incoherence_diagnostics` already states: a missing record is an
    under-declaration whether it was dropped by a contradiction or by silence.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="unconverted_foreign_currency",
            source_kind=str(_invoice_source_kind(invoice)),
            resolver_id=resolver_id,
            source_ref=f"invoice:{invoice.invoice_id}",
            message=(
                f"invoice {invoice.invoice_number!r} is denominated in {invoice.currency} with no "
                f"resolved euro rate, so it is NOT declared on this Modelo {context.modelo}; its "
                "euro value is unknown and declaring the foreign amount as euro would misstate it"
            ),
            remedy=(
                "Record the euro conversion rate on the invoice, then recalculate so the "
                "operation reaches the declaration"
            ),
        )
        for invoice in invoices
    )


def _invoice_sources_for_revision(context: CalculationSourceContext) -> frozenset[BindingSourceKind]:
    declared_sources = frozenset(
        binding.source for binding in context.revision.bindings if binding.source in _OWNED_SOURCES
    )
    if any(is_m347_declarante_summary_invoice_binding(binding) for binding in context.revision.bindings):
        return frozenset(_OWNED_SOURCES)
    return declared_sources


def _invoice_in_context(invoice: Invoice, context: CalculationSourceContext) -> bool:
    """Whether this invoice is declarable for the context's bucket and period.

    Only a POPULATED, mismatching bucket excludes. An unattributed invoice
    belongs to the store it was loaded from, and that store is opened against
    ``context.bucket_id`` -- with ``InvoiceCatalogueRepository`` refusing a
    foreign row on read, so nothing another bucket owns reaches here.

    Treating ``None`` as a mismatch is what this reads as if the check is
    written against the bucket id alone, and it is silent: an unattributed
    invoice compares unequal to every real bucket, so it drops out of M347 and
    M349 with no defect, no advisory and no refusal. Nothing downstream of the
    filter can tell "this taxpayer had no such operations" apart from "the
    filter discarded them", which is the shape a declaration must never take.

    This is the same rule the persistence guard applies, deliberately: the two
    layers previously disagreed about whether an unattributed invoice was
    normal, and a disagreement about that between the store and the projection
    is resolved in favour of declaring.
    """
    if invoice.bucket_id is not None and invoice.bucket_id != context.bucket_id:
        return False
    return _date_in_period(invoice.issued_at, period=context.period)


def _date_in_period(value: date, *, period: Period) -> bool:
    return period.contains(value)


def _invoice_source_kind(invoice: Invoice) -> str:
    return invoice_direction_to_source_kind(invoice.kind).value


def _eur(converted: Decimal | None, invoice: Invoice) -> Decimal:
    """Return the euro amount, refusing rather than falling back to face value.

    ``None`` here means the caller skipped the
    :func:`_is_unconverted_foreign_invoice` gate. Falling back to the native
    amount would be the exact silent mis-declaration this path exists to
    prevent, so the inconsistency is raised instead.
    """
    if converted is None:
        msg = (
            f"invoice {invoice.invoice_id} is denominated in {invoice.currency} with no resolved "
            f"euro value; it must be gated out of projection, not declared at face value"
        )
        raise RegistryValidationError(msg)
    return converted


def _is_unconverted_foreign_invoice(invoice: Invoice) -> bool:
    """Return whether *invoice* is foreign-currency with no euro equivalent.

    Mirrors the ledger's ``is_non_eur_without_conversion`` gate. Every modelo
    amount is declared in euro, so an invoice whose euro value could not be
    resolved must be withheld from projection: summing its face value would
    declare foreign units as euro.
    """
    return invoice.currency != DEFAULT_CURRENCY and invoice.grand_total_eur is None


def _invoice_observation(invoice: Invoice, *, context: CalculationSourceContext) -> InvoiceObservation | None:
    if _is_unconverted_foreign_invoice(invoice):
        return None
    if invoice.counterparty_tax_id is None:
        # M347/M349 both declare a third party by their tax id; a factura
        # simplificada legitimately carries none (RD 1619/2012 art. 6.1.d), so
        # it has nothing these informativas can declare rather than a defect.
        return None
    if context.modelo == Modelo.M347.value:
        return _m347_invoice_observation(invoice)
    clave = _intracommunity_clave(invoice)
    if clave is None:
        return None
    if context.modelo == Modelo.M349.value:
        validate_m349_country_prefix_context(
            country_code=invoice.counterparty_country,
            clave_operacion=clave,
            filing_year=context.filing_year,
            period=context.period.registry_token,
        )
    return InvoiceObservation(
        invoice_id=invoice.invoice_id,
        source_kind=BindingSourceKind(_invoice_source_kind(invoice)),
        party_tax_id=invoice.counterparty_tax_id,
        country_code=invoice.counterparty_country,
        transaction_date=invoice.issued_at,
        base_amount=_eur(invoice.base_total_eur, invoice),
        invoice_total_amount=_eur(invoice.grand_total_eur, invoice),
        intracommunity_clave=clave,
        party_legal_name=invoice.counterparty_name,
    )


def _m347_invoice_observation(invoice: Invoice) -> InvoiceObservation | None:
    """Build the M347 observation for one invoice, or ``None`` if excluded.

    Declares a counterparty regardless of residency: RD 1065/2007 art. 33.2 is
    a CLOSED exclusion list, and a counterparty's non-residency is not one of
    its nine enumerated items (see `2026-08-27-tui-architecture-modelo-347-counterparty-residency-scope-adr`).
    The diseño de registro's own `pais-codigo` field (a "XX" alphabetic slot
    for a non-established non-resident declarado) is direct evidence AEAT
    expects some M347 counterparties to be non-resident.

    The one residency-shaped exclusion the article DOES state is art.
    33.2.i): an operation already reported through a coincident periodic
    informativa. For an invoice, that informativa is Modelo 349's
    intracommunity recapitulativa, so an operation `_intracommunity_clave`
    classifies as intracommunity is excluded here and routes to M349 instead
    -- the same classification M349's own branch of this resolver uses, never
    a bare country comparison.
    """
    if _intracommunity_clave(invoice) is not None:
        return None
    if invoice.counterparty_tax_id is None:
        # Same reason as the general builder above: M347 declares a third party
        # by their tax id, and a factura simplificada legitimately carries none
        # (RD 1619/2012 art. 6.1.d). Without this the row reached the observation
        # constructor with None and raised there instead of being skipped.
        return None
    return InvoiceObservation(
        invoice_id=invoice.invoice_id,
        source_kind=BindingSourceKind(_invoice_source_kind(invoice)),
        party_tax_id=invoice.counterparty_tax_id,
        country_code=invoice.counterparty_country,
        transaction_date=invoice.issued_at,
        base_amount=_eur(invoice.base_total_eur, invoice),
        invoice_total_amount=_eur(invoice.grand_total_eur, invoice),
        intracommunity_clave=None,
        party_legal_name=invoice.counterparty_name,
    )


def _intracommunity_clave(invoice: Invoice) -> str | None:
    """Return the Modelo 349 clave de operación for one invoice, or ``None``.

    :class:`~cadrumo.core.IntracomOperationType` is the clave authority -- its
    member VALUES are the letters the diseño de registro defines, which is why
    the explicit branch below returns the value directly rather than mapping it.
    The category branches are a fallback for an invoice that carries no
    operation type, which is the common case: the field is optional on every
    creation path.

    That fallback reaches five of the ten claves, and the five it omits are
    omitted for two different reasons worth separating, because the gap reads
    as an oversight otherwise.

    R, D and C are unreachable here BY CONSTRUCTION, not by omission. They are
    the call-off stock claves -- a transfer of goods under a consignment sales
    arrangement, a return of those goods, and a substitution of the intended
    acquirer. LIVA art. 9 bis.Dos places the entrega, and its art. 25 exemption,
    at the moment the acquirer takes the power of disposal, which is later than
    and separate from the movement those three claves report. The movement
    transfers no ownership and so carries no invoice at all; art. 9 bis.Uno.d
    has the vendor declare the despatch through the libro registro and the
    declaración recapitulativa precisely because there is no supply yet to
    invoice. An invoice-sourced path therefore cannot produce them, and no
    predicate added here would help -- they need a non-invoice record source.

    M and H are a real limit rather than a scope boundary. Both are ordinary
    invoiced entregas intracomunitarias that happen to FOLLOW an exempt
    importation (LIVA art. 27.12, H being the variant made by a representante
    fiscal under art. 86.Tres), so they carry the same intra-community supply
    category as an art. 25 supply and the fallback cannot tell them apart --
    the distinguishing fact is the prior importation, which appears nowhere on
    the invoice except in the operation type itself. The diseño defines E as
    excluding exactly these, directing them to M or H, so an operator with such
    a supply MUST set the operation type. The fallback's E is correct for the
    ordinary case and wrong for this one, and refusing instead is not the
    remedy: no predicate here separates the two, so a refusal falls on the whole
    category and makes the ordinary supply undeclarable -- measured, six
    otherwise-passing M349 flows.
    """
    operation_type = invoice.operation_type
    if operation_type is not None:
        return _m349_clave_for_operation_type(
            invoice_id=invoice.invoice_id,
            source_kind=BindingSourceKind(_invoice_source_kind(invoice)),
            operation_type=operation_type,
            record_label="catalogue invoice",
        )
    # Triangulation first, and kind-independent: LIVA art. 26.3 exempts the
    # intermediary's adquisición while the onward leg is a supply, so the
    # taxpayer files clave T from either side of the operation.
    if invoice.iva_category is IvaCategory.INTRA_COMMUNITY_TRIANGULATION:
        return IntracomOperationType.T.value
    if invoice.iva_category is None:
        return None
    derived = _CLAVE_BY_KIND_AND_CATEGORY.get((invoice.kind, invoice.iva_category))
    return None if derived is None else derived.value


def _m349_clave_for_operation_type(
    *,
    invoice_id: str,
    source_kind: BindingSourceKind,
    operation_type: IntracomOperationType,
    record_label: str,
) -> str:
    allowed = (
        _COLLECTIBLE_M349_OPERATION_TYPES
        if source_kind is BindingSourceKind.COLLECTIBLE_INVOICE
        else _PAYABLE_M349_OPERATION_TYPES
    )
    if operation_type not in allowed:
        accepted = ", ".join(item.value for item in sorted(allowed, key=lambda item: item.value))
        raise RegistryValidationError(
            f"{record_label} {invoice_id!r} uses operation type {operation_type.value!r} "
            f"with source kind {source_kind.value!r}; accepted: {accepted}",
        )
    return operation_type.value


def _m349_declarante_summary_union(
    *,
    context: CalculationSourceContext,
    binding_values: dict[str, Decimal],
) -> dict[str, Decimal]:
    if context.modelo != Modelo.M349.value:
        return binding_values
    merged = dict(binding_values)
    for payable_binding, public_binding in _M349_PAYABLE_SUMMARY_BINDING_MIRRORS.items():
        if payable_binding not in binding_values:
            continue
        merged[public_binding] = merged.get(public_binding, Decimal("0")) + binding_values[payable_binding]
    return merged


def _m349_operador_rows_from_observations(
    *,
    context: CalculationSourceContext,
    observations: tuple[InvoiceObservation, ...],
) -> tuple[Modelo349OperadorRow, ...]:
    if context.modelo != Modelo.M349.value or not observations:
        return ()
    row_values = resolve_invoice_binding_row_values(context.revision, observations)
    rows: list[Modelo349OperadorRow] = []
    row_indexes = sorted(
        {row_index for binding_id, row_index in row_values if binding_id in _M349_OPERADOR_ROW_BINDINGS},
    )
    for row_index in row_indexes:
        values = {
            attr: row_values[(binding_id, row_index)]
            for binding_id, attr in _M349_OPERADOR_ROW_BINDINGS.items()
            if (binding_id, row_index) in row_values
        }
        if set(values) != set(_M349_OPERADOR_ROW_BINDINGS.values()):
            raise RegistryValidationError(f"Modelo 349 invoice row {row_index} is incomplete")
        codigo_pais = values["codigo_pais"]
        nif_comunitario = values["nif_comunitario"]
        razon_social = values["razon_social"]
        clave_operacion = values["clave_operacion"]
        importe = values["importe"]
        if not (
            isinstance(codigo_pais, str)
            and isinstance(nif_comunitario, str)
            and isinstance(razon_social, str)
            and isinstance(clave_operacion, str)
            and isinstance(importe, Decimal)
        ):
            raise RegistryValidationError(f"Modelo 349 invoice row {row_index} has invalid field types")
        try:
            row = Modelo349OperadorRow.model_validate(
                {
                    "codigo_pais": codigo_pais,
                    "nif_comunitario": f"{codigo_pais}{nif_comunitario}",
                    "razon_social": razon_social,
                    "clave_operacion": clave_operacion,
                    "importe": importe,
                },
            )
        except ValueError as exc:
            raise RegistryValidationError(str(exc)) from exc
        rows.append(row)
    return tuple(rows)


def _invoice_provenance(invoice: Invoice, observation: InvoiceObservation) -> CalculationSourceProvenance:
    payload = observation.model_dump_json()
    source_kind = _invoice_source_kind(invoice)
    return CalculationSourceProvenance(
        resolver_id=InvoiceCatalogueSourceResolver.resolver_id,
        resolved_binding_source=BindingSourceKind(source_kind),
        contributor_source_kind=source_kind,
        contributor_binding_source=BindingSourceKind(source_kind),
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=f"{source_kind}:{observation.invoice_id}",
        parent_source_ref=None,
        fingerprint=f"sha256:{sha256_hex(payload.encode('utf-8'))}",
    )


__all__ = ["InvoiceCatalogueSourceResolver", "invoice_direction_to_source_kind"]
