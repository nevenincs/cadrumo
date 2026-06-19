"""Typer registration for the unified ledger business invoice command.

One ``aeat app ledger invoice`` noun-group gated by ``--kind issued|received``
replaces the prior payable-invoice / collectible-invoice split. The operator's
``--kind`` is routed through :func:`invoice_direction_to_source_kind` (the single
contractual direction->settlement mapping) to select the matching slim CRUD
service over the encrypted :class:`BusinessOperationInvoice` catalogue.
"""

from __future__ import annotations

from enum import StrEnum

import typer

from ...application.invoices import (
    create_catalogue_invoice,
    invoice_direction_to_source_kind,
    remove_catalogue_invoice,
    resolve_catalogue_invoice_from_repository,
)
from ...application.ledger import (
    BusinessOperationInvoiceInputError,
    BusinessOperationInvoicePatch,
    BusinessOperationInvoiceSourceKind,
    CollectibleInvoiceService,
    IntracomOperationType,
    PayableInvoiceService,
    validate_eu_iva_id,
)
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...domain.iva import InvoiceKind, IvaCategory
from ._common import (
    _bad,
    _emit_envelope,
    _parse_iso_date,
    _parse_iso_date_str,
    _parse_optional_iso_date_str,
    parse_decimal_amount,
    parse_optional_decimal_amount,
)
from ._common import (
    active_bucket_id_or_refuse as _business_invoice_bucket_id,
)
from ._ledger_catalogue_invoice_payloads import (
    CatalogueInvoiceCreateResult,
    CatalogueInvoiceListResult,
    CatalogueInvoiceRemoveResult,
    CatalogueInvoiceViewResult,
)
from ._ledger_payloads import (
    InvoiceAddResult,
    InvoiceListResult,
    InvoiceRemoveResult,
    InvoiceUpdateResult,
    InvoiceViewResult,
)


class InvoiceKindOption(StrEnum):
    """Operator-facing ``--kind`` axis for the unified invoice command.

    Mirrors :class:`InvoiceKind`; declared as the Typer option type so click
    renders ``Choice([issued, received])`` and instructs the operator on parse
    failure. ``issued`` settles to ``collectible_invoice``; ``received`` settles
    to ``payable_invoice`` via :func:`invoice_direction_to_source_kind`.
    """

    ISSUED = "issued"
    RECEIVED = "received"


def register_business_invoice_commands(app: typer.Typer) -> None:
    """Mount the unified invoice command group on the ledger app."""
    invoice_app.add_typer(catalogue_app, name="catalogue")
    app.add_typer(invoice_app, name="invoice")


def _service_for_kind(
    kind: InvoiceKindOption,
) -> PayableInvoiceService | CollectibleInvoiceService:
    """Select the slim CRUD service for ``kind`` via the contractual mapping."""
    source_kind = invoice_direction_to_source_kind(InvoiceKind(kind.value))
    if source_kind is BusinessOperationInvoiceSourceKind.COLLECTIBLE_INVOICE:
        return CollectibleInvoiceService()
    return PayableInvoiceService()


def _validated_eu_iva_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        return validate_eu_iva_id(raw)
    except BusinessOperationInvoiceInputError as exc:
        raise _bad(str(exc)) from exc


def _parse_intracom_operation_type(raw: str | None, *, translation_key: str) -> IntracomOperationType | None:
    if raw is None:
        return None
    try:
        return IntracomOperationType(raw.upper())
    except ValueError:
        valid = ", ".join(t.value for t in IntracomOperationType)
        raise _bad(
            tr(
                translation_key,
                default=f"--operation-type must be one of: {valid}",
                valid=valid,
            ),
        ) from None


# M349 operation-type codes the calculation-feeding catalogue can represent
# today: the resolver derives the intra-community clave (E/A/T) from the rich
# invoice's ``iva_category``. Goods supplies (E), goods acquisitions (A), and
# triangular operations (T) map onto a category; the service codes (S/I), the
# rectification code (R), and the miscellany code (M) have no category the
# resolver reads, so they are refused here rather than silently dropped.
_OPERATION_TYPE_TO_IVA_CATEGORY: dict[IntracomOperationType, IvaCategory] = {
    IntracomOperationType.E: IvaCategory.INTRA_COMMUNITY_SUPPLY,
    IntracomOperationType.A: IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    IntracomOperationType.T: IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
}


def _catalogue_iva_category_for_operation_type(
    operation_type: IntracomOperationType | None,
) -> IvaCategory | None:
    """Map an M349 operation type onto the catalogue invoice's ``iva_category``.

    Returns ``None`` when no operation type is supplied (a domestic invoice).
    Refuses the service / rectification / miscellany codes the resolver cannot
    yet represent, naming the supported set, so the operator is never misled
    into believing an unrepresentable invoice will reach Modelo 349.
    """
    if operation_type is None:
        return None
    category = _OPERATION_TYPE_TO_IVA_CATEGORY.get(operation_type)
    if category is None:
        supported = ", ".join(t.value for t in _OPERATION_TYPE_TO_IVA_CATEGORY)
        raise _bad(
            tr(
                "cli.app.ledger.invoice.catalogue.operation_type_unsupported",
                default=(
                    f"--operation-type {operation_type.value} cannot feed Modelo 349 "
                    f"from the catalogue yet; supported: {supported}."
                ),
                value=operation_type.value,
                supported=supported,
            ),
        )
    return category


def _business_invoice_payload(record) -> dict[str, object]:
    payload: dict[str, object] = record.model_dump(mode="json")
    return payload


def _business_invoice_text_lines(record) -> list[str]:
    return [
        f"invoice_id\t{record.invoice_id}",
        f"source_kind\t{record.source_kind.value}",
        f"bucket\t{record.bucket_id}",
        f"counterparty_nif\t{record.counterparty_nif}",
        f"counterparty_name\t{record.counterparty_name}",
        f"invoice_number\t{record.invoice_number}",
        f"invoice_date\t{record.invoice_date}",
        f"currency\t{record.currency}",
        f"taxable_base\t{record.taxable_base}",
        f"iva_rate\t{'' if record.iva_rate is None else record.iva_rate}",
        f"iva_amount\t{record.iva_amount}",
        f"total_amount\t{record.total_amount}",
    ]


invoice_app = typer.Typer(
    name="invoice",
    help=tr(
        "cli.app.ledger.invoice.group_help",
        default="Business invoice records (issued or received).",
    ),
    no_args_is_help=True,
)


@invoice_app.command(
    "add",
    help=tr("cli.app.ledger.invoice.add_help", default="Register a new business invoice."),
)
def invoice_add(
    ctx: typer.Context,
    kind: InvoiceKindOption = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
    counterparty_nif: str = typer.Option(..., "--counterparty-nif"),
    invoice_number: str = typer.Option(..., "--invoice-number"),
    invoice_date: str = typer.Option(
        ...,
        "--invoice-date",
        help=tr("cli.app.ledger.invoice.invoice_date_help", default="Invoice date (YYYY-MM-DD)."),
    ),
    counterparty_name: str = typer.Option("", "--counterparty-name"),
    currency: str = typer.Option(DEFAULT_CURRENCY, "--currency"),
    taxable_base: str = typer.Option("0", "--taxable-base"),
    iva_rate: str | None = typer.Option(None, "--iva-rate"),
    iva_amount: str = typer.Option("0", "--iva-amount"),
    total_amount: str = typer.Option("0", "--total-amount"),
    notes: str = typer.Option("", "--notes"),
    country_code: str | None = typer.Option(
        None,
        "--country-code",
        help=tr(
            "cli.app.ledger.invoice.country_code_help",
            default="Counterparty ISO 3166-1 alpha-2 country code (intracom EU operations).",
        ),
    ),
    eu_iva_id: str | None = typer.Option(
        None,
        "--eu-iva-id",
        help=tr(
            "cli.app.ledger.invoice.eu_iva_id_help",
            default="Counterparty EU IVA-ID (e.g. DE345678901) for intracom operations.",
        ),
    ),
    operation_type: str | None = typer.Option(
        None,
        "--operation-type",
        help=tr(
            "cli.app.ledger.invoice.operation_type_help",
            default=(
                "M349 operation type: E entrega, S servicios, T triangular,"
                " R rectificacion, A adquisicion bienes, I adquisicion servicios, M miscelanea."
            ),
        ),
    ),
) -> None:
    """Register a new business invoice record on the active bucket."""
    bucket_id = _business_invoice_bucket_id()
    result = _service_for_kind(kind).add(
        bucket_id=bucket_id,
        counterparty_nif=counterparty_nif,
        invoice_number=invoice_number,
        invoice_date=_parse_iso_date_str(invoice_date, label="invoice-date"),
        counterparty_name=counterparty_name,
        currency=currency,
        taxable_base=parse_decimal_amount(taxable_base, label="taxable-base"),
        iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
        iva_amount=parse_decimal_amount(iva_amount, label="iva-amount"),
        total_amount=parse_decimal_amount(total_amount, label="total-amount"),
        notes=notes,
        country_code=country_code,
        eu_iva_id=_validated_eu_iva_id(eu_iva_id),
        operation_type=_parse_intracom_operation_type(
            operation_type,
            translation_key="cli.app.ledger.invoice.operation_type_invalid",
        ),
    )
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.invoice.add",
        result=InvoiceAddResult.model_validate(payload),
        lines=lines,
    )


@invoice_app.command(
    "view",
    help=tr("cli.app.ledger.invoice.view_help", default="Show one business invoice."),
)
def invoice_view(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
    kind: InvoiceKindOption = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
) -> None:
    """Show one business invoice record by id or unambiguous prefix."""
    bucket_id = _business_invoice_bucket_id()
    record = _service_for_kind(kind).view(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit_envelope(
        ctx,
        command="ledger.invoice.view",
        result=InvoiceViewResult.model_validate(_business_invoice_payload(record)),
        lines=_business_invoice_text_lines(record),
    )


@invoice_app.command(
    "list",
    help=tr(
        "cli.app.ledger.invoice.list_help",
        default="List business invoices (both kinds unless --kind filters).",
    ),
)
def invoice_list(
    ctx: typer.Context,
    kind: InvoiceKindOption | None = typer.Option(
        None,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
) -> None:
    """List business invoices; without ``--kind`` both kinds are returned.

    Defaulting to both kinds prevents a bare ``invoice list`` from silently
    dropping half the operator's records (no-silent-under-declaration).
    """
    bucket_id = _business_invoice_bucket_id()
    if kind is None:
        services: tuple[PayableInvoiceService | CollectibleInvoiceService, ...] = (
            PayableInvoiceService(),
            CollectibleInvoiceService(),
        )
    else:
        services = (_service_for_kind(kind),)
    rows = tuple(record for service in services for record in service.list_all(bucket_id=bucket_id))
    payload = {
        "bucket_id": bucket_id,
        "rows": [r.model_dump(mode="json") for r in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(
            f"{r.invoice_id}\t{r.source_kind.value}\t{r.counterparty_nif}\t"
            f"{r.invoice_number}\t{r.invoice_date}\t{r.total_amount}",
        )
    _emit_envelope(
        ctx,
        command="ledger.invoice.list",
        result=InvoiceListResult.model_validate(payload),
        lines=lines,
    )


@invoice_app.command(
    "update",
    help=tr(
        "cli.app.ledger.invoice.update_help",
        default="Update mutable fields on one business invoice.",
    ),
)
def invoice_update(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
    kind: InvoiceKindOption = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
    counterparty_nif: str | None = typer.Option(None, "--counterparty-nif"),
    counterparty_name: str | None = typer.Option(None, "--counterparty-name"),
    invoice_number: str | None = typer.Option(None, "--invoice-number"),
    invoice_date: str | None = typer.Option(None, "--invoice-date"),
    currency: str | None = typer.Option(None, "--currency"),
    taxable_base: str | None = typer.Option(None, "--taxable-base"),
    iva_rate: str | None = typer.Option(None, "--iva-rate"),
    iva_amount: str | None = typer.Option(None, "--iva-amount"),
    total_amount: str | None = typer.Option(None, "--total-amount"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    """Update mutable fields on one business invoice record."""
    bucket_id = _business_invoice_bucket_id()
    patch = BusinessOperationInvoicePatch(
        counterparty_nif=counterparty_nif,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=_parse_optional_iso_date_str(invoice_date, label="invoice-date"),
        currency=currency,
        taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
        iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
        iva_amount=parse_optional_decimal_amount(iva_amount, label="iva-amount"),
        total_amount=parse_optional_decimal_amount(total_amount, label="total-amount"),
        notes=notes,
    )
    result = _service_for_kind(kind).update(bucket_id=bucket_id, invoice_id=invoice_id, patch=patch)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.invoice.update",
        result=InvoiceUpdateResult.model_validate(payload),
        lines=lines,
    )


catalogue_app = typer.Typer(
    name="catalogue",
    help=tr(
        "cli.app.ledger.invoice.catalogue.group_help",
        default="Reconciliation catalogue invoices that link to transactions.",
    ),
    no_args_is_help=True,
)


def _catalogue_invoice_payload(invoice) -> dict[str, object]:
    return {
        "invoice_id": invoice.invoice_id,
        "bucket_id": invoice.bucket_id,
        "kind": invoice.kind.value,
        "invoice_number": invoice.invoice_number,
        "issued_at": invoice.issued_at.isoformat(),
        "counterparty_name": invoice.counterparty_name,
        "counterparty_tax_id": invoice.counterparty_tax_id,
        "counterparty_country": invoice.counterparty_country,
        "base_total": format(invoice.base_total, "f"),
        "iva_total": format(invoice.iva_total, "f"),
        "grand_total": format(invoice.grand_total, "f"),
        "currency": invoice.currency,
        "payment_status": invoice.payment_status.value,
        "linked_transaction_ids": list(invoice.linked_transaction_ids),
        "notes": invoice.notes,
    }


def _catalogue_invoice_lines(invoice) -> list[str]:
    return [
        f"invoice_id\t{invoice.invoice_id}",
        f"kind\t{invoice.kind.value}",
        f"counterparty_name\t{invoice.counterparty_name}",
        f"counterparty_tax_id\t{invoice.counterparty_tax_id}",
        f"invoice_number\t{invoice.invoice_number}",
        f"issued_at\t{invoice.issued_at.isoformat()}",
        f"grand_total\t{format(invoice.grand_total, 'f')}",
        f"currency\t{invoice.currency}",
        f"linked_transaction_ids\t{','.join(invoice.linked_transaction_ids)}",
    ]


@catalogue_app.command(
    "create",
    help=tr(
        "cli.app.ledger.invoice.catalogue.create_help",
        default="Create a linkable reconciliation invoice in the catalogue.",
    ),
)
def catalogue_create(
    ctx: typer.Context,
    kind: InvoiceKindOption = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
    counterparty_nif: str = typer.Option(..., "--counterparty-nif"),
    counterparty_name: str = typer.Option(..., "--counterparty-name"),
    invoice_number: str = typer.Option(..., "--invoice-number"),
    invoice_date: str = typer.Option(
        ...,
        "--invoice-date",
        help=tr("cli.app.ledger.invoice.invoice_date_help", default="Invoice date (YYYY-MM-DD)."),
    ),
    taxable_base: str = typer.Option(..., "--taxable-base"),
    iva_rate: str | None = typer.Option(None, "--iva-rate"),
    currency: str = typer.Option(DEFAULT_CURRENCY, "--currency"),
    country_code: str = typer.Option(
        "ES",
        "--country-code",
        help=tr(
            "cli.app.ledger.invoice.catalogue.country_code_help",
            default="Counterparty ISO 3166-1 alpha-2 country code.",
        ),
    ),
    operation_type: str | None = typer.Option(
        None,
        "--operation-type",
        help=tr(
            "cli.app.ledger.invoice.operation_type_help",
            default=(
                "M349 operation type: E entrega, S servicios, T triangular,"
                " R rectificación, A adquisición bienes, I adquisición servicios,"
                " M miscelánea."
            ),
        ),
    ),
    notes: str = typer.Option("", "--notes"),
) -> None:
    """Create a rich linkable invoice in the reconciliation catalogue.

    The slim ``invoice add`` record cannot be linked to a transaction; this
    verb mints the rich :class:`Invoice` whose content-addressed ``invoice_id``
    is the value ``aeat app ledger link --invoice-id`` resolves. Supplying an
    intra-community ``--operation-type`` (E/A/T) stamps the invoice's
    ``iva_category`` so the Modelo 349 recapitulative calculation can read it.
    """
    from pydantic import ValidationError

    from ...domain.invoices import InvoiceValidationError

    bucket_id = _business_invoice_bucket_id()
    iva_category = _catalogue_iva_category_for_operation_type(
        _parse_intracom_operation_type(
            operation_type,
            translation_key="cli.app.ledger.invoice.operation_type_invalid",
        ),
    )
    try:
        result = create_catalogue_invoice(
            bucket_id=bucket_id,
            kind=InvoiceKind(kind.value),
            counterparty_name=counterparty_name,
            counterparty_tax_id=counterparty_nif,
            counterparty_country=country_code,
            invoice_number=invoice_number,
            issued_at=_parse_iso_date(invoice_date, label="invoice-date"),
            taxable_base=parse_decimal_amount(taxable_base, label="taxable-base"),
            iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
            currency=currency,
            notes=notes,
            iva_category=iva_category,
        )
    except InvoiceValidationError as exc:
        raise _bad(str(exc)) from exc
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {"msg": "invalid invoice input"}
        raise _bad(str(first.get("msg", "invalid invoice input"))) from exc

    _emit_envelope(
        ctx,
        command="ledger.invoice.catalogue.create",
        result=CatalogueInvoiceCreateResult.model_validate(_catalogue_invoice_payload(result.invoice)),
        lines=_catalogue_invoice_lines(result.invoice),
    )


@catalogue_app.command(
    "list",
    help=tr(
        "cli.app.ledger.invoice.catalogue.list_help",
        default="List reconciliation catalogue invoices.",
    ),
)
def catalogue_list(
    ctx: typer.Context,
    kind: InvoiceKindOption | None = typer.Option(
        None,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
) -> None:
    """List the rich reconciliation catalogue invoices for the active bucket."""
    from ...domain.invoices import InvoiceCatalogueRepository

    bucket_id = _business_invoice_bucket_id()
    catalogue = InvoiceCatalogueRepository(bucket_id=bucket_id).load()
    wanted = None if kind is None else InvoiceKind(kind.value)
    rows = tuple(
        invoice
        for invoice in catalogue.values()
        if wanted is None or invoice.kind is wanted
    )
    payload = {
        "bucket_id": bucket_id,
        "rows": [_catalogue_invoice_payload(invoice) for invoice in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for invoice in rows:
        lines.append(
            f"{invoice.invoice_id}\t{invoice.kind.value}\t{invoice.counterparty_tax_id}\t"
            f"{invoice.invoice_number}\t{invoice.issued_at.isoformat()}\t{format(invoice.grand_total, 'f')}",
        )

    _emit_envelope(
        ctx,
        command="ledger.invoice.catalogue.list",
        result=CatalogueInvoiceListResult.model_validate(payload),
        lines=lines,
    )


@catalogue_app.command(
    "view",
    help=tr(
        "cli.app.ledger.invoice.catalogue.view_help",
        default="Show one reconciliation catalogue invoice by id or unambiguous prefix.",
    ),
)
def catalogue_view(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr(
            "cli.app.ledger.invoice.catalogue.invoice_id_help",
            default="Catalogue invoice id (or unambiguous prefix).",
        ),
    ),
) -> None:
    """Show one rich catalogue invoice, resolving a full id or unambiguous prefix.

    The catalogue invoice carries a long content-addressed id that
    ``aeat app ledger link --invoice-id`` resolves; this verb lets an operator
    confirm that id and inspect the invoice's linked transactions before
    linking or removing it. A not-found id, or a prefix matching more than one
    invoice, is a typed refusal naming the candidates — never a silent miss.
    """
    bucket_id = _business_invoice_bucket_id()
    invoice = resolve_catalogue_invoice_from_repository(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit_envelope(
        ctx,
        command="ledger.invoice.catalogue.view",
        result=CatalogueInvoiceViewResult.model_validate(_catalogue_invoice_payload(invoice)),
        lines=_catalogue_invoice_lines(invoice),
    )


@catalogue_app.command(
    "remove",
    help=tr(
        "cli.app.ledger.invoice.catalogue.remove_help",
        default="Delete one reconciliation catalogue invoice.",
    ),
)
def catalogue_remove(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr(
            "cli.app.ledger.invoice.catalogue.invoice_id_help",
            default="Catalogue invoice id (or unambiguous prefix).",
        ),
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help=tr("cli.app.ledger.invoice.yes_help", default="Confirm removal."),
    ),
) -> None:
    """Delete one rich catalogue invoice, resolving a full id or unambiguous prefix.

    Removal is refused while the invoice still carries linked transactions:
    deleting it from the catalogue alone would leave the transaction side
    citing a vanished invoice — the operator must ``link``-unlink first. The
    write rides the sanctioned :class:`InvoiceCatalogueRepository`.
    """
    if not yes:
        raise _bad(
            tr(
                "cli.app.ledger.invoice.yes_required",
                default="--yes is required to remove an invoice record",
            ),
        )
    bucket_id = _business_invoice_bucket_id()
    result = remove_catalogue_invoice(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit_envelope(
        ctx,
        command="ledger.invoice.catalogue.remove",
        result=CatalogueInvoiceRemoveResult.model_validate(_catalogue_invoice_payload(result.invoice)),
        lines=_catalogue_invoice_lines(result.invoice),
    )


@invoice_app.command(
    "remove",
    help=tr("cli.app.ledger.invoice.remove_help", default="Delete one business invoice."),
)
def invoice_remove(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
    kind: InvoiceKindOption = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help=tr("cli.app.ledger.invoice.yes_help", default="Confirm removal."),
    ),
) -> None:
    """Delete one business invoice record."""
    if not yes:
        raise _bad(
            tr(
                "cli.app.ledger.invoice.yes_required",
                default="--yes is required to remove an invoice record",
            ),
        )
    bucket_id = _business_invoice_bucket_id()
    result = _service_for_kind(kind).remove(bucket_id=bucket_id, invoice_id=invoice_id)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.invoice.remove",
        result=InvoiceRemoveResult.model_validate(payload),
        lines=lines,
    )
