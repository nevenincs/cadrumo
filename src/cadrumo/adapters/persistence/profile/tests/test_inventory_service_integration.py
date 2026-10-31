"""Persistence-backed integration tests for the inventory application service."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.storage.errors import StorageValidationError
from cadrumo.adapters.persistence.storage.runtime_readiness import StorageRuntimeReadinessCode
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.secure_object_namespaces import PROFILE_INVENTORY_LEDGER_NAMESPACE
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.domain.buckets.event import BucketEventType

from .....domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
    fingerprint_prior_closing_source,
)
from .....domain.contribuyente.inventory.closing_value_facts import (
    InventoryClosingValueFacts,
    InventoryPhysicalCountFacts,
)
from .....domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryCorrectionReason,
    InventoryHistoryKind,
    InventoryLedgerDescriptor,
    InventoryRetirementReason,
    MovementKind,
    ValuationMethod,
)
from .....domain.contribuyente.inventory.valuation import (
    compute_inventory_anexo_d_projection,
    derive_inventory_anexo_d_values,
)

if TYPE_CHECKING:
    from cadrumo.domain.contribuyente.inventory import closing_authority_records as _closing_types
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.inventory.errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from cadrumo.application.inventory.ports import InventoryServicePorts
from cadrumo.application.inventory.service import InventoryLedgerResult, InventoryMovementCommand, InventoryService
from cadrumo.core.time.clock import now
from cadrumo.domain.filing_evidence import FilingEvidenceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "f2b75bc8-7925-49a1-9744-55c86dce3064"
_BUCKET_A_ID = "b319db66-5926-4885-80db-2d3c9137b2e6"
_BUCKET_B_ID = "f054bdb7-870f-40e6-b7c8-99d9a9c9d265"
_OTHER_BUCKET_ID = "7add327e-476e-4abe-b306-a25d88026213"

secure_engine = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="secure_engine")


def _make_svc(profile: TestRuntimeProfile) -> InventoryService:
    return InventoryService(
        ports=InventoryServicePorts(
            inventory_repository_factory=lambda bucket_id: InventoryLedgerRepository(
                objects=secure_object_repository_for_bucket(bucket_id, profile.settings),
            ),
            document_file_name=lambda _digest: None,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        ),
    )


def _event_repo(profile: TestRuntimeProfile) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=profile.repository)


def _acquisition(value: str) -> InventoryAcquisitionCost:
    invoice = FilingEvidenceReference(reference="invoice-evidence")
    cost_review = FilingEvidenceReference(reference="cost-review-evidence")
    iva_review = FilingEvidenceReference(reference="iva-review-evidence")
    return InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal(value),
        consideration_iva_amount=Decimal("0.00"),
        consideration_deductible_iva_ratio=Decimal("1"),
        attributable_cost_components=(),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=invoice,
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=cost_review,
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="b" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=iva_review,
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="c" * 64,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=invoice,
            attributable_cost_review_evidence=cost_review,
            iva_recoverability_review_evidence=iva_review,
        ),
        directly_attributable_cost_total=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("0.00"),
        total_acquisition_cost=Decimal(value),
    )


def _authority_record(
    *, reason: str = "Reviewed movement-derived closing."
) -> _closing_types.InventoryClosingAuthorityRecord:
    from cadrumo.domain.contribuyente.inventory.closing_authority_records import (
        InventoryClosingAuthorityDecision,
        InventoryClosingAuthorityRecord,
        PriorAuthoritativeClosingLink,
    )

    continuity_evidence = (
        PriorClosingContinuityEvidence(
            reference=FilingEvidenceReference(reference="prior-closing-evidence"),
            content_digest="f" * 64,
        ),
    )
    return InventoryClosingAuthorityRecord(
        decision=InventoryClosingAuthorityDecision(
            decision_id="decision-2025",
            actividad_id="A1",
            filing_year=2025,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            reason=reason,
            actor="inventory-reviewer",
            source_command="inventory.closing.authority.decide",
            decided_at=datetime(2026, 1, 2, tzinfo=UTC),
            evidence=(
                InventoryClosingDecisionEvidence(
                    reference=FilingEvidenceReference(reference="decision-evidence"),
                    role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                    content_digest="e" * 64,
                ),
            ),
        ),
        prior_closing_link=PriorAuthoritativeClosingLink(
            actividad_id="A1",
            current_filing_year=2025,
            prior_filing_year=2024,
            prior_authoritative_closing_value=Decimal("100.00"),
            current_opening_value=Decimal("100.00"),
            prior_authoritative_source_fingerprint="c" * 64,
            prior_authoritative_closing_fingerprint=fingerprint_prior_authoritative_closing(
                actividad_id="A1",
                filing_year=2024,
                authoritative_closing_value=Decimal("100.00"),
                authoritative_source_fingerprint="c" * 64,
                evidence=continuity_evidence,
            ),
            evidence=continuity_evidence,
        ),
    )


def _physical_authority_record() -> _closing_types.InventoryClosingAuthorityRecord:
    from cadrumo.domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord

    base = _authority_record()
    observation = PhysicalClosingObservation(
        observation_id="physical-2025",
        observed_on=date(2026, 1, 1),
        as_of_date=date(2025, 12, 31),
        actividad_id="A1",
        filing_year=2025,
        closing_value=Decimal("101.00"),
        valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
        evidence=(
            PhysicalClosingEvidence(
                reference=FilingEvidenceReference(reference="physical-count-evidence"),
                role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                content_digest="a" * 64,
            ),
            PhysicalClosingEvidence(
                reference=FilingEvidenceReference(reference="physical-value-evidence"),
                role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
                content_digest="b" * 64,
            ),
        ),
    )
    return InventoryClosingAuthorityRecord(
        decision=base.decision.model_copy(
            update={
                "authority": InventoryClosingAuthority.PHYSICAL_OBSERVATION,
                "physical_observation_id": observation.observation_id,
                "physical_observation_fingerprint": observation.fingerprint,
            },
        ),
        physical_observation=observation,
        prior_closing_link=base.prior_closing_link,
    )


class TestCreate:
    def test_create_persists_a_fresh_ledger(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
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
        svc = _make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        with pytest.raises(InventoryActividadConflictError) as exc_info:
            svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="pmp")
        assert exc_info.value.translated_message == "application.inventory.service.errors.activity_conflict"
        assert exc_info.value.context == {"actividad_id": "A1", "year": "2025"}

    def test_create_refuses_invalid_valuation_method(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        with pytest.raises(InventoryServiceInputError) as exc_info:
            svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="lifo")
        assert exc_info.value.translated_message == "application.inventory.service.errors.invalid_valuation_method"
        assert exc_info.value.context == {"valuation_method": "lifo"}

    def test_create_persists_across_service_instances(self, secure_engine: TestRuntimeProfile) -> None:
        _make_svc(secure_engine).create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
        )
        fresh = _make_svc(secure_engine)
        ledgers = fresh.list_all(bucket_id=secure_engine.bucket_id)
        assert len(ledgers) == 1
        assert ledgers[0].actividad_id == "A1"


class TestList:
    def test_list_empty_bucket_returns_empty_tuple(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        assert svc.list_all(bucket_id=secure_engine.bucket_id) == ()

    def test_list_returns_one_summary_per_actividad_year(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2024, valuation_method="fifo")
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="pmp")
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A2", year=2025, valuation_method="fifo")
        summaries = svc.list_all(bucket_id=secure_engine.bucket_id)
        assert len(summaries) == 3
        keys = {(s.actividad_id, s.year) for s in summaries}
        assert keys == {("A1", 2024), ("A1", 2025), ("A2", 2025)}


class TestShow:
    def test_show_returns_ledger_with_movements(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
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
                acquisition_cost=_acquisition("500.00"),
            ),
        )
        ledger = svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert len(ledger.period_movements) == 1
        assert ledger.period_movements[0].movement_id == "M-001"

    def test_show_refuses_on_missing_actividad(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        with pytest.raises(InventoryActividadNotFoundError) as exc_info:
            svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert exc_info.value.translated_message == "application.inventory.service.errors.activity_not_found"
        assert exc_info.value.context == {"actividad_id": "A1", "year": "2025"}


class TestMovementAdd:
    def test_movement_add_appends_to_existing_ledger(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
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
                acquisition_cost=_acquisition("500.00"),
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
        svc = _make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        cmd = InventoryMovementCommand(
            movement_id="DUP",
            movement_date=date(2025, 3, 1),
            kind=MovementKind.PURCHASE,
            quantity=Decimal("1"),
            acquisition_cost=_acquisition("100.00"),
        )
        svc.movement_add(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, movement=cmd)
        with pytest.raises(InventoryServiceInputError) as exc_info:
            svc.movement_add(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, movement=cmd)
        assert exc_info.value.translated_message == "application.inventory.service.errors.duplicate_movement_id"
        assert exc_info.value.context == {"movement_id": "DUP"}

    def test_movement_add_refuses_when_actividad_missing(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        cmd = InventoryMovementCommand(
            movement_id="M-001",
            movement_date=date(2025, 3, 1),
            kind=MovementKind.PURCHASE,
            quantity=Decimal("1"),
            acquisition_cost=_acquisition("100.00"),
        )
        with pytest.raises(InventoryActividadNotFoundError):
            svc.movement_add(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, movement=cmd)

    def test_movement_add_refuses_invalid_negative_stock(self, secure_engine: TestRuntimeProfile) -> None:
        """The domain valuation guard runs in the service before persisting.

        A COGS movement that consumes more stock than the ledger holds must be
        refused by ``movement_add`` itself — the persistence adapter no longer
        runs the valuation calculation.
        """
        svc = _make_svc(secure_engine)
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
                acquisition_cost=_acquisition("10.00"),
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
        svc = _make_svc(secure_engine)
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
                acquisition_cost=_acquisition("500.00"),
            ),
        )
        result = svc.valuation_preview(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        preview = result.preview
        assert preview.valuation_method is ValuationMethod.FIFO
        assert preview.derived_closing_value == Decimal("500.00")
        assert preview.cogs == Decimal("0.00")


class TestClosingAuthorityRecord:
    def test_record_persists_and_exact_replay_is_idempotent(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        svc.create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("100.00"),
        )
        record = _authority_record()
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

        svc = _make_svc(secure_engine)
        svc.create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            opening_stock=Decimal("100.00"),
        )
        original = _authority_record()
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
                authority_record=_authority_record(reason="A different reviewed decision."),
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
                authority_record=_physical_authority_record(),
            )
        assert (
            svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025).closing_authority_record
            == original
        )


class TestInventoryEventEmission:
    """Verify each mutating verb emits the correct BucketEventType."""

    def test_create_emits_ledger_inventory_created(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        result = svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_CREATED
        assert event.bucket_id == secure_engine.bucket_id
        assert "A1" in event.object_id

    def test_movement_add_emits_ledger_inventory_movement_added(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
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
                acquisition_cost=_acquisition("500.00"),
            ),
        )
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_MOVEMENT_ADDED

    def test_valuation_preview_emits_ledger_inventory_valuation_previewed(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.valuation_preview(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_VALUATION_PREVIEWED


def _purchase(movement_id: str, *, month: int, quantity: str, total: str) -> InventoryMovementCommand:
    return InventoryMovementCommand(
        movement_id=movement_id,
        movement_date=date(2025, month, 1),
        kind=MovementKind.PURCHASE,
        quantity=Decimal(quantity),
        acquisition_cost=_acquisition(total),
    )


def _sale(movement_id: str, *, month: int, quantity: str) -> InventoryMovementCommand:
    return InventoryMovementCommand(
        movement_id=movement_id,
        movement_date=date(2025, month, 1),
        kind=MovementKind.COGS,
        quantity=Decimal(quantity),
    )


def _seed_two_purchases_and_a_sale(svc: InventoryService, bucket_id: str, *, method: str) -> None:
    """10 units for 100.00, 10 units for 140.00, then 15 units sold."""
    svc.create(bucket_id=bucket_id, actividad_id="A1", year=2025, valuation_method=method)
    for movement in (
        _purchase("BUY-1", month=3, quantity="10", total="100.00"),
        _purchase("BUY-2", month=4, quantity="10", total="140.00"),
        _sale("SELL-1", month=5, quantity="15"),
    ):
        svc.movement_add(bucket_id=bucket_id, actividad_id="A1", year=2025, movement=movement)


class TestLedgerCorrections:
    """Hand-worked valuations through the real repository and valuation engine."""

    @pytest.mark.parametrize(
        ("method", "before", "after"),
        [
            # FIFO: 10 at 10.00 + 5 at 14.00 = 170.00 sold, 5 at 14.00 = 70.00 left.
            # At 160.00 the second layer is 16.00: 100.00 + 80.00 = 180.00 sold, 80.00 left.
            ("fifo", ("70.00", "170.00"), ("80.00", "180.00")),
            # Average: 240.00 / 20 = 12.00, 180.00 sold, 60.00 left.
            # At 160.00: 260.00 / 20 = 13.00, 195.00 sold, 65.00 left.
            ("pmp", ("60.00", "180.00"), ("65.00", "195.00")),
        ],
    )
    def test_a_corrected_movement_moves_both_valuations_and_keeps_the_original(
        self,
        secure_engine: TestRuntimeProfile,
        method: str,
        before: tuple[str, str],
        after: tuple[str, str],
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _seed_two_purchases_and_a_sale(svc, bucket, method=method)
        preview = svc.valuation_preview(bucket_id=bucket, actividad_id="A1", year=2025).preview
        assert (preview.derived_closing_value, preview.cogs) == (Decimal(before[0]), Decimal(before[1]))

        result = svc.movement_correct(
            bucket_id=bucket,
            actividad_id="A1",
            year=2025,
            correction_id="fix-1",
            target_movement_id="BUY-2",
            replacement=_purchase("BUY-2B", month=4, quantity="10", total="160.00"),
            reason=InventoryCorrectionReason.SOURCE_DOCUMENT_CORRECTED,
        )

        assert result.changed is True
        preview = svc.valuation_preview(bucket_id=bucket, actividad_id="A1", year=2025).preview
        assert (preview.derived_closing_value, preview.cogs) == (Decimal(after[0]), Decimal(after[1]))
        ledger = svc.show(bucket_id=bucket, actividad_id="A1", year=2025)
        assert {item.movement_id for item in ledger.period_movements} == {"BUY-1", "BUY-2B", "SELL-1"}
        (entry,) = ledger.history
        assert entry.kind is InventoryHistoryKind.MOVEMENT_CORRECTED
        assert entry.superseded_movement is not None
        assert entry.superseded_movement.movement_id == "BUY-2"
        assert entry.superseded_movement.capitalized_value == Decimal("140.00")
        assert entry.replacement_movement_id == "BUY-2B"
        event = _event_repo(secure_engine).load().events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_MOVEMENT_CORRECTED

    def test_a_reversal_leaves_the_effective_set_and_keeps_history(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _seed_two_purchases_and_a_sale(svc, bucket, method="fifo")

        svc.movement_reverse(
            bucket_id=bucket,
            actividad_id="A1",
            year=2025,
            correction_id="undo-sale",
            target_movement_id="SELL-1",
            reason=InventoryCorrectionReason.OPERATION_DID_NOT_OCCUR,
        )

        preview = svc.valuation_preview(bucket_id=bucket, actividad_id="A1", year=2025).preview
        assert (preview.derived_closing_value, preview.cogs) == (Decimal("240.00"), Decimal("0.00"))
        ledger = svc.show(bucket_id=bucket, actividad_id="A1", year=2025)
        assert ledger.known_movement_ids == {"BUY-1", "BUY-2", "SELL-1"}
        assert [item.movement_id for item in ledger.period_movements] == ["BUY-1", "BUY-2"]

    def test_a_reversal_that_would_take_stock_negative_refuses_and_changes_nothing(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _seed_two_purchases_and_a_sale(svc, bucket, method="fifo")
        before = svc.show(bucket_id=bucket, actividad_id="A1", year=2025)

        with pytest.raises(InventoryServiceInputError) as refused:
            svc.movement_reverse(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="undo-buy",
                target_movement_id="BUY-2",
                reason=InventoryCorrectionReason.DUPLICATE_ENTRY,
            )

        assert refused.value.translated_message == "application.inventory.service.errors.stock_would_go_negative"
        assert svc.show(bucket_id=bucket, actividad_id="A1", year=2025) == before

    def test_an_exact_replay_changes_nothing_and_another_request_under_the_id_refuses(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _seed_two_purchases_and_a_sale(svc, bucket, method="fifo")

        def reverse(target_movement_id: str) -> InventoryLedgerResult:
            return svc.movement_reverse(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="undo-sale",
                target_movement_id=target_movement_id,
                reason=InventoryCorrectionReason.OPERATION_DID_NOT_OCCUR,
            )

        first = reverse("SELL-1")
        replay = reverse("SELL-1")

        assert first.changed is True and len(first.bucket_event_ids) == 1
        assert replay.changed is False and replay.bucket_event_ids == ()
        assert replay.ledger == first.ledger

        with pytest.raises(InventoryServiceInputError) as refused:
            reverse("BUY-1")
        assert refused.value.translated_message == "application.inventory.service.errors.correction_id_conflict"

    def test_a_superseded_movement_can_be_neither_rectified_nor_reissued(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _seed_two_purchases_and_a_sale(svc, bucket, method="fifo")
        svc.movement_reverse(
            bucket_id=bucket,
            actividad_id="A1",
            year=2025,
            correction_id="undo-sale",
            target_movement_id="SELL-1",
            reason=InventoryCorrectionReason.OPERATION_DID_NOT_OCCUR,
        )

        with pytest.raises(InventoryServiceInputError) as again:
            svc.movement_reverse(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="undo-sale-2",
                target_movement_id="SELL-1",
                reason=InventoryCorrectionReason.OPERATION_DID_NOT_OCCUR,
            )
        assert again.value.translated_message == "application.inventory.service.errors.movement_already_superseded"
        with pytest.raises(InventoryServiceInputError) as reissued:
            svc.movement_add(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                movement=_sale("SELL-1", month=6, quantity="1"),
            )
        assert reissued.value.translated_message == "application.inventory.service.errors.duplicate_movement_id"
        with pytest.raises(InventoryServiceInputError) as absent:
            svc.movement_reverse(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="undo-ghost",
                target_movement_id="GHOST",
                reason=InventoryCorrectionReason.KEYING_ERROR,
            )
        assert absent.value.translated_message == "application.inventory.service.errors.movement_not_found"

    def test_a_replacement_dated_outside_the_ledger_year_refuses(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _seed_two_purchases_and_a_sale(svc, bucket, method="fifo")
        with pytest.raises(InventoryServiceInputError) as refused:
            svc.movement_correct(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="wrong-year",
                target_movement_id="BUY-1",
                replacement=InventoryMovementCommand(
                    movement_id="BUY-1B",
                    movement_date=date(2024, 12, 31),
                    kind=MovementKind.PURCHASE,
                    quantity=Decimal("10"),
                    acquisition_cost=_acquisition("100.00"),
                ),
                reason=InventoryCorrectionReason.KEYING_ERROR,
            )
        assert refused.value.translated_message == "application.inventory.service.errors.movement_outside_year"

    def test_opening_and_method_corrections_keep_what_they_displace(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        svc.create(
            bucket_id=bucket, actividad_id="A1", year=2025, valuation_method="fifo", opening_stock=Decimal("100.00")
        )

        result = svc.correct_opening(
            bucket_id=bucket,
            actividad_id="A1",
            year=2025,
            correction_id="open-1",
            reason=InventoryCorrectionReason.KEYING_ERROR,
            opening_stock=Decimal("120.00"),
            valuation_method=ValuationMethod.PMP,
        )

        assert result.ledger.opening_stock == Decimal("120.00")
        assert result.ledger.valuation_method is ValuationMethod.PMP
        (entry,) = result.ledger.history
        assert entry.prior_opening_stock == Decimal("100.00")
        assert entry.prior_valuation_method is ValuationMethod.FIFO
        with pytest.raises(InventoryServiceInputError) as unchanged:
            svc.correct_opening(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="open-2",
                reason=InventoryCorrectionReason.KEYING_ERROR,
                opening_stock=Decimal("120.00"),
                valuation_method=None,
            )
        assert unchanged.value.translated_message == "application.inventory.service.errors.correction_changes_nothing"

    def test_describing_never_moves_valuation_and_stays_open_after_a_closing_authority(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        svc.create(
            bucket_id=bucket, actividad_id="A1", year=2025, valuation_method="fifo", opening_stock=Decimal("100.00")
        )
        svc.closing_authority_record(
            bucket_id=bucket, actividad_id="A1", year=2025, authority_record=_authority_record()
        )

        first = svc.describe(
            bucket_id=bucket,
            actividad_id="A1",
            year=2025,
            correction_id="name-1",
            label="Hardware",
            description=None,
        )
        second = svc.describe(
            bucket_id=bucket,
            actividad_id="A1",
            year=2025,
            correction_id="name-2",
            label="Tools",
            description="Hand tools",
        )

        assert first.ledger.descriptor is not None
        assert second.ledger.descriptor == InventoryLedgerDescriptor(label="Tools", description="Hand tools")
        assert second.ledger.history[-1].prior_descriptor == first.ledger.descriptor
        preview = svc.valuation_preview(bucket_id=bucket, actividad_id="A1", year=2025).preview
        assert preview.derived_closing_value == Decimal("100.00")
        assert compute_inventory_anexo_d_projection(first.ledger).projection_fingerprint == (
            compute_inventory_anexo_d_projection(second.ledger).projection_fingerprint
        )

    def test_a_recorded_closing_authority_refuses_every_stock_change(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        svc.create(
            bucket_id=bucket, actividad_id="A1", year=2025, valuation_method="fifo", opening_stock=Decimal("100.00")
        )
        svc.closing_authority_record(
            bucket_id=bucket, actividad_id="A1", year=2025, authority_record=_authority_record()
        )
        key = "application.inventory.service.errors.closing_authority_recorded"

        with pytest.raises(InventoryServiceInputError) as opening:
            svc.correct_opening(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="open-1",
                reason=InventoryCorrectionReason.KEYING_ERROR,
                opening_stock=Decimal("1.00"),
                valuation_method=None,
            )
        assert opening.value.translated_message == key
        with pytest.raises(InventoryServiceInputError) as movement:
            svc.movement_add(
                bucket_id=bucket, actividad_id="A1", year=2025, movement=_sale("SELL-1", month=3, quantity="1")
            )
        assert movement.value.translated_message == key
        with pytest.raises(InventoryServiceInputError) as retire:
            svc.retire(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="out",
                reason=InventoryRetirementReason.CREATED_IN_ERROR,
            )
        assert retire.value.translated_message == key

    def test_a_later_years_closing_authority_refuses_a_change_to_the_year_it_rests_on(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        svc.create(bucket_id=bucket, actividad_id="A1", year=2024, valuation_method="fifo")
        svc.create(
            bucket_id=bucket, actividad_id="A1", year=2025, valuation_method="fifo", opening_stock=Decimal("100.00")
        )
        svc.closing_authority_record(
            bucket_id=bucket, actividad_id="A1", year=2025, authority_record=_authority_record()
        )

        with pytest.raises(InventoryServiceInputError) as refused:
            svc.correct_opening(
                bucket_id=bucket,
                actividad_id="A1",
                year=2024,
                correction_id="open-1",
                reason=InventoryCorrectionReason.KEYING_ERROR,
                opening_stock=Decimal("5.00"),
                valuation_method=None,
            )

        assert refused.value.translated_message == (
            "application.inventory.service.errors.later_closing_authority_recorded"
        )
        assert refused.value.context is not None
        assert refused.value.context["later_year"] == "2025"

    def test_retiring_keeps_every_fact_refuses_stock_changes_and_restoring_reopens(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _seed_two_purchases_and_a_sale(svc, bucket, method="fifo")

        retired = svc.retire(
            bucket_id=bucket,
            actividad_id="A1",
            year=2025,
            correction_id="out",
            reason=InventoryRetirementReason.ACTIVITY_CEASED,
        )

        assert retired.ledger.is_retired is True
        assert len(retired.ledger.period_movements) == 3
        (row,) = svc.list_all(bucket_id=bucket)
        assert row.retired is True and row.retirement_reason is InventoryRetirementReason.ACTIVITY_CEASED
        assert row.leaves_year_unresolved is True
        with pytest.raises(InventoryServiceInputError) as blocked:
            svc.movement_add(
                bucket_id=bucket, actividad_id="A1", year=2025, movement=_sale("SELL-2", month=6, quantity="1")
            )
        assert blocked.value.translated_message == "application.inventory.service.errors.inventory_retired"
        with pytest.raises(InventoryServiceInputError) as twice:
            svc.retire(
                bucket_id=bucket,
                actividad_id="A1",
                year=2025,
                correction_id="out-again",
                reason=InventoryRetirementReason.ACTIVITY_CEASED,
            )
        assert twice.value.translated_message == "application.inventory.service.errors.inventory_already_retired"

        restored = svc.restore(bucket_id=bucket, actividad_id="A1", year=2025, correction_id="back")
        assert restored.ledger.is_retired is False
        assert restored.ledger.retirement_reason is None
        svc.movement_add(
            bucket_id=bucket, actividad_id="A1", year=2025, movement=_sale("SELL-2", month=6, quantity="1")
        )
        with pytest.raises(InventoryServiceInputError) as not_retired:
            svc.restore(bucket_id=bucket, actividad_id="A1", year=2025, correction_id="back-again")
        assert not_retired.value.translated_message == "application.inventory.service.errors.inventory_not_retired"

    def test_a_change_to_an_absent_inventory_refuses_as_not_found(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        with pytest.raises(InventoryActividadNotFoundError) as refused:
            svc.restore(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, correction_id="back")
        assert refused.value.translated_message == "application.inventory.service.errors.activity_not_found"
        assert refused.value.context == {"actividad_id": "A1", "year": "2025"}


class TestBucketIsolation:
    def test_requested_bucket_must_match_active_runtime(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)

        # The typed readiness code, not prose: the refusal is locale-neutral, so
        # a regex over its message matches a translation key and would pass on
        # any unrelated storage refusal just as readily.
        with pytest.raises(StorageValidationError) as raised:
            svc.list_all(bucket_id=_OTHER_BUCKET_ID)

        assert raised.value.translated_message == "errors.storage.runtime.not_ready"
        assert raised.value.context is not None
        assert raised.value.context["readiness_code"] in {
            StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH.value,
            StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET.value,
        }

    def test_ledgers_are_runtime_profile_scoped(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path / "profile-a", bucket_id=_BUCKET_A_ID) as bucket_a:
            svc_a = _make_svc(bucket_a)
            svc_a.create(bucket_id=bucket_a.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
            assert svc_a.show(bucket_id=bucket_a.bucket_id, actividad_id="A1", year=2025).valuation_method is (
                ValuationMethod.FIFO
            )

        with isolated_runtime_profile(tmp_path=tmp_path / "profile-b", bucket_id=_BUCKET_B_ID) as bucket_b:
            svc_b = _make_svc(bucket_b)
            assert svc_b.list_all(bucket_id=bucket_b.bucket_id) == ()
            svc_b.create(bucket_id=bucket_b.bucket_id, actividad_id="A1", year=2025, valuation_method="pmp")
            assert svc_b.show(bucket_id=bucket_b.bucket_id, actividad_id="A1", year=2025).valuation_method is (
                ValuationMethod.PMP
            )


class TestSecureStorage:
    def test_create_persists_inventory_document_as_secure_object(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        svc.create(
            bucket_id=secure_engine.bucket_id,
            actividad_id="SECURE-A1",
            year=2025,
            valuation_method="fifo",
        )

        record = secure_engine.repository.load(
            PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace,
            PROFILE_INVENTORY_LEDGER_NAMESPACE.require_default_object_key(),
            expected_class=PROFILE_INVENTORY_LEDGER_NAMESPACE.sensitivity,
            max_supported_version=PROFILE_INVENTORY_LEDGER_NAMESPACE.schema_version,
        )

        assert record is not None
        assert b"SECURE-A1" in record.payload


_CLOSING_SOURCE = "ledger.inventory.closing-value.record"


def _evidence_reference(name: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=name)


def _closing_decision_evidence() -> tuple[InventoryClosingDecisionEvidence, ...]:
    return (
        InventoryClosingDecisionEvidence(
            reference=_evidence_reference("reconciliation"),
            role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
            content_digest="e" * 64,
        ),
    )


def _closing_prior_evidence() -> tuple[PriorClosingContinuityEvidence, ...]:
    return (PriorClosingContinuityEvidence(reference=_evidence_reference("closing-2024"), content_digest="f" * 64),)


def _closing_facts(
    *,
    decision_id: str = "decision-1",
    year: int = 2025,
    authority: InventoryClosingAuthority = InventoryClosingAuthority.MOVEMENT_DERIVED,
    physical_count: InventoryPhysicalCountFacts | None = None,
    prior_evidence: tuple[PriorClosingContinuityEvidence, ...] | None = None,
) -> InventoryClosingValueFacts:
    return InventoryClosingValueFacts(
        decision_id=decision_id,
        actividad_id="A1",
        year=year,
        authority=authority,
        reason="Reviewed closing.",
        decision_evidence=_closing_decision_evidence(),
        physical_count=physical_count,
        prior_evidence=_closing_prior_evidence() if prior_evidence is None else prior_evidence,
    )


def _closing_count(value: str = "55.00") -> InventoryPhysicalCountFacts:
    return InventoryPhysicalCountFacts(
        observed_on=date(2026, 1, 2),
        closing_value=Decimal(value),
        valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
        evidence=(
            PhysicalClosingEvidence(
                reference=_evidence_reference("count-sheet"),
                role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                content_digest="a" * 64,
            ),
            PhysicalClosingEvidence(
                reference=_evidence_reference("price-sheet"),
                role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
                content_digest="b" * 64,
            ),
        ),
    )


def _closing_book(svc: InventoryService, bucket: str, *, year: int = 2025, opening: str = "0.00") -> None:
    svc.create(
        bucket_id=bucket,
        actividad_id="A1",
        year=year,
        valuation_method="fifo",
        opening_stock=Decimal(opening),
    )
    for movement in (
        InventoryMovementCommand(
            movement_id=f"BUY-{year}",
            movement_date=date(year, 3, 1),
            kind=MovementKind.PURCHASE,
            quantity=Decimal("10"),
            acquisition_cost=_acquisition("100.00"),
        ),
        InventoryMovementCommand(
            movement_id=f"SELL-{year}",
            movement_date=date(year, 5, 1),
            kind=MovementKind.COGS,
            quantity=Decimal("4"),
        ),
    ):
        svc.movement_add(bucket_id=bucket, actividad_id="A1", year=year, movement=movement)


def _closing_value(
    svc: InventoryService, bucket: str, facts: InventoryClosingValueFacts
) -> _closing_types.InventoryClosingAuthorityRecord:
    result = svc.closing_value_record(bucket_id=bucket, facts=facts, actor="runtime", source_command=_CLOSING_SOURCE)
    record = result.ledger.closing_authority_record
    assert record is not None
    return record


# A book opening at 0.00 buys 10 units for 100.00 and sells 4, so FIFO closes at 60.00.
class TestClosingValueFromPlainFacts:
    def test_a_movement_derived_closing_derives_every_fingerprint(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket)

        record = _closing_value(svc, bucket, _closing_facts())

        source = fingerprint_prior_closing_source(
            actividad_id="A1", filing_year=2024, evidence=_closing_prior_evidence()
        )
        link = record.prior_closing_link
        assert link.prior_authoritative_source_fingerprint == source
        assert link.prior_authoritative_closing_fingerprint == fingerprint_prior_authoritative_closing(
            actividad_id="A1",
            filing_year=2024,
            authoritative_closing_value=Decimal("0.00"),
            authoritative_source_fingerprint=source,
            evidence=_closing_prior_evidence(),
        )
        assert record.decision.source_command == _CLOSING_SOURCE
        assert record.decision.physical_observation_fingerprint is None
        ledger = svc.show(bucket_id=bucket, actividad_id="A1", year=2025)
        assert derive_inventory_anexo_d_values(ledger).authoritative_closing_value == Decimal("60.00")

    def test_a_count_is_bound_by_its_own_fingerprint_and_its_difference_retained(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket)

        record = _closing_value(
            svc,
            bucket,
            _closing_facts(authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION, physical_count=_closing_count()),
        )

        observation = record.physical_observation
        assert observation is not None
        assert observation.as_of_date == date(2025, 12, 31)
        assert record.decision.physical_observation_fingerprint == observation.fingerprint
        derivation = derive_inventory_anexo_d_values(svc.show(bucket_id=bucket, actividad_id="A1", year=2025))
        assert derivation.authoritative_closing_value == Decimal("55.00")
        assert derivation.movement_derived_closing_value == Decimal("60.00")
        assert derivation.issues == ("physical_closing_conflict",)

    def test_the_same_facts_are_an_exact_replay_and_other_facts_refuse(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket)

        first = svc.closing_value_record(
            bucket_id=bucket, facts=_closing_facts(), actor="runtime", source_command=_CLOSING_SOURCE
        )
        replay = svc.closing_value_record(
            bucket_id=bucket, facts=_closing_facts(), actor="runtime", source_command=_CLOSING_SOURCE
        )
        assert first.changed is True
        assert replay.changed is False

        with pytest.raises(InventoryServiceInputError) as refused:
            svc.closing_value_record(
                bucket_id=bucket,
                facts=_closing_facts(decision_id="other"),
                actor="runtime",
                source_command=_CLOSING_SOURCE,
            )
        assert refused.value.translated_message == "application.inventory.service.errors.closing_authority_conflict"

    def test_the_backend_stamps_the_decision_and_a_retry_keeps_the_stamp(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket)
        before = now()
        first = svc.closing_value_record(
            bucket_id=bucket, facts=_closing_facts(), actor="runtime", source_command=_CLOSING_SOURCE
        )
        after = now()
        replay = svc.closing_value_record(
            bucket_id=bucket, facts=_closing_facts(), actor="runtime", source_command=_CLOSING_SOURCE
        )

        assert first.changed is True
        assert replay.changed is False
        record = svc.show(bucket_id=bucket, actividad_id="A1", year=2025).closing_authority_record
        assert record is not None
        assert before <= record.decision.decided_at <= after

    def test_a_retry_with_other_details_still_conflicts_at_a_later_instant(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket)
        svc.closing_value_record(
            bucket_id=bucket, facts=_closing_facts(), actor="runtime", source_command=_CLOSING_SOURCE
        )

        with pytest.raises(InventoryServiceInputError) as refused:
            svc.closing_value_record(
                bucket_id=bucket,
                facts=replace(_closing_facts(), reason="Another reason."),
                actor="runtime",
                source_command=_CLOSING_SOURCE,
            )

        assert refused.value.translated_message == "application.inventory.service.errors.closing_authority_conflict"

    def test_a_copy_that_read_the_book_before_the_commit_replays_the_stored_stamp(
        self, secure_engine: TestRuntimeProfile, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket)
        repository = svc._repository_for(bucket)
        before_the_commit = repository.load()
        first = svc.closing_value_record(
            bucket_id=bucket, facts=_closing_facts(), actor="runtime", source_command=_CLOSING_SOURCE
        )
        assert first.ledger.closing_authority_record is not None
        real_load = type(repository).load
        reads: list[object] = []

        def stale_first_read(instance: object) -> object:
            reads.append(instance)
            return before_the_commit if len(reads) == 1 else real_load(instance)

        monkeypatch.setattr(type(repository), "load", stale_first_read)
        copy = svc.closing_value_record(
            bucket_id=bucket, facts=_closing_facts(), actor="runtime", source_command=_CLOSING_SOURCE
        )

        assert copy.changed is False
        assert copy.ledger.closing_authority_record is not None
        assert copy.ledger.closing_authority_record.fingerprint == first.ledger.closing_authority_record.fingerprint

    def test_a_closed_prior_book_needs_no_document_and_its_closing_must_be_the_opening(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket, year=2024)
        prior = _closing_value(svc, bucket, _closing_facts(year=2024))
        _closing_book(svc, bucket, year=2025, opening="60.00")

        record = _closing_value(svc, bucket, _closing_facts(prior_evidence=()))

        assert record.prior_closing_link.prior_authoritative_source_fingerprint == prior.fingerprint
        assert record.prior_closing_link.prior_authoritative_closing_value == Decimal("60.00")
        assert {item.reference.reference for item in record.prior_closing_link.evidence} == {"reconciliation"}

    def test_an_opening_that_differs_from_the_closed_prior_book_refuses(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket, year=2024)
        _closing_value(svc, bucket, _closing_facts(year=2024))
        _closing_book(svc, bucket, year=2025, opening="61.00")

        with pytest.raises(InventoryServiceInputError) as refused:
            _closing_value(svc, bucket, _closing_facts(prior_evidence=()))
        assert refused.value.translated_message == "application.inventory.service.errors.closing_authority_invalid"

    def test_an_opening_with_no_closed_prior_book_needs_a_document(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        bucket = secure_engine.bucket_id
        _closing_book(svc, bucket)

        with pytest.raises(InventoryServiceInputError) as refused:
            _closing_value(svc, bucket, _closing_facts(prior_evidence=()))
        assert refused.value.translated_message == "application.inventory.service.errors.prior_closing_document_needed"
        assert svc.show(bucket_id=bucket, actividad_id="A1", year=2025).closing_authority_record is None

    def test_a_missing_book_is_named(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)

        with pytest.raises(InventoryActividadNotFoundError):
            _closing_value(svc, secure_engine.bucket_id, _closing_facts())
