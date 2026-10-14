"""A local observation and a Modelo 145 draft do the same on every frontend, under the actor of the session.

The production registry and the real executors run over a stored profile with
a session host that answers for the frontend that admitted the invocation.
Recording an operator figure, recording over the observation of a pending
local filing, clearing a figure and drafting a payer communication, signed
blocks included, have the same effect and result whichever frontend submits
them. What an MCP session records carries its own session label.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ...adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.calculations.observations_repository import ObservationLayers, ObservationSourceKind
from ...application.modelo.local_observation_contracts import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationCasillaValue,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationRequest,
)
from ...application.modelo.m145_communication_contracts import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationCreateRequest,
    M145CommunicationOperationResult,
    M145CommunicationRecordProjection,
    M145CommunicationValidateRequest,
    M145CommunicationValidationProjection,
)
from ...application.modelo.m145_communication_period import M145CommunicationPeriod
from ...application.modelo.m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecordState,
    derive_m145_communication_record_id,
)
from ...application.operations.composition import OperationSubmission
from ...application.operations.execution_actor import OperationExecutionCaller
from ...application.operations.frontend_requests import OperationObservationSuccessV1
from ...application.operations.models import OperationIdentity
from ...application.operations.public_period import PublicPeriod
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.user_profile.access_contracts import SessionKind
from ...core.casilla_id import validated_casilla_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from . import modelo_operation_test_support
from . import registered_executor_case_support as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_TYPED_ACTOR = "typed by the caller"
_AGENT_LABEL = f"agent:mcp.attended.{_SESSION_CLIENT}"
_FRONTENDS = pytest.mark.parametrize(
    ("frontend", "recorded"),
    [(_MCP, _AGENT_LABEL), (_CLI, _TYPED_ACTOR), (_TUI, _TYPED_ACTOR)],
    ids=["mcp", "cli", "tui"],
)

_OBSERVATION = MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID
_MODELO = modelo_operation_test_support.MODELO
_PERIOD = Period.from_year_and_code(
    modelo_operation_test_support.MODELO_FILING_YEAR, modelo_operation_test_support.MODELO_PERIOD
)
_CASILLA = validated_casilla_id("19")
_STORED_AT = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
_OFFICIAL_METADATA = {"aeat_register_status": "ALTA", "aeat_expediente_id": "202513000000001Z"}

_M145_CREATE = M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID
_M145_VALIDATE = M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID
_M145_YEAR = 2026
_M145_PERIOD = M145CommunicationPeriod.COMMUNICATION
_WORKER = {
    "perceptor.nif": "12345678Z",
    "perceptor.primer-apellido": "Garcia",
    "perceptor.segundo-apellido": "Lopez",
    "perceptor.nombre": "Ana",
    "perceptor.anio-nacimiento": "1981",
}


class _SessionHost:
    """A session host that answers with the frontend one test admits its invocations on."""

    def __init__(self, frontend: OperationFrontendProjection) -> None:
        self.frontend = frontend

    def __call__(self, identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id in {_OBSERVATION, _M145_CREATE, _M145_VALIDATE}
        return OperationExecutionCaller(
            frontend=self.frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT
        )


def _run(
    driver: conformance._ExecutionDriver, definition_id: str, profile_id: UUID, payload: BaseModel
) -> tuple[OperationSubmission, OperationObservationSuccessV1]:
    submitted, observed = asyncio.run(
        driver.run(
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=payload,
        )
    )
    assert isinstance(submitted, OperationSubmission)
    assert isinstance(observed, OperationObservationSuccessV1)
    return submitted, observed


def _events(profile_id: UUID, event_type: BucketEventType) -> list[BucketEvent]:
    events = bucket_event_history_repository(bucket_id=str(profile_id)).load().events
    return [event for event in events.values() if event.event_type is event_type]


# ---------------------------------------------------------------------------
# The operator's local observation
# ---------------------------------------------------------------------------


def _observation_request(
    profile_id: UUID, *, value: str = "125.00", reason: str = "figure read from the paper copy"
) -> ModeloLocalObservationMutationRequest:
    return ModeloLocalObservationMutationRequest(
        profile_id=profile_id,
        action="record",
        modelo=_MODELO,
        period=PublicPeriod.from_period(_PERIOD),
        casilla_values=(ModeloLocalObservationCasillaValue(casilla_id=_CASILLA, value=value),),
        actor=_TYPED_ACTOR,
        reason=reason,
    )


def _clear_request(profile_id: UUID, *, reason: str) -> ModeloLocalObservationMutationRequest:
    return ModeloLocalObservationMutationRequest(
        profile_id=profile_id,
        action="clear",
        modelo=_MODELO,
        period=PublicPeriod.from_period(_PERIOD),
        actor=_TYPED_ACTOR,
        reason=reason,
    )


def _store_observation(profile_id: UUID, value: str, *, source_kind: ObservationSourceKind) -> None:
    """Place one stored observation in the layer its source kind selects, through the real repository."""
    revision = resolved_revision(modelo=_MODELO, filing_year=_PERIOD.filing_year, period=_PERIOD.registry_token)
    casilla = next(item for item in revision.casillas if item.id == _CASILLA)
    repository = CalculationObservationRepository(bucket_id=str(profile_id))
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=_MODELO,
                filing_year=_PERIOD.filing_year,
                period=_PERIOD.registry_token,
                observations=(
                    CasillaObservation(
                        casilla_id=_CASILLA,
                        value=Decimal(value),
                        legal_refs=casilla.legal_refs,
                        source_refs=casilla.source_refs,
                    ),
                ),
            ),
            source_kind=source_kind,
            captured_at=_STORED_AT,
            source_metadata=_OFFICIAL_METADATA if source_kind.is_official_aeat else {},
            stamped_revision_id=revision.id,
        )
    )


def _stored_layers(profile_id: UUID) -> ObservationLayers:
    return CalculationObservationRepository(bucket_id=str(profile_id)).load_observation_layers(_MODELO, _PERIOD)


def _observation_result(
    driver: conformance._ExecutionDriver,
    registry: OperationRegistry,
    submitted: OperationSubmission,
    observed: OperationObservationSuccessV1,
) -> ModeloLocalObservationMutationProjection:
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert observed.projection.effect is OperationEffect.UPDATED
    return conformance._resolve_result_projection(
        driver,
        registry,
        definition_id=_OBSERVATION,
        operation_id=submitted.receipt.operation_id,
        terminal_revision=observed.projection.revision,
        projection_type=ModeloLocalObservationMutationProjection,
    )


@_FRONTENDS
def test_a_recorded_figure_carries_the_session_label_for_an_agent_and_never_reads_as_official(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The result, the stored override and its audit event name who recorded it, and state what it is not."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_SessionHost(frontend)
    ) as (driver, registry, profile_id):
        modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)

        submitted, observed = _run(driver, _OBSERVATION, profile_id, _observation_request(profile_id))

        result = _observation_result(driver, registry, submitted, observed)
        assert result.captured_by == recorded
        assert result.source_kind is ObservationSourceKind.OPERATOR_MANUAL
        assert (result.official_evidence, result.filing_record_created, result.aeat_accepted) == (False, False, False)
        assert result.observation_layers.official is None
        assert result.observation_layers.effective_source_kind is ObservationSourceKind.OPERATOR_MANUAL
        assert result.observation_layers.override is not None
        assert result.observation_layers.override.actor == recorded

        pending = _stored_layers(profile_id).pending_local
        assert pending is not None and pending.override is not None
        assert pending.source_kind is ObservationSourceKind.OPERATOR_MANUAL
        assert pending.override.actor == recorded
        assert pending.source_metadata["captured_by"] == recorded
        assert pending.source_metadata["official_evidence"] == "false"
        (event,) = _events(profile_id, BucketEventType.MODELO_OBSERVATION_OVERRIDDEN)
        assert event.actor == recorded


@_FRONTENDS
def test_a_figure_leaves_official_evidence_stored_and_says_what_it_replaced(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """Nothing of the official layer is lost, so the result states it for the caller to tell the person."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_SessionHost(frontend)
    ) as (driver, registry, profile_id):
        modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
        _store_observation(profile_id, "250.00", source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE)
        official_before = _stored_layers(profile_id).official
        assert official_before is not None

        submitted, observed = _run(driver, _OBSERVATION, profile_id, _observation_request(profile_id))

        layers = _observation_result(driver, registry, submitted, observed).observation_layers
        assert layers.override is not None
        assert layers.override.actor == recorded
        assert layers.override.replaced_source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
        assert layers.override.replaced_values == ((_CASILLA, "250.00"),)
        assert layers.official is not None
        assert layers.official.official_evidence is True
        assert layers.official.casilla_values == ((_CASILLA, "250.00"),)
        assert layers.pending_local is not None
        assert layers.pending_local.official_evidence is False
        assert _stored_layers(profile_id).official == official_before


@_FRONTENDS
def test_a_figure_recorded_over_a_local_filings_observation_replaces_it_and_says_so_on_every_frontend(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """That observation shares the layer the figure is written to, so the result names what was replaced."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_SessionHost(frontend)
    ) as (driver, registry, profile_id):
        modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
        _store_observation(profile_id, "300.00", source_kind=ObservationSourceKind.APP_FILING)
        filed = _stored_layers(profile_id)
        assert filed.pending_local is not None and filed.pending_local.override is None

        submitted, observed = _run(driver, _OBSERVATION, profile_id, _observation_request(profile_id))

        override = _observation_result(driver, registry, submitted, observed).observation_layers.override
        assert override is not None
        assert override.actor == recorded
        assert override.replaced_source_kind is ObservationSourceKind.APP_FILING
        assert override.replaced_values == ((_CASILLA, "300.00"),)
        pending = _stored_layers(profile_id).pending_local
        assert pending is not None and pending.override is not None
        assert pending.source_kind is ObservationSourceKind.OPERATOR_MANUAL
        (event,) = _events(profile_id, BucketEventType.MODELO_OBSERVATION_OVERRIDDEN)
        assert event.actor == recorded


@_FRONTENDS
def test_an_operator_figure_is_replaced_and_then_cleared_alike_on_every_frontend(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """A later figure keeps the values of the one it replaces, and clearing removes the figure."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_SessionHost(frontend)
    ) as (driver, registry, profile_id):
        modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
        _run(driver, _OBSERVATION, profile_id, _observation_request(profile_id, value="125.00"))

        submitted, observed = _run(driver, _OBSERVATION, profile_id, _observation_request(profile_id, value="130.00"))
        override = _observation_result(driver, registry, submitted, observed).observation_layers.override
        assert override is not None
        assert (override.actor, override.replaced_source_kind) == (recorded, ObservationSourceKind.OPERATOR_MANUAL)
        assert override.replaced_values == ((_CASILLA, "125.00"),)

        submitted, observed = _run(
            driver, _OBSERVATION, profile_id, _clear_request(profile_id, reason="the figure was mistyped")
        )
        cleared = _observation_result(driver, registry, submitted, observed)
        assert cleared.action == "cleared"
        assert cleared.captured_by == recorded
        assert _stored_layers(profile_id).pending_local is None
        (event,) = _events(profile_id, BucketEventType.MODELO_OBSERVATION_OVERRIDE_CLEARED)
        assert event.actor == recorded


# ---------------------------------------------------------------------------
# The Modelo 145 payer communication
# ---------------------------------------------------------------------------


def _draft_request(
    profile_id: UUID, values: dict[str, str], *, note: str = "drafted for review"
) -> M145CommunicationCreateRequest:
    return M145CommunicationCreateRequest.from_command(
        profile_id=profile_id,
        command=M145CommunicationCreateCommand(
            communication_year=_M145_YEAR, period_token=_M145_PERIOD, field_values=values, note=note
        ),
        actor=_TYPED_ACTOR,
    )


def _m145_result(
    driver: conformance._ExecutionDriver,
    registry: OperationRegistry,
    definition_id: str,
    submitted: OperationSubmission,
    observed: OperationObservationSuccessV1,
) -> M145CommunicationOperationResult:
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    return conformance._resolve_result_projection(
        driver,
        registry,
        definition_id=definition_id,
        operation_id=submitted.receipt.operation_id,
        terminal_revision=observed.projection.revision,
        projection_type=M145CommunicationOperationResult,
    )


@_FRONTENDS
def test_a_draft_is_a_created_record_whose_event_carries_the_session_label_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The draft is delivered to no one and completed by no one, and its creation names who drafted it."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_SessionHost(frontend)
    ) as (driver, registry, profile_id):
        submitted, observed = _run(driver, _M145_CREATE, profile_id, _draft_request(profile_id, _WORKER))

        result = _m145_result(driver, registry, _M145_CREATE, submitted, observed)
        assert result.effect is OperationEffect.UPDATED
        record = result.result
        assert isinstance(record, M145CommunicationRecordProjection)
        assert record.state is M145CommunicationRecordState.CREATED
        assert (record.delivered_to_payer_at, record.locally_completed_at) == (None, None)
        assert {item.casilla_id: item.value for item in record.field_values} == _WORKER
        (event,) = _events(profile_id, BucketEventType.MODELO_145_COMMUNICATION_CREATED)
        assert event.object_id == record.communication_record_id
        assert event.actor == recorded


@_FRONTENDS
def test_a_draft_that_fills_the_signed_blocks_is_stored_on_every_frontend(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
) -> None:
    """The signature block of the worker and the acknowledgement of the payer are fields of the draft like any other."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_SessionHost(frontend)
    ) as (driver, registry, profile_id):
        values = {**_WORKER, "comunicacion.firma-lugar": "1", "acuse-recibo.tipo-firma": "1"}
        revision = operation.snapshot("145", filing_year=_M145_YEAR, period=_M145_PERIOD.value).revision
        record_id = derive_m145_communication_record_id(
            bucket_id=str(profile_id),
            communication_year=_M145_YEAR,
            period_token=_M145_PERIOD,
            revision_id=revision.id,
            field_values=values,
        )
        records = build_m145_communication_records_ports(bucket_id=str(profile_id)).record_repository

        submitted, observed = _run(driver, _M145_CREATE, profile_id, _draft_request(profile_id, values))

        record = _m145_result(driver, registry, _M145_CREATE, submitted, observed).result
        assert isinstance(record, M145CommunicationRecordProjection)
        assert record.communication_record_id == record_id
        assert record.state is M145CommunicationRecordState.CREATED
        assert {item.casilla_id: item.value for item in record.field_values} == values
        assert records.exists(record_id)
        (event,) = _events(profile_id, BucketEventType.MODELO_145_COMMUNICATION_CREATED)
        assert event.actor == recorded


def test_an_agents_validation_reads_the_draft_and_writes_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Validation settles with no effect and appends no event, on a draft the agent created."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_SessionHost(_MCP)
    ) as (driver, registry, profile_id):
        submitted, observed = _run(driver, _M145_CREATE, profile_id, _draft_request(profile_id, _WORKER))
        draft = _m145_result(driver, registry, _M145_CREATE, submitted, observed).result
        assert isinstance(draft, M145CommunicationRecordProjection)
        history_before = bucket_event_history_repository(bucket_id=str(profile_id)).load().events

        submitted, observed = _run(
            driver,
            _M145_VALIDATE,
            profile_id,
            M145CommunicationValidateRequest(
                profile_id=profile_id, communication_record_id=draft.communication_record_id
            ),
        )

        result = _m145_result(driver, registry, _M145_VALIDATE, submitted, observed)
        assert observed.projection.effect is OperationEffect.NONE
        assert result.effect is OperationEffect.NONE
        validation = result.result
        assert isinstance(validation, M145CommunicationValidationProjection)
        assert validation.communication_record_id == draft.communication_record_id
        assert (validation.valid, validation.issue_count) == (True, 0)
        assert bucket_event_history_repository(bucket_id=str(profile_id)).load().events == history_before
