"""Behavior handlers for the unified ledger business invoice command.

One ``aeat app ledger invoice`` noun-group gated by ``--kind issued|received``
replaces the prior payable-invoice / collectible-invoice split. Every verb
reads and writes the sole invoice aggregate — the
:class:`Invoice` records held in the
:class:`InvoiceCatalogue`. Mutations use the application-layer lifecycle
functions; list, view, import, and wizard use authenticated profile-worker
operations over that same catalogue identity.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Never
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.cli_exception_preconditions import CliExceptionPrecondition
from ...application.invoices.catalogue_add_operation import InvoiceAddLine, InvoiceAddRequest, InvoiceAddResult
from ...application.invoices.catalogue_intake_operation import InvoiceImportProjection
from ...application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from ...application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ...application.invoices.catalogue_update_operation import InvoiceUpdatePatch
from ...application.invoices.simplificada_advisory import (
    SimplificadaTaxIdAdvisory,
    resolve_simplificada_tax_id_advisory,
    resolve_simplificada_tax_id_legal_refs,
)
from ...application.invoices.source_resolver import iva_category_for_operation_type
from ...application.operations.public_scalar import PublicDecimal
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.aggregation import IntracomOperationType
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.type_guards import is_object_list_or_tuple
from ...domain.invoices.enums import (
    InvoiceClass,
    InvoiceOperationDateRole,
    IvaRate,
    default_invoice_class,
    require_invoice_class,
)
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory, IvaRateKind
from ._date_parsing import _parse_iso_date
from ._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from ._ledger_catalogue_invoice_payloads import (
    CatalogueInvoiceCreatePayload,
    CatalogueInvoiceImportResult,
    CatalogueInvoiceLinePayload,
    CatalogueInvoiceListResult,
    CatalogueInvoiceRecordPayload,
    CatalogueInvoiceRemovePayload,
    CatalogueInvoiceUpdatePayload,
    CatalogueInvoiceViewResult,
    CatalogueInvoiceWizardResult,
)
from ._ledger_support import ledger_cli_no_recovery, ledger_invoice_validation_no_recovery
from .common import (
    active_bucket_id_or_refuse as _business_invoice_bucket_id,
)
from .common import bad, emit_envelope
from .errors import CliRefusedBoundaryError
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import submitted_operation_error
from .runtime_invoice_catalogue import (
    add_invoice_catalogue,
    read_invoice_catalogue,
    remove_invoice_catalogue,
    update_invoice_catalogue,
    view_invoice_catalogue,
)
from .runtime_invoice_intake import submit_invoice_import, submit_invoice_wizard

# The domain-invoice fields shared by mutation readback and evidence-confirm.
# Authenticated list/view use the closed application snapshot instead.
_SHARED_INVOICE_FIELDS: tuple[str, ...] = (
    "invoice_id",
    "kind",
    "invoice_number",
    "issued_at",
    "counterparty_name",
    "counterparty_tax_id",
    "counterparty_country",
    "base_total",
    "iva_total",
    "grand_total",
    "currency",
    "payment_status",
    "linked_transaction_ids",
    "notes",
    # Settlement-side retención sits outside the totals and recargo inside, so
    # neither is recoverable from the three totals above.
    "retention_rate",
    "retention_amount",
    "recargo_amount",
    # The euro conversion and its provenance. A foreign-currency invoice
    # rendered as totals plus a currency code told the operator nothing about
    # whether those figures had reached euro at all -- and an unconverted
    # invoice is precisely the one held back from the modelo totals, so the
    # surface stayed silent on the fact that most needed saying. All six are
    # ``None`` on a euro invoice (nothing was converted) and the eur trio is
    # ``None`` on a foreign invoice with no resolvable rate, which is what makes
    # the refusal visible rather than merely correct.
    "fx_rate",
    "fx_rate_date",
    "fx_rate_source",
    "base_total_eur",
    "iva_total_eur",
    "grand_total_eur",
)


def _wire_scalar(value: object) -> object:
    """Render one invoice field in its string wire form.

    The evidence-confirm envelope declares every field as ``str``, so its
    projection needs the rendered form where the catalogue envelope wants the
    native typed value. Keeping the rendering here means the two differ only in
    FORM, never in which fields they carry.
    """
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_object_list_or_tuple(value):
        return list(value)
    return value


def catalogue_invoice_shared_fields(invoice: Invoice) -> dict[str, object]:
    """Project the :class:`Invoice` identity/total fields in their string wire form.

    Consumed by the evidence-confirm verb, whose envelope is all-``str``. Shares
    :data:`_SHARED_INVOICE_FIELDS` with the canonical evidence-confirm payload.
    """
    return {name: _wire_scalar(getattr(invoice, name)) for name in _SHARED_INVOICE_FIELDS}


def _snapshot_invoice_payload(snapshot: CatalogueInvoiceSnapshot) -> CatalogueInvoiceRecordPayload:
    """Restore the output DTO's tokens from the worker's canonical projection.

    The authenticated result already captured registry values under its held
    authority. Rendering neither constructs new tax values nor resolves them
    against a different publication.
    """

    def amount(value: object) -> Decimal | None:
        from ...application.operations.public_scalar import PublicDecimal

        return Decimal(value.decimal) if isinstance(value, PublicDecimal) else None

    return CatalogueInvoiceRecordPayload(
        invoice_id=snapshot.invoice_id,
        bucket_id=snapshot.bucket_id,
        kind=snapshot.kind,
        invoice_number=snapshot.invoice_number,
        issued_at=snapshot.issued_at,
        counterparty_name=snapshot.counterparty_name,
        counterparty_tax_id=snapshot.counterparty_tax_id,
        counterparty_country=snapshot.counterparty_country,
        base_total=Decimal(snapshot.base_total.decimal),
        iva_total=Decimal(snapshot.iva_total.decimal),
        grand_total=Decimal(snapshot.grand_total.decimal),
        currency=snapshot.currency,
        payment_status=snapshot.payment_status,
        linked_transaction_ids=list(snapshot.linked_transaction_ids),
        source_filename=snapshot.source_filename,
        source_sha256=snapshot.source_sha256,
        source_row_index=snapshot.source_row_index,
        notes=snapshot.notes,
        retention_rate=amount(snapshot.retention_rate),
        retention_amount=amount(snapshot.retention_amount),
        recargo_amount=amount(snapshot.recargo_amount),
        operation_type=snapshot.operation_type,
        lines=[
            CatalogueInvoiceLinePayload(
                description=line.description,
                quantity=Decimal(line.quantity.decimal),
                unit_price=Decimal(line.unit_price.decimal),
                subtotal=Decimal(line.subtotal.decimal),
                iva_rate=IvaRate.from_registry(line.iva_rate),
                iva_amount=Decimal(line.iva_amount.decimal),
                spending_category_id=line.spending_category_id,
                oss_rate_kind=IvaRateKind(line.oss_rate_kind) if line.oss_rate_kind is not None else None,
            )
            for line in snapshot.lines
        ],
        invoice_class=InvoiceClass.from_registry(snapshot.invoice_class),
        series=snapshot.series,
        operation_date=snapshot.operation_date,
        operation_date_role=(
            InvoiceOperationDateRole.from_registry(snapshot.operation_date_role)
            if snapshot.operation_date_role is not None
            else None
        ),
        iva_category=IvaCategory(snapshot.iva_category) if snapshot.iva_category is not None else None,
        rectifies_invoice_number=snapshot.rectifies_invoice_number,
        fx_rate=amount(snapshot.fx_rate),
        fx_rate_date=snapshot.fx_rate_date,
        fx_rate_source=snapshot.fx_rate_source,
        base_total_eur=amount(snapshot.base_total_eur),
        iva_total_eur=amount(snapshot.iva_total_eur),
        grand_total_eur=amount(snapshot.grand_total_eur),
    )


def _parse_invoice_lines(raw_lines: Sequence[str]) -> tuple[InvoiceLine, ...]:
    """Parse ordered ``--line`` JSON objects through the canonical line model."""
    parsed: list[InvoiceLine] = []
    for raw_line in raw_lines:
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise InvoiceValidationError("line must be one JSON object") from exc
        if not isinstance(payload, dict):
            raise InvoiceValidationError("line must be one JSON object")
        parsed.append(InvoiceLine.model_validate(payload))
    return tuple(parsed)


def _euro_value_pending_notices(
    invoice: Invoice | CatalogueInvoiceRecordPayload, *, pending: bool | None = None
) -> list[Notice]:
    """Say at capture that a foreign-currency invoice was recorded without a euro rate.

    The invoice is kept and held back from every euro figure until a rate is
    stamped on it. Without this notice the first sign was a refusal at
    calculation, far from the capture that could have been corrected.
    """
    if pending is None:
        if not isinstance(invoice, Invoice):
            raise ValueError("invoice add result requires a worker-owned euro-rate status")
        pending = invoice.euro_value_pending
    if not pending:
        return []
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="ledger.invoice.euro_rate_unavailable",
            message=tr(
                "cli.app.ledger.invoice.euro_rate_unavailable_message",
                currency=invoice.currency,
                date=invoice.issued_at.isoformat(),
            ),
            context={
                "invoice_id": invoice.invoice_id,
                "currency": invoice.currency,
                "issued_at": invoice.issued_at.isoformat(),
            },
        ),
    ]


def _simplificada_tax_id_notices(
    invoice: Invoice | CatalogueInvoiceRecordPayload, *, required: bool | None = None
) -> list[Notice]:
    """Surface RD 1619/2012 art. 6.1.d case 3.º as an advisory, never a refusal.

    Case 3.º asks for the destinatario's NIF on a DOMESTIC factura simplificada
    whose issuer is established in the TAI. Whether it applies -- and whether
    the issuing taxpayer could be resolved to decide at all -- is answered by
    :func:`~application.invoices.simplificada_advisory.resolve_simplificada_tax_id_advisory`.

    Deliberately advisory. An ordinary domestic ticket with no identified
    customer is common and legitimate practice, and the predicate rests on a
    residency approximation that is over-strict for a Canarias, Ceuta or
    Melilla issuer. Refusing here would block lawful invoices; saying nothing
    leaves a filer unaware of a real requirement. The Notice channel is the one
    that fits, which is what the predicate's own docstring instructs.

    Emits nothing for ``ISSUER_UNKNOWN``: an advisory whose premise could not
    be evaluated must not be asserted. That the check did not run is a distinct
    fact the resolver preserves, and a surface with somewhere to report it can
    say so; this channel has only "advise" and "do not".
    """
    if required is None:
        if not isinstance(invoice, Invoice):
            raise ValueError("invoice add result requires a worker-owned simplificada advisory")
        required = resolve_simplificada_tax_id_advisory(invoice=invoice) is SimplificadaTaxIdAdvisory.REQUIRED
    if not required:
        return []
    legal_refs = resolve_simplificada_tax_id_legal_refs()
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="ledger.invoice.simplificada_tax_id_expected",
            message=tr("cli.app.ledger.invoice.simplificada_tax_id_expected_message"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_class": invoice.invoice_class.value,
                "legal_ref": legal_refs[0],
            },
        ),
    ]


def _catalogue_invoice_lines(invoice: Invoice | CatalogueInvoiceRecordPayload) -> list[str]:
    return [
        f"invoice_id\t{invoice.invoice_id}",
        f"kind\t{invoice.kind.value}",
        f"counterparty_name\t{invoice.counterparty_name}",
        f"counterparty_tax_id\t{invoice.counterparty_tax_id}",
        f"invoice_number\t{invoice.invoice_number}",
        f"issued_at\t{invoice.issued_at.isoformat()}",
        # Base and cuota alongside the total: the grand total alone cannot be
        # checked against a factura, and an operator reconciling a recargo or a
        # reverse-charge line needs to see which part is base and which is IVA.
        f"base_total\t{format(invoice.base_total, 'f')}",
        f"iva_total\t{format(invoice.iva_total, 'f')}",
        f"grand_total\t{format(invoice.grand_total, 'f')}",
        f"currency\t{invoice.currency}",
        f"operation_type\t{'' if invoice.operation_type is None else invoice.operation_type.value}",
        # The regime axes an operator can now set. Echoed back because a
        # setting the surface does not confirm is one the operator cannot tell
        # they failed to apply -- and a rectificativa silently recorded as
        # ordinaria is a filing error, not a display one.
        f"invoice_class\t{invoice.invoice_class.value}",
        f"series\t{invoice.series or ''}",
        f"rectifies_invoice_number\t{invoice.rectifies_invoice_number or ''}",
        f"recargo_amount\t{'' if invoice.recargo_amount is None else format(invoice.recargo_amount, 'f')}",
        f"iva_category\t{'' if invoice.iva_category is None else invoice.iva_category.value}",
        f"linked_transaction_ids\t{','.join(invoice.linked_transaction_ids)}",
    ]


# Shared Typer option aliases for the two catalogue entry verbs (``create`` and
# ``wizard``), which carry a byte-identical 11-option signature. Declaring them
# once keeps the ``cli.app.ledger.invoice.*`` help keys in one home so ``--help``
# renders identically for both verbs from one ``tr`` lookup.
#: The destinatario's NIF. Optional because RD 1619/2012 art. 7 does not require
#: it on a factura simplificada -- that relief is the point of the simplified
#: form. The domain has always accepted its absence for an issued simplified invoice;
#: only this option forced one, so the state the art. 6.1.d advisory evaluates
#: could not be reached through the CLI at all. Every other class still refuses
#: an absent id at the domain boundary, with the accepted set named.

#: The wizard keeps the NIF REQUIRED. It is a guided flow that assembles a
#: complete record field by field and validates the id as it goes, so an absent
#: one is an unanswered question rather than the deliberate omission that a
#: simplificada represents on the direct `add` path.


def invoice_add(
    ctx: typer.Context,
    kind: InvoiceKind,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    taxable_base: str | None,
    country_code: str,
    iva_rate: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    invoice_class: str | None = None,
    counterparty_nif: str | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    recargo: str | None = None,
    iva_category: IvaCategory | None = None,
    line: tuple[str, ...] = (),
    notes: str = "",
) -> None:
    """Create a rich linkable invoice in the reconciliation catalogue.

    The slim ``invoice add`` record cannot be linked to a transaction; this
    verb mints the rich :class:`Invoice` whose
    content-addressed ``invoice_id`` is the value the canonical ledger-link
    action resolves. Supplying an intra-community
    ``--operation-type`` stamps the invoice so the Modelo 349 recapitulative
    calculation can read it. Supplying ``--retention-amount`` (optionally with
    ``--retention-rate``) records a RIRPF art. 95 withholding, which
    ``modelo aggregate --received-invoice-retencion`` routes to Modelo 111 for
    a received invoice.
    """
    bucket_id = _business_invoice_bucket_id()
    # An explicitly stated treatment WINS over the one derived from the M349
    # clave. The derivation exists so an intracomunitaria is not left
    # ungrounded when the operator only states the clave; it is a fallback, and
    # silently overriding a value the operator did state would be the reverse.
    resolved_iva_category = iva_category or iva_category_for_operation_type(
        operation_type,
    )
    try:
        request = _invoice_add_request(
            bucket_id=bucket_id,
            resolved_iva_category=resolved_iva_category,
            kind=kind,
            counterparty_name=counterparty_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            taxable_base=taxable_base,
            country_code=country_code,
            iva_rate=iva_rate,
            currency=currency,
            operation_type=operation_type,
            operation_date=operation_date,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
            invoice_class=invoice_class,
            counterparty_nif=counterparty_nif,
            series=series,
            rectifies_invoice_number=rectifies_invoice_number,
            recargo=recargo,
            line=line,
            notes=notes,
        )
    except (InvoiceValidationError, ValidationError) as exc:
        if (refusal := ledger_invoice_validation_no_recovery(exc)) is not None:
            raise refusal from None
        raise

    completed, added = add_invoice_catalogue(ctx, request=request)
    if added.outcome == "validation_error":
        _raise_invoice_add_validation(completed, added)
    try:
        if added.invoice is None:
            raise ValueError("created invoice result is missing its snapshot")
        invoice = _snapshot_invoice_payload(added.invoice)
        emit_envelope(
            ctx,
            command="ledger.invoice.add",
            result=CatalogueInvoiceCreatePayload.model_validate(invoice.model_dump(mode="python")),
            lines=_catalogue_invoice_lines(invoice),
            notices=[
                *_simplificada_tax_id_notices(invoice, required=added.simplificada_tax_id_advisory_required),
                *_euro_value_pending_notices(invoice, pending=added.euro_value_pending),
            ],
        )
    except typer.Exit:
        raise
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def invoice_wizard(
    ctx: typer.Context,
    kind: InvoiceKind,
    counterparty_nif: str,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    taxable_base: str,
    country_code: str,
    iva_rate: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    invoice_class: str | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    recargo: str | None = None,
    iva_category: IvaCategory | None = None,
    notes: str = "",
) -> None:
    """Guided manual-entry invoice creation for when extraction is unavailable.

    A non-interactive, step-wise validated entry point: every field is
    supplied up front as an option (a non-interactive caller
    cannot answer an interactive prompt), and every field is validated
    independently before any write is attempted — a malformed NIF and a
    malformed date are BOTH reported in one refusal, never just the first one
    found (``no-silent-under-declaration``). The write delegates to the same
    :func:`cadrumo.application.invoices.catalogue_creation.create_catalogue_invoice` primitive
    ``catalogue create`` uses (``aeat-architecture-boundaries``).
    A retry with identical fields resolves to the already-catalogued
    content-derived identity and is reported as a guarded idempotent no-op
    rather than re-written or raised as a duplicate
    (``aeat-cli-contract``).
    """
    wizard_result = submit_invoice_wizard(
        ctx,
        kind=kind,
        counterparty_nif=counterparty_nif,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        currency=currency,
        country_code=country_code,
        operation_date=operation_date,
        notes=notes,
        iva_category=iva_category,
        operation_type=operation_type,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        invoice_class=invoice_class,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        recargo_amount=recargo,
    )
    invoice = _snapshot_invoice_payload(wizard_result.invoice)
    payload = CatalogueInvoiceWizardResult.model_validate(
        {**invoice.model_dump(mode="python"), "already_existed": wizard_result.already_existed}
    )
    lines = _catalogue_invoice_lines(invoice)
    lines.append(f"already_existed\t{wizard_result.already_existed}")

    notices: list[Notice] = []
    if wizard_result.already_existed:
        noop_message = tr(
            "cli.app.ledger.invoice.wizard_idempotent_noop",
            invoice_id=invoice.invoice_id,
        )
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.invoice.catalogue.wizard.idempotent_noop",
                message=noop_message,
                context={"invoice_id": invoice.invoice_id},
            ),
        )
        lines.append(noop_message)
    notices.extend(_euro_value_pending_notices(invoice, pending=wizard_result.euro_value_pending))

    emit_envelope(
        ctx,
        command="ledger.invoice.wizard",
        result=payload,
        lines=lines,
        notices=notices,
    )


def _invoice_import_summary_lines(bucket_id: str, result: InvoiceImportProjection) -> list[str]:
    return [
        f"bucket\t{bucket_id}",
        f"rows\t{result.rows}",
        f"created\t{result.created}",
        f"skipped_duplicate\t{result.skipped_duplicate}",
        f"refused\t{len(result.refused)}",
    ]


def _invoice_import_refusal_lines(result: InvoiceImportProjection) -> list[str]:
    return [
        f"  refused\trow={failure.row_number}\tfield={failure.field}\treason={failure.reason}"
        for failure in result.refused
    ]


def _invoice_import_unmapped_report(
    unmapped_column_headers: tuple[str, ...],
) -> tuple[str, Notice] | None:
    if not unmapped_column_headers:
        return None
    headers = ", ".join(unmapped_column_headers)
    message = tr(
        "cli.app.ledger.invoice.import_unmapped_columns",
        columns=headers,
    )
    return (
        f"unmapped_columns\t{headers}",
        Notice(
            severity=NoticeSeverity.INFO,
            code="ledger.invoice.catalogue.import.unmapped_columns",
            message=message,
            context={"columns": headers, "count": str(len(unmapped_column_headers))},
        ),
    )


def _invoice_import_mapping_reports(mapping_reasons: Sequence[str]) -> tuple[list[str], list[Notice]]:
    lines: list[str] = []
    notices: list[Notice] = []
    for index, reason in enumerate(mapping_reasons):
        # The positional mapping carries roles only, so a token the allow-list
        # refused would otherwise reach the operator as nothing more than
        # "column not imported". The reason is the difference between an
        # unrecognised column and a mapping that named a role which does not
        # exist, and only one of those is worth an operator's attention.
        lines.append(f"mapping_note\t{reason}")
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.invoice.catalogue.import.column_role_not_applied",
                message=tr(
                    "cli.app.ledger.invoice.import_column_role_not_applied",
                    detail=reason,
                ),
                context={"detail": reason, "index": str(index)},
            ),
        )
    return lines, notices


def _invoice_import_all_refused_report(
    result: InvoiceImportProjection,
) -> tuple[str, Notice] | None:
    if not (result.rows > 0 and result.created == 0 and result.skipped_duplicate == 0 and bool(result.refused)):
        return None
    message = tr(
        "cli.app.ledger.invoice.import_all_refused",
    )
    return (
        message,
        Notice(
            severity=NoticeSeverity.WARNING,
            code="ledger.invoice.catalogue.import.all_refused",
            message=message,
            context={"rows": str(result.rows), "refused": str(len(result.refused))},
        ),
    )


def _invoice_import_payload(result: InvoiceImportProjection) -> dict[str, object]:
    return {
        "bucket_id": str(result.profile_id),
        "rows": result.rows,
        "created": result.created,
        "skipped_duplicate": result.skipped_duplicate,
        "refused": [failure.model_dump(mode="json") for failure in result.refused],
        "created_invoice_ids": list(result.created_invoice_ids),
    }


def invoice_import(
    ctx: typer.Context,
    file: Path,
    kind: InvoiceKind,
    country: str | None = None,
) -> None:
    """Bulk-create reconciliation catalogue invoices from a CSV/XLSX file.

    Each row is handed one at a time to
    :func:`cadrumo.application.invoices.catalogue_creation.create_catalogue_invoice` -- the same sole
    write path ``catalogue create`` uses for a single invoice; this verb never
    writes the catalogue itself. A row whose content-derived identity already
    exists in the catalogue (a re-import of an unchanged file) is reported
    ``skipped_duplicate`` rather than re-written or raised. A malformed row
    (missing field, bad date, unsupported IVA rate) is reported in ``refused``
    with its row number and the failing field; the remaining valid rows still
    import.
    """
    result = submit_invoice_import(ctx, source_path=file, kind=kind, country=country)
    bucket_id = str(result.profile_id)
    lines = _invoice_import_summary_lines(bucket_id, result)
    lines.extend(_invoice_import_refusal_lines(result))
    notices: list[Notice] = []
    if unmapped_report := _invoice_import_unmapped_report(result.unmapped_column_headers):
        unmapped_line, unmapped_notice = unmapped_report
        lines.append(unmapped_line)
        notices.append(unmapped_notice)
    mapping_lines, mapping_notices = _invoice_import_mapping_reports(result.mapping_reasons)
    lines.extend(mapping_lines)
    notices.extend(mapping_notices)
    all_refused_report = _invoice_import_all_refused_report(result)
    if all_refused_report:
        all_refused_message, all_refused_notice = all_refused_report
        lines.insert(1, all_refused_message)
        notices.append(all_refused_notice)
    emit_envelope(
        ctx,
        command="ledger.invoice.import",
        result=CatalogueInvoiceImportResult.model_validate(_invoice_import_payload(result)),
        lines=lines,
        notices=notices,
    )
    # Only a failed import exits non-zero. The unmapped-column report is an
    # observation about a SUCCESSFUL import, so keying the exit on "any notice"
    # would turn every book carrying an extra column into a failure -- exactly
    # the refuse-whole behaviour this path exists to remove.
    if all_refused_report:
        raise typer.Exit(code=1)


def invoice_list(
    ctx: typer.Context,
    kind: InvoiceKind | None = None,
) -> None:
    """List the rich reconciliation catalogue invoices for the active bucket."""
    read = read_invoice_catalogue(ctx, kind=kind)
    try:
        rows = [_snapshot_invoice_payload(invoice) for invoice in read.invoices]
        bucket_id = str(read.completion.projection.profile_id)
        lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
        for invoice in rows:
            lines.append(
                f"{invoice.invoice_id}\t{invoice.kind.value}\t{invoice.counterparty_tax_id}\t"
                f"{invoice.invoice_number}\t{invoice.issued_at.isoformat()}\t{format(invoice.grand_total, 'f')}",
            )
        emit_envelope(
            ctx,
            command="ledger.invoice.list",
            result=CatalogueInvoiceListResult(bucket_id=bucket_id, rows=rows, count=len(rows)),
            lines=lines,
        )
    except typer.Exit:
        raise
    except Exception:
        receipt = read.completion
        raise submitted_operation_error(
            receipt.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=receipt.terminal_condition,
            effect=receipt.effect,
            refusal_code=receipt.refusal_code,
        ) from None


def invoice_view(
    ctx: typer.Context,
    invoice_id: str,
) -> None:
    """Show one rich catalogue invoice, resolving a full id or unambiguous prefix.

    The catalogue invoice carries a long content-addressed id that the
    canonical ledger-link action resolves; this verb lets an operator
    confirm that id and inspect the invoice's linked transactions before
    linking or removing it. A not-found id, or a prefix matching more than one
    invoice, is a typed refusal naming the candidates — never a silent miss.
    """
    read = view_invoice_catalogue(ctx, invoice_id=invoice_id)
    try:
        invoice = _snapshot_invoice_payload(read.invoice)
        emit_envelope(
            ctx,
            command="ledger.invoice.view",
            result=CatalogueInvoiceViewResult.model_validate(invoice.model_dump(mode="python")),
            lines=_catalogue_invoice_lines(invoice),
        )
    except typer.Exit:
        raise
    except Exception:
        receipt = read.completion
        raise submitted_operation_error(
            receipt.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=receipt.terminal_condition,
            effect=receipt.effect,
            refusal_code=receipt.refusal_code,
        ) from None


def invoice_remove(
    ctx: typer.Context,
    invoice_id: str,
    yes: bool = False,
) -> None:
    """Delete one rich catalogue invoice, resolving a full id or unambiguous prefix.

    Removal is refused while the invoice still carries linked transactions:
    deleting it from the catalogue alone would leave the transaction side
    citing a vanished invoice — the operator must ``link``-unlink first. The
    write rides the sanctioned :class:`InvoiceCatalogueRepository`.
    """
    if not yes:
        raise bad(
            tr("cli.app.ledger.invoice.yes_required"),
        )
    completed, snapshot = remove_invoice_catalogue(ctx, invoice_id=invoice_id)
    try:
        invoice = _snapshot_invoice_payload(snapshot)
        emit_envelope(
            ctx,
            command="ledger.invoice.remove",
            result=CatalogueInvoiceRemovePayload.model_validate(invoice.model_dump(mode="python")),
            lines=_catalogue_invoice_lines(invoice),
        )
    except typer.Exit:
        raise
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def invoice_update(
    ctx: typer.Context,
    invoice_id: str,
    counterparty_name: str | None = None,
    counterparty_country: str | None = None,
    notes: str | None = None,
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    invoice_class: str | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
) -> None:
    """Correct one persisted invoice without re-keying it.

    The identity fields -- kind, number, issue date, counterparty tax id,
    currency and the totals -- are deliberately absent. The invoice id is
    derived from them, so changing one would mint a different record and
    strand every transaction already linked to the old id. An identity
    correction is a remove followed by a create, which the remove verb guards
    by refusing to delete a linked record.
    """
    patch_values = {
        "counterparty_name": counterparty_name,
        "counterparty_country": counterparty_country,
        "notes": notes,
        "iva_category": iva_category,
        "operation_type": operation_type,
        "operation_date": None if operation_date is None else _parse_iso_date(operation_date, label="operation-date"),
        "retention_rate": parse_optional_decimal_amount(retention_rate, label="retention-rate"),
        "retention_amount": parse_optional_decimal_amount(retention_amount, label="retention-amount"),
        "invoice_class": None if invoice_class is None else require_invoice_class(invoice_class),
        "series": series,
        "rectifies_invoice_number": rectifies_invoice_number,
    }
    patch = CatalogueInvoicePatch.model_validate(
        {key: value for key, value in patch_values.items() if value is not None}
    )
    if not patch.model_fields_set:
        empty_patch = InvoiceValidationError(
            translated_message="application.invoices.lifecycle.errors.empty_invoice_patch",
            context={"invoice_id": invoice_id},
        )
        if (refusal := ledger_invoice_validation_no_recovery(empty_patch)) is not None:
            raise refusal from None
        raise empty_patch
    completed, result = update_invoice_catalogue(
        ctx,
        invoice_id=invoice_id,
        patch=InvoiceUpdatePatch.from_patch(patch),
    )

    try:
        invoice = _snapshot_invoice_payload(result.invoice)
        payload = invoice.model_dump(mode="python")
        payload["bucket_event_ids"] = list(result.bucket_event_ids)
        lines = _catalogue_invoice_lines(invoice)
        lines.append(f"bucket_event_ids	{','.join(result.bucket_event_ids)}")
        emit_envelope(
            ctx,
            command="ledger.invoice.update",
            result=CatalogueInvoiceUpdatePayload.model_validate(payload),
            lines=lines,
        )
    except typer.Exit:
        raise
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _invoice_add_request(
    *,
    bucket_id: str,
    resolved_iva_category: IvaCategory | None,
    kind: InvoiceKind,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    taxable_base: str | None,
    country_code: str,
    iva_rate: str | None,
    currency: str,
    operation_type: IntracomOperationType | None,
    operation_date: str | None,
    retention_rate: str | None,
    retention_amount: str | None,
    invoice_class: str | None,
    counterparty_nif: str | None,
    series: str | None,
    rectifies_invoice_number: str | None,
    recargo: str | None,
    line: tuple[str, ...],
    notes: str,
) -> InvoiceAddRequest:
    """Construct the exact registered request from the already resolved CLI inputs."""

    def public_amount(raw: str | None, *, label: str) -> PublicDecimal | None:
        parsed = parse_optional_decimal_amount(raw, label=label)
        return None if parsed is None else PublicDecimal(decimal=str(parsed))

    structured_lines = _parse_invoice_lines(line)
    parsed_taxable_base, parsed_iva_rate = _invoice_add_base_and_rate(structured_lines, taxable_base, iva_rate)
    request = InvoiceAddRequest(
        profile_id=UUID(bucket_id),
        kind=kind,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_nif,
        counterparty_country=country_code,
        invoice_number=invoice_number,
        issued_at=_parse_iso_date(invoice_date, label="invoice-date"),
        taxable_base=None if parsed_taxable_base is None else PublicDecimal(decimal=str(parsed_taxable_base)),
        iva_rate=None if parsed_iva_rate is None else PublicDecimal(decimal=str(parsed_iva_rate)),
        currency=currency,
        notes=notes,
        iva_category=None if resolved_iva_category is None else str(resolved_iva_category),
        operation_type=operation_type,
        operation_date=(None if operation_date is None else _parse_iso_date(operation_date, label="operation-date")),
        retention_rate=public_amount(retention_rate, label="retention-rate"),
        retention_amount=public_amount(retention_amount, label="retention-amount"),
        invoice_class=str(default_invoice_class() if invoice_class is None else require_invoice_class(invoice_class)),
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        recargo_amount=public_amount(recargo, label="recargo"),
        lines=tuple(InvoiceAddLine.from_invoice_line(item) for item in structured_lines),
    )
    return request


def _invoice_add_base_and_rate(
    structured_lines: tuple[InvoiceLine, ...], taxable_base: str | None, iva_rate: str | None
) -> tuple[Decimal | None, Decimal | None]:
    """Refuse mixed input routes before parsing an unstructured invoice amount."""
    if structured_lines and (taxable_base is not None or iva_rate is not None):
        raise InvoiceValidationError("--line cannot be combined with --taxable-base or --iva-rate")
    if structured_lines:
        parsed_taxable_base: Decimal | None = None
        parsed_iva_rate: Decimal | None = None
    else:
        if taxable_base is None:
            raise InvoiceValidationError("--taxable-base is required when --line is not supplied")
        parsed_taxable_base = parse_decimal_amount(taxable_base, label="taxable-base")
        parsed_iva_rate = parse_optional_decimal_amount(iva_rate, label="iva-rate")
    return parsed_taxable_base, parsed_iva_rate


def _raise_invoice_add_validation(
    completed: RegisteredOperationCompletion[InvoiceAddResult], added: InvoiceAddResult
) -> Never:
    """Keep the exact invoice validation refusal and its complete settled receipt."""
    details: dict[str, str] = {
        "operation_id": str(completed.operation_id),
        "terminal_condition": completed.terminal_condition.value,
        "effect": completed.effect.value,
        "refusal_code": completed.refusal_code or "",
    }
    if added.invoice_id is not None:
        details["invoice_id"] = added.invoice_id
    error = CliRefusedBoundaryError(
        translated_message=(
            "application.invoices.creation.errors.duplicate_invoice"
            if added.validation_code == "duplicate_invoice"
            else "errors.refused.refused_cli_validation_boundary"
        ),
        context=details,
    )
    raise ledger_cli_no_recovery(
        error,
        condition=CliExceptionPrecondition.LEDGER_INVOICE_VALID,
        facts={"invoice_valid": False},
    ) from None
