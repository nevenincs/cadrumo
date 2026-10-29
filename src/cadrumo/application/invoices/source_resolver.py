"""Invoice source source resolver responsibilities."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import ClassVar

from ...core.aggregation import (
    BindingSourceKind,
    CalculationSourceLineageRole,
)
from ...core.hashing import prefixed_digest
from ...core.modelo import Modelo
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_binding_values,
)
from ...domain.calculations.registry.iva_category_catalogue import (
    require_iva_category,
)
from ...domain.invoices.decomposition import InvoiceDecomposition, InvoiceDecompositionDefect, decompose_invoice
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ..aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..aggregation.source_resolution_operations import storage_degradation_resolution
from .source_advisories import (
    m347_declaration_advisories,
    m347_exclusion_reading_advisories,
    m347_received_invoice_dating_advisories,
    m347_role_fact_advisories,
)
from .source_observations import (
    COMBINED_DIRECTION_SOURCES,
    OWNED_SOURCES,
    M347Filer,
    ObservedInvoice,
    filing_period_date,
    invoice_direction_to_source_kind,
    invoice_in_context,
    invoice_observation,
    invoice_row_values,
    invoice_source_kind,
    invoice_sources_for_revision,
    is_unconverted_foreign_invoice,
    m349_operador_rows_from_values,
    resolve_m347_filer,
    row_values_not_carried_by_detail_rows,
)
from .source_resolver_ports import InvoiceSourcePersistenceError, InvoiceSourceResolverPorts

_IncoherentInvoice = tuple[Invoice, InvoiceDecomposition]


def _invoice_sources_in_context(
    invoices: Iterable[Invoice],
    *,
    context: CalculationSourceContext,
    active_sources: frozenset[BindingSourceKind],
) -> tuple[Invoice, ...]:
    return tuple(
        invoice
        for invoice in invoices
        if invoice_in_context(invoice, context) and invoice_source_kind(invoice) in active_sources
    )


def _observe_invoice_sources(
    source_invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    m347_filer: M347Filer,
) -> tuple[tuple[ObservedInvoice, ...], tuple[_IncoherentInvoice, ...], tuple[Invoice, ...]]:
    observed_items: list[ObservedInvoice] = []
    incoherent: list[_IncoherentInvoice] = []
    withheld_for_conversion: list[Invoice] = []
    for invoice in source_invoices:
        if is_unconverted_foreign_invoice(invoice):
            withheld_for_conversion.append(invoice)
        observation = invoice_observation(invoice, context=context, m347_filer=m347_filer)
        if observation is None:
            continue
        verdict = _m349_incoherent_verdict(invoice, context=context)
        if verdict is not None:
            incoherent.append((invoice, verdict))
            continue
        observed_items.append((invoice, observation))
    return tuple(observed_items), tuple(incoherent), tuple(withheld_for_conversion)


def _invoice_resolution_from_observations(
    *,
    context: CalculationSourceContext,
    catalogue_invoices: Sequence[Invoice],
    source_invoices: Sequence[Invoice],
    observed_items: tuple[ObservedInvoice, ...],
    incoherent: tuple[_IncoherentInvoice, ...],
    withheld_for_conversion: tuple[Invoice, ...],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    m347_filer: M347Filer,
) -> CalculationSourceResolution:
    observations = tuple(observation for _, observation in observed_items)
    binding_values = resolve_invoice_binding_values(
        context.revision,
        observations,
        effective_date=filing_period_date(context),
    )
    row_values = invoice_row_values(context=context, observations=observations)
    resolved_binding_ids = binding_values.keys() | {binding_id for binding_id, _ in row_values}
    resolved_sources = frozenset(
        binding.source for binding in context.revision.bindings if binding.id in resolved_binding_ids
    )
    declared_invoices = tuple(invoice for invoice, _ in observed_items)
    diagnostics = _m349_incoherence_diagnostics(incoherent, resolver_id=resolver_id)
    diagnostics += _unconverted_foreign_diagnostics(
        withheld_for_conversion,
        context=context,
        resolver_id=resolver_id,
    )
    if context.modelo == Modelo("349").value:
        diagnostics += _m349_inferred_clave_diagnostics(
            declared_invoices,
            bucket_invoices=catalogue_invoices,
            resolver_id=resolver_id,
        )
    diagnostics += m347_role_fact_advisories(
        source_invoices,
        context=context,
        resolver_id=resolver_id,
        declaration_roles=m347_filer.declaration_roles,
    )
    diagnostics += m347_declaration_advisories(
        observed_items,
        source_invoices,
        context=context,
        resolver_id=resolver_id,
    )
    diagnostics += m347_exclusion_reading_advisories(observed_items, context=context, resolver_id=resolver_id)
    diagnostics += m347_received_invoice_dating_advisories(
        observed_items,
        catalogue_invoices,
        context=context,
        resolver_id=resolver_id,
        m347_filer=m347_filer,
    )
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        binding_values=binding_values,
        row_binding_values=row_values_not_carried_by_detail_rows(row_values),
        detail_rows=m349_operador_rows_from_values(row_values),
        source_transaction_ids=_source_transaction_ids(observed_items),
        diagnostics=diagnostics,
        provenance=tuple(
            row
            for invoice, observation in observed_items
            for row in _invoice_provenance(invoice, observation, resolved_sources=resolved_sources)
        ),
    )


def _source_transaction_ids(observed_items: Sequence[ObservedInvoice]) -> tuple[str, ...]:
    return tuple(
        sorted({transaction_id for invoice, _ in observed_items for transaction_id in invoice.linked_transaction_ids})
    )


class InvoiceCatalogueSourceResolver:
    """Resolve invoice-source bindings and detail rows from persisted invoice records.

    The resolver owns both invoice source kinds in the calculation mesh. It
    filters records by :class:`CalculationSourceContext`, turns declarable
    intracommunity entries into :class:`InvoiceObservation` facts, and returns a
    :class:`CalculationSourceResolution` carrying binding values, row binding
    values, Modelo 349 detail rows, linked transaction ids, and stable source
    provenance.
    """

    resolver_id: ClassVar[str] = "invoice_catalogue"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = OWNED_SOURCES

    def __init__(
        self,
        *,
        ports: InvoiceSourceResolverPorts,
    ) -> None:
        """Bind the resolver to its explicitly composed invoice read capability.

        Args:
            ports: Required application-owned capabilities for invoice source
                resolution.
        """
        self._ports = ports

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve this context's invoice-source bindings against the catalogue.

        Args:
            context: Modelo, revision, period, and bucket selecting both the
                active invoice sources and the invoices in scope.

        Returns:
            The resolution carrying binding values, row binding values, Modelo
            349 detail rows, linked transaction ids, diagnostics, and source
            provenance. Sources
            the active revision does not declare resolve to an empty result, and
            a degraded catalogue read resolves to a storage-degradation result
            rather than a zero total.
        """
        active_sources = invoice_sources_for_revision(context)
        if not active_sources:
            return CalculationSourceResolution(resolver_id=self.resolver_id, owned_sources=self.owned_sources)

        try:
            catalogue = self._ports.catalogue_reader.load()
        except InvoiceSourcePersistenceError as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=tuple(active_sources),
                error=exc,
            )
        catalogue_invoices = tuple(catalogue.values())
        source_invoices = _invoice_sources_in_context(
            catalogue_invoices,
            context=context,
            active_sources=active_sources,
        )
        m347_filer = resolve_m347_filer(context)
        observed_items, incoherent, withheld_for_conversion = _observe_invoice_sources(
            source_invoices,
            context=context,
            m347_filer=m347_filer,
        )
        return _invoice_resolution_from_observations(
            context=context,
            catalogue_invoices=catalogue_invoices,
            source_invoices=source_invoices,
            observed_items=observed_items,
            incoherent=incoherent,
            withheld_for_conversion=withheld_for_conversion,
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            m347_filer=m347_filer,
        )


_M349_SELF_CONTRADICTION_DEFECTS: frozenset[InvoiceDecompositionDefect] = frozenset(
    {
        InvoiceDecompositionDefect.CUOTA_CONTRADICTS_CATEGORY,
        InvoiceDecompositionDefect.CATEGORY_IMPOSSIBLE_ON_THIS_KIND,
    },
)


def _m349_incoherent_verdict(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
) -> InvoiceDecomposition | None:
    """Return the decomposition verdict when it disqualifies an M349 record.

    Scoped to Modelo 349 deliberately, and only after the clave is settled.

    Modelo 349 is the one invoice-sourced surface whose declared figure is
    conditioned on the declared IVA treatment: the clave is CHOSEN from
    :attr:`~cadrumo.domain.invoices.models.Invoice.iva_category`, and the base
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
    :class:`~cadrumo.domain.iva.schema.IvaCategory` member names an OSS operation at
    all -- the OSS axis is the regime and transaction kind -- so every
    legitimate OSS invoice would come back ungrounded, and that path already
    runs the coherence check that does apply to it, cross-checking the
    persisted cuota against the destination Member State's published rate.

    Within Modelo 349 the check is narrowed again, to the defects where the
    record CONTRADICTS ITSELF. Absence is deliberately not disqualifying, and
    the reason is structural: **an absent category does not mean the operation
    was inexpressible, it usually means the clave came from somewhere else.**
    :func:`~cadrumo.application.invoices.source_observations.intracommunity_clave` consults an explicit
    :attr:`~cadrumo.domain.invoices.models.Invoice.operation_type` FIRST and returns
    without ever reading ``iva_category``, so a record carrying a directly
    declared clave legitimately carries no category at all. Since this check
    runs only after the clave is settled, treating absence as disqualifying
    would drop exactly the records whose clave the operator stated most
    explicitly -- the least ambiguous rows in the store.

    That reasoning is deliberately independent of what the category enum
    happens to contain, because the previous justification was not and went
    stale. It asserted that an ordinary prestacion or adquisicion de servicios
    intracomunitaria "maps to no :class:`~cadrumo.domain.iva.schema.IvaCategory`
    member at all, because the enum names goods, acquisitions and triangulation
    but not services". The enum has since gained
    ``INTRA_COMMUNITY_SERVICE_SUPPLY`` and
    ``INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE``, and
    :func:`~cadrumo.application.invoices.source_observations.intracommunity_clave` maps both to their claves
    -- so the stated ground for weakening a filing-path guard was refuted
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
    if context.modelo != Modelo("349").value:
        return None
    verdict = decompose_invoice(invoice)
    contradictions = tuple(defect for defect in verdict.defects if defect in _M349_SELF_CONTRADICTION_DEFECTS)
    if not contradictions:
        return None
    return verdict.model_copy(update={"defects": contradictions})


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
        and invoice.iva_category == require_iva_category("intra_community_supply")
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
    if not any(invoice.iva_category == require_iva_category("import_third_country") for invoice in bucket_invoices):
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
            source_kind=invoice_source_kind(invoice),
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
            source_kind=invoice_source_kind(invoice),
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


def _invoice_provenance(
    invoice: Invoice,
    observation: InvoiceObservation,
    *,
    resolved_sources: frozenset[BindingSourceKind],
) -> tuple[CalculationSourceProvenance, ...]:
    """Attribute the selected binding families to their real directional invoice."""
    payload = observation.model_dump_json()
    source_kind = invoice_direction_to_source_kind(invoice.kind)
    families = tuple(
        family
        for family in OWNED_SOURCES
        if family in resolved_sources and (family is source_kind or family in COMBINED_DIRECTION_SOURCES)
    )
    source_ref = f"{source_kind}:{observation.invoice_id}"
    fingerprint = prefixed_digest(payload.encode("utf-8"))
    return tuple(
        CalculationSourceProvenance(
            resolver_id=InvoiceCatalogueSourceResolver.resolver_id,
            resolved_binding_source=family,
            contributor_source_kind=source_kind.value,
            contributor_binding_source=source_kind,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=source_ref if len(families) == 1 else f"{family}:{source_ref}",
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.INVOICE_CATALOGUE,
            fingerprint=fingerprint,
        )
        for family in families
    )
