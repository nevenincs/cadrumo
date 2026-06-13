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

from ...application.invoices import invoice_direction_to_source_kind
from ...application.ledger import (
    BusinessOperationInvoiceInputError,
    BusinessOperationInvoicePatch,
    BusinessOperationInvoiceSourceKind,
    CollectibleInvoiceService,
    IntracomOperationType,
    PayableInvoiceService,
    validate_eu_iva_id,
)
from ...core import require_active_bucket_id
from ...core.errors import NoActiveProfileError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...domain.iva import InvoiceKind
from ._common import (
    _bad,
    _emit_envelope,
    _no_active_profile_refusal,
    _parse_iso_date_str,
    _parse_optional_iso_date_str,
    parse_decimal_amount,
    parse_optional_decimal_amount,
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
    app.add_typer(invoice_app, name="invoice")


def _business_invoice_bucket_id() -> str:
    """Return the active workflow bucket id or raise the standard CLI refusal."""
    try:
        return require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise _no_active_profile_refusal() from exc


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
