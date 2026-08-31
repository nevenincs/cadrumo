"""Tests for the inventory application service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.inventory import InventoryLedgerRepository
from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.runtime_readiness import StorageRuntimeReadinessCode
from ....adapters.persistence.storage.secure_object_namespaces import PROFILE_INVENTORY_LEDGER_NAMESPACE
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....domain.buckets.event import BucketEventType
from ....domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryClosingAuthority,
    InventoryClosingAuthorityDecision,
    InventoryClosingAuthorityRecord,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    InventoryLedgerError,
    MovementKind,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorAuthoritativeClosingLink,
    PriorClosingContinuityEvidence,
    ValuationMethod,
    fingerprint_prior_authoritative_closing,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..errors import InventoryActividadConflictError, InventoryActividadNotFoundError, InventoryServiceInputError
from ..service import InventoryMovementCommand, InventoryService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "f2b75bc8-7925-49a1-9744-55c86dce3064"
_BUCKET_A_ID = "b319db66-5926-4885-80db-2d3c9137b2e6"
_BUCKET_B_ID = "f054bdb7-870f-40e6-b7c8-99d9a9c9d265"
_OTHER_BUCKET_ID = "7add327e-476e-4abe-b306-a25d88026213"

secure_engine = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="secure_engine")


def _make_svc(profile: TestRuntimeProfile) -> InventoryService:
    return InventoryService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
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


def _authority_record(*, reason: str = "Reviewed movement-derived closing.") -> InventoryClosingAuthorityRecord:
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


def _physical_authority_record() -> InventoryClosingAuthorityRecord:
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
        assert exc_info.value.translated_message == "application.inventory.service.errors.actividad_conflict"
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
        assert exc_info.value.translated_message == "application.inventory.service.errors.actividad_not_found"
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
        with pytest.raises(InventoryLedgerError, match="consume more stock"):
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


class TestRemove:
    def test_remove_deletes_ledger(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.remove(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert result.ledger.actividad_id == "A1"
        assert svc.list_all(bucket_id=secure_engine.bucket_id) == ()
        with pytest.raises(InventoryActividadNotFoundError):
            svc.show(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)

    def test_remove_refuses_on_missing_actividad(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        with pytest.raises(InventoryActividadNotFoundError) as exc_info:
            svc.remove(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert exc_info.value.translated_message == "application.inventory.service.errors.actividad_not_found"
        assert exc_info.value.context == {"actividad_id": "A1", "year": "2025"}


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

    def test_remove_emits_ledger_inventory_removed(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _make_svc(secure_engine)
        svc.create(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025, valuation_method="fifo")
        result = svc.remove(bucket_id=secure_engine.bucket_id, actividad_id="A1", year=2025)
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.LEDGER_INVENTORY_REMOVED


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
