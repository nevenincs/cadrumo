"""An unanswered IVA yes/no question refuses work creation with the door to that question.

A profile claiming the Modelo IVA block owes four yes/no enrolments that the
taxpayer projection will not guess. Left unanswered, ``modelo.work.create``
used to settle FAILED on ``ERROR_DEADLINES_PROFILE`` from inside that
projection. The answer is the person's to give, so the production create
definition under a real supervisor settles REFUSED on the profile-readiness
refusal with no effect, writes no work unit, logs no error, and its served
detail opens the unanswered question. The same profile with the question
answered creates the work.

Real encrypted store, real published authority, real supervisor. No doubles.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.tests.supervision_support import run_to_settlement
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import ModeloProfileReadinessError
from cadrumo.application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateRequest,
    build_modelo_work_create_definition,
    build_modelo_work_create_registration,
)
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.operations.error_detail import OperationErrorDetailKind
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.next_step import OperationOpenProfileFieldStepV1
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.form_codes import form_for_role
from cadrumo.domain.deadlines.profiles import MODELO_IVA_BLOCK_REQUIRED_PATHS
from cadrumo.domain.user_profile.values import ProfileSetupState, create_user_profile_record
from cadrumo.entrypoints.tests.dependency_operation_gating_support import (
    settle_to_error_detail,
    supervisor_with_projections,
)

from ....adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    replace_test_profile_record,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET = "44444444-4444-4444-8444-444444440126"
_T0 = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_UNANSWERED = "iva.redeme_enrolled"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _leave_unanswered(path: str, *, operation: PinnedAuthorityOperation) -> None:
    """Drop one answer from the stored complete profile, as a profile saved before it was asked."""
    record = load_test_profile_record(_BUCKET)
    assert any(fact.path == path for fact in record.facts)
    replace_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET,
            facts=tuple(fact for fact in record.facts if fact.path != path),
            created_at=record.created_at,
            updated_at=record.updated_at,
            context=operation.profile_create_context(),
        ),
    )


def _create_request(*, operation: PinnedAuthorityOperation) -> OperationRequest[BaseModel]:
    modelo = form_for_role("iva.periodic", authority=operation)
    filing_year = operation.supported_filing_years().horizon
    return OperationRequest[BaseModel](
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_BUCKET),
        payload=ModeloWorkCreateRequest(
            profile_id=UUID(_BUCKET),
            modelo=modelo,
            period=PublicPeriod(filing_year=filing_year, code="1T"),
            actor="operator-A",
        ),
    )


def _registry(secure_objects: SecureObjectRepository) -> tuple[OperationRegistry, str, WorkUnitCatalogueRepository]:
    work_units = WorkUnitCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    ports = WorkLifecyclePorts(
        work_unit_repository=work_units,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
    )
    definition = build_modelo_work_create_definition(lambda: ports)
    registration = build_modelo_work_create_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration.contract.definition_contract_digest, work_units


def test_an_unanswered_iva_question_settles_refused_with_the_door_to_that_question(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    assert _UNANSWERED in MODELO_IVA_BLOCK_REQUIRED_PATHS
    seed_ready_profile(bucket_id=_BUCKET, at=_T0)
    _leave_unanswered(_UNANSWERED, operation=operation)
    registry, digest, work_units = _registry(secure_objects)
    supervisor, projections = supervisor_with_projections(
        tmp_path=tmp_path, profile_objects=secure_objects, authority_operation=operation, registry=registry
    )

    with caplog.at_level(logging.ERROR):
        receipt, detail = asyncio.run(
            settle_to_error_detail(
                supervisor,
                projections,
                _create_request(operation=operation),
                definition_contract_digest=digest,
            )
        )

    refusal = get_registered_error_code(ModeloProfileReadinessError)
    assert refusal.code.startswith("REFUSED_")
    assert receipt.condition is OperationTerminalCondition.REFUSED, receipt
    assert receipt.refusal_ref == refusal.code
    assert receipt.failure_error_code is None
    assert receipt.effect is OperationEffect.NONE
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == refusal.code
    assert isinstance(detail.next_step, OperationOpenProfileFieldStepV1)
    assert detail.next_step.path == _UNANSWERED
    assert detail.next_step.words.strip()
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert not work_units.load().work_units


def test_the_answered_question_creates_the_work(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """ANTI-VACUITY: the same profile with every IVA question answered is not refused."""
    seed_ready_profile(bucket_id=_BUCKET, at=_T0)
    registry, _digest, work_units = _registry(secure_objects)
    supervisor, _projections = supervisor_with_projections(
        tmp_path=tmp_path, profile_objects=secure_objects, authority_operation=operation, registry=registry
    )

    async def settle() -> OperationTerminalCondition | None:
        operation_id = await supervisor.submit(_create_request(operation=operation), operation_id="4" * 64)
        terminal = await run_to_settlement(supervisor, operation_id)
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.effect is OperationEffect.UPDATED
        return terminal.terminal_receipt.condition

    assert asyncio.run(settle()) is OperationTerminalCondition.SUCCEEDED
    assert len(work_units.load().work_units) == 1
