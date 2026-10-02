"""Authenticated Modelo work-wizard discovery and historical access scope."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..metadata_projection import ModeloWorkMetadataSnapshot
from ..wizard_context_operation import (
    MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
    ModeloWorkWizardContextExecutor,
    ModeloWorkWizardContextProjection,
    ModeloWorkWizardContextRequest,
    build_modelo_work_wizard_context_definition,
    build_modelo_work_wizard_context_registration,
)
from ..work_lifecycle_ports import WorkLifecyclePorts
from ..work_wizard import ModeloWorkWizardStep, discover_modelo_work_wizard_steps

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    instant = datetime(2026, 3, 10, 12, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=period, revision_id="2026-y-siguientes"
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="First-quarter return",
        created_at=instant,
        updated_at=instant,
        state=WorkUnitState.BORRADOR,
    )


def _request(unit: WorkUnit, *, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
        subject_ref=unit.work_unit_id,
        payload=ModeloWorkWizardContextRequest(
            profile_id=profile_id, work_unit_id=unit.work_unit_id, output_language=OutputLanguage.CA
        ),
    )


class _WorkRepository:
    def __init__(self, unit: WorkUnit, *, bucket_id: str = str(_PROFILE)) -> None:
        self.bucket_id = bucket_id
        self._unit = unit
        self.loads = 0

    def load(self) -> WorkUnitCatalogue:
        self.loads += 1
        return WorkUnitCatalogue(work_units={self._unit.work_unit_id: self._unit})


def _registration(repository: _WorkRepository):
    def factory() -> WorkLifecyclePorts:
        return cast(WorkLifecyclePorts, cast(object, SimpleNamespace(work_unit_repository=repository)))

    definition = build_modelo_work_wizard_context_definition(factory)
    registration = build_modelo_work_wizard_context_registration(definition, factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration, factory


def _context(
    registration,
    *,
    action: AccessAction = AccessAction.SUBMIT,
    profile_id: UUID = _PROFILE,
    admitted: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


def test_request_and_projection_bind_exact_profile_and_unique_step_identity() -> None:
    unit = _unit()
    request = _request(unit)
    assert isinstance(request.payload, ModeloWorkWizardContextRequest)
    assert request.subject_ref == request.payload.work_unit_id
    assert request.payload.output_language is OutputLanguage.CA
    with pytest.raises(ValidationError):
        ModeloWorkWizardContextRequest(profile_id=_PROFILE, work_unit_id="bad", output_language=OutputLanguage.CA)

    step = ModeloWorkWizardStep(
        channel="binding",
        key="synthetic.binding",
        casilla_id="synthetic.binding",
        number="synthetic.binding",
        label="Synthetic binding",
    )
    projection = ModeloWorkWizardContextProjection(
        profile_id=_PROFILE,
        unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
        output_language=OutputLanguage.CA,
        steps=(step,),
    )
    assert ModeloWorkWizardContextProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        ModeloWorkWizardContextProjection.model_validate(projection.model_dump() | {"profile_id": _OTHER_PROFILE})
    with pytest.raises(ValidationError):
        ModeloWorkWizardContextProjection.model_validate(projection.model_dump() | {"steps": (step, step)})


def test_profile_and_subject_mismatch_refuse_before_catalogue_load() -> None:
    unit = _unit()
    repository = _WorkRepository(unit)
    registry, registration, _ = _registration(repository)
    for request, profile_id in [
        (_request(unit, profile_id=_OTHER_PROFILE), _PROFILE),
        (_request(unit), _OTHER_PROFILE),
        (
            OperationRequest[BaseModel](
                definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
                subject_ref="different-subject",
                payload=_request(unit).payload,
            ),
            _PROFILE,
        ),
    ]:
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry, request=request, context=_context(registration, profile_id=profile_id)
            )
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert repository.loads == 0


def test_fresh_submit_uses_stored_period_and_rejects_wrong_repository_bucket() -> None:
    unit = _unit()
    repository = _WorkRepository(unit)
    registry, registration, _ = _registration(repository)
    resolved = resolve_operation_access(registry=registry, request=_request(unit), context=_context(registration))
    assert resolved.request.periods == frozenset({unit.period})
    assert not resolved.request.period_independent
    assert AccessAction.COMMIT not in resolved.policy.actions
    assert repository.loads == 1

    wrong_repository = _WorkRepository(unit, bucket_id=str(_OTHER_PROFILE))
    wrong_registry, wrong_registration, _ = _registration(wrong_repository)
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=wrong_registry, request=_request(unit), context=_context(wrong_registration))
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert wrong_repository.loads == 0


@pytest.mark.parametrize("action", [AccessAction.OBSERVE, AccessAction.RESULT])
def test_historical_read_uses_admitted_period_without_catalogue_reload(action: AccessAction) -> None:
    unit = _unit()
    repository = _WorkRepository(unit)
    registry, registration, _ = _registration(repository)
    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({unit.period}),
        period_independent=False,
        destination_id=uuid4(),
    )
    resolved = resolve_operation_access(
        registry=registry,
        request=_request(unit),
        context=_context(registration, action=action, admitted=admitted),
    )
    assert resolved.request.periods == admitted.periods
    assert resolved.policy.periods == admitted.periods
    assert repository.loads == 0


def test_executor_captures_canonical_steps_and_echoes_output_language(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _unit()
    repository = _WorkRepository(unit)
    _, _, factory = _registration(repository)
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Events:
        async def phase(self, _code: str) -> None:
            pass

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            stored.append(operand)
            return "f" * 64

    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
                    subject_ref=unit.work_unit_id,
                ),
                authority_operation=authority_operation,
                events=Events(),
                operands=Operands(),
            ),
        ),
    )
    request = OperationRequest[ModeloWorkWizardContextRequest](
        definition_id=MODELO_WORK_WIZARD_CONTEXT_OPERATION_DEFINITION_ID,
        subject_ref=unit.work_unit_id,
        payload=ModeloWorkWizardContextRequest(
            profile_id=_PROFILE, work_unit_id=unit.work_unit_id, output_language=OutputLanguage.CA
        ),
    )
    reference = asyncio.run(ModeloWorkWizardContextExecutor(factory).execute(request, context))

    assert reference == "f" * 64
    assert effects == [OperationEffect.NONE]
    assert repository.loads == 1
    assert len(stored) == 1
    result = ModeloWorkWizardContextProjection.model_validate(stored[0])
    assert result.profile_id == _PROFILE
    assert result.unit.work_unit_id == unit.work_unit_id
    assert result.output_language is OutputLanguage.CA
    with override_settings(cadrumo_output_language=OutputLanguage.CA.value):
        assert result.steps == discover_modelo_work_wizard_steps(unit, operation=authority_operation)
