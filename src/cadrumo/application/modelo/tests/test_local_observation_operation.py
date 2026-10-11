"""Contract checks for registered local observation mutations."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ...calculations.observations_repository import ObservationSourceKind
from ...operations.access_resolution import OperationAccessContext
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import OperationRequest
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..calculation_action_ports import CalculationActionPortsFactory
from ..filing_record_view_operation import (
    ModeloFilingObservationLayerProjection,
    ModeloFilingObservationLayersProjection,
    ModeloFilingObservationOverrideProjection,
)
from ..local_observation_contracts import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationCasillaValue,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationRequest,
)
from ..local_observation_operation import (
    build_modelo_local_observation_definition,
    build_modelo_local_observation_registration,
    resolve_modelo_local_observation_access,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = PublicPeriod(filing_year=2026, code="1T")
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_MCP = OperationFrontendProjection.MCP
_CLI = OperationFrontendProjection.CLI


def _factory() -> CalculationActionPortsFactory:
    return cast(CalculationActionPortsFactory, cast(object, lambda **_kwargs: None))


def _definition_and_registration():
    definition = build_modelo_local_observation_definition(_factory())
    return definition, build_modelo_local_observation_registration(definition)


def _request(*, profile_id: UUID = _PROFILE) -> OperationRequest[ModeloLocalObservationMutationRequest]:
    payload = ModeloLocalObservationMutationRequest(
        profile_id=profile_id,
        action="clear",
        modelo="130",
        period=_PERIOD,
        actor=None,
        reason="remove local override",
    )
    return OperationRequest[ModeloLocalObservationMutationRequest](
        definition_id=MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=payload,
    )


def test_operation_secures_values_and_keeps_wire_decimals_as_text() -> None:
    definition, _registration = _definition_and_registration()

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert definition.capabilities.permitted_effects == frozenset(
        {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}
    )

    request_schema = ModeloLocalObservationMutationRequest.model_json_schema()
    projection_schema = ModeloLocalObservationMutationProjection.model_json_schema()
    for schema in (request_schema, projection_schema):
        row_schema = schema["$defs"]["ModeloLocalObservationCasillaValue"]
        assert row_schema["properties"]["value"]["type"] == "string"
        assert row_schema["properties"]["casilla_id"]["$ref"] == "#/$defs/CasillaId"
        assert schema["$defs"]["CasillaId"]["type"] == "string"


def test_request_requires_sorted_unique_values_and_action_specific_shape() -> None:
    value = ModeloLocalObservationCasillaValue(casilla_id="base_imponible", value="125.00")
    recorded = ModeloLocalObservationMutationRequest(
        profile_id=_PROFILE,
        action="record",
        modelo="130",
        period=_PERIOD,
        casilla_values=(value,),
        reason="operator estimate",
    )
    assert recorded.casilla_values == (value,)

    with pytest.raises(ValidationError):
        ModeloLocalObservationMutationRequest(
            profile_id=_PROFILE,
            action="record",
            modelo="130",
            period=_PERIOD,
            casilla_values=(value, value),
            reason="duplicate",
        )
    with pytest.raises(ValidationError):
        ModeloLocalObservationMutationRequest(
            profile_id=_PROFILE,
            action="clear",
            modelo="130",
            period=_PERIOD,
            casilla_values=(value,),
            reason="clear cannot carry values",
        )
    with pytest.raises(ValidationError):
        ModeloLocalObservationCasillaValue(casilla_id="base_imponible", value="125.000")


def test_access_is_bound_to_the_submitted_period_and_requires_commit() -> None:
    _definition, registration = _definition_and_registration()
    request = _request()
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_modelo_local_observation_access(
        cast(OperationRequest[BaseModel], cast(object, request)), context
    )

    assert resolved.request.periods == frozenset({_PERIOD.to_period()})
    assert not resolved.request.period_independent
    assert AccessAction.COMMIT in resolved.policy.actions

    wrong_profile = replace(context, profile_id=_OTHER_PROFILE)
    with pytest.raises(ProfileAccessRefusedError) as caught:
        resolve_modelo_local_observation_access(cast(OperationRequest[BaseModel], cast(object, request)), wrong_profile)
    assert caught.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_projection_keeps_the_canonical_record_and_its_persisted_layer_aligned() -> None:
    actor = f"profile:{_PROFILE}"
    casilla_values = (ModeloLocalObservationCasillaValue(casilla_id="base_imponible", value="125.00"),)
    pending = ModeloFilingObservationLayerProjection(
        source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        official_evidence=False,
        captured_at=_NOW,
        stamped_revision_id="revision-1",
        casilla_values=(("base_imponible", "125.00"),),
    )
    override = ModeloFilingObservationOverrideProjection(
        actor=actor,
        reason="operator estimate",
        recorded_at=_NOW,
        replaced_values=(),
    )
    layers = ModeloFilingObservationLayersProjection(
        modelo="130",
        filing_year=2026,
        period="1T",
        pending_local=pending,
        effective_source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        override=override,
    )

    projection = ModeloLocalObservationMutationProjection(
        profile_id=_PROFILE,
        action="recorded",
        modelo="130",
        period=_PERIOD,
        revision_id="revision-1",
        observation_key="130:2026:1T",
        source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        casilla_values=casilla_values,
        captured_at=_NOW,
        captured_by=actor,
        reason="operator estimate",
        observation_layers=layers,
    )

    wire = projection.model_dump(mode="json")
    assert wire["casilla_values"] == [{"casilla_id": "base_imponible", "value": "125.00"}]
    assert wire["official_evidence"] is False
    assert wire["filing_record_created"] is False
    assert wire["aeat_accepted"] is False


def _access_context(
    frontend: OperationFrontendProjection, *, action: AccessAction = AccessAction.SUBMIT
) -> OperationAccessContext:
    _definition, registration = _definition_and_registration()
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _record_request() -> OperationRequest[BaseModel]:
    payload = ModeloLocalObservationMutationRequest(
        profile_id=_PROFILE,
        action="record",
        modelo="130",
        period=_PERIOD,
        casilla_values=(ModeloLocalObservationCasillaValue(casilla_id="base_imponible", value="125.00"),),
        reason="operator estimate",
    )
    return OperationRequest[BaseModel](
        definition_id=MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def test_the_definition_is_open_to_the_command_line_and_to_mcp() -> None:
    definition, registration = _definition_and_registration()

    listed = frozenset({_CLI, _MCP})
    assert definition.permitted_frontends == listed
    assert registration.contract.permitted_frontends == listed


def test_an_mcp_session_is_admitted_to_record_exactly_as_the_command_line_is() -> None:
    """A recorded figure is never official evidence, so recording it states nothing only the person can."""
    on_mcp = resolve_modelo_local_observation_access(_record_request(), _access_context(_MCP))
    on_cli = resolve_modelo_local_observation_access(_record_request(), _access_context(_CLI))

    assert on_mcp.request.frontend is _MCP
    assert on_mcp.request.periods == on_cli.request.periods == frozenset({_PERIOD.to_period()})
    assert on_mcp.policy.actions == on_cli.policy.actions
    assert AccessAction.COMMIT in on_mcp.policy.actions
    assert not on_mcp.policy.requires_human


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.RESULT])
def test_clearing_a_figure_is_refused_to_mcp_at_every_access_and_to_no_other_frontend(action: AccessAction) -> None:
    """Clearing removes the figure and keeps no copy of it, so it waits for the person."""
    clear = cast(OperationRequest[BaseModel], cast(object, _request()))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_modelo_local_observation_access(clear, _access_context(_MCP, action=action))
    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED

    on_cli = resolve_modelo_local_observation_access(clear, _access_context(_CLI))
    assert on_cli.request.frontend is _CLI
    assert AccessAction.COMMIT in on_cli.policy.actions
