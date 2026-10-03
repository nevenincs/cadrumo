"""The wizard attempt has exact identity, historical scope, and result shapes."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.external_constants import OutputLanguage
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..calculation_action_ports import CalculationActionPortsFactory
from ..metadata_projection import ModeloWorkMetadataSnapshot
from ..operation_definitions import ModeloWorkCalculateRequest
from ..wizard_attempt_operation import (
    MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
    ModeloWorkWizardAttemptNeedsInput,
    ModeloWorkWizardAttemptProjection,
    ModeloWorkWizardAttemptRequest,
    build_modelo_work_wizard_attempt_definition,
    build_modelo_work_wizard_attempt_registration,
)
from ..work_lifecycle_ports import WorkLifecyclePorts
from ..work_wizard import ModeloWorkWizardStep
from .test_wizard_context_operation import _unit, _WorkRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _request(*, profile_id: UUID = _PROFILE, subject_ref: str | None = None) -> OperationRequest[BaseModel]:
    unit = _unit()
    return OperationRequest[BaseModel](
        definition_id=MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref or unit.work_unit_id,
        payload=ModeloWorkWizardAttemptRequest(
            profile_id=profile_id,
            output_language=OutputLanguage.CA,
            calculation=ModeloWorkCalculateRequest(work_unit_id=unit.work_unit_id, actor="operator"),
        ),
    )


def _registration(repository: _WorkRepository):
    def work_factory() -> WorkLifecyclePorts:
        return cast(WorkLifecyclePorts, cast(object, SimpleNamespace(work_unit_repository=repository)))

    definition = build_modelo_work_wizard_attempt_definition(
        calculation_action_ports_factory=cast(CalculationActionPortsFactory, cast(object, lambda **_kwargs: None)),
        attachment_store_factory=cast(Callable[[str], AttachmentStoreProtocol], lambda _bucket_id: None),
    )
    registration = build_modelo_work_wizard_attempt_registration(definition, work_factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration


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


def test_request_and_needs_input_projection_are_strictly_profile_bound() -> None:
    unit = _unit()
    request = _request()
    assert isinstance(request.payload, ModeloWorkWizardAttemptRequest)
    assert request.payload.calculation.work_unit_id == unit.work_unit_id
    with pytest.raises(ValidationError):
        ModeloWorkWizardAttemptRequest.model_validate(request.payload.model_dump() | {"output_language": "unknown"})

    step = ModeloWorkWizardStep(
        channel="binding",
        key="binding",
        casilla_id="casilla",
        number="1",
        label="Input",
        legal_refs=("legal-ref",),
        source_refs=("source-ref",),
    )
    unit_snapshot = ModeloWorkMetadataSnapshot.from_work_unit(unit)
    projection = ModeloWorkWizardAttemptProjection(
        profile_id=_PROFILE,
        output_language=OutputLanguage.CA,
        outcome=ModeloWorkWizardAttemptNeedsInput(unit=unit_snapshot, step=step),
    )
    assert ModeloWorkWizardAttemptProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        ModeloWorkWizardAttemptProjection.model_validate(projection.model_dump() | {"profile_id": _OTHER_PROFILE})
    with pytest.raises(ValidationError):
        ModeloWorkWizardAttemptProjection.model_validate(
            projection.model_dump() | {"outcome": {"kind": "unsupported", "unit": unit_snapshot, "step": step}}
        )
    for invalid_step in (
        step.model_copy(update={"channel": "relation"}),
        step.model_copy(update={"key": "INVALID BINDING"}),
        step.model_copy(update={"legal_refs": ()}),
        step.model_copy(update={"source_refs": ()}),
    ):
        with pytest.raises(ValidationError):
            ModeloWorkWizardAttemptNeedsInput(unit=unit_snapshot, step=invalid_step)


def test_exact_profile_rejected_before_work_catalogue_load() -> None:
    repository = _WorkRepository(_unit())
    registry, registration = _registration(repository)
    for request, profile_id in (
        (_request(profile_id=_OTHER_PROFILE), _PROFILE),
        (_request(), _OTHER_PROFILE),
        (_request(subject_ref="different-subject"), _PROFILE),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry, request=request, context=_context(registration, profile_id=profile_id)
            )
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert repository.loads == 0


def test_submit_period_and_historical_observation_result_commit_use_admitted_period() -> None:
    unit = _unit()
    repository = _WorkRepository(unit)
    registry, registration = _registration(repository)
    request = _request()
    resolved = resolve_operation_access(registry=registry, request=request, context=_context(registration))
    assert resolved.request.periods == frozenset({unit.period})
    assert repository.loads == 1
    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({unit.period}),
        period_independent=False,
        destination_id=uuid4(),
    )
    for action in (AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.COMMIT):
        historical = resolve_operation_access(
            registry=registry,
            request=request,
            context=_context(registration, action=action, admitted=admitted),
        )
        assert historical.request.periods == admitted.periods
    assert repository.loads == 1
