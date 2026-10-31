"""Invoice source source advisories responsibilities."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ...core.aggregation import (
    BindingSourceKind,
    ThirdPartyDeclarationRole,
)
from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.invoice_bindings import (
    m347_declarable_set,
)
from ...domain.calculations.registry.iva_category_catalogue import (
    IvaCategoryExclusion,
)
from ...domain.calculations.registry.m347_threshold import M347DeclarableSet, M347ThresholdBucket
from ...domain.calculations.registry.third_party_declaration_roles import (
    resolve_third_party_declaration_role_catalogue,
)
from ...domain.invoices.business_premises import SITUACIONES_CON_REFERENCIA_CATASTRAL
from ...domain.invoices.models import Invoice
from ...domain.iva.establishment import SPAIN_COUNTRY_CODE
from ...domain.iva.schema import InvoiceKind
from ..aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
)
from .source_observations import (
    M347Filer,
    ObservedInvoice,
    carries_withholding,
    filing_period_date,
    invoice_observation,
    invoice_source_kind,
    is_rectificativa,
    m347_category_exclusion,
)


def m347_role_fact_advisories(
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
    clave_d_eligible = bool(
        declaration_roles & role_catalogue.roles_for_clave(role_catalogue.clave_for("outside_economic_activity"))
    )
    clave_e_eligible = bool(
        declaration_roles & role_catalogue.roles_for_clave(role_catalogue.clave_for("subsidy_or_aid"))
    )
    diagnostics: list[CalculationSourceDiagnostic] = []
    for invoice in invoices:
        if clave_d_eligible and invoice.kind is InvoiceKind.RECEIVED and invoice.outside_economic_activity is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="unclassified_declarant_role_fact",
                    source_kind=invoice_source_kind(invoice),
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
                    source_kind=invoice_source_kind(invoice),
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


_M347_THRESHOLD_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-33",)


_M347_GOODS_EXCLUSION_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-33.2.g",)


_M347_NET_TOTAL_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-33", "rd-1065-2007:art-34.4")


_M347_WITHHELD_ISSUED_LEGAL_REFS: tuple[str, ...] = (
    "rd-1065-2007:art-33.2.i",
    "rd-1065-2007:art-34.1.d",
    "rd-439-2007:art-108",
)


def _m347_observed_items(observed_items: Sequence[ObservedInvoice]) -> tuple[ObservedInvoice, ...]:
    return tuple(
        (invoice, observation) for invoice, observation in observed_items if observation.operation_clave is not None
    )


def _m347_threshold_bucket_numbers(
    bucket: M347ThresholdBucket,
    m347_items: Sequence[ObservedInvoice],
) -> list[str]:
    return sorted(
        invoice.invoice_number for invoice, observation in m347_items if observation.operation_clave in bucket.claves
    )


def _m347_threshold_bucket_advisory(
    bucket: M347ThresholdBucket,
    m347_items: Sequence[ObservedInvoice],
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
    m347_items: Sequence[ObservedInvoice],
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
    m347_items: Sequence[ObservedInvoice],
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
    m347_items: Sequence[ObservedInvoice],
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
    m347_items: Sequence[ObservedInvoice],
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
    rectificativas = [invoice for invoice, _observation in m347_items if is_rectificativa(invoice)]
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


def m347_declaration_advisories(
    observed_items: Sequence[ObservedInvoice],
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
        effective_date=filing_period_date(context),
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
    m347_items: Sequence[ObservedInvoice],
) -> tuple[ObservedInvoice, ...]:
    return tuple(
        (invoice, observation)
        for invoice, observation in m347_items
        if observation.operation_clave is not None
        and declarable.admits(observation.party_tax_id, observation.operation_clave)
    )


def _m347_record_field_advisories(
    declarable: M347DeclarableSet,
    m347_items: Sequence[ObservedInvoice],
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
    m347_items: Sequence[ObservedInvoice],
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
    without_situacion, without_referencia = _m347_inmueble_missing_fields(leases)
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


def _m347_inmueble_missing_fields(leases: Sequence[Invoice]) -> tuple[list[str], list[str]]:
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
    return without_situacion, without_referencia


def _m347_unsettled_exclusion_invoice_numbers(declared: Sequence[Invoice], *, effective_date: date) -> list[str]:
    return sorted(
        invoice.invoice_number
        for invoice in declared
        if m347_category_exclusion(invoice, effective_date=effective_date) is IvaCategoryExclusion.UNSETTLED
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
        and carries_withholding(invoice)
        and invoice.business_premises_lease is None
    )


def m347_exclusion_reading_advisories(
    observed_items: Sequence[ObservedInvoice],
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
    unsettled = _m347_unsettled_exclusion_invoice_numbers(declared, effective_date=filing_period_date(context))
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


_M347_RECEIVED_DATING_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-35", "rd-1624-1992:art-69")


_LAST_MONTH_CODE = "12"


def m347_received_invoice_dating_advisories(
    observed_items: Sequence[ObservedInvoice],
    catalogue_invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    resolver_id: str,
    m347_filer: M347Filer,
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
    declared, left_out = _m347_received_dating_numbers(
        observed_items, catalogue_invoices, context=context, m347_filer=m347_filer
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


def _m347_received_dating_numbers(
    observed_items: Sequence[ObservedInvoice],
    catalogue_invoices: Sequence[Invoice],
    *,
    context: CalculationSourceContext,
    m347_filer: M347Filer,
) -> tuple[list[str], list[str]]:
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
        and _m347_invoice_in_bucket(invoice, context)
        and previous_last_month.contains(invoice.issued_at)
        and invoice_observation(invoice, context=context, m347_filer=m347_filer) is not None
    )
    return declared, left_out


def _m347_invoice_in_bucket(invoice: Invoice, context: CalculationSourceContext) -> bool:
    return invoice.bucket_id is None or invoice.bucket_id == context.bucket_id
