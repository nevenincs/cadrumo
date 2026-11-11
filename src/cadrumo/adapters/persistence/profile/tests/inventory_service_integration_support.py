"""Shared setup for the split test modules."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.application.inventory.ports import InventoryServicePorts
from cadrumo.application.inventory.service import InventoryService
from cadrumo.domain.filing_evidence import FilingEvidenceReference

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
)
from .....domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
)

if TYPE_CHECKING:
    from cadrumo.domain.contribuyente.inventory import closing_authority_records


_BUCKET_ID = "f2b75bc8-7925-49a1-9744-55c86dce3064"


BUCKET_A_ID = "b319db66-5926-4885-80db-2d3c9137b2e6"


BUCKET_B_ID = "f054bdb7-870f-40e6-b7c8-99d9a9c9d265"


OTHER_BUCKET_ID = "7add327e-476e-4abe-b306-a25d88026213"


secure_engine = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="secure_engine")


def make_svc(profile: TestRuntimeProfile) -> InventoryService:
    return InventoryService(
        ports=InventoryServicePorts(
            inventory_repository_factory=lambda bucket_id: InventoryLedgerRepository(
                objects=secure_object_repository_for_bucket(bucket_id, profile.settings),
            ),
            document_file_name=lambda _digest: None,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        ),
    )


def event_repo(profile: TestRuntimeProfile) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=profile.repository)


def acquisition(value: str) -> InventoryAcquisitionCost:
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


def authority_record(
    *, reason: str = "Reviewed movement-derived closing."
) -> closing_authority_records.InventoryClosingAuthorityRecord:
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


def physical_authority_record() -> closing_authority_records.InventoryClosingAuthorityRecord:
    from cadrumo.domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord

    base = authority_record()
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
