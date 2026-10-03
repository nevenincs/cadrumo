"""Registered exact-profile view of a filing receipt and both observation layers."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.casilla_id import validated_casilla_id
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...core.period import Period
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.filing_text import ModeloActorLabel, OperatorReason
from ..calculations.observations_repository import (
    ObservationEnvelopePayload,
    ObservationLayers,
    ObservationOverride,
    ObservationSourceKind,
)
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_single_period_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filing_record_list_operation import ModeloFilingRecordListEntryProjection
from .filing_record_ownership import load_profile_filing_record
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID = "modelo.filing_record.view"
MAX_FILING_RECORD_VIEW_CASILLA_VALUES = 4_096
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096

_ObservationCasillaValues = Annotated[
    tuple[tuple[Annotated[str, Field(min_length=1, max_length=32)], Annotated[str, Field(max_length=128)]], ...],
    Field(max_length=MAX_FILING_RECORD_VIEW_CASILLA_VALUES),
]
_OverrideCasillaValues = Annotated[
    tuple[tuple[Annotated[str, Field(min_length=1, max_length=32)], Annotated[str, Field(max_length=512)]], ...],
    Field(max_length=MAX_FILING_RECORD_VIEW_CASILLA_VALUES),
]


class ModeloFilingRecordViewRequest(CredentialFreeOperationRequest):
    """Select one filing receipt in the authenticated profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    filing_record_id: FilingRecordId


class ModeloFilingObservationLayerProjection(BaseModel):
    """Public fields for one stored observation layer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_kind: ObservationSourceKind
    official_evidence: bool
    captured_at: datetime
    stamped_revision_id: RevisionId
    casilla_values: _ObservationCasillaValues

    @field_validator("captured_at")
    @classmethod
    @pydantic_validation_boundary
    def _captured_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _casilla_keys_are_canonical(self) -> Self:
        keys = tuple(key for key, _value in self.casilla_values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("filing observation casillas must be unique and sorted")
        for key in keys:
            validated_casilla_id(key, surface="filing record view")
        return self

    @classmethod
    def from_envelope(cls, envelope: ObservationEnvelopePayload) -> ModeloFilingObservationLayerProjection:
        """Copy only the filing-view fields, in stable casilla order."""
        return cls(
            source_kind=envelope.source_kind,
            official_evidence=envelope.source_kind.is_official_aeat,
            captured_at=envelope.captured_at,
            stamped_revision_id=envelope.stamped_revision_id,
            casilla_values=tuple(
                (str(key), str(value)) for key, value in sorted(envelope.observation.casilla_values.items())
            ),
        )


class ModeloFilingObservationOverrideProjection(BaseModel):
    """Bounded audit fields for an operator override on the pending layer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    actor: ModeloActorLabel
    reason: OperatorReason
    recorded_at: datetime
    replaced_source_kind: ObservationSourceKind | None = None
    replaced_values: _OverrideCasillaValues

    @field_validator("recorded_at")
    @classmethod
    @pydantic_validation_boundary
    def _recorded_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _replaced_keys_are_canonical(self) -> Self:
        keys = tuple(key for key, _value in self.replaced_values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("filing override casillas must be unique and sorted")
        for key in keys:
            validated_casilla_id(key, surface="filing record view override")
        return self

    @classmethod
    def from_override(cls, override: ObservationOverride) -> ModeloFilingObservationOverrideProjection:
        """Copy the safe override audit fields in stable casilla order."""
        return cls(
            actor=override.actor,
            reason=override.reason,
            recorded_at=override.recorded_at,
            replaced_source_kind=override.replaced_source_kind,
            replaced_values=tuple(sorted(override.replaced_values.items())),
        )


class ModeloFilingObservationLayersProjection(BaseModel):
    """Both observation layers and the coordinate they belong to."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: Annotated[str, Field(min_length=1, max_length=16)]
    filing_year: FilingYear
    period: Annotated[str, Field(min_length=1, max_length=16)]
    member_nif: Annotated[str, Field(min_length=1, max_length=16)] | None = None
    official: ModeloFilingObservationLayerProjection | None = None
    pending_local: ModeloFilingObservationLayerProjection | None = None
    effective_source_kind: ObservationSourceKind | None = None
    override: ModeloFilingObservationOverrideProjection | None = None

    @classmethod
    def from_layers(cls, layers: ObservationLayers) -> ModeloFilingObservationLayersProjection:
        """Project the two stored envelopes and the pending-layer audit."""
        pending = layers.pending_local
        effective = layers.effective
        return cls(
            modelo=layers.modelo,
            filing_year=layers.filing_year,
            period=Period.from_year_and_code(layers.filing_year, layers.period).registry_token,
            member_nif=layers.member_nif,
            official=(
                ModeloFilingObservationLayerProjection.from_envelope(layers.official)
                if layers.official is not None
                else None
            ),
            pending_local=(
                ModeloFilingObservationLayerProjection.from_envelope(pending) if pending is not None else None
            ),
            effective_source_kind=effective.source_kind if effective is not None else None,
            override=(
                ModeloFilingObservationOverrideProjection.from_override(pending.override)
                if pending is not None and pending.override is not None
                else None
            ),
        )


class ModeloFilingRecordViewProjection(BaseModel):
    """Bounded receipt and both observation layers for one exact filing ID."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    filing_record_id: FilingRecordId
    record: ModeloFilingRecordListEntryProjection
    observation_layers: ModeloFilingObservationLayersProjection

    @model_validator(mode="after")
    def _bound_result(self) -> Self:
        record = self.record
        layers = self.observation_layers
        if (
            record.filing_record_id != self.filing_record_id
            or record.bucket_id != str(self.profile_id)
            or record.modelo != layers.modelo
            or record.filing_year != layers.filing_year
            or record.period != layers.period
            or record.member_nif != layers.member_nif
        ):
            raise ValueError("filing view coordinates do not match the selected profile and receipt")
        return self


def _resolve_period(
    payload: ModeloFilingRecordViewRequest,
    factory: VerificationRepositoryBundleFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> PublicPeriod:
    """Resolve exact filing scope without reading observation values at admission."""
    bundle = factory(str(payload.profile_id), operation=operation)
    record, _unit = load_profile_filing_record(
        bundle, profile_id=payload.profile_id, filing_record_id=payload.filing_record_id
    )
    return PublicPeriod.from_period(record.period)


def _capture(
    payload: ModeloFilingRecordViewRequest,
    bundle: VerificationRepositoryBundle,
) -> ModeloFilingRecordViewProjection:
    """Capture one receipt and both canonical observation layers together."""
    record, _unit = load_profile_filing_record(
        bundle, profile_id=payload.profile_id, filing_record_id=payload.filing_record_id
    )
    layers = bundle.observation.load_observation_layers(str(record.modelo), record.period, member_nif=record.member_nif)
    projection = ModeloFilingRecordViewProjection(
        profile_id=payload.profile_id,
        filing_record_id=payload.filing_record_id,
        record=ModeloFilingRecordListEntryProjection.from_record(record),
        observation_layers=ModeloFilingObservationLayersProjection.from_layers(layers),
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return projection


class ModeloFilingRecordViewExecutor:
    """Read the filing and observations in one worker-owned profile custody."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        """Retain the composition-supplied application repository factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloFilingRecordViewRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture the exact record and its observation layers into encrypted custody."""
        payload = request.payload
        subject = profile_operation_subject(str(payload.profile_id))
        if (
            request.definition_id != MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID)

        def read() -> ModeloFilingRecordViewProjection:
            bundle = self._factory(str(payload.profile_id), operation=context.authority_operation)
            return _capture(payload, bundle)

        return await capture_read_result(context, read, task_name="modelo-filing-record-view")


def build_modelo_filing_record_view_definition(
    factory: VerificationRepositoryBundleFactory,
) -> OperationDefinition:
    """Declare a credential-free, recorded, nonmutating filing view."""
    return OperationDefinition(
        definition_id=MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
        request_type=ModeloFilingRecordViewRequest,
        result_type=ModeloFilingRecordViewProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloFilingRecordViewRequest,
            executor_type=ModeloFilingRecordViewExecutor,
            build=lambda: ModeloFilingRecordViewExecutor(factory),
        ),
        phase_codes=(MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_modelo_filing_record_view_registration(
    definition: OperationDefinition,
    factory: VerificationRepositoryBundleFactory,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind observation and result disclosure to the admitted receipt period."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloFilingRecordViewRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            period = _resolve_period(
                payload,
                factory,
                operation=context.authority_operation,
            ).to_period()
            periods = frozenset({period})

        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloFilingRecordViewProjection,
        access_resolver=resolve,
    )


__all__ = [
    "MAX_FILING_RECORD_VIEW_CASILLA_VALUES",
    "MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID",
    "ModeloFilingObservationLayerProjection",
    "ModeloFilingObservationLayersProjection",
    "ModeloFilingObservationOverrideProjection",
    "ModeloFilingRecordViewExecutor",
    "ModeloFilingRecordViewProjection",
    "ModeloFilingRecordViewRequest",
    "build_modelo_filing_record_view_definition",
    "build_modelo_filing_record_view_registration",
]
