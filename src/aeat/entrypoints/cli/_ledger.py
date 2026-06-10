"""User-facing ledger and transaction management CLI commands.

Provides the ``aeat ledger`` command group for importing, reviewing, and
exporting financial transaction data. Transaction records are accessed
through :class:`TransactionCatalogueRepository` and invoice records through
:class:`InvoiceCatalogueRepository`. Lifecycle events are appended to the
profile audit trail via :class:`BucketEventHistoryRepository`.

Use of :class:`OutputSchema` for compliance.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Protocol

import typer
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from ...application.ledger import (
    LedgerTransactionResultPayload,
    LLMProvider,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    apply_llm_classification,
    apply_saturated_llm_classification,
    create_manual_transaction,
    is_llm_provider_available,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_review_status,
    list_manual_transactions,
    resolve_lineage_transaction_id,
    resolve_transaction_id,
    saturate_llm_classification,
    suggest_llm_classification,
    update_manual_transaction_fields,
)
from ...core import resolve_active_bucket_id
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.categories import (
    SpendingCategory,
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
    TransactionValidationError,
)
from ._common import (
    _bad,
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
from ._ledger_classify_cli import ledger_classify_bulk_csv
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
from ._ledger_ratios_cli import ratios_app, register_ratios_commands
from ._ledger_read_cli import register_read_commands
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


def _format_percent(value: Decimal) -> str:
    """Render a 0..1 proportion as its percentage for operator context."""
    # ``format(..., "f")`` avoids scientific notation (e.g. ``5E+3``);
    # trim trailing zeros only when a fractional part is present.
    text = format(value * Decimal(100), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}%"


def _validate_business_pct_range(value: Decimal | None) -> Decimal | None:
    """Refuse a business proportion outside the inclusive 0..1 range.

    The domain validator rejects an out-of-range proportion but its
    message ("business_pct must be within 0..1") names neither the
    offending value nor its percentage. An operator who types ``50``
    (meaning 50 %) or ``1.5`` then sees a bare invalid. Surface the
    value with its percent context here at the CLI boundary — the
    operator's first instructive surface — so the share is
    self-explanatory and the 0.5-for-50 % convention is shown.
    """
    if value is None:
        return None
    if not Decimal("0") <= value <= Decimal("1"):
        raise _bad(
            tr(
                "cli.ledger.errors.business_pct_out_of_range",
                value=format(value.normalize(), "f"),
                percent=_format_percent(value),
            )
        )
    return value


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


def _prefix_error_bad(exc: TransactionIdPrefixError, prefix: str) -> typer.BadParameter:
    """Translate a :exc:`TransactionIdPrefixError` into a localized ``_bad``.

    Wraps the domain-layer exception into ``tr()``-rendered messages so the
    operator sees a locale-translated explanation rather than a raw Python
    exception string. Five distinct refusal keys are emitted depending on
    which invariant was violated.
    """
    raw_message = str(exc)
    if "is empty" in raw_message:
        return _bad(tr("cli.ledger.errors.id_prefix_empty"))
    if "non-hex" in raw_message:
        return _bad(tr("cli.ledger.errors.id_prefix_not_hex", prefix=prefix))
    if "longer than" in raw_message:
        return _bad(tr("cli.ledger.errors.id_prefix_too_long", prefix=prefix))
    if "no transaction" in raw_message:
        return _bad(tr("cli.ledger.errors.id_prefix_not_found", prefix=prefix))
    if "matches" in raw_message:
        # collision — surface the candidate ids inline so the
        # operator can lengthen the prefix.
        _, _, candidates = raw_message.partition(":")
        return _bad(
            tr(
                "cli.ledger.errors.id_prefix_collision",
                prefix=prefix,
                candidates=candidates.strip() or "?",
            )
        )
    return _bad(tr("cli.ledger.errors.id_prefix_unknown", message=raw_message))


def _resolve_id(transaction_repository: _TransactionRepo, prefix: str) -> str:
    """Resolve a CLI-supplied id or unambiguous prefix to a live transaction id.

    Used by the *mutation* verbs (update, classify, allocate, link,
    archive, stash, restore, ...). It matches only ids of rows still in the
    catalogue, because a mutation always targets a live row; an ``update``
    additionally requires the target to be ACTIVE. Read verbs use
    :func:`_resolve_read_id` instead, which also follows edit lineage.
    """
    try:
        return resolve_transaction_id(prefix, _bucket_transaction_ids(transaction_repository))
    except TransactionIdPrefixError as exc:
        raise _prefix_error_bad(exc, prefix) from exc


def _resolve_read_id(transaction_repository: _TransactionRepo, prefix: str) -> str:
    """Resolve a CLI-supplied id for the *read* verbs, following edit lineage.

    This is the D3 stable-lineage-handle resolution path for
    ``ledger history`` / ``view`` / ``track``. It first resolves ``prefix``
    against live catalogue ids exactly as :func:`_resolve_id` does; when no
    live row matches, it walks the edit-lineage chain so a superseded
    (pre-``update``) id written down by the operator still resolves to the
    current row — see
    :func:`aeat.application.ledger.resolve_lineage_transaction_id`. The
    content-addressed id stays authoritative; this is a read-side lookup
    convenience, never a change to how ids are minted.
    """
    if not isinstance(transaction_repository, TransactionCatalogueRepository):
        # Read verbs always receive a real catalogue repository through
        # _tx_repo; the structural Protocol is only used by mutation
        # helpers. Fall back to the live-id resolver if a non-catalogue
        # repository is ever supplied so the read path never crashes.
        return _resolve_id(transaction_repository, prefix)
    catalogue = transaction_repository.load()
    try:
        return resolve_lineage_transaction_id(prefix, catalogue)
    except TransactionIdPrefixError as exc:
        raise _prefix_error_bad(exc, prefix) from exc


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
        operator_supplied=_validate_business_pct_range(_parse_decimal(business_pct, label="business-pct")),
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
            default=(
                "Path to a CSV file with columns transaction_id, classification"
                "[, category_id, business_pct, taxable_base, iva_rate, iva_amount]."
            ),
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
    saturate: bool = typer.Option(False, "--saturate", help=tr("cli.ledger.classify.saturate_help")),
) -> None:
    """Classify one ledger transaction (--id), via LLM (--llm), or in bulk (--from-csv)."""
    if llm is not None:
        if saturate:
            _ledger_saturate_llm(
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
    if saturate:
        raise _bad(
            tr(
                "cli.ledger.classify.saturate_requires_llm",
                default="--saturate only applies to the --llm path; supply --llm <provider>.",
            )
        )
    state = _state()
    transaction_repository = _tx_repo(state)

    if from_csv is not None:
        ledger_classify_bulk_csv(
            ctx,
            transaction_repository=transaction_repository,
            transaction_id=transaction_id,
            classification=classification,
            from_csv=from_csv,
            actor=actor,
        )
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
            business_pct=_validate_business_pct_range(_parse_decimal(business_pct, label="business-pct")),
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


def _ledger_saturate_llm(
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
    """Run the saturating LLM suggest / apply loop for ``classify --llm --saturate``.

    Extends the stage-1 loop to the rich tax substrate: the model selects an
    :class:`aeat.domain.iva.IvaCategory` and the system DERIVES the rate, base,
    and amount from the registry — never the model. Without ``--apply`` the full
    saturated suggestion is previewed and nothing is persisted; with ``--apply``
    it is written through the manual-command write with ``llm:<model>``
    provenance. Manual ``classify`` flags remain the explicit per-field
    override; rejecting is simply not applying.
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
        suggestion = saturate_llm_classification(
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

    iva_category_value = suggestion.iva_category.value if suggestion.iva_category is not None else None
    iva_rate_value = format(suggestion.iva_rate, "f") if suggestion.iva_rate is not None else None
    taxable_base_value = format(suggestion.taxable_base, "f") if suggestion.taxable_base is not None else None
    iva_amount_value = format(suggestion.iva_amount, "f") if suggestion.iva_amount is not None else None
    derived_fields = {
        "iva_category": iva_category_value,
        "iva_rate": iva_rate_value,
        "taxable_base": taxable_base_value,
        "iva_amount": iva_amount_value,
        "rate_derivable": suggestion.rate_derivable,
        "derivation_note": suggestion.derivation_note or None,
    }

    if not apply:
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
                **derived_fields,
            }
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{suggestion.classification.value}",
            f"{tr('cli.ledger.labels.category_id')}\t{suggestion.category.value if suggestion.category else ''}",
            f"{tr('cli.ledger.labels.iva_category')}\t{iva_category_value or ''}",
        ]
        if suggestion.rate_derivable:
            lines.extend(
                [
                    f"{tr('cli.ledger.labels.taxable_base')}\t{taxable_base_value}",
                    f"{tr('cli.ledger.labels.iva_rate')}\t{iva_rate_value}",
                    f"{tr('cli.ledger.labels.iva_amount')}\t{iva_amount_value}",
                ]
            )
        elif suggestion.iva_category is not None:
            lines.append(f"{tr('cli.ledger.classify.saturate_non_derivable')}\t{suggestion.derivation_note}")
        lines.append(f"{tr('cli.ledger.classify.llm_confidence_label')}\t{format(suggestion.confidence, 'f')}")
        lines.append(tr("cli.ledger.classify.llm_review_hint"))
        _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)
        return

    try:
        result = apply_saturated_llm_classification(
            suggestion,
            bucket_id=transaction_repository.bucket_id,
            business_pct=_parse_decimal(business_pct, label="business-pct"),
            actor=actor or resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    except TransactionValidationError as exc:
        raise _bad(str(exc)) from exc
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
            **derived_fields,
        }
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.iva_category')}\t{iva_category_value or ''}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


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
    parsed_business_pct = _validate_business_pct_range(_parse_required_decimal(business_pct, label="business-pct"))
    assert parsed_business_pct is not None
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


register_read_commands(app, resolve_transaction_id=_resolve_read_id)


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
