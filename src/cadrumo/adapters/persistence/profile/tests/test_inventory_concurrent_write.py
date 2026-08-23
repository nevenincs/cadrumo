"""Concurrent inventory writes do not discard each other.

The inventory document is a SINGLETON row, so BOTH ``create`` and
``record_movement`` are really read-whole-document, rebuild,
write-whole-document. Performed unguarded, two callers touching DIFFERENT
activity/year ledgers both read the same document and the later write silently
discarded the earlier one.

``record_movement`` needs the guard more than ``create`` does, and that is easy
to miss: appending one movement to one activity's ledger rewrites the entire
document, so it could discard a whole ledger belonging to a different activity.

Observed deterministically, by landing the interloping write inside the guarded
unit of work's read-to-write window rather than by racing threads.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted
SQL backend, independent repository instances. Nothing is mocked.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....domain.contribuyente.inventory import (
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
    MovementKind,
    MovementRecord,
    ValuationMethod,
)
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..inventory import InventoryLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "38303830-3830-4383-8383-383038303830"
_YEAR = 2025

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _ledger(actividad_id: str, *, opening: str) -> InventoryLedger:
    return InventoryLedger(
        actividad_id=actividad_id,
        year=_YEAR,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal(opening),
        closing_authority_record=None,
    )


def _movement(movement_id: str) -> MovementRecord:
    return MovementRecord(
        movement_id=movement_id,
        kind=MovementKind.PURCHASE,
        movement_date=date(_YEAR, 6, 1),
        quantity=Decimal("2"),
        unit_cost=Decimal("10"),
    )


def test_sequential_creates_through_independent_instances_accumulate() -> None:
    """Baseline: two repository instances do not lose a ledger on their own."""
    InventoryLedgerRepository().create(_ledger("retail", opening="150.00"))
    InventoryLedgerRepository().create(_ledger("wholesale", opening="250.00"))

    pairs = [(item.actividad_id, item.year) for item in InventoryLedgerRepository().load().ledgers]
    assert sorted(pairs) == [("retail", _YEAR), ("wholesale", _YEAR)]


def test_a_concurrent_create_does_not_discard_the_other_ledger() -> None:
    """DISCRIMINATING: the interleaving that used to lose a ledger."""
    repo = InventoryLedgerRepository()
    interloper_written = False

    def _create_one_while_another_lands(current: InventoryLedgerDocument) -> InventoryLedgerDocument:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            InventoryLedgerRepository().create(_ledger("wholesale", opening="250.00"))
        return InventoryLedgerDocument(ledgers=(*current.ledgers, _ledger("retail", opening="150.00")))

    repo._storage.mutate(_create_one_while_another_lands)

    pairs = [(item.actividad_id, item.year) for item in InventoryLedgerRepository().load().ledgers]
    assert sorted(pairs) == [("retail", _YEAR), ("wholesale", _YEAR)]


def test_a_concurrent_movement_does_not_discard_a_whole_foreign_ledger() -> None:
    """DISCRIMINATING, and the case most easily missed.

    ``record_movement`` appends to ONE activity's ledger but rewrites the whole
    singleton document. Unguarded, a movement recorded against ``retail`` could
    discard a ``wholesale`` ledger created in the interim — losing an entire
    activity's inventory, not just a movement.
    """
    InventoryLedgerRepository().create(_ledger("retail", opening="150.00"))

    repo = InventoryLedgerRepository()
    interloper_written = False

    def _append_to_retail_while_wholesale_lands(current: InventoryLedgerDocument) -> InventoryLedgerDocument:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            InventoryLedgerRepository().create(_ledger("wholesale", opening="250.00"))
        ledgers = list(current.ledgers)
        for index, ledger in enumerate(ledgers):
            if ledger.actividad_id == "retail":
                ledgers[index] = ledger.model_copy(
                    update={"period_movements": (*ledger.period_movements, _movement("mv-1"))},
                )
        return InventoryLedgerDocument(ledgers=tuple(ledgers))

    repo._storage.mutate(_append_to_retail_while_wholesale_lands)

    loaded = InventoryLedgerRepository().load()
    pairs = sorted((item.actividad_id, item.year) for item in loaded.ledgers)
    assert pairs == [("retail", _YEAR), ("wholesale", _YEAR)]
    retail = next(item for item in loaded.ledgers if item.actividad_id == "retail")
    assert [mv.movement_id for mv in retail.period_movements] == ["mv-1"]


def test_record_movement_returns_the_committed_ledger() -> None:
    """POSITIVE CONTROL: the public verb still returns the right ledger.

    ``mutate`` may run the mutation more than once, so the returned ledger is
    re-read out of the committed document rather than captured inside the
    closure. This pins that the value callers receive is the persisted one.
    """
    InventoryLedgerRepository().create(_ledger("retail", opening="150.00"))

    updated = InventoryLedgerRepository().record_movement("retail", _movement("mv-9"), year=_YEAR)

    assert updated.actividad_id == "retail"
    assert [mv.movement_id for mv in updated.period_movements] == ["mv-9"]
    persisted = next(item for item in InventoryLedgerRepository().load().ledgers if item.actividad_id == "retail")
    assert persisted == updated


def test_a_duplicate_pair_is_still_refused_and_not_retried() -> None:
    """A refusal is not a conflict, so the guard must not retry it."""
    InventoryLedgerRepository().create(_ledger("retail", opening="150.00"))

    with pytest.raises(InventoryLedgerError):
        InventoryLedgerRepository().create(_ledger("retail", opening="900.00"))

    assert len(InventoryLedgerRepository().load().ledgers) == 1


def test_a_concurrent_create_is_not_discarded_by_a_removal() -> None:
    """Removal rewrites the whole document too, so the seam must survive it.

    An operator deleting ``retail`` must not take ``wholesale`` with it because
    that ledger was created while the removal was in flight.

    Like its siblings above, this reaches the interleaving window through the
    seam directly, because the public verb exposes none. It therefore measures
    the GUARD and cannot see whether ``remove`` still routes through it --
    reverting the verb to an inline load-and-save leaves this green. The
    routing gate is the instrument for that half, and ``remove`` is enrolled in
    it for exactly this reason.
    """
    InventoryLedgerRepository().create(_ledger("retail", opening="150.00"))

    repo = InventoryLedgerRepository()
    interloper_written = False

    def _remove_retail_while_wholesale_lands(current: InventoryLedgerDocument) -> InventoryLedgerDocument:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            InventoryLedgerRepository().create(_ledger("wholesale", opening="250.00"))
        return InventoryLedgerDocument(
            ledgers=tuple(item for item in current.ledgers if item.actividad_id != "retail"),
        )

    repo._storage.mutate(_remove_retail_while_wholesale_lands)

    pairs = [(item.actividad_id, item.year) for item in InventoryLedgerRepository().load().ledgers]
    assert pairs == [("wholesale", _YEAR)]


def test_removing_a_ledger_that_is_already_gone_refuses_as_absent() -> None:
    """A second removal of the same ledger refuses rather than reporting success.

    Sequential rather than interleaved, deliberately: this pins the refusal
    itself, which is what a caller re-judging the absence check on a retry
    depends on. Without it a retry could find nothing to remove and report a
    deletion the call never performed.
    """
    InventoryLedgerRepository().create(_ledger("retail", opening="150.00"))
    InventoryLedgerRepository().remove("retail", year=_YEAR)

    with pytest.raises(InventoryLedgerError):
        InventoryLedgerRepository().remove("retail", year=_YEAR)
