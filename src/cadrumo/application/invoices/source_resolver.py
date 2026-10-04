"""Source-mesh resolver for governed invoice records.

:class:`InvoiceCatalogueSourceResolver` reads the
:class:`~domain.invoices.models.InvoiceCatalogue` supplied through its application-owned
read capability. It projects those records into the calculation mesh as
:class:`~application.aggregation.source_mesh.CalculationSourceResolution` values for
:attr:`~core.aggregation.BindingSourceKind.COLLECTIBLE_INVOICE`,
:attr:`~core.aggregation.BindingSourceKind.PAYABLE_INVOICE`, and the combined-direction
:attr:`~core.aggregation.BindingSourceKind.M347_THIRD_PARTY_OPERATION` and
:attr:`~core.aggregation.BindingSourceKind.M349_INTRACOMMUNITY_OPERATION`.

The :class:`~domain.invoices.models.Invoice` aggregate is the sole invoice record and
the reconciliation and link authority. Records reach the mesh only once they can
be represented as registry
:class:`~domain.calculations.registry.invoice_bindings.InvoiceObservation` facts, with summary
bindings, the repeated-record row bindings (the Modelo 347 declarado records),
Modelo 349 detail rows, transaction ids, and source provenance emitted through
one resolver envelope.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

from ...core.aggregation import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    IntracomOperationType,
    ThirdPartyDeclarationRole,
)
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import prefixed_digest
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    m347_declarable_set,
    m347_operation_clave,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from ...domain.calculations.registry.iva_category_catalogue import (
    IvaCategoryExclusion,
    require_iva_category,
    resolve_iva_category_catalogue,
)
from ...domain.calculations.registry.m347_operation_scope import resolve_m347_estimacion_objetiva_scope
from ...domain.calculations.registry.m347_threshold import M347DeclarableSet, M347ThresholdBucket
from ...domain.calculations.registry.third_party_declaration_roles import (
    resolve_third_party_declaration_role_catalogue,
)
from ...domain.calculations.registry.travel_agency_mediation import (
    is_travel_agency_air_passenger_transport,
)
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.invoices.business_premises import SITUACIONES_CON_REFERENCIA_CATASTRAL
from ...domain.invoices.decomposition import InvoiceDecomposition, InvoiceDecompositionDefect, decompose_invoice
from ...domain.invoices.enums import invoice_class_rectificativa, resolve_invoice_legal_mention
from ...domain.invoices.models import Invoice
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.establishment import SPAIN_COUNTRY_CODE
from ...domain.iva.flow import derive_flow_for_classification, is_inversion_sujeto_pasivo_flow
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.row_models import Modelo349OperadorRow, validate_m349_country_prefix_context
from ..aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..aggregation.source_resolution_operations import source_context_operation, storage_degradation_resolution
from .source_resolver_ports import InvoiceSourcePersistenceError, InvoiceSourceResolverPorts

_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (
    BindingSourceKind.COLLECTIBLE_INVOICE,
    BindingSourceKind.PAYABLE_INVOICE,
    BindingSourceKind.M347_THIRD_PARTY_OPERATION,
    BindingSourceKind.M349_INTRACOMMUNITY_OPERATION,
)
_COMBINED_DIRECTION_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.M347_THIRD_PARTY_OPERATION,
        BindingSourceKind.M349_INTRACOMMUNITY_OPERATION,
    },
)
_ObservedInvoice = tuple[Invoice, InvoiceObservation]
_IncoherentInvoice = tuple[Invoice, InvoiceDecomposition]
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
#: Values are :class:`~cadrumo.core.aggregation.IntracomOperationType` MEMBERS, never the
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
def _clave_by_kind_and_category() -> dict[tuple[InvoiceKind, IvaCategory], IntracomOperationType]:
    """Project the dated Modelo 349 category-to-clave bindings."""
    catalogue = resolve_iva_category_catalogue()
    return {
        (InvoiceKind.ISSUED, catalogue.require("intra_community_supply")): IntracomOperationType(
            catalogue.operation_type("issued.intra_community_supply")
        ),
        (InvoiceKind.ISSUED, catalogue.require("intra_community_service_supply")): IntracomOperationType(
            catalogue.operation_type("issued.intra_community_service_supply")
        ),
        (
            InvoiceKind.RECEIVED,
            catalogue.require("intra_community_service_acquisition_reverse_charge"),
        ): IntracomOperationType(
            catalogue.operation_type("received.intra_community_service_acquisition_reverse_charge")
        ),
        (
            InvoiceKind.RECEIVED,
            catalogue.require("intra_community_acquisition_reverse_charge"),
        ): IntracomOperationType(catalogue.operation_type("received.intra_community_acquisition_reverse_charge")),
    }


def invoice_direction_to_source_kind(kind: InvoiceKind) -> BindingSourceKind:
    """Map an invoice direction to its settlement source kind.

    The single contractual home for the direction<->settlement relationship,
    consumed by both :class:`InvoiceCatalogueSourceResolver` and the operator
    ``aeat app ledger invoice`` CLI. An *issued* invoice (we billed a customer)
    is *collectible*; a *received* invoice (a vendor billed us) is *payable*.

    Returns the canonical :class:`~core.aggregation.BindingSourceKind` member rather than a
    locally-declared direction enum: the settlement taxonomy has exactly one
    home per ``aeat-registry-bindings``.

    Returns:
        The :class:`BindingSourceKind` settling ``kind``.
    """
    if kind is InvoiceKind.ISSUED:
        return BindingSourceKind.COLLECTIBLE_INVOICE
    return BindingSourceKind.PAYABLE_INVOICE


def _invoice_sources_in_context(
    invoices: Iterable[Invoice],
    *,
    context: CalculationSourceContext,
    active_sources: frozenset[BindingSourceKind],
) -> tuple[Invoice, ...]:
    return tuple(
        invoice
        for invoice in invoices
        if _invoice_in_context(invoice, context) and _invoice_source_kind(invoice) in active_sources
    )


def _observe_invoice_sources(
    source_invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    m347_filer: _M347Filer,
) -> tuple[tuple[_ObservedInvoice, ...], tuple[_IncoherentInvoice, ...], tuple[Invoice, ...]]:
    observed_items: list[_ObservedInvoice] = []
    incoherent: list[_IncoherentInvoice] = []
    withheld_for_conversion: list[Invoice] = []
    for invoice in source_invoices:
        if _is_unconverted_foreign_invoice(invoice):
            withheld_for_conversion.append(invoice)
        observation = _invoice_observation(invoice, context=context, m347_filer=m347_filer)
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
    observed_items: tuple[_ObservedInvoice, ...],
    incoherent: tuple[_IncoherentInvoice, ...],
    withheld_for_conversion: tuple[Invoice, ...],
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    m347_filer: _M347Filer,
) -> CalculationSourceResolution:
    observations = tuple(observation for _, observation in observed_items)
    binding_values = resolve_invoice_binding_values(
        context.revision,
        observations,
        effective_date=_filing_period_date(context),
    )
    row_values = _invoice_row_values(context=context, observations=observations)
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
    diagnostics += _m347_role_fact_advisories(
        source_invoices,
        context=context,
        resolver_id=resolver_id,
        declaration_roles=m347_filer.declaration_roles,
    )
    diagnostics += _m347_declaration_advisories(
        observed_items,
        source_invoices,
        context=context,
        resolver_id=resolver_id,
    )
    diagnostics += _m347_exclusion_reading_advisories(observed_items, context=context, resolver_id=resolver_id)
    diagnostics += _m347_received_invoice_dating_advisories(
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
        row_binding_values=_row_values_not_carried_by_detail_rows(row_values),
        detail_rows=_m349_operador_rows_from_values(row_values),
        source_transaction_ids=tuple(
            sorted(
                {transaction_id for invoice, _ in observed_items for transaction_id in invoice.linked_transaction_ids},
            ),
        ),
        diagnostics=diagnostics,
        provenance=tuple(_invoice_provenance(invoice, observation) for invoice, observation in observed_items),
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
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = _OWNED_SOURCES

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
        active_sources = _invoice_sources_for_revision(context)
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
        m347_filer = _m347_filer(context)
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
    :func:`_intracommunity_clave` consults an explicit
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
    if context.modelo != Modelo("349").value:
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


def _m347_role_fact_advisories(
    invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
    declaration_roles: frozenset[ThirdPartyDeclarationRole],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on a Modelo 347 clave D/E fact left UNDECLARED, rather than silently deciding it.

    Fires only for a filer who actually carries a clave D or E role -- an
    empty role set (the overwhelming majority of filers) never triggers
    this, so the advisory is proportionate to the population the roles
    exist to cover, not every invoice everywhere. Scoped to RECEIVED
    invoices for clave D, matching the article's own "adquisiciones" text;
    clave E carries no direction restriction in the article, so every
    invoice from a public-administration filer is in scope.
    """
    if context.modelo != Modelo("347").value:
        return ()
    if not declaration_roles:
        return ()
    role_catalogue = resolve_third_party_declaration_role_catalogue()
    clave_d_eligible = bool(declaration_roles & role_catalogue.roles_for_clave("D"))
    clave_e_eligible = bool(declaration_roles & role_catalogue.roles_for_clave("E"))
    diagnostics: list[CalculationSourceDiagnostic] = []
    for invoice in invoices:
        if clave_d_eligible and invoice.kind is InvoiceKind.RECEIVED and invoice.outside_economic_activity is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="unclassified_declarant_role_fact",
                    source_kind=str(_invoice_source_kind(invoice)),
                    resolver_id=resolver_id,
                    source_ref=f"invoice:{invoice.invoice_id}",
                    message=(
                        f"invoice {invoice.invoice_number!r} is an acquisition from a filer carrying a "
                        "Modelo 347 clave D role, but whether it is al margen de la actividad "
                        "empresarial is undeclared, so it is NOT classified as clave D"
                    ),
                    remedy="Declare outside_economic_activity on this invoice, then recalculate",
                ),
            )
        if clave_e_eligible and invoice.is_subvencion_ayuda is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="unclassified_declarant_role_fact",
                    source_kind=str(_invoice_source_kind(invoice)),
                    resolver_id=resolver_id,
                    source_ref=f"invoice:{invoice.invoice_id}",
                    message=(
                        f"invoice {invoice.invoice_number!r} is from a filer carrying the Modelo 347 "
                        "public-administration role, but whether it is a subvención, auxilio or ayuda "
                        "is undeclared, so it is NOT classified as clave E"
                    ),
                    remedy="Declare is_subvencion_ayuda on this invoice, then recalculate",
                ),
            )
    return tuple(diagnostics)


#: The provision every Modelo 347 declaration-floor reading is a claim about.
_M347_THRESHOLD_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-33",)
#: Art. 33.2.g, "Las importaciones y exportaciones de mercancías": the letter an
#: unsettled category exclusion is a claim about.
_M347_GOODS_EXCLUSION_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-33.2.g",)
#: Art. 33.2.i (operations already in a coincident periodic declaration), the
#: payer's annual withholding summary it points at (RIRPF art. 108.2), and art.
#: 34.1.d, which has the landlord of business premises relate the lease all the same.
#: Art. 34.4: the annual total is declared "neto de las devoluciones, descuentos y
#: bonificaciones concedidos y de las operaciones que queden sin efecto en el mismo
#: año natural", read with art. 33's floor whenever that net is nil or negative.
_M347_NET_TOTAL_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-33", "rd-1065-2007:art-34.4")
_M347_WITHHELD_ISSUED_LEGAL_REFS: tuple[str, ...] = (
    "rd-1065-2007:art-33.2.i",
    "rd-1065-2007:art-34.1.d",
    "rd-439-2007:art-108",
)


def _m347_observed_items(observed_items: Sequence[_ObservedInvoice]) -> tuple[_ObservedInvoice, ...]:
    return tuple(
        (invoice, observation) for invoice, observation in observed_items if observation.operation_clave is not None
    )


def _m347_threshold_bucket_numbers(
    bucket: M347ThresholdBucket,
    m347_items: Sequence[_ObservedInvoice],
) -> list[str]:
    return sorted(
        invoice.invoice_number for invoice, observation in m347_items if observation.operation_clave in bucket.claves
    )


def _m347_threshold_bucket_advisory(
    bucket: M347ThresholdBucket,
    m347_items: Sequence[_ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> CalculationSourceDiagnostic | None:
    if not bucket.reading_unsettled:
        return None
    numbers = _m347_threshold_bucket_numbers(bucket, m347_items)
    if not numbers:
        return None
    rule = "whatever their amount" if bucket.floor is None else f"against a {bucket.floor} EUR floor"
    return CalculationSourceDiagnostic(
        reason="unsettled_legal_reading",
        source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
        resolver_id=resolver_id,
        source_ref=f"m347-threshold-bucket:{bucket.token}",
        message=(
            f"Modelo 347 clave {', '.join(sorted(bucket.claves))} operations ({', '.join(numbers)}) are "
            f"judged in their own declaration bucket {bucket.token!r} {rule} for ejercicio "
            f"{context.filing_year}. The registry marks that reading of RD 1065/2007 art. 33 as "
            "unsettled, so the declarado records follow it and AEAT may read the provision differently."
        ),
        remedy=(
            "Check these operations against current AEAT guidance for this ejercicio before filing; "
            "the declarado records shown follow the registry's reading."
        ),
        asserted_legal_refs=_M347_THRESHOLD_LEGAL_REFS,
    )


def _m347_unsettled_bucket_advisories(
    declarable: M347DeclarableSet,
    m347_items: Sequence[_ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    diagnostics: list[CalculationSourceDiagnostic] = []
    for bucket in declarable.buckets.buckets:
        advisory = _m347_threshold_bucket_advisory(
            bucket,
            m347_items,
            context=context,
            resolver_id=resolver_id,
        )
        if advisory is not None:
            diagnostics.append(advisory)
    return tuple(diagnostics)


def _m347_nonpositive_total_advisory(
    declarable: M347DeclarableSet,
    m347_items: Sequence[_ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> CalculationSourceDiagnostic | None:
    nonpositive = sorted(
        invoice.invoice_number
        for invoice, observation in m347_items
        if observation.operation_clave is not None
        and declarable.admits_unconditional_nonpositive(observation.party_tax_id, observation.operation_clave)
    )
    if not nonpositive:
        return None
    return CalculationSourceDiagnostic(
        reason="unsettled_legal_reading",
        source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
        resolver_id=resolver_id,
        source_ref="m347-threshold-bucket:nonpositive-total",
        message=(
            f"Modelo 347 operations ({', '.join(nonpositive)}) net to zero or less for their "
            "counterparty in a bucket related whatever its amount, so they are declared at that total "
            f"for ejercicio {context.filing_year}. Whether a nil or negative annual total belongs on "
            "the declaration is not settled."
        ),
        remedy=(
            "Check the rectifications and returns behind these totals; keep the record only if the "
            "operations still have to be related for this ejercicio."
        ),
        asserted_legal_refs=_M347_NET_TOTAL_LEGAL_REFS,
    )


def _m347_floored_nonpositive_total_advisory(
    declarable: M347DeclarableSet,
    m347_items: Sequence[_ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> CalculationSourceDiagnostic | None:
    """Name the counterparties a floored bucket leaves out because their net total is nil or negative.

    Art. 33.1 relates a party whose operations "hayan superado" the floor, and
    a total netted to nothing or below by its rectifications (art. 34.4) never
    exceeds it, so no record is emitted. The record design nonetheless carries
    an "N" sign for a negative annual amount and no text in the corpus says
    whether such a party must still be related, so the omission is disclosed.
    """
    left_out = sorted(
        invoice.invoice_number
        for invoice, observation in m347_items
        if observation.operation_clave is not None
        and declarable.leaves_out_floored_nonpositive(observation.party_tax_id, observation.operation_clave)
    )
    if not left_out:
        return None
    return CalculationSourceDiagnostic(
        reason="unsettled_legal_reading",
        source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
        resolver_id=resolver_id,
        source_ref="m347-threshold-bucket:nonpositive-total-left-out",
        message=(
            f"Modelo 347 operations ({', '.join(left_out)}) net to zero or less for their counterparty once "
            "the rectifications are netted (RD 1065/2007 art. 34.4), so no record is declared for ejercicio "
            f"{context.filing_year}: art. 33.1 relates a party only above its floor. Whether a negative annual "
            "total must still be related, as the record's N sign allows, is not settled."
        ),
        remedy=(
            "Check whether these counterparties must still appear with a negative annual amount before filing; "
            "the declaration shown leaves them out."
        ),
        asserted_legal_refs=_M347_NET_TOTAL_LEGAL_REFS,
    )


def _m347_rectificativa_netting_advisory(
    m347_items: Sequence[_ObservedInvoice],
    source_invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> CalculationSourceDiagnostic | None:
    """Name the rectificativas netted as reductions, and those whose rectified invoice is not in this ejercicio.

    The invoice stores a correction as a non-negative amount and its class, not
    the direction of the correction, so every rectificativa nets as a reduction
    of the amount it states. A rectificativa that raises the price, or replaces
    the original in full, would net the wrong way, and one rectifying an
    invoice not related in this ejercicio reduces this year's total although
    art. 34.4 speaks of operations "en el mismo año natural".
    """
    rectificativas = [invoice for invoice, _observation in m347_items if _is_rectificativa(invoice)]
    if not rectificativas:
        return None
    related = {(invoice.kind, invoice.counterparty_tax_id, invoice.invoice_number) for invoice in source_invoices}
    outside = sorted(
        invoice.invoice_number
        for invoice in rectificativas
        if (invoice.kind, invoice.counterparty_tax_id, invoice.rectifies_invoice_number) not in related
    )
    message = (
        f"Modelo 347 nets the rectificativas {', '.join(sorted(item.invoice_number for item in rectificativas))} "
        "as reductions of their counterparty's total for ejercicio "
        f"{context.filing_year} (RD 1065/2007 art. 34.4). Each records its amount but not whether it lowers "
        "the price, so one that raises it or replaces the original in full nets the wrong way."
    )
    if outside:
        message += (
            f" {', '.join(outside)} rectify an invoice not related in this ejercicio, and art. 34.4 nets "
            "operations of the same año natural."
        )
    return CalculationSourceDiagnostic(
        reason="unsettled_legal_reading",
        source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
        resolver_id=resolver_id,
        source_ref="m347-rectificativa:netted-as-reduction",
        message=message,
        remedy=(
            "Check each listed rectificativa: one that raises the price, replaces the original in full or "
            "corrects an earlier ejercicio needs its counterparty's declarado amount corrected before filing."
        ),
        asserted_legal_refs=("rd-1065-2007:art-34.4",),
    )


def _m347_declaration_advisories(
    observed_items: Sequence[_ObservedInvoice],
    source_invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Disclose the Modelo 347 declaration-floor readings the registry leaves unsettled, and the record gaps.

    The declarable set is the one the row family and the declarante summary
    use (:func:`~cadrumo.domain.calculations.registry.invoice_bindings.m347_declarable_set`),
    read at the same filing-period date, so what is disclosed is exactly what
    was declared. Each case is one advisory per calculation rather than one
    per invoice:

    - a threshold bucket the registry flags ``reading_unsettled`` holds
      operations: the clave D bucket kept apart from the ordinary
      adquisiciones (art. 33.3 neither joins nor separates them), or clave E
      related whatever its amount while the record design still in use states
      a floor;
    - a bucket with no floor admits a counterparty whose net total is zero or
      negative, which the bucket declares but whose place on the declaration
      no rule settles;
    - a bucket with a floor leaves out a counterparty whose rectifications net
      its total to zero or below, which the floor does not relate although the
      record's sign field could carry it;
    - rectificativas are netted as reductions of the amount they state, a
      direction the invoice record does not carry.

    The operations follow the registry's reading; the advisory says which ones
    rest on it. The record fields the declared operations need but the invoice
    records cannot fill are disclosed by :func:`_m347_record_field_advisories`
    over the same declarable set, and the inmueble record fields the leases
    leave open by :func:`_m347_inmueble_record_advisories`.
    """
    if context.modelo != Modelo("347").value:
        return ()
    m347_items = _m347_observed_items(observed_items)
    if not m347_items:
        return ()
    declarable = m347_declarable_set(
        tuple(observation for _, observation in m347_items),
        effective_date=_filing_period_date(context),
    )
    diagnostics = list(
        _m347_unsettled_bucket_advisories(
            declarable,
            m347_items,
            context=context,
            resolver_id=resolver_id,
        ),
    )
    nonpositive_advisory = _m347_nonpositive_total_advisory(
        declarable,
        m347_items,
        context=context,
        resolver_id=resolver_id,
    )
    if nonpositive_advisory is not None:
        diagnostics.append(nonpositive_advisory)
    left_out_advisory = _m347_floored_nonpositive_total_advisory(
        declarable,
        m347_items,
        context=context,
        resolver_id=resolver_id,
    )
    if left_out_advisory is not None:
        diagnostics.append(left_out_advisory)
    netting_advisory = _m347_rectificativa_netting_advisory(
        m347_items,
        source_invoices,
        context=context,
        resolver_id=resolver_id,
    )
    if netting_advisory is not None:
        diagnostics.append(netting_advisory)
    diagnostics.extend(
        _m347_record_field_advisories(
            declarable,
            m347_items,
            context=context,
            resolver_id=resolver_id,
        ),
    )
    diagnostics.extend(_m347_inmueble_record_advisories(m347_items, context=context, resolver_id=resolver_id))
    return tuple(diagnostics)


def _m347_declared_items(
    declarable: M347DeclarableSet,
    m347_items: Sequence[_ObservedInvoice],
) -> tuple[_ObservedInvoice, ...]:
    return tuple(
        (invoice, observation)
        for invoice, observation in m347_items
        if observation.operation_clave is not None
        and declarable.admits(observation.party_tax_id, observation.operation_clave)
    )


def _m347_record_field_advisories(
    declarable: M347DeclarableSet,
    m347_items: Sequence[_ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name the declarado record fields the declared operations need but the invoices cannot fill.

    Three gaps, each one advisory per calculation and only for operations that
    are actually declared:

    - a criterio de caja record must also carry the amount devengado in the
      year under LIVA art. 163 terdecies (2025 design pos. 284-299), which
      turns on the collection and payment dates the invoice does not record;
    - a Spanish declarado's CÓDIGO PROVINCIA (pos. 77-78) is that of its
      domicilio fiscal, which the invoice holds only inside free-text addresses;
    - the amounts above 6.000 EUR received in cash from a declarado (art.
      34.1.h, pos. 101-115) need a cash-collection fact no invoice carries.
    """
    declared = _m347_declared_items(declarable, m347_items)
    diagnostics: list[CalculationSourceDiagnostic] = []
    cash_accounting = sorted(
        invoice.invoice_number for invoice, observation in declared if observation.cash_accounting_operation
    )
    if cash_accounting:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="missing_transaction_evidence",
                source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
                resolver_id=resolver_id,
                source_ref="m347-record:criterio-caja-devengo",
                message=(
                    f"Modelo 347 relates the criterio de caja operations on invoices {', '.join(cash_accounting)} "
                    f"in their own records for ejercicio {context.filing_year}, marked and without quarterly "
                    "amounts. Each record must also carry the amount devengado in the year under LIVA art. 163 "
                    "terdecies, which depends on collection and payment dates the invoices do not record, so "
                    "that amount is left without content."
                ),
                remedy=(
                    "Enter the art. 163 terdecies amount of each criterio de caja record on the AEAT form "
                    "before filing; Cadrumo cannot derive it from the invoices."
                ),
                asserted_legal_refs=("rd-1065-2007:art-34.1.j", "ley-37-1992:art-163-terdecies"),
            ),
        )
    without_provincia = sorted(
        {
            observation.party_tax_id
            for _invoice, observation in declared
            if observation.country_code == SPAIN_COUNTRY_CODE
        },
    )
    if without_provincia:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
                resolver_id=resolver_id,
                source_ref="m347-record:provincia-not-recorded",
                message=(
                    f"Modelo 347 declares the Spanish counterparties {', '.join(without_provincia)} for ejercicio "
                    f"{context.filing_year}, but each record's provincia code is that of the counterparty's "
                    "domicilio fiscal, which the invoices hold only as free-text addresses, so it is left "
                    "without content."
                ),
                remedy="Complete the provincia code of each listed counterparty on the AEAT form before filing.",
            ),
        )
    if any(invoice.kind is InvoiceKind.ISSUED for invoice, _observation in declared):
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
                resolver_id=resolver_id,
                source_ref="m347-record:metalico-not-recorded",
                message=(
                    f"Modelo 347 declares sales for ejercicio {context.filing_year}, and the amounts above "
                    "6.000 EUR received in cash from a declarado belong on its record (RD 1065/2007 art. 34.1.h). "
                    "The invoices do not record how they were collected, so no cash amount is declared."
                ),
                remedy=(
                    "If you received more than 6.000 EUR in cash from any declarado this year, enter that amount "
                    "on its record on the AEAT form before filing."
                ),
                asserted_legal_refs=("rd-1065-2007:art-34.1.h",),
            ),
        )
    return tuple(diagnostics)


_M347_INMUEBLE_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-34.1.d",)


def _m347_inmueble_record_advisories(
    m347_items: Sequence[_ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name the inmueble record fields the recorded business-premises leases leave open.

    RD 1065/2007 art. 34.1.d has the landlord consign, for each lease, "las
    referencias catastrales y los datos necesarios para la localización de los
    inmuebles arrendados", and the inmueble record is related whatever its
    amount, so every lease invoice reaches one. One advisory per gap:

    - a lease that records no SITUACIÓN DEL INMUEBLE (pos. 115), which the
      record needs to say where the premises is;
    - a lease whose situación is 1 or 2 but records no REFERENCIA CATASTRAL
      (pos. 116): code 3 is the one for "cualquiera de las situaciones
      anteriores pero sin referencia catastral";
    - the DIRECCIÓN DEL INMUEBLE (pos. 141-333), whose INE-coded street, number
      and municipality fields no invoice records, so it is left without content
      on every inmueble record.
    """
    leases = [invoice for invoice, _observation in m347_items if invoice.business_premises_lease is not None]
    if not leases:
        return ()
    without_situacion = sorted(
        invoice.invoice_number
        for invoice in leases
        if invoice.business_premises_lease is not None and invoice.business_premises_lease.situacion_inmueble is None
    )
    without_referencia = sorted(
        invoice.invoice_number
        for invoice in leases
        if (
            invoice.business_premises_lease is not None
            and invoice.business_premises_lease.situacion_inmueble in SITUACIONES_CON_REFERENCIA_CATASTRAL
            and invoice.business_premises_lease.referencia_catastral is None
        )
    )
    diagnostics: list[CalculationSourceDiagnostic] = []
    if without_situacion:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
                resolver_id=resolver_id,
                source_ref="m347-inmueble:situacion-not-recorded",
                message=(
                    f"Modelo 347 relates the business-premises leases on invoices {', '.join(without_situacion)} "
                    f"in inmueble records for ejercicio {context.filing_year}, but they record no situación del "
                    "inmueble, which RD 1065/2007 art. 34.1.d needs to locate each leased premises."
                ),
                remedy="Record the situación del inmueble (1 to 4) on each listed invoice, then recalculate.",
                asserted_legal_refs=_M347_INMUEBLE_LEGAL_REFS,
            ),
        )
    if without_referencia:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
                resolver_id=resolver_id,
                source_ref="m347-inmueble:referencia-catastral-not-recorded",
                message=(
                    f"Modelo 347 relates the business-premises leases on invoices {', '.join(without_referencia)} "
                    f"for ejercicio {context.filing_year} with a situación that carries a referencia catastral, "
                    "but they record none, and RD 1065/2007 art. 34.1.d has the landlord consign it."
                ),
                remedy=(
                    "Record the referencia catastral of each listed premises, or situación 3 if it has none, "
                    "then recalculate."
                ),
                asserted_legal_refs=_M347_INMUEBLE_LEGAL_REFS,
            ),
        )
    diagnostics.append(
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
            resolver_id=resolver_id,
            source_ref="m347-inmueble:direccion-not-recorded",
            message=(
                f"Modelo 347 relates business-premises leases in inmueble records for ejercicio "
                f"{context.filing_year} ({', '.join(sorted(invoice.invoice_number for invoice in leases))}). Each "
                "record's dirección del inmueble needs the INE-coded street, number and municipality, which the "
                "invoices do not record, so it is left without content."
            ),
            remedy="Complete the dirección of each inmueble record on the AEAT form before filing.",
            asserted_legal_refs=_M347_INMUEBLE_LEGAL_REFS,
        ),
    )
    return tuple(diagnostics)


def _m347_unsettled_exclusion_invoice_numbers(declared: Sequence[Invoice], *, effective_date: date) -> list[str]:
    return sorted(
        invoice.invoice_number
        for invoice in declared
        if _m347_category_exclusion(invoice, effective_date=effective_date) is IvaCategoryExclusion.UNSETTLED
    )


def _m347_withheld_issued_invoice_numbers(declared: Sequence[Invoice]) -> list[str]:
    """The issued invoices with a withholding whose place on the declaration no text settles.

    A business-premises lease is not among them: art. 34.1.d has the landlord
    relate it, withheld or not, and the invoice records that it is one.
    """
    return sorted(
        invoice.invoice_number
        for invoice in declared
        if invoice.kind is InvoiceKind.ISSUED
        and _carries_withholding(invoice)
        and invoice.business_premises_lease is None
    )


def _m347_exclusion_reading_advisories(
    observed_items: Sequence[_ObservedInvoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Disclose the declared Modelo 347 operations whose art. 33.2 exclusion is arguable.

    The counterpart of the exclusions :func:`_m347_invoice_observation`
    applies: what the text settles is excluded there; what it leaves open is
    declared and named here, one advisory per case rather than one per
    invoice. The two open cases are an IVA category the catalogue marks
    ``unsettled`` for Modelo 347 (an operation assimilated to an export, goods
    or services by its facts), and an ISSUED invoice on which the customer
    practised a withholding, which the customer reports but whose exclusion
    from the withheld party's own declaration no text in the corpus states.
    A landlord of business premises is the exception the text does settle:
    art. 34.1.d has it relate the lease, withheld or not, so an invoice that
    records the lease is declared without an advisory.
    """
    if context.modelo != Modelo("347").value:
        return ()
    declared = tuple(invoice for invoice, observation in observed_items if observation.operation_clave is not None)
    unsettled = _m347_unsettled_exclusion_invoice_numbers(declared, effective_date=_filing_period_date(context))
    withheld = _m347_withheld_issued_invoice_numbers(declared)
    diagnostics: list[CalculationSourceDiagnostic] = []
    if unsettled:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unsettled_legal_reading",
                source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
                resolver_id=resolver_id,
                source_ref="m347-exclusion:iva-category",
                message=(
                    f"Modelo 347 declares the operations on invoices {', '.join(unsettled)}, whose IVA category "
                    "the registry marks as an unsettled exclusion under RD 1065/2007 art. 33.2: letter g "
                    "excludes the imports and exports of goods, and the category does not say whether these "
                    f"operations are goods, so they are declared for ejercicio {context.filing_year}."
                ),
                remedy=(
                    "Check whether these operations are imports or exports of goods; if they are, record the "
                    "export or import category on the invoice so Modelo 347 leaves them out."
                ),
                asserted_legal_refs=_M347_GOODS_EXCLUSION_LEGAL_REFS,
            ),
        )
    if withheld:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unsettled_legal_reading",
                source_kind=BindingSourceKind.M347_THIRD_PARTY_OPERATION.value,
                resolver_id=resolver_id,
                source_ref="m347-exclusion:withheld-issued-invoice",
                message=(
                    f"Modelo 347 declares the issued invoices {', '.join(withheld)}, on which the customer "
                    "practised a withholding, for ejercicio "
                    f"{context.filing_year}. RD 1065/2007 art. 33.2.i excludes what the customer reports in "
                    "its withholding summary (RIRPF art. 108.2), but no text settles whether that reaches "
                    "your side. None of them records a business-premises lease, which art. 34.1.d would "
                    "have you relate all the same."
                ),
                remedy=(
                    "Mark any of these invoices that documents the lease of a local de negocio as such; for "
                    "the rest, check current AEAT guidance before filing. The declarado records shown include "
                    "them all."
                ),
                asserted_legal_refs=_M347_WITHHELD_ISSUED_LEGAL_REFS,
            ),
        )
    return tuple(diagnostics)


#: RD 1065/2007 art. 35.1 dates a Modelo 347 operation by the registry entry of its invoice, and RIVA
#: art. 69.3 sets when a received invoice is entered.
_M347_RECEIVED_DATING_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-35", "rd-1624-1992:art-69")
#: The last monthly period of an ejercicio, the shortest IVA liquidation period.
_LAST_MONTH_CODE = "12"


def _m347_received_invoice_dating_advisories(
    observed_items: Sequence[_ObservedInvoice],
    catalogue_invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
    m347_filer: _M347Filer,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name the received invoices whose ejercicio the issue date may not decide.

    RD 1065/2007 art. 35.1: "las operaciones se entenderán producidas en el
    período en el que, de acuerdo con lo previsto en el artículo 69 del
    Reglamento del Impuesto sobre el Valor Añadido, se debe realizar la
    anotación registral de la factura o documento contable que sirva de
    justificante de las mismas". RIVA art. 69.3 enters a received invoice "por
    el orden en que se reciban, y dentro del período de liquidación en que
    proceda efectuar su deducción", so its ejercicio follows its reception and
    deduction, which the invoice does not record: it carries only the issue
    date the resolver dates it by. Which ejercicio such an invoice belongs to
    therefore cannot be decided here.

    The case is disclosed where it can change the ejercicio: a received
    invoice issued in the last month of the year, the shortest liquidation
    period, may be received and entered only in the next year. That covers the
    invoices of this ejercicio's last month, declared here, and those of the
    previous ejercicio's last month that this declaration would otherwise
    relate, which it leaves out.
    """
    if context.modelo != Modelo("347").value:
        return ()
    last_month = Period.from_year_and_code(context.filing_year, _LAST_MONTH_CODE)
    previous_last_month = Period.from_year_and_code(context.filing_year - 1, _LAST_MONTH_CODE)
    declared = sorted(
        invoice.invoice_number
        for invoice, observation in observed_items
        if observation.operation_clave is not None
        and invoice.kind is InvoiceKind.RECEIVED
        and last_month.contains(invoice.issued_at)
    )
    left_out = sorted(
        invoice.invoice_number
        for invoice in catalogue_invoices
        if invoice.kind is InvoiceKind.RECEIVED
        and (invoice.bucket_id is None or invoice.bucket_id == context.bucket_id)
        and previous_last_month.contains(invoice.issued_at)
        and _invoice_observation(invoice, context=context, m347_filer=m347_filer) is not None
    )
    if not declared and not left_out:
        return ()
    parts: list[str] = []
    if declared:
        parts.append(f"declares the received invoices {', '.join(declared)} issued in December")
    if left_out:
        parts.append(
            f"leaves out the received invoices {', '.join(left_out)} issued in December {context.filing_year - 1}"
        )
    return (
        CalculationSourceDiagnostic(
            reason="unsettled_legal_reading",
            source_kind=BindingSourceKind.PAYABLE_INVOICE.value,
            resolver_id=resolver_id,
            source_ref="m347-dating:received-invoice-registry-entry",
            message=(
                f"Modelo 347 for ejercicio {context.filing_year} {' and '.join(parts)}, dating each by its issue "
                "date. RD 1065/2007 art. 35.1 dates an operation by the entry of its invoice in the libro registro, "
                "made when it is received (RIVA art. 69.3), and the invoices do not record when they were received."
            ),
            remedy=(
                "Check when each listed invoice was received and entered in your libro registro de facturas "
                "recibidas; one entered in another year belongs to that year's Modelo 347."
            ),
            asserted_legal_refs=_M347_RECEIVED_DATING_LEGAL_REFS,
        ),
    )


def _invoice_sources_for_revision(context: CalculationSourceContext) -> frozenset[BindingSourceKind]:
    declared_sources = frozenset(
        binding.source for binding in context.revision.bindings if binding.source in _OWNED_SOURCES
    )
    if declared_sources & _COMBINED_DIRECTION_SOURCES:
        # A combined-direction binding reads both invoice directions, so both feed it.
        return frozenset(_OWNED_SOURCES)
    return declared_sources


def _invoice_in_context(invoice: Invoice, context: CalculationSourceContext) -> bool:
    """Whether this invoice is declarable for the context's bucket and period.

    Only a POPULATED, mismatching bucket excludes. An unattributed invoice
    belongs to the store it was loaded from, and that store is opened against
    ``context.bucket_id`` -- with the composed catalogue reader refusing a
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


def _filing_period_date(context: CalculationSourceContext) -> date:
    """The one date every dated registry read of this resolver is made as of: the period's last day.

    The threshold buckets, the category exclusion keys, the art. 32.b scope and
    the filer's profile facts all read the same coordinate, so a fact that
    changes inside the year cannot reach one consumer and miss another.
    """
    return context.period.end_date


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


def _invoice_observation(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
    m347_filer: _M347Filer,
) -> InvoiceObservation | None:
    if _is_unconverted_foreign_invoice(invoice):
        return None
    if invoice.counterparty_tax_id is None:
        # M347/M349 both declare a third party by their tax id; a factura
        # simplificada legitimately carries none (RD 1619/2012 art. 6.1.d), so
        # it has nothing these informativas can declare rather than a defect.
        return None
    if context.modelo == Modelo("347").value:
        return _m347_invoice_observation(
            invoice,
            m347_filer=m347_filer,
            effective_date=_filing_period_date(context),
        )
    clave = _intracommunity_clave(invoice)
    if clave is None:
        return None
    if context.modelo == Modelo("349").value:
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


@dataclass(frozen=True, slots=True)
class _M347Filer:
    """The filer facts Modelo 347 classification reads, resolved once per calculation context.

    ``declared_invoice_kinds`` is ``None`` when RD 1065/2007 art. 32.b does
    not scope the filer, so every invoice direction is related; otherwise it
    is the set the ``m347-estimacion-objetiva-operation-scope`` fact keeps for
    the filer's IRPF estimation and IVA regimes. ``annual_computation_basis``
    is true for the filers RD 1065/2007 art. 33.1 has report "sobre una base de
    cómputo anual": those under the régimen especial del criterio de caja and
    the propiedad horizontal entities.
    """

    declaration_roles: frozenset[ThirdPartyDeclarationRole] = frozenset()
    declared_invoice_kinds: frozenset[InvoiceKind] | None = None
    annual_computation_basis: bool = False

    def relates(self, kind: InvoiceKind) -> bool:
        """Whether an invoice of this direction is related for this filer."""
        return self.declared_invoice_kinds is None or kind in self.declared_invoice_kinds


_UNSCOPED_M347_FILER = _M347Filer()


def _m347_filer(context: CalculationSourceContext) -> _M347Filer:
    """Read the filer's Modelo 347 roles and art. 32.b scope once for ``context``.

    The profile is the one the calculation pinned (``context.profile``), read
    through the context's own authority lease, and projected as of the last day
    of the filing period, so a role or regime recorded for a later window does
    not reach back into an earlier ejercicio. Only a context built outside a
    calculation command loads the profile itself, once, through the same
    :func:`~cadrumo.application.modelo.profile_readiness_gate.load_modelo_work_profile`
    every modelo calculation uses (the invocation's pinned record first, then
    the store). A missing profile
    fails closed to no roles and no scoping, because the overwhelming majority
    of filers legitimately carry no role and an unscoped filer relates every
    operation: claves C, D and E simply do not classify, and nothing is left
    out that art. 32.b has not been shown to exclude.
    """
    if context.modelo != Modelo("347").value:
        return _UNSCOPED_M347_FILER
    from ..modelo.profile_readiness_gate import load_modelo_work_profile
    from ..user_profile.projections import projection_for_taxpayer

    as_of = _filing_period_date(context)
    with source_context_operation(context) as operation:
        profile = context.profile or load_modelo_work_profile(
            bucket_id=context.bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
        if profile is None:
            return _UNSCOPED_M347_FILER
        taxpayer = projection_for_taxpayer(
            profile.record,
            schema=profile.profile_decode_context.schema,
            as_of=as_of,
        )
        annual_computation_basis = _m347_files_on_an_annual_basis(taxpayer)
        if taxpayer.irpf_estimation_regime is None:
            # Art. 32.b concerns activities taxed by an IRPF estimation method;
            # a filer that declares none is outside it and relates every invoice.
            return _M347Filer(
                declaration_roles=taxpayer.declaration_roles,
                annual_computation_basis=annual_computation_basis,
            )
        scope = resolve_m347_estimacion_objetiva_scope(effective_date=as_of, authority=operation)
    return _M347Filer(
        declaration_roles=taxpayer.declaration_roles,
        declared_invoice_kinds=scope.invoice_kinds_for(
            irpf_estimation_regime=taxpayer.irpf_estimation_regime,
            iva_regime=taxpayer.iva_regime,
        ),
        annual_computation_basis=annual_computation_basis,
    )


def _m347_files_on_an_annual_basis(taxpayer: TaxpayerProfile) -> bool:
    """Whether RD 1065/2007 art. 33.1 has this filer report every operation on an annual basis.

    "Como excepción a lo dispuesto en el segundo párrafo de este apartado, los
    sujetos pasivos que realicen operaciones a las que sea de aplicación el
    régimen especial del criterio de caja ... y, las entidades a las que sea de
    aplicación la Ley 49/1960, de 21 de junio sobre la propiedad horizontal,
    suministrarán toda la información que vengan obligados a relacionar en su
    declaración anual, sobre una base de cómputo anual."
    """
    propiedad_horizontal = resolve_third_party_declaration_role_catalogue().require("propiedad_horizontal_entity")
    criterio_de_caja = taxpayer.iva is not None and taxpayer.iva.cash_accounting_regime_enrolled
    return criterio_de_caja or propiedad_horizontal in taxpayer.declaration_roles


def _m347_category_exclusion(invoice: Invoice, *, effective_date: date) -> IvaCategoryExclusion | None:
    """How Modelo 347 treats this invoice's IVA category, per the catalogue's dated exclusion keys."""
    if invoice.iva_category is None:
        return None
    return resolve_iva_category_catalogue(effective_date=effective_date).exclusion(Modelo("347"), invoice.iva_category)


def _carries_withholding(invoice: Invoice) -> bool:
    """Whether the invoice records an IRPF withholding actually practised on it."""
    return invoice.retention_amount is not None and invoice.retention_amount > 0


def _m347_invoice_observation(
    invoice: Invoice,
    *,
    m347_filer: _M347Filer,
    effective_date: date,
) -> InvoiceObservation | None:
    """Build the M347 observation for one invoice, or ``None`` if excluded.

    This is the single point where RD 1065/2007 art. 33.2 excludes an
    operation. Declares a counterparty regardless of residency: art. 33.2 is a
    CLOSED exclusion list, and a counterparty's non-residency is not one of
    its nine enumerated items. The diseño de registro's own `pais-codigo`
    field (a "XX" alphabetic slot for a non-established non-resident
    declarado) is direct evidence AEAT expects some M347 counterparties to be
    non-resident. What the list excludes, it excludes by the operation:

    - art. 33.2.i), an operation already reported through a coincident
      periodic informativa: for an invoice, Modelo 349's intracommunity
      recapitulativa, so an operation `_intracommunity_clave` classifies as
      intracommunity routes to M349 instead -- the same classification M349's
      own branch of this resolver uses, never a bare country comparison;
    - art. 33.2.g), "Las importaciones y exportaciones de mercancías", read
      off the IVA category catalogue's Modelo 347 exclusion keys so that the
      goods exports and imports drop out while services with a non-resident
      stay declared; a category the catalogue marks unsettled stays declared
      and is disclosed by :func:`_m347_exclusion_reading_advisories`;
    - art. 33.2.i) again for a RECEIVED invoice carrying a withholding: the
      payer declares it in the "declaración anual de las retenciones e
      ingresos a cuenta efectuados" of RIRPF art. 108.2, a periodic
      information duty of coincident content. The withheld party's own side
      has no such declaration of its own, so an ISSUED invoice with a
      withholding stays declared and is disclosed instead.

    Letters c, e, f and h turn on facts the invoice does not carry (a
    gratuitous title, stamps or postage, the social entity's exempt sector,
    a shipment to or from Canarias, Ceuta or Melilla), so nothing here
    decides them. Art. 32.b scopes the operations of an estimación objetiva
    filer under a special IVA regime to the invoices it issues (plus, under
    the régimen simplificado, the received invoices of its libro registro);
    ``m347_filer`` carries that scope, read once for the calculation.

    Clave C additionally needs the filer's own
    :class:`ThirdPartyDeclarationRole` membership, carried by ``m347_filer``.
    When the invoice IS a clave-C collection
    (``collected_on_behalf_of_tax_id`` set AND the filer carries the
    registry-selected collector role), the declared counterparty is the
    BENEFICIARY whose fees were collected (RD 1065/2007 art. 34.g), not
    whoever actually paid this invoice -- so ``party_tax_id`` and
    ``party_legal_name`` are substituted, not merely the clave.
    """
    if _intracommunity_clave(invoice) is not None:
        return None
    if _m347_category_exclusion(invoice, effective_date=effective_date) is IvaCategoryExclusion.EXCLUDED:
        return None
    if invoice.kind is InvoiceKind.RECEIVED and _carries_withholding(invoice):
        return None
    if not m347_filer.relates(invoice.kind):
        return None
    if invoice.counterparty_tax_id is None:
        # Same reason as the general builder above: M347 declares a third party
        # by their tax id, and a factura simplificada legitimately carries none
        # (RD 1619/2012 art. 6.1.d). Without this the row reached the observation
        # constructor with None and raised there instead of being skipped.
        return None
    source_kind = BindingSourceKind(_invoice_source_kind(invoice))
    clave = _m347_operation_clave(invoice, source_kind=source_kind, declaration_roles=m347_filer.declaration_roles)
    is_third_party_collection = clave == "C"
    party_tax_id = invoice.collected_on_behalf_of_tax_id if is_third_party_collection else invoice.counterparty_tax_id
    party_legal_name = invoice.collected_on_behalf_of_name if is_third_party_collection else invoice.counterparty_name
    if party_tax_id is None:
        raise RegistryValidationError(
            f"invoice {invoice.invoice_id!r} resolves modelo 347 clave {clave!r} with no declaring party tax id",
        )
    cash_accounting_operation = _m347_cash_accounting_operation(invoice, effective_date=effective_date)
    return InvoiceObservation(
        invoice_id=invoice.invoice_id,
        source_kind=source_kind,
        party_tax_id=party_tax_id,
        country_code=invoice.counterparty_country,
        transaction_date=invoice.issued_at,
        base_amount=_m347_netted_amount(invoice, _eur(invoice.base_total_eur, invoice)),
        invoice_total_amount=_m347_netted_amount(invoice, _eur(invoice.grand_total_eur, invoice)),
        intracommunity_clave=None,
        operation_clave=clave,
        party_legal_name=party_legal_name,
        cash_accounting_operation=cash_accounting_operation,
        reverse_charge_recipient=_m347_reverse_charge_recipient(invoice),
        annual_computation_basis=m347_filer.annual_computation_basis or cash_accounting_operation,
        arrendamiento_local_negocio=invoice.business_premises_lease is not None,
        situacion_inmueble=(
            None
            if invoice.business_premises_lease is None or invoice.business_premises_lease.situacion_inmueble is None
            else invoice.business_premises_lease.situacion_inmueble.value
        ),
        referencia_catastral=(
            None if invoice.business_premises_lease is None else invoice.business_premises_lease.referencia_catastral
        ),
    )


def _m347_cash_accounting_operation(invoice: Invoice, *, effective_date: date) -> bool:
    """Whether the invoice documents an operation under the régimen especial del criterio de caja.

    RD 1619/2012 art. 6.1.p has every invoice of such an operation carry the
    mention "régimen especial del criterio de caja", and the invoice records the
    mentions it printed as typed tokens. The mention speaks for both sides: the
    issuer applying the regime and the destinatario of its operation, and the
    347 design marks the record for either ("Tanto para sujetos pasivos acogidos
    al régimen especial como para destinatarios de las operaciones incluidas en
    el mismo").
    """
    mention = resolve_invoice_legal_mention("CASH_ACCOUNTING_REGIME", effective_date)
    return mention in invoice.legal_mentions


def _m347_reverse_charge_recipient(invoice: Invoice) -> bool:
    """Whether the declarant received the operation as the sujeto pasivo destinatario (LIVA art. 84.Uno.2º).

    Read through the same flow classification the Modelo 303 invoice bindings
    use to find a recipient self-assessment, so the two modelos cannot
    disagree about which received invoices are reverse-charged. Only the
    destinatario marks it: the 347 design reads "(Sólo el destinatario de la
    operación)".
    """
    if invoice.kind is not InvoiceKind.RECEIVED or invoice.iva_category is None:
        return False
    return is_inversion_sujeto_pasivo_flow(
        derive_flow_for_classification(category=invoice.iva_category, invoice_direction=invoice.kind),
    )


def _is_rectificativa(invoice: Invoice) -> bool:
    """Whether the invoice is a factura rectificativa, by the registry's invoice-class token."""
    return invoice.invoice_class == invoice_class_rectificativa()


def _m347_netted_amount(invoice: Invoice, amount: Decimal) -> Decimal:
    """Give a rectificativa's amount the sign that nets it against the operations it corrects.

    RD 1065/2007 art. 34.4: "el importe total de las operaciones se declarará
    neto de las devoluciones, descuentos y bonificaciones concedidos y de las
    operaciones que queden sin efecto en el mismo año natural". The invoice
    stores every total as a non-negative magnitude with the correction carried
    by its class, so the corrective direction enters here, on the observation
    total, and the one row builder and the one declarable-set summation net it
    like any other amount: a counterparty's annual and quarterly amounts can
    fall below zero and render with the record's "N" sign. Which direction a
    given rectificativa corrects is not on the record, so every rectificativa
    nets as a reduction and :func:`_m347_rectificativa_netting_advisory` names
    them.
    """
    return -amount if _is_rectificativa(invoice) else amount


def _m347_role_operation_clave(
    invoice: Invoice,
    *,
    declaration_roles: frozenset[ThirdPartyDeclarationRole],
) -> str | None:
    role_catalogue = resolve_third_party_declaration_role_catalogue()
    if invoice.collected_on_behalf_of_tax_id is not None and declaration_roles & role_catalogue.roles_for_clave("C"):
        return "C"
    if invoice.outside_economic_activity is True and declaration_roles & role_catalogue.roles_for_clave("D"):
        return "D"
    if invoice.is_subvencion_ayuda is True and declaration_roles & role_catalogue.roles_for_clave("E"):
        return "E"
    return None


def _m347_mediation_operation_clave(invoice: Invoice) -> str | None:
    mediation = invoice.travel_agency_mediation
    if mediation is not None and invoice.kind is InvoiceKind.ISSUED:
        return "F"
    if (
        mediation is not None
        and invoice.kind is InvoiceKind.RECEIVED
        and is_travel_agency_air_passenger_transport(
            mediation,
            effective_date=invoice.issued_at,
        )
    ):
        return "G"
    return None


def _m347_operation_clave(
    invoice: Invoice,
    *,
    source_kind: BindingSourceKind,
    declaration_roles: frozenset[ThirdPartyDeclarationRole] = frozenset(),
) -> str | None:
    """Classify the M347 clave de operacion for one invoice, or ``None``.

    Checks clave C first (RD 1065/2007 art. 31.3: the filer collects this
    amount on behalf of a socio, asociado or colegiado), then clave D (arts.
    31.1's last paragraph / 31.2: an acquisition al margen de la actividad
    empresarial by one of four disjoint filer roles), then clave E (art.
    31.2's second paragraph: a subvención/ayuda from a public-administration
    filer), then the RD 1619/2012 disposición adicional cuarta travel-agency
    mediation fact (claves F/G), then falls back to
    :func:`m347_operation_clave`'s invoice-direction classification (claves
    A/B).

    Claves C, D and E all require the SAME conjunction shape: a filer-level
    role membership AND a transaction-level fact, NEITHER alone sufficient.
    A collecting entity's ordinary sale is not clave C; a D-role filer's
    acquisition WITHIN its own economic activity is not clave D; an ordinary
    payment from a public administration is not clave E. Every fact is
    checked with ``is True`` rather than truthiness, so an undeclared
    tri-state ``None`` never silently classifies either way -- it falls
    through here and is surfaced as an advisory by the caller instead.
    """
    role_clave = _m347_role_operation_clave(invoice, declaration_roles=declaration_roles)
    if role_clave is not None:
        return role_clave
    mediation_clave = _m347_mediation_operation_clave(invoice)
    if mediation_clave is not None:
        return mediation_clave
    return m347_operation_clave(source_kind)


def _intracommunity_clave(invoice: Invoice) -> str | None:
    """Return the Modelo 349 clave de operación for one invoice, or ``None``.

    :class:`~cadrumo.core.aggregation.IntracomOperationType` is the clave authority -- its
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
    if invoice.iva_category == require_iva_category("intra_community_triangulation"):
        return IntracomOperationType.T.value
    if invoice.iva_category is None:
        return None
    derived = _clave_by_kind_and_category().get((invoice.kind, invoice.iva_category))
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


def _m349_operador_row_indexes(row_values: Mapping[tuple[BindingId, int], Decimal | str]) -> list[int]:
    return sorted(
        {row_index for binding_id, row_index in row_values if binding_id in _M349_OPERADOR_ROW_BINDINGS},
    )


def _m349_operador_row_values(
    row_values: Mapping[tuple[BindingId, int], Decimal | str],
    *,
    row_index: int,
) -> dict[str, Decimal | str]:
    return {
        attr: row_values[(binding_id, row_index)]
        for binding_id, attr in _M349_OPERADOR_ROW_BINDINGS.items()
        if (binding_id, row_index) in row_values
    }


def _m349_operador_row_from_values(
    values: Mapping[str, Decimal | str],
    *,
    row_index: int,
) -> Modelo349OperadorRow:
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
        return Modelo349OperadorRow.model_validate(
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


def _invoice_row_values(
    *,
    context: CalculationSourceContext,
    observations: tuple[InvoiceObservation, ...],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Build the revision's invoice row families once, through the canonical row builder."""
    if not observations:
        return {}
    return resolve_invoice_binding_row_values(
        context.revision,
        observations,
        effective_date=_filing_period_date(context),
    )


def _row_values_not_carried_by_detail_rows(
    row_values: Mapping[tuple[BindingId, int], Decimal | str],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Keep the row values that reach the revision as row bindings rather than typed detail rows.

    Modelo 349 operador rows travel as :class:`Modelo349OperadorRow` detail rows,
    where they union with operator-entered rows and replay into the same
    bindings; emitting them here as well would persist one row on two channels.
    """
    return {key: value for key, value in row_values.items() if key[0] not in _M349_OPERADOR_ROW_BINDINGS}


def _m349_operador_rows_from_values(
    row_values: Mapping[tuple[BindingId, int], Decimal | str],
) -> tuple[Modelo349OperadorRow, ...]:
    return tuple(
        _m349_operador_row_from_values(
            _m349_operador_row_values(row_values, row_index=row_index),
            row_index=row_index,
        )
        for row_index in _m349_operador_row_indexes(row_values)
    )


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
        terminal_origin=TerminalOriginClass.INVOICE_CATALOGUE,
        fingerprint=prefixed_digest(payload.encode("utf-8")),
    )


#: The forward reading of the same clave<->category relationship the inverse
#: map above expresses: what IVA treatment an operator has stated by choosing a
#: Modelo 349 clave. It lives beside its inverse deliberately. The two were
#: declared in different layers, agreeing only because both were maintained by
#: hand, and a clave added to one would have been invisible to the other.
#:
#: ``T`` appears here but not in the inverse map, and that asymmetry is real
#: rather than an omission: triangulation is filed from either side of the
#: operation, so it carries no kind and the kind-keyed inverse cannot express
#: it. It is special-cased ahead of that lookup instead.
def iva_category_for_operation_type(operation_type: IntracomOperationType | None) -> IvaCategory | None:
    """Return the IVA treatment an operator stated by choosing a 349 clave.

    Args:
        operation_type: The clave the operator selected, if any.

    Returns:
        The category that clave declares, or ``None`` when no clave was chosen.
        A clave outside the invoice-sourced set also yields ``None`` rather than
        a guess: the claves reporting call-off stock movements carry no invoice,
        so no category can be inferred from them.
    """
    if operation_type is None:
        return None
    return resolve_iva_category_catalogue().category_for_operation_type(operation_type.value)


__all__ = [
    "InvoiceCatalogueSourceResolver",
    "invoice_direction_to_source_kind",
    "iva_category_for_operation_type",
]
