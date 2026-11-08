"""A withholding quarter with no retención settles the calculate operation as a refusal.

APP-QA's build e621263e8c settled modelo.work.calculate FAILED on
ERROR_FINANCIAL_AGGREGATION_VALIDATION twice from the retenciones resolver: a
quarter of the periodic work-withholding return with no retención recorded and
no attestation that none was paid. That is the person's to state, so submitted
as the window submits it, the production calculate definition under a real
supervisor settles REFUSED on the retenciones refusal's code, writes no
revision, and its served detail opens the profile answer that states it.

Real encrypted store, real published authority, real calculation engine. No doubles.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.errors import RetencionesWindowEmptyError
from cadrumo.application.calculations.m111_no_retenciones import M111_NO_RETENCIONES_PROFILE_PATH
from cadrumo.application.modelo.calculation_operation import (
    build_modelo_work_calculate_definition,
    build_modelo_work_calculate_registration,
)
from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculateRequest
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.operations.error_detail import OperationErrorDetailKind
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.next_step import OperationOpenProfileFieldStepV1
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.form_codes import form_for_role
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.tests.dependency_operation_gating_support import (
    settle_to_error_detail,
    supervisor_with_projections,
)
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET = "44444444-4444-4444-8444-444444440111"
_T0 = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def test_a_work_withholding_quarter_with_no_retencion_settles_refused_with_the_door_to_its_answer(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    modelo = form_for_role("withholding.work_periodic", authority=operation)
    year = _T0.year
    # An employer pays income subject to withholding, which makes the return apply to the profile.
    seed_ready_profile(
        bucket_id=_BUCKET, at=_T0, facts=(UserProfileFact(path="withholding.has_employees", value=True),)
    )
    work_units = WorkUnitCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    calculations = CalculationRevisionCatalogueRepository(objects=secure_objects)
    events = BucketEventHistoryRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot(modelo, filing_year=year, period="1T")
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo=modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, "1T"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=work_units, bucket_event_repository=events),
        clock=_T0,
        operation=operation,
    )

    with calculation_ports_for_test(
        bucket_id=_BUCKET,
        work_unit_repository=work_units,
        calculation_repository=calculations,
        bucket_event_repository=events,
    ) as ports:
        definition = build_modelo_work_calculate_definition(
            calculation_action_ports_factory=lambda **_composition: ports,
            attachment_store_factory=lambda _bucket_id: AttachmentStore(objects=secure_objects),
        )
        registration = build_modelo_work_calculate_registration(definition)
        supervisor, projections = supervisor_with_projections(
            tmp_path=tmp_path,
            profile_objects=secure_objects,
            authority_operation=operation,
            registry=OperationRegistry(definitions=(definition,), public_registrations=(registration,)),
        )
        receipt, detail = asyncio.run(
            settle_to_error_detail(
                supervisor,
                projections,
                OperationRequest[BaseModel](
                    definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                    subject_ref=work_unit.work_unit_id,
                    payload=ModeloWorkCalculateRequest(work_unit_id=work_unit.work_unit_id, actor="operator-A"),
                ),
                definition_contract_digest=registration.contract.definition_contract_digest,
            )
        )

    refusal = get_registered_error_code(RetencionesWindowEmptyError)
    assert receipt.condition is OperationTerminalCondition.REFUSED, receipt
    assert receipt.refusal_ref == refusal.code
    assert receipt.failure_error_code is None
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == refusal.code
    assert isinstance(detail.next_step, OperationOpenProfileFieldStepV1)
    assert detail.next_step.path == M111_NO_RETENCIONES_PROFILE_PATH
    assert not calculations.load(operation=operation).revisions
