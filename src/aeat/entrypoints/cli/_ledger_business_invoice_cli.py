"""Typer registration for ledger business invoice commands."""

from __future__ import annotations

import typer

from ...application.ledger import (
    BusinessOperationInvoiceInputError,
    BusinessOperationInvoicePatch,
    CollectibleInvoiceService,
    IntracomOperationType,
    PayableInvoiceService,
    validate_eu_iva_id,
)
from ...core import require_active_bucket_id
from ...core.errors import NoActiveProfileError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
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
    CollectibleInvoiceAddResult,
    CollectibleInvoiceListResult,
    CollectibleInvoiceRemoveResult,
    CollectibleInvoiceUpdateResult,
    CollectibleInvoiceViewResult,
    PayableInvoiceAddResult,
    PayableInvoiceListResult,
    PayableInvoiceRemoveResult,
    PayableInvoiceUpdateResult,
    PayableInvoiceViewResult,
)


def register_business_invoice_commands(app: typer.Typer) -> None:
    """Mount business invoice command groups on the ledger app."""
    app.add_typer(payable_invoice_app, name="payable-invoice")
    app.add_typer(collectible_invoice_app, name="collectible-invoice")


def _business_invoice_bucket_id() -> str:
    """Return the active workflow bucket id or raise the standard CLI refusal."""
    try:
        return require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise _no_active_profile_refusal() from exc


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


def _payable_invoice_service() -> PayableInvoiceService:
    return PayableInvoiceService()


def _collectible_invoice_service() -> CollectibleInvoiceService:
    return CollectibleInvoiceService()


payable_invoice_app = typer.Typer(
    name="payable-invoice",
    help=tr("cli.app.ledger.payable_invoice.group_help", default="Payable invoice records (we owe a vendor)."),
    no_args_is_help=True,
)


@payable_invoice_app.command(
    "add", help=tr("cli.app.ledger.payable_invoice.add_help", default="Register a new payable invoice record."),
)
def payable_invoice_add(
    ctx: typer.Context,
    counterparty_nif: str = typer.Option(..., "--counterparty-nif"),
    invoice_number: str = typer.Option(..., "--invoice-number"),
    invoice_date: str = typer.Option(
        ...,
        "--invoice-date",
        help=tr("cli.app.ledger.payable_invoice.invoice_date_help", default="Invoice date (YYYY-MM-DD)."),
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
            "cli.app.ledger.payable_invoice.country_code_help",
            default="Counterparty ISO 3166-1 alpha-2 country code (intracom EU operations).",
        ),
    ),
    eu_iva_id: str | None = typer.Option(
        None,
        "--eu-iva-id",
        help=tr(
            "cli.app.ledger.payable_invoice.eu_iva_id_help",
            default="Counterparty EU IVA-ID (e.g. DE345678901) for intracom operations.",
        ),
    ),
    operation_type: str | None = typer.Option(
        None,
        "--operation-type",
        help=tr(
            "cli.app.ledger.payable_invoice.operation_type_help",
            default=(
                "M349 operation type: E entrega, S servicios, T triangular,"
                " R rectificacion, A adquisicion bienes, I adquisicion servicios, M miscelanea."
            ),
        ),
    ),
) -> None:
    """Register a new payable invoice record on the active bucket."""
    bucket_id = _business_invoice_bucket_id()
    result = _payable_invoice_service().add(
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
            translation_key="cli.app.ledger.payable_invoice.operation_type_invalid",
        ),
    )
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.payable_invoice.add",
        result=PayableInvoiceAddResult.model_validate(payload),
        lines=lines,
    )


@payable_invoice_app.command(
    "view", help=tr("cli.app.ledger.payable_invoice.view_help", default="Show one payable invoice record."),
)
def payable_invoice_view(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.payable_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
) -> None:
    """Show one payable invoice record by id or unambiguous prefix."""
    bucket_id = _business_invoice_bucket_id()
    record = _payable_invoice_service().view(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit_envelope(
        ctx,
        command="ledger.payable_invoice.view",
        result=PayableInvoiceViewResult.model_validate(_business_invoice_payload(record)),
        lines=_business_invoice_text_lines(record),
    )


@payable_invoice_app.command(
    "list",
    help=tr(
        "cli.app.ledger.payable_invoice.list_help", default="List every payable invoice record on the active profile.",
    ),
)
def payable_invoice_list(ctx: typer.Context) -> None:
    """List every payable invoice record on the active bucket."""
    bucket_id = _business_invoice_bucket_id()
    rows = _payable_invoice_service().list_all(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [r.model_dump(mode="json") for r in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.invoice_id}\t{r.counterparty_nif}\t{r.invoice_number}\t{r.invoice_date}\t{r.total_amount}")
    _emit_envelope(
        ctx,
        command="ledger.payable_invoice.list",
        result=PayableInvoiceListResult.model_validate(payload),
        lines=lines,
    )


@payable_invoice_app.command(
    "update",
    help=tr(
        "cli.app.ledger.payable_invoice.update_help", default="Update mutable fields on one payable invoice record.",
    ),
)
def payable_invoice_update(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.payable_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
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
    """Update mutable fields on one payable invoice record."""
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
    result = _payable_invoice_service().update(bucket_id=bucket_id, invoice_id=invoice_id, patch=patch)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.payable_invoice.update",
        result=PayableInvoiceUpdateResult.model_validate(payload),
        lines=lines,
    )


@payable_invoice_app.command(
    "remove", help=tr("cli.app.ledger.payable_invoice.remove_help", default="Delete one payable invoice record."),
)
def payable_invoice_remove(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.payable_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
    yes: bool = typer.Option(
        False, "--yes", help=tr("cli.app.ledger.payable_invoice.yes_help", default="Confirm removal."),
    ),
) -> None:
    """Delete one payable invoice record."""
    if not yes:
        raise _bad(
            tr(
                "cli.app.ledger.payable_invoice.yes_required",
                default="--yes is required to remove a payable invoice record",
            ),
        )
    bucket_id = _business_invoice_bucket_id()
    result = _payable_invoice_service().remove(bucket_id=bucket_id, invoice_id=invoice_id)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.payable_invoice.remove",
        result=PayableInvoiceRemoveResult.model_validate(payload),
        lines=lines,
    )


collectible_invoice_app = typer.Typer(
    name="collectible-invoice",
    help=tr(
        "cli.app.ledger.collectible_invoice.group_help", default="Collectible invoice records (a customer owes us).",
    ),
    no_args_is_help=True,
)


@collectible_invoice_app.command(
    "add", help=tr("cli.app.ledger.collectible_invoice.add_help", default="Register a new collectible invoice record."),
)
def collectible_invoice_add(
    ctx: typer.Context,
    counterparty_nif: str = typer.Option(..., "--counterparty-nif"),
    invoice_number: str = typer.Option(..., "--invoice-number"),
    invoice_date: str = typer.Option(
        ...,
        "--invoice-date",
        help=tr("cli.app.ledger.collectible_invoice.invoice_date_help", default="Invoice date (YYYY-MM-DD)."),
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
            "cli.app.ledger.collectible_invoice.country_code_help",
            default="Counterparty ISO 3166-1 alpha-2 country code (intracom EU operations).",
        ),
    ),
    eu_iva_id: str | None = typer.Option(
        None,
        "--eu-iva-id",
        help=tr(
            "cli.app.ledger.collectible_invoice.eu_iva_id_help",
            default="Counterparty EU IVA-ID (e.g. DE345678901) for intracom operations.",
        ),
    ),
    operation_type: str | None = typer.Option(
        None,
        "--operation-type",
        help=tr(
            "cli.app.ledger.collectible_invoice.operation_type_help",
            default=(
                "M349 operation type: E entrega, S servicios, T triangular,"
                " R rectificacion, A adquisicion bienes, I adquisicion servicios, M miscelanea."
            ),
        ),
    ),
) -> None:
    """Register a new collectible invoice record on the active bucket."""
    bucket_id = _business_invoice_bucket_id()
    result = _collectible_invoice_service().add(
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
            translation_key="cli.app.ledger.collectible_invoice.operation_type_invalid",
        ),
    )
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.collectible_invoice.add",
        result=CollectibleInvoiceAddResult.model_validate(payload),
        lines=lines,
    )


@collectible_invoice_app.command(
    "view", help=tr("cli.app.ledger.collectible_invoice.view_help", default="Show one collectible invoice record."),
)
def collectible_invoice_view(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.collectible_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
) -> None:
    """Show one collectible invoice record by id or unambiguous prefix."""
    bucket_id = _business_invoice_bucket_id()
    record = _collectible_invoice_service().view(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit_envelope(
        ctx,
        command="ledger.collectible_invoice.view",
        result=CollectibleInvoiceViewResult.model_validate(_business_invoice_payload(record)),
        lines=_business_invoice_text_lines(record),
    )


@collectible_invoice_app.command(
    "list",
    help=tr(
        "cli.app.ledger.collectible_invoice.list_help",
        default="List every collectible invoice record on the active profile.",
    ),
)
def collectible_invoice_list(ctx: typer.Context) -> None:
    """List every collectible invoice record on the active bucket."""
    bucket_id = _business_invoice_bucket_id()
    rows = _collectible_invoice_service().list_all(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [r.model_dump(mode="json") for r in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.invoice_id}\t{r.counterparty_nif}\t{r.invoice_number}\t{r.invoice_date}\t{r.total_amount}")
    _emit_envelope(
        ctx,
        command="ledger.collectible_invoice.list",
        result=CollectibleInvoiceListResult.model_validate(payload),
        lines=lines,
    )


@collectible_invoice_app.command(
    "update",
    help=tr(
        "cli.app.ledger.collectible_invoice.update_help",
        default="Update mutable fields on one collectible invoice record.",
    ),
)
def collectible_invoice_update(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.collectible_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
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
    """Update mutable fields on one collectible invoice record."""
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
    result = _collectible_invoice_service().update(bucket_id=bucket_id, invoice_id=invoice_id, patch=patch)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.collectible_invoice.update",
        result=CollectibleInvoiceUpdateResult.model_validate(payload),
        lines=lines,
    )


@collectible_invoice_app.command(
    "remove",
    help=tr("cli.app.ledger.collectible_invoice.remove_help", default="Delete one collectible invoice record."),
)
def collectible_invoice_remove(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.collectible_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
    yes: bool = typer.Option(
        False, "--yes", help=tr("cli.app.ledger.collectible_invoice.yes_help", default="Confirm removal."),
    ),
) -> None:
    """Delete one collectible invoice record."""
    if not yes:
        raise _bad(
            tr(
                "cli.app.ledger.collectible_invoice.yes_required",
                default="--yes is required to remove a collectible invoice record",
            ),
        )
    bucket_id = _business_invoice_bucket_id()
    result = _collectible_invoice_service().remove(bucket_id=bucket_id, invoice_id=invoice_id)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.collectible_invoice.remove",
        result=CollectibleInvoiceRemoveResult.model_validate(payload),
        lines=lines,
    )
