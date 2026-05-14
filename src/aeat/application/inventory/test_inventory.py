"""Tests for the inventory application service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.application.inventory import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryMovementCommand,
    InventoryService,
    InventoryServiceInputError,
)
from aeat.core.config import Settings
from aeat.domain.profile.inventory import MovementKind, ValuationMethod

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return Settings(aeat_ledgers_dir=tmp_path / "ledgers")


class TestCreate:
    def test_create_persists_a_fresh_ledger(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        ledger = svc.create(
            bucket_id="bucket-001",
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("1000.00"),
        )
        assert ledger.actividad_id == "A1"
        assert ledger.year == 2025
        assert ledger.valuation_method is ValuationMethod.FIFO
        assert ledger.opening_stock == Decimal("1000.00")
        assert ledger.period_movements == ()

    def test_create_refuses_duplicate_actividad_year(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        with pytest.raises(InventoryActividadConflictError):
            svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="pmp")

    def test_create_refuses_invalid_valuation_method(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        with pytest.raises(InventoryServiceInputError, match="invalid valuation_method"):
            svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="lifo")

    def test_create_persists_across_service_instances(self, isolated_settings: Settings) -> None:
        InventoryService(settings=isolated_settings).create(
            bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo",
        )
        fresh = InventoryService(settings=isolated_settings)
        ledgers = fresh.list_all(bucket_id="b1")
        assert len(ledgers) == 1
        assert ledgers[0].actividad_id == "A1"


class TestList:
    def test_list_empty_bucket_returns_empty_tuple(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        assert svc.list_all(bucket_id="b1") == ()

    def test_list_returns_one_summary_per_actividad_year(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(bucket_id="b1", actividad_id="A1", year=2024, valuation_method="fifo")
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="pmp")
        svc.create(bucket_id="b1", actividad_id="A2", year=2025, valuation_method="fifo")
        summaries = svc.list_all(bucket_id="b1")
        assert len(summaries) == 3
        keys = {(s.actividad_id, s.year) for s in summaries}
        assert keys == {("A1", 2024), ("A1", 2025), ("A2", 2025)}


class TestShow:
    def test_show_returns_ledger_with_movements(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        svc.movement_add(
            bucket_id="b1",
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-001",
                movement_date=date(2025, 3, 15),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("10"),
                unit_cost=Decimal("50.00"),
            ),
        )
        ledger = svc.show(bucket_id="b1", actividad_id="A1", year=2025)
        assert len(ledger.period_movements) == 1
        assert ledger.period_movements[0].movement_id == "M-001"

    def test_show_refuses_on_missing_actividad(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        with pytest.raises(InventoryActividadNotFoundError):
            svc.show(bucket_id="b1", actividad_id="A1", year=2025)


class TestMovementAdd:
    def test_movement_add_appends_to_existing_ledger(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        svc.movement_add(
            bucket_id="b1", actividad_id="A1", year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-001",
                movement_date=date(2025, 3, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("5"),
                unit_cost=Decimal("100.00"),
            ),
        )
        ledger = svc.movement_add(
            bucket_id="b1", actividad_id="A1", year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-002",
                movement_date=date(2025, 3, 15),
                kind=MovementKind.COGS,
                quantity=Decimal("2"),
                unit_cost=Decimal("100.00"),
            ),
        )
        assert len(ledger.period_movements) == 2
        ids = [m.movement_id for m in ledger.period_movements]
        assert ids == ["M-001", "M-002"]

    def test_movement_add_refuses_duplicate_movement_id(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        cmd = InventoryMovementCommand(
            movement_id="DUP",
            movement_date=date(2025, 3, 1),
            kind=MovementKind.PURCHASE,
            quantity=Decimal("1"),
            unit_cost=Decimal("100.00"),
        )
        svc.movement_add(bucket_id="b1", actividad_id="A1", year=2025, movement=cmd)
        with pytest.raises(InventoryServiceInputError, match="already present"):
            svc.movement_add(bucket_id="b1", actividad_id="A1", year=2025, movement=cmd)

    def test_movement_add_refuses_when_actividad_missing(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        cmd = InventoryMovementCommand(
            movement_id="M-001",
            movement_date=date(2025, 3, 1),
            kind=MovementKind.PURCHASE,
            quantity=Decimal("1"),
            unit_cost=Decimal("100.00"),
        )
        with pytest.raises(InventoryActividadNotFoundError):
            svc.movement_add(bucket_id="b1", actividad_id="A1", year=2025, movement=cmd)


class TestValuationPreview:
    def test_valuation_preview_runs_domain_engine(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(
            bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo",
            opening_stock=Decimal("0"),
        )
        # Single purchase of 10 units at 50 EUR; no COGS -> closing 500, cogs 0
        svc.movement_add(
            bucket_id="b1", actividad_id="A1", year=2025,
            movement=InventoryMovementCommand(
                movement_id="P1",
                movement_date=date(2025, 1, 10),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("10"),
                unit_cost=Decimal("50.00"),
            ),
        )
        preview = svc.valuation_preview(bucket_id="b1", actividad_id="A1", year=2025)
        assert preview.valuation_method is ValuationMethod.FIFO
        assert preview.closing_stock == Decimal("500.00")
        assert preview.cogs == Decimal("0.00")


class TestRemove:
    def test_remove_deletes_ledger(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        removed = svc.remove(bucket_id="b1", actividad_id="A1", year=2025)
        assert removed.actividad_id == "A1"
        assert svc.list_all(bucket_id="b1") == ()
        with pytest.raises(InventoryActividadNotFoundError):
            svc.show(bucket_id="b1", actividad_id="A1", year=2025)

    def test_remove_refuses_on_missing_actividad(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        with pytest.raises(InventoryActividadNotFoundError):
            svc.remove(bucket_id="b1", actividad_id="A1", year=2025)


class TestBucketIsolation:
    def test_ledgers_are_bucket_scoped(self, isolated_settings: Settings) -> None:
        svc = InventoryService(settings=isolated_settings)
        svc.create(bucket_id="bucket-A", actividad_id="A1", year=2025, valuation_method="fifo")
        svc.create(bucket_id="bucket-B", actividad_id="A1", year=2025, valuation_method="pmp")
        a = svc.show(bucket_id="bucket-A", actividad_id="A1", year=2025)
        b = svc.show(bucket_id="bucket-B", actividad_id="A1", year=2025)
        assert a.valuation_method is ValuationMethod.FIFO
        assert b.valuation_method is ValuationMethod.PMP
