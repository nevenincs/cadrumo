"""Registered-executor conformance scenario for the maritime exemption preview."""

from __future__ import annotations

from ...adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ...application.modelo.maritime_preview_operation import (
    MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
    MaritimePreviewRetmarWarning,
    ModeloMaritimePreviewProjection,
    ModeloMaritimePreviewRequest,
)
from ...application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

# A RETMAR-registered sea worker on a Spanish-flagged vessel in national waters
# with no special register: neither Art. 7.p) LIRPF (foreign flag or
# international waters) nor REBECA (an eligible register) applies
# (domain/renta/maritime_exemption.py:114-134), and RETMAR registration makes
# the IRPF return mandatory (Ley 35/2006 art. 96; maritime_exemption.py:300).
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
        # Amounts are required only by an eligible pathway, so supplying them
        # here must not conjure an observation for this profile.
        request=ModeloMaritimePreviewRequest(
            profile_id=profile_id,
            annual_salary="42000.00",
            qualifying_days=200,
            gross_navigation_income="30000.00",
        ),
        expected_result=ModeloMaritimePreviewProjection(
            profile_id=profile_id,
            worker_class=_WORKER_CLASS,
            vessel_flag="ES",
            waters_type="national",
            vessel_registry=None,
            retmar_registered=True,
            # Read from the original facts, not the warning-path rerun (maritime_preview.py:78).
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
        # A pure read: one phase, then NONE before any service call (maritime_preview_operation.py:198-199).
        RegisteredExecutorConformanceCase(
            MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
