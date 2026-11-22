"""Application service for creating one rich catalogue :class:`Invoice`.

The operator-facing ``aeat app ledger invoice add`` verb mints a **linkable**
invoice directly: the :class:`~domain.invoices.models.Invoice` in the
:class:`~domain.invoices.catalogue.InvoiceCatalogue` is the only invoice record, and it
carries
``linked_transaction_ids`` and is the reconciliation authority ``link`` targets.

:func:`create_catalogue_invoice` builds a strict :class:`Invoice` from
operator-friendly fields and persists it through the required catalogue
creation port bundle (no parallel write path). A caller that
supplies no line set gets a single line synthesised from the taxable base and
IVA rate; a caller that supplies one gets those lines, which is how an invoice
carrying several IVA rates is expressed.

This is the ONE line-synthesis site. The bulk import path does not carry its
own: it routes every row through :func:`build_catalogue_invoice`, so the two
transports cannot disagree about the shape they produce. Its row model does
still admit only one rate per row, which is a limit of that file format rather
than a second synthesis to keep in step. The returned :attr:`Invoice.invoice_id` is the
content-addressed hash ``link --invoice-id`` resolves, closing the documented
add->link gap without collapsing the two stores.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from ...core.aggregation import IntracomOperationType
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...core.parsing.codes import normalise_iso_4217_currency
from ...core.time.clock import now
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import build_bucket_event
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.calculations.registry.temporal import select_revision_metadata_for_year
from ...domain.currency.models import FxConversionStamp
from ...domain.currency.service import declared_fx_conversion_stamp, resolve_fx_conversion_stamp
from ...domain.invoices.business_premises import BusinessPremisesLease
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.enums import (
    InvoiceClass,
    IvaRate,
    PaymentStatus,
    default_invoice_class,
    operation_performed_role,
)
from ...domain.invoices.enums import (
    resolve_iva_rate_slot as resolve_iva_rate_slot_for_date,
)
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.figures import (
    computed_grand_total,
    computed_line_iva,
    rounded_line_totals,
)
from ...domain.invoices.models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ...domain.invoices.rule_findings import InvoiceRuleFindingCode
from ...domain.iva.errors import IvaRateNotFoundError
from ...domain.iva.schema import InvoiceKind, IvaCategory
from ..aggregation.counterpart import counterpart_catalogue_entry, counterpart_operation_catalogue_entries
from .catalogue_creation_ports import (
    CatalogueCreationPorts,
    CatalogueInvoiceRateProviderPort,
)


class CatalogueInvoiceCreateResult(BaseModel):
    """Result of persisting one rich catalogue invoice."""

    model_config = STRICT_FROZEN_CONFIG

    invoice: Invoice
    catalogue: InvoiceCatalogue
    bucket_event_ids: tuple[str, ...] = ()


# An invoice's DIRECTION decides which lifecycle event it emits, so the
# canonical store speaks the same event vocabulary the slim store did rather
# than inventing a second one. Issued invoices are collectible (a customer owes
# us); received ones are payable (we owe a vendor).
_EVENT_OBJECT_BY_KIND: dict[InvoiceKind, BucketEventObjectType] = {
    InvoiceKind.ISSUED: BucketEventObjectType.COLLECTIBLE_INVOICE,
    InvoiceKind.RECEIVED: BucketEventObjectType.PAYABLE_INVOICE,
}

# (created, updated, removed) per direction, mirroring the triple the slim
# store declared. Kept as one table so a caller cannot pair a created event
# with a removed object type, and so the three verbs stay visibly related.
_EVENT_TYPES_BY_KIND: dict[InvoiceKind, tuple[BucketEventType, BucketEventType, BucketEventType]] = {
    InvoiceKind.ISSUED: (
        BucketEventType.COLLECTIBLE_INVOICE_CREATED,
        BucketEventType.COLLECTIBLE_INVOICE_UPDATED,
        BucketEventType.COLLECTIBLE_INVOICE_REMOVED,
    ),
    InvoiceKind.RECEIVED: (
        BucketEventType.PAYABLE_INVOICE_CREATED,
        BucketEventType.PAYABLE_INVOICE_UPDATED,
        BucketEventType.PAYABLE_INVOICE_REMOVED,
    ),
}

_INVOICE_EVENT_PAYLOAD_VERSION = 1


def build_catalogue_invoice_event(
    *,
    invoice: Invoice,
    bucket_id: str,
    slot: int,
    occurred_at: datetime,
    actor: str,
) -> BucketEvent:
    """Build the durable audit entry for a canonically-written invoice.

    The canonical write paths emitted NO bucket event of any kind, while the
    slim store emitted six types and returned their ids to the operator. So
    repointing the operator's verbs onto this store would have dropped the
    invoice audit trail and the event-ids field in the same change -- a
    capability loss with no replacement, which is why it blocked the fold.

    The event type is chosen by direction so this store speaks the vocabulary
    that already exists rather than minting a parallel one; the six members
    outlive the slim store that used to be their only emitter.
    """
    event_type = _EVENT_TYPES_BY_KIND[invoice.kind][slot]
    object_type = _EVENT_OBJECT_BY_KIND[invoice.kind]
    return build_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=invoice.invoice_id,
        payload={
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.issued_at.isoformat(),
            "counterparty_nif": invoice.counterparty_tax_id or "",
        },
        payload_version=_INVOICE_EVENT_PAYLOAD_VERSION,
    )


def registry_m349_operation_type_requirement(
    effective_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[IvaCategory, tuple[IntracomOperationType, ...]]:
    """Resolve the M349 category/clave ambiguity from registry data."""
    select_revision_metadata_for_year(
        operation.modelo_directory("349"),
        filing_year=effective_date.year,
        on=effective_date,
    )
    entries = counterpart_operation_catalogue_entries(effective_date, operation=operation)

    try:
        category = require_iva_category(
            counterpart_catalogue_entry(entries, "modelo.349.operation_type_required_category"),
            effective_date=effective_date,
            authority=operation,
        )
    except (RegistryValidationError, ValueError) as exc:
        raise ValueError("counterpart registry declares an unknown operation-type category") from exc
    tokens = tuple(
        token.strip()
        for token in counterpart_catalogue_entry(entries, "modelo.349.operation_type_candidates").split(",")
        if token.strip()
    )
    if not tokens or len(set(tokens)) != len(tokens):
        raise ValueError("counterpart registry declares an empty or duplicate operation-type candidate set")
    try:
        candidates = tuple(IntracomOperationType(token) for token in tokens)
    except ValueError as exc:
        raise ValueError("counterpart registry declares an unknown Modelo 349 operation type") from exc
    return category, candidates


def _require_operation_type_where_the_category_cannot_settle_it(
    *,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse an entrega intracomunitaria that does not state its clave.

    Closing the ambiguity HERE rather than screening it at calculate time is
    the whole point. At creation the operator is looking at the document and
    knows whether this supply followed an exempt importation; by the time the
    Modelo 349 resolver runs, nobody does, and the best it can offer is to
    infer E and disclose that it guessed. A fact that only one party holds
    should be captured from that party, not reconstructed downstream from
    evidence that cannot carry it.

    Scoped to the single category where the ambiguity is real. Demanding an
    operation type for the service or triangulation categories would make the
    operator restate a clave their category already determines, and a
    redundant required field is how a boundary check earns the reputation that
    gets it removed.

    Raises:
        InvoiceValidationError: When an ``INTRA_COMMUNITY_SUPPLY`` invoice
            carries no ``operation_type``, naming the three candidate claves so
            the refusal tells the operator what to state rather than only that
            something is missing.
    """
    if effective_date < operation.supported_filing_years().date_envelope().floor:
        # No Modelo 349 is filed for a date older than the filing years, so no clave is owed to one.
        return
    required_category, candidates = registry_m349_operation_type_requirement(
        effective_date,
        operation=operation,
    )
    if iva_category != required_category or operation_type is not None:
        return
    candidate_labels = ", ".join(f"clave {candidate.value}" for candidate in candidates)
    raise InvoiceValidationError(
        "an intra-community supply must state its Modelo 349 operation type: the category alone "
        f"cannot distinguish among {candidate_labels}, because all candidates carry this same IVA category",
        translated_message="application.invoices.creation.errors.intracom_operation_type_required",
        context={
            "iva_category": required_category.value,
            "rule_finding_code": InvoiceRuleFindingCode.OPERATION_TYPE_REQUIRED.value,
            "fields": ("operation_type", "iva_category"),
        },
    )


def resolve_iva_rate_slot(iva_rate: Decimal | None, on_date: date) -> IvaRate:
    """Map a printed percentage to its dated authority-backed persisted slot.

    ``None`` resolves to the registry-declared exempt slot so a base-only
    invoice with no cuota is accepted. A percentage outside the governed slot
    vocabulary is refused with the accepted set named, never a bare "value
    invalid".

    Public because the percentage does not only come from an operator: the
    ledger's evidence-confirm path reads it off the document itself and needs
    the SAME refusal. Two resolvers previously split that job between them and
    disagreed about the outcome -- one raised a localised error naming the
    accepted set, the other a raw English one -- so which message an operator
    saw depended on whether their document happened to print a cuota.
    """
    try:
        return resolve_iva_rate_slot_for_date(iva_rate, on_date)
    except IvaRateNotFoundError as exc:
        accepted = (exc.context or {}).get("accepted", "")
        raise InvoiceValidationError(
            "iva_rate is not a recognised IVA percentage",
            translated_message="application.invoices.creation.errors.unsupported_iva_rate",
            context={
                "iva_rate": "" if iva_rate is None else format(iva_rate, "f"),
                "on_date": on_date.isoformat(),
                "accepted": accepted,
            },
        ) from exc


def _resolve_invoice_line_totals(
    *,
    taxable_base: Decimal | None,
    lines: Sequence[InvoiceLine] | None,
    invoice_number: str,
    rate_slot: IvaRate,
    iva_percentage: Decimal | None,
) -> tuple[Decimal, Decimal, object]:
    """Return the authoritative line payload and totals for one invoice.

    Supplied lines own their own amounts; otherwise this is the sole synthesis
    of the one operator-supplied rate line.
    """
    if lines is not None:
        return _totals_from_supplied_invoice_lines(lines)

    if taxable_base is None:
        raise InvoiceValidationError("taxable_base is required when lines are not supplied")
    base_total = round_to_cents(taxable_base)
    iva_amount = computed_line_iva(taxable_base, iva_percentage)
    return (
        base_total,
        iva_amount,
        [
            {
                "description": invoice_number or "Invoice",
                "quantity": "1",
                "unit_price": format(base_total, "f"),
                "subtotal": format(base_total, "f"),
                "iva_rate": rate_slot.value,
                "iva_amount": format(iva_amount, "f"),
            },
        ],
    )


def _totals_from_supplied_invoice_lines(
    lines: Sequence[InvoiceLine],
) -> tuple[Decimal, Decimal, list[dict[str, object]]]:
    if not lines:
        raise InvoiceValidationError("lines must not be empty")
    if not all(isinstance(item, InvoiceLine) for item in lines):
        raise InvoiceValidationError("lines must be InvoiceLine records")
    base_total, iva_total = rounded_line_totals(
        [item.subtotal for item in lines],
        [item.iva_amount for item in lines],
    )
    return base_total, iva_total, [item.model_dump(mode="json") for item in lines]


def _apply_operator_asserted_invoice_facts(
    invoice_payload: dict[str, object],
    *,
    series: str | None,
    rectifies_invoice_number: str | None,
    rectification_method: str | None,
    rectification_cause: str | None,
    rectification_direction: str | None,
    document_received_on: date | None,
    recargo_amount: Decimal | None,
    suplido_amount: Decimal | None,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    operation_date: date | None,
    retention_rate: Decimal | None,
    retention_amount: Decimal | None,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> None:
    if series is not None:
        invoice_payload["series"] = series
    if rectifies_invoice_number is not None:
        invoice_payload["rectifies_invoice_number"] = rectifies_invoice_number
    # The rectification facts travel as the tokens the operator stated; the
    # record's own deserialisation boundary projects each through fact 0141 and
    # refuses one the registry does not declare for this date, so no second
    # vocabulary check lives here. Each is applied only when stated: a
    # rectificativa missing one is admitted and blocked at declaration.
    if rectification_method is not None:
        invoice_payload["rectification_method"] = rectification_method
    if rectification_cause is not None:
        invoice_payload["rectification_cause"] = rectification_cause
    if rectification_direction is not None:
        invoice_payload["rectification_direction"] = rectification_direction
    if document_received_on is not None:
        invoice_payload["document_received_on"] = document_received_on.isoformat()
    if recargo_amount is not None:
        invoice_payload["recargo_amount"] = format(recargo_amount, "f")
    if suplido_amount is not None:
        invoice_payload["suplido_amount"] = format(suplido_amount, "f")
    if iva_category is not None:
        invoice_payload["iva_category"] = iva_category.value
    _require_operation_type_where_the_category_cannot_settle_it(
        iva_category=iva_category,
        operation_type=operation_type,
        effective_date=effective_date,
        operation=operation,
    )
    if operation_type is not None:
        invoice_payload["operation_type"] = operation_type.value
    if operation_date is not None:
        # LIVA art. 75.Uno: the general-regime devengo. The art. 75.Dos
        # advance-payment role carries its own preconditions (money actually
        # received, art. 25 entregas excluded) and is not something this
        # operator-supplied date can assert, so it is not offered here.
        invoice_payload["operation_date"] = operation_date.isoformat()
        invoice_payload["operation_date_role"] = operation_performed_role().value
    if retention_rate is not None:
        invoice_payload["retention_rate"] = format(retention_rate, "f")
    if retention_amount is not None:
        invoice_payload["retention_amount"] = format(retention_amount, "f")


def require_declarable_fx_rate(*, currency: str, declared_fx_rate: Decimal) -> None:
    """Refuse an exchange rate the operator cannot state for this invoice.

    A euro invoice converts nothing, so a rate on it would assert a conversion
    that never happened. A rate must be strictly positive: the stored euro
    figure is ``amount * rate``, and a zero or negative rate would erase or
    reverse the operation.

    Raises:
        InvoiceValidationError: For a euro invoice or a rate that is not above zero.
    """
    if currency == DEFAULT_CURRENCY:
        raise InvoiceValidationError(
            "a EUR invoice takes no exchange rate",
            translated_message="application.invoices.creation.errors.declared_fx_rate_on_euro_invoice",
            context={"fx_rate": format(declared_fx_rate, "f")},
        )
    if not declared_fx_rate.is_finite() or declared_fx_rate <= Decimal(0):
        raise InvoiceValidationError(
            "the declared exchange rate must be greater than zero",
            translated_message="application.invoices.creation.errors.declared_fx_rate_not_positive",
            context={"fx_rate": format(declared_fx_rate, "f")},
        )


def _fx_stamp_fields(fx_stamp: FxConversionStamp) -> dict[str, object]:
    return {
        "fx_rate": format(fx_stamp.rate, "f"),
        "fx_rate_date": fx_stamp.rate_date.isoformat(),
        "fx_rate_source": fx_stamp.source,
        "fx_rate_observation_date": (
            None if fx_stamp.observation_date is None else fx_stamp.observation_date.isoformat()
        ),
    }


def declared_fx_conversion_fields(*, currency: str, devengo_date: date, declared_fx_rate: Decimal) -> dict[str, object]:
    """Return the invoice fields that stamp an operator-declared exchange rate.

    ``devengo_date`` is the date the operator's statement answers for -- the
    LIVA art. 75 devengo date, which is the date the provider policy reads a
    published rate at -- and the stamp names the operator as its source. Every
    stamp field is returned, the empty observation date included, so applying
    them to a stored record replaces any earlier stamp whole.

    Raises:
        InvoiceValidationError: For a euro invoice or a rate that is not above zero.
    """
    require_declarable_fx_rate(currency=currency, declared_fx_rate=declared_fx_rate)
    return _fx_stamp_fields(declared_fx_conversion_stamp(rate=declared_fx_rate, on_date=devengo_date))


def _apply_fx_conversion_stamp(
    invoice_payload: dict[str, object],
    *,
    currency: str,
    devengo_date: date,
    rate_provider: CatalogueInvoiceRateProviderPort,
    declared_fx_rate: Decimal | None,
) -> None:
    if declared_fx_rate is not None:
        require_declarable_fx_rate(currency=currency, declared_fx_rate=declared_fx_rate)
    fx_stamp = resolve_fx_conversion_stamp(
        currency=currency,
        on_date=devengo_date,
        rate_provider=rate_provider,
        declared_rate=declared_fx_rate,
    )
    if fx_stamp is not None:
        invoice_payload.update(_fx_stamp_fields(fx_stamp))


def build_catalogue_invoice(
    *,
    bucket_id: str | None,
    kind: InvoiceKind,
    counterparty_name: str,
    counterparty_tax_id: str | None,
    counterparty_country: str,
    invoice_number: str,
    issued_at: date,
    currency: str,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    payment_status: PaymentStatus = PaymentStatus.PENDING,
    notes: str = "",
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: date | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    invoice_class: InvoiceClass | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    rectification_method: str | None = None,
    rectification_cause: str | None = None,
    rectification_direction: str | None = None,
    document_received_on: date | None = None,
    recargo_amount: Decimal | None = None,
    suplido_amount: Decimal | None = None,
    business_premises_lease: BusinessPremisesLease | None = None,
    lines: Sequence[InvoiceLine] | None = None,
    declared_fx_rate: Decimal | None = None,
    rate_provider: CatalogueInvoiceRateProviderPort,
    operation: PinnedAuthorityOperation | None = None,
) -> Invoice:
    """Return a strict rich :class:`Invoice` from operator-supplied fields.

    When ``lines`` is omitted a single line item is synthesised from
    ``taxable_base`` and the resolved IVA rate slot, and the invoice totals are
    derived from that line so the :class:`Invoice` arithmetic invariants hold.
    The returned invoice carries no linked transactions yet — ``link
    --invoice-id`` populates them later.

    When ``lines`` IS supplied they are authoritative and the totals are summed
    from them, which is what lets one invoice carry several IVA rates. A real
    invoice mixing 21% and 10% lines is not exotic — collapsing it to one line
    at a single rate reports the right grand total while attributing the cuota
    to the wrong rate, and the per-rate breakdown is precisely what the IVA
    modelos declare.

    Structured callers do not supply ``taxable_base`` or ``iva_rate``: those
    scalar synthesis inputs would create a second source of truth for the line
    set. The application derives the canonical totals from the ordered lines.

    ``iva_category`` carries the intra-community classification the M349
    recapitulative resolver reads for historical goods/triangulation records.
    ``operation_type`` carries the explicit Modelo 349 clave for invoice
    records that need a key not represented by an IVA category.

    ``retention_rate`` / ``retention_amount`` record the RIRPF art. 95
    withholding a payer settles against a received invoice (or a customer
    against an issued one). Neither is derived here: :class:`Invoice`'s own
    ``_validate_retencion_consistency`` accepts an amount alone, requires an
    amount whenever a rate is supplied, and refuses either that does not
    match the invoice's ``base_total``.

    ``rectification_method``, ``rectification_cause``,
    ``rectification_direction`` and ``document_received_on`` carry the facts a
    factura rectificativa states and no other invoice does. Each is the
    operator's own statement: the method decides whether the stated figures ARE
    the modification or the post-rectification figures (RD 1619/2012
    art. 15.5), the cause places it in a period (LIVA art. 89.Cinco and
    art. 114.Dos), the direction carries its sense while the totals stay
    magnitudes, and the reception date is the recipient's. None is derived from
    the class, the dates or an amount, and a rectificativa stating none of them
    is written as it stands -- the Modelo 303 declaration refuses, naming the
    gaps.

    ``invoice_class``, ``series``, ``rectifies_invoice_number`` and
    ``recargo_amount`` reach axes the aggregate has always modelled and no
    write path could set. Until they existed here every canonically-written
    invoice was ordinary with no series and no recargo **by construction**,
    and a rectificativa was unrepresentable — so the aggregate claimed a
    vocabulary the writer could not speak.

    The recargo rides INSIDE ``grand_total`` (LIVA art. 161) while a retención
    is settled outside it, which is why only the recargo and the suplido enter
    the totals identity. A suplido (LIVA art. 78.Tres.3.º) is carried in the
    total but is no part of the base or the cuota. The model re-checks that identity exactly, so a stated recargo
    the lines do not support refuses rather than being balanced silently.

    ``business_premises_lease`` states that an issued invoice documents the
    lease of a local de negocio and, when known, the premises' situación and
    referencia catastral (RD 1065/2007 art. 34.1.d), which Modelo 347 relates
    in its own declarado and inmueble records.

    ``declared_fx_rate`` is the euro value of one unit of a foreign
    ``currency`` that the operator states was in force at the devengo -- the
    ``operation_date`` where one is recorded and ``issued_at`` otherwise, since
    LIVA art. 79.Once applies the rate "vigente en el momento del devengo". It
    wins over ``rate_provider`` and is stamped with the operator-declared
    source; it is refused for a euro invoice and for a rate that is not above
    zero.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return build_catalogue_invoice(
                bucket_id=bucket_id,
                kind=kind,
                counterparty_name=counterparty_name,
                counterparty_tax_id=counterparty_tax_id,
                counterparty_country=counterparty_country,
                invoice_number=invoice_number,
                issued_at=issued_at,
                taxable_base=taxable_base,
                iva_rate=iva_rate,
                currency=currency,
                payment_status=payment_status,
                notes=notes,
                iva_category=iva_category,
                operation_type=operation_type,
                operation_date=operation_date,
                retention_rate=retention_rate,
                retention_amount=retention_amount,
                invoice_class=invoice_class,
                series=series,
                rectifies_invoice_number=rectifies_invoice_number,
                rectification_method=rectification_method,
                rectification_cause=rectification_cause,
                rectification_direction=rectification_direction,
                document_received_on=document_received_on,
                recargo_amount=recargo_amount,
                suplido_amount=suplido_amount,
                business_premises_lease=business_premises_lease,
                lines=lines,
                declared_fx_rate=declared_fx_rate,
                rate_provider=rate_provider,
                operation=indexed_operation,
            )

    return _build_pinned_catalogue_invoice(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country=counterparty_country,
        invoice_number=invoice_number,
        issued_at=issued_at,
        currency=currency,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        payment_status=payment_status,
        notes=notes,
        iva_category=iva_category,
        operation_type=operation_type,
        operation_date=operation_date,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        invoice_class=invoice_class,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        rectification_method=rectification_method,
        rectification_cause=rectification_cause,
        rectification_direction=rectification_direction,
        document_received_on=document_received_on,
        recargo_amount=recargo_amount,
        suplido_amount=suplido_amount,
        business_premises_lease=business_premises_lease,
        lines=lines,
        declared_fx_rate=declared_fx_rate,
        rate_provider=rate_provider,
        operation=operation,
    )


def _build_pinned_catalogue_invoice(
    *,
    bucket_id: str | None,
    kind: InvoiceKind,
    counterparty_name: str,
    counterparty_tax_id: str | None,
    counterparty_country: str,
    invoice_number: str,
    issued_at: date,
    currency: str,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    payment_status: PaymentStatus = PaymentStatus.PENDING,
    notes: str = "",
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: date | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    invoice_class: InvoiceClass | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    rectification_method: str | None = None,
    rectification_cause: str | None = None,
    rectification_direction: str | None = None,
    document_received_on: date | None = None,
    recargo_amount: Decimal | None = None,
    suplido_amount: Decimal | None = None,
    business_premises_lease: BusinessPremisesLease | None = None,
    lines: Sequence[InvoiceLine] | None = None,
    declared_fx_rate: Decimal | None = None,
    rate_provider: CatalogueInvoiceRateProviderPort,
    operation: PinnedAuthorityOperation,
) -> Invoice:
    """Construct and validate the invoice inside its exact supplied authority operation."""
    from ...domain.invoices.enums import iva_rate_percentage

    # Every governed fact this construction reads -- the rate slot, the invoice
    # class default, the Modelo 349 clave rule, the devengo role and the final
    # validation -- resolves under the operation the caller handed in, never
    # under whatever scope the calling thread happens to hold.
    with validating_governed_facts(operation):
        if lines is not None and (taxable_base is not None or iva_rate is not None):
            raise InvoiceValidationError("structured lines cannot be combined with taxable_base or iva_rate")
        # Normalise once, before either the persisted payload or the FX lookup
        # reads it: a padded or lowercase token ("gbp", " gbp ") must resolve the
        # SAME provider rate as its canonical "GBP" form, not silently miss the
        # rate and leave the invoice unstamped.
        currency = normalise_iso_4217_currency(currency)
        devengo_date = operation_date or issued_at
        if lines is None:
            rate_slot = resolve_iva_rate_slot(iva_rate, devengo_date)
            # The exact devengo date is present at this composition boundary, so both
            # synthesis and Invoice validation project the same authority fact.
            pct = iva_rate_percentage(rate_slot, devengo_date)
            base_total, iva_total, payload_lines = _resolve_invoice_line_totals(
                taxable_base=taxable_base,
                lines=None,
                invoice_number=invoice_number,
                rate_slot=rate_slot,
                iva_percentage=pct,
            )
        else:
            if not lines:
                raise InvoiceValidationError("lines must not be empty")
            base_total, iva_total, payload_lines = _resolve_invoice_line_totals(
                taxable_base=None,
                lines=lines,
                invoice_number=invoice_number,
                rate_slot=lines[0].iva_rate,
                iva_percentage=None,
            )
        # The recargo de equivalencia rides INSIDE the invoice total (LIVA art. 161)
        # while a retencion is settled outside it, which is why only the recargo
        # appears here. The model re-checks this identity exactly, so a caller that
        # states a recargo the lines do not support is refused rather than balanced.
        grand_total = computed_grand_total(base_total, iva_total, recargo_amount) + (suplido_amount or Decimal(0))
        invoice_payload: dict[str, object] = {
            "bucket_id": bucket_id,
            "kind": kind.value,
            "invoice_number": invoice_number,
            "issued_at": issued_at.isoformat(),
            "counterparty_name": counterparty_name,
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": format(base_total, "f"),
            "iva_total": format(iva_total, "f"),
            "grand_total": format(grand_total, "f"),
            "currency": currency,
            "payment_status": payment_status.value,
            "lines": payload_lines,
            "notes": notes,
            "invoice_class": (invoice_class or default_invoice_class()).value,
        }
        _apply_operator_asserted_invoice_facts(
            invoice_payload,
            series=series,
            rectifies_invoice_number=rectifies_invoice_number,
            rectification_method=rectification_method,
            rectification_cause=rectification_cause,
            rectification_direction=rectification_direction,
            document_received_on=document_received_on,
            recargo_amount=recargo_amount,
            suplido_amount=suplido_amount,
            iva_category=iva_category,
            operation_type=operation_type,
            operation_date=operation_date,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
            effective_date=devengo_date,
            operation=operation,
        )
        invoice_payload["business_premises_lease"] = business_premises_lease
        # The euro-conversion stamp, taken at the devengo date resolved above --
        # the same date this construction already reads every other dated
        # authority fact at, because LIVA art. 79.Once reads the rate "vigente en
        # el momento del devengo". ``currency`` is already the canonical uppercase
        # ISO 4217 token (normalised once above), so the provider is queried with the
        # same token the record stores. Whether a record is deliberately left
        # unstamped is resolve_fx_conversion_stamp's to answer -- this only writes
        # the result into the payload shape.
        _apply_fx_conversion_stamp(
            invoice_payload,
            currency=currency,
            devengo_date=devengo_date,
            rate_provider=rate_provider,
            declared_fx_rate=declared_fx_rate,
        )
        return Invoice.model_validate(invoice_payload, context=INVOICE_WRITE_ADMISSION)


def create_catalogue_invoice(
    *,
    invoice: Invoice,
    ports: CatalogueCreationPorts,
    occurred_at: datetime | None = None,
    actor: str = "cli",
) -> CatalogueInvoiceCreateResult:
    """Persist one pre-built catalogue invoice and return the updated catalogue.

    :func:`build_catalogue_invoice` is the sole construction authority for
    operator-supplied fields and line synthesis. This service co-commits the
    catalogue mutation and its durable audit entry, so the invoice cannot
    survive an event-write failure without a traceable audit record.
    """
    bucket_id = invoice.bucket_id
    if bucket_id is None:
        raise InvoiceValidationError("a catalogue invoice must declare its bucket_id before persistence")

    def _add(catalogue: InvoiceCatalogue) -> InvoiceCatalogue:
        """Rebuild the catalogue with this invoice, refusing an identity it already holds."""
        if invoice.invoice_id in catalogue:
            raise InvoiceValidationError(
                "an invoice with the same identity already exists in the catalogue",
                translated_message="application.invoices.creation.errors.duplicate_invoice",
                context={"invoice_id": invoice.invoice_id},
            )
        updated = dict(catalogue.invoices)
        updated[invoice.invoice_id] = invoice
        return InvoiceCatalogue.model_validate({"invoices": updated})

    event = build_catalogue_invoice_event(
        invoice=invoice,
        bucket_id=bucket_id,
        slot=0,
        occurred_at=occurred_at or now(),
        actor=actor,
    )
    # Both singleton catalogues are rebuilt from their revisioned reads at each
    # retry.  The batch consequently cannot discard a concurrent invoice or
    # audit entry, and a failed batch persists neither half of this command.
    new_catalogue = ports.audit_commit.mutate_with_event(_add, event)
    return CatalogueInvoiceCreateResult(
        invoice=invoice,
        catalogue=new_catalogue,
        bucket_event_ids=(event.event_id,),
    )


__all__ = [
    "CatalogueInvoiceCreateResult",
    "build_catalogue_invoice",
    "build_catalogue_invoice_event",
    "create_catalogue_invoice",
    "declared_fx_conversion_fields",
    "require_declarable_fx_rate",
]
