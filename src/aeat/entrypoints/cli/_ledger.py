from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

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
    query_ledger_review_rows,
    remove_manual_transaction,
    reset_ledger_catalogue,
    resolve_transaction_id,
    stash_manual_transaction,
    summarize_manual_transactions,
    update_manual_transaction_fields,
)
from ...application.review import (
    FilterParseError,
    LedgerReviewFilterSpec,
)
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionDirection,
)
from ._common import (
    _bad,
    _canonical_period,
    _emit,
    _parse_iso_date,
    _state,
    _tx_repo,
)
from ._i18n import tr

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


def _bucket_transaction_ids(transaction_repository: object) -> tuple[str, ...]:
    """Return the full transaction ids known to the active bucket."""
    bucket_id = transaction_repository.bucket_id  # type: ignore[attr-defined]
    results = list_manual_transactions(
        bucket_id=bucket_id,
        transaction_repository=transaction_repository,  # type: ignore[arg-type]
    )
    return tuple(result.transaction.transaction_id for result in results)


def _resolve_id(transaction_repository: object, prefix: str) -> str:
    """Resolve a CLI-supplied id or unambiguous prefix to a full transaction id."""
    return resolve_transaction_id(prefix, _bucket_transaction_ids(transaction_repository))


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


@app.command("create", help=tr("cli.ledger.create.help"))
def ledger_create(
    ctx: typer.Context,
    booked_date: str = typer.Option(..., "--date", help=tr("cli.ledger.create.date_help")),
    amount: str = typer.Option(..., "--amount", help=tr("cli.ledger.create.amount_help")),
    direction: TransactionDirection = typer.Option(..., "--direction", help=tr("cli.ledger.create.direction_help")),
    description: str = typer.Option(..., "--description", help=tr("cli.ledger.create.description_help")),
    value_date: str | None = typer.Option(None, "--value-date", help=tr("cli.ledger.create.value_date_help")),
    currency: str = typer.Option("EUR", "--currency", help=tr("cli.ledger.create.currency_help")),
    counterparty: str | None = typer.Option(None, "--counterparty", help=tr("cli.ledger.create.counterparty_help")),
    business_classification: BusinessClassification = typer.Option(
        BusinessClassification.NOT_YET_PROCESSED,
        "--classification",
        help=tr("cli.ledger.create.classification_help"),
    ),
    business_pct: str | None = typer.Option(None, "--business-pct", help=tr("cli.ledger.create.business_pct_help")),
    category_id: str | None = typer.Option(None, "--category-id", help=tr("cli.ledger.create.category_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.create.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.create.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.create.iva_amount_help")),
    irpf_category: str | None = typer.Option(None, "--irpf-category", help=tr("cli.ledger.create.irpf_category_help")),
    usage_ratio_id: str | None = typer.Option(None, "--usage-ratio-id", help=tr("cli.ledger.create.usage_ratio_help")),
    prorrata_reference: str | None = typer.Option(
        None,
        "--prorrata-reference",
        help=tr("cli.ledger.create.prorrata_reference_help"),
    ),
    purchase_invoice_evidence_id: str | None = typer.Option(
        None,
        "--purchase-invoice-evidence-id",
        help=tr("cli.ledger.create.purchase_invoice_evidence_help"),
    ),
    attachment_ids: list[str] = typer.Option(
        [],
        "--attachment-id",
        help=tr("cli.ledger.create.attachment_help"),
    ),
    notes: str = typer.Option("", "--notes", help=tr("cli.ledger.create.notes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.create.actor_help")),
    idempotency_key: str | None = typer.Option(
        None,
        "--idempotency-key",
        help=tr("cli.ledger.create.idempotency_key_help"),
    ),
) -> None:
    """Create one manual ledger transaction through the bucket-scoped backend."""
    current_state = _state()
    transaction_repository = _tx_repo(current_state)
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
        business_pct=_parse_decimal(business_pct, label="business-pct"),
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
        actor=actor or current_state.active_profile or "operator",
        source_command="aeat app ledger create",
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


@app.command("edit", help=tr("cli.ledger.edit.help"))
def ledger_edit(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.edit.id_help")),
    booked_date: str | None = typer.Option(None, "--date", help=tr("cli.ledger.edit.date_help")),
    value_date: str | None = typer.Option(None, "--value-date", help=tr("cli.ledger.edit.value_date_help")),
    amount: str | None = typer.Option(None, "--amount", help=tr("cli.ledger.edit.amount_help")),
    direction: TransactionDirection | None = typer.Option(
        None,
        "--direction",
        help=tr("cli.ledger.edit.direction_help"),
    ),
    currency: str | None = typer.Option(None, "--currency", help=tr("cli.ledger.edit.currency_help")),
    counterparty: str | None = typer.Option(None, "--counterparty", help=tr("cli.ledger.edit.counterparty_help")),
    description: str | None = typer.Option(None, "--description", help=tr("cli.ledger.edit.description_help")),
    taxable_base: str | None = typer.Option(None, "--taxable-base", help=tr("cli.ledger.edit.taxable_base_help")),
    iva_rate: str | None = typer.Option(None, "--iva-rate", help=tr("cli.ledger.edit.iva_rate_help")),
    iva_amount: str | None = typer.Option(None, "--iva-amount", help=tr("cli.ledger.edit.iva_amount_help")),
    irpf_category: str | None = typer.Option(None, "--irpf-category", help=tr("cli.ledger.edit.irpf_category_help")),
    notes: str | None = typer.Option(None, "--notes", help=tr("cli.ledger.edit.notes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.edit.actor_help")),
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
        actor=actor or state.active_profile or "operator",
        source_command="aeat app ledger edit",
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
        actor=actor or state.active_profile or "operator",
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
    result = update_manual_transaction_fields(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        patch=_patch_from_options(
            business_classification=BusinessClassification.MIXED,
            business_pct=_parse_required_decimal(business_pct, label="business-pct"),
            category_id=category_id,
            usage_ratio_id=usage_ratio_id,
            prorrata_reference=prorrata_reference,
        ),
        actor=actor or state.active_profile or "operator",
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
        actor=actor or state.active_profile or "operator",
        source_command="aeat app ledger attach",
        transaction_repository=transaction_repository,
    )
    _emit_update_result(ctx, result.transaction, result.ref.bucket_id, result.bucket_event_ids)


@app.command("archive", help=tr("cli.ledger.archive.help"))
def ledger_archive(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.archive.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.archive.reason_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.archive.actor_help")),
) -> None:
    """Archive one ledger transaction through the bucket-scoped backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = archive_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or state.active_profile or "operator",
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
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.stash.actor_help")),
) -> None:
    """Stash one ledger transaction through the bucket-scoped backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = stash_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or state.active_profile or "operator",
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
        actor=actor or state.active_profile or "operator",
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
        actor=actor or state.active_profile or "operator",
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
            actor=actor or state.active_profile or "operator",
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


@app.command("read", help=tr("cli.ledger.read.help"))
def ledger_read(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.read.transaction_id_help")),
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
    result = get_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=transaction_id,
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
        actor = current_state.active_profile or "operator"
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
