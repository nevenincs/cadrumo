"""Plan and write one batch edit of ledger movements.

Every row is resolved against one decrypted catalogue: a movement that is gone
or changed since the person saw it is a conflict, one that cannot take changes
or that a finalized declaration seals is refused with its cause, and every other
row is built through the same canonical replacement a single correction uses.
The plan's digest binds what each row would become and what it held, so a
write happens only for the plan the person reviewed, in one guarded save of the
catalogue and its events.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ...core.errors.hierarchy import CadrumoError
from ...domain.buckets.event import BucketEvent
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.classification_effects import takes_changes
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction, TransactionCatalogue
from .action_ports import LedgerActionPorts
from .actions_common import (
    blockers_by_source_transaction_id,
    display_decimal,
    replace_transaction,
    resolve_bucket_event_repository,
    resolve_revision_guarded_transaction_repository,
    save_transaction_catalogue_and_events,
    transaction_modelo_source_ids,
)
from .batch_update_contracts import (
    LEDGER_BATCH_UPDATE_MAX_ROW_MESSAGES,
    LEDGER_PROPERTY_SET_CLASSIFY_FIELD_NAMES,
    LEDGER_PROPERTY_SET_UNCLEARABLE_FIELD_NAMES,
    LedgerBatchRowCause,
    LedgerBatchRowResult,
    LedgerBatchUpdateRow,
    LedgerPropertySet,
    LedgerPropertySetField,
)
from .classify_patch import resolve_classification_patch_values
from .classify_requests import require_primary_classification
from .manual_update import command_from_patch, prepare_manual_transaction_update
from .models import ManualLedgerTransactionPatch
from .validation_messages import ledger_refusal_sentence

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .models import LedgerRemovalBlocker

_ROW_REFUSALS = (CadrumoError, ValidationError, ValueError)
_SEALED_CONTEXT_KEY = "calculation_revision_id"
"""The context a finalized-declaration refusal names its blocking revision under."""


class LedgerBatchPlanChangedError(CadrumoError):
    """A batch edit's apply found a plan other than the reviewed one, and wrote nothing."""

    def __init__(self, plan: BatchUpdatePlan) -> None:
        """Keep the plan found, for the person to review again."""
        super().__init__("batch edit plan changed since it was reviewed", context={"plan_digest": plan.digest})
        self.plan = plan


@dataclass(frozen=True, slots=True)
class BatchUpdatePlan:
    """The per-row answer for one batch edit and what writing it stores."""

    rows: tuple[LedgerBatchRowResult, ...]
    digest: str
    catalogue: TransactionCatalogue
    catalogue_revision: str
    events: tuple[BucketEvent, ...]


def property_text(transaction: Transaction, name: LedgerPropertySetField) -> str | None:
    """Return the stored value of one property as the text a property set carries."""
    value: object = transaction.raw.counterparty if name == "counterparty" else getattr(transaction, name)
    if value is None:
        return None
    if isinstance(value, Decimal):
        return display_decimal(value)
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def property_set_of(transaction: Transaction, fields: tuple[LedgerPropertySetField, ...]) -> LedgerPropertySet:
    """Return the stored values of ``fields``, as one typed property set."""
    values: dict[str, object] = {"fields": fields}
    for name in fields:
        values[name] = property_text(transaction, name)
    return LedgerPropertySet.model_validate(values)


def _row_patch(
    properties: LedgerPropertySet, *, current: Transaction, operation: PinnedAuthorityOperation
) -> ManualLedgerTransactionPatch:
    for name in sorted(LEDGER_PROPERTY_SET_UNCLEARABLE_FIELD_NAMES & set(properties.fields)):
        value = getattr(properties, name)
        if value is None or not value.strip():
            raise TransactionValidationError(
                f"a batch edit cannot clear {name}; leave it out to keep it",
                context={"transaction_id": current.transaction_id, "field": name},
            )
    classify_fields = tuple(name for name in properties.fields if name in LEDGER_PROPERTY_SET_CLASSIFY_FIELD_NAMES)
    wire_patch = properties.classify_patch()
    if "business_classification" in classify_fields:
        require_primary_classification(wire_patch, classify_fields)
    values = resolve_classification_patch_values(wire_patch, classify_fields, current=current, operation=operation)
    for name in ("usage_ratio_id", "counterparty", "group_label"):
        if name in properties.fields:
            values[name] = getattr(properties, name)
    return ManualLedgerTransactionPatch.model_validate(values)


def _refusal(transaction_id: str, cause: LedgerBatchRowCause, messages: tuple[str, ...] = ()) -> LedgerBatchRowResult:
    outcome = "conflict" if cause in {"changed_since_seen", "not_found"} else "refused"
    return LedgerBatchRowResult(
        transaction_id=transaction_id,
        outcome=outcome,
        cause=cause,
        messages=messages[:LEDGER_BATCH_UPDATE_MAX_ROW_MESSAGES],
    )


def _error_cause(error: Exception) -> LedgerBatchRowCause:
    context = error.context if isinstance(error, CadrumoError) else None
    return "sealed" if context is not None and _SEALED_CONTEXT_KEY in context else "invalid"


@dataclass(frozen=True, slots=True)
class _RowPlan:
    result: LedgerBatchRowResult
    working: TransactionCatalogue
    events: tuple[BucketEvent, ...] = ()


def _plan_row(
    row: LedgerBatchUpdateRow,
    *,
    working: TransactionCatalogue,
    bucket_id: str,
    actor: str,
    source_command: str,
    now: datetime,
    blockers_by_txid: Mapping[str, tuple[LedgerRemovalBlocker, ...]],
    ports: LedgerActionPorts,
) -> _RowPlan:
    transaction_id = row.transaction_id
    current = working.transactions.get(transaction_id)
    if current is None:
        return _RowPlan(_refusal(transaction_id, "not_found"), working)
    if current.modified_at != row.expected_modified_instant():
        return _RowPlan(_refusal(transaction_id, "changed_since_seen"), working)
    if not takes_changes(current.lifecycle_state):
        return _RowPlan(_refusal(transaction_id, "not_active"), working)
    fields = row.properties.fields
    previous = property_set_of(current, fields)
    try:
        patch = _row_patch(row.properties, current=current, operation=ports.operation)
        command = command_from_patch(
            bucket_id=bucket_id, current=current, patch=patch, actor=actor, source_command=source_command
        )
        blockers = tuple(b for txid in transaction_modelo_source_ids(current) for b in blockers_by_txid.get(txid, ()))
        prepared = prepare_manual_transaction_update(
            current=current,
            command=command,
            previous_transaction_id=transaction_id,
            now=now,
            ports=ports,
            decides_classification="business_classification" in fields,
            finalized_blockers=blockers,
        )
    except _ROW_REFUSALS as error:
        sentence = ledger_refusal_sentence(error, fallback=type(error).__name__)
        return _RowPlan(_refusal(transaction_id, _error_cause(error), (sentence,)), working)
    if prepared is None:
        unchanged = LedgerBatchRowResult(
            transaction_id=transaction_id,
            outcome="unchanged",
            previous=previous,
            result_transaction_id=transaction_id,
            modified_at=current.modified_at.isoformat(),
        )
        return _RowPlan(unchanged, working)
    replacement, events = prepared
    selected: tuple[LedgerPropertySetField, ...] = fields
    changed: tuple[LedgerPropertySetField, ...] = tuple(
        name for name in selected if property_text(current, name) != property_text(replacement, name)
    )
    applied = LedgerBatchRowResult(
        transaction_id=transaction_id,
        outcome="applied",
        # A restated classification another party gave changes who decided it, not its value.
        changed_fields=changed or selected,
        previous=previous,
        result_transaction_id=replacement.transaction_id,
        modified_at=replacement.modified_at.isoformat(),
    )
    updated = replace_transaction(working, old_transaction_id=transaction_id, replacement=replacement)
    return _RowPlan(applied, updated, tuple(events))


def plan_digest(
    profile_id: str, rows: tuple[LedgerBatchUpdateRow, ...], results: tuple[LedgerBatchRowResult, ...]
) -> str:
    """Digest what each row asks, what it held and what it would become.

    Sentences and the new stamps are left out: they follow the language and the
    clock, not the plan.
    """
    body = {
        "profile_id": profile_id,
        "rows": [
            {
                "request": row.model_dump(mode="json"),
                "outcome": result.outcome,
                "cause": result.cause,
                "changed_fields": list(result.changed_fields),
                "previous": result.previous.model_dump(mode="json") if result.previous else None,
                "result_transaction_id": result.result_transaction_id,
            }
            for row, result in zip(rows, results, strict=True)
        ],
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def plan_batch_update(
    *,
    bucket_id: str,
    rows: tuple[LedgerBatchUpdateRow, ...],
    actor: str,
    source_command: str,
    ports: LedgerActionPorts,
    now: datetime,
) -> BatchUpdatePlan:
    """Resolve every row against one load of the catalogue, writing nothing."""
    repository = resolve_revision_guarded_transaction_repository(
        bucket_id=bucket_id, repository=ports.transaction_repository
    )
    working, catalogue_revision = repository.load_revisioned()
    blockers_by_txid = blockers_by_source_transaction_id(
        bucket_id=bucket_id,
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
    )
    results: list[LedgerBatchRowResult] = []
    events: list[BucketEvent] = []
    for row in rows:
        planned = _plan_row(
            row,
            working=working,
            bucket_id=bucket_id,
            actor=actor,
            source_command=source_command,
            now=now,
            blockers_by_txid=blockers_by_txid,
            ports=ports,
        )
        working = planned.working
        results.append(planned.result)
        events.extend(planned.events)
    frozen = tuple(results)
    return BatchUpdatePlan(
        rows=frozen,
        digest=plan_digest(bucket_id, rows, frozen),
        catalogue=working,
        catalogue_revision=catalogue_revision,
        events=tuple(events),
    )


def require_reviewed_plan(plan: BatchUpdatePlan, reviewed_digest: str) -> None:
    """Refuse, before any write, a plan other than the one the person reviewed."""
    if plan.digest != reviewed_digest:
        raise LedgerBatchPlanChangedError(plan)


def write_batch_update(*, bucket_id: str, plan: BatchUpdatePlan, ports: LedgerActionPorts) -> tuple[str, ...]:
    """Store the planned catalogue and its events in one guarded save; return the event ids."""
    if not plan.events:
        return ()
    save_transaction_catalogue_and_events(
        transaction_repository=resolve_revision_guarded_transaction_repository(
            bucket_id=bucket_id, repository=ports.transaction_repository
        ),
        event_repository=resolve_bucket_event_repository(bucket_id=bucket_id, repository=ports.bucket_event_repository),
        catalogue=plan.catalogue,
        events=plan.events,
        expected_catalogue_revision=plan.catalogue_revision,
    )
    return tuple(event.event_id for event in plan.events)


__all__ = [
    "BatchUpdatePlan",
    "LedgerBatchPlanChangedError",
    "plan_batch_update",
    "plan_digest",
    "property_set_of",
    "property_text",
    "require_reviewed_plan",
    "write_batch_update",
]
