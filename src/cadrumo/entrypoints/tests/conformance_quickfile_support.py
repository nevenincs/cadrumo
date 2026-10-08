"""Registered-executor conformance scenario for the local quickfile chain."""

from __future__ import annotations

from pathlib import Path

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo.quickfile import QUICKFILE_STAGE_ORDER, QuickfileStage, QuickfileStageStatus
from ...application.modelo.quickfile_operation import QUICKFILE_OPERATION_DEFINITION_ID
from ...application.modelo.quickfile_operation_contracts import (
    QuickfileRequest,
    QuickfileStageError,
    QuickfileStageSnapshot,
)
from ...application.modelo.quickfile_operation_projections import QuickfileProjection
from ...application.modelo.work_addressing import ModeloWorkRegistryYearMismatchError
from ...application.operations.public_period import PublicPeriod
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .modelo_operation_test_support import (
    MODELO,
    MODELO_FILING_YEAR,
    MODELO_OPERATION_TEST_ACTOR,
    MODELO_PERIOD,
    seeded_modelo_work_unit,
)

# A well-formed revision id the law never selects for any target. Quickfile
# refuses a revision assertion that diverges from the law-determined one before
# any stage writes (work_addressing.py:911).
_UNSELECTED_REVISION = "conformance-not-law-selected"


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id != QUICKFILE_OPERATION_DEFINITION_ID:
        raise AssertionError(f"no quickfile conformance scenario for {context.definition.definition_id}")
    profile_id = context.profile_id
    # A ready profile and an existing work unit for the exact target, so the
    # chain is stopped by the revision assertion alone, not by missing setup.
    seeded_modelo_work_unit(profile_id, operation=context.operation)
    units_before = WorkUnitCatalogueRepository().load()
    output_path = context.input_root / "quickfile-130.boe"
    period = Period.from_year_and_code(MODELO_FILING_YEAR, MODELO_PERIOD)
    refusal = get_registered_error_code(ModeloWorkRegistryYearMismatchError)

    def verify(outcome: ConformanceOutcome) -> None:
        del outcome
        assert WorkUnitCatalogueRepository().load() == units_before
        assert not Path(output_path).exists()

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=QuickfileRequest(
            profile_id=profile_id,
            modelo=MODELO,
            period=PublicPeriod.from_period(period),
            revision_id=_UNSELECTED_REVISION,
            output_path=str(output_path),
            actor=MODELO_OPERATION_TEST_ACTOR,
        ),
        expected_result=QuickfileProjection(
            profile_id=profile_id,
            modelo=MODELO,
            filing_year=MODELO_FILING_YEAR,
            period=PublicPeriod.from_period(period),
            # Readiness refused before a law revision was accepted (quickfile.py:386).
            registry_revision_id="",
            completed=False,
            stopped_at_stage=QuickfileStage.READINESS,
            readiness=None,
            work_unit_id=None,
            calculation_revision_id=None,
            verification_report=None,
            export=None,
            stages=(
                # A refusal stage carries only its registered code; this error
                # declares no recovery verdict (quickfile_operation_projections.py:209).
                QuickfileStageSnapshot(
                    stage=QuickfileStage.READINESS,
                    status=QuickfileStageStatus.REFUSED,
                    error=QuickfileStageError(code=refusal.code, message_key=refusal.message_key),
                ),
                *(
                    QuickfileStageSnapshot(stage=stage, status=QuickfileStageStatus.SKIPPED)
                    for stage in QUICKFILE_STAGE_ORDER[1:]
                ),
            ),
            write_count=0,
            effect=OperationEffect.NONE,
        ),
        verify=verify,
    )


QUICKFILE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # A stopped chain is result data, not a refusal; with no confirmed write
        # it settles NONE (quickfile_operation.py:182, :259, :109).
        RegisteredExecutorConformanceCase(
            QUICKFILE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (QUICKFILE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
