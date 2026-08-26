"""Bulk and rule-based ledger classification services.

CSV bulk classification parses
:class:`~application.ledger.models.BulkClassifyRow` records, converts populated
fields into :class:`~application.ledger.models.ManualLedgerTransactionPatch`,
and applies them through
:func:`~application.ledger.actions_manual.update_manual_transaction_fields`. Rule
application evaluates :class:`~domain.transactions.LedgerClassificationRule`
instances over active transactions and returns
:class:`~application.ledger.models.ApplyRulesResult`.

Batch persistence uses the concrete
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`
so the end-of-batch save can compose the catalogue write with bucket events in
one secure-object unit of work.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, NamedTuple

from pydantic import ValidationError

if TYPE_CHECKING:
    from datetime import datetime

    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...domain.transactions import LedgerClassificationRule, TransactionCatalogue
    from .models import LedgerRemovalBlocker
    from .rule_repository import LedgerClassificationRuleRepositoryProtocol

from ...core.errors import CadrumoError, resolve_error_message
from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepositoryProtocol,
)
from ...domain.modelos import (
    CalculationRevisionCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogueRepositoryProtocol,
    TransactionLifecycleState,
    TransactionValidationError,
    is_classified,
)
from .actions_common import (
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
from .actions_manual import (
    command_from_patch as _command_from_patch,
)
from .actions_manual import (
    prepare_manual_transaction_update as _prepare_manual_transaction_update,
)
from .actions_manual import (
    update_manual_transaction_fields,
)
from .id_resolution import resolve_transaction_id
from .models import (
    BULK_CLASSIFY_ALLOWED_COLUMNS,
    ApplyRulesAppliedRow,
    ApplyRulesResult,
    BulkClassifyFailure,
    BulkClassifyResult,
    BulkClassifyRow,
    ManualLedgerTransactionPatch,
)

_BULK_CLASSIFY_NON_PATCH_COLUMNS = frozenset({"transaction_id"})
_BULK_CLASSIFY_PATCH_COLUMNS = BULK_CLASSIFY_ALLOWED_COLUMNS - _BULK_CLASSIFY_NON_PATCH_COLUMNS
type _ParsedBulkClassifyRow = tuple[int, BulkClassifyRow, frozenset[str]]


def _raw_csv_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_bulk_classify_rows(csv_text: str) -> tuple[list[_ParsedBulkClassifyRow], list[BulkClassifyFailure]]:
    # Parse the CSV header to detect unknown columns before touching storage.
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return [], []
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

    parsed_rows: list[_ParsedBulkClassifyRow] = []
    parse_failures: list[BulkClassifyFailure] = []
    for idx, raw_row in enumerate(reader):
        transaction_id = _raw_csv_text(raw_row.get("transaction_id", ""))
        surplus_cells = raw_row.get(None)
        if surplus_cells:
            parse_failures.append(
                BulkClassifyFailure(
                    row_index=idx,
                    transaction_id=transaction_id,
                    reason="bulk classify CSV row has more cells than header columns",
                ),
            )
            continue
        normalised_row: dict[str, str | None] = {}
        malformed_cells: list[str] = []
        for key, value in raw_row.items():
            if key is None:
                malformed_cells.append("<extra>")
                continue
            if value is not None and not isinstance(value, str):
                malformed_cells.append(str(key))
                continue
            normalised_row[key] = (value.strip() or None) if value is not None else None
        if malformed_cells:
            parse_failures.append(
                BulkClassifyFailure(
                    row_index=idx,
                    transaction_id=transaction_id,
                    reason=f"bulk classify CSV row contains non-text cells: {', '.join(malformed_cells)}",
                ),
            )
            continue
        try:
            parsed = BulkClassifyRow.model_validate(
                # A present-but-blank optional cell (e.g. an empty
                # ``taxable_base`` on a classification-only row) maps to
                # ``None`` so the row behaves exactly as if the column were
                # absent; a populated cell carries its trimmed text into the
                # same typed ``Decimal`` coercion the single-classify path
                # uses, so a malformed value reds the row rather than
                # coercing silently.
                normalised_row,
                strict=False,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            parse_failures.append(
                BulkClassifyFailure(
                    row_index=idx,
                    transaction_id=transaction_id,
                    reason=str(exc),
                ),
            )
            continue
        if not is_classified(parsed.classification):
            # Mirror the single-classify guard: only BUSINESS / PERSONAL / MIXED
            # are operator-assignable. A row naming a pipeline-managed state
            # (SKIPPED_BY_RULE, FAILED_VALIDATION, ...) reds rather than applying.
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
        provided_patch_columns = frozenset(
            column
            for column in _BULK_CLASSIFY_PATCH_COLUMNS
            if column != "classification" and normalised_row.get(column) is not None
        )
        parsed_rows.append((idx, parsed, provided_patch_columns))
    return parsed_rows, parse_failures


class _BulkRowOutcome(NamedTuple):
    """The per-row result of applying one parsed bulk-classify row.

    ``working`` is the (possibly-updated) working :class:`TransactionCatalogue`;
    on a skip or a failure it is the unchanged input catalogue. Exactly one of
    ``applied``, ``skipped``, or ``failure is not None`` characterises the row.
    """

    working: TransactionCatalogue
    events: tuple[BucketEvent, ...]
    applied: bool
    skipped: bool
    failure: BulkClassifyFailure | None


def _apply_one_bulk_classify_row(
    *,
    working: TransactionCatalogue,
    parsed_row: _ParsedBulkClassifyRow,
    bucket_id: str,
    actor: str,
    source_command: str,
    now: datetime,
    blockers_by_txid: dict[str, tuple[LedgerRemovalBlocker, ...]],
) -> _BulkRowOutcome:
    """Validate and apply one parsed row against the working catalogue.

    Returns the row outcome without mutating shared batch state; the caller
    folds the outcome into the accumulated counters, events, and catalogue.
    """
    idx, row, provided_patch_columns = parsed_row
    patch_values: dict[str, object] = {"business_classification": row.classification}
    patch_values.update({column: getattr(row, column) for column in provided_patch_columns})
    patch = ManualLedgerTransactionPatch.model_validate(patch_values)
    try:
        resolved_transaction_id = resolve_transaction_id(row.transaction_id, working.transactions.keys())
        current = _require_transaction(working, resolved_transaction_id)
        if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            raise TransactionValidationError(
                "only active ledger transactions can be edited; archived, stashed, and split-parent rows are immutable",
                context={
                    "transaction_id": resolved_transaction_id,
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
            previous_transaction_id=resolved_transaction_id,
            now=now,
        )
        if prepared is None:
            # field-for-field identical â€” classification already applied.
            return _BulkRowOutcome(working, (), applied=False, skipped=True, failure=None)
        replacement, events = prepared
        updated = _replace_transaction(working, old_transaction_id=resolved_transaction_id, replacement=replacement)
        return _BulkRowOutcome(updated, tuple(events), applied=True, skipped=False, failure=None)
    except (CadrumoError, ValidationError, ValueError) as exc:
        reason = resolve_error_message(exc) if isinstance(exc, CadrumoError) else str(exc)
        failure = BulkClassifyFailure(
            row_index=idx,
            transaction_id=row.transaction_id,
            reason=reason or type(exc).__name__,
        )
        return _BulkRowOutcome(working, (), applied=False, skipped=False, failure=failure)


def _apply_bulk_classify_rows(
    *,
    bucket_id: str,
    actor: str,
    source_command: str,
    # concrete, not Protocol: the accumulated end-of-batch save below calls
    # ``_save_transaction_catalogue_and_events``, which needs the adapter-only
    # ``save_with_secure_object_writes`` / ``to_secure_object_write`` methods
    # absent from the Protocol. The sole caller always passes already-narrowed
    # concrete repositories (see ``_transaction_repository`` /
    # ``_bucket_event_repository`` at the call site).
    repository: TransactionCatalogueRepository,
    event_repo: BucketEventHistoryRepository,
    parsed_rows: list[_ParsedBulkClassifyRow],
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> tuple[int, int, list[BulkClassifyFailure], list[str]]:
    apply_failures: list[BulkClassifyFailure] = []
    all_event_ids: list[str] = []
    applied = 0
    skipped = 0

    # Load-once/save-once: the per-row path re-encrypted the whole
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

    for parsed_row in parsed_rows:
        outcome = _apply_one_bulk_classify_row(
            working=working,
            parsed_row=parsed_row,
            bucket_id=bucket_id,
            actor=actor,
            source_command=source_command,
            now=now,
            blockers_by_txid=blockers_by_txid,
        )
        working = outcome.working
        if outcome.failure is not None:
            apply_failures.append(outcome.failure)
        elif outcome.skipped:
            skipped += 1
        else:
            all_events.extend(outcome.events)
            all_event_ids.extend(event.event_id for event in outcome.events)
            applied += 1

    if all_events:
        _save_transaction_catalogue_and_events(
            transaction_repository=repository,
            event_repository=event_repo,
            catalogue=working,
            events=tuple(all_events),
        )

    return applied, skipped, apply_failures, all_event_ids


def bulk_classify_from_csv(
    *,
    bucket_id: str,
    csv_text: str,
    actor: str,
    source_command: str = "aeat app ledger classify --file",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> BulkClassifyResult:
    """Apply batch classifications from a CSV string.

    The CSV must contain ``transaction_id`` and ``classification`` columns;
    ``category_id``, ``business_pct``, ``usage_ratio_id``, ``taxable_base``,
    ``iva_rate``, ``iva_amount``, ``iva_category``, and ``irpf_category`` are
    optional. Blank optional cells are treated as omitted, so a partial CSV
    classification row preserves existing tax facts instead of clearing them
    accidentally. Populated tax facts ride the same
    :class:`~application.ledger.models.ManualLedgerTransactionPatch` and the
    :func:`~application.ledger.actions_manual.update_manual_transaction_fields` write
    path the single-classify surface uses, so a bulk row persists the same typed
    ``taxable_base``/``iva_rate``/``iva_amount``/``iva_category``/
    ``irpf_category`` values as ``--id``-mode classify with identical
    validation. Unknown columns are rejected before any writes. Rows that fail
    validation (unknown transaction id, invalid classification value, malformed
    tax fact, pydantic error) are collected in ``failures`` and the remaining
    valid rows are applied
    (partial-success semantics matching the ledger import pattern).

    Returns a :class:`~application.ledger.models.BulkClassifyResult`.
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repo = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    parsed_rows, parse_failures = _parse_bulk_classify_rows(csv_text)
    if not parsed_rows and not parse_failures:
        return BulkClassifyResult(total=0, applied=0, skipped=0)

    applied, skipped, apply_failures, all_event_ids = _apply_bulk_classify_rows(
        bucket_id=bucket_id,
        actor=actor,
        source_command=source_command,
        repository=repository,
        event_repo=event_repo,
        parsed_rows=parsed_rows,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
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
    rule_repository: LedgerClassificationRuleRepositoryProtocol | None = None,
) -> LedgerClassificationRule:
    """Persist a new ledger classification rule and return it.

    ``rule_id`` is content-addressed: adding the same
    ``description_pattern + classification + category_id`` combination
    twice produces the same id and the repository save overwrites the
    prior entry (idempotent creation).

    Returns a :class:`~domain.transactions.LedgerClassificationRule`.

    Raises :exc:`ValueError` when ``description_pattern`` is not a valid
    regex, as validated by
    :class:`~domain.transactions.LedgerClassificationRule`.
    """
    from ...domain.transactions import LedgerClassificationRule
    from .rule_repository import ledger_classification_rule_repository

    repo = (
        rule_repository if rule_repository is not None else ledger_classification_rule_repository(bucket_id=bucket_id)
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
    rule_repository: LedgerClassificationRuleRepositoryProtocol | None = None,
) -> ApplyRulesResult:
    """Apply stored classification rules to unclassified ACTIVE transactions.

    Scope: ACTIVE transactions in ``NOT_YET_PROCESSED`` state.
    When ``reaffirm=True``, also includes ACTIVE transactions where
    ``classified_by == "manual"`` so the operator can explicitly
    re-run the rule engine over manually classified rows.

    Rules are evaluated in priority order (lower number = higher priority);
    the first matching rule wins. Match is ``re.search(pattern, description,
    re.IGNORECASE)``.

    Returns an :class:`~application.ledger.models.ApplyRulesResult`.
    """
    from .rule_repository import ledger_classification_rule_repository

    tx_repo = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repo = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    rule_repo = (
        rule_repository if rule_repository is not None else ledger_classification_rule_repository(bucket_id=bucket_id)
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


__all__ = [
    "add_classification_rule",
    "apply_classification_rules",
    "bulk_classify_from_csv",
]
