"""Invoice source source observations responsibilities.

Core types:
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.aggregation import (
    BindingSourceKind,
    IntracomOperationType,
    ThirdPartyDeclarationRole,
)
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    m347_operation_clave,
    resolve_invoice_binding_row_values,
)
from ...domain.calculations.registry.iva_category_catalogue import (
    IvaCategoryExclusion,
    require_iva_category,
    resolve_iva_category_catalogue,
)
from ...domain.calculations.registry.m347_operation_scope import resolve_m347_estimacion_objetiva_scope
from ...domain.calculations.registry.third_party_declaration_roles import (
    resolve_third_party_declaration_role_catalogue,
)
from ...domain.calculations.registry.travel_agency_mediation import (
    is_travel_agency_air_passenger_transport,
)
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.invoices.enums import invoice_class_rectificativa, resolve_invoice_legal_mention
from ...domain.invoices.models import Invoice
from ...domain.iva.flow import derive_flow_for_classification, is_inversion_sujeto_pasivo_flow
from ...domain.iva.schema import InvoiceKind, IvaCategory
from ...domain.modelos.row_models import Modelo349OperadorRow, validate_m349_country_prefix_context
from ..aggregation.source_mesh import (
    CalculationSourceContext,
)
from ..aggregation.source_resolution_operations import source_context_operation

ObservedInvoice = tuple[Invoice, InvoiceObservation]


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


_THIRD_PARTY_COLLECTION = "third_party_collection"
_OUTSIDE_ECONOMIC_ACTIVITY = "outside_economic_activity"
_SUBSIDY_OR_AID = "subsidy_or_aid"


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


def invoice_sources_for_revision(context: CalculationSourceContext) -> frozenset[BindingSourceKind]:
    """Return invoice source families declared by the revision."""
    declared_sources = frozenset(
        binding.source for binding in context.revision.bindings if binding.source in OWNED_SOURCES
    )
    if declared_sources & COMBINED_DIRECTION_SOURCES:
        # A combined-direction binding reads both invoice directions, so both feed it.
        return frozenset(OWNED_SOURCES)
    return declared_sources


def invoice_in_context(invoice: Invoice, context: CalculationSourceContext) -> bool:
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


def filing_period_date(context: CalculationSourceContext) -> date:
    """The one date every dated registry read of this resolver is made as of: the period's last day.

    The threshold buckets, the category exclusion keys, the art. 32.b scope and
    the filer's profile facts all read the same coordinate, so a fact that
    changes inside the year cannot reach one consumer and miss another.
    """
    return context.period.end_date


def invoice_source_kind(invoice: Invoice) -> str:
    """Return the directional source kind for an invoice."""
    return invoice_direction_to_source_kind(invoice.kind).value


def _eur(converted: Decimal | None, invoice: Invoice) -> Decimal:
    """Return the euro amount, refusing rather than falling back to face value.

    ``None`` here means the caller skipped the
    :func:`is_unconverted_foreign_invoice` gate. Falling back to the native
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


def is_unconverted_foreign_invoice(invoice: Invoice) -> bool:
    """Return whether *invoice* is foreign-currency with no euro equivalent.

    Mirrors the ledger's ``is_non_eur_without_conversion`` gate. Every modelo
    amount is declared in euro, so an invoice whose euro value could not be
    resolved must be withheld from projection: summing its face value would
    declare foreign units as euro.
    """
    return invoice.currency != DEFAULT_CURRENCY and invoice.grand_total_eur is None


def invoice_observation(
    invoice: Invoice,
    *,
    context: CalculationSourceContext,
    m347_filer: M347Filer,
) -> InvoiceObservation | None:
    """Project an invoice into its registry observation."""
    if is_unconverted_foreign_invoice(invoice):
        return None
    if invoice.counterparty_tax_id is None:
        # M347/M349 both declare a third party by their tax id; a factura
        # simplificada legitimately carries none (RD 1619/2012 art. 6.1.d), so
        # it has nothing these informativas can declare rather than a defect.
        return None
    if context.modelo == form_for_role("third_party.annual_operations"):
        return _m347_invoice_observation(
            invoice,
            m347_filer=m347_filer,
            effective_date=filing_period_date(context),
        )
    clave = intracommunity_clave(invoice)
    if clave is None:
        return None
    if context.modelo == form_for_role("iva.intracommunity_summary"):
        validate_m349_country_prefix_context(
            country_code=invoice.counterparty_country,
            clave_operacion=clave,
            filing_year=context.filing_year,
            period=context.period.registry_token,
        )
    return InvoiceObservation(
        invoice_id=invoice.invoice_id,
        source_kind=BindingSourceKind(invoice_source_kind(invoice)),
        party_tax_id=invoice.counterparty_tax_id,
        country_code=invoice.counterparty_country,
        transaction_date=invoice.issued_at,
        base_amount=_eur(invoice.base_total_eur, invoice),
        invoice_total_amount=_eur(invoice.grand_total_eur, invoice),
        intracommunity_clave=clave,
        party_legal_name=invoice.counterparty_name,
    )


@dataclass(frozen=True, slots=True)
class M347Filer:
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


_UNSCOPED_M347_FILER = M347Filer()


def resolve_m347_filer(context: CalculationSourceContext) -> M347Filer:
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
    if context.modelo != form_for_role("third_party.annual_operations"):
        return _UNSCOPED_M347_FILER
    from ..modelo.profile_readiness_gate import load_modelo_work_profile
    from ..user_profile.projections import projection_for_taxpayer

    as_of = filing_period_date(context)
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
            return M347Filer(
                declaration_roles=taxpayer.declaration_roles,
                annual_computation_basis=annual_computation_basis,
            )
        scope = resolve_m347_estimacion_objetiva_scope(effective_date=as_of, authority=operation)
    return M347Filer(
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


def m347_category_exclusion(invoice: Invoice, *, effective_date: date) -> IvaCategoryExclusion | None:
    """How Modelo 347 treats this invoice's IVA category, per the catalogue's dated exclusion keys."""
    if invoice.iva_category is None:
        return None
    return resolve_iva_category_catalogue(effective_date=effective_date).exclusion(Modelo("347"), invoice.iva_category)


def carries_withholding(invoice: Invoice) -> bool:
    """Whether the invoice records an IRPF withholding actually practised on it."""
    return invoice.retention_amount is not None and invoice.retention_amount > 0


def _m347_invoice_observation(
    invoice: Invoice,
    *,
    m347_filer: M347Filer,
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
      recapitulativa, so an operation `intracommunity_clave` classifies as
      intracommunity routes to M349 instead -- the same classification M349's
      own branch of this resolver uses, never a bare country comparison;
    - art. 33.2.g), "Las importaciones y exportaciones de mercancías", read
      off the IVA category catalogue's Modelo 347 exclusion keys so that the
      goods exports and imports drop out while services with a non-resident
      stay declared; a category the catalogue marks unsettled stays declared
      and is disclosed by :func:`m347_exclusion_reading_advisories`;
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
    if not _m347_invoice_included(invoice, m347_filer=m347_filer, effective_date=effective_date):
        return None
    source_kind = BindingSourceKind(invoice_source_kind(invoice))
    clave = _m347_operation_clave(invoice, source_kind=source_kind, declaration_roles=m347_filer.declaration_roles)
    is_third_party_collection = clave == resolve_third_party_declaration_role_catalogue().clave_for(
        _THIRD_PARTY_COLLECTION
    )
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
            else invoice.business_premises_lease.situacion_inmueble.code
        ),
        referencia_catastral=(
            None if invoice.business_premises_lease is None else invoice.business_premises_lease.referencia_catastral
        ),
    )


def _m347_invoice_included(invoice: Invoice, *, m347_filer: M347Filer, effective_date: date) -> bool:
    if intracommunity_clave(invoice) is not None:
        return False
    if m347_category_exclusion(invoice, effective_date=effective_date) is IvaCategoryExclusion.EXCLUDED:
        return False
    if invoice.kind is InvoiceKind.RECEIVED and carries_withholding(invoice):
        return False
    if not m347_filer.relates(invoice.kind):
        return False
    # Simplified invoices may lack a counterparty tax ID and cannot form a M347 row.
    return invoice.counterparty_tax_id is not None


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


def is_rectificativa(invoice: Invoice) -> bool:
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
    return -amount if is_rectificativa(invoice) else amount


def _m347_role_operation_clave(
    invoice: Invoice,
    *,
    declaration_roles: frozenset[ThirdPartyDeclarationRole],
) -> str | None:
    role_catalogue = resolve_third_party_declaration_role_catalogue()
    for circumstance, holds in (
        (_THIRD_PARTY_COLLECTION, invoice.collected_on_behalf_of_tax_id is not None),
        (_OUTSIDE_ECONOMIC_ACTIVITY, invoice.outside_economic_activity is True),
        (_SUBSIDY_OR_AID, invoice.is_subvencion_ayuda is True),
    ):
        clave = role_catalogue.clave_for(circumstance)
        if holds and declaration_roles & role_catalogue.roles_for_clave(clave):
            return clave
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


def intracommunity_clave(invoice: Invoice) -> str | None:
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
            source_kind=BindingSourceKind(invoice_source_kind(invoice)),
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


def invoice_row_values(
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
        effective_date=filing_period_date(context),
    )


def row_values_not_carried_by_detail_rows(
    row_values: Mapping[tuple[BindingId, int], Decimal | str],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Keep the row values that reach the revision as row bindings rather than typed detail rows.

    Modelo 349 operador rows travel as :class:`Modelo349OperadorRow` detail rows,
    where they union with operator-entered rows and replay into the same
    bindings; emitting them here as well would persist one row on two channels.
    """
    return {key: value for key, value in row_values.items() if key[0] not in _M349_OPERADOR_ROW_BINDINGS}


def m349_operador_rows_from_values(
    row_values: Mapping[tuple[BindingId, int], Decimal | str],
) -> tuple[Modelo349OperadorRow, ...]:
    """Construct Modelo 349 operator rows from binding values."""
    return tuple(
        _m349_operador_row_from_values(
            _m349_operador_row_values(row_values, row_index=row_index),
            row_index=row_index,
        )
        for row_index in _m349_operador_row_indexes(row_values)
    )


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


OWNED_SOURCES: tuple[BindingSourceKind, ...] = (
    BindingSourceKind.COLLECTIBLE_INVOICE,
    BindingSourceKind.PAYABLE_INVOICE,
    BindingSourceKind.M347_THIRD_PARTY_OPERATION,
    BindingSourceKind.M349_INTRACOMMUNITY_OPERATION,
)

COMBINED_DIRECTION_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {
        BindingSourceKind.M347_THIRD_PARTY_OPERATION,
        BindingSourceKind.M349_INTRACOMMUNITY_OPERATION,
    },
)
