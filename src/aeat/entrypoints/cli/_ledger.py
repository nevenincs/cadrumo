"""User-facing ledger and transaction management CLI commands.

Provides the ``aeat ledger`` command group for importing, reviewing, and
exporting financial transaction data. Transaction records are accessed
through :class:`TransactionCatalogueRepository` and invoice records through
:class:`InvoiceCatalogueRepository`. Lifecycle events are appended to the
profile audit trail via :class:`BucketEventHistoryRepository`.

Use of :class:`OutputSchema` for compliance.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

import typer
from pydantic import BaseModel, ValidationError

from ...application.ledger import (
    LedgerTransactionResultPayload,
    LLMProvider,
    LLMSplitSuggestion,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    apply_evidence_classification,
    apply_evidence_split,
    apply_llm_classification,
    apply_saturated_llm_classification,
    create_manual_transaction,
    derive_operator_iva_substrate,
    is_llm_provider_available,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_review_status,
    resolve_lineage_transaction_id,
    saturate_llm_classification,
    suggest_evidence_split,
    suggest_llm_classification,
    update_manual_transaction_fields,
)
from ...core import resolve_active_bucket_id
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.logging import get_logger
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
    invoice_app,
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
from ._ledger_support import (
    _invoice_link_error_bad_parameter,
    _ledger_validation_bad,
    _parse_amount_magnitude,
    _parse_decimal,
    _parse_required_decimal,
    _prefix_error_bad,
    _resolve_business_pct_with_censo,
    _resolve_id,
    _resolve_source_jurisdiction,
    _TransactionRepo,
    _validate_business_pct_range,
    _validate_category_id,
)
from ._schemas import OutputSchema

_log = get_logger(__name__)

__all__ = [
    "app",
    "inventory_app",
    "invoice_app",
    "ledger_archive",
    "ledger_attach",
    "ledger_doclink",
    "ledger_merge",
    "ledger_remove",
    "ledger_reset",
    "ledger_split",
    "ledger_stash",
    "ratios_app",
    "rule_app",
]

app = typer.Typer(
    name="ledger",
    help=tr("cli.ledger.app_help"),
    no_args_is_help=True,
)


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
        {key: value for key, value in values.items() if value is not None},
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
        },
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
            amount=_parse_amount_magnitude(amount),
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
    review_status = ledger_transaction_review_status(result.transaction)
    add_result = LedgerAddResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.ref.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
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
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ],
    )


@app.command("update", help=tr("cli.ledger.update.help"))
def ledger_update(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.update.id_help")),
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
                amount=_parse_amount_magnitude(amount) if amount is not None else None,
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


_FromCsvOpt = Annotated[
    str | None,
    typer.Option(
        "--from-csv",
        help=tr(
            "cli.ledger.classify.from_csv_help",
            default=(
                "Path to a CSV file with columns transaction_id, classification"
                "[, category_id, business_pct, taxable_base, iva_rate, iva_amount]."
            ),
        ),
    ),
]


@app.command("classify", help=tr("cli.ledger.classify.help"))
def ledger_classify(
    ctx: typer.Context,
    transaction_id: str | None = typer.Argument(None, help=tr("cli.ledger.classify.id_help")),
    classification: BusinessClassification | None = typer.Option(
        None,
        "--classification",
        help=tr("cli.ledger.classify.classification_help"),
    ),
    from_csv: _FromCsvOpt = None,
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
    read_evidence: bool = typer.Option(False, "--read-evidence", help=tr("cli.ledger.classify.read_evidence_help")),
    evidence_acknowledged: bool = typer.Option(
        False,
        "--evidence-acknowledged",
        help=tr("cli.ledger.classify.evidence_acknowledged_help"),
    ),
    vision_model: str | None = typer.Option(
        None,
        "--vision-model",
        help=tr("cli.ledger.classify.vision_model_help"),
    ),
    auto_split: bool = typer.Option(
        False,
        "--auto-split",
        help=tr("cli.ledger.classify.auto_split_help"),
    ),
) -> None:
    """Classify one ledger transaction (positional id), via LLM (--llm), or in bulk (--from-csv)."""
    if auto_split:
        if not read_evidence:
            raise _bad(
                tr(
                    "cli.ledger.classify.auto_split_needs_evidence",
                    default="--auto-split requires --read-evidence: the split decision is read from the invoice.",
                ),
            )
        if classification is not None or from_csv is not None:
            raise _bad(
                tr(
                    "cli.ledger.classify.llm_exclusive",
                    default="--llm cannot be combined with --classification or --from-csv; "
                    "the manual path is the explicit operator override.",
                ),
            )
        _ledger_autosplit_llm(
            ctx,
            transaction_id=transaction_id,
            provider=llm,
            apply=apply,
            actor=actor,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
        )
        return
    if llm is not None or read_evidence:
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
                read_evidence=read_evidence,
                evidence_acknowledged=evidence_acknowledged,
                vision_model=vision_model,
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
            read_evidence=read_evidence,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
        )
        return
    if saturate:
        _ledger_operator_iva_derive(
            ctx,
            transaction_id=transaction_id,
            classification=classification,
            from_csv=from_csv,
            iva_category=iva_category,
            actor=actor,
        )
        return
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

    # Single-transaction mode: the positional id and --classification are required
    if transaction_id is None:
        raise _bad(
            tr(
                "cli.ledger.classify.id_required",
                default="A transaction id is required when --from-csv is not provided.",
            ),
        )
    if classification is None:
        raise _bad(
            tr(
                "cli.ledger.classify.classification_required",
                default="--classification is required when --from-csv is not provided.",
            ),
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
    # cause, matching the `ledger add` / `ledger review` treatment.
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
    from ._ledger_payloads import LedgerClassifySingleResult

    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
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


def _split_recommendation_notice(transaction_id: str, *, provider: LLMProvider | None) -> Notice:
    """Build the typed ``info`` notice recommending an evidence-driven split.

    Fired when the evidence read judged the invoice multi-component. The
    ``suggestion`` is the exact runnable command that actions the split, preserving
    the provider the operator used (``cli-notices-are-the-only-diagnostic-channel``;
    the recommendation rides the Notice channel, never a bespoke result field).
    """
    provider_flag = f" --llm {provider.value}" if provider is not None else ""
    command = (
        f"aeat app ledger classify {transaction_id} "
        f"--read-evidence --saturate --auto-split --apply{provider_flag}"
    )
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.classify.split_recommended",
        message=tr(
            "cli.ledger.classify.split_recommended_message",
            default=(
                "The attached invoice appears to carry multiple rate or category lines. "
                "Re-run with --auto-split to separate them into independently-filable "
                "base and IVA children."
            ),
        ),
        suggestion=command,
        context={"transaction_id": transaction_id, "source": "evidence_read"},
    )


def _ledger_classify_llm(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    from_csv: str | None,
    business_pct: str | None,
    provider: LLMProvider | None,
    apply: bool,
    actor: str | None,
    read_evidence: bool = False,
    evidence_acknowledged: bool = False,
    vision_model: str | None = None,
) -> None:
    """Run the LLM suggest / apply loop for ``aeat app ledger classify --llm``.

    Without ``--apply`` the model's suggestion is printed for review and
    nothing is persisted (the suggest step; rejecting is simply not applying).
    With ``--apply`` the decision is written via
    :func:`apply_llm_classification` with ``llm:<model>`` provenance. ``--llm``
    is mutually exclusive with the manual ``--classification`` / ``--from-csv``
    paths (manual classification is always the explicit override).
    """
    from ._ledger_payloads import LedgerClassifyLlmSuggestResult, LedgerClassifySingleResult

    if classification is not None or from_csv is not None:
        raise _bad(
            tr(
                "cli.ledger.classify.llm_exclusive",
                default="--llm cannot be combined with --classification or --from-csv; "
                "the manual path is the explicit operator override.",
            ),
        )
    if transaction_id is None:
        raise _bad(
            tr(
                "cli.ledger.classify.id_required",
                default="A transaction id is required when --from-csv is not provided.",
            ),
        )
    # A provider is checked for PATH availability only when one is named. With
    # --read-evidence and no --llm, a scanned/image invoice is read on-host by the
    # local vision model, which needs no subprocess provider; a text-layer read with
    # no provider is refused instructively downstream by the application.
    if provider is not None and not is_llm_provider_available(provider):
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
            ),
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
            read_evidence=read_evidence,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
        )
    except LLMClassifierError as exc:
        raise _bad(
            tr(
                "cli.ledger.classify.llm_failed",
                reason=str(exc),
                default=f"LLM classification failed: {exc}",
            ),
        ) from exc

    if not apply:
        # Suggest (preview) — persist nothing. Rejecting = not applying.
        suggest_result = LedgerClassifyLlmSuggestResult.model_validate(
            {
                "llm": True,
                "persisted": False,
                "transaction_id": suggestion.transaction_id,
                "provider": suggestion.provider.value if suggestion.provider is not None else "local-vision",
                "classification": suggestion.classification.value,
                "category": suggestion.category.value if suggestion.category is not None else None,
                "confidence": format(suggestion.confidence, "f"),
                "reason": suggestion.reason,
                "provenance": suggestion.provenance,
            },
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{suggestion.classification.value}",
            f"{tr('cli.ledger.labels.category_id')}\t{suggestion.category.value if suggestion.category else ''}",
            f"{tr('cli.ledger.classify.llm_confidence_label')}\t{format(suggestion.confidence, 'f')}",
            f"{tr('cli.ledger.classify.llm_reason_label')}\t{suggestion.reason}",
            tr("cli.ledger.classify.llm_review_hint"),
        ]
        notices: list[Notice] = []
        if suggestion.recommends_split:
            notice = _split_recommendation_notice(suggestion.transaction_id, provider=provider)
            notices.append(notice)
            lines.append(f"{tr('cli.ledger.classify.split_recommended_label')}\t{notice.suggestion}")
        _emit_envelope(ctx, command="ledger.classify", result=suggest_result, lines=lines, notices=notices)
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
    # D1: the --llm --apply path is a single-transaction mutation, so it emits the
    # canonical mutation quintet (LedgerClassifySingleResult); the llm provenance
    # is surfaced in the operator-facing text lines below.
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


def _autosplit_child_payloads(suggestion: LLMSplitSuggestion) -> list[object]:
    """Project a split suggestion's children to the shared proposal payload."""
    from ._ledger_payloads import LedgerSplitChildProposalPayload

    return [
        LedgerSplitChildProposalPayload.model_validate(
            {
                "proportion": format(child.proportion, "f"),
                "amount": format(child.amount, "f"),
                "description": child.description,
                "category": child.category.value if child.category is not None else None,
                "iva_category": child.iva_category.value if child.iva_category is not None else None,
                "iva_rate": format(child.iva_rate, "f") if child.iva_rate is not None else None,
                "taxable_base": format(child.taxable_base, "f") if child.taxable_base is not None else None,
                "iva_amount": format(child.iva_amount, "f") if child.iva_amount is not None else None,
                "rate_derivable": child.rate_derivable,
            },
        ).model_dump(mode="json")
        for child in suggestion.children
    ]


def _ledger_autosplit_llm(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    provider: LLMProvider | None,
    apply: bool,
    actor: str | None,
    evidence_acknowledged: bool,
    vision_model: str | None,
) -> None:
    """Route ``classify --read-evidence --auto-split`` on the model's split verdict.

    One model call — the split proposer — yields the verdict. A multi-child verdict
    drives the evidence-driven split (preview, or with ``--apply`` the
    base/IVA-separating split); a single-child "no split" verdict classifies the
    transaction in place from that child's selections (preview, or with ``--apply``
    the in-place write). The model emits no euro amount or regulated number; the
    registry derives every child's base and IVA.
    """
    from ._ledger_payloads import LedgerClassifyLlmSuggestResult, LedgerClassifySingleResult

    if transaction_id is None:
        raise _bad(
            tr(
                "cli.ledger.classify.id_required",
                default="A transaction id is required when --from-csv is not provided.",
            ),
        )
    if provider is not None and not is_llm_provider_available(provider):
        raise _bad(
            tr(
                "cli.ledger.classify.llm_provider_unavailable",
                provider=provider.value,
                default=(
                    f"LLM provider {provider.value!r} is unavailable: its CLI is not on PATH. "
                    f"Install the {provider.value!r} CLI and ensure it is on PATH, "
                    "or run 'aeat app ledger providers' to list usable providers."
                ),
            ),
        )

    state = _state()
    transaction_repository = _tx_repo(state)
    bucket_id = transaction_repository.bucket_id
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    try:
        suggestion = suggest_evidence_split(
            bucket_id=bucket_id,
            transaction_id=resolved_id,
            provider=provider,
            transaction_repository=transaction_repository,
            read_evidence=True,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
        )
    except LLMClassifierError as exc:
        raise _bad(
            tr("cli.ledger.classify.llm_failed", reason=str(exc), default=f"LLM split proposal failed: {exc}"),
        ) from exc

    if suggestion.recommends_split:
        _autosplit_emit_split(ctx, suggestion, bucket_id=bucket_id, apply=apply, actor=actor)
        return
    _autosplit_emit_single(
        ctx,
        suggestion,
        bucket_id=bucket_id,
        apply=apply,
        actor=actor,
        result_models=(LedgerClassifyLlmSuggestResult, LedgerClassifySingleResult),
    )


def _autosplit_emit_split(
    ctx: typer.Context,
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    apply: bool,
    actor: str | None,
) -> None:
    """Preview or apply the multi-child evidence-driven split for the auto-split route."""
    from ._ledger_payloads import LedgerSplitResult

    proposed_children = _autosplit_child_payloads(suggestion)
    if not apply:
        result = LedgerSplitResult.model_validate(
            {
                "bucket_id": bucket_id,
                "parent_transaction_id": suggestion.transaction_id,
                "llm": True,
                "persisted": False,
                "provider": suggestion.provider.value if suggestion.provider is not None else None,
                "provenance": suggestion.provenance,
                "reason": suggestion.reason,
                "parent_amount": format(suggestion.parent_amount, "f"),
                "proposed_children": proposed_children,
            },
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(proposed_children)}",
            tr("cli.ledger.classify.llm_review_hint"),
        ]
        _emit_envelope(ctx, command="ledger.split", result=result, lines=lines)
        return
    try:
        applied = apply_evidence_split(
            suggestion,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
        )
    except TransactionValidationError as exc:
        raise _bad(str(exc)) from exc
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    result = LedgerSplitResult.model_validate(
        {
            "bucket_id": applied.bucket_id,
            "parent_transaction_id": applied.parent_transaction_id,
            "split_group_id": applied.split_group_id,
            "child_transaction_ids": list(applied.child_transaction_ids),
            "llm": True,
            "persisted": True,
            "provenance": applied.provenance,
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{applied.parent_transaction_id}",
        f"{tr('cli.ledger.labels.children')}\t{len(applied.child_transaction_ids)}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{applied.provenance}",
    ]
    _emit_envelope(ctx, command="ledger.split", result=result, lines=lines)


def _autosplit_emit_single(
    ctx: typer.Context,
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    apply: bool,
    actor: str | None,
    result_models: tuple[type[BaseModel], type[BaseModel]],
) -> None:
    """Preview or apply the in-place single-line classification (no-split verdict)."""
    suggest_model, single_model = result_models
    child = suggestion.children[0]
    if not apply:
        suggest_result = suggest_model.model_validate(
            {
                "llm": True,
                "persisted": False,
                "transaction_id": suggestion.transaction_id,
                "provider": suggestion.provider.value if suggestion.provider is not None else "local-vision",
                "classification": BusinessClassification.BUSINESS.value,
                "category": child.category.value if child.category is not None else None,
                "confidence": "1",
                "reason": suggestion.reason,
                "provenance": suggestion.provenance,
            },
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{BusinessClassification.BUSINESS.value}",
            f"{tr('cli.ledger.labels.category_id')}\t{child.category.value if child.category else ''}",
            f"{tr('cli.ledger.labels.iva_category')}\t{child.iva_category.value if child.iva_category else ''}",
            tr("cli.ledger.classify.auto_split_single_line"),
            tr("cli.ledger.classify.llm_review_hint"),
        ]
        _emit_envelope(ctx, command="ledger.classify", result=suggest_result, lines=lines)
        return
    try:
        result = apply_evidence_classification(
            suggestion,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
        )
    except TransactionValidationError as exc:
        raise _bad(str(exc)) from exc
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = single_model.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
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
    provider: LLMProvider | None,
    apply: bool,
    actor: str | None,
    read_evidence: bool = False,
    evidence_acknowledged: bool = False,
    vision_model: str | None = None,
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
    from ._ledger_payloads import LedgerClassifyLlmSaturateResult, LedgerClassifySingleResult

    if classification is not None or from_csv is not None:
        raise _bad(
            tr(
                "cli.ledger.classify.llm_exclusive",
                default="--llm cannot be combined with --classification or --from-csv; "
                "the manual path is the explicit operator override.",
            ),
        )
    if transaction_id is None:
        raise _bad(
            tr(
                "cli.ledger.classify.id_required",
                default="A transaction id is required when --from-csv is not provided.",
            ),
        )
    if provider is not None and not is_llm_provider_available(provider):
        raise _bad(
            tr(
                "cli.ledger.classify.llm_provider_unavailable",
                provider=provider.value,
                default=(
                    f"LLM provider {provider.value!r} is unavailable: its CLI is not on PATH. "
                    f"Install the {provider.value!r} CLI and ensure it is on PATH, "
                    "or run 'aeat app ledger providers' to list usable providers."
                ),
            ),
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
            read_evidence=read_evidence,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
        )
    except LLMClassifierError as exc:
        raise _bad(
            tr(
                "cli.ledger.classify.llm_failed",
                reason=str(exc),
                default=f"LLM classification failed: {exc}",
            ),
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
        classify_result = LedgerClassifyLlmSaturateResult.model_validate(
            {
                "llm": True,
                "persisted": False,
                "transaction_id": suggestion.transaction_id,
                "provider": suggestion.provider.value if suggestion.provider is not None else "local-vision",
                "classification": suggestion.classification.value,
                "category": suggestion.category.value if suggestion.category is not None else None,
                "confidence": format(suggestion.confidence, "f"),
                "reason": suggestion.reason,
                "provenance": suggestion.provenance,
                **derived_fields,
            },
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
                ],
            )
        elif suggestion.iva_category is not None:
            lines.append(f"{tr('cli.ledger.classify.saturate_non_derivable')}\t{suggestion.derivation_note}")
        lines.append(f"{tr('cli.ledger.classify.llm_confidence_label')}\t{format(suggestion.confidence, 'f')}")
        lines.append(tr("cli.ledger.classify.llm_review_hint"))
        notices: list[Notice] = []
        if suggestion.recommends_split:
            notice = _split_recommendation_notice(suggestion.transaction_id, provider=provider)
            notices.append(notice)
            lines.append(f"{tr('cli.ledger.classify.split_recommended_label')}\t{notice.suggestion}")
        _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines, notices=notices)
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
    # D1: the --llm --saturate --apply path is a single-transaction mutation; it
    # emits the canonical mutation quintet (the saturated substrate is already
    # persisted on `transaction`), with the substrate surfaced in the text lines.
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.iva_category')}\t{iva_category_value or ''}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


def _ledger_operator_iva_derive(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: str | None,
    from_csv: str | None,
    iva_category: IvaCategory | None,
    actor: str | None,
) -> None:
    """Derive the IVA substrate from an OPERATOR-chosen category (no LLM).

    The fallback for ``classify --saturate`` without ``--llm``: when the model
    declines (returns ``unknown``) or the operator already knows the category,
    pick it with ``--iva-category`` and the system derives the base, rate, and
    amount from the registry — the same grounded
    :func:`derive_operator_iva_substrate` path the LLM saturate uses, but
    operator-initiated and stamped with ``derived:`` provenance. Only the IVA
    substrate is touched; the business classification and its provenance are
    left intact.
    """
    from ._ledger_payloads import LedgerClassifySingleResult

    if from_csv is not None or classification is not None:
        raise _bad(
            "--saturate without --llm derives the IVA substrate from --iva-category alone; "
            "it cannot be combined with --classification or --from-csv. Classify the row "
            "first, then run 'classify <id> --iva-category <category> --saturate'.",
        )
    if transaction_id is None:
        raise _bad(
            tr(
                "cli.ledger.classify.id_required",
                default="A transaction id is required when --from-csv is not provided.",
            ),
        )
    if iva_category is None:
        raise _bad(
            tr(
                "cli.ledger.classify.saturate_requires_llm",
                default=(
                    "--saturate needs an IVA category: supply --iva-category to derive the "
                    "base, rate, and amount, or --llm <provider> to have the model select one."
                ),
            ),
        )

    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    try:
        derivation = derive_operator_iva_substrate(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            iva_category=iva_category,
            actor=actor or resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    except TransactionValidationError as exc:
        raise _bad(str(exc)) from exc
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc

    if not derivation.derivable:
        raise _bad(
            f"{iva_category.value} has no simple Spanish rate to derive: {derivation.note} "
            "Supply --taxable-base, --iva-rate, and --iva-amount by hand for this category.",
        )

    result = derivation.result
    taxable_base = derivation.taxable_base
    iva_rate = derivation.iva_rate
    iva_amount = derivation.iva_amount
    if result is None or taxable_base is None or iva_rate is None or iva_amount is None:
        raise _bad(
            f"{iva_category.value} was reported derivable but produced no IVA substrate; "
            "supply --taxable-base, --iva-rate, and --iva-amount by hand for this category.",
        )

    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.labels.iva_category')}\t{derivation.iva_category.value}",
        f"{tr('cli.ledger.labels.taxable_base')}\t{format(taxable_base, 'f')}",
        f"{tr('cli.ledger.labels.iva_rate')}\t{format(iva_rate, 'f')}",
        f"{tr('cli.ledger.labels.iva_amount')}\t{format(iva_amount, 'f')}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


@app.command("allocate", help=tr("cli.ledger.allocate.help"))
def ledger_allocate(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.allocate.id_help")),
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
    transaction_id: str = typer.Argument(
        ...,
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
        # D1/D2: project the mutated transaction onto the result's `transaction`
        # slot and carry the evidence update as a typed payload (mode="json" so
        # the nested TransactionPayload's str fields validate cleanly).
        payload["evidence_update"] = evidence_result_payload.model_dump(mode="json")
        payload["transaction"] = evidence_result_payload.transaction.model_dump(mode="json")
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


register_ratios_commands(app)


register_business_invoice_commands(app)


register_inventory_commands(app)


register_evidence_commands(app)


register_rule_commands(app)


register_import_commands(app)
