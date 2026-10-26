"""Cross-period transport retains only typed, CLI-visible dependency facts."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ...calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyInventoryItem,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ...calculations.observations_repository import ObservationSourceKind
from ..dependency_projection import (
    DependencyCleanStateSnapshot,
    DependencyEvidenceSnapshot,
    DependencyInventoryItemSnapshot,
    DependencyRequirementSnapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _requirement() -> CrossPeriodDependencyRequirement:
    casilla = validated_casilla_id("71", surface="test casilla id")
    return CrossPeriodDependencyRequirement(
        source_modelo="303",
        filing_year=2026,
        period=_PERIOD,
        source_casilla_ids=(casilla,),
        required_source_casilla_ids=(casilla,),
        source_presence_groups=((casilla,),),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("modelo-303-compensacion-pendiente-anteriores",),
        legal_refs=("ley-37-1992:art-99",),
        source_refs=("aeat-iva-2025",),
        requires_member_fan_in=True,
    )


def _item() -> CrossPeriodDependencyInventoryItem:
    return CrossPeriodDependencyInventoryItem(
        target_modelo="303",
        target_revision_id="2026-y-siguientes",
        target_filing_year=2026,
        target_period=_PERIOD,
        dependencies=(_requirement(),),
    )


def _evidence(*, blockers: tuple[CrossPeriodCleanStateBlocker, ...] = ()) -> CrossPeriodDependencyEvidence:
    return CrossPeriodDependencyEvidence(
        requirement=_requirement(),
        observation_source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        filing_record_id="a" * 64,
        calculation_revision_id="b" * 64,
        external_evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        expected_member_nifs=("11111111H", "22222222J"),
        observed_member_nifs=("11111111H",),
        missing_member_nifs=("22222222J",),
        unexpected_member_nifs=(),
        blockers=blockers,
    )


def test_requirement_and_item_round_trip_through_canonical_invariants() -> None:
    requirement = _requirement()
    snapshot = DependencyRequirementSnapshot.from_requirement(requirement)
    assert snapshot.to_requirement() == requirement
    assert DependencyRequirementSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    item = _item()
    projected = DependencyInventoryItemSnapshot.from_item(item)
    assert projected.to_item() == item
    assert projected.dependency_count == 1 and projected.source_modelos == ("303",)
    assert DependencyInventoryItemSnapshot.model_validate_json(projected.model_dump_json()) == projected
    with pytest.raises(ValidationError, match="filing_year"):
        DependencyRequirementSnapshot.model_validate(snapshot.model_dump() | {"filing_year": 2025})
    with pytest.raises(ValidationError, match="derived fields"):
        DependencyInventoryItemSnapshot.model_validate(projected.model_dump() | {"source_modelos": ("130",)})


def test_evidence_keeps_member_nifs_and_rejects_fake_clean_or_identity() -> None:
    evidence = _evidence(blockers=(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE,))
    snapshot = DependencyEvidenceSnapshot.from_evidence(evidence)
    assert snapshot.expected_member_nifs == evidence.expected_member_nifs
    assert snapshot.observed_member_nifs == evidence.observed_member_nifs
    assert snapshot.missing_member_nifs == evidence.missing_member_nifs
    assert snapshot.blockers == evidence.blockers and not snapshot.clean
    assert DependencyEvidenceSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    with pytest.raises(ValidationError, match="clean state contradicts blockers"):
        DependencyEvidenceSnapshot.model_validate(snapshot.model_dump() | {"clean": True})
    with pytest.raises(ValidationError):
        DependencyEvidenceSnapshot.model_validate(snapshot.model_dump() | {"filing_record_id": "not-a-record"})
    with pytest.raises(ValidationError, match="period differs"):
        DependencyEvidenceSnapshot.model_validate(snapshot.model_dump() | {"filing_year": 2025})


def test_clean_state_uses_only_emitted_rows_and_aggregate_blockers() -> None:
    verdict = CrossPeriodCleanStateVerdict(
        bucket_id=str(_PROFILE),
        target_modelo="303",
        target_filing_year=2026,
        target_period=_PERIOD,
        dependencies=(
            _evidence(blockers=(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE,)),
            _evidence(blockers=(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE,)),
        ),
    )
    snapshot = DependencyCleanStateSnapshot.from_verdict(verdict)
    assert len(snapshot.dependencies) == 2
    assert snapshot.blockers == (CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE,)
    assert snapshot.requires_clean_state and not snapshot.clean
    assert "bucket_id" not in DependencyCleanStateSnapshot.model_fields
    assert "requirement" not in DependencyEvidenceSnapshot.model_fields
    assert DependencyCleanStateSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    with pytest.raises(ValidationError, match="contradicts its evidence rows"):
        DependencyCleanStateSnapshot.model_validate(snapshot.model_dump() | {"clean": True})
    with pytest.raises(ValidationError, match="target period differs"):
        DependencyCleanStateSnapshot.model_validate(snapshot.model_dump() | {"target_filing_year": 2025})
