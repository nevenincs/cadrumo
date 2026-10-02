"""Real encrypted-store expectations for modelo history and annual projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.bucket_event_projection import BucketEventProjection
from ...application.modelo.calculation_actions import calculate_modelo_revision
from ...application.modelo.history import assemble_modelo_lifecycle_history
from ...application.modelo.history_timeline_operation import (
    ModeloHistoryTimelineProjection,
    ModeloHistoryTimelineRequest,
    ModeloTimelineEvent,
)
from ...application.modelo.lifecycle_history_operation import (
    ModeloHistoryOperationProjection,
    ModeloHistoryOperationRequest,
)
from ...application.modelo.projection import compare_modelo_years, project_modelo_100_from_m130
from ...application.modelo.projection_operation import (
    ModeloCompareOperationProjection,
    ModeloCompareOperationRequest,
    ModeloProjectOperationProjection,
    ModeloProjectOperationRequest,
)
from ...application.modelo.work_lifecycle import create_work_unit
from ...core.operations import OperationEffect
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ...domain.user_profile.values import UserProfileFact
from ..adapter_composition import build_calculation_action_ports, build_modelo_history_ports, build_work_lifecycle_ports
from . import modelo_operation_test_support


@dataclass(frozen=True, slots=True)
class ModeloProjectionHistoryConformanceCase:
    """A real persisted source, typed request and independently calculated answer."""

    request: BaseModel
    expected_projection: BaseModel
    expected_effect: OperationEffect
    expected_phase_codes: tuple[str, ...]


def _seed_2026_revision(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> None:
    bucket_id = str(profile_id)
    revision = resolved_revision(modelo="130", filing_year=2026, period="1T")
    unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=revision.id,
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        operation=operation,
    )
    with bundled_indexed_authority().operation() as calculation_operation:
        calculate_modelo_revision(
            unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=bucket_id, operation=calculation_operation),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            casilla_inputs={},
            binding_values=modelo_operation_test_support.FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        )


def prepare_modelo_projection_history_conformance_case(
    definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ModeloProjectionHistoryConformanceCase:
    """Seed canonical work/calculation doors; derive expected rows outside the executor."""
    bucket_id = str(profile_id)
    modelo_operation_test_support.seeded_modelo_calculation_revision(profile_id, operation=operation)
    if definition_id in {"modelo.history", "modelo.history.timeline"}:
        history = assemble_modelo_lifecycle_history(
            "130",
            filing_year=2025,
            period="1T",
            ports=build_modelo_history_ports(bucket_id=bucket_id, operation=operation),
        )
        assert len(history.events) >= 2
        if definition_id == "modelo.history.timeline":
            return ModeloProjectionHistoryConformanceCase(
                request=ModeloHistoryTimelineRequest(profile_id=profile_id, modelo="130", year=2025, period="1T"),
                expected_projection=ModeloHistoryTimelineProjection(
                    profile_id=profile_id,
                    modelo=str(history.modelo),
                    year=history.filing_year,
                    period=history.period,
                    count=len(history.events),
                    events=tuple(ModeloTimelineEvent.from_event(event) for event in history.events),
                ),
                expected_effect=OperationEffect.NONE,
                expected_phase_codes=("modelo.history.timeline",),
            )
        return ModeloProjectionHistoryConformanceCase(
            request=ModeloHistoryOperationRequest(profile_id=profile_id, modelo="130", year=2025, period="1T"),
            expected_projection=ModeloHistoryOperationProjection(
                profile_id=profile_id,
                modelo=str(history.modelo),
                year=history.filing_year,
                period=history.period,
                count=len(history.events),
                events=tuple(BucketEventProjection.from_event(event) for event in history.events),
            ),
            expected_effect=OperationEffect.NONE,
            expected_phase_codes=("modelo.history",),
        )

    upsert_test_profile_facts(
        profile_id,
        (
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 1, 1)),
        ),
    )
    if definition_id == "modelo.project":
        expected = project_modelo_100_from_m130(
            year=2025,
            ccaa="madrid",
            bucket_id=bucket_id,
            ports=build_calculation_action_ports(bucket_id=bucket_id, operation=operation),
            operation=operation,
        )
        assert expected.quarters_filed == 1 and expected.quarters_available == ("1T",)
        return ModeloProjectionHistoryConformanceCase(
            request=ModeloProjectOperationRequest(profile_id=profile_id, year=2025, ccaa="madrid"),
            expected_projection=ModeloProjectOperationProjection.from_service(profile_id, expected),
            expected_effect=OperationEffect.NONE,
            expected_phase_codes=("modelo.project.prepare", "modelo.project.result"),
        )

    if definition_id != "modelo.compare":
        raise ValueError(f"unknown modelo projection/history operation: {definition_id}")
    _seed_2026_revision(profile_id, operation=operation)
    expected_compare = compare_modelo_years(
        modelo="130",
        years=(2025, 2026),
        ports=build_calculation_action_ports(bucket_id=bucket_id, operation=operation),
        operation=operation,
    )
    assert expected_compare.delta_rows and expected_compare.sections
    return ModeloProjectionHistoryConformanceCase(
        request=ModeloCompareOperationRequest(profile_id=profile_id, modelo="130", years=(2025, 2026)),
        expected_projection=ModeloCompareOperationProjection.from_service(profile_id, expected_compare),
        expected_effect=OperationEffect.NONE,
        expected_phase_codes=("modelo.compare.prepare", "modelo.compare.result"),
    )


__all__ = ["ModeloProjectionHistoryConformanceCase", "prepare_modelo_projection_history_conformance_case"]
