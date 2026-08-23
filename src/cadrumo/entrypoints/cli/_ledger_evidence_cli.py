"""Typer registration for ledger purchase invoice evidence commands."""

from __future__ import annotations

from typing import TypedDict

import typer

from ...application.cli_exception_preconditions import CliExceptionPrecondition
from ...application.ledger import (
    FindingResolution,
    InvoiceConfirmationResult,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
    confirm_invoice_draft_from_evidence,
    extract_invoice_draft_from_evidence,
    get_attachment_review_item,
    list_attachment_review_queue,
)
from ...application.user_profile import cloud_evidence_upload_eligible_for_active_profile
from ...core import IntracomOperationType
from ...core.config import load_settings
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.invoices import InvoiceClass, InvoiceValidationError
from ...domain.iva import InvoiceKind, SupplyNature
from ...llm import EvidenceConsentToken, LLMProvider, mint_evidence_consent_token
from ._command_policy import command_execution_policy
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
from ._evidence_field_notices import field_degradation_notices
from ._ledger_business_invoice_cli import _catalogue_invoice_shared_fields
from ._ledger_evidence_batch_cli import register_evidence_batch_command
from ._ledger_evidence_confirm_notices import confirm_resolution_lines, confirm_resolution_notices
from ._ledger_evidence_consent_cli import register_evidence_consent_commands
from ._ledger_evidence_review_cli import parse_finding_resolution, register_evidence_review_commands
from ._ledger_execution_policies import (
    LEDGER_DESTRUCTIVE,
    LEDGER_NETWORK_WRITE,
    LEDGER_READ,
    LEDGER_WRITE,
    declare_metadata_group,
)
from ._ledger_payloads import (
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceAddResult,
    EvidenceConfirmResult,
    EvidenceExtractResult,
    EvidenceListResult,
    EvidenceRemoveResult,
    EvidenceUpdateResult,
    EvidenceViewResult,
)
from ._ledger_support import _ledger_cli_no_recovery

evidence_app = typer.Typer(
    name="evidence",
    help=tr("cli.app.ledger.evidence.group_help"),
    no_args_is_help=True,
)
declare_metadata_group(evidence_app)


class _InvoiceClassKwarg(TypedDict, total=False):
    """Optional keyword passed only when the operator supplied an invoice class."""

    invoice_class: InvoiceClass


def register_evidence_commands(app: typer.Typer) -> None:
    """Mount and register ledger evidence commands."""
    app.add_typer(evidence_app, name="evidence")
    _register_evidence_add_command()
    _register_evidence_view_command()
    _register_evidence_list_command()
    _register_attachment_review_commands()
    _register_evidence_update_command()
    _register_evidence_remove_command()
    _register_evidence_extract_command()
    _register_evidence_confirm_command()
    register_evidence_batch_command(evidence_app)
    register_evidence_consent_commands(evidence_app)
    register_evidence_review_commands(evidence_app)


def _attachment_store(bucket_id: str):
    """Build the active bucket's encrypted attachment repository."""
    from ...adapters.persistence.storage import AttachmentStore, secure_object_repository_for_bucket

    return AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, load_settings()))


def _attachment_review_payload(item: object) -> dict[str, object]:
    payload = item.model_dump(mode="json")
    if not isinstance(payload, dict):
        raise TypeError("attachment review payload must be a mapping")
    return payload


def _attachment_review_lines(payload: dict[str, object]) -> list[str]:
    return [
        f"attachment_id\t{payload['attachment_id']}",
        f"sha256\t{payload['sha256']}",
        f"mime_type\t{payload['mime_type']}",
        f"bytes_size\t{payload['bytes_size']}",
        f"source\t{payload['source']}",
        f"provider_locator\t{payload['provider_locator']}",
        f"captured_at\t{payload['captured_at']}",
        f"pending_review\t{payload['pending_review']}",
        f"linked_invoice_ids\t{','.join(payload['linked_invoice_ids'])}",
    ]


def _register_attachment_review_commands() -> None:
    @evidence_app.command("attachment-queue", help=tr("cli.app.ledger.evidence.attachment_queue_help"))
    @command_execution_policy(LEDGER_READ)
    def attachment_queue(ctx: typer.Context) -> None:
        """List Drive attachments that still require invoice review."""
        bucket_id = _tx_repo(_state()).bucket_id
        rows = list_attachment_review_queue(_attachment_store(bucket_id))
        payloads = [_attachment_review_payload(row) for row in rows]
        _emit_envelope(
            ctx,
            command="ledger.evidence.attachment_queue",
            result=AttachmentReviewQueueResult.model_validate(
                {"bucket_id": bucket_id, "count": len(payloads), "rows": payloads},
            ),
            lines=[line for payload in payloads for line in _attachment_review_lines(payload)],
        )

    @evidence_app.command("attachment-view", help=tr("cli.app.ledger.evidence.attachment_view_help"))
    @command_execution_policy(LEDGER_READ)
    def attachment_view(
        ctx: typer.Context,
        attachment_id: str = typer.Argument(..., help=tr("cli.app.ledger.evidence.attachment_id_help")),
    ) -> None:
        """Inspect non-secret metadata and provenance for one attachment."""
        bucket_id = _tx_repo(_state()).bucket_id
        item = get_attachment_review_item(_attachment_store(bucket_id), attachment_id)
        payload = {"bucket_id": bucket_id, **_attachment_review_payload(item)}
        _emit_envelope(
            ctx,
            command="ledger.evidence.attachment_view",
            result=AttachmentReviewViewResult.model_validate(payload),
            lines=[f"bucket_id\t{bucket_id}", *_attachment_review_lines(payload)],
        )


def _register_evidence_add_command() -> None:
    @evidence_app.command(
        "add",
        help=tr("cli.app.ledger.evidence.add_help"),
    )
    @command_execution_policy(LEDGER_WRITE)
    def evidence_add(
        ctx: typer.Context,
        source_path: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.source_path_help"),
        ),
        supplier: str | None = typer.Option(
            None,
            "--supplier",
            help=tr("cli.app.ledger.evidence.supplier_help"),
        ),
        invoice_number: str | None = typer.Option(
            None,
            "--invoice-number",
            help=tr("cli.app.ledger.evidence.invoice_number_help"),
        ),
        invoice_date: str | None = typer.Option(
            None,
            "--invoice-date",
            help=tr("cli.app.ledger.evidence.invoice_date_help"),
        ),
        taxable_base: str | None = typer.Option(
            None,
            "--taxable-base",
            help=tr("cli.app.ledger.evidence.taxable_base_help"),
        ),
        iva_rate: str | None = typer.Option(
            None,
            "--iva-rate",
            help=tr("cli.app.ledger.evidence.iva_rate_help"),
        ),
        iva_amount: str | None = typer.Option(
            None,
            "--iva-amount",
            help=tr("cli.app.ledger.evidence.iva_amount_help"),
        ),
        notes: str = typer.Option(
            "",
            "--notes",
            help=tr("cli.app.ledger.evidence.notes_help"),
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
        help=tr("cli.app.ledger.evidence.view_help"),
    )
    @command_execution_policy(LEDGER_READ)
    def evidence_view(
        ctx: typer.Context,
        evidence_id: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.evidence_id_help"),
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
        help=tr("cli.app.ledger.evidence.list_help"),
    )
    @command_execution_policy(LEDGER_READ)
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
        help=tr("cli.app.ledger.evidence.update_help"),
    )
    @command_execution_policy(LEDGER_WRITE)
    def evidence_update(
        ctx: typer.Context,
        evidence_id: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.evidence_id_help"),
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
        help=tr("cli.app.ledger.evidence.remove_help"),
    )
    @command_execution_policy(LEDGER_DESTRUCTIVE)
    def evidence_remove(
        ctx: typer.Context,
        evidence_id: str = typer.Argument(
            ...,
            help=tr("cli.app.ledger.evidence.evidence_id_help"),
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help=tr("cli.app.ledger.evidence.yes_help"),
        ),
    ) -> None:
        """Delete one purchase invoice evidence record."""
        if not yes:
            raise _bad(
                tr("cli.app.ledger.evidence.yes_required"),
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


#: Operator surface recorded on a token this command mints. Names the exact verb
#: rather than "cli", because a withdrawal survey answers "where was this
#: acknowledged" and a whole-entrypoint label cannot.
_EXTRACT_CONSENT_SURFACE = "cli:ledger.evidence.extract"


def _mint_extract_consent(
    *,
    bucket_id: str,
    evidence_id: str | None,
    off_host_provider: LLMProvider | None,
    acknowledged: bool,
) -> EvidenceConsentToken | None:
    """Return the token authorising ONE off-host read, or ``None`` for the on-host default.

    Both flags absent is the overwhelmingly common call and returns ``None``
    immediately: no token, no provider override, behaviour identical to before
    this option existed. Everything below runs only when an operator has
    explicitly asked for an off-host read.

    The two flags are required TOGETHER, and each missing half refuses rather
    than being absorbed. A provider without the acknowledgement would send a
    taxpayer's document off-host on a flag that does not say so; an
    acknowledgement without a provider takes a consent and then changes nothing,
    which is worse than not asking, because it trains an operator to believe the
    prompt is meaningless.

    Nothing here is stored. There is no config key and no profile field behind
    either flag -- a stored acknowledgement would be exactly the standing
    enablement the default-off posture exists to prevent, and it would decay
    into consent nobody remembers granting.

    Returns:
        The minted token, or ``None`` when no off-host read was requested.

    Raises:
        typer.BadParameter: When the flags are supplied incompletely, when the
            provider names the on-host default, when the read has no
            content-addressable evidence record behind it, or when the consent
            gate refuses this invocation.
    """
    if off_host_provider is None and not acknowledged:
        return None
    if off_host_provider is None:
        raise _bad(
            tr("cli.app.ledger.evidence.extract_acknowledge_without_provider"),
        )
    if off_host_provider is LLMProvider.LOCAL:
        raise _bad(
            tr("cli.app.ledger.evidence.extract_off_host_provider_is_local"),
        )
    if not acknowledged:
        raise _bad(
            tr("cli.app.ledger.evidence.extract_provider_without_acknowledge"),
        )

    # The token binds to the BYTES, so a read with no content-addressable record
    # behind it cannot mint one. An attachment-only extract is exactly that case:
    # an id names the bytes but does not fingerprint them, and recording one as
    # the other would let a later withdrawal believe it had proved a match it
    # never checked.
    if evidence_id is None:
        raise _bad(
            tr("cli.app.ledger.evidence.extract_off_host_needs_evidence_id"),
        )
    record = PurchaseInvoiceEvidenceService().view(bucket_id=bucket_id, evidence_id=evidence_id)
    content_address = record.source_sha256
    if not content_address:
        raise _bad(
            tr("cli.app.ledger.evidence.extract_off_host_needs_content_address"),
        )

    return mint_evidence_consent_token(
        settings=load_settings(),
        # The SINGLE production reading of the standing per-profile bar. Passed
        # through rather than re-decided here: the minting path refuses when it
        # is false, so a surface cannot widen the posture by forgetting it.
        profile_eligible=cloud_evidence_upload_eligible_for_active_profile(),
        acknowledged=acknowledged,
        surface=_EXTRACT_CONSENT_SURFACE,
        evidence_content_address=content_address,
    )


def _register_evidence_extract_command() -> None:
    @evidence_app.command(
        "extract",
        help=tr("cli.app.ledger.evidence.extract_help"),
    )
    @command_execution_policy(LEDGER_NETWORK_WRITE)
    def evidence_extract(
        ctx: typer.Context,
        evidence_id: str | None = typer.Option(
            None,
            "--evidence-id",
            help=tr("cli.app.ledger.evidence.extract_evidence_id_help"),
        ),
        attachment_id: str | None = typer.Option(
            None,
            "--attachment-id",
            help=tr("cli.app.ledger.evidence.extract_attachment_id_help"),
        ),
        off_host_provider: LLMProvider | None = typer.Option(
            None,
            "--off-host-provider",
            help=tr("cli.app.ledger.evidence.extract_off_host_provider_help"),
        ),
        acknowledge_off_host: bool = typer.Option(
            False,
            "--acknowledge-off-host",
            help=tr("cli.app.ledger.evidence.extract_acknowledge_off_host_help"),
        ),
    ) -> None:
        """Run the on-host PDF text-layer extractor over stored evidence bytes.

        Reads the evidence or attachment bytes from secure storage into memory,
        runs the grounded on-host heuristics (never a cloud call, never a
        temp file: ``sensitive-financial-data-secure-storage-only``), and
        prints the best-effort :class:`InvoiceDraft` for operator review.
        Every field the heuristics could not ground in the extracted text is
        ``null`` rather than guessed. Extracting never mints or persists an
        invoice; confirmation is a separate operator action.
        """
        if (evidence_id is None) == (attachment_id is None):
            raise _bad(
                tr("cli.app.ledger.evidence.extract_reference_required"),
            )
        transaction_repository = _tx_repo(_state())
        consent_token = _mint_extract_consent(
            bucket_id=transaction_repository.bucket_id,
            evidence_id=evidence_id,
            off_host_provider=off_host_provider,
            acknowledged=acknowledge_off_host,
        )
        draft = extract_invoice_draft_from_evidence(
            bucket_id=transaction_repository.bucket_id,
            evidence_id=evidence_id,
            attachment_id=attachment_id,
            off_host_provider=off_host_provider,
            consent_token=consent_token,
        )

        payload = {
            "bucket_id": transaction_repository.bucket_id,
            "evidence_id": evidence_id,
            "attachment_id": attachment_id,
            **draft.model_dump(mode="json"),
            # Read off the TOKEN rather than off the flags. A flag says what the
            # operator asked for; the token exists only because the deployment
            # posture, the profile bar and the acknowledgement all permitted it,
            # so it is the nearest thing to an observation this surface holds.
            "off_host_provider": None if consent_token is None else off_host_provider,
            "off_host_acknowledged_surface": None if consent_token is None else consent_token.surface,
        }
        lines = [
            f"bucket_id\t{transaction_repository.bucket_id}",
            f"evidence_id\t{evidence_id or '-'}",
            f"attachment_id\t{attachment_id or '-'}",
            f"supplier_tax_id\t{draft.supplier_tax_id or '-'}",
            f"supplier_name\t{draft.supplier_name or '-'}",
            f"customer_tax_id\t{draft.customer_tax_id or '-'}",
            f"customer_name\t{draft.customer_name or '-'}",
            f"invoice_number\t{draft.invoice_number or '-'}",
            f"invoice_series\t{draft.invoice_series or '-'}",
            f"invoice_date\t{draft.invoice_date or '-'}",
            f"taxable_base\t{draft.taxable_base if draft.taxable_base is not None else '-'}",
            f"iva_rate\t{draft.iva_rate if draft.iva_rate is not None else '-'}",
            f"iva_amount\t{draft.iva_amount if draft.iva_amount is not None else '-'}",
            f"grand_total\t{draft.grand_total if draft.grand_total is not None else '-'}",
            f"currency\t{draft.currency if draft.currency is not None else '-'}",
            f"retencion_rate\t{draft.retencion_rate if draft.retencion_rate is not None else '-'}",
            f"retencion_amount\t{draft.retencion_amount if draft.retencion_amount is not None else '-'}",
            f"suplidos_amount\t{draft.suplidos_amount if draft.suplidos_amount is not None else '-'}",
            f"suggested_kind\t{draft.suggested_kind.value if draft.suggested_kind is not None else '-'}",
            f"transcription_sha256\t{draft.transcription_sha256 or '-'}",
            # The text surface cannot carry a per-field envelope legibly, so it
            # carries the COUNT and the JSON payload carries the envelopes. A
            # count of zero is honest -- it says no provenance was recorded, not
            # that the values were exact.
            f"provenance_fields\t{len(draft.provenance)}",
            f"discrepancies\t{len(draft.discrepancies)}",
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
                ),
                context={
                    "reference": reviewed_reference,
                },
            ),
        ]
        # Per-field degradation, so a thin read is distinguishable from a clean
        # one. The reading path raises on neither, and the field COUNT above
        # cannot say which fields failed a check or why.
        notices.extend(field_degradation_notices(draft.provenance))
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
        help=tr("cli.app.ledger.evidence.confirm_help"),
    )
    @command_execution_policy(LEDGER_NETWORK_WRITE)
    def evidence_confirm(
        ctx: typer.Context,
        kind: InvoiceKind = typer.Option(
            ...,
            "--kind",
            help=tr("cli.app.ledger.invoice.kind_help"),
        ),
        evidence_id: str | None = typer.Option(
            None,
            "--evidence-id",
            help=tr("cli.app.ledger.evidence.extract_evidence_id_help"),
        ),
        attachment_id: str | None = typer.Option(
            None,
            "--attachment-id",
            help=tr("cli.app.ledger.evidence.extract_attachment_id_help"),
        ),
        counterparty_nif: str | None = typer.Option(
            None,
            "--counterparty-nif",
            help=tr("cli.app.ledger.evidence.confirm_counterparty_nif_help"),
        ),
        counterparty_name: str | None = typer.Option(
            None,
            "--counterparty-name",
            help=tr("cli.app.ledger.evidence.confirm_counterparty_name_help"),
        ),
        invoice_number: str | None = typer.Option(
            None,
            "--invoice-number",
            help=tr("cli.app.ledger.evidence.confirm_invoice_number_help"),
        ),
        invoice_date: str | None = typer.Option(
            None,
            "--invoice-date",
            help=tr("cli.app.ledger.evidence.confirm_invoice_date_help"),
        ),
        taxable_base: str | None = typer.Option(
            None,
            "--taxable-base",
            help=tr("cli.app.ledger.evidence.confirm_taxable_base_help"),
        ),
        iva_rate: str | None = typer.Option(
            None,
            "--iva-rate",
            help=tr("cli.app.ledger.evidence.confirm_iva_rate_help"),
        ),
        country_code: str = typer.Option(
            ...,
            "--country-code",
            help=tr("cli.app.ledger.invoice.country_code_help"),
        ),
        currency: str | None = typer.Option(
            None,
            "--currency",
            help=tr("cli.app.ledger.evidence.confirm_currency_help"),
        ),
        operation_type: IntracomOperationType | None = typer.Option(
            None,
            "--operation-type",
            help=tr("cli.app.ledger.evidence.confirm_operation_type_help"),
        ),
        supply_nature: SupplyNature | None = typer.Option(
            None,
            "--supply-nature",
            help=tr("cli.app.ledger.evidence.confirm_supply_nature_help"),
        ),
        invoice_class: InvoiceClass | None = typer.Option(
            None,
            "--invoice-class",
            help=tr("cli.app.ledger.evidence.confirm_invoice_class_help"),
        ),
        rectifies: str | None = typer.Option(
            None,
            "--rectifies",
            help=tr("cli.app.ledger.evidence.confirm_rectifies_help"),
        ),
        series: str | None = typer.Option(
            None,
            "--series",
            help=tr("cli.app.ledger.evidence.confirm_series_help"),
        ),
        notes: str = typer.Option(
            "",
            "--notes",
            help=tr("cli.app.ledger.evidence.notes_help"),
        ),
        resolve: list[str] = typer.Option(
            [],
            "--resolve",
            help=tr("cli.app.ledger.evidence.confirm_resolve_help"),
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
            operation_type=operation_type,
            supply_nature=supply_nature,
            invoice_class=invoice_class,
            rectifies=rectifies,
            series=series,
            notes=notes,
            resolve=resolve,
        )


def _run_evidence_confirm(
    *,
    ctx: typer.Context,
    kind: InvoiceKind,
    evidence_id: str | None,
    attachment_id: str | None,
    counterparty_nif: str | None,
    counterparty_name: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    taxable_base: str | None,
    iva_rate: str | None,
    country_code: str,
    currency: str | None,
    operation_type: IntracomOperationType | None,
    supply_nature: SupplyNature | None,
    invoice_class: InvoiceClass | None,
    rectifies: str | None,
    series: str | None,
    notes: str,
    resolve: list[str],
) -> None:
    if (evidence_id is None) == (attachment_id is None):
        raise _bad(
            tr("cli.app.ledger.evidence.extract_reference_required"),
        )
    transaction_repository = _tx_repo(_state())
    bucket_id = transaction_repository.bucket_id
    resolutions: list[FindingResolution] = [parse_finding_resolution(raw) for raw in resolve]
    try:
        result = confirm_invoice_draft_from_evidence(
            bucket_id=bucket_id,
            kind=kind,
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
            operation_type=operation_type,
            supply_nature=supply_nature,
            # Omitted rather than defaulted when the operator says nothing, so the
            # DOCUMENT's own statement stands. Passing ORDINARIA here would
            # override a rectificativa the reader correctly recovered.
            **_invoice_class_kwarg(invoice_class),
            rectifies_invoice_number=rectifies,
            series=series,
            notes=notes,
            resolutions=resolutions,
        )
    except InvoiceValidationError as exc:
        raise _ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_INVOICE_VALID,
            facts={"error_type": type(exc).__name__},
        ) from None

    invoice = result.invoice
    payload = {
        "bucket_id": bucket_id,
        "evidence_id": evidence_id,
        "attachment_id": attachment_id,
        "created": result.created,
        **_catalogue_invoice_shared_fields(invoice),
        # Read off the draft the confirmation was based on, so the how-was-this-
        # obtained record reaches the operator on the confirm surface too and not
        # only on extract. `result.draft` is the pre-override extraction, which is
        # exactly the thing the provenance describes.
        "provenance": [envelope.model_dump(mode="json") for envelope in result.draft.provenance],
        "discrepancies": [finding.model_dump(mode="json") for finding in result.draft.discrepancies],
        # The confirmed view, beside the document's own. An operator-asserted
        # field reads OPERATOR here while `provenance` still shows what the
        # document said, which is the pairing the confirmation record persists.
        "confirmed_provenance": [envelope.model_dump(mode="json") for envelope in result.confirmed_provenance],
        "confirmation_id": result.confirmation_id,
        # Which IVA treatment this record got and which rung established it.
        # Result data rather than a diagnostic: a consumer enumerating the
        # weakly-placed records is asking about what was written, and before
        # this it could only find them by re-running the resolution.
        "iva_category": _resolved_category(result),
        "iva_category_outcome": _resolved_outcome(result),
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
    if result.total_discrepancy is not None:
        # The derived total stands; this only reports that the document disagrees
        # with it. A recargo de equivalencia, an unread rate that fell back to the
        # EXEMPT slot, or a misread base all surface here as a figure the record
        # could not represent -- silently dropping the printed total is what let
        # those through.
        discrepancy = result.total_discrepancy
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.confirm.printed_total_mismatch",
                message=tr(
                    "cli.app.ledger.evidence.confirm_printed_total_mismatch_message",
                ),
                context={
                    "printed_total": format(discrepancy.printed_total, "f"),
                    "recorded_total": format(discrepancy.recorded_total, "f"),
                    "difference": format(discrepancy.difference, "f"),
                    "currency": invoice.currency,
                },
            ),
        )
    if not result.created:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.confirm.already_exists",
                message=tr(
                    "cli.app.ledger.evidence.confirm_already_exists_message",
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
                ),
                context={
                    "invoice_id": invoice.invoice_id,
                },
            ),
        )
    # The confirm surface describes the SAME pre-override draft, so the operator
    # sees why a field they are about to accept was not corroborated.
    notices.extend(field_degradation_notices(result.draft.provenance))
    # What the confirm path resolved about the operation's IVA treatment and
    # what it left open. Every one of these was computed on this call and read
    # by nobody before this line.
    notices.extend(confirm_resolution_notices(result.establishment))
    lines.extend(confirm_resolution_lines(result.establishment))
    _emit_envelope(
        ctx,
        command="ledger.evidence.confirm",
        result=EvidenceConfirmResult.model_validate(payload),
        lines=lines,
        notices=notices,
    )


def _resolved_category(result: InvoiceConfirmationResult) -> str | None:
    """Return the IVA treatment this confirm recorded, or ``None`` where none was.

    ``None`` is a real answer here and not an absence of information: it is what
    a withheld relief claim, a self-contradicting document and an unplaceable
    operation all leave behind, and the accompanying outcome says which.
    """
    if result.establishment is None or result.establishment.category.category is None:
        return None
    return result.establishment.category.category.value


def _resolved_outcome(result: InvoiceConfirmationResult) -> str | None:
    """Return which rung established the treatment, or why none did.

    Emitted beside the category rather than folded into it, because the pair is
    the whole point: a category on the weakest rung and one the rule table placed
    outright are the same string, and only this field tells them apart.
    """
    if result.establishment is None:
        return None
    return result.establishment.category.outcome.value


def _invoice_class_kwarg(invoice_class: InvoiceClass | None) -> _InvoiceClassKwarg:
    """Keep an omitted invoice class omitted so document-derived defaults survive."""
    if invoice_class is None:
        return {}
    return {"invoice_class": invoice_class}


def _evidence_service() -> PurchaseInvoiceEvidenceService:
    return PurchaseInvoiceEvidenceService()


def _evidence_payload(record: PurchaseInvoiceEvidence) -> dict[str, object]:
    dumped = record.model_dump(mode="json")
    if not isinstance(dumped, dict):
        raise TypeError("evidence payload dump must be a mapping")
    payload: dict[str, object] = {}
    for key, value in dumped.items():
        if not isinstance(key, str):
            raise TypeError("evidence payload keys must be text")
        payload[key] = value
    return payload


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
