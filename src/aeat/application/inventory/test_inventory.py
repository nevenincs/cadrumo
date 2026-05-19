"""Tests for the inventory application service."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.application.inventory import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryMovementCommand,
    InventoryService,
    InventoryServiceInputError,
)
from aeat.core.config import Settings
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType
from aeat.domain.profile.inventory import MovementKind, ValuationMethod

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return Settings(aeat_ledgers_dir=tmp_path / "ledgers")


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
        )
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


def _make_svc(isolated_settings: Settings, engine: Engine) -> InventoryService:
    objects = SecureObjectRepository(engine=engine)
    return InventoryService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def _event_repo(engine: Engine) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=SecureObjectRepository(engine=engine))


class TestCreate:
    def test_create_persists_a_fresh_ledger(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        result = svc.create(
            bucket_id="bucket-001",
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("1000.00"),
        )
        ledger = result.ledger
        assert ledger.actividad_id == "A1"
        assert ledger.year == 2025
        assert ledger.valuation_method is ValuationMethod.FIFO
        assert ledger.opening_stock == Decimal("1000.00")
        assert ledger.period_movements == ()

    def test_create_refuses_duplicate_actividad_year(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        with pytest.raises(InventoryActividadConflictError):
            svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="pmp")

    def test_create_refuses_invalid_valuation_method(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        with pytest.raises(InventoryServiceInputError, match="invalid valuation_method"):
            svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="lifo")

    def test_create_persists_across_service_instances(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        _make_svc(isolated_settings, secure_engine).create(
            bucket_id="b1",
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
        )
        fresh = _make_svc(isolated_settings, secure_engine)
        ledgers = fresh.list_all(bucket_id="b1")
        assert len(ledgers) == 1
        assert ledgers[0].actividad_id == "A1"


class TestList:
    def test_list_empty_bucket_returns_empty_tuple(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        assert svc.list_all(bucket_id="b1") == ()

    def test_list_returns_one_summary_per_actividad_year(
        self, isolated_settings: Settings, secure_engine: Engine
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="b1", actividad_id="A1", year=2024, valuation_method="fifo")
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="pmp")
        svc.create(bucket_id="b1", actividad_id="A2", year=2025, valuation_method="fifo")
        summaries = svc.list_all(bucket_id="b1")
        assert len(summaries) == 3
        keys = {(s.actividad_id, s.year) for s in summaries}
        assert keys == {("A1", 2024), ("A1", 2025), ("A2", 2025)}


class TestShow:
    def test_show_returns_ledger_with_movements(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
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

    def test_show_refuses_on_missing_actividad(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        with pytest.raises(InventoryActividadNotFoundError):
            svc.show(bucket_id="b1", actividad_id="A1", year=2025)


class TestMovementAdd:
    def test_movement_add_appends_to_existing_ledger(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        svc.movement_add(
            bucket_id="b1",
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-001",
                movement_date=date(2025, 3, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("5"),
                unit_cost=Decimal("100.00"),
            ),
        )
        result = svc.movement_add(
            bucket_id="b1",
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-002",
                movement_date=date(2025, 3, 15),
                kind=MovementKind.COGS,
                quantity=Decimal("2"),
                unit_cost=Decimal("100.00"),
            ),
        )
        ledger = result.ledger
        assert len(ledger.period_movements) == 2
        ids = [m.movement_id for m in ledger.period_movements]
        assert ids == ["M-001", "M-002"]

    def test_movement_add_refuses_duplicate_movement_id(
        self, isolated_settings: Settings, secure_engine: Engine
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
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

    def test_movement_add_refuses_when_actividad_missing(
        self, isolated_settings: Settings, secure_engine: Engine
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
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
    def test_valuation_preview_runs_domain_engine(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(
            bucket_id="b1",
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("0"),
        )
        svc.movement_add(
            bucket_id="b1",
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="P1",
                movement_date=date(2025, 1, 10),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("10"),
                unit_cost=Decimal("50.00"),
            ),
        )
        result = svc.valuation_preview(bucket_id="b1", actividad_id="A1", year=2025)
        preview = result.preview
        assert preview.valuation_method is ValuationMethod.FIFO
        assert preview.closing_stock == Decimal("500.00")
        assert preview.cogs == Decimal("0.00")


class TestRemove:
    def test_remove_deletes_ledger(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.remove(bucket_id="b1", actividad_id="A1", year=2025)
        assert result.ledger.actividad_id == "A1"
        assert svc.list_all(bucket_id="b1") == ()
        with pytest.raises(InventoryActividadNotFoundError):
            svc.show(bucket_id="b1", actividad_id="A1", year=2025)

    def test_remove_refuses_on_missing_actividad(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        with pytest.raises(InventoryActividadNotFoundError):
            svc.remove(bucket_id="b1", actividad_id="A1", year=2025)


class TestInventoryEventEmission:
    """Verify each mutating verb emits the correct BucketEventType."""

    def test_create_emits_ledger_inventory_created(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        result = svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_CREATED
        assert event.bucket_id == "b1"
        assert "A1" in event.object_id

    def test_movement_add_emits_ledger_inventory_movement_added(
        self, isolated_settings: Settings, secure_engine: Engine
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.movement_add(
            bucket_id="b1",
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-001",
                movement_date=date(2025, 3, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("5"),
                unit_cost=Decimal("100.00"),
            ),
        )
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_MOVEMENT_ADDED

    def test_valuation_preview_emits_ledger_inventory_valuation_previewed(
        self, isolated_settings: Settings, secure_engine: Engine
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.valuation_preview(bucket_id="b1", actividad_id="A1", year=2025)
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_VALUATION_PREVIEWED

    def test_remove_emits_ledger_inventory_removed(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="b1", actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.remove(bucket_id="b1", actividad_id="A1", year=2025)
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_REMOVED


class TestBucketIsolation:
    def test_ledgers_are_bucket_scoped(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        svc.create(bucket_id="bucket-A", actividad_id="A1", year=2025, valuation_method="fifo")
        svc.create(bucket_id="bucket-B", actividad_id="A1", year=2025, valuation_method="pmp")
        a = svc.show(bucket_id="bucket-A", actividad_id="A1", year=2025)
        b = svc.show(bucket_id="bucket-B", actividad_id="A1", year=2025)
        assert a.valuation_method is ValuationMethod.FIFO
        assert b.valuation_method is ValuationMethod.PMP
