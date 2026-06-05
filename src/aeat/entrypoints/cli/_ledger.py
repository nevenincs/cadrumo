"""User-facing ledger and transaction management CLI commands.

Provides the ``aeat ledger`` command group for importing, reviewing, and
exporting financial transaction data. Transaction records are accessed
through :class:`TransactionCatalogueRepository` and invoice records through
:class:`InvoiceCatalogueRepository`. Lifecycle events are appended to the
profile audit trail via :class:`BucketEventHistoryRepository`.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol

import typer
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from ...application.export import ExportSerializationFormat
from ...application.ledger import (
    LedgerExportCommand,
    LedgerReviewQuery,
    LedgerReviewQueryResult,
    LedgerReviewRow,
    LedgerTransactionResultPayload,
    LLMProvider,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    apply_llm_classification,
    available_llm_providers,
    compute_display_id_width,
    create_manual_transaction,
    export_ledger_transactions,
    get_manual_transaction,
    is_llm_provider_available,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_review_status,
    ledger_transaction_tracking_payload,
    list_manual_transactions,
    query_ledger_review_rows,
    resolve_transaction_id,
    suggest_llm_classification,
    summarize_manual_transactions,
    update_manual_transaction_fields,
)
from ...application.review import (
    FilterParseError,
    LedgerReviewFilterSpec,
)
from ...core import resolve_active_bucket_id
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.categories import (
    CATEGORY_FAMILY_MEMBERS,
    SpendingCategory,
    SpendingCategoryFamily,
)
from ...domain.contribuyente._renta_codes import FiscalResidency
from ...domain.deadlines._models import IrpfSpecialRegime
from ...domain.iva._schema import EUMemberState, IvaCategory
from ...domain.transactions import (
    BusinessClassification,
    LLMClassifierError,
    Transaction,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionIdPrefixError,
)
from ._common import (
    _bad,
    _canonical_period,
    _emit_envelope,
    _parse_iso_date,
    _profile_to_taxpayer,
    _state,
    _tx_repo,
)
from ._ledger_business_invoice_cli import (
    collectible_invoice_app,
    payable_invoice_app,
    register_business_invoice_commands,
)
from ._ledger_evidence_cli import register_evidence_commands
from ._ledger_import_cli import register_import_commands
from ._ledger_inventory_cli import inventory_app, register_inventory_commands
from ._ledger_lifecycle_cli import (
    ledger_archive,
    ledger_attach,
    ledger_doclink,
    ledger_merge,
    ledger_remove,
    ledger_reset,
    ledger_split,
    ledger_stash,
    register_lifecycle_commands,
)
from ._ledger_list import parse_ledger_list_filter_spec, project_ledger_list
from ._ledger_ratios_cli import ratios_app, register_ratios_commands
from ._ledger_rules_cli import register_rule_commands, rule_app
from ._schemas import OutputSchema

_log = get_logger(__name__)

__all__ = [
    "app",
    "collectible_invoice_app",
    "inventory_app",
    "ledger_archive",
    "ledger_attach",
    "ledger_doclink",
    "ledger_merge",
    "ledger_remove",
    "ledger_reset",
    "ledger_split",
    "ledger_stash",
    "payable_invoice_app",
    "ratios_app",
    "rule_app",
]

app = typer.Typer(
    name="ledger",
    help=tr("cli.ledger.app_help"),
    no_args_is_help=True,
)


def _invoice_link_error_bad_parameter() -> typer.BadParameter:
    return _bad(tr("errors.error.error_financial_invoices_invoice_link"))


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


def _category_catalogue_text() -> str:
    """Return the comma-joined recognised spending-category ids."""
    return ", ".join(category.value for category in SpendingCategory)


def _validate_category_id(category_id: str | None) -> str | None:
    """Reject a `--category-id` value outside the closed spending taxonomy.

    The canonical category set is :class:`SpendingCategory` — the
    closed enum of deductible autónomo expense classes whose members
    map one-to-one onto the modelo registry bindings. Free text such
    as ``ventas_actividad`` is silently accepted by the bare string
    field, so an operator can miscategorise rows all year and only
    discover the drift when modelo calculations are wrong. Validating
    here refuses an unknown id immediately and points at
    ``aeat app ledger categories`` for the recognised catalogue.
    """
    if category_id is None:
        return None
    trimmed = category_id.strip()
    if not trimmed:
        return None
    try:
        return SpendingCategory(trimmed).value
    except ValueError as exc:
        # Show one concrete valid id inline: operators repeatedly
        # guessed compound keys (`office:material_oficina`,
        # `office_material_oficina`); only the bare enum value is
        # accepted, so the refusal must demonstrate the exact shape.
        example = next(iter(SpendingCategory)).value
        raise _bad(
            tr(
                "cli.ledger.errors.unknown_category",
                category=category_id,
                example=example,
            )
        ) from exc


def _ledger_validation_bad(error: ValidationError) -> typer.BadParameter:
    """Convert a leaked pydantic `ValidationError` into a specific refusal.

    The generic CLI error boundary wraps every leaked
    :exc:`pydantic.ValidationError` into the opaque "command input
    failed validation. Run ``aeat config repair``" message, discarding
    the real cause. The ledger command models raise precise validator
    messages (for example "business_pct must be None unless
    classification is MIXED"); this helper extracts those messages so
    the operator sees the actual illegal field combination rather than
    a misleading repair hint.
    """
    details = "; ".join(_format_validation_error(item) for item in error.errors())
    return _bad(
        tr(
            "cli.ledger.errors.command_input_invalid",
            details=details or tr("cli.ledger.errors.command_input_invalid_fallback"),
        )
    )


def _format_validation_error(item: ErrorDetails) -> str:
    """Render one pydantic error entry as ``field: message`` text."""
    location = item.get("loc", ())
    message = str(item.get("msg", "")).removeprefix("Value error, ").strip()
    field_path = ".".join(str(part) for part in location if part != "__root__")
    if field_path:
        return f"{field_path}: {message}"
    return message


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
        raise _bad(tr("cli.ledger.errors.id_prefix_unknown", message=raw_message)) from exc


def _patch_from_options(**values: object) -> ManualLedgerTransactionPatch:
    return ManualLedgerTransactionPatch.model_validate(
        {key: value for key, value in values.items() if value is not None}
    )


def _emit_update_result(
    ctx: typer.Context,
    result_transaction: Transaction,
    bucket_id: str,
    events: tuple[str, ...],
    *,
    command: str,
    result_cls: type[OutputSchema],
) -> None:
    transaction_payload = ledger_transaction_payload(result_transaction)
    review_status = ledger_transaction_review_status(result_transaction)
    result = result_cls.model_validate(
        {
            "bucket_id": bucket_id,
            "transaction_id": result_transaction.transaction_id,
            "bucket_event_ids": list(events),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        }
    )
    _emit_envelope(
        ctx,
        command=command,
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{result_transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
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
    currency: str = typer.Option(DEFAULT_CURRENCY, "--currency", help=tr("cli.ledger.add.currency_help")),
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
    source_jurisdiction: str | None = typer.Option(
        None,
        "--source-jurisdiction",
        help=tr("cli.ledger.add.source_jurisdiction_help"),
    ),
) -> None:
    """Create one manual ledger transaction through the bucket-scoped backend."""
    current_state = _state()
    transaction_repository = _tx_repo(current_state)
    validated_category_id = _validate_category_id(category_id)
    resolved_business_pct = _resolve_business_pct_with_censo(
        bucket_id=transaction_repository.bucket_id,
        active_profile=resolve_active_bucket_id(),
        category_id=validated_category_id,
        operator_supplied=_parse_decimal(business_pct, label="business-pct"),
    )
    active_taxpayer = _profile_to_taxpayer(current_state)
    resolved_source_jurisdiction = _resolve_source_jurisdiction(
        source_jurisdiction,
        fiscal_residency=active_taxpayer.fiscal_residency,
        irpf_special_regime=active_taxpayer.irpf_special_regime,
    )
    try:
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
            category_id=validated_category_id,
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
            source_jurisdiction=resolved_source_jurisdiction,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    result = create_manual_transaction(
        command,
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerAddResult

    transaction_payload = ledger_transaction_payload(result.transaction)
    add_result = LedgerAddResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.ref.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "transaction": transaction_payload.model_dump(mode="json"),
        }
    )
    _emit_envelope(
        ctx,
        command="ledger.add",
        result=add_result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{result.ref.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
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
    group: str | None = typer.Option(None, "--group", help=tr("cli.ledger.update.group_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.update.actor_help")),
) -> None:
    """Correct editable transaction facts through the bucket-scoped backend."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    # A leaked `pydantic.ValidationError` (negative amount, illegal field
    # combination) would be swallowed by the generic CLI boundary into an
    # opaque "config repair" hint. Catch it here and surface the real
    # validator cause, mirroring the `ledger classify` treatment.
    try:
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
                group_label=group,
            ),
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger update",
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerUpdateResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.update",
        result_cls=LedgerUpdateResult,
    )


@app.command("classify", help=tr("cli.ledger.classify.help"))
def ledger_classify(
    ctx: typer.Context,
    transaction_id: str | None = typer.Option(None, "--id", help=tr("cli.ledger.classify.id_help")),
    classification: BusinessClassification | None = typer.Option(
        None,
        "--classification",
        help=tr("cli.ledger.classify.classification_help"),
    ),
    from_csv: str | None = typer.Option(
        None,
        "--from-csv",
        help=tr(
            "cli.ledger.classify.from_csv_help",
            default="Path to a CSV file with columns transaction_id, classification[, category_id].",
        ),
    ),
    business_pct: str | None = typer.Option(
        None,
        "--business-pct",
        help=tr("cli.ledger.classify.business_pct_help"),
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
    iva_category: IvaCategory | None = typer.Option(
        None,
        "--iva-category",
        help=tr("cli.ledger.classify.iva_category_help"),
    ),
    counterparty_eu_member_state: EUMemberState | None = typer.Option(
        None,
        "--counterparty-eu-member-state",
        help=tr("cli.ledger.classify.counterparty_eu_member_state_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.classify.actor_help")),
    reaffirm: bool = typer.Option(False, "--reaffirm", help=tr("cli.ledger.classify.reaffirm_help")),
    llm: LLMProvider | None = typer.Option(None, "--llm", help=tr("cli.ledger.classify.llm_help")),
    apply: bool = typer.Option(False, "--apply", help=tr("cli.ledger.classify.apply_help")),
) -> None:
    """Classify one ledger transaction (--id), via LLM (--llm), or in bulk (--from-csv)."""
    if llm is not None:
        _ledger_classify_llm(
            ctx,
            transaction_id=transaction_id,
            classification=classification,
            from_csv=from_csv,
            business_pct=business_pct,
            provider=llm,
            apply=apply,
            actor=actor,
        )
        return
    from ...application.ledger import bulk_classify_from_csv as _bulk_classify

    state = _state()
    transaction_repository = _tx_repo(state)

    if from_csv is not None:
        # Bulk-classify mode: --id and --classification must not be combined
        if transaction_id is not None or classification is not None:
            raise _bad(
                tr(
                    "cli.ledger.classify.from_csv_exclusive",
                    default="--from-csv cannot be combined with --id or --classification.",
                )
            )
        csv_path = Path(from_csv)
        if not csv_path.exists():
            raise _bad(
                tr("cli.ledger.classify.from_csv_not_found", path=from_csv, default=f"CSV file not found: {from_csv}")
            )
        csv_text = csv_path.read_text(encoding="utf-8")
        result = _bulk_classify(
            bucket_id=transaction_repository.bucket_id,
            csv_text=csv_text,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger classify",
            transaction_repository=transaction_repository,
        )
        lines = [
            tr(
                "cli.ledger.classify.bulk_summary",
                total=result.total,
                applied=result.applied,
                skipped=result.skipped,
                fail=len(result.failures),
                default=(
                    f"bulk classify: {result.total} rows, {result.applied} applied, "
                    f"{result.skipped} skipped, {len(result.failures)} failed"
                ),
            )
        ]
        from ._ledger_payloads import LedgerClassifyResult

        for failure in result.failures:
            # MACHINE-FORMAT-RATIONALE-LEDGER-BULK-CLASSIFY-FAILURE:
            # tab-separated machine record (id, reason), not user-facing prose.
            lines.append(f"  failed\t{failure.transaction_id}\t{failure.reason}")
        classify_result = LedgerClassifyResult.model_validate(
            {
                "total": result.total,
                "applied": result.applied,
                "skipped": result.skipped,
                "failures": [f.model_dump(mode="json") for f in result.failures],
            }
        )
        _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)
        return

    # Single-transaction mode: --id and --classification are required
    if transaction_id is None:
        raise _bad(tr("cli.ledger.classify.id_required", default="--id is required when --from-csv is not provided."))
    if classification is None:
        raise _bad(
            tr(
                "cli.ledger.classify.classification_required",
                default="--classification is required when --from-csv is not provided.",
            )
        )
    validated_category_id = _validate_category_id(category_id)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    if classification is BusinessClassification.MIXED and business_pct is None:
        # MIXED demands a proportion; surface the `--business-pct` flag
        # directly rather than letting the patch validator's generic
        # message route through the opaque boundary.
        raise _bad(tr("cli.ledger.classify.mixed_requires_business_pct"))
    if classification is not BusinessClassification.MIXED and business_pct is not None:
        # `--business-pct` only carries meaning for a MIXED row; a
        # BUSINESS or PERSONAL classification is wholly business or
        # wholly private. Refuse rather than silently dropping it.
        raise _bad(tr("cli.ledger.classify.business_pct_requires_mixed"))
    # A leaked `pydantic.ValidationError` (negative `--taxable-base`,
    # an illegal field combination) is otherwise wrapped by the generic
    # CLI boundary into "command input failed validation. Run config
    # repair" — a misleading hint, since `config repair` cannot fix a
    # bad CLI argument. Catch it here and surface the real validator
    # cause, matching the `ledger add` / `ledger review --id` treatment.
    try:
        patch = _patch_from_options(
            business_classification=classification,
            business_pct=_parse_decimal(business_pct, label="business-pct"),
            category_id=validated_category_id,
            taxable_base=_parse_decimal(taxable_base, label="taxable-base"),
            iva_rate=_parse_decimal(iva_rate, label="iva-rate"),
            iva_amount=_parse_decimal(iva_amount, label="iva-amount"),
            irpf_category=irpf_category,
            iva_category=iva_category,
            counterparty_eu_member_state=counterparty_eu_member_state,
        )
        result = update_manual_transaction_fields(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            patch=patch,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger classify",
            reaffirm=reaffirm,
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerClassifyResult

    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = LedgerClassifyResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        }
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
        f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
        f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    if reaffirm:
        lines.insert(0, tr("cli.ledger.classify.reaffirmed"))
    _emit_envelope(
        ctx,
        command="ledger.classify",
        result=classify_result,
        lines=lines,
    )


def _ledger_classify_llm(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    from_csv: str | None,
    business_pct: str | None,
    provider: LLMProvider,
    apply: bool,
    actor: str | None,
) -> None:
    """Run the LLM suggest / apply loop for ``aeat app ledger classify --llm``.

    Without ``--apply`` the model's suggestion is printed for review and
    nothing is persisted (the suggest step; rejecting is simply not applying).
    With ``--apply`` the decision is written via
    :func:`apply_llm_classification` with ``llm:<model>`` provenance. ``--llm``
    is mutually exclusive with the manual ``--classification`` / ``--from-csv``
    paths (manual classification is always the explicit override).
    """
    from ._ledger_payloads import LedgerClassifyResult

    if classification is not None or from_csv is not None:
        raise _bad(
            tr(
                "cli.ledger.classify.llm_exclusive",
                default="--llm cannot be combined with --classification or --from-csv; "
                "the manual path is the explicit operator override.",
            )
        )
    if transaction_id is None:
        raise _bad(tr("cli.ledger.classify.id_required", default="--id is required when --from-csv is not provided."))
    if not is_llm_provider_available(provider):
        # Instructive refusal: name the provider and the CLI it needs on PATH,
        # never a crash. The subprocess backend shells to a local CLI binary.
        raise _bad(
            tr(
                "cli.ledger.classify.llm_provider_unavailable",
                provider=provider.value,
                default=(
                    f"LLM provider {provider.value!r} is unavailable: its CLI is not on PATH. "
                    f"Install the {provider.value!r} CLI and ensure it is on PATH, "
                    "or run 'aeat app ledger providers' to list usable providers."
                ),
            )
        )

    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    try:
        suggestion = suggest_llm_classification(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            provider=provider,
            transaction_repository=transaction_repository,
        )
    except LLMClassifierError as exc:
        raise _bad(
            tr(
                "cli.ledger.classify.llm_failed",
                reason=str(exc),
                default=f"LLM classification failed: {exc}",
            )
        ) from exc

    if not apply:
        # Suggest (preview) — persist nothing. Rejecting = not applying.
        classify_result = LedgerClassifyResult.model_validate(
            {
                "llm": True,
                "persisted": False,
                "transaction_id": suggestion.transaction_id,
                "provider": suggestion.provider.value,
                "classification": suggestion.classification.value,
                "category": suggestion.category.value if suggestion.category is not None else None,
                "confidence": format(suggestion.confidence, "f"),
                "reason": suggestion.reason,
                "provenance": suggestion.provenance,
            }
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{suggestion.classification.value}",
            f"{tr('cli.ledger.labels.category_id')}\t{suggestion.category.value if suggestion.category else ''}",
            f"{tr('cli.ledger.classify.llm_confidence_label')}\t{format(suggestion.confidence, 'f')}",
            f"{tr('cli.ledger.classify.llm_reason_label')}\t{suggestion.reason}",
            tr("cli.ledger.classify.llm_review_hint"),
        ]
        _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)
        return

    try:
        result = apply_llm_classification(
            suggestion,
            bucket_id=transaction_repository.bucket_id,
            business_pct=_parse_decimal(business_pct, label="business-pct"),
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger classify --llm --apply",
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc

    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = LedgerClassifyResult.model_validate(
        {
            "llm": True,
            "persisted": True,
            "provider": suggestion.provider.value,
            "provenance": suggestion.provenance,
            "confidence": format(suggestion.confidence, "f"),
            "reason": suggestion.reason,
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        }
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


@app.command("providers", help=tr("cli.ledger.providers.help"))
def ledger_providers(ctx: typer.Context) -> None:
    """List which subprocess LLM providers have a usable CLI on PATH."""
    from ._ledger_payloads import LedgerProvidersResult

    listings = available_llm_providers()
    result = LedgerProvidersResult.model_validate(
        {
            "providers": [
                {
                    "provider": item.provider.value,
                    "cli_binary": item.cli_binary,
                    "available": item.available,
                    "resolved_path": item.resolved_path,
                }
                for item in listings
            ]
        }
    )
    lines: list[str] = []
    for item in listings:
        status = "available" if item.available else "unavailable"
        location = item.resolved_path or item.cli_binary
        # tab-separated machine record (provider, status, location), not prose.
        lines.append(f"{item.provider.value}\t{status}\t{location}")
    _emit_envelope(ctx, command="ledger.providers", result=result, lines=lines)


@app.command("categories", help=tr("cli.ledger.categories.help"))
def ledger_categories(ctx: typer.Context) -> None:
    """List the recognised `--category-id` spending-category catalogue.

    The catalogue is the closed :class:`SpendingCategory` taxonomy of
    deductible autónomo expense classes, grouped by coarse
    :class:`SpendingCategoryFamily`. Every id printed here is a legal
    value for the ``--category-id`` flag on ``ledger add``,
    ``ledger classify``, and ``ledger allocate``; any other value is
    refused. The grouped view lets an operator discover the correct id
    before classifying a transaction rather than after modelo
    calculations surface the drift.

    The taxonomy is deductible-expense only. Income (INCOMING)
    transactions are classified by direction alone and need no
    ``--category-id``; ``ledger check`` / ``ledger preflight`` do not
    flag a pure-income transaction as ``missing_category``.
    """
    families: list[dict[str, object]] = []
    # The first column is the literal `--category-id` value; the second
    # is the family it belongs to. An earlier `family<TAB>id` layout
    # read like a compound key, so operators guessed `office:material…`
    # or `office_material…` and every guess was refused. The id is now
    # first and the column header names it explicitly.
    lines: list[str] = [
        tr("cli.ledger.categories.header"),
        f"{tr('cli.ledger.categories.id_column')}\t{tr('cli.ledger.categories.family_column')}",
    ]
    first_category_id: str | None = None
    for family in SpendingCategoryFamily:
        members = CATEGORY_FAMILY_MEMBERS.get(family, ())
        if not members:
            continue
        category_ids = tuple(member.value for member in members)
        families.append({"family": family.value, "category_ids": list(category_ids)})
        for category_id in category_ids:
            if first_category_id is None:
                first_category_id = category_id
            lines.append(f"{category_id}\t{family.value}")
    if first_category_id is not None:
        lines.append(tr("cli.ledger.categories.usage_example", example=first_category_id))
    lines.append(tr("cli.ledger.categories.income_note"))
    from ._ledger_payloads import LedgerCategoriesResult

    _emit_envelope(
        ctx,
        command="ledger.categories",
        result=LedgerCategoriesResult.model_validate(
            {
                "families": families,
                "category_ids": [category.value for category in SpendingCategory],
                "income_requires_category": False,
            }
        ),
        lines=lines,
    )


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
    validated_category_id = _validate_category_id(category_id)
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
    # A leaked `pydantic.ValidationError` (business_pct out of range, illegal
    # field combination) is caught here and surfaced as the real validator
    # cause, mirroring the `ledger classify` treatment.
    try:
        result = update_manual_transaction_fields(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            patch=_patch_from_options(
                business_classification=allocation_classification,
                business_pct=parsed_business_pct,
                category_id=validated_category_id,
                usage_ratio_id=usage_ratio_id,
                prorrata_reference=prorrata_reference,
            ),
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger allocate",
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerAllocateResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.allocate",
        result_cls=LedgerAllocateResult,
    )


register_lifecycle_commands(app)


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
            raise _invoice_link_error_bad_parameter() from exc

    evidence_result_payload: LedgerTransactionResultPayload | None = None
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
    if evidence_result_payload is not None:
        payload["evidence_update"] = evidence_result_payload.model_dump(mode="python")
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
    from ._ledger_payloads import LedgerLinkResult

    _emit_envelope(
        ctx,
        command="ledger.link",
        result=LedgerLinkResult.model_validate(payload),
        lines=lines,
    )


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
    from ...application.ledger import LedgerPreflightIssue, preflight_transaction_catalogue
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
    from ._ledger_payloads import LedgerCheckResult

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
        _emit_envelope(
            ctx,
            command="ledger.check",
            result=LedgerCheckResult.model_validate(payload),
            lines=lines,
        )
        return

    aggregated_issues: list[LedgerPreflightIssue] = []
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
    _emit_envelope(
        ctx,
        command="ledger.check",
        result=LedgerCheckResult.model_validate(payload),
        lines=lines,
    )


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
    from ...application.ledger import preflight_ledger_tax_readiness

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
    from ._ledger_payloads import LedgerPreflightResult

    _emit_envelope(
        ctx,
        command="ledger.preflight",
        result=LedgerPreflightResult.model_validate(payload),
        lines=lines,
    )


@app.command("history", help=tr("cli.ledger.history.help"))
def ledger_history(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.history.id_help")),
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
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{transaction_repository.bucket_id}",
        f"{tr('cli.ledger.labels.id')}\t{resolved_id}",
        f"{tr('cli.ledger.labels.event_count')}\t{len(matches)}",
    ]
    lines.extend(f"{event.occurred_at.isoformat()}\t{event.event_type.value}\t{event.event_id}" for event in matches)
    from ._ledger_payloads import LedgerHistoryResult

    _emit_envelope(
        ctx,
        command="ledger.history",
        result=LedgerHistoryResult.model_validate(
            {
                "bucket_id": transaction_repository.bucket_id,
                "transaction_id": resolved_id,
                "event_count": len(matches),
                "events": [event.model_dump(mode="json") for event in matches],
            }
        ),
        lines=lines,
    )


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
    period: str | None = typer.Option(
        None,
        "--period",
        help=tr(
            "cli.ledger.export.period_help",
            default="Restrict the export to one filing period (e.g. 2025Q1, 2025).",
        ),
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
            period=_canonical_period(period) if period else None,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger export",
        ),
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerExportPayload

    _emit_envelope(
        ctx,
        command="ledger.export",
        result=LedgerExportPayload.from_result(result, output_path=str(output)),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.export_id')}\t{result.export_id}",
            f"{tr('cli.ledger.labels.rows')}\t{result.row_count}",
            f"{tr('cli.ledger.labels.sha256')}\t{result.sha256}",
            f"{tr('cli.ledger.labels.output')}\t{output}",
        ],
    )


@app.command("list", help=tr("cli.ledger.list.help"))
def ledger_list(
    ctx: typer.Context,
    filters: list[str] = typer.Option([], "--filter", help=tr("cli.ledger.list.filter_help")),
    limit: int | None = typer.Option(None, "--limit", min=1, help=tr("cli.ledger.list.limit_help")),
    offset: int = typer.Option(0, "--offset", min=0, help=tr("cli.ledger.list.offset_help")),
    group: str | None = typer.Option(None, "--group", help=tr("cli.ledger.list.group_filter_help")),
    by_group: bool = typer.Option(False, "--by-group", help=tr("cli.ledger.list.by_group_help")),
) -> None:
    """List bucket-scoped ledger transactions through the backend read service.

    ``--filter KEY=VALUE`` narrows the listing using the same typed
    :class:`LedgerReviewFilterSpec` that ``ledger review`` uses, so the two
    surfaces share one closed-key catalogue: ``period`` (``YYYY-Qn`` / ``YYYYQn``
    / ``YYYY-MM`` / bare ``YYYY`` for a whole year), ``status`` (pending /
    reviewed / skipped), ``classification`` (business / personal / mixed / ...),
    ``issue`` (gap / duplicate / ...), ``import``, ``direction`` (ingreso /
    gasto), and ``text`` free-text. Filters apply before paging and grouping, so
    an operator can scope a large ledger to one period/year/class instead of
    dumping every row and grepping. Filtering by organisational group label is the
    separate ``--group`` option, not a ``--filter`` key.

    ``--limit`` / ``--offset`` page the (filtered) result. The page is clipped
    honestly: when more rows exist beyond the window a truncation footer states
    the full total, so a large ledger is never silently capped. ``--group``
    filters to one organisational :attr:`group_label`; ``--by-group`` sections the
    listing under a header per label so thousands of rows stay legible.
    """
    # S09 doc-note: `ledger list` is a read-only query; ValidationError cannot
    # originate here from operator input. Stored-data drift (a persisted record
    # that no longer deserialises) surfaces as a CliStoredDataValidationBoundaryError
    # raised by _state() / _tx_repo() — handled by S05, not this verb.
    state = _state()
    transaction_repository = _tx_repo(state)
    try:
        spec = parse_ledger_list_filter_spec(filters)
    except FilterParseError as exc:
        raise _bad(tr("cli.ledger.errors.filter_parse_error", reason=exc.reason, token=exc.safe_token)) from exc
    projection = project_ledger_list(
        transaction_repository=transaction_repository,
        spec=spec,
        group=group,
        by_group=by_group,
        limit=limit,
        offset=offset,
    )
    from ._ledger_payloads import LedgerListResult

    _emit_envelope(
        ctx,
        command="ledger.list",
        result=LedgerListResult.model_validate(
            {
                "bucket_id": projection.bucket_id,
                "rows": projection.rows,
                "total": projection.total,
                "shown": projection.shown,
                "offset": projection.offset,
                "limit": projection.limit,
                "truncated": projection.truncated,
            }
        ),
        lines=projection.lines,
    )


@app.command("view", help=tr("cli.ledger.view.help"))
def ledger_view(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.view.transaction_id_help")),
) -> None:
    """Read one bucket-scoped ledger transaction through the backend read service."""
    # S10 doc-note: `ledger view` is a read-only query; ValidationError cannot
    # originate here from operator input. Stored-data drift surfaces via S05
    # (CliStoredDataValidationBoundaryError at _state() / _tx_repo()), not here.
    transaction_repository = _tx_repo(_state())
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = get_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
    )
    result_payload = ledger_transaction_result_payload(result)
    transaction_payload = result_payload.transaction
    review_status = ledger_transaction_review_status(result.transaction)

    # `ledger view` is the operator's confirmation that the data they
    # entered was stored. Rendering only id/date/amount/description left
    # the IVA triple, counterparty, classification, category and notes
    # invisible - the operator could not verify those fields persisted.
    # Every stored field is now shown; `-` marks a field left unset.
    def _field(value: object) -> str:
        return "-" if value is None or value == "" else str(value)

    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.ref.transaction_id}",
        f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
        f"{tr('cli.ledger.labels.value_date', default='Value date')}\t{_field(transaction_payload.value_date)}",
        f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
        f"{tr('cli.ledger.labels.currency', default='Currency')}\t{_field(transaction_payload.currency)}",
        f"{tr('cli.ledger.labels.direction', default='Direction')}\t{_field(transaction_payload.direction)}",
        f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
        f"{tr('cli.ledger.labels.counterparty', default='Counterparty')}\t{_field(transaction_payload.counterparty)}",
        f"{tr('cli.ledger.labels.business_classification', default='Classification')}"
        f"\t{_field(transaction_payload.business_classification)}",
        f"{tr('cli.ledger.labels.business_pct', default='Business %')}\t{_field(transaction_payload.business_pct)}",
        f"{tr('cli.ledger.labels.category_id', default='Category')}\t{_field(transaction_payload.category_id)}",
        f"{tr('cli.ledger.labels.taxable_base', default='Taxable base')}\t{_field(transaction_payload.taxable_base)}",
        f"{tr('cli.ledger.labels.iva_rate', default='IVA rate')}\t{_field(transaction_payload.iva_rate)}",
        f"{tr('cli.ledger.labels.iva_amount', default='IVA amount')}\t{_field(transaction_payload.iva_amount)}",
        f"{tr('cli.ledger.labels.irpf_category', default='IRPF category')}"
        f"\t{_field(transaction_payload.irpf_category)}",
        f"{tr('cli.ledger.labels.notes', default='Notes')}\t{_field(transaction_payload.notes)}",
        f"{tr('cli.ledger.labels.lifecycle_state')}\t{_field(transaction_payload.lifecycle_state)}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    from ._ledger_payloads import LedgerViewResult

    _emit_envelope(
        ctx,
        command="ledger.view",
        result=LedgerViewResult.model_validate(result_payload.model_dump(mode="json")),
        lines=lines,
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
    transactions = transaction_repository.load()
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
        f"income_total\t{report.income_total}",
        f"expense_total\t{report.expense_total}",
        f"net_total\t{report.net_total}",
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
        from ...application.ledger import preflight_ledger_tax_readiness

        preflight = preflight_ledger_tax_readiness(
            bucket_id=transaction_repository.bucket_id,
            period=report.period,
            transaction_repository=transaction_repository,
        )
        for issue in preflight.issues:
            transaction = transactions.get(issue.transaction_id)
            if transaction is None:
                continue
            lines.append(
                _ledger_status_readiness_issue_line(transaction, reason=issue.reason.value, detail=issue.detail)
            )
    # Advisory: surface any finalized modelo revision whose backing ledger
    # snapshot has drifted from the live ledger (modelo-filing-ledger-snapshot
    # ADR). Appended as free-form lines; the structured envelope is unchanged.
    from ...application.aggregation import stale_filed_revisions
    from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
    from ...domain.modelos._repository import WorkUnitCatalogueRepository

    revisions = CalculationRevisionCatalogueRepository().load().revisions
    work_units = WorkUnitCatalogueRepository().load()
    for revision, verdict in stale_filed_revisions(revisions=revisions, catalogue=transactions):
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != transaction_repository.bucket_id:
            continue
        lines.append(
            "\t".join(
                (
                    "ledger_filing_stale",
                    f"modelo={work_unit.modelo}",
                    f"year={work_unit.filing_year}",
                    f"period={work_unit.period}",
                    f"revision={revision.calculation_revision_id}",
                    f"changed={len(verdict.changed)}",
                    f"removed={len(verdict.removed)}",
                )
            )
        )

    from ._ledger_payloads import LedgerStatusResult

    _emit_envelope(
        ctx,
        command="ledger.status",
        result=LedgerStatusResult.model_validate(report.model_dump(mode="json")),
        lines=lines,
    )


def _ledger_status_readiness_issue_line(transaction: Transaction, *, reason: str, detail: str) -> str:
    def _value(value: object) -> str:
        return "-" if value is None or value == "" else str(value)

    return "\t".join(
        (
            "readiness_issue",
            transaction.transaction_id,
            f"classification={transaction.business_classification.value}",
            f"category_id={_value(transaction.category_id)}",
            f"taxable_base={_value(transaction.taxable_base)}",
            f"iva_rate={_value(transaction.iva_rate)}",
            f"iva_amount={_value(transaction.iva_amount)}",
            f"reason={reason}",
            f"detail={detail}",
        )
    )


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
    from ._ledger_payloads import LedgerTrackResult

    _emit_envelope(
        ctx,
        command="ledger.track",
        result=LedgerTrackResult.model_validate(
            {
                "bucket_id": result.ref.bucket_id,
                "transaction": ledger_transaction_payload(result.transaction).model_dump(mode="json"),
                "tracking": ledger_transaction_tracking_payload(result.transaction).model_dump(mode="json"),
            }
        ),
        lines=_ledger_track_lines(result.ref.transaction_id, result.transaction),
    )


def _ledger_track_lines(transaction_id: str, transaction: Transaction) -> list[str]:
    """Track lines, naming the import-batch provenance for imported rows.

    Imported transactions carry no ``created_event_id`` (set only by
    ``ledger add``); rather than render a bare ``-``, surface the import
    provenance the row already carries (provider, source file, ingest time,
    fingerprint) so an asesor can defend a row's origin from ``track`` alone.
    """
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{transaction_id}",
        f"{tr('cli.ledger.labels.lifecycle_state')}\t{transaction.lifecycle_state.value}",
        f"{tr('cli.ledger.labels.created_event_id')}\t{transaction.created_event_id or '-'}",
    ]
    if transaction.created_event_id is None:
        provenance = transaction.raw.provenance
        lines.append(f"import_provider\t{provenance.provider_name}")
        lines.append(f"import_source\t{provenance.source_path.name}")
        lines.append(f"import_ingested_at\t{provenance.ingested_at.isoformat()}")
        lines.append(f"import_fingerprint\t{transaction.import_fingerprint or '-'}")
    return lines


def _ledger_review_filter_spec(filters: list[str]) -> LedgerReviewFilterSpec:
    try:
        return LedgerReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(tr("cli.ledger.errors.filter_parse_error", reason=exc.reason, token=exc.safe_token)) from exc


def _ledger_review_query(
    transaction_repository: _TransactionRepo,
    *,
    spec: LedgerReviewFilterSpec,
    record_id: str | None,
) -> LedgerReviewQuery:
    resolved_record_id = _resolve_id(transaction_repository, record_id) if record_id is not None else None
    return LedgerReviewQuery(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_record_id,
        period=_canonical_period(spec.period) if spec.period else None,
        status=spec.status.value if spec.status is not None else None,
        issue=spec.issue.value if spec.issue is not None else None,
        import_id=spec.import_id,
        classification=spec.classification.value if spec.classification is not None else None,
        text=spec.text,
        direction=spec.direction.value if spec.direction is not None else None,
    )


def _ledger_review_empty_payload(result: LedgerReviewQueryResult) -> dict[str, object]:
    return {"rows": [], "filters": list(result.filters)}


def _ledger_review_detail_payload(row: LedgerReviewRow, *, verbose: bool) -> dict[str, object]:
    return {
        "id": row.id,
        "date": row.date,
        "amount": row.amount,
        "description": row.description,
        "review_status": row.status,
        "transaction": row.transaction.model_dump(mode="json") if row.transaction is not None else None,
        "verbose": verbose,
    }


def _ledger_review_detail_lines(row: LedgerReviewRow) -> list[str]:
    return [
        f"{tr('cli.ledger.labels.id')}\t{row.id}",
        f"{tr('cli.ledger.labels.date')}\t{row.date}",
        f"{tr('cli.ledger.labels.amount')}\t{row.amount}",
        f"{tr('cli.ledger.labels.description')}\t{row.description}",
    ]


def _ledger_review_list_payload(result: LedgerReviewQueryResult) -> dict[str, object]:
    return {
        "rows": [row.model_dump(mode="json", exclude_none=True) for row in result.rows],
        "filters": list(result.filters),
    }


def _ledger_review_list_lines(result: LedgerReviewQueryResult) -> list[str]:
    lines: list[str] = [tr("cli.ledger.review.header")]
    review_ids = tuple(row.id for row in result.rows)
    review_width = compute_display_id_width(review_ids)
    lines.extend(
        f"{row.id[:review_width]}\t{row.id}\t{row.date}\t{row.amount}\t{row.description}\t{row.status}"
        for row in result.rows
    )
    if not result.rows:
        lines.append(tr("cli.ledger.review.no_rows"))
    return lines


def _emit_ledger_review_result(
    ctx: typer.Context,
    *,
    record_id: str | None,
    verbose: bool,
    result: LedgerReviewQueryResult,
) -> None:
    from ._ledger_payloads import LedgerReviewResult

    if record_id is not None:
        if not result.rows:
            _emit_envelope(
                ctx,
                command="ledger.review",
                result=LedgerReviewResult.model_validate(_ledger_review_empty_payload(result)),
                lines=[tr("cli.ledger.review.header"), tr("cli.ledger.review.no_rows")],
            )
            return
        row = result.rows[0]
        _emit_envelope(
            ctx,
            command="ledger.review",
            result=LedgerReviewResult.model_validate(_ledger_review_detail_payload(row, verbose=verbose)),
            lines=_ledger_review_detail_lines(row),
        )
        return
    _emit_envelope(
        ctx,
        command="ledger.review",
        result=LedgerReviewResult.model_validate(_ledger_review_list_payload(result)),
        lines=_ledger_review_list_lines(result),
    )


@app.command("review", help=tr("cli.ledger.review.help"))
def ledger_review(
    ctx: typer.Context,
    filters: list[str] = typer.Option([], "--filter", help=tr("cli.ledger.review.filter_help")),
    record_id: str | None = typer.Option(None, "--id", help=tr("cli.ledger.review.id_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.ledger.review.verbose_help")),
) -> None:
    """Render rows or a single row using the typed filter spec."""
    spec = _ledger_review_filter_spec(filters)
    transaction_repository = _tx_repo(_state())
    # `LedgerReviewQuery.transaction_id` requires the full 64-char
    # SHA-256 id. An operator naturally passes the short display id
    # surfaced by `ledger list` / `ledger review`, so the raw `--id`
    # value must be resolved through the same prefix-resolution path
    # every other ledger `--id` verb uses; otherwise the query model
    # rejects the short prefix and the generic boundary masks it as
    # "command input failed validation. Run aeat config repair".
    result = query_ledger_review_rows(
        _ledger_review_query(transaction_repository, spec=spec, record_id=record_id),
        transaction_repository=transaction_repository,
    )
    _emit_ledger_review_result(ctx, record_id=record_id, verbose=verbose, result=result)


def _resolve_source_jurisdiction(
    operator_value: str | None,
    *,
    fiscal_residency: FiscalResidency | None,
    irpf_special_regime: IrpfSpecialRegime | None,
) -> str | None:
    """Stamp the profile-conditional default for ``--source-jurisdiction``.

    Future entrypoints (importer, bulk classify, etc.) must pre-validate
    profile-conditional defaults via this helper. Resolution rules track
    the regulatory branching anchored in LIRPF Art. 8 (universal-base
    presumption for Spanish residents), TRLIRNR Art. 2 / Art. 10
    (non-residents must declare jurisdiction explicitly), and Art. 93
    LIRPF (impatriados must declare; the Beckham regime treats Spanish-
    and foreign-source income distinctly so a silent ES default would
    quietly include foreign-source amounts in the IRPF base).

    Args:
        operator_value: Operator-supplied jurisdiction string, or ``None``
            when the flag was omitted.
        fiscal_residency: Resolved fiscal-residency classification from
            the active profile, or ``None`` when unavailable.
        irpf_special_regime: Resolved IRPF special-regime classification
            from the active profile, or ``None`` when unavailable.

    Returns:
        The operator-supplied value when present, or ``"ES"`` when the
        profile is RESIDENT_IRPF / GENERAL and no operator value was given.

    Raises:
        _bad: When the profile is NON_RESIDENT_IRNR or RESIDENT_IRPF /
            IMPATRIADO and no operator value was given.
    """
    if operator_value is not None:
        return operator_value
    if fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR:
        raise _bad(tr("cli.ledger.add.source_jurisdiction_required_irnr"))
    if irpf_special_regime is IrpfSpecialRegime.IMPATRIADO:
        raise _bad(tr("cli.ledger.add.source_jurisdiction_required_beckham"))
    return "ES"


def _resolve_business_pct_with_censo(
    *,
    bucket_id: str,
    active_profile: str | None,
    category_id: str | None,
    operator_supplied,
):
    """Stamp the censo-derived business_pct when the operator omits one.

    Operator-supplied values always win — the helper only fills the
    gap when ``business_pct`` is not given AND the transaction targets
    a HOME_OFFICE category that the censo actually governs. Returns
    the operator-supplied value unchanged on every other path, so non-
    HOME_OFFICE transactions and explicit-override flows are not
    perturbed.
    """
    from ...application.ledger import censo_business_pct_for
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
    return censo_business_pct_for(category_enum, raw_afectacion)


register_ratios_commands(app)


register_business_invoice_commands(app)


register_inventory_commands(app)


register_evidence_commands(app)


register_rule_commands(app)


register_import_commands(app)

