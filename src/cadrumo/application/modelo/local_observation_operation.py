"""Registered exact-profile mutations for operator-local modelo observations."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.filing_text import ModeloActorLabel, OperatorReason
from ..calculations.observations_repository import ObservationSourceKind
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_errors import ModeloLocalObservationError
from .calculation_action_ports import CalculationActionPortsFactory
from .filing_record_view_operation import ModeloFilingObservationLayersProjection
from .local_observation_actions import (
    LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL,
    LocalObservationPorts,
    ModeloLocalObservationClearResult,
    ModeloLocalObservationResult,
    clear_operator_local_observation,
    record_operator_local_observation,
)

MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID = "modelo.observation.local"
MAX_MODELO_LOCAL_OBSERVATION_CASILLAS = 4_096
_PHASES = (MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,)

_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]


class ModeloLocalObservationCasillaValue(BaseModel):
    """One canonical casilla and decimal-text pair on the operation wire."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    value: _DecimalText

    @field_validator("value")
    @classmethod
    def _canonical_decimal_text(cls, value: str) -> str:
        """Keep the operation schema textual while matching the CLI decimal grammar."""
        if try_parse_canonical_decimal(value, max_fraction_digits=2) is None:
            raise ValueError("local observation values must be canonical decimal text")
        return value


_CasillaValues = Annotated[
    tuple[ModeloLocalObservationCasillaValue, ...],
    Field(max_length=MAX_MODELO_LOCAL_OBSERVATION_CASILLAS),
]


class ModeloLocalObservationMutationRequest(BaseModel):
    """One profile-bound record or clear request with securely stored values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    action: Literal["record", "clear"]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    casilla_values: _CasillaValues = ()
    actor: ModeloActorLabel | None = None
    reason: OperatorReason

    @model_validator(mode="after")
    def _action_values(self) -> Self:
        """Require the exact input shape for the selected mutation."""
        keys = tuple(row.casilla_id for row in self.casilla_values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("local observation casilla values must be unique and sorted")
        if self.action == "record" and not self.casilla_values:
            raise ValueError("recording a local observation requires at least one casilla value")
        if self.action == "clear" and self.casilla_values:
            raise ValueError("clearing a local observation cannot carry casilla values")
        return self


class ModeloLocalObservationMutationProjection(BaseModel):
    """Allowlisted command result with string decimals and both observation layers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    action: Literal["recorded", "cleared"]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    revision_id: RevisionId | None = None
    observation_key: Annotated[str, Field(min_length=1, max_length=256)]
    source_kind: ObservationSourceKind | None = None
    casilla_values: _CasillaValues = ()
    captured_at: datetime
    captured_by: ModeloActorLabel
    reason: OperatorReason
    observation_layers: ModeloFilingObservationLayersProjection
    official_evidence: Literal[False] = False
    filing_record_created: Literal[False] = False
    aeat_accepted: Literal[False] = False

    @field_validator("captured_at")
    @classmethod
    def _captured_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _coherent_projection(self) -> Self:
        """Prove record/clear shape and the persisted layers describe one coordinate."""
        carries_detail = LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL[self.action]
        details = (self.revision_id is not None, self.source_kind is not None, bool(self.casilla_values))
        if any(value is not carries_detail for value in details):
            raise ValueError("local observation result fields do not match its action")

        keys = tuple(row.casilla_id for row in self.casilla_values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("local observation result casilla values must be unique and sorted")

        layers = self.observation_layers
        if (
            layers.modelo != self.modelo
            or layers.filing_year != self.period.filing_year
            or layers.period != self.period.code
            or layers.member_nif is not None
        ):
            raise ValueError("local observation result layers do not match its coordinate")

        if self.action == "recorded":
            pending = layers.pending_local
            override = layers.override
            if (
                self.source_kind is not ObservationSourceKind.OPERATOR_MANUAL
                or pending is None
                or pending.source_kind is not ObservationSourceKind.OPERATOR_MANUAL
                or pending.stamped_revision_id != self.revision_id
                or pending.captured_at != self.captured_at
                or pending.casilla_values != tuple((row.casilla_id, row.value) for row in self.casilla_values)
                or layers.effective_source_kind is not ObservationSourceKind.OPERATOR_MANUAL
                or override is None
                or override.actor != self.captured_by
                or override.reason != self.reason
                or override.recorded_at != self.captured_at
            ):
                raise ValueError("recorded local observation differs from its persisted pending layer")
        elif (
            layers.pending_local is not None
            or layers.override is not None
            or layers.effective_source_kind != (layers.official.source_kind if layers.official is not None else None)
        ):
            raise ValueError("cleared local observation still exposes a pending override")
        return self


class ModeloLocalObservationMutationReport(BaseModel):
    """Encrypted operation result before the receipt-bound public projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloLocalObservationMutationProjection
    local_write_performed: Literal[True]


def project_modelo_local_observation_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release only a result whose exact receipt proves the local write."""
    if type(result) is not ModeloLocalObservationMutationReport:
        raise ValueError("invalid local observation operation result")
    report = ModeloLocalObservationMutationReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    if (
        receipt.identity.definition_id != MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("local observation result contradicts its terminal receipt")
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ValueError("local observation result exceeds the projection document limit")
    return projection


def _local_observation_ports(
    factory: CalculationActionPortsFactory,
    *,
    profile_id: str,
    operation: PinnedAuthorityOperation,
) -> LocalObservationPorts:
    """Build the canonical calculation repository bundle for one exact profile."""
    calculation_ports = factory(bucket_id=profile_id, operation=operation)
    if calculation_ports.work_unit_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LocalObservationPorts(
        bucket_id=profile_id,
        observation_repository=calculation_ports.observation_repository,
        bucket_event_repository=calculation_ports.bucket_event_repository,
        work_unit_repository=calculation_ports.work_unit_repository,
    )


def _projection_from_record(
    *,
    profile_id: UUID,
    result: ModeloLocalObservationResult,
    layers: ModeloFilingObservationLayersProjection,
) -> ModeloLocalObservationMutationProjection:
    """Project a canonical record result without exposing an unbounded domain object."""
    return ModeloLocalObservationMutationProjection(
        profile_id=profile_id,
        action="recorded",
        modelo=result.modelo,
        period=PublicPeriod.from_period(result.period),
        revision_id=result.revision_id,
        observation_key=result.observation_key,
        source_kind=result.source_kind,
        casilla_values=tuple(
            ModeloLocalObservationCasillaValue(casilla_id=str(casilla_id), value=str(value))
            for casilla_id, value in sorted(result.casilla_values.items())
        ),
        captured_at=result.captured_at,
        captured_by=result.captured_by,
        reason=result.override.reason,
        observation_layers=layers,
    )


def _projection_from_clear(
    *,
    profile_id: UUID,
    result: ModeloLocalObservationClearResult,
    layers: ModeloFilingObservationLayersProjection,
) -> ModeloLocalObservationMutationProjection:
    """Project a clear result without releasing the removed override's old values."""
    return ModeloLocalObservationMutationProjection(
        profile_id=profile_id,
        action="cleared",
        modelo=result.modelo,
        period=PublicPeriod.from_period(result.period),
        observation_key=result.observation_key,
        captured_at=result.cleared_at,
        captured_by=result.cleared_by,
        reason=result.reason,
        observation_layers=layers,
    )


class ModeloLocalObservationMutationExecutor:
    """Run the existing local observation service in exact-profile worker custody."""

    def __init__(self, factory: CalculationActionPortsFactory) -> None:
        """Retain the canonical profile-bound calculation ports factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloLocalObservationMutationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Commit one audited override or clear under the supervisor COMMIT fence."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        subject_ref = profile_operation_subject(profile_id)
        if (
            request.definition_id != MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID
            or request.subject_ref != subject_ref
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject_ref
            or require_active_bucket_id() != profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        period = payload.period.to_period()
        actor = payload.actor or f"profile:{profile_id}"
        ports = _local_observation_ports(
            self._factory,
            profile_id=profile_id,
            operation=context.authority_operation,
        )
        await context.events.phase(MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID)

        def mutate() -> ModeloLocalObservationResult | ModeloLocalObservationClearResult:
            """Call the existing application action; both actions batch all writes once."""
            if payload.action == "record":
                values = {row.casilla_id: Decimal(row.value) for row in payload.casilla_values}
                return record_operator_local_observation(
                    modelo=payload.modelo,
                    filing_year=period.filing_year,
                    period=period,
                    casilla_values=values,
                    actor=actor,
                    reason=payload.reason,
                    ports=ports,
                    operation=context.authority_operation,
                )
            return clear_operator_local_observation(
                payload.modelo,
                period.filing_year,
                period,
                reason=payload.reason,
                actor=actor,
                ports=ports,
            )

        async def commit_and_publish() -> str:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(mutate)
                except ModeloLocalObservationError:
                    # This exception is raised by pre-write validation/read paths.
                    await context.events.effect(OperationEffect.NONE)
                    raise

                await context.events.effect(OperationEffect.UPDATED)
                layers = await asyncio.to_thread(
                    ports.observation_repository.load_observation_layers,
                    payload.modelo,
                    period,
                )
                layer_projection = ModeloFilingObservationLayersProjection.from_layers(layers)
                if payload.action == "record":
                    if not isinstance(result, ModeloLocalObservationResult):
                        raise ValueError("record action returned a clear result")
                    projection = _projection_from_record(
                        profile_id=payload.profile_id,
                        result=result,
                        layers=layer_projection,
                    )
                else:
                    if not isinstance(result, ModeloLocalObservationClearResult):
                        raise ValueError("clear action returned a record result")
                    projection = _projection_from_clear(
                        profile_id=payload.profile_id,
                        result=result,
                        layers=layer_projection,
                    )
                if (
                    projection.modelo != payload.modelo
                    or projection.period != payload.period
                    or projection.captured_by != actor
                    or projection.reason != payload.reason
                    or projection.observation_layers.modelo != payload.modelo
                ):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                report = ModeloLocalObservationMutationReport(
                    projection=projection,
                    local_write_performed=True,
                )
                if len(canonical_json_bytes(report.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                return await context.operands.put(report, written_at=now())

        return await await_cancellation_complete(commit_and_publish(), task_name="modelo-local-observation-mutation")


def build_modelo_local_observation_definition(factory: CalculationActionPortsFactory) -> OperationDefinition:
    """Declare one durable mutation with encrypted request and result custody."""
    return OperationDefinition(
        definition_id=MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
        request_type=ModeloLocalObservationMutationRequest,
        result_type=ModeloLocalObservationMutationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloLocalObservationMutationRequest,
            executor_type=ModeloLocalObservationMutationExecutor,
            build=lambda: ModeloLocalObservationMutationExecutor(factory),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_modelo_local_observation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require exact profile and filing period access, plus fresh COMMIT authority."""
    if request.definition_id != MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, ModeloLocalObservationMutationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset({payload.period.to_period()}),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_modelo_local_observation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the secure request and receipt-projected output schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloLocalObservationMutationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloLocalObservationMutationProjection,
        ),
        result_projector=project_modelo_local_observation_result,
        access_resolver=resolve_modelo_local_observation_access,
    )


__all__ = [
    "MAX_MODELO_LOCAL_OBSERVATION_CASILLAS",
    "MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID",
    "ModeloLocalObservationCasillaValue",
    "ModeloLocalObservationMutationExecutor",
    "ModeloLocalObservationMutationProjection",
    "ModeloLocalObservationMutationReport",
    "ModeloLocalObservationMutationRequest",
    "build_modelo_local_observation_definition",
    "build_modelo_local_observation_registration",
    "project_modelo_local_observation_result",
    "resolve_modelo_local_observation_access",
]
