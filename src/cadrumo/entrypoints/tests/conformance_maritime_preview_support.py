"""Registered-executor conformance scenario for the maritime exemption preview."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import (
    seed_modelo_ready_profile_record,
    seed_test_profile_record,
    upsert_test_profile_facts,
)
from ...application.modelo.calculation_request_fields import ModeloCalculationOverride
from ...application.modelo.maritime_preview_operation import (
    MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
    MaritimePreviewRetmarWarning,
    ModeloMaritimePreviewProjection,
    ModeloMaritimePreviewRequest,
)
from ...application.modelo.quickfile import QUICKFILE_STAGE_ORDER, QuickfileStage, QuickfileStageStatus
from ...application.modelo.quickfile_operation_contracts import QuickfileCalculationInputs, QuickfileRequest
from ...application.modelo.quickfile_operation_projections import QuickfileProjection
from ...application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ...application.operations.public_period import PublicPeriod
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_WORKER_CLASS = "trabajador_del_mar"
_MARITIME_FACTS = (
    UserProfileFact(path="maritime_worker.worker_class", value=_WORKER_CLASS),
    UserProfileFact(path="maritime_worker.vessel_flag", value="ES"),
    UserProfileFact(path="maritime_worker.waters_type", value="national"),
    UserProfileFact(path="maritime_worker.retmar_registered", value="true"),
)
_RETMAR_LEGAL_REF = "ley-35-2006:art-96"


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id != MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID:
        raise AssertionError(f"no maritime preview conformance scenario for {context.definition.definition_id}")
    profile_id = context.profile_id
    seeded_at = now()
    seed_test_profile_record(
        create_user_profile_record(
            context=context.operation.profile_create_context(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=str(profile_id),
            facts=(*MODELO_READY_PROFILE_FACTS, *_MARITIME_FACTS),
            created_at=seeded_at,
            updated_at=seeded_at,
        )
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=ModeloMaritimePreviewRequest(
            profile_id=profile_id, annual_salary="42000.00", qualifying_days=200, gross_navigation_income="30000.00"
        ),
        expected_result=ModeloMaritimePreviewProjection(
            profile_id=profile_id,
            worker_class=_WORKER_CLASS,
            vessel_flag="ES",
            waters_type="national",
            vessel_registry=None,
            retmar_registered=True,
            retmar_mandatory_filing=True,
            retmar_warning=MaritimePreviewRetmarWarning(
                code="ERROR_RENTA_PROFILE_COMPLETENESS_WARNING", legal_ref=_RETMAR_LEGAL_REF
            ),
            observations=(),
            casilla_values=(),
        ),
    )


MARITIME_PREVIEW_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)


def _retained_maritime_quickfile_prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    if context.definition.definition_id == "modelo.work.preview_maritime_exemption":
        upsert_test_profile_facts(
            profile,
            tuple(
                (
                    UserProfileFact(path=f"maritime_worker.{key}", value=value)
                    for key, value in (
                        ("worker_class", "trabajador_del_mar"),
                        ("vessel_flag", "foreign"),
                        ("waters_type", "international"),
                    )
                )
            ),
        )

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(ModeloMaritimePreviewProjection)
            assert result.profile_id == context.profile_id and result.worker_class == "trabajador_del_mar"
            assert result.vessel_flag == "foreign" and result.waters_type == "international"
            assert (
                not result.retmar_registered
                and (not result.retmar_mandatory_filing)
                and (result.retmar_warning is None)
            )
            assert len(result.observations) == len(result.casilla_values) == 1
            row = result.observations[0]
            assert Decimal(row.value) == Decimal("36500") * 100 / 365
            assert row.legal_refs == ("ley-35-2006:art-7",) and row.source_refs == ("boe-lirpf-statutory-facts",)
            assert result.casilla_values[0].casilla_id == row.casilla_id and Decimal(
                result.casilla_values[0].value
            ) == Decimal("10000")

        return ConformancePreparation(
            profile_operation_subject(profile),
            ModeloMaritimePreviewRequest(profile_id=context.profile_id, annual_salary="36500.00", qualifying_days=100),
            verify=verify,
        )
    seed_modelo_ready_profile_record(profile, clock=datetime(2026, 4, 1, tzinfo=UTC))
    output = context.input_root / "quickfile.fichero-boe"
    units = WorkUnitCatalogueRepository(bucket_id=profile)
    calculations = CalculationRevisionCatalogueRepository(bucket_id=profile)
    assert not units.load().work_units and (not calculations.load().revisions)

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(QuickfileProjection)
        assert result.profile_id == context.profile_id and result.modelo == "130" and (result.filing_year == 2025)
        assert not result.completed and result.stopped_at_stage is QuickfileStage.CALCULATE and (result.export is None)
        assert result.write_count > 0 and result.effect is OperationEffect.PARTIAL
        assert tuple(row.stage for row in result.stages) == QUICKFILE_STAGE_ORDER
        assert result.stages[0].status in {QuickfileStageStatus.OK, QuickfileStageStatus.WARNING}
        assert result.stages[1].status is QuickfileStageStatus.OK and result.stages[1].message == "created"
        rejected = result.stages[2]
        assert rejected.status is QuickfileStageStatus.REFUSED and rejected.error is not None
        assert rejected.error.code == "REFUSED_MODELO_CALCULATE_BINDING_INPUT"
        assert rejected.precondition_verdict is not None
        assert all(row.status is QuickfileStageStatus.SKIPPED for row in result.stages[3:])
        assert result.work_unit_id is not None and units.load().get(result.work_unit_id) is not None
        assert result.calculation_revision_id is None and (not calculations.load().revisions)
        assert result.verification_report is None and (not output.exists())

    return ConformancePreparation(
        profile_operation_subject(profile),
        QuickfileRequest(
            profile_id=context.profile_id,
            modelo="130",
            period=PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")),
            output_path=str(output),
            actor="conformance",
            inputs=QuickfileCalculationInputs(
                binding_overrides=(ModeloCalculationOverride(key="conformance.undeclared_binding", value="0"),)
            ),
        ),
        verify=verify,
    )


MARITIME_QUICKFILE_MATERIAL_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            "modelo.work.preview_maritime_exemption",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.work.preview_maritime_exemption",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.quickfile", OperationTerminalCondition.SUCCEEDED, OperationEffect.PARTIAL, ("modelo.quickfile",)
        ),
    ),
    prepare=_retained_maritime_quickfile_prepare,
)
