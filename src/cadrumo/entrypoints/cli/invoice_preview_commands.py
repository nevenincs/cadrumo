"""``aeat app ledger invoice preview``: the backend's figures and verdict for one invoice draft."""

from __future__ import annotations

import json
from typing import Final
from uuid import UUID

import typer
from pydantic import ValidationError

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.commands.secure_input import (
    MachineSecretPayload,
    read_machine_secret_payload,
    select_machine_secret_channel,
)

from ...application.invoices.figures_preview_contracts import (
    INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
    InvoiceFiguresPreviewFinding,
    InvoiceFiguresPreviewLease,
    InvoiceFiguresPreviewLine,
    InvoiceFiguresPreviewRequest,
    InvoiceFiguresPreviewResult,
    InvoiceFiguresPreviewRuleFinding,
    InvoiceFiguresPreviewStored,
)
from ...application.operations.public_scalar import PublicDecimal, restore_facts
from ...core.aggregation import IntracomOperationType
from ...core.bucket_pointer import require_active_bucket_id
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.iva.schema import InvoiceKind, IvaCategory
from ._date_parsing import _parse_iso_date
from ._decimal_parsing import parse_decimal_amount, parse_fraction
from ._ledger_support import ledger_invoice_validation_no_recovery
from .common import emit_envelope
from .ledger_results import LedgerInvoicePreviewResult
from .machine_secret_json_items import json_array_items

_LINE_DECIMAL_FRACTIONS: Final = frozenset({"quantity", "unit_price"})
_LINE_DECIMAL_AMOUNTS: Final = frozenset({"subtotal", "iva_amount"})
_LINE_TEXT: Final = frozenset({"key", "description", "iva_rate", "spending_category_id", "oss_rate_kind"})


class InvoicePreviewSecrets(MachineSecretPayload):
    """Machine-channel draft material for ``app ledger invoice preview``.

    ``counterparty_nif`` is the counterparty's tax id. ``lines`` is a JSON array of draft
    line objects, each with optional ``key``, ``description``, ``quantity``,
    ``unit_price``, ``iva_rate``, ``subtotal`` and ``iva_amount``. Blank is absent.
    """

    counterparty_nif: str = ""
    lines: str = ""


def _secret_lines(text: str) -> tuple[str, ...]:
    try:
        return json_array_items(text)
    except ValueError as exc:
        raise InvoiceValidationError("lines must be one JSON array of line objects") from exc


def _amount(raw: str | None, *, label: str) -> PublicDecimal | None:
    return None if raw is None else PublicDecimal(decimal=str(parse_decimal_amount(raw, label=label)))


def _fraction(raw: str | None, *, label: str) -> PublicDecimal | None:
    return None if raw is None else PublicDecimal(decimal=str(parse_fraction(raw, label=label)))


def _draft_line(raw_line: str, position: int) -> InvoiceFiguresPreviewLine:
    """Parse one ``--line`` JSON object; a figure stays absent unless the object states it."""
    try:
        stated = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise InvoiceValidationError("line must be one JSON object") from exc
    if not isinstance(stated, dict):
        raise InvoiceValidationError("line must be one JSON object")
    unknown = sorted(set(stated) - _LINE_TEXT - _LINE_DECIMAL_FRACTIONS - _LINE_DECIMAL_AMOUNTS)
    if unknown:
        raise InvoiceValidationError(f"line states a field the preview does not take: {', '.join(unknown)}")
    values: dict[str, object] = {"key": stated.get("key", f"line-{position}")}
    for name in _LINE_TEXT - {"key"}:
        if name in stated:
            values[name] = stated[name]
    for name in _LINE_DECIMAL_FRACTIONS | _LINE_DECIMAL_AMOUNTS:
        if stated.get(name) is not None:
            parse = _fraction if name in _LINE_DECIMAL_FRACTIONS else _amount
            values[name] = parse(str(stated[name]), label=name)
    return InvoiceFiguresPreviewLine.model_validate(values)


def _draft_lease(
    *,
    lease_selected: bool,
    situacion_inmueble: str | None,
    referencia_catastral: str | None,
) -> InvoiceFiguresPreviewLease | None:
    """Carry the premises facts as typed; the read answers their rules with a served finding."""
    if lease_selected:
        return InvoiceFiguresPreviewLease(
            situacion_inmueble=situacion_inmueble,
            referencia_catastral=referencia_catastral,
        )
    if situacion_inmueble is not None or referencia_catastral is not None:
        raise InvoiceValidationError("premises facts require the business-premises lease choice")
    return None


def _stored_invoice(
    *,
    stored_invoice_id: str | None,
    stored_grand_total: str | None,
    operation_date_role: str | None,
) -> InvoiceFiguresPreviewStored | None:
    """Name the invoice a correction restates; its id and total travel together."""
    if stored_invoice_id is None and stored_grand_total is None:
        if operation_date_role is not None:
            raise InvoiceValidationError("operation-date-role restates a stored invoice")
        return None
    if stored_invoice_id is None or stored_grand_total is None:
        raise InvoiceValidationError("a stored invoice states both its id and its grand total")
    return InvoiceFiguresPreviewStored(
        invoice_id=stored_invoice_id,
        grand_total=PublicDecimal(decimal=str(parse_decimal_amount(stored_grand_total, label="stored-grand-total"))),
        operation_date_role=operation_date_role,
    )


def _draft_request(
    *,
    profile_id: UUID,
    kind: InvoiceKind | None,
    counterparty_name: str | None,
    counterparty_nif: str | None,
    country_code: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    currency: str | None,
    operation_date: str | None,
    operation_type: IntracomOperationType | None,
    iva_category: IvaCategory | None,
    invoice_class: str | None,
    series: str | None,
    rectifies_invoice_number: str | None,
    taxable_base: str | None,
    recargo: str | None,
    retention_rate: str | None,
    retention_amount: str | None,
    printed_total: str | None,
    arrendamiento_local_negocio: bool,
    situacion_inmueble: str | None,
    referencia_catastral: str | None,
    line: tuple[str, ...],
    notes: str,
    stored: InvoiceFiguresPreviewStored | None,
) -> InvoiceFiguresPreviewRequest:
    """Parse every stated option at the boundary; an option left out stays absent in the draft."""
    return InvoiceFiguresPreviewRequest(
        profile_id=profile_id,
        kind=kind,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_nif,
        counterparty_country=country_code,
        invoice_number=invoice_number,
        issued_at=None if invoice_date is None else _parse_iso_date(invoice_date, label="invoice-date"),
        currency=currency,
        operation_date=None if operation_date is None else _parse_iso_date(operation_date, label="operation-date"),
        operation_type=operation_type,
        iva_category=None if iva_category is None else str(iva_category),
        invoice_class=invoice_class,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        base_total=_amount(taxable_base, label="taxable-base"),
        recargo_amount=_amount(recargo, label="recargo"),
        retention_rate=_fraction(retention_rate, label="retention-rate"),
        retention_amount=_amount(retention_amount, label="retention-amount"),
        printed_total=_amount(printed_total, label="printed-total"),
        business_premises_lease=_draft_lease(
            lease_selected=arrendamiento_local_negocio,
            situacion_inmueble=situacion_inmueble,
            referencia_catastral=referencia_catastral,
        ),
        lines=tuple(_draft_line(raw, position) for position, raw in enumerate(line, start=1)),
        notes=notes,
        stored=stored,
    )


def _unwrapped(value: object) -> object:
    """Flatten the wire's tagged decimal, ``{"decimal": "21.00"}``, to the text it carries."""
    if isinstance(value, dict):
        if set(value) == {"decimal"}:
            return value["decimal"]
        return {key: _unwrapped(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_unwrapped(item) for item in value]
    return value


def _finding_line(finding: InvoiceFiguresPreviewFinding | InvoiceFiguresPreviewRuleFinding) -> str:
    words = {key: str(value) for key, value in restore_facts(finding.values).items()}
    where = finding.line_key or ""
    return f"finding\t{finding.severity.value}\t{finding.code.value}\t{where}\t{tr(finding.label_key, **words)}"


def _result_lines(answer: InvoiceFiguresPreviewResult) -> tuple[str, ...]:
    def amount(value: PublicDecimal | None) -> str:
        return "" if value is None else value.decimal

    return (
        f"verdict\t{answer.verdict}\t{answer.verdict_scope}",
        f"refusal_code\t{answer.refusal_code or ''}",
        f"invoice_id\t{answer.invoice_id or ''}",
        f"on_date\t{answer.on_date.isoformat()}\t{answer.on_date_source}",
        *(
            f"line\t{row.key}\t{amount(row.subtotal.computed)}\t{amount(row.iva_amount.computed)}"
            for row in answer.lines
        ),
        f"base_total\t{amount(answer.totals.base)}",
        f"iva_total\t{amount(answer.totals.iva)}",
        f"recargo_amount\t{amount(answer.totals.recargo)}",
        f"grand_total\t{amount(answer.totals.total)}",
        f"net_of_retention\t{amount(answer.totals.net_of_retention)}",
        *(f"missing\t{name}" for name in answer.missing_fields),
        *(_finding_line(finding) for finding in answer.findings),
        *(_finding_line(finding) for finding in answer.rule_findings),
    )


def invoice_preview(
    ctx: typer.Context,
    kind: InvoiceKind | None = None,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    taxable_base: str | None = None,
    country_code: str | None = None,
    currency: str | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    invoice_class: str | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    recargo: str | None = None,
    printed_total: str | None = None,
    iva_category: IvaCategory | None = None,
    arrendamiento_local_negocio: bool = False,
    situacion_inmueble: str | None = None,
    referencia_catastral: str | None = None,
    notes: str = "",
    stored_invoice_id: str | None = None,
    stored_grand_total: str | None = None,
    operation_date_role: str | None = None,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Answer one invoice draft with the figures and verdict the add operation would reach."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    secrets = (
        read_machine_secret_payload(InvoicePreviewSecrets, selection=selection)
        if selection is not None
        else InvoicePreviewSecrets()
    )
    counterparty_nif = secrets.counterparty_nif or None
    try:
        line = _secret_lines(secrets.lines)
        request = _draft_request(
            profile_id=client.profile_id,
            kind=kind,
            counterparty_name=counterparty_name,
            counterparty_nif=counterparty_nif,
            country_code=country_code,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            currency=currency,
            operation_date=operation_date,
            operation_type=operation_type,
            iva_category=iva_category,
            invoice_class=invoice_class,
            series=series,
            rectifies_invoice_number=rectifies_invoice_number,
            taxable_base=taxable_base,
            recargo=recargo,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
            printed_total=printed_total,
            arrendamiento_local_negocio=arrendamiento_local_negocio,
            situacion_inmueble=situacion_inmueble,
            referencia_catastral=referencia_catastral,
            line=line,
            notes=notes,
            stored=_stored_invoice(
                stored_invoice_id=stored_invoice_id,
                stored_grand_total=stored_grand_total,
                operation_date_role=operation_date_role,
            ),
        )
    except (InvoiceValidationError, ValidationError) as exc:
        if (refusal := ledger_invoice_validation_no_recovery(exc)) is not None:
            raise refusal from None
        raise
    completed = run_registered_operation(
        client,
        request,
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=InvoiceFiguresPreviewResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=False,
    )
    answer = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or answer.profile_id != client.profile_id
    ):
        raise invalid_completion_error(completed)
    result = LedgerInvoicePreviewResult.model_validate(
        _unwrapped(answer.model_dump(mode="json", exclude={"profile_id"}))
    )
    emit_envelope(ctx, command="ledger.invoice.preview", result=result, lines=_result_lines(answer))


__all__ = ["invoice_preview"]
