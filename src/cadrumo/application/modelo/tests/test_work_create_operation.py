"""Work creation binds a private request and terminal result to one profile period."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.modelos.work_unit import derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..metadata_projection import ModeloWorkMetadataSnapshot
from ..work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
    ModeloWorkCreateResult,
    ModeloWorkCreateSuccess,
    build_modelo_work_create_definition,
    build_modelo_work_create_registration,
    project_modelo_work_create_result,
)
from ..work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from .test_wizard_context_operation import _unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = PublicPeriod(filing_year=2026, code="1T")


def _request(*, profile_id: UUID = _PROFILE) -> OperationRequest[ModeloWorkCreateRequest]:
    return OperationRequest[ModeloWorkCreateRequest](
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloWorkCreateRequest(profile_id=profile_id, modelo="303", period=_PERIOD, actor="operator"),
    )


def _registration():
    factory = cast(ActiveWorkLifecyclePortsFactory, cast(object, lambda: None))
    definition = build_modelo_work_create_definition(factory)
    registration = build_modelo_work_create_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _context(registration, *, action: AccessAction = AccessAction.SUBMIT, admitted=None) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


def _receipt(condition: OperationTerminalCondition, effect: OperationEffect) -> OperationTerminalReceipt:
    identity = OperationIdentity(
        operation_id="a" * 64,
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    return OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=datetime(2026, 3, 10, tzinfo=UTC),
        result_ref="f" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
        if condition is OperationTerminalCondition.REFUSED
        else None,
        refusal_detail_ref="e" * 64 if condition is OperationTerminalCondition.REFUSED else None,
    )


def test_request_schema_and_exact_period_access() -> None:
    registry, registration = _registration()
    request = _request()
    resolved = resolve_operation_access(
        registry=registry,
        request=cast(OperationRequest[BaseModel], cast(object, request)),
        context=_context(registration),
    )
    assert resolved.request.periods == frozenset({Period.from_year_and_code(2026, "1T")})
    assert AccessAction.COMMIT in resolved.policy.actions
    assert not resolved.policy.allow_period_independent
    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=request.definition_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=resolved.request.periods,
        period_independent=False,
        destination_id=uuid4(),
    )
    for action in (AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.COMMIT):
        historical = resolve_operation_access(
            registry=registry,
            request=cast(OperationRequest[BaseModel], cast(object, request)),
            context=_context(registration, action=action, admitted=admitted),
        )
        assert historical.request.periods == admitted.periods
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=cast(OperationRequest[BaseModel], cast(object, _request(profile_id=_OTHER))),
            context=_context(registration),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    with pytest.raises(ValidationError):
        ModeloWorkCreateRequest(profile_id=_PROFILE, modelo="303x", period=_PERIOD, actor="operator")


def test_terminal_projector_distinguishes_success_reuse_rename_and_refusal() -> None:
    unit = ModeloWorkMetadataSnapshot.from_work_unit(_unit())
    for reused, name_applied, effect in (
        (False, None, OperationEffect.UPDATED),
        (True, None, OperationEffect.NONE),
        (True, unit.name, OperationEffect.UPDATED),
    ):
        private = ModeloWorkCreateResult(
            profile_id=_PROFILE,
            period=_PERIOD,
            outcome=ModeloWorkCreateSuccess(
                unit=unit,
                reused=reused,
                name_applied=name_applied,
                applicability_guard_bypassed=False,
                advisory_keys=(),
            ),
        )
        public = project_modelo_work_create_result(private, _receipt(OperationTerminalCondition.SUCCEEDED, effect))
        assert isinstance(public, ModeloWorkCreateProjection)
        assert type(public) is not type(private)
        assert public.outcome == private.outcome
        with pytest.raises(ValueError):
            project_modelo_work_create_result(
                private, _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.UNKNOWN)
            )
    refusal = ModeloWorkCreateResult(
        profile_id=_PROFILE,
        period=_PERIOD,
        outcome=ModeloWorkCreateRefusal(modelo="303", reason="taxpayer category excludes this form"),
    )
    projected = project_modelo_work_create_result(
        refusal, _receipt(OperationTerminalCondition.REFUSED, OperationEffect.NONE)
    )
    assert isinstance(projected, ModeloWorkCreateProjection) and projected.outcome == refusal.outcome
    with pytest.raises(ValueError):
        project_modelo_work_create_result(refusal, _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE))
    source_unit = _unit()
    foreign_unit = ModeloWorkMetadataSnapshot.from_work_unit(
        source_unit.model_copy(
            update={
                "bucket_id": str(_OTHER),
                "work_unit_id": derive_work_unit_id(
                    bucket_id=str(_OTHER),
                    modelo=source_unit.modelo,
                    filing_year=source_unit.filing_year,
                    period=source_unit.period,
                    revision_id=source_unit.revision_id,
                ),
            }
        )
    )
    with pytest.raises(ValidationError):
        ModeloWorkCreateProjection(
            profile_id=_PROFILE,
            period=_PERIOD,
            outcome=ModeloWorkCreateSuccess(
                unit=foreign_unit,
                reused=False,
                name_applied=None,
                applicability_guard_bypassed=False,
                advisory_keys=(),
            ),
        )
