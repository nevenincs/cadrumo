"""Persistence-backed integration tests for the inventory application service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.inventory.errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from cadrumo.application.inventory.service import InventoryMovementCommand
from cadrumo.domain.buckets.event import BucketEventType

from .....domain.contribuyente.inventory.closing_foundations import (
    fingerprint_prior_authoritative_closing,
)
from .....domain.contribuyente.inventory.records import (
    MovementKind,
    ValuationMethod,
)
from .inventory_service_integration_support import (
    acquisition,
    authority_record,
    event_repo,
    make_svc,
    physical_authority_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


class TestCreate:
    def test_create_persists_a_fresh_ledger(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        result = svc.create(
            bucket_id=secure_engine.bucket_id,
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

    def test_create_refuses_duplicate_actividad_year(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        with pytest.raises(InventoryActividadConflictError) as exc_info:
            svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="pmp")
        assert exc_info.value.translated_message == "application.inventory.service.errors.activity_conflict"
        assert exc_info.value.context == {"actividad_id": "A1", "year": "2025"}

    def test_create_refuses_invalid_valuation_method(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        with pytest.raises(InventoryServiceInputError) as exc_info:
            svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="lifo")
        assert exc_info.value.translated_message == "application.inventory.service.errors.invalid_valuation_method"
        assert exc_info.value.context == {"valuation_method": "lifo"}

    def test_create_persists_across_service_instances(self, secure_engine: TestRuntimeProfile) -> None:
        make_svc(secure_engine).create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
        )
        fresh = make_svc(secure_engine)
        ledgers = fresh.list_all(bucket_id=secure_engine.bucket_id)
        assert len(ledgers) == 1
        assert ledgers[0].actividad_id == "A1"


class TestList:
    def test_list_empty_bucket_returns_empty_tuple(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        assert svc.list_all(bucket_id=secure_engine.bucket_id) == ()

    def test_list_returns_one_summary_per_actividad_year(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2024, valuation_method="fifo")
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="pmp")
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A2", year=2025, valuation_method="fifo")
        summaries = svc.list_all(bucket_id=secure_engine.bucket_id)
        assert len(summaries) == 3
        keys = {(s.actividad_id, s.year) for s in summaries}
        assert keys == {("A1", 2024), ("A1", 2025), ("A2", 2025)}


class TestShow:
    def test_show_returns_ledger_with_movements(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        svc.movement_add(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-001",
                movement_date=date(2025, 3, 15),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("10"),
                acquisition_cost=acquisition("500.00"),
            ),
        )
        ledger = svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert len(ledger.period_movements) == 1
        assert ledger.period_movements[0].movement_id == "M-001"

    def test_show_refuses_on_missing_actividad(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        with pytest.raises(InventoryActividadNotFoundError) as exc_info:
            svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert exc_info.value.translated_message == "application.inventory.service.errors.activity_not_found"
        assert exc_info.value.context == {"actividad_id": "A1", "year": "2025"}


class TestMovementAdd:
    def test_movement_add_appends_to_existing_ledger(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        svc.movement_add(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-001",
                movement_date=date(2025, 3, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("5"),
                acquisition_cost=acquisition("500.00"),
            ),
        )
        result = svc.movement_add(
            bucket_id=secure_engine.bucket_id,
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

    def test_movement_add_refuses_duplicate_movement_id(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        cmd = InventoryMovementCommand(
            movement_id="DUP",
            movement_date=date(2025, 3, 1),
            kind=MovementKind.PURCHASE,
            quantity=Decimal("1"),
            acquisition_cost=acquisition("100.00"),
        )
        svc.movement_add(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, movement=cmd)
        with pytest.raises(InventoryServiceInputError) as exc_info:
            svc.movement_add(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, movement=cmd)
        assert exc_info.value.translated_message == "application.inventory.service.errors.duplicate_movement_id"
        assert exc_info.value.context == {"movement_id": "DUP"}

    def test_movement_add_refuses_when_actividad_missing(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        cmd = InventoryMovementCommand(
            movement_id="M-001",
            movement_date=date(2025, 3, 1),
            kind=MovementKind.PURCHASE,
            quantity=Decimal("1"),
            acquisition_cost=acquisition("100.00"),
        )
        with pytest.raises(InventoryActividadNotFoundError):
            svc.movement_add(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, movement=cmd)

    def test_movement_add_refuses_invalid_negative_stock(self, secure_engine: TestRuntimeProfile) -> None:
        """The domain valuation guard runs in the service before persisting.

        A COGS movement that consumes more stock than the ledger holds must be
        refused by ``movement_add`` itself — the persistence adapter no longer
        runs the valuation calculation.
        """
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        svc.movement_add(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="BUY-1",
                movement_date=date(2025, 3, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("1"),
                acquisition_cost=acquisition("10.00"),
            ),
        )
        with pytest.raises(InventoryServiceInputError) as exc_info:
            svc.movement_add(
                bucket_id=secure_engine.bucket_id,
                actividad_id="A1",
                year=2025,
                movement=InventoryMovementCommand(
                    movement_id="SELL-TOO-MANY",
                    movement_date=date(2025, 3, 2),
                    kind=MovementKind.COGS,
                    quantity=Decimal("2"),
                ),
            )
        assert exc_info.value.translated_message == "application.inventory.service.errors.stock_would_go_negative"
        assert exc_info.value.context is not None
        assert exc_info.value.context["actividad_id"] == "A1"
        assert exc_info.value.context["sku"] == "default"
        assert [
            movement.movement_id
            for movement in svc.show(
                bucket_id=secure_engine.bucket_id,
                actividad_id="A1",
                year=2025,
            ).period_movements
        ] == ["BUY-1"]


class TestValuationPreview:
    def test_valuation_preview_runs_domain_engine(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("0"),
        )
        svc.movement_add(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="P1",
                movement_date=date(2025, 1, 10),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("10"),
                acquisition_cost=acquisition("500.00"),
            ),
        )
        result = svc.valuation_preview(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        preview = result.preview
        assert preview.valuation_method is ValuationMethod.FIFO
        assert preview.derived_closing_value == Decimal("500.00")
        assert preview.cogs == Decimal("0.00")


class TestClosingAuthorityRecord:
    def test_record_persists_and_exact_replay_is_idempotent(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("100.00"),
        )
        record = authority_record()
        first = svc.closing_authority_record(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            authority_record=record,
        )
        replay = svc.closing_authority_record(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            authority_record=record,
        )

        assert first.ledger.closing_authority_record == record
        assert replay.ledger.closing_authority_record == record
        assert (
            svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025).closing_authority_record == record
        )
        stored = InventoryLedgerRepository(objects=secure_engine.repository).load()
        assert stored.schema_version == "3"
        assert stored.ledgers[0].closing_authority_record == record

    def test_record_refuses_divergent_replay_without_overwrite(self, secure_engine: TestRuntimeProfile) -> None:
        from cadrumo.domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord

        svc = make_svc(secure_engine)
        svc.create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("100.00"),
        )
        original = authority_record()
        svc.closing_authority_record(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            authority_record=original,
        )

        with pytest.raises(InventoryServiceInputError, match="closing_authority"):
            svc.closing_authority_record(
                bucket_id=secure_engine.bucket_id,
                actividad_id="A1",
                year=2025,
                authority_record=authority_record(reason="A different reviewed decision."),
            )
        link = original.prior_closing_link
        changed_source = "d" * 64
        changed_link = link.model_copy(
            update={
                "prior_authoritative_source_fingerprint": changed_source,
                "prior_authoritative_closing_fingerprint": fingerprint_prior_authoritative_closing(
                    actividad_id=link.actividad_id,
                    filing_year=link.prior_filing_year,
                    authoritative_closing_value=link.prior_authoritative_closing_value,
                    authoritative_source_fingerprint=changed_source,
                    evidence=link.evidence,
                ),
            },
        )
        with pytest.raises(InventoryServiceInputError, match="closing_authority"):
            svc.closing_authority_record(
                bucket_id=secure_engine.bucket_id,
                actividad_id="A1",
                year=2025,
                authority_record=InventoryClosingAuthorityRecord(
                    decision=original.decision,
                    physical_observation=None,
                    prior_closing_link=changed_link,
                ),
            )
        with pytest.raises(InventoryServiceInputError, match="closing_authority"):
            svc.closing_authority_record(
                bucket_id=secure_engine.bucket_id,
                actividad_id="A1",
                year=2025,
                authority_record=physical_authority_record(),
            )
        assert (
            svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025).closing_authority_record
            == original
        )


class TestInventoryEventEmission:
    """Verify each mutating verb emits the correct BucketEventType."""

    def test_create_emits_ledger_inventory_created(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        result = svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        assert len(result.bucket_event_ids) == 1
        catalogue = event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_CREATED
        assert event.bucket_id == secure_engine.bucket_id
        assert "A1" in event.object_id

    def test_movement_add_emits_ledger_inventory_movement_added(self, secure_engine: TestRuntimeProfile) -> None:
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.movement_add(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            movement=InventoryMovementCommand(
                movement_id="M-001",
                movement_date=date(2025, 3, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("5"),
                acquisition_cost=acquisition("500.00"),
            ),
        )
        assert len(result.bucket_event_ids) == 1
        catalogue = event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_MOVEMENT_ADDED

    def test_valuation_preview_emits_ledger_inventory_valuation_previewed(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.valuation_preview(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert len(result.bucket_event_ids) == 1
        catalogue = event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_VALUATION_PREVIEWED
