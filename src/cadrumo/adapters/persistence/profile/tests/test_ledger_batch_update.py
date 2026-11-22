"""One reviewed batch edit against encrypted profile storage, row by row."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.batch_update import BatchUpdatePlan, plan_batch_update, write_batch_update
from cadrumo.application.ledger.batch_update_contracts import LedgerBatchUpdateRow, LedgerPropertySet
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.categories.spending_category_catalogue import spending_category_tokens
from cadrumo.domain.transactions.models import Transaction

from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    BUCKET_ID,
    create_manual_row,
    persist_verified_revision_citing_transaction,
    repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@contextmanager
def _ports(secure_objects: SecureObjectRepository) -> Generator[LedgerActionPorts]:
    transaction_repository, event_repository = repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
    ) as ports:
        yield ports


def _rows(secure_objects: SecureObjectRepository, count: int) -> tuple[Transaction, ...]:
    for index in range(count):
        create_manual_row(secure_objects, description=f"synthetic batch row {index}", idempotency_key=f"batch-{index}")
    catalogue = repositories(secure_objects)[0].load()
    return tuple(sorted(catalogue.transactions.values(), key=lambda row: row.raw.description))


def _category(operation: PinnedAuthorityOperation, at: int = 0) -> str:
    return spending_category_tokens(authority=operation)[at].value


def _business(category: str) -> LedgerPropertySet:
    return LedgerPropertySet(
        fields=("business_classification", "category_id"), business_classification="BUSINESS", category_id=category
    )


def _row(
    transaction: Transaction, properties: LedgerPropertySet, *, seen: datetime | None = None
) -> LedgerBatchUpdateRow:
    return LedgerBatchUpdateRow(
        transaction_id=transaction.transaction_id,
        expected_modified_at=(seen or transaction.modified_at).isoformat(),
        properties=properties,
    )


def _plan(
    secure_objects: SecureObjectRepository, rows: tuple[LedgerBatchUpdateRow, ...], *, later: timedelta = timedelta()
) -> BatchUpdatePlan:
    # Each plan is stamped a little after the newest stored row, so its correction events are distinct.
    newest = max(row.modified_at for row in repositories(secure_objects)[0].load().transactions.values())
    at = newest + timedelta(minutes=1) + later
    with _ports(secure_objects) as ports:
        return plan_batch_update(
            bucket_id=BUCKET_ID, rows=rows, actor="operator", source_command="ledger batch edit", ports=ports, now=at
        )


def _write(secure_objects: SecureObjectRepository, plan: BatchUpdatePlan) -> tuple[str, ...]:
    with _ports(secure_objects) as ports:
        return write_batch_update(bucket_id=BUCKET_ID, plan=plan, ports=ports)


def _event_types(secure_objects: SecureObjectRepository) -> list[BucketEventType]:
    return [event.event_type for event in repositories(secure_objects)[1].load().for_bucket(BUCKET_ID)]


def test_one_property_set_is_written_onto_every_row_in_one_save_with_previous_values(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    rows = _rows(secure_objects, 3)
    category = _category(operation)
    request = tuple(_row(row, _business(category)) for row in rows)
    preview = _plan(secure_objects, request)
    assert [row.outcome for row in preview.rows] == ["applied"] * 3
    assert all(
        row.previous
        == LedgerPropertySet(
            fields=("business_classification", "category_id"), business_classification="NOT_YET_PROCESSED"
        )
        for row in preview.rows
    )
    # A preview writes nothing.
    assert all(row.category_id is None for row in repositories(secure_objects)[0].load().transactions.values())

    written = _plan(secure_objects, request)
    assert written.digest == preview.digest
    event_ids = _write(secure_objects, written)
    assert event_ids
    stored = repositories(secure_objects)[0].load().transactions
    for result in written.rows:
        assert result.result_transaction_id is not None
        assert stored[result.result_transaction_id].category_id == category
        assert stored[result.result_transaction_id].modified_at.isoformat() == result.modified_at
    assert _event_types(secure_objects).count(BucketEventType.LEDGER_TRANSACTION_CREATED) == 3
    assert len(_event_types(secure_objects)) == 3 + len(event_ids)


def test_a_row_changed_since_it_was_seen_or_gone_is_a_conflict_and_the_others_apply(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    first, second, third = _rows(secure_objects, 3)
    properties = _business(_category(operation))
    missing = LedgerBatchUpdateRow(
        transaction_id="0" * 64, expected_modified_at=first.modified_at.isoformat(), properties=properties
    )
    request = (
        _row(first, properties),
        _row(second, properties, seen=second.modified_at - timedelta(seconds=1)),
        missing,
        _row(third, properties),
    )
    plan = _plan(secure_objects, request)
    assert [(row.outcome, row.cause) for row in plan.rows] == [
        ("applied", None),
        ("conflict", "changed_since_seen"),
        ("conflict", "not_found"),
        ("applied", None),
    ]
    _write(secure_objects, plan)
    stored = repositories(secure_objects)[0].load().transactions
    assert stored[second.transaction_id] == second


def test_an_invalid_value_refuses_only_its_row_with_a_said_cause(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    first, second = _rows(secure_objects, 2)
    good = _business(_category(operation))
    unknown = _business("no-such-synthetic-category")
    plan = _plan(secure_objects, (_row(first, unknown), _row(second, good)))
    refused, applied = plan.rows
    assert (refused.outcome, refused.cause) == ("refused", "invalid")
    assert refused.messages and all(message.strip() for message in refused.messages)
    assert applied.outcome == "applied"
    _write(secure_objects, plan)
    stored = repositories(secure_objects)[0].load().transactions
    assert stored[first.transaction_id] == first


def test_a_row_a_finalized_declaration_cites_is_refused_as_sealed(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    sealed, free = _rows(secure_objects, 2)
    persist_verified_revision_citing_transaction(
        secure_objects, transaction_id=sealed.transaction_id, operation=operation
    )
    properties = _business(_category(operation))
    plan = _plan(secure_objects, (_row(sealed, properties), _row(free, properties)))
    assert [(row.outcome, row.cause) for row in plan.rows] == [("refused", "sealed"), ("applied", None)]


def test_a_restated_value_is_unchanged_and_writes_nothing(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    (row,) = _rows(secure_objects, 1)
    properties = _business(_category(operation))
    _write(secure_objects, _plan(secure_objects, (_row(row, properties),)))
    current = next(iter(repositories(secure_objects)[0].load().transactions.values()))
    events_before = _event_types(secure_objects)
    again = _plan(secure_objects, (_row(current, properties),))
    assert [result.outcome for result in again.rows] == ["unchanged"]
    assert _write(secure_objects, again) == ()
    assert _event_types(secure_objects) == events_before


def test_undo_writes_the_previous_values_back_as_a_new_correction(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    rows = _rows(secure_objects, 2)
    first_category, second_category = _category(operation, 0), _category(operation, 1)
    _write(secure_objects, _plan(secure_objects, tuple(_row(row, _business(first_category)) for row in rows)))
    stored = repositories(secure_objects)[0].load().transactions
    edit = LedgerPropertySet(fields=("category_id",), category_id=second_category)
    applied = _plan(secure_objects, tuple(_row(row, edit) for row in stored.values()), later=timedelta(hours=1))
    _write(secure_objects, applied)
    history = len(_event_types(secure_objects))

    after = repositories(secure_objects)[0].load().transactions
    undo = tuple(
        LedgerBatchUpdateRow(
            transaction_id=result.result_transaction_id or "",
            expected_modified_at=result.modified_at or "",
            properties=result.previous or edit,
        )
        for result in applied.rows
    )
    undone = _plan(secure_objects, undo, later=timedelta(hours=2))
    assert [row.outcome for row in undone.rows] == ["applied", "applied"]
    _write(secure_objects, undone)
    restored = repositories(secure_objects)[0].load().transactions
    assert {row.category_id for row in restored.values()} == {first_category}
    # History is kept: the undo is one more recorded correction, not an erasure.
    assert len(restored) == len(after)
    assert len(_event_types(secure_objects)) > history
