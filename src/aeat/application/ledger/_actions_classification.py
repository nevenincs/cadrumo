"""Application services for bucket-scoped manual ledger transactions.

Services operate over a :class:`TransactionCatalogueRepository` for ledger
state, a :class:`BucketEventHistoryRepository` for durable audit events, and
an optional :class:`InvoiceCatalogueRepository` for purchase-invoice evidence
cascade on removal. The inner functions accept a :class:`TransactionCatalogue`
or :class:`InvoiceCatalogue` directly when the caller supplies pre-loaded data.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    from ...domain.transactions._classification_rule import LedgerClassificationRule

from ...core.errors import AeatError
from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...domain.buckets import (
    BucketEvent,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionLifecycleState,
    TransactionValidationError,
    is_classified,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ._actions_common import (
    _blockers_by_source_transaction_id,
    _bucket_event_repository,
    _normalise_timestamp,
    _raise_finalized_modelo_blocked,
    _replace_transaction,
    _require_transaction,
    _save_transaction_catalogue_and_events,
    _transaction_modelo_source_ids,
    _transaction_repository,
)
from ._actions_manual import _command_from_patch, _prepare_manual_transaction_update, update_manual_transaction_fields
from ._models import (
    BULK_CLASSIFY_ALLOWED_COLUMNS,
    ApplyRulesAppliedRow,
    ApplyRulesResult,
    BulkClassifyFailure,
    BulkClassifyResult,
    BulkClassifyRow,
    ManualLedgerTransactionPatch,
)


def bulk_classify_from_csv(
    *,
    bucket_id: str,
    csv_text: str,
    actor: str,
    source_command: str = "aeat app ledger classify",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> BulkClassifyResult:
    """Apply batch classifications from a CSV string.

    The CSV must contain ``transaction_id`` and ``classification`` columns;
    ``category_id``, ``business_pct``, ``taxable_base``, ``iva_rate``, and
    ``iva_amount`` are optional. The IVA facts ride the same
    :class:`ManualLedgerTransactionPatch` and
    :func:`update_manual_transaction_fields` write path the single-classify
    surface uses, so a bulk row persists the same typed
    ``taxable_base``/``iva_rate``/``iva_amount`` values as ``--id``-mode
    classify with identical validation. Unknown columns are rejected before
    any writes. Rows that fail validation (unknown transaction id, invalid
    classification value, malformed IVA-fact Decimal, pydantic error) are
    collected in ``failures`` and the remaining valid rows are applied
    (partial-success semantics matching the ledger import pattern).

    Returns a :class:`BulkClassifyResult`.
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repo = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)

    # Parse the CSV header to detect unknown columns before touching storage.
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return BulkClassifyResult(total=0, applied=0, skipped=0)
    unknown = frozenset(reader.fieldnames) - BULK_CLASSIFY_ALLOWED_COLUMNS
    if unknown:
        raise TransactionValidationError(
            f"bulk classify CSV contains unknown columns: {', '.join(sorted(unknown))}",
            context={"unknown_columns": sorted(unknown)},
        )
    if "transaction_id" not in reader.fieldnames or "classification" not in reader.fieldnames:
        raise TransactionValidationError(
            "bulk classify CSV must include 'transaction_id' and 'classification' columns",
        )

    parsed_rows: list[BulkClassifyRow] = []
    parse_failures: list[BulkClassifyFailure] = []
    for idx, raw_row in enumerate(reader):
        try:
            parsed = BulkClassifyRow.model_validate(
                # A present-but-blank optional cell (e.g. an empty
                # ``taxable_base`` on a classification-only row) maps to
                # ``None`` so the row behaves exactly as if the column were
                # absent; a populated cell carries its trimmed text into the
                # same typed ``Decimal`` coercion the single-classify path
                # uses, so a malformed value reds the row rather than
                # coercing silently.
                {k: (v.strip() or None if v is not None else v) for k, v in raw_row.items()},
                strict=False,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            parse_failures.append(
                BulkClassifyFailure(
                    row_index=idx,
                    transaction_id=raw_row.get("transaction_id", ""),
                    reason=str(exc),
                ),
            )
            continue
        if not is_classified(parsed.classification):
            # Mirror the single-classify guard: only BUSINESS / PERSONAL / MIXED
            # are operator-assignable. A row naming a pipeline-managed state
            # (SKIPPED_BY_RULE, FAILED_VALIDATION, …) reds rather than applying.
            parse_failures.append(
                BulkClassifyFailure(
                    row_index=idx,
                    transaction_id=parsed.transaction_id,
                    reason=(
                        f"classification '{parsed.classification.value}' is set automatically by aeat; "
                        "use BUSINESS, PERSONAL, or MIXED"
                    ),
                ),
            )
            continue
        parsed_rows.append(parsed)

    apply_failures: list[BulkClassifyFailure] = []
    all_event_ids: list[str] = []
    applied = 0
    skipped = 0

    # Load-once/save-once (S31): the per-row path re-encrypted the whole
    # catalogue on every update, so a 270-row batch cost ~400s of O(n)
    # re-encryption. Load the catalogue and the finalized-modelo blocker map
    # once, mutate an in-memory working catalogue, accumulate events, and
    # persist a single atomic write at the end.
    now = _normalise_timestamp(None)
    working = repository.load()
    all_events: list[BucketEvent] = []
    blockers_by_txid = _blockers_by_source_transaction_id(
        bucket_id=bucket_id,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )

    for idx, row in enumerate(parsed_rows):
        patch = ManualLedgerTransactionPatch(
            business_classification=row.classification,
            category_id=row.category_id,
            business_pct=row.business_pct,
            taxable_base=row.taxable_base,
            iva_rate=row.iva_rate,
            iva_amount=row.iva_amount,
        )
        try:
            current = _require_transaction(working, row.transaction_id)
            if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
                raise TransactionValidationError(
                    "only active ledger transactions can be edited; archived, stashed, "
                    "and split-parent rows are immutable",
                    context={
                        "transaction_id": row.transaction_id,
                        "lifecycle_state": current.lifecycle_state.value,
                    },
                )
            source_ids = _transaction_modelo_source_ids(current)
            blockers = tuple(b for txid in source_ids for b in blockers_by_txid.get(txid, ()))
            if blockers:
                _raise_finalized_modelo_blocked(
                    operation="ledger transaction update",
                    transaction_ids=source_ids,
                    blockers=blockers,
                )
            command = _command_from_patch(
                bucket_id=bucket_id,
                current=current,
                patch=patch,
                actor=actor,
                source_command=source_command,
            )
            prepared = _prepare_manual_transaction_update(
                current=current,
                command=command,
                previous_transaction_id=row.transaction_id,
                now=now,
            )
            if prepared is None:
                # field-for-field identical â€” classification already applied.
                skipped += 1
                continue
            replacement, events = prepared
            working = _replace_transaction(working, old_transaction_id=row.transaction_id, replacement=replacement)
            all_events.extend(events)
            all_event_ids.extend(event.event_id for event in events)
            applied += 1
        except (AeatError, ValidationError) as exc:
            apply_failures.append(
                BulkClassifyFailure(
                    row_index=idx,
                    transaction_id=row.transaction_id,
                    reason=str(exc),
                ),
            )

    if all_events:
        _save_transaction_catalogue_and_events(
            transaction_repository=repository,
            event_repository=event_repo,
            catalogue=working,
            events=tuple(all_events),
        )

    all_failures = parse_failures + apply_failures
    return BulkClassifyResult(
        total=len(parsed_rows) + len(parse_failures),
        applied=applied,
        skipped=skipped,
        failures=tuple(all_failures),
        bucket_event_ids=tuple(all_event_ids),
    )


def add_classification_rule(
    *,
    bucket_id: str,
    description_pattern: str,
    classification: BusinessClassification,
    category_id: str | None = None,
    priority: int = 100,
    actor: str,
    rule_repository: object | None = None,
) -> LedgerClassificationRule:
    """Persist a new ledger classification rule and return it.

    ``rule_id`` is content-addressed: adding the same
    ``description_pattern + classification + category_id`` combination
    twice produces the same id and the repository save overwrites the
    prior entry (idempotent creation).

    Raises :class:`ValueError` when ``description_pattern`` is not a
    valid regex (validated by :class:`~aeat.domain.transactions._classification_rule.LedgerClassificationRule`).
    """
    from typing import cast

    from ...domain.transactions._classification_rule import LedgerClassificationRule
    from ._rule_repository import LedgerClassificationRuleRepository

    repo: LedgerClassificationRuleRepository = (
        # CAST-RATIONALE-LEDGER-RULE-REPO-INJECT: ``rule_repository`` is typed
        # ``object | None`` to keep the public signature injection-friendly;
        # the non-None guard ensures narrowing is safe here.
        cast(LedgerClassificationRuleRepository, rule_repository)
        if rule_repository is not None
        else LedgerClassificationRuleRepository()
    )
    rule = LedgerClassificationRule.create(
        description_pattern=description_pattern,
        classification=classification,
        category_id=category_id,
        priority=priority,
        actor=actor,
    )
    repo.save(rule)
    return rule


def apply_classification_rules(
    *,
    bucket_id: str,
    reaffirm: bool = False,
    actor: str,
    source_command: str = "aeat app ledger rule apply",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    rule_repository: object | None = None,
) -> ApplyRulesResult:
    """Apply stored classification rules to unclassified ACTIVE transactions.

    Scope: ACTIVE transactions in ``NOT_YET_PROCESSED`` state.
    When ``reaffirm=True``, also includes ACTIVE transactions where
    ``classified_by == "manual"`` so the operator can explicitly
    re-run the rule engine over manually classified rows.

    Rules are evaluated in priority order (lower number = higher priority);
    the first matching rule wins. Match is ``re.search(pattern, description,
    re.IGNORECASE)``.

    Returns an :class:`ApplyRulesResult`.
    """
    from typing import cast

    from ._rule_repository import LedgerClassificationRuleRepository

    tx_repo = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repo = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    rule_repo: LedgerClassificationRuleRepository = (
        # CAST-RATIONALE-LEDGER-RULE-REPO-INJECT: same injection-friendly
        # ``object | None`` pattern as ``add_classification_rule``; the
        # non-None guard ensures the cast is safe at this point.
        cast(LedgerClassificationRuleRepository, rule_repository)
        if rule_repository is not None
        else LedgerClassificationRuleRepository()
    )

    rules: tuple[LedgerClassificationRule, ...] = rule_repo.list_rules()
    catalogue = tx_repo.load()

    all_event_ids: list[str] = []
    applied_rows: list[ApplyRulesAppliedRow] = []

    def _in_scope(tx: Transaction) -> bool:
        if tx.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            return False
        if tx.business_classification is BusinessClassification.NOT_YET_PROCESSED:
            return True
        return reaffirm and tx.classified_by == CLASSIFIED_BY_MANUAL

    active_txs = [tx for tx in catalogue.transactions.values() if _in_scope(tx)]
    transactions_scanned = len(active_txs)
    skipped_already_classified = sum(
        1
        for tx in catalogue.transactions.values()
        if tx.lifecycle_state is TransactionLifecycleState.ACTIVE
        and not _in_scope(tx)
        and tx.business_classification is not BusinessClassification.NOT_YET_PROCESSED
    )

    no_match = 0
    for tx in active_txs:
        rule_matched: LedgerClassificationRule | None = None
        for rule in rules:
            if rule.matches(tx.raw.description or ""):
                rule_matched = rule
                break
        if rule_matched is None:
            no_match += 1
            continue

        patch = ManualLedgerTransactionPatch(
            business_classification=rule_matched.classification,
            category_id=rule_matched.category_id,
        )
        result = update_manual_transaction_fields(
            bucket_id=bucket_id,
            transaction_id=tx.transaction_id,
            patch=patch,
            actor=actor,
            classified_by_override=f"rule:{rule_matched.rule_id}",
            source_command=source_command,
            reaffirm=reaffirm,
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
        )
        all_event_ids.extend(result.bucket_event_ids)
        applied_rows.append(
            ApplyRulesAppliedRow(
                transaction_id=tx.transaction_id,
                matched_rule_id=rule_matched.rule_id,
                classification=rule_matched.classification,
            ),
        )

    return ApplyRulesResult(
        rules_evaluated=len(rules),
        transactions_scanned=transactions_scanned,
        matched=len(applied_rows),
        skipped_already_classified=skipped_already_classified,
        no_match=no_match,
        applied=tuple(applied_rows),
        bucket_event_ids=tuple(all_event_ids),
    )
