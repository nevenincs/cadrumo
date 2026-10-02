"""Calculation advisories survive strict transport without losing domain facts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.application.aggregation.source_mesh import CalculationSourceDiagnostic
from cadrumo.application.modelo.calculate_input import (
    Modelo202ModalitySummary,
    ModeloWorkCalculationServiceResult,
)
from cadrumo.application.modelo.calculation_advisory_projection import (
    CalculationSourceDiagnosticSnapshot,
    ModeloCalculationAdvisories,
    ModeloWorkDeadlinePostureSnapshot,
)
from cadrumo.application.modelo.work_plazo import (
    ModeloWorkConditionalRecargoPreview,
    ModeloWorkDeadlinePosture,
)
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _diagnostic() -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind="profile",
        binding_source=BindingSourceKind.PROFILE,
        message="A declared source needs attention.",
        remedy="Review the profile fact before filing.",
        resolver_id="profile.source",
        source_ref="profile:fact",
        binding_id="profile.fact",
        relation_id="profile.relation",
        relation_ids=("profile.relation", "profile.other-relation"),
        casilla_id="05",
        legal_refs=("ley-58-2003:art-119",),
        source_refs=("aeat-modelo-130-instructions",),
        asserted_legal_refs=("ley-58-2003:art-120",),
        out_of_window_count=2,
        out_of_window_min_filing_date=date(2025, 1, 1),
        out_of_window_max_filing_date=date(2025, 3, 31),
    )


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(2025, "4T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="calculation-advisory-projection",
            modelo="130",
            filing_year=2025,
            period=period,
            revision_id="2019-y-siguientes",
        ),
        bucket_id="calculation-advisory-projection",
        modelo=ModeloCode("130"),
        filing_year=2025,
        period=period,
        revision_id="2019-y-siguientes",
        name="M130 2025 4T",
        created_at=datetime(2025, 12, 31, tzinfo=UTC),
        updated_at=datetime(2025, 12, 31, tzinfo=UTC),
    )


def _revision(work_unit: WorkUnit) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="130", revision_id="2019-y-siguientes", modelo_year=2025, period="4T"
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        created_at=datetime(2025, 12, 31, tzinfo=UTC),
        updated_at=datetime(2025, 12, 31, tzinfo=UTC),
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_diagnostic_all_fields_survive_json_and_domain_validation() -> None:
    original = _diagnostic()
    snapshot = CalculationSourceDiagnosticSnapshot.from_diagnostic(original)
    restored = CalculationSourceDiagnosticSnapshot.model_validate_json(snapshot.model_dump_json())

    assert restored.to_diagnostic() == original
    assert set(type(restored).model_fields) == set(type(original).model_fields)
    assert restored.relation_ids == ("profile.relation", "profile.other-relation")
    assert restored.asserted_legal_refs != restored.legal_refs


def test_malformed_diagnostic_is_refused_before_rendering() -> None:
    value = CalculationSourceDiagnosticSnapshot.from_diagnostic(_diagnostic()).model_dump(mode="json")
    value["out_of_window_max_filing_date"] = "2024-12-31"
    with pytest.raises(ValidationError):
        CalculationSourceDiagnosticSnapshot.model_validate(value)


def test_overdue_preview_roundtrip_preserves_unassessed_rate_facts() -> None:
    posture = ModeloWorkDeadlinePosture(
        closes_on=date(2025, 1, 31),
        days_overdue=31,
        conditional_recargo_preview=ModeloWorkConditionalRecargoPreview(
            band_id="recargo-band",
            surcharge_pct=Decimal("5.00"),
            interest_applies=False,
            legal_ref="ley-58-2003:art-27",
            rate_reference_on=date(2025, 3, 3),
        ),
    )
    snapshot = ModeloWorkDeadlinePostureSnapshot.from_posture(posture)
    restored = ModeloWorkDeadlinePostureSnapshot.model_validate_json(snapshot.model_dump_json())

    assert restored.to_posture() == posture
    assert restored.conditional_recargo_preview is not None
    assert restored.conditional_recargo_preview.surcharge_pct == "5.00"


def test_preview_cannot_be_attached_to_in_time_posture() -> None:
    snapshot = ModeloWorkDeadlinePostureSnapshot.from_posture(
        ModeloWorkDeadlinePosture(closes_on=date(2025, 12, 31), days_overdue=1)
    )
    value = snapshot.model_dump(mode="json")
    value["days_remaining"], value["days_overdue"] = 1, None
    value["conditional_recargo_preview"] = {
        "band_id": "recargo-band",
        "surcharge_pct": "5",
        "interest_applies": False,
        "legal_ref": "ley-58-2003:art-27",
        "rate_reference_on": "2025-03-03",
        "assessment_status": "unassessed",
    }
    with pytest.raises(ValidationError):
        ModeloWorkDeadlinePostureSnapshot.model_validate(value)


def test_result_capture_preserves_diagnostics_and_modality_under_pinned_authority(
    operation: PinnedAuthorityOperation,
) -> None:
    unit = _work_unit()
    result = ModeloWorkCalculationServiceResult(
        revision=_revision(unit),
        work_unit=unit,
        revision_published=True,
        modality=Modelo202ModalitySummary(modality="art-40-2", reason="Registry-selected example."),
        source_diagnostics=(_diagnostic(),),
    )

    captured = ModeloCalculationAdvisories.from_result(result, operation=operation)
    restored = ModeloCalculationAdvisories.model_validate_json(captured.model_dump_json())

    assert restored.to_diagnostics() == result.source_diagnostics
    assert restored.to_modality() == result.modality
    assert restored.to_plazo_resolutions() == ()
    assert restored.to_deadline_posture() == captured.to_deadline_posture()
