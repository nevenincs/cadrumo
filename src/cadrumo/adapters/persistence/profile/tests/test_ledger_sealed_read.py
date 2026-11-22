"""Which movements a finalized declaration seals, read once against encrypted profile storage."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.batch_update import plan_batch_update
from cadrumo.application.ledger.batch_update_contracts import (
    LEDGER_BATCH_UPDATE_MAX_ROWS,
    LedgerBatchUpdateRow,
    LedgerPropertySet,
)
from cadrumo.application.ledger.sealed_read_operation import LedgerSealedReadRequest, read_sealed_rows
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from .ledger_action_persistence_support import (
    BUCKET_ID,
    persist_verified_revision_citing_transaction,
    repositories,
)
from .test_ledger_batch_update import _ports, _rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SEALED = 200
_OPEN = 5


def test_two_hundred_sealed_movements_are_answered_in_one_read_as_the_batch_guard_refuses_them(
    secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    rows = _rows(secure_objects, _SEALED + _OPEN)
    sealed_ids = [row.transaction_id for row in rows[:_SEALED]]
    open_ids = [row.transaction_id for row in rows[_SEALED:]]
    # The expectation is what this test sealed, not what the read derives.
    persist_verified_revision_citing_transaction(
        secure_objects,
        transaction_id=sealed_ids[0],
        additional_transaction_ids=sealed_ids[1:],
        operation=operation,
    )
    missing = "f" * 64
    asked = (*open_ids[:2], *sealed_ids, *open_ids[2:], missing)

    with _ports(secure_objects) as ports:
        answered = read_sealed_rows(asked, bucket_id=BUCKET_ID, ports=ports)

    assert [row.transaction_id for row in answered] == list(asked)
    states = {row.transaction_id: row.state for row in answered}
    assert {txid for txid, state in states.items() if state == "sealed"} == set(sealed_ids)
    assert {txid for txid, state in states.items() if state == "open"} == set(open_ids)
    assert states[missing] == "not_found"
    for row in answered:
        if row.state == "sealed":
            assert row.seal_count == 1 and len(row.seals) == 1
            assert row.seals[0].revision_state
        else:
            assert row.seal_count == 0 and row.seals == ()

    # The batch edit refuses exactly the movements the read calls sealed.
    properties = LedgerPropertySet(fields=("group_label",), group_label="synthetic group")
    stored = repositories(secure_objects)[0].load().transactions
    probe = (sealed_ids[0], sealed_ids[-1], *open_ids[:2])
    newest = max(row.modified_at for row in stored.values())
    with _ports(secure_objects) as ports:
        plan = plan_batch_update(
            bucket_id=BUCKET_ID,
            rows=tuple(
                LedgerBatchUpdateRow(
                    transaction_id=txid,
                    expected_modified_at=stored[txid].modified_at.isoformat(),
                    properties=properties,
                )
                for txid in probe
            ),
            actor="operator",
            source_command="ledger batch edit",
            ports=ports,
            now=newest + timedelta(minutes=1),
        )
    assert [(row.cause == "sealed") for row in plan.rows] == [states[txid] == "sealed" for txid in probe]


def test_a_read_names_each_movement_once_and_within_the_batch_bound() -> None:
    with pytest.raises(ValidationError):
        LedgerSealedReadRequest(profile_id=uuid4(), transaction_ids=("a", "a"))
    with pytest.raises(ValidationError):
        LedgerSealedReadRequest(profile_id=uuid4(), transaction_ids=())
    with pytest.raises(ValidationError):
        LedgerSealedReadRequest(
            profile_id=uuid4(), transaction_ids=tuple(f"{n:x}" for n in range(LEDGER_BATCH_UPDATE_MAX_ROWS + 1))
        )
