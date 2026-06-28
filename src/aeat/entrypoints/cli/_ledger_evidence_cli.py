"""Typer registration for ledger purchase invoice evidence commands."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.ledger import (
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
)
from ...core.i18n import tr
from ._common import (
    _bad,
    _emit_envelope,
    _parse_optional_iso_date_str,
    _state,
    _tx_repo,
    parse_optional_decimal_amount,
)
from ._ledger_payloads import (
    EvidenceAddResult,
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
        source_path: Path = typer.Argument(
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
