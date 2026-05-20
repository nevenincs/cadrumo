from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol

import typer

from ...application.export import ExportSerializationFormat
from ...application.ledger import (
    LedgerExportCommand,
    LedgerReviewQuery,
    LedgerSourceImportCommand,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
    SplitChildCommand,
    archive_manual_transaction,
    attach_manual_transaction_evidence,
    compute_display_id_width,
    create_manual_transaction,
    export_ledger_transactions,
    get_manual_transaction,
    import_ledger_source,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_review_payload,
    ledger_transaction_review_status,
    ledger_transaction_tracking_payload,
    list_manual_transactions,
    merge_transactions,
    query_ledger_review_rows,
    remove_manual_transaction,
    reset_ledger_catalogue,
    resolve_transaction_id,
    split_transaction,
    stash_manual_transaction,
    summarize_manual_transactions,
    update_manual_transaction_fields,
)
from ...application.review import (
    FilterParseError,
    LedgerReviewFilterSpec,
)
from ...application.workflow._models import resolve_active_bucket_id
from ...core.i18n import tr
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionIdPrefixError,
)
from ._common import (
    _bad,
    _canonical_period,
    _emit,
    _parse_iso_date,
    _state,
    _tx_repo,
)

app = typer.Typer(
    name="ledger",
    help=tr("cli.ledger.app_help"),
    no_args_is_help=True,
)


def _parse_decimal(raw: str | None, *, label: str) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError) as exc:
        raise _bad(tr("cli.ledger.errors.invalid_decimal", label=label, raw=raw)) from exc


def _parse_required_decimal(raw: str, *, label: str) -> Decimal:
    parsed = _parse_decimal(raw, label=label)
    assert parsed is not None
    return parsed


class _TransactionRepo(Protocol):
    """Structural interface consumed by `_bucket_transaction_ids` and `_resolve_id`."""

    @property
    def bucket_id(self) -> str: ...


def _bucket_transaction_ids(transaction_repository: _TransactionRepo) -> tuple[str, ...]:
    """Return the full transaction ids known to the active bucket."""
    bucket_id = transaction_repository.bucket_id
    results = list_manual_transactions(
        bucket_id=bucket_id,
        transaction_repository=transaction_repository
        if isinstance(transaction_repository, TransactionCatalogueRepository)
        else None,
    )
    return tuple(result.transaction.transaction_id for result in results)


def _resolve_id(transaction_repository: _TransactionRepo, prefix: str) -> str:
    """Resolve a CLI-supplied id or unambiguous prefix to a full transaction id.

    Wraps the domain-layer :exc:`TransactionIdPrefixError` into ``tr()``-
    rendered messages routed through ``_bad`` so the operator sees a
    locale-translated explanation rather than a raw Python exception
    string. Four distinct refusal keys are emitted depending on which
    invariant was violated.
    """

    try:
        return resolve_transaction_id(prefix, _bucket_transaction_ids(transaction_repository))
    except TransactionIdPrefixError as exc:
        raw_message = str(exc)
        if "is empty" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_empty")) from exc
        if "non-hex" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_not_hex", prefix=prefix)) from exc
        if "longer than" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_too_long", prefix=prefix)) from exc
        if "no transaction" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_not_found", prefix=prefix)) from exc
        if "matches" in raw_message:
            # collision — surface the candidate ids inline so the
            # operator can lengthen the prefix.
            _, _, candidates = raw_message.partition(":")
            raise _bad(
                tr(
                    "cli.ledger.errors.id_prefix_collision",
                    prefix=prefix,
                    candidates=candidates.strip() or "?",
                )
            ) from exc
        raise _bad(raw_message) from exc


def _patch_from_options(**values: object) -> ManualLedgerTransactionPatch:
    return ManualLedgerTransactionPatch.model_validate(
        {key: value for key, value in values.items() if value is not None}
    )


def _emit_update_result(
    ctx: typer.Context,
    result_transaction: Transaction,
    bucket_id: str,
    events: tuple[str, ...],
) -> None:
    transaction_payload = ledger_transaction_payload(result_transaction)
    payload = {
        "bucket_id": bucket_id,
        "transaction_id": result_transaction.transaction_id,
        "bucket_event_ids": list(events),
        "review_status": ledger_transaction_review_status(result_transaction),
        "transaction": transaction_payload,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.id')}\t{result_transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload['date']}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload['amount']}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload['description']}",
            f"{tr('cli.ledger.labels.review_status')}\t{payload['review_status']}",
        ],
    )


@app.command("add", help=tr("cli.ledger.add.help"))
def ledger_add(
    ctx: typer.Context,
    booked_date: str = typer.Option(..., "--date", help=tr("cli.ledger.add.date_help")),
    amount: str = typer.Option(..., "--amount", help=tr("cli.ledger.add.amount_help")),
    direction: TransactionDirection = typer.Option(..., "--direction", help=tr("cli.ledger.add.direction_help")),
    description: str = typer.Option(..., "--description", help=tr("cli.ledger.add.description_help")),
    value_date: str | None = typer.Option(None, "--value-date", help=tr("cli.ledger.add.value_date_help")),
    currency: str = typer.Option("EUR", "--currency", help=tr("cli.ledger.add.currency_help")),
    counterparty: str | None = typer.Option(None, "--counterparty", help=tr("cli.ledger.add.counterparty_help")),
    business_classification: BusinessClassification = typer.Option(
        BusinessClassification.NOT_YET_PROCESSED,
        "--classification",
        help=tr("cli.ledger.add.classification_help"),
    ),
    business_pct: str | None = typer.Option(None, "--business-pct", help=tr("cli.ledger.add.business_pct_help")),
    category_id: str | None = typer.Option(None, "--category-id", help=tr("cli.ledger.add.category_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.add.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.add.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.add.iva_amount_help")),
    irpf_category: str | None = typer.Option(None, "--irpf-category", help=tr("cli.ledger.add.irpf_category_help")),
    usage_ratio_id: str | None = typer.Option(None, "--usage-ratio-id", help=tr("cli.ledger.add.usage_ratio_help")),
    prorrata_reference: str | None = typer.Option(
        None,
        "--prorrata-reference",
        help=tr("cli.ledger.add.prorrata_reference_help"),
    ),
    purchase_invoice_evidence_id: str | None = typer.Option(
        None,
        "--purchase-invoice-evidence-id",
        help=tr("cli.ledger.add.purchase_invoice_evidence_help"),
    ),
    attachment_ids: list[str] = typer.Option(
        [],
        "--attachment-id",
        help=tr("cli.ledger.add.attachment_help"),
    ),
    notes: str = typer.Option("", "--notes", help=tr("cli.ledger.add.notes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.add.actor_help")),
    idempotency_key: str | None = typer.Option(
        None,
        "--idempotency-key",
        help=tr("cli.ledger.add.idempotency_key_help"),
    ),
) -> None:
    """Create one manual ledger transaction through the bucket-scoped backend."""
    current_state = _state()
    transaction_repository = _tx_repo(current_state)
    resolved_business_pct = _resolve_business_pct_with_census(
        bucket_id=transaction_repository.bucket_id,
        active_profile=resolve_active_bucket_id(),
        category_id=category_id,
        operator_supplied=_parse_decimal(business_pct, label="business-pct"),
    )
    command = ManualLedgerTransactionCommand(
        bucket_id=transaction_repository.bucket_id,
        booked_date=_parse_iso_date(booked_date, label="date"),
        value_date=_parse_iso_date(value_date, label="value-date") if value_date is not None else None,
        amount=_parse_required_decimal(amount, label="amount"),
        currency=currency,
        direction=direction,
        counterparty=counterparty,
        description=description,
        business_classification=business_classification,
        business_pct=resolved_business_pct,
        category_id=category_id,
        taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
        iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
        iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
        irpf_category=irpf_category,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        attachment_ids=tuple(attachment_ids),
        notes=notes,
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger add",
        idempotency_key=idempotency_key,
    )
    result = create_manual_transaction(
        command,
        transaction_repository=transaction_repository,
    )
    transaction_payload = ledger_transaction_payload(result.transaction)
    payload = {
        "bucket_id": result.ref.bucket_id,
        "transaction_id": result.ref.transaction_id,
        "bucket_event_ids": list(result.bucket_event_ids),
        "transaction": transaction_payload,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.id')}\t{result.ref.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload['date']}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload['amount']}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload['description']}",
        ],
    )


@app.command("update", help=tr("cli.ledger.update.help"))
def ledger_update(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.update.id_help")),
    booked_date: str | None = typer.Option(None, "--date", help=tr("cli.ledger.update.date_help")),
    value_date: str | None = typer.Option(None, "--value-date", help=tr("cli.ledger.update.value_date_help")),
    amount: str | None = typer.Option(None, "--amount", help=tr("cli.ledger.update.amount_help")),
    direction: TransactionDirection | None = typer.Option(
        None,
        "--direction",
        help=tr("cli.ledger.update.direction_help"),
    ),
    currency: str | None = typer.Option(None, "--currency", help=tr("cli.ledger.update.currency_help")),
    counterparty: str | None = typer.Option(None, "--counterparty", help=tr("cli.ledger.update.counterparty_help")),
    description: str | None = typer.Option(None, "--description", help=tr("cli.ledger.update.description_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.update.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.update.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.update.iva_amount_help")),
    irpf_category: str | None = typer.Option(None, "--irpf-category", help=tr("cli.ledger.update.irpf_category_help")),
    notes: str | None = typer.Option(None, "--notes", help=tr("cli.ledger.update.notes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.update.actor_help")),
) -> None:
    """Correct editable transaction facts through the bucket-scoped backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = update_manual_transaction_fields(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        patch=_patch_from_options(
            booked_date=_parse_iso_date(booked_date, label="date") if booked_date is not None else None,
            value_date=_parse_iso_date(value_date, label="value-date") if value_date is not None else None,
            amount=_parse_decimal(amount, label="amount"),
            direction=direction,
            currency=currency,
            counterparty=counterparty,
            description=description,
            taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
            iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
            iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
            irpf_category=irpf_category,
            notes=notes,
        ),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger update",
        transaction_repository=transaction_repository,
    )
    _emit_update_result(ctx, result.transaction, result.ref.bucket_id, result.bucket_event_ids)


@app.command("classify", help=tr("cli.ledger.classify.help"))
def ledger_classify(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.classify.id_help")),
    classification: BusinessClassification = typer.Option(
        ...,
        "--classification",
        help=tr("cli.ledger.classify.classification_help"),
    ),
    category_id: str | None = typer.Option(None, "--category-id", help=tr("cli.ledger.classify.category_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.classify.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.classify.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.classify.iva_amount_help")),
    irpf_category: str | None = typer.Option(
        None,
        "--irpf-category",
        help=tr("cli.ledger.classify.irpf_category_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.classify.actor_help")),
) -> None:
    """Classify one ledger transaction through the bucket-scoped backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = update_manual_transaction_fields(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        patch=_patch_from_options(
            business_classification=classification,
            category_id=category_id,
            taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
            iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
            iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
            irpf_category=irpf_category,
        ),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
    )
    _emit_update_result(ctx, result.transaction, result.ref.bucket_id, result.bucket_event_ids)


@app.command("allocate", help=tr("cli.ledger.allocate.help"))
def ledger_allocate(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.allocate.id_help")),
    business_pct: str = typer.Option(..., "--business-pct", help=tr("cli.ledger.allocate.business_pct_help")),
    category_id: str | None = typer.Option(None, "--category-id", help=tr("cli.ledger.allocate.category_help")),
    usage_ratio_id: str | None = typer.Option(
        None,
        "--usage-ratio-id",
        help=tr("cli.ledger.allocate.usage_ratio_help"),
    ),
    prorrata_reference: str | None = typer.Option(
        None,
        "--prorrata-reference",
        help=tr("cli.ledger.allocate.prorrata_reference_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.allocate.actor_help")),
) -> None:
    """Record business/private proportionality through the ledger backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    parsed_business_pct = _parse_required_decimal(business_pct, label="business-pct")
    # The classification follows the proportion: a 100% allocation is
    # BUSINESS, a 0% allocation is PERSONAL, and anything strictly
    # between is genuinely MIXED. Hard-coding MIXED silently mislabels
    # a fully-business expense as mixed-use (CLI testimonial, Nuria).
    if parsed_business_pct == Decimal(1):
        allocation_classification = BusinessClassification.BUSINESS
    elif parsed_business_pct == Decimal(0):
        allocation_classification = BusinessClassification.PERSONAL
    else:
        allocation_classification = BusinessClassification.MIXED
    result = update_manual_transaction_fields(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        patch=_patch_from_options(
            business_classification=allocation_classification,
            business_pct=parsed_business_pct,
            category_id=category_id,
            usage_ratio_id=usage_ratio_id,
            prorrata_reference=prorrata_reference,
        ),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger allocate",
        transaction_repository=transaction_repository,
    )
    _emit_update_result(ctx, result.transaction, result.ref.bucket_id, result.bucket_event_ids)


@app.command("attach", help=tr("cli.ledger.attach.help"))
def ledger_attach(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.attach.id_help")),
    purchase_invoice_evidence_id: str | None = typer.Option(
        None,
        "--purchase-invoice-evidence-id",
        help=tr("cli.ledger.attach.purchase_invoice_evidence_help"),
    ),
    attachment_ids: list[str] = typer.Option(
        [],
        "--attachment-id",
        help=tr("cli.ledger.attach.attachment_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.attach.actor_help")),
) -> None:
    """Attach existing secure evidence objects to one ledger transaction."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = attach_manual_transaction_evidence(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        attachment_ids=tuple(attachment_ids),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger attach",
        transaction_repository=transaction_repository,
    )
    _emit_update_result(ctx, result.transaction, result.ref.bucket_id, result.bucket_event_ids)


@app.command("archive", help=tr("cli.ledger.archive.help"))
def ledger_archive(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.archive.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.archive.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.archive.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.archive.actor_help")),
) -> None:
    """Archive one ledger transaction through the bucket-scoped backend."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = archive_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger archive",
        transaction_repository=transaction_repository,
    )
    _emit_update_result(ctx, result.transaction, result.ref.bucket_id, result.bucket_event_ids)


@app.command("stash", help=tr("cli.ledger.stash.help"))
def ledger_stash(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.stash.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.stash.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.stash.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.stash.actor_help")),
) -> None:
    """Stash one ledger transaction through the bucket-scoped backend."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = stash_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger stash",
        transaction_repository=transaction_repository,
    )
    _emit_update_result(ctx, result.transaction, result.ref.bucket_id, result.bucket_event_ids)


@app.command("remove", help=tr("cli.ledger.remove.help"))
def ledger_remove(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.remove.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.remove.reason_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.remove.dry_run_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.remove.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.remove.actor_help")),
) -> None:
    """Remove one ledger transaction through the bucket-scoped backend."""
    if not dry_run and not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    report = remove_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        dry_run=dry_run,
        source_command="aeat app ledger remove",
        transaction_repository=transaction_repository,
    )
    payload = report.model_dump(mode="json")
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
            f"{tr('cli.ledger.labels.id')}\t{report.transaction_id}",
            f"{tr('cli.ledger.labels.removed')}\t{report.removed}",
            f"{tr('cli.ledger.labels.dry_run')}\t{report.dry_run}",
        ],
    )


@app.command("reset", help=tr("cli.ledger.reset.help"))
def ledger_reset(
    ctx: typer.Context,
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.reset.reason_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.reset.dry_run_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.reset.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.reset.actor_help")),
) -> None:
    """Reset the active bucket ledger catalogue through the backend."""
    if not dry_run and not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    report = reset_ledger_catalogue(
        bucket_id=transaction_repository.bucket_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        dry_run=dry_run,
        source_command="aeat app ledger reset",
        transaction_repository=transaction_repository,
    )
    payload = report.model_dump(mode="json")
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
            f"{tr('cli.ledger.labels.rows')}\t{len(report.removed_transaction_ids)}",
            f"{tr('cli.ledger.labels.reset')}\t{report.reset}",
            f"{tr('cli.ledger.labels.dry_run')}\t{report.dry_run}",
        ],
    )


@app.command("split", help=tr("cli.ledger.split.help"))
def ledger_split(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.split.id_help")),
    child_amount: list[str] = typer.Option(
        [],
        "--child-amount",
        help=tr("cli.ledger.split.child_amount_help"),
    ),
    child_description: list[str] = typer.Option(
        [],
        "--child-description",
        help=tr("cli.ledger.split.child_description_help"),
    ),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.split.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.split.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.split.actor_help")),
) -> None:
    """Redistribute one parent transaction into N child transactions."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    if len(child_amount) != len(child_description):
        raise _bad(tr("cli.ledger.split.errors.child_args_mismatch"))
    if len(child_amount) < 2:
        raise _bad(tr("cli.ledger.split.errors.min_two_children"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    children = tuple(
        SplitChildCommand(
            amount=_parse_required_decimal(amount_raw, label="child-amount"),
            description=description_raw,
        )
        for amount_raw, description_raw in zip(child_amount, child_description, strict=True)
    )
    result = split_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        children=children,
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger split",
        reason=reason,
        transaction_repository=transaction_repository,
    )
    payload = {
        "bucket_id": result.bucket_id,
        "parent_transaction_id": result.parent_transaction_id,
        "split_group_id": result.split_group_id,
        "child_transaction_ids": list(result.child_transaction_ids),
        "bucket_event_id": result.bucket_event_id,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.parent_id')}\t{result.parent_transaction_id}",
            f"{tr('cli.ledger.labels.split_group_id')}\t{result.split_group_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(result.child_transaction_ids)}",
            f"{tr('cli.ledger.labels.event_id')}\t{result.bucket_event_id}",
        ],
    )


@app.command("merge", help=tr("cli.ledger.merge.help"))
def ledger_merge(
    ctx: typer.Context,
    child_id: list[str] = typer.Option(
        [],
        "--child-id",
        help=tr("cli.ledger.merge.child_id_help"),
    ),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.merge.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.merge.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.merge.actor_help")),
) -> None:
    """Re-merge a complete cohort of split children into a fresh transaction."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    if len(child_id) < 2:
        raise _bad(tr("cli.ledger.merge.errors.min_two_children"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_ids = tuple(_resolve_id(transaction_repository, raw) for raw in child_id)
    result = merge_transactions(
        bucket_id=transaction_repository.bucket_id,
        child_transaction_ids=resolved_ids,
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger merge",
        reason=reason,
        transaction_repository=transaction_repository,
    )
    payload = {
        "bucket_id": result.bucket_id,
        "split_group_id": result.split_group_id,
        "parent_transaction_id": result.parent_transaction_id,
        "merged_transaction_id": result.merged_transaction_id,
        "source_child_ids": list(result.source_child_ids),
        "bucket_event_id": result.bucket_event_id,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.split_group_id')}\t{result.split_group_id}",
            f"{tr('cli.ledger.labels.parent_id')}\t{result.parent_transaction_id}",
            f"{tr('cli.ledger.labels.merged_id')}\t{result.merged_transaction_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(result.source_child_ids)}",
            f"{tr('cli.ledger.labels.event_id')}\t{result.bucket_event_id}",
        ],
    )


_LEDGER_HISTORY_EVENT_TYPES: tuple[BucketEventType, ...] = (
    BucketEventType.LEDGER_TRANSACTION_CREATED,
    BucketEventType.LEDGER_TRANSACTION_IMPORTED,
    BucketEventType.LEDGER_TRANSACTION_UPDATED,
    BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
    BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    BucketEventType.LEDGER_TRANSACTION_STASHED,
    BucketEventType.LEDGER_TRANSACTION_REMOVED,
    BucketEventType.LEDGER_TRANSACTION_EXPORTED,
    BucketEventType.LEDGER_TRANSACTION_SPLIT,
    BucketEventType.LEDGER_TRANSACTION_MERGED,
)


@app.command(
    "link",
    help=tr(
        "cli.ledger.link.help",
        default=(
            "Bind a ledger transaction to an invoice and/or a purchase-invoice "
            "evidence record in a single canonical call. Refuses cross-bucket "
            "links. Local-only; never contacts AEAT."
        ),
    ),
)
def ledger_link(
    ctx: typer.Context,
    transaction_id: str = typer.Option(
        ...,
        "--id",
        help=tr("cli.ledger.link.id_help", default="Ledger transaction id (SHA-256 or unambiguous prefix)."),
    ),
    invoice_id: str | None = typer.Option(
        None,
        "--invoice-id",
        help=tr(
            "cli.ledger.link.invoice_id_help",
            default="Invoice id to bind bidirectionally to the transaction.",
        ),
    ),
    evidence_id: str | None = typer.Option(
        None,
        "--evidence-id",
        help=tr(
            "cli.ledger.link.evidence_id_help",
            default="Purchase-invoice evidence record id to attach to the transaction.",
        ),
    ),
    actor: str | None = typer.Option(
        None,
        "--by",
        help=tr("cli.ledger.link.actor_help", default="Operator label recorded on bucket events."),
    ),
) -> None:
    """Bind a transaction to invoice / evidence references in one call."""

    from ...application.invoices import link_invoice_transaction_repositories
    from ...domain.invoices import InvoiceCatalogueRepository
    from ...domain.invoices._errors import InvoiceLinkError

    if invoice_id is None and evidence_id is None:
        raise _bad(
            tr(
                "cli.ledger.link.errors.missing_target",
                default="Supply at least one of --invoice-id or --evidence-id.",
            ),
        )

    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    bucket_id = transaction_repository.bucket_id
    actor_label = (actor or "operator").strip() or "operator"

    if invoice_id is not None:
        # Pre-write bucket guard: load the invoice and verify it is
        # scoped to the active bucket BEFORE invoking the linker.
        # link_invoice_transaction_repositories mutates both invoice and
        # transaction catalogues; a post-write check would leave a
        # cross-bucket link persisted.
        invoice_repo = InvoiceCatalogueRepository()
        invoices_snapshot = invoice_repo.load()
        invoice_record = invoices_snapshot.invoices.get(invoice_id)
        if invoice_record is None:
            raise _bad(
                tr(
                    "cli.ledger.link.errors.invoice_not_found",
                    default="Invoice id not found in the active profile invoice catalogue.",
                ),
            )
        if invoice_record.bucket_id not in (None, bucket_id):
            raise _bad(
                tr(
                    "cli.ledger.link.errors.cross_bucket_invoice",
                    default="Invoice belongs to a different bucket than the active profile.",
                ),
            )
        try:
            link_invoice_transaction_repositories(
                bucket_id=bucket_id,
                invoice_id=invoice_id,
                transaction_id=resolved_id,
                invoice_repository=invoice_repo,
                transaction_repository=transaction_repository,
            )
        except InvoiceLinkError as exc:
            raise _bad(str(exc)) from exc

    evidence_result_payload: dict[str, object] = {}
    if evidence_id is not None:
        evidence_patch = ManualLedgerTransactionPatch(purchase_invoice_evidence_id=evidence_id)
        evidence_result = update_manual_transaction_fields(
            bucket_id=bucket_id,
            transaction_id=resolved_id,
            patch=evidence_patch,
            actor=actor_label,
            source_command="aeat app ledger link",
        )
        evidence_result_payload = ledger_transaction_result_payload(evidence_result)

    payload: dict[str, object] = {
        "operation": "ledger.link",
        "bucket_id": bucket_id,
        "transaction_id": resolved_id,
        "invoice_id": invoice_id,
        "evidence_id": evidence_id,
        "actor": actor_label,
    }
    if evidence_result_payload:
        payload["evidence_update"] = evidence_result_payload
    lines = [
        "operation\tledger.link",
        f"bucket\t{bucket_id}",
        f"transaction_id\t{resolved_id}",
        f"actor\t{actor_label}",
    ]
    if invoice_id is not None:
        lines.append(f"invoice_id\t{invoice_id}")
    if evidence_id is not None:
        lines.append(f"evidence_id\t{evidence_id}")
    _emit(ctx, payload, lines)


@app.command(
    "check",
    help=tr(
        "cli.ledger.check.help",
        default=(
            "Probe ledger transactions in the addressed bucket (defaults to the active "
            "profile bucket) and report anomaly rows aggregated across every period a "
            "transaction touches. Local-only; never contacts AEAT."
        ),
    ),
)
def ledger_check(
    ctx: typer.Context,
    bucket_id_option: str | None = typer.Option(
        None,
        "--bucket-id",
        help=tr(
            "cli.ledger.check.bucket_id_help",
            default="Bucket id to probe (defaults to the active profile bucket).",
        ),
    ),
) -> None:
    """Surface ledger anomalies for the addressed bucket without mutating state."""

    from ...application.ledger._preflight import preflight_transaction_catalogue
    from ...domain.transactions import TransactionCatalogueRepository

    if bucket_id_option is not None:
        transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id_option)
    else:
        transaction_repository = _tx_repo(_state())
    bucket_id = transaction_repository.bucket_id
    catalogue = transaction_repository.load()

    # Aggregate readiness across every year the catalogue's transactions
    # touch (per-year periods are the largest periodic envelope the
    # readiness service accepts). An "all-period audit" omits no anomaly.
    years = sorted(
        {
            (tx.raw.value_date or tx.raw.booked_date).year
            for tx in catalogue.values()
            if (tx.raw.value_date or tx.raw.booked_date) is not None
        },
    )
    if not years:
        payload = {
            "bucket_id": bucket_id,
            "periods": [],
            "checked_transaction_count": 0,
            "issues": [],
            "ready": True,
        }
        lines = [
            f"bucket\t{bucket_id}",
            "periods\t",
            "checked\t0",
            "issues\t0",
            "ready\ttrue",
        ]
        _emit(ctx, payload, lines)
        return

    aggregated_issues: list[object] = []
    aggregated_payload_issues: list[dict[str, object]] = []
    checked_total = 0
    for year in years:
        report = preflight_transaction_catalogue(
            bucket_id=bucket_id,
            period=str(year),
            transactions=catalogue,
        )
        checked_total += report.checked_transaction_count
        for issue in report.issues:
            aggregated_issues.append(issue)
            aggregated_payload_issues.append(issue.model_dump(mode="json"))

    payload = {
        "bucket_id": bucket_id,
        "periods": [str(year) for year in years],
        "checked_transaction_count": checked_total,
        "issues": aggregated_payload_issues,
        "ready": not aggregated_issues,
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"periods\t{','.join(str(year) for year in years)}",
        f"checked\t{checked_total}",
        f"issues\t{len(aggregated_issues)}",
        f"ready\t{str(not aggregated_issues).lower()}",
    ]
    for issue in aggregated_issues:
        lines.append(f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
    _emit(ctx, payload, lines)


@app.command(
    "preflight",
    help=tr(
        "cli.ledger.preflight.help",
        default=(
            "Report missing ledger facts (category, taxable base, IVA amount/rate, "
            "currency, proportionality reference) for the active bucket's transactions "
            "in a given period. Local-only; never contacts AEAT."
        ),
    ),
)
def ledger_preflight(
    ctx: typer.Context,
    period: str = typer.Option(
        ...,
        "--period",
        help=tr(
            "cli.ledger.preflight.period_help",
            default="Canonical period (e.g. 2026Q1, 2026-03, 2026).",
        ),
    ),
) -> None:
    """Surface modelo-readiness gaps for the active bucket without mutating ledger state."""

    from ...application.ledger._preflight import preflight_ledger_tax_readiness

    transaction_repository = _tx_repo(_state())
    canonical = _canonical_period(period)
    report = preflight_ledger_tax_readiness(
        bucket_id=transaction_repository.bucket_id,
        period=canonical,
        transaction_repository=transaction_repository,
    )
    payload = report.model_dump(mode="json")
    lines = [
        f"bucket\t{report.bucket_id}",
        f"period\t{canonical}",
        f"checked\t{report.checked_transaction_count}",
        f"issues\t{len(report.issues)}",
        f"ready\t{str(report.ready).lower()}",
    ]
    for issue in report.issues:
        lines.append(f"issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
    _emit(ctx, payload, lines)


@app.command("history", help=tr("cli.ledger.history.help"))
def ledger_history(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.history.id_help")),
    include_split_siblings: bool = typer.Option(
        False,
        "--include-split-siblings",
        help=tr("cli.ledger.history.include_split_siblings_help"),
    ),
) -> None:
    """Emit the chronological event chain for one ledger transaction id."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    object_ids = _history_object_ids(
        transaction_repository,
        resolved_id=resolved_id,
        include_split_siblings=include_split_siblings,
    )
    matches = _collect_ledger_history_events(object_ids)
    payload = {
        "bucket_id": transaction_repository.bucket_id,
        "transaction_id": resolved_id,
        "event_count": len(matches),
        "events": [event.model_dump(mode="json") for event in matches],
    }
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{transaction_repository.bucket_id}",
        f"{tr('cli.ledger.labels.id')}\t{resolved_id}",
        f"{tr('cli.ledger.labels.event_count')}\t{len(matches)}",
    ]
    lines.extend(
        f"{event.occurred_at.isoformat()}\t{event.event_type.value}\t{event.event_id}" for event in matches
    )
    _emit(ctx, payload, lines)


def _history_object_ids(
    transaction_repository: TransactionCatalogueRepository,
    *,
    resolved_id: str,
    include_split_siblings: bool,
) -> list[str]:
    """Return ``[resolved_id, ...siblings]`` (de-duped, order-preserving) when the operator opts in.

    Sibling expansion is the operator-facing escape hatch that lets
    `aeat app ledger history --include-split-siblings` follow the
    complete split-group chain from one supplied transaction id;
    without the flag, only the supplied id's events are emitted.
    """
    object_ids = [resolved_id]
    if not include_split_siblings:
        return object_ids
    transaction = transaction_repository.load().get(resolved_id)
    if transaction is None or transaction.split_lineage is None:
        return object_ids
    for sibling in transaction.split_lineage.sibling_transaction_ids:
        if sibling not in object_ids:
            object_ids.append(sibling)
    return object_ids


def _collect_ledger_history_events(object_ids: list[str]) -> list:
    """Return the chronological union of LEDGER-history events across ``object_ids``."""
    event_catalogue = BucketEventHistoryRepository().load()
    matches: list = []
    for object_id in object_ids:
        matches.extend(
            event
            for event in event_catalogue.for_object(
                object_type=BucketEventObjectType.LEDGER_TRANSACTION,
                object_id=object_id,
            )
            if event.event_type in _LEDGER_HISTORY_EVENT_TYPES
        )
    matches.sort(key=lambda event: event.occurred_at)
    return matches


@app.command("export", help=tr("cli.ledger.export.help"))
def ledger_export(
    ctx: typer.Context,
    output: Path = typer.Option(..., "--output", help=tr("cli.ledger.export.output_help")),
    export_kind: ExportSerializationFormat = typer.Option(
        ExportSerializationFormat.CSV,
        "--export-format",
        help=tr("cli.ledger.export.format_help"),
    ),
    include_inactive: bool = typer.Option(
        False,
        "--include-inactive",
        help=tr("cli.ledger.export.include_inactive_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.export.actor_help")),
) -> None:
    """Export canonical bucket-scoped ledger rows through the backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    result = export_ledger_transactions(
        LedgerExportCommand(
            bucket_id=transaction_repository.bucket_id,
            export_format=export_kind,
            include_inactive=include_inactive,
            output_path=output,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger export",
        ),
        transaction_repository=transaction_repository,
    )
    payload = result.model_dump(mode="json", exclude={"payload"})
    payload["output_path"] = str(output)
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.export_id')}\t{result.export_id}",
            f"{tr('cli.ledger.labels.rows')}\t{result.row_count}",
            f"{tr('cli.ledger.labels.sha256')}\t{result.sha256}",
            f"{tr('cli.ledger.labels.output')}\t{output}",
        ],
    )


@app.command("list", help=tr("cli.ledger.list.help"))
def ledger_list(ctx: typer.Context) -> None:
    """List bucket-scoped ledger transactions through the backend read service."""
    state = _state()
    transaction_repository = _tx_repo(state)
    results = list_manual_transactions(
        bucket_id=transaction_repository.bucket_id,
        transaction_repository=transaction_repository,
    )
    rows: list[dict[str, object]] = []
    lines = [tr("cli.ledger.list.header")]
    full_ids = tuple(result.transaction.transaction_id for result in results)
    display_width = compute_display_id_width(full_ids)
    for result in results:
        transaction = result.transaction
        review_status = ledger_transaction_review_status(transaction)
        row = ledger_transaction_review_payload(transaction)
        row["full_id"] = transaction.transaction_id
        row["display_id"] = transaction.transaction_id[:display_width]
        rows.append(row)
        lines.append(
            f"{row['display_id']}\t{transaction.transaction_id}\t{row['date']}\t"
            f"{row['amount']}\t{row['description']}\t{review_status}"
        )
    _emit(
        ctx,
        {"bucket_id": transaction_repository.bucket_id, "rows": rows},
        lines,
    )


@app.command("view", help=tr("cli.ledger.view.help"))
def ledger_view(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.view.transaction_id_help")),
) -> None:
    """Read one bucket-scoped ledger transaction through the backend read service."""
    transaction_repository = _tx_repo(_state())
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = get_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
    )
    payload = ledger_transaction_result_payload(result)
    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.id')}\t{result.ref.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload['date']}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload['amount']}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload['description']}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ],
    )


@app.command("status", help=tr("cli.ledger.status.help"))
def ledger_status(
    ctx: typer.Context,
    period: str | None = typer.Option(None, "--period", help=tr("cli.ledger.status.period_help")),
) -> None:
    """Summarize active-bucket ledger state through the backend status service."""
    state = _state()
    transaction_repository = _tx_repo(state)
    report = summarize_manual_transactions(
        bucket_id=transaction_repository.bucket_id,
        period=_canonical_period(period) if period else None,
        transaction_repository=transaction_repository,
    )
    payload = report.model_dump(mode="json")
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
        f"{tr('cli.ledger.labels.rows')}\t{report.total_count}",
        f"{tr('cli.ledger.labels.active')}\t{report.active_count}",
        f"{tr('cli.ledger.labels.archived')}\t{report.archived_count}",
        f"{tr('cli.ledger.labels.stashed')}\t{report.stashed_count}",
        f"{tr('cli.ledger.labels.pending')}\t{report.pending_review_count}",
        f"{tr('cli.ledger.labels.reviewed')}\t{report.reviewed_count}",
        f"{tr('cli.ledger.labels.skipped')}\t{report.skipped_count}",
    ]
    if report.period is not None:
        lines.extend(
            [
                f"{tr('cli.ledger.labels.period')}\t{report.period}",
                f"{tr('cli.ledger.labels.checked')}\t{report.checked_transaction_count}",
                f"{tr('cli.ledger.labels.readiness_issues')}\t{report.readiness_issue_count}",
                f"{tr('cli.ledger.labels.ready')}\t{report.ready}",
            ]
        )
    _emit(ctx, payload, lines)


@app.command("track", help=tr("cli.ledger.track.help"))
def ledger_track(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.track.transaction_id_help")),
) -> None:
    """Show audit lineage for one bucket-scoped ledger transaction."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = get_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
    )
    payload = {
        "bucket_id": result.ref.bucket_id,
        "transaction": ledger_transaction_payload(result.transaction),
        "tracking": ledger_transaction_tracking_payload(result.transaction),
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.id')}\t{result.ref.transaction_id}",
            f"{tr('cli.ledger.labels.lifecycle_state')}\t{result.transaction.lifecycle_state.value}",
            f"{tr('cli.ledger.labels.created_event_id')}\t{result.transaction.created_event_id or '-'}",
        ],
    )


@app.command("import", help=tr("cli.ledger.import.help"))
def ledger_import(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help=tr("cli.ledger.import.path_help")),
    provider: str = typer.Option(..., "--provider", help=tr("cli.ledger.import.provider_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.import.dry_run_help")),
    verify: bool = typer.Option(False, "--verify", help=tr("cli.ledger.import.verify_help")),
    source: Path | None = typer.Option(None, "--source", help=tr("cli.ledger.import.source_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.ledger.import.verbose_help")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.ledger.import.period_help")),
) -> None:
    """Import a financial-statement file via the existing provider registry."""
    bucket_id: str | None = None
    actor = "operator"
    transaction_repository = None
    if not dry_run:
        current_state = _state()
        transaction_repository = _tx_repo(current_state)
        bucket_id = transaction_repository.bucket_id
        actor = resolve_active_bucket_id() or "operator"
    result = import_ledger_source(
        LedgerSourceImportCommand(
            bucket_id=bucket_id,
            path=path,
            provider=provider,
            dry_run=dry_run,
            verify=verify,
            source=source,
            period=_canonical_period(period) if period else None,
            actor=actor,
            source_command="aeat app ledger import",
        ),
        transaction_repository=transaction_repository,
    )
    payload = result.model_dump(mode="json")
    lines = [
        f"{tr('cli.ledger.labels.rows')}\t{result.rows}",
        f"{tr('cli.ledger.labels.imported')}\t{result.imported}",
        f"{tr('cli.ledger.labels.skipped')}\t{result.skipped}",
    ]
    if result.dry_run:
        lines.append(f"{tr('cli.ledger.labels.dry_run')}\t{tr('cli.ledger.labels.yes')}")
    if verbose or verify:
        lines.extend(_validation_lines(result.validation, result.source))
    _emit(
        ctx,
        payload,
        lines,
    )


def _validation_lines(
    validation: LedgerSourceValidationReport,
    source_verification: LedgerSourceVerificationReport,
) -> list[str]:
    validation_payload = validation.model_dump(mode="json")
    source_payload = source_verification.model_dump(mode="json")
    valid_label = tr("cli.ledger.labels.yes") if validation_payload["valid"] else tr("cli.ledger.labels.no")
    lines = [
        f"{tr('cli.ledger.labels.valid')}\t{valid_label}",
        f"{tr('cli.ledger.labels.dialect')}\t{validation_payload['dialect'] or '-'}",
    ]
    if validation_payload["warnings"]:
        lines.append(f"{tr('cli.ledger.labels.warnings')}\t{'; '.join(validation_payload['warnings'])}")
    if source_payload["requested"]:
        lines.append(f"{tr('cli.ledger.labels.source')}\t{source_payload['path'] or '-'}")
    return lines


@app.command("review", help=tr("cli.ledger.review.help"))
def ledger_review(
    ctx: typer.Context,
    filters: list[str] = typer.Option([], "--filter", help=tr("cli.ledger.review.filter_help")),
    record_id: str | None = typer.Option(None, "--id", help=tr("cli.ledger.review.id_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.ledger.review.verbose_help")),
) -> None:
    """Render rows or a single row using the typed filter spec."""
    try:
        spec = LedgerReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(tr("cli.ledger.errors.filter_parse_error", reason=exc.reason, token=exc.raw_token)) from exc
    transaction_repository = _tx_repo(_state())
    result = query_ledger_review_rows(
        LedgerReviewQuery(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=record_id,
            period=_canonical_period(spec.period) if spec.period else None,
            status=spec.status.value if spec.status is not None else None,
            issue=spec.issue.value if spec.issue is not None else None,
            import_id=spec.import_id,
        ),
        transaction_repository=transaction_repository,
    )
    if record_id is not None:
        if not result.rows:
            _emit(
                ctx,
                {"rows": [], "filters": list(result.filters)},
                [tr("cli.ledger.review.header"), tr("cli.ledger.review.no_rows")],
            )
            return
        row = result.rows[0]
        payload = {
            "id": row.id,
            "date": row.date,
            "amount": row.amount,
            "description": row.description,
            "review_status": row.status,
            "transaction": row.transaction,
            "verbose": verbose,
        }
        _emit(
            ctx,
            payload,
            [
                f"{tr('cli.ledger.labels.id')}\t{row.id}",
                f"{tr('cli.ledger.labels.date')}\t{row.date}",
                f"{tr('cli.ledger.labels.amount')}\t{row.amount}",
                f"{tr('cli.ledger.labels.description')}\t{row.description}",
            ],
        )
        return
    payload = {
        "rows": [row.model_dump(mode="json", exclude_none=True) for row in result.rows],
        "filters": list(result.filters),
    }
    lines: list[str] = [tr("cli.ledger.review.header")]
    review_ids = tuple(row.id for row in result.rows)
    review_width = compute_display_id_width(review_ids)
    lines.extend(
        f"{row.id[:review_width]}\t{row.id}\t{row.date}\t{row.amount}\t{row.description}\t{row.status}"
        for row in result.rows
    )
    if not result.rows:
        lines.append(tr("cli.ledger.review.no_rows"))
    _emit(ctx, payload, lines)


ratios_app = typer.Typer(
    name="ratios",
    help=tr("cli.app.ledger.ratios.group_help", default="Per-category proportional-deduction overrides."),
    no_args_is_help=True,
)
app.add_typer(ratios_app, name="ratios")


def _ratios_bucket_id() -> str:
    """Return the active workflow bucket id or raise the standard CLI refusal."""

    from ...application.workflow._models import active_bucket_id_or_raise

    try:
        return active_bucket_id_or_raise()
    except Exception as exc:  # NoActiveProfileError + downstream raises
        raise _bad(tr("cli.config.errors.no_active_profile")) from exc


def _ratios_bucket_and_profile() -> tuple[str, str | None]:
    """Return ``(bucket_id, active_profile_id)`` from workflow state.

    ``active_profile_id`` is ``None`` when the workflow has a bucket
    selected but no active profile (e.g. mid-init); ratios mutations
    are still allowed in that state but census-override warnings stay
    silent because there is no profile to look up snapshots against.
    """

    from ...application.workflow._models import active_bucket_id_or_raise, resolve_active_bucket_id

    try:
        bucket_id = active_bucket_id_or_raise()
    except Exception as exc:  # NoActiveProfileError + downstream raises
        raise _bad(tr("cli.config.errors.no_active_profile")) from exc
    return bucket_id, resolve_active_bucket_id()


def _emit_ratios_event(
    *,
    bucket_id: str,
    event_type,
    category: str,
    prior,
    new,
) -> None:
    """Append a ratios mutation event to the bucket-event-history catalogue.

    Records the per-category ratio change so downstream auditors can
    reconstruct the sequence of overrides without re-deriving them
    from secure-object snapshots. ``prior`` is ``None`` on a first
    set; ``new`` is ``None`` on unset.
    """

    from datetime import UTC, datetime

    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = datetime.now(UTC)
    payload = {
        "category": category,
        "prior": "" if prior is None else str(prior),
        "new": "" if new is None else str(new),
    }
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=category,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    repo.save(
        append_bucket_event(
            catalogue,
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=event_type,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=category,
                payload=payload,
                payload_version=1,
            ),
        )
    )


def _resolve_business_pct_with_census(
    *,
    bucket_id: str,
    active_profile: str | None,
    category_id: str | None,
    operator_supplied,
):
    """Stamp the census-derived business_pct when the operator omits one.

    Operator-supplied values always win — the helper only fills the
    gap when ``business_pct`` is not given AND the transaction targets
    a HOME_OFFICE category that the census actually governs. Returns
    the operator-supplied value unchanged on every other path, so non-
    HOME_OFFICE transactions and explicit-override flows are not
    perturbed.
    """


    from ...application.ledger._ratios import census_business_pct_for
    from ...application.user_profile import CensoSyncService
    from ...domain.categories import SpendingCategory

    if operator_supplied is not None:
        return operator_supplied
    if category_id is None or active_profile is None:
        return operator_supplied
    try:
        category_enum = SpendingCategory(category_id.strip())
    except ValueError:
        return operator_supplied
    sync_service = CensoSyncService(bucket_id=bucket_id)
    raw_afectacion: Decimal | None = sync_service.bound_raw_afectacion_ratio(profile_id=active_profile)
    if raw_afectacion is None:
        return operator_supplied
    return census_business_pct_for(category_enum, raw_afectacion)


def _emit_ratios_census_override_warning(
    *,
    bucket_id: str,
    warning,
) -> None:
    """Append LEDGER_RATIOS_CENSUS_OVERRIDE_WARNING to the bucket catalogue.

    Fires when a HOME_OFFICE per-category override diverges from the
    legally-binding census-derived value (LIRPF Art. 30.2 rule 5 for
    suministros; raw afectación for ownership). The set operation
    itself is not refused — the operator may legitimately model a
    planned change — but downstream auditors get a typed record of
    the divergence.
    """

    from datetime import UTC, datetime

    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = datetime.now(UTC)
    payload = {
        "category": warning.category.value,
        "override_ratio": str(warning.override_ratio),
        "census_derived_ratio": str(warning.census_derived_ratio),
        "raw_afectacion_ratio": str(warning.raw_afectacion_ratio),
    }
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_CENSUS_OVERRIDE_WARNING,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=warning.category.value,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    repo.save(
        append_bucket_event(
            catalogue,
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=BucketEventType.LEDGER_RATIOS_CENSUS_OVERRIDE_WARNING,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=warning.category.value,
                payload=payload,
                payload_version=1,
            ),
        ),
    )


def _resolve_category(raw: str):
    from ...domain.categories import SpendingCategory

    try:
        return SpendingCategory(raw.strip())
    except ValueError as exc:
        raise _bad(
            tr("cli.app.ledger.ratios.unknown_category", default="Unknown spending category: {raw!r}").format(raw=raw)
        ) from exc


@ratios_app.command(
    "list",
    help=tr(
        "cli.app.ledger.ratios.list_help", default="List every per-category usage-ratio override on the active bucket."
    ),
)
def ratios_list(ctx: typer.Context) -> None:
    from ...application.user_profile import CensoSyncService
    from ...domain.usage_ratios import (
        CensoRatioMismatchError,
        load_usage_ratios,
        load_usage_ratios_with_census_guard,
    )

    bucket_id, profile_id = _ratios_bucket_and_profile()
    raw_afectacion = None
    if profile_id is not None:
        raw_afectacion = CensoSyncService(bucket_id=bucket_id).bound_raw_afectacion_ratio(
            profile_id=profile_id,
        )
    census_mismatch: str | None = None
    try:
        profile = load_usage_ratios_with_census_guard(
            bucket_id=bucket_id,
            raw_afectacion_ratio=raw_afectacion,
        )
    except CensoRatioMismatchError as exc:
        # The operator should still see what's persisted; we surface the
        # divergence as a typed warning row but never hide the rows.
        census_mismatch = str(exc)
        profile = load_usage_ratios(bucket_id=bucket_id)
    rows = [{"category": category.value, "ratio": str(ratio)} for category, ratio in profile.ratios.items()]
    payload = {
        "bucket_id": bucket_id,
        "rows": rows,
        "count": len(rows),
        "census_mismatch": census_mismatch,
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    if census_mismatch is not None:
        lines.append(f"census_mismatch\t{census_mismatch}")
    lines.extend(f"{row['category']}\t{row['ratio']}" for row in rows)
    _emit(ctx, payload, lines)


@ratios_app.command(
    "set", help=tr("cli.app.ledger.ratios.set_help", default="Set or replace one per-category usage-ratio override.")
)
def ratios_set(
    ctx: typer.Context,
    category: str = typer.Argument(
        ..., help=tr("cli.app.ledger.ratios.category_help", default="Spending category id (e.g. USAGE_RATIO_VEHICLE).")
    ),
    ratio: str = typer.Argument(
        ..., help=tr("cli.app.ledger.ratios.ratio_help", default="Override ratio in the closed interval [0, 1].")
    ),
) -> None:
    from ...application.ledger._ratios import census_override_warning
    from ...application.user_profile import CensoSyncService
    from ...domain.usage_ratios import load_usage_ratios, save_usage_ratios

    category_enum = _resolve_category(category)
    parsed = _parse_required_decimal(ratio, label="ratio")
    bucket_id, profile_id = _ratios_bucket_and_profile()
    profile = load_usage_ratios(bucket_id=bucket_id)
    prior = profile.ratios.get(category_enum)
    updated = profile.with_ratio(category_enum, parsed)
    save_usage_ratios(updated, bucket_id=bucket_id)
    _emit_ratios_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_SET,
        category=category_enum.value,
        prior=prior,
        new=parsed,
    )
    if profile_id is not None:
        sync_service = CensoSyncService(bucket_id=bucket_id)
        raw_afectacion = sync_service.bound_raw_afectacion_ratio(profile_id=profile_id)
        warning = census_override_warning(
            category=category_enum,
            override_ratio=parsed,
            raw_afectacion_ratio=raw_afectacion if raw_afectacion is not None else parsed,
        ) if raw_afectacion is not None else None
        if warning is not None:
            _emit_ratios_census_override_warning(bucket_id=bucket_id, warning=warning)
    payload = {"bucket_id": bucket_id, "category": category_enum.value, "ratio": str(parsed)}
    _emit(
        ctx,
        payload,
        (f"bucket\t{bucket_id}", f"{category_enum.value}\t{parsed}"),
    )


@ratios_app.command(
    "unset", help=tr("cli.app.ledger.ratios.unset_help", default="Clear one per-category usage-ratio override.")
)
def ratios_unset(
    ctx: typer.Context,
    category: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.ratios.unset_category_help", default="Spending category id whose override to clear."),
    ),
) -> None:
    from ...domain.usage_ratios import load_usage_ratios, save_usage_ratios

    category_enum = _resolve_category(category)
    bucket_id = _ratios_bucket_id()
    profile = load_usage_ratios(bucket_id=bucket_id)
    if category_enum not in profile.ratios:
        raise _bad(
            tr(
                "cli.app.ledger.ratios.no_override_error",
                default="No persisted override for category {category!r} on bucket {bucket_id!r}",
            ).format(category=category_enum.value, bucket_id=bucket_id)
        )
    prior = profile.ratios.get(category_enum)
    updated = profile.without_ratio(category_enum)
    save_usage_ratios(updated, bucket_id=bucket_id)
    _emit_ratios_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_UNSET,
        category=category_enum.value,
        prior=prior,
        new=None,
    )
    payload = {"bucket_id": bucket_id, "category": category_enum.value, "ratio": ""}
    _emit(ctx, payload, (f"bucket\t{bucket_id}", f"{category_enum.value}\t<unset>"))


@ratios_app.command(
    "eligible",
    help=tr(
        "cli.app.ledger.ratios.eligible_help", default="List every category that may carry a per-category override."
    ),
)
def ratios_eligible(ctx: typer.Context) -> None:
    from ...application.ledger._ratios import list_eligible_ratios_for_bucket

    bucket_id = _ratios_bucket_id()
    rows = list_eligible_ratios_for_bucket(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        default = "" if row.default_ratio is None else str(row.default_ratio)
        override_marker = "X" if row.override_present else "."
        lines.append(
            f"{row.category.value}\t{row.proportionality_kind}\tdefault={default or '-'}\toverride={override_marker}"
        )
    _emit(ctx, payload, lines)


@ratios_app.command(
    "validate",
    help=tr(
        "cli.app.ledger.ratios.validate_help",
        default="Validate the per-category overrides against eligibility + bound rules.",
    ),
)
def ratios_validate(ctx: typer.Context) -> None:
    from ...application.ledger._ratios import validate_ratios_for_bucket

    bucket_id = _ratios_bucket_id()
    report = validate_ratios_for_bucket(bucket_id=bucket_id)
    payload = report.model_dump(mode="json")
    lines = [
        f"bucket\t{bucket_id}",
        f"profile_present\t{report.profile_present}",
        f"eligible\t{report.eligible_count}",
        f"overrides\t{report.overrides_count}",
    ]
    if report.missing_overrides:
        lines.append("missing\t" + ",".join(c.value for c in report.missing_overrides))
    for finding in report.findings:
        detail = f"\t{finding.detail}" if finding.detail else ""
        lines.append(f"finding\t{finding.category.value}\t{finding.kind}{detail}")
    _emit(ctx, payload, lines)


def _business_invoice_payload(record) -> dict[str, object]:
    return record.model_dump(mode="json")


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


def _payable_invoice_service():
    from ...application.ledger._business_operation_invoice import PayableInvoiceService

    return PayableInvoiceService()


def _collectible_invoice_service():
    from ...application.ledger._business_operation_invoice import CollectibleInvoiceService

    return CollectibleInvoiceService()


payable_invoice_app = typer.Typer(
    name="payable-invoice",
    help=tr("cli.app.ledger.payable_invoice.group_help", default="Payable invoice records (we owe a vendor)."),
    no_args_is_help=True,
)


@payable_invoice_app.command(
    "add", help=tr("cli.app.ledger.payable_invoice.add_help", default="Register a new payable invoice record.")
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
    currency: str = typer.Option("EUR", "--currency"),
    taxable_base: str = typer.Option("0", "--taxable-base"),
    iva_rate: str | None = typer.Option(None, "--iva-rate"),
    iva_amount: str = typer.Option("0", "--iva-amount"),
    total_amount: str = typer.Option("0", "--total-amount"),
    notes: str = typer.Option("", "--notes"),
) -> None:
    bucket_id = _ratios_bucket_id()
    result = _payable_invoice_service().add(
        bucket_id=bucket_id,
        counterparty_nif=counterparty_nif,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        counterparty_name=counterparty_name,
        currency=currency,
        taxable_base=_parse_required_decimal(taxable_base, label="taxable-base"),
        iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
        iva_amount=_parse_required_decimal(iva_amount, label="iva-amount"),
        total_amount=_parse_required_decimal(total_amount, label="total-amount"),
        notes=notes,
    )
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)


@payable_invoice_app.command(
    "view", help=tr("cli.app.ledger.payable_invoice.view_help", default="Show one payable invoice record.")
)
def payable_invoice_view(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.payable_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix).")
    ),
) -> None:
    bucket_id = _ratios_bucket_id()
    record = _payable_invoice_service().view(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit(ctx, _business_invoice_payload(record), _business_invoice_text_lines(record))


@payable_invoice_app.command(
    "list",
    help=tr(
        "cli.app.ledger.payable_invoice.list_help", default="List every payable invoice record on the active bucket."
    ),
)
def payable_invoice_list(ctx: typer.Context) -> None:
    bucket_id = _ratios_bucket_id()
    rows = _payable_invoice_service().list_all(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [r.model_dump(mode="json") for r in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.invoice_id}\t{r.counterparty_nif}\t{r.invoice_number}\t{r.invoice_date}\t{r.total_amount}")
    _emit(ctx, payload, lines)


@payable_invoice_app.command(
    "update",
    help=tr(
        "cli.app.ledger.payable_invoice.update_help", default="Update mutable fields on one payable invoice record."
    ),
)
def payable_invoice_update(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.payable_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix).")
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
    from ...application.ledger._business_operation_invoice import BusinessOperationInvoicePatch

    bucket_id = _ratios_bucket_id()
    patch = BusinessOperationInvoicePatch(
        counterparty_nif=counterparty_nif,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        currency=currency,
        taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
        iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
        iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
        total_amount=_parse_decimal(total_amount, label="total-amount"),
        notes=notes,
    )
    result = _payable_invoice_service().update(bucket_id=bucket_id, invoice_id=invoice_id, patch=patch)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)


@payable_invoice_app.command(
    "remove", help=tr("cli.app.ledger.payable_invoice.remove_help", default="Delete one payable invoice record.")
)
def payable_invoice_remove(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.payable_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix).")
    ),
    yes: bool = typer.Option(
        False, "--yes", help=tr("cli.app.ledger.payable_invoice.yes_help", default="Confirm removal.")
    ),
) -> None:
    if not yes:
        raise _bad(
            tr(
                "cli.app.ledger.payable_invoice.yes_required",
                default="--yes is required to remove a payable invoice record",
            )
        )
    bucket_id = _ratios_bucket_id()
    result = _payable_invoice_service().remove(bucket_id=bucket_id, invoice_id=invoice_id)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)


collectible_invoice_app = typer.Typer(
    name="collectible-invoice",
    help=tr(
        "cli.app.ledger.collectible_invoice.group_help", default="Collectible invoice records (a customer owes us)."
    ),
    no_args_is_help=True,
)


@collectible_invoice_app.command(
    "add", help=tr("cli.app.ledger.collectible_invoice.add_help", default="Register a new collectible invoice record.")
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
    currency: str = typer.Option("EUR", "--currency"),
    taxable_base: str = typer.Option("0", "--taxable-base"),
    iva_rate: str | None = typer.Option(None, "--iva-rate"),
    iva_amount: str = typer.Option("0", "--iva-amount"),
    total_amount: str = typer.Option("0", "--total-amount"),
    notes: str = typer.Option("", "--notes"),
) -> None:
    bucket_id = _ratios_bucket_id()
    result = _collectible_invoice_service().add(
        bucket_id=bucket_id,
        counterparty_nif=counterparty_nif,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        counterparty_name=counterparty_name,
        currency=currency,
        taxable_base=_parse_required_decimal(taxable_base, label="taxable-base"),
        iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
        iva_amount=_parse_required_decimal(iva_amount, label="iva-amount"),
        total_amount=_parse_required_decimal(total_amount, label="total-amount"),
        notes=notes,
    )
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)


@collectible_invoice_app.command(
    "view", help=tr("cli.app.ledger.collectible_invoice.view_help", default="Show one collectible invoice record.")
)
def collectible_invoice_view(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.collectible_invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
) -> None:
    bucket_id = _ratios_bucket_id()
    record = _collectible_invoice_service().view(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit(ctx, _business_invoice_payload(record), _business_invoice_text_lines(record))


@collectible_invoice_app.command(
    "list",
    help=tr(
        "cli.app.ledger.collectible_invoice.list_help",
        default="List every collectible invoice record on the active bucket.",
    ),
)
def collectible_invoice_list(ctx: typer.Context) -> None:
    bucket_id = _ratios_bucket_id()
    rows = _collectible_invoice_service().list_all(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [r.model_dump(mode="json") for r in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.invoice_id}\t{r.counterparty_nif}\t{r.invoice_number}\t{r.invoice_date}\t{r.total_amount}")
    _emit(ctx, payload, lines)


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
    from ...application.ledger._business_operation_invoice import BusinessOperationInvoicePatch

    bucket_id = _ratios_bucket_id()
    patch = BusinessOperationInvoicePatch(
        counterparty_nif=counterparty_nif,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        currency=currency,
        taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
        iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
        iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
        total_amount=_parse_decimal(total_amount, label="total-amount"),
        notes=notes,
    )
    result = _collectible_invoice_service().update(bucket_id=bucket_id, invoice_id=invoice_id, patch=patch)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)


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
        False, "--yes", help=tr("cli.app.ledger.collectible_invoice.yes_help", default="Confirm removal.")
    ),
) -> None:
    if not yes:
        raise _bad(
            tr(
                "cli.app.ledger.collectible_invoice.yes_required",
                default="--yes is required to remove a collectible invoice record",
            )
        )
    bucket_id = _ratios_bucket_id()
    result = _collectible_invoice_service().remove(bucket_id=bucket_id, invoice_id=invoice_id)
    payload = _business_invoice_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _business_invoice_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)


app.add_typer(payable_invoice_app, name="payable-invoice")
app.add_typer(collectible_invoice_app, name="collectible-invoice")


inventory_app = typer.Typer(
    name="inventory",
    help=tr(
        "cli.app.ledger.inventory.group_help", default="Per-actividad inventory ledgers (stock, movements, valuation)."
    ),
    no_args_is_help=True,
)
app.add_typer(inventory_app, name="inventory")

inventory_movement_app = typer.Typer(
    name="movement",
    help=tr("cli.app.ledger.inventory.movement_group_help", default="Inventory movement subcommands."),
    no_args_is_help=True,
)
inventory_valuation_app = typer.Typer(
    name="valuation",
    help=tr("cli.app.ledger.inventory.valuation_group_help", default="Inventory valuation subcommands."),
    no_args_is_help=True,
)
inventory_app.add_typer(inventory_movement_app, name="movement")
inventory_app.add_typer(inventory_valuation_app, name="valuation")


def _inventory_service():
    from ...application.inventory import InventoryService

    return InventoryService()


@inventory_app.command(
    "list",
    help=tr(
        "cli.app.ledger.inventory.list_help", default="List every per-actividad inventory ledger on the active bucket."
    ),
)
def inventory_list(ctx: typer.Context) -> None:
    bucket_id = _ratios_bucket_id()
    rows = _inventory_service().list_all(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        lines.append(
            f"{row.actividad_id}\t{row.year}\t{row.valuation_method.value}\t"
            f"opening={row.opening_stock}\tmovements={row.movement_count}"
        )
    _emit(ctx, payload, lines)


@inventory_app.command(
    "create",
    help=tr(
        "cli.app.ledger.inventory.create_help", default="Create a fresh inventory ledger for one actividad and year."
    ),
)
def inventory_create(
    ctx: typer.Context,
    actividad_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.inventory.actividad_id_help", default="Actividad identifier.")
    ),
    year: int = typer.Option(..., "--year", help=tr("cli.app.ledger.inventory.year_help", default="Fiscal year.")),
    valuation_method: str = typer.Option(
        ...,
        "--valuation-method",
        help=tr("cli.app.ledger.inventory.valuation_method_help", default="Valuation method (fifo or pmp)."),
    ),
    opening_stock: str = typer.Option(
        "0", "--opening-stock", help=tr("cli.app.ledger.inventory.opening_stock_help", default="Opening stock value.")
    ),
) -> None:
    bucket_id = _ratios_bucket_id()
    result = _inventory_service().create(
        bucket_id=bucket_id,
        actividad_id=actividad_id,
        year=year,
        valuation_method=valuation_method,
        opening_stock=_parse_required_decimal(opening_stock, label="opening-stock"),
    )
    ledger = result.ledger
    payload = ledger.model_dump(mode="json")
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    _emit(
        ctx,
        payload,
        (
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"valuation_method\t{ledger.valuation_method.value}",
            f"opening_stock\t{ledger.opening_stock}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )


@inventory_movement_app.command(
    "add",
    help=tr(
        "cli.app.ledger.inventory.movement_add_help",
        default="Append one movement (purchase/sale/adjustment) to an actividad ledger.",
    ),
)
def inventory_movement_add(
    ctx: typer.Context,
    actividad_id: str = typer.Option(
        ..., "--actividad-id", help=tr("cli.app.ledger.inventory.actividad_id_help", default="Actividad identifier.")
    ),
    year: int = typer.Option(..., "--year", help=tr("cli.app.ledger.inventory.year_help", default="Fiscal year.")),
    movement_id: str = typer.Option(
        ...,
        "--movement-id",
        help=tr("cli.app.ledger.inventory.movement_id_help", default="Movement identifier (unique per ledger)."),
    ),
    movement_date: str = typer.Option(
        ..., "--date", help=tr("cli.app.ledger.inventory.movement_date_help", default="Movement date (YYYY-MM-DD).")
    ),
    kind: str = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.inventory.movement_kind_help", default="Movement kind (purchase, sale, adjustment, ...)"
        ),
    ),
    quantity: str = typer.Option(
        ...,
        "--quantity",
        help=tr("cli.app.ledger.inventory.quantity_help", default="Movement quantity (positive or negative)."),
    ),
    unit_cost: str | None = typer.Option(
        None,
        "--unit-cost",
        help=tr("cli.app.ledger.inventory.unit_cost_help", default="Unit cost (purchase movements)."),
    ),
    taxable_base: str | None = typer.Option(
        None, "--taxable-base", help=tr("cli.app.ledger.inventory.taxable_base_help", default="Taxable base (for VAT).")
    ),
    vat_rate: str = typer.Option(
        "21.00", "--vat-rate", help=tr("cli.app.ledger.inventory.vat_rate_help", default="VAT rate in percent.")
    ),
) -> None:
    from ...application.inventory import InventoryMovementCommand
    from ...domain.profile.inventory import MovementKind

    try:
        kind_enum = MovementKind(kind)
    except ValueError as exc:
        raise _bad(
            tr("cli.app.ledger.inventory.unknown_movement_kind", default="Unknown movement kind: {kind!r}").format(
                kind=kind
            )
        ) from exc

    bucket_id = _ratios_bucket_id()
    command = InventoryMovementCommand(
        movement_id=movement_id,
        movement_date=_parse_iso_date(movement_date, label="--date"),
        kind=kind_enum,
        quantity=_parse_required_decimal(quantity, label="quantity"),
        unit_cost=_parse_decimal(unit_cost, label="unit-cost"),
        taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
        vat_rate=_parse_required_decimal(vat_rate, label="vat-rate"),
    )
    result = _inventory_service().movement_add(
        bucket_id=bucket_id,
        actividad_id=actividad_id,
        year=year,
        movement=command,
    )
    ledger = result.ledger
    payload = ledger.model_dump(mode="json")
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    _emit(
        ctx,
        payload,
        (
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"movements\t{len(ledger.period_movements)}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )


@inventory_valuation_app.command(
    "preview",
    help=tr(
        "cli.app.ledger.inventory.valuation_preview_help",
        default="Preview closing stock and COGS for one actividad/year ledger.",
    ),
)
def inventory_valuation_preview(
    ctx: typer.Context,
    actividad_id: str = typer.Option(
        ..., "--actividad-id", help=tr("cli.app.ledger.inventory.actividad_id_help", default="Actividad identifier.")
    ),
    year: int = typer.Option(..., "--year", help=tr("cli.app.ledger.inventory.year_help", default="Fiscal year.")),
) -> None:
    bucket_id = _ratios_bucket_id()
    result = _inventory_service().valuation_preview(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
    preview = result.preview
    payload = preview.model_dump(mode="json")
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    _emit(
        ctx,
        payload,
        (
            f"bucket\t{bucket_id}",
            f"actividad_id\t{preview.actividad_id}",
            f"year\t{preview.year}",
            f"valuation_method\t{preview.valuation_method.value}",
            f"closing_stock\t{preview.closing_stock}",
            f"cogs\t{preview.cogs}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )


evidence_app = typer.Typer(
    name="evidence",
    help=tr(
        "cli.app.ledger.evidence.group_help",
        default="Purchase invoice evidence records (PDF or image).",
    ),
    no_args_is_help=True,
)
app.add_typer(evidence_app, name="evidence")


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
        None, "--supplier", help=tr("cli.app.ledger.evidence.supplier_help", default="Supplier name.")
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
    notes: str = typer.Option("", "--notes", help=tr("cli.app.ledger.evidence.notes_help", default="Free-text notes.")),
) -> None:
    """Register a purchase invoice evidence record and return its id."""
    transaction_repository = _tx_repo(_state())
    result = _evidence_service().add(
        bucket_id=transaction_repository.bucket_id,
        source_path=source_path,
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
        iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
        iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
        notes=notes,
    )
    payload = _evidence_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _evidence_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)


@evidence_app.command(
    "view",
    help=tr(
        "cli.app.ledger.evidence.view_help",
        default="View one purchase invoice evidence record.",
    ),
)
def evidence_view(
    ctx: typer.Context,
    evidence_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.evidence.evidence_id_help", default="Evidence record id.")
    ),
) -> None:
    transaction_repository = _tx_repo(_state())
    record = _evidence_service().view(
        bucket_id=transaction_repository.bucket_id,
        evidence_id=evidence_id,
    )
    _emit(ctx, _evidence_payload(record), _evidence_text_lines(record))


@evidence_app.command(
    "list",
    help=tr(
        "cli.app.ledger.evidence.list_help",
        default="List every purchase invoice evidence record in the active bucket.",
    ),
)
def evidence_list(ctx: typer.Context) -> None:
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
            f"{data.get('taxable_base') or '-'}\t{data.get('notes') or '-'}"
        )
    _emit(ctx, payload, lines)


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
        ..., help=tr("cli.app.ledger.evidence.evidence_id_help", default="Evidence record id.")
    ),
    supplier: str | None = typer.Option(None, "--supplier"),
    invoice_number: str | None = typer.Option(None, "--invoice-number"),
    invoice_date: str | None = typer.Option(None, "--invoice-date"),
    taxable_base: str | None = typer.Option(None, "--taxable-base"),
    iva_rate: str | None = typer.Option(None, "--iva-rate"),
    iva_amount: str | None = typer.Option(None, "--iva-amount"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    transaction_repository = _tx_repo(_state())
    patch = PurchaseInvoiceEvidencePatch(
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
        iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
        iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
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
    _emit(ctx, payload, lines)


@evidence_app.command(
    "remove",
    help=tr(
        "cli.app.ledger.evidence.remove_help",
        default="Delete a purchase invoice evidence record.",
    ),
)
def evidence_remove(
    ctx: typer.Context,
    evidence_id: str = typer.Argument(
        ..., help=tr("cli.app.ledger.evidence.evidence_id_help", default="Evidence record id.")
    ),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.app.ledger.evidence.yes_help", default="Confirm removal.")),
) -> None:
    if not yes:
        raise _bad(tr("cli.app.ledger.evidence.yes_required", default="--yes is required to remove an evidence record"))
    transaction_repository = _tx_repo(_state())
    result = _evidence_service().remove(
        bucket_id=transaction_repository.bucket_id,
        evidence_id=evidence_id,
    )
    payload = _evidence_payload(result.record)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _evidence_text_lines(result.record)
    lines.append(f"bucket_event_ids\t{','.join(result.bucket_event_ids)}")
    _emit(ctx, payload, lines)
