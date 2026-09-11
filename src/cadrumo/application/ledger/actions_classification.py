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
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, NamedTuple

from pydantic import ValidationError

if TYPE_CHECKING:
    from datetime import datetime

    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...domain.transactions.classification_rule import LedgerClassificationRule
    from ...domain.transactions.models import TransactionCatalogue
    from .models import LedgerRemovalBlocker
    from .rule_repository import LedgerClassificationRuleRepositoryProtocol

from ...core.errors.error_codes import resolve_error_message
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...domain.buckets.event import BucketEvent
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState, is_classified
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from .actions_common import (
    blockers_by_source_transaction_id,
    normalise_timestamp,
    raise_finalized_modelo_blocked,
    replace_transaction,
    require_transaction,
    resolve_bucket_event_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
    transaction_modelo_source_ids,
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


def _validate_bulk_classify_headers(fieldnames: Sequence[str] | None) -> bool:
    """Validate CSV columns before any row or storage processing begins."""
    if fieldnames is None:
        return False
    unknown = frozenset(fieldnames) - BULK_CLASSIFY_ALLOWED_COLUMNS
    if unknown:
        raise TransactionValidationError(
            f"bulk classify CSV contains unknown columns: {', '.join(sorted(unknown))}",
            context={"unknown_columns": sorted(unknown)},
        )
    if "transaction_id" not in fieldnames or "classification" not in fieldnames:
        raise TransactionValidationError(
            "bulk classify CSV must include 'transaction_id' and 'classification' columns",
        )
    return True


def _surplus_bulk_classify_failure(
    idx: int,
    raw_row: Mapping[str | None, object],
) -> BulkClassifyFailure | None:
    """Return the localized failure for a row wider than its CSV header."""
    transaction_id = _raw_csv_text(raw_row.get("transaction_id", ""))
    if not raw_row.get(None):
        return None
    return BulkClassifyFailure(
        row_index=idx,
        transaction_id=transaction_id,
        reason="bulk classify CSV row has more cells than header columns",
    )


def _normalise_bulk_classify_row(
    raw_row: Mapping[str | None, object],
) -> tuple[str, dict[str, str | None], list[str]]:
    """Trim textual CSV cells and identify cells that cannot be classified."""
    transaction_id = _raw_csv_text(raw_row.get("transaction_id", ""))
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
    return transaction_id, normalised_row, malformed_cells


def _parse_bulk_classify_data_row(
    idx: int,
    raw_row: Mapping[str | None, object],
) -> tuple[BulkClassifyRow | None, frozenset[str], BulkClassifyFailure | None]:
    """Parse one normalized row and retain its source-row failure context."""
    transaction_id, normalised_row, malformed_cells = _normalise_bulk_classify_row(raw_row)
    if malformed_cells:
        return (
            None,
            frozenset[str](),
            BulkClassifyFailure(
                row_index=idx,
                transaction_id=transaction_id,
                reason=f"bulk classify CSV row contains non-text cells: {', '.join(malformed_cells)}",
            ),
        )
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
        return (
            None,
            frozenset[str](),
            BulkClassifyFailure(
                row_index=idx,
                transaction_id=transaction_id,
                reason=str(exc),
            ),
        )
    if not is_classified(parsed.classification):
        # Mirror the single-classify guard: only BUSINESS / PERSONAL / MIXED
        # are operator-assignable. A row naming a pipeline-managed state
        # (SKIPPED_BY_RULE, FAILED_VALIDATION, ...) reds rather than applying.
        return (
            None,
            frozenset[str](),
            BulkClassifyFailure(
                row_index=idx,
                transaction_id=parsed.transaction_id,
                reason=(
                    f"classification '{parsed.classification.value}' is set automatically by aeat; "
                    "use BUSINESS, PERSONAL, or MIXED"
                ),
            ),
        )
    return parsed, _provided_bulk_classify_patch_columns(normalised_row), None


def _provided_bulk_classify_patch_columns(normalised_row: Mapping[str, str | None]) -> frozenset[str]:
    """Return populated patch columns, excluding the row identity column."""
    return frozenset(
        column
        for column in _BULK_CLASSIFY_PATCH_COLUMNS
        if column != "classification" and normalised_row.get(column) is not None
    )


def _parse_bulk_classify_rows(csv_text: str) -> tuple[list[_ParsedBulkClassifyRow], list[BulkClassifyFailure]]:
    """Parse the CSV header and collect localized row failures in input order."""
    # Parse the CSV header to detect unknown columns before touching storage.
    reader = csv.DictReader(io.StringIO(csv_text))
    if not _validate_bulk_classify_headers(reader.fieldnames):
        return [], []

    parsed_rows: list[_ParsedBulkClassifyRow] = []
    parse_failures: list[BulkClassifyFailure] = []
    for idx, raw_row in enumerate(reader):
        surplus_failure = _surplus_bulk_classify_failure(idx, raw_row)
        if surplus_failure is not None:
            parse_failures.append(surplus_failure)
            continue
        parsed, provided_patch_columns, parse_failure = _parse_bulk_classify_data_row(idx, raw_row)
        if parse_failure is not None:
            parse_failures.append(parse_failure)
        elif parsed is not None:
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
        current = require_transaction(working, resolved_transaction_id)
        if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            raise TransactionValidationError(
                "only active ledger transactions can be edited; archived, stashed, and split-parent rows are immutable",
                context={
                    "transaction_id": resolved_transaction_id,
                    "lifecycle_state": current.lifecycle_state.value,
                },
            )
        source_ids = transaction_modelo_source_ids(current)
        blockers = tuple(b for txid in source_ids for b in blockers_by_txid.get(txid, ()))
        if blockers:
            raise_finalized_modelo_blocked(
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
        updated = replace_transaction(working, old_transaction_id=resolved_transaction_id, replacement=replacement)
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
    # ``save_transaction_catalogue_and_events``, which needs the adapter-only
    # ``save_with_secure_object_writes`` / ``to_secure_object_write`` methods
    # absent from the Protocol. The sole caller always passes already-narrowed
    # concrete repositories (see ``resolve_transaction_repository`` /
    # ``resolve_bucket_event_repository`` at the call site).
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
    now = normalise_timestamp(None)
    working = repository.load()
    all_events: list[BucketEvent] = []
    blockers_by_txid = blockers_by_source_transaction_id(
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
        save_transaction_catalogue_and_events(
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
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repo = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
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
    from ...domain.transactions.classification_rule import LedgerClassificationRule
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


class ClassificationRulePlanRow(NamedTuple):
    """One transaction the stored rules would classify, and the rule that wins."""

    transaction_id: str
    description: str
    matched_rule_id: str
    classification: BusinessClassification
    category_id: str | None


class ClassificationRulePlan(NamedTuple):
    """What applying the stored rules right now would do, without doing it.

    Carries the same counters the applied result reports, so a preview and the
    run it previews describe the same scan rather than two different summaries.
    """

    rules_evaluated: int
    transactions_scanned: int
    skipped_already_classified: int
    no_match: int
    matches: tuple[ClassificationRulePlanRow, ...]


def _classification_rule_in_scope(transaction: Transaction, *, reaffirm: bool) -> bool:
    """Return whether one transaction belongs to the rule-engine scan."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    if transaction.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return True
    return reaffirm and transaction.classified_by == CLASSIFIED_BY_MANUAL


def _classification_rule_scope(
    catalogue: TransactionCatalogue,
    *,
    reaffirm: bool,
) -> tuple[tuple[Transaction, ...], int]:
    """Collect in-scope rows and count active rows excluded from that scope."""
    in_scope = tuple(
        transaction
        for transaction in catalogue.transactions.values()
        if _classification_rule_in_scope(transaction, reaffirm=reaffirm)
    )
    skipped_already_classified = sum(
        1
        for transaction in catalogue.transactions.values()
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and not _classification_rule_in_scope(transaction, reaffirm=reaffirm)
        and transaction.business_classification is not BusinessClassification.NOT_YET_PROCESSED
    )
    return in_scope, skipped_already_classified


def _winning_classification_rule(
    transaction: Transaction,
    rules: tuple[LedgerClassificationRule, ...],
) -> LedgerClassificationRule | None:
    """Return the first stored rule matching a transaction description."""
    return next((rule for rule in rules if rule.matches(transaction.raw.description)), None)


def _planned_rule_matches(
    transactions: tuple[Transaction, ...],
    rules: tuple[LedgerClassificationRule, ...],
) -> tuple[int, tuple[ClassificationRulePlanRow, ...]]:
    """Build ordered winning-rule rows and count transactions with no match."""
    matches: list[ClassificationRulePlanRow] = []
    no_match = 0
    for transaction in transactions:
        winner = _winning_classification_rule(transaction, rules)
        if winner is None:
            no_match += 1
            continue
        matches.append(
            ClassificationRulePlanRow(
                transaction_id=transaction.transaction_id,
                description=transaction.raw.description,
                matched_rule_id=winner.rule_id,
                classification=winner.classification,
                category_id=winner.category_id,
            )
        )
    return no_match, tuple(matches)


def plan_classification_rules(
    *,
    bucket_id: str,
    reaffirm: bool = False,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    rule_repository: LedgerClassificationRuleRepositoryProtocol | None = None,
) -> ClassificationRulePlan:
    """Resolve which stored rule would classify each in-scope transaction.

    This is the ONE place scope and first-match are decided. ``apply`` writes
    the plan it returns and a preview renders it, so a preview cannot promise
    an outcome the run does not produce -- the failure mode of two engines that
    agree only until one of them is edited.

    Scope is ACTIVE transactions in ``NOT_YET_PROCESSED``; ``reaffirm`` widens
    it to ACTIVE rows already classified manually. Rules are evaluated in
    stored priority order and the first match wins.

    Args:
        bucket_id: The owning profile bucket.
        reaffirm: Whether to re-run over manually classified rows.
        transaction_repository: Injected catalogue; resolved when omitted.
        rule_repository: Injected rule store; resolved when omitted.

    Returns:
        The planned matches and the counters describing the scan.
    """
    from .rule_repository import ledger_classification_rule_repository

    tx_repo = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    rule_repo = (
        rule_repository if rule_repository is not None else ledger_classification_rule_repository(bucket_id=bucket_id)
    )
    rules: tuple[LedgerClassificationRule, ...] = rule_repo.list_rules()
    catalogue = tx_repo.load()
    in_scope, skipped_already_classified = _classification_rule_scope(catalogue, reaffirm=reaffirm)
    no_match, matches = _planned_rule_matches(in_scope, rules)

    return ClassificationRulePlan(
        rules_evaluated=len(rules),
        transactions_scanned=len(in_scope),
        skipped_already_classified=skipped_already_classified,
        no_match=no_match,
        matches=tuple(matches),
    )


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
    tx_repo = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repo = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    plan = plan_classification_rules(
        bucket_id=bucket_id,
        reaffirm=reaffirm,
        transaction_repository=tx_repo,
        rule_repository=rule_repository,
    )

    all_event_ids: list[str] = []
    applied_rows: list[ApplyRulesAppliedRow] = []
    for row in plan.matches:
        patch = ManualLedgerTransactionPatch(
            business_classification=row.classification,
            category_id=row.category_id,
        )
        result = update_manual_transaction_fields(
            bucket_id=bucket_id,
            transaction_id=row.transaction_id,
            patch=patch,
            actor=actor,
            classified_by_override=f"rule:{row.matched_rule_id}",
            source_command=source_command,
            reaffirm=reaffirm,
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
        )
        all_event_ids.extend(result.bucket_event_ids)
        applied_rows.append(
            ApplyRulesAppliedRow(
                transaction_id=row.transaction_id,
                matched_rule_id=row.matched_rule_id,
                classification=row.classification,
            ),
        )

    return ApplyRulesResult(
        rules_evaluated=plan.rules_evaluated,
        transactions_scanned=plan.transactions_scanned,
        matched=len(applied_rows),
        skipped_already_classified=plan.skipped_already_classified,
        no_match=plan.no_match,
        applied=tuple(applied_rows),
        bucket_event_ids=tuple(all_event_ids),
    )


__all__ = [
    "add_classification_rule",
    "apply_classification_rules",
    "bulk_classify_from_csv",
]
