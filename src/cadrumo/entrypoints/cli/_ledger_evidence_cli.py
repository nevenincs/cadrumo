"""Typer registration for ledger purchase invoice evidence commands."""

from __future__ import annotations

import typer

from ...application.ledger import (
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceInputError,
    PurchaseInvoiceEvidenceNotFoundError,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
    confirm_invoice_draft_from_evidence,
    extract_invoice_draft_from_evidence,
)
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.invoices import InvoiceValidationError
from ...domain.iva import InvoiceKind
from ._common import (
    _bad,
    _emit_envelope,
    _parse_iso_date,
    _parse_optional_iso_date_str,
    _state,
    _tx_repo,
    parse_decimal_amount,
    parse_optional_decimal_amount,
)
from ._ledger_business_invoice_cli import InvoiceKindOption
from ._ledger_payloads import (
    EvidenceAddResult,
    EvidenceConfirmResult,
    EvidenceExtractResult,
    EvidenceListResult,
    EvidenceRemoveResult,
    EvidenceUpdateResult,
    EvidenceViewResult,
)

evidence_app = typer.Typer(
    name="evidence",
    help=tr(
        "cli.app.ledger.evidence.group_help",
        default="Purchase invoice evidence records (PDF or image).",
    ),
    no_args_is_help=True,
)


def register_evidence_commands(app: typer.Typer) -> None:
    """Mount and register ledger evidence commands."""
    app.add_typer(evidence_app, name="evidence")
    _register_evidence_add_command()
    _register_evidence_view_command()
    _register_evidence_list_command()
    _register_evidence_update_command()
    _register_evidence_remove_command()
    _register_evidence_extract_command()
    _register_evidence_confirm_command()


def _register_evidence_add_command() -> None:
    @evidence_app.command(
        "add",
        help=tr(
            "cli.app.ledger.evidence.add_help",
            default="Register a purchase invoice evidence record from a PDF or image file.",
        ),
    )
    def evidence_add(
        ctx: typer.Context,
        source_path: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.source_path_help", default="Path to a PDF or image receipt/invoice."),
        ),
        supplier: str | None = typer.Option(
            None,
            "--supplier",
            help=tr("cli.app.ledger.evidence.supplier_help", default="Supplier name."),
        ),
        invoice_number: str | None = typer.Option(
            None,
            "--invoice-number",
            help=tr("cli.app.ledger.evidence.invoice_number_help", default="Supplier invoice number."),
        ),
        invoice_date: str | None = typer.Option(
            None,
            "--invoice-date",
            help=tr("cli.app.ledger.evidence.invoice_date_help", default="Invoice date (ISO-8601)."),
        ),
        taxable_base: str | None = typer.Option(
            None,
            "--taxable-base",
            help=tr("cli.app.ledger.evidence.taxable_base_help", default="Taxable base (Decimal)."),
        ),
        iva_rate: str | None = typer.Option(
            None,
            "--iva-rate",
            help=tr("cli.app.ledger.evidence.iva_rate_help", default="IVA rate (Decimal)."),
        ),
        iva_amount: str | None = typer.Option(
            None,
            "--iva-amount",
            help=tr("cli.app.ledger.evidence.iva_amount_help", default="IVA amount (Decimal)."),
        ),
        notes: str = typer.Option(
            "",
            "--notes",
            help=tr("cli.app.ledger.evidence.notes_help", default="Free-text notes."),
        ),
    ) -> None:
        """Register a purchase invoice evidence record and return its id."""
        transaction_repository = _tx_repo(_state())
        result = _evidence_service().add(
            bucket_id=transaction_repository.bucket_id,
            source_path=source_path,
            supplier=supplier,
            invoice_number=invoice_number,
            invoice_date=_parse_optional_iso_date_str(invoice_date, label="invoice-date"),
            taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
            iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
            iva_amount=parse_optional_decimal_amount(iva_amount, label="iva-amount"),
            notes=notes,
        )
        payload = _evidence_payload(result.record)
        payload["bucket_event_ids"] = list(result.bucket_event_ids)
        lines = _evidence_text_lines(result.record)
        lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
        _emit_envelope(
            ctx,
            command="ledger.evidence.add",
            result=EvidenceAddResult.model_validate(payload),
            lines=lines,
        )


def _register_evidence_view_command() -> None:
    @evidence_app.command(
        "view",
        help=tr("cli.app.ledger.evidence.view_help", default="View one purchase invoice evidence record."),
    )
    def evidence_view(
        ctx: typer.Context,
        evidence_id: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.evidence_id_help", default="Evidence record id."),
        ),
    ) -> None:
        """Show one purchase invoice evidence record by id."""
        transaction_repository = _tx_repo(_state())
        record = _evidence_service().view(bucket_id=transaction_repository.bucket_id, evidence_id=evidence_id)
        _emit_envelope(
            ctx,
            command="ledger.evidence.view",
            result=EvidenceViewResult.model_validate(_evidence_payload(record)),
            lines=_evidence_text_lines(record),
        )


def _register_evidence_list_command() -> None:
    @evidence_app.command(
        "list",
        help=tr(
            "cli.app.ledger.evidence.list_help",
            default="List every purchase invoice evidence record in the active profile.",
        ),
    )
    def evidence_list(ctx: typer.Context) -> None:
        """List every purchase invoice evidence record in the active bucket."""
        transaction_repository = _tx_repo(_state())
        records = _evidence_service().list_all(bucket_id=transaction_repository.bucket_id)
        payload = {
            "bucket_id": transaction_repository.bucket_id,
            "count": len(records),
            "rows": [_evidence_payload(record) for record in records],
        }
        lines = ["evidence_id\tmedia_kind\tsupplier\tinvoice_number\tinvoice_date\ttaxable_base\tnotes"]
        for record in records:
            data = _evidence_payload(record)
            lines.append(
                f"{data['evidence_id']}\t{data['media_kind']}\t{data.get('supplier') or '-'}\t"
                f"{data.get('invoice_number') or '-'}\t{data.get('invoice_date') or '-'}\t"
                f"{data.get('taxable_base') or '-'}\t{data.get('notes') or '-'}",
            )
        _emit_envelope(
            ctx,
            command="ledger.evidence.list",
            result=EvidenceListResult.model_validate(payload),
            lines=lines,
        )


def _register_evidence_update_command() -> None:
    @evidence_app.command(
        "update",
        help=tr(
            "cli.app.ledger.evidence.update_help",
            default="Update mutable fields on a purchase invoice evidence record.",
        ),
    )
    def evidence_update(
        ctx: typer.Context,
        evidence_id: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.evidence_id_help", default="Evidence record id."),
        ),
        supplier: str | None = typer.Option(None, "--supplier"),
        invoice_number: str | None = typer.Option(None, "--invoice-number"),
        invoice_date: str | None = typer.Option(None, "--invoice-date"),
        taxable_base: str | None = typer.Option(None, "--taxable-base"),
        iva_rate: str | None = typer.Option(None, "--iva-rate"),
        iva_amount: str | None = typer.Option(None, "--iva-amount"),
        notes: str | None = typer.Option(None, "--notes"),
    ) -> None:
        """Update mutable fields on one purchase invoice evidence record."""
        transaction_repository = _tx_repo(_state())
        patch = PurchaseInvoiceEvidencePatch(
            supplier=supplier,
            invoice_number=invoice_number,
            invoice_date=_parse_optional_iso_date_str(invoice_date, label="invoice-date"),
            taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
            iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
            iva_amount=parse_optional_decimal_amount(iva_amount, label="iva-amount"),
            notes=notes,
        )
        result = _evidence_service().update(
            bucket_id=transaction_repository.bucket_id,
            evidence_id=evidence_id,
            patch=patch,
        )
        payload = _evidence_payload(result.record)
        payload["bucket_event_ids"] = list(result.bucket_event_ids)
        lines = _evidence_text_lines(result.record)
        lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
        _emit_envelope(
            ctx,
            command="ledger.evidence.update",
            result=EvidenceUpdateResult.model_validate(payload),
            lines=lines,
        )


def _register_evidence_remove_command() -> None:
    @evidence_app.command(
        "remove",
        help=tr("cli.app.ledger.evidence.remove_help", default="Delete a purchase invoice evidence record."),
    )
    def evidence_remove(
        ctx: typer.Context,
        evidence_id: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.evidence_id_help", default="Evidence record id."),
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help=tr("cli.app.ledger.evidence.yes_help", default="Confirm removal."),
        ),
    ) -> None:
        """Delete one purchase invoice evidence record."""
        if not yes:
            raise _bad(
                tr(
                    "cli.app.ledger.evidence.yes_required",
                    default="--yes is required to remove an evidence record",
                ),
            )
        transaction_repository = _tx_repo(_state())
        result = _evidence_service().remove(bucket_id=transaction_repository.bucket_id, evidence_id=evidence_id)
        payload = _evidence_payload(result.record)
        payload["bucket_event_ids"] = list(result.bucket_event_ids)
        lines = _evidence_text_lines(result.record)
        lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
        _emit_envelope(
            ctx,
            command="ledger.evidence.remove",
            result=EvidenceRemoveResult.model_validate(payload),
            lines=lines,
        )


def _register_evidence_extract_command() -> None:
    @evidence_app.command(
        "extract",
        help=tr(
            "cli.app.ledger.evidence.extract_help",
            default="Read an invoice PDF's fields on-host into a reviewable draft.",
        ),
    )
    def evidence_extract(
        ctx: typer.Context,
        evidence_id: str | None = typer.Option(
            None,
            "--evidence-id",
            help=tr(
                "cli.app.ledger.evidence.extract_evidence_id_help",
                default="Purchase invoice evidence record id to extract from.",
            ),
        ),
        attachment_id: str | None = typer.Option(
            None,
            "--attachment-id",
            help=tr(
                "cli.app.ledger.evidence.extract_attachment_id_help",
                default="Linked attachment id to extract from (alternative to --evidence-id).",
            ),
        ),
    ) -> None:
        """Run the on-host PDF text-layer extractor over stored evidence bytes.

        Reads the evidence or attachment bytes from secure storage into memory,
        runs the grounded on-host heuristics (never a cloud call, never a
        temp file: ``sensitive-financial-data-secure-storage-only``), and
        prints the best-effort :class:`InvoiceDraft` for operator review.
        Every field the heuristics could not ground in the extracted text is
        ``null`` rather than guessed. Extracting never mints or persists an
        invoice; confirm the fields, then create the record explicitly with
        ``aeat app ledger invoice add`` or ``aeat app ledger invoice
        catalogue create``.
        """
        if (evidence_id is None) == (attachment_id is None):
            raise _bad(
                tr(
                    "cli.app.ledger.evidence.extract_reference_required",
                    default="Supply exactly one of --evidence-id or --attachment-id.",
                ),
            )
        transaction_repository = _tx_repo(_state())
        try:
            draft = extract_invoice_draft_from_evidence(
                bucket_id=transaction_repository.bucket_id,
                evidence_id=evidence_id,
                attachment_id=attachment_id,
            )
        except (PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceNotFoundError) as exc:
            raise _bad(str(exc)) from exc

        payload = {
            "bucket_id": transaction_repository.bucket_id,
            "evidence_id": evidence_id,
            "attachment_id": attachment_id,
            **draft.model_dump(mode="json"),
        }
        lines = [
            f"bucket_id\t{transaction_repository.bucket_id}",
            f"evidence_id\t{evidence_id or '-'}",
            f"attachment_id\t{attachment_id or '-'}",
            f"supplier_tax_id\t{draft.supplier_tax_id or '-'}",
            f"invoice_number\t{draft.invoice_number or '-'}",
            f"invoice_date\t{draft.invoice_date or '-'}",
            f"taxable_base\t{draft.taxable_base if draft.taxable_base is not None else '-'}",
            f"iva_rate\t{draft.iva_rate if draft.iva_rate is not None else '-'}",
            f"iva_amount\t{draft.iva_amount if draft.iva_amount is not None else '-'}",
            f"grand_total\t{draft.grand_total if draft.grand_total is not None else '-'}",
            f"raw_text_length\t{draft.raw_text_length}",
        ]
        # `extract_invoice_draft_from_evidence` raises when the resolved PDF has
        # no usable text layer at all (scan-only / XFA), so a returned draft
        # always carries `raw_text_length > 0`; the review hint below is
        # therefore unconditional.
        reviewed_reference = evidence_id or attachment_id or ""
        notices: list[Notice] = [
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.extract.review_hint",
                message=tr(
                    "cli.app.ledger.evidence.extract_review_hint_message",
                    default=("This is a best-effort draft; confirm every field before minting an invoice."),
                ),
                suggestion=(
                    "aeat app ledger invoice catalogue create --kind received "
                    f"--counterparty-nif {draft.supplier_tax_id or '<nif>'} "
                    f"--invoice-number {draft.invoice_number or '<number>'} "
                    f"--invoice-date {draft.invoice_date or '<yyyy-mm-dd>'} "
                    f"--taxable-base {draft.taxable_base if draft.taxable_base is not None else '<base>'} "
                    f"--iva-rate {draft.iva_rate if draft.iva_rate is not None else '<rate>'}"
                ),
                context={"reference": reviewed_reference},
            ),
        ]
        _emit_envelope(
            ctx,
            command="ledger.evidence.extract",
            result=EvidenceExtractResult.model_validate(payload),
            lines=lines,
            notices=notices,
        )


def _register_evidence_confirm_command() -> None:
    @evidence_app.command(
        "confirm",
        help=tr(
            "cli.app.ledger.evidence.confirm_help",
            default="Re-extract evidence on-host and confirm it into a real catalogue Invoice.",
        ),
    )
    def evidence_confirm(
        ctx: typer.Context,
        kind: InvoiceKindOption = typer.Option(
            ...,
            "--kind",
            help=tr(
                "cli.app.ledger.invoice.kind_help",
                default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
            ),
        ),
        evidence_id: str | None = typer.Option(
            None,
            "--evidence-id",
            help=tr(
                "cli.app.ledger.evidence.extract_evidence_id_help",
                default="Purchase invoice evidence record id to extract from.",
            ),
        ),
        attachment_id: str | None = typer.Option(
            None,
            "--attachment-id",
            help=tr(
                "cli.app.ledger.evidence.extract_attachment_id_help",
                default="Linked attachment id to extract from (alternative to --evidence-id).",
            ),
        ),
        counterparty_nif: str | None = typer.Option(
            None,
            "--counterparty-nif",
            help=tr(
                "cli.app.ledger.evidence.confirm_counterparty_nif_help",
                default="Override the extracted supplier tax id.",
            ),
        ),
        counterparty_name: str | None = typer.Option(
            None,
            "--counterparty-name",
            help=tr(
                "cli.app.ledger.evidence.confirm_counterparty_name_help",
                default="Counterparty display name (no extraction heuristic yet; normally required).",
            ),
        ),
        invoice_number: str | None = typer.Option(
            None,
            "--invoice-number",
            help=tr(
                "cli.app.ledger.evidence.confirm_invoice_number_help",
                default="Override the extracted invoice number.",
            ),
        ),
        invoice_date: str | None = typer.Option(
            None,
            "--invoice-date",
            help=tr(
                "cli.app.ledger.evidence.confirm_invoice_date_help",
                default="Override the extracted invoice date (YYYY-MM-DD).",
            ),
        ),
        taxable_base: str | None = typer.Option(
            None,
            "--taxable-base",
            help=tr(
                "cli.app.ledger.evidence.confirm_taxable_base_help",
                default="Override the extracted taxable base.",
            ),
        ),
        iva_rate: str | None = typer.Option(
            None,
            "--iva-rate",
            help=tr(
                "cli.app.ledger.evidence.confirm_iva_rate_help",
                default="Override the extracted IVA rate (omit to keep the extracted value).",
            ),
        ),
        country_code: str = typer.Option(
            "ES",
            "--country-code",
            help=tr(
                "cli.app.ledger.invoice.catalogue.country_code_help",
                default="Counterparty ISO 3166-1 alpha-2 country code.",
            ),
        ),
        currency: str = typer.Option(
            "EUR",
            "--currency",
            help=tr("cli.app.ledger.evidence.confirm_currency_help", default="ISO-4217 currency code."),
        ),
        notes: str = typer.Option(
            "",
            "--notes",
            help=tr("cli.app.ledger.evidence.notes_help", default="Free-text notes."),
        ),
    ) -> None:
        """Non-interactively confirm a reviewed evidence extraction into an Invoice.

        Re-runs the on-host extraction (never a cloud call, never a temp
        file), layers any supplied override on top of each extracted field,
        and delegates the write to the sole sanctioned catalogue-invoice
        writer. A confirm whose resolved fields match an already-persisted
        invoice is a guarded no-op: the existing invoice is returned
        unchanged (``created: false``) rather than raising or duplicating.
        """
        _run_evidence_confirm(
            ctx=ctx,
            kind=kind,
            evidence_id=evidence_id,
            attachment_id=attachment_id,
            counterparty_nif=counterparty_nif,
            counterparty_name=counterparty_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            taxable_base=taxable_base,
            iva_rate=iva_rate,
            country_code=country_code,
            currency=currency,
            notes=notes,
        )


def _run_evidence_confirm(
    *,
    ctx: typer.Context,
    kind: InvoiceKindOption,
    evidence_id: str | None,
    attachment_id: str | None,
    counterparty_nif: str | None,
    counterparty_name: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    taxable_base: str | None,
    iva_rate: str | None,
    country_code: str,
    currency: str,
    notes: str,
) -> None:
    if (evidence_id is None) == (attachment_id is None):
        raise _bad(
            tr(
                "cli.app.ledger.evidence.extract_reference_required",
                default="Supply exactly one of --evidence-id or --attachment-id.",
            ),
        )
    transaction_repository = _tx_repo(_state())
    bucket_id = transaction_repository.bucket_id
    try:
        result = confirm_invoice_draft_from_evidence(
            bucket_id=bucket_id,
            kind=InvoiceKind(kind.value),
            counterparty_country=country_code,
            evidence_id=evidence_id,
            attachment_id=attachment_id,
            counterparty_tax_id=counterparty_nif,
            counterparty_name=counterparty_name,
            invoice_number=invoice_number,
            invoice_date=_parse_iso_date(invoice_date, label="invoice-date") if invoice_date else None,
            taxable_base=parse_decimal_amount(taxable_base, label="taxable-base") if taxable_base else None,
            iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
            currency=currency,
            notes=notes,
        )
    except (PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceNotFoundError) as exc:
        raise _bad(str(exc)) from exc
    except InvoiceValidationError as exc:
        raise _bad(str(exc)) from exc

    invoice = result.invoice
    payload = {
        "bucket_id": bucket_id,
        "evidence_id": evidence_id,
        "attachment_id": attachment_id,
        "created": result.created,
        "invoice_id": invoice.invoice_id,
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
    lines = [
        f"bucket_id\t{bucket_id}",
        f"evidence_id\t{evidence_id or '-'}",
        f"attachment_id\t{attachment_id or '-'}",
        f"created\t{result.created}",
        f"invoice_id\t{invoice.invoice_id}",
        f"kind\t{invoice.kind.value}",
        f"counterparty_name\t{invoice.counterparty_name}",
        f"counterparty_tax_id\t{invoice.counterparty_tax_id}",
        f"invoice_number\t{invoice.invoice_number}",
        f"issued_at\t{invoice.issued_at.isoformat()}",
        f"grand_total\t{format(invoice.grand_total, 'f')}",
        f"currency\t{invoice.currency}",
    ]
    notices: list[Notice] = []
    if not result.created:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.confirm.already_exists",
                message=tr(
                    "cli.app.ledger.evidence.confirm_already_exists_message",
                    default=(
                        "An invoice with this identity already exists; returning it unchanged "
                        "rather than creating a duplicate."
                    ),
                ),
                context={"invoice_id": invoice.invoice_id},
            ),
        )
    else:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.confirm.linked_transaction_hint",
                message=tr(
                    "cli.app.ledger.evidence.confirm_link_hint_message",
                    default="Link this invoice to a ledger transaction with `aeat app ledger link`.",
                ),
                suggestion=f"aeat app ledger link <transaction-id> --invoice-id {invoice.invoice_id}",
                context={"invoice_id": invoice.invoice_id},
            ),
        )
    _emit_envelope(
        ctx,
        command="ledger.evidence.confirm",
        result=EvidenceConfirmResult.model_validate(payload),
        lines=lines,
        notices=notices,
    )


def _evidence_service() -> PurchaseInvoiceEvidenceService:
    return PurchaseInvoiceEvidenceService()


def _evidence_payload(record: PurchaseInvoiceEvidence) -> dict[str, object]:
    return record.model_dump(mode="json")


def _evidence_text_lines(record: PurchaseInvoiceEvidence) -> list[str]:
    payload = _evidence_payload(record)
    return [
        f"evidence_id\t{payload['evidence_id']}",
        f"bucket_id\t{payload['bucket_id']}",
        f"source_path\t{payload['source_path']}",
        f"source_sha256\t{payload['source_sha256']}",
        f"media_kind\t{payload['media_kind']}",
        f"supplier\t{payload.get('supplier') or '-'}",
        f"invoice_number\t{payload.get('invoice_number') or '-'}",
        f"invoice_date\t{payload.get('invoice_date') or '-'}",
        f"taxable_base\t{payload.get('taxable_base') or '-'}",
        f"iva_rate\t{payload.get('iva_rate') or '-'}",
        f"iva_amount\t{payload.get('iva_amount') or '-'}",
        f"notes\t{payload.get('notes') or '-'}",
        f"created_at\t{payload['created_at']}",
        f"updated_at\t{payload['updated_at']}",
    ]


__all__ = ["evidence_app", "register_evidence_commands"]
