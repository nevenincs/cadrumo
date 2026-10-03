"""Registered, exact-profile listing of persisted Modelo filing receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...core.period import Period
from ...core.time.utc import validate_utc_aware
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
)
from ...domain.modelos.filing_text import FilingNotes, ModeloActorLabel
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
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
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID = "modelo.filing_record.list"
MAX_MODELO_FILING_RECORD_LIST_ROWS = 4_096
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096

_BoundedPeriod = Annotated[str, Field(min_length=1, max_length=16)]
_BoundedMemberNif = Annotated[str, Field(min_length=1, max_length=32)]
_ModeloCodeValue = Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")]
_EvidenceReferenceValue = Annotated[str, StringConstraints(min_length=1, max_length=128)]
_CsvValue = Annotated[
    str,
    StringConstraints(
        min_length=AEAT_CSV_MIN_LENGTH,
        max_length=AEAT_CSV_MAX_LENGTH,
        pattern=rf"^[A-Z0-9]{{{AEAT_CSV_MIN_LENGTH},{AEAT_CSV_MAX_LENGTH}}}$",
    ),
]
_PresentationValue = Annotated[str, Field(max_length=64)]
_TipoSolicitudValue = Annotated[str, Field(min_length=1, max_length=64)]


class ModeloFilingRecordRegisterProjection(BaseModel):
    """Bounded AEAT register identifiers carried by the CLI filing row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    expediente_id: _EvidenceReferenceValue | None = None
    csv: _CsvValue | None = None
    justificante_number: _PresentationValue | None = None
    tipo_solicitud: _TipoSolicitudValue | None = None
    presented_at: datetime | None = None

    @field_validator("presented_at")
    @classmethod
    @pydantic_validation_boundary
    def _presented_at_is_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _has_register_identity(self) -> Self:
        if self.expediente_id is None and self.csv is None:
            raise ValueError("an AEAT register reference needs an expediente id or a CSV")
        return self


class ModeloFilingRecordEvidenceProjection(BaseModel):
    """Bounded external-evidence metadata without evidence bytes or locators."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: ExternalEvidenceKind
    reference_id: _EvidenceReferenceValue
    imported_at: datetime

    @field_validator("imported_at")
    @classmethod
    @pydantic_validation_boundary
    def _imported_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)


class ModeloFilingRecordListRequest(CredentialFreeOperationRequest):
    """Select one profile's complete filing history or one modelo."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    modelo: _ModeloCodeValue | None = None
    include_superseded: bool = False


class ModeloFilingRecordListEntryProjection(BaseModel):
    """Allowlisted wire fields already exposed by the filing-record CLI."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: _ModeloCodeValue
    filing_year: FilingYear
    period: _BoundedPeriod
    filed_at: datetime
    filed_by: ModeloActorLabel
    member_nif: _BoundedMemberNif | None
    notes: FilingNotes | None
    origin: FilingOrigin
    confirmation: AeatConfirmationState
    declaration_kind: FilingDeclarationKind
    aeat_register: ModeloFilingRecordRegisterProjection | None
    aeat_accepted: bool
    status: ModeloRecordStatus
    superseded_at: datetime | None
    superseded_by_filing_record_id: FilingRecordId | None
    external_evidence: ModeloFilingRecordEvidenceProjection | None
    amends_filing_record_id: FilingRecordId | None
    kind: Literal["internal_filing"] = "internal_filing"
    live_submission: Literal[False] = False

    @field_validator("filed_at", "superseded_at")
    @classmethod
    @pydantic_validation_boundary
    def _filing_timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _ground_public_fields(self) -> Self:
        Period.from_year_and_code(self.filing_year, self.period)
        confirmed = self.confirmation is AeatConfirmationState.CONFIRMADA
        if self.aeat_accepted != confirmed or self.aeat_accepted != (self.external_evidence is not None):
            raise ValueError("AEAT acceptance must match confirmation and external evidence")
        if self.status is ModeloRecordStatus.VIGENTE:
            if self.superseded_at is not None or self.superseded_by_filing_record_id is not None:
                raise ValueError("current filing record must not carry supersession metadata")
        elif self.superseded_at is None or self.superseded_by_filing_record_id is None:
            raise ValueError("superseded filing record must carry supersession metadata")
        elif self.superseded_at < self.filed_at:
            raise ValueError("superseded_at must not precede filed_at")
        return self

    @classmethod
    def from_record(cls, record: ModeloRecord) -> ModeloFilingRecordListEntryProjection:
        """Copy only the stable list payload fields from a canonical receipt."""
        return cls(
            filing_record_id=record.filing_record_id,
            work_unit_id=record.work_unit_id,
            calculation_revision_id=record.calculation_revision_id,
            bucket_id=record.bucket_id,
            modelo=str(record.modelo),
            filing_year=record.filing_year,
            period=record.period.registry_token,
            filed_at=record.filed_at,
            filed_by=record.filed_by,
            member_nif=record.member_nif,
            notes=record.notes,
            origin=record.origin,
            confirmation=record.confirmation,
            declaration_kind=record.declaration_kind,
            aeat_register=(
                ModeloFilingRecordRegisterProjection.model_validate(record.aeat_register.model_dump(mode="python"))
                if record.aeat_register is not None
                else None
            ),
            aeat_accepted=record.aeat_accepted,
            status=record.status,
            superseded_at=record.superseded_at,
            superseded_by_filing_record_id=record.superseded_by_filing_record_id,
            external_evidence=(
                ModeloFilingRecordEvidenceProjection.model_validate(record.external_evidence.model_dump(mode="python"))
                if record.external_evidence is not None
                else None
            ),
            amends_filing_record_id=record.amends_filing_record_id,
        )


_Rows = Annotated[
    tuple[ModeloFilingRecordListEntryProjection, ...],
    Field(max_length=MAX_MODELO_FILING_RECORD_LIST_ROWS),
]


class ModeloFilingRecordListProjection(BaseModel):
    """Complete, bounded result for one exact-profile filing-record listing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    modelo: _ModeloCodeValue | None
    include_superseded: bool
    record_count: NonNegativeInt
    records: _Rows

    @model_validator(mode="after")
    def _correlate_rows(self) -> Self:
        """Reject cross-profile, out-of-filter, duplicate, or noncanonical rows."""
        if self.record_count != len(self.records):
            raise ValueError("filing record count does not match its rows")
        profile_id = str(self.profile_id)
        if any(record.bucket_id != profile_id for record in self.records):
            raise ValueError("filing record list contains another profile")
        if self.modelo is not None and any(record.modelo != self.modelo for record in self.records):
            raise ValueError("filing record list exceeds its modelo filter")
        if not self.include_superseded and any(
            record.status is not ModeloRecordStatus.VIGENTE for record in self.records
        ):
            raise ValueError("filing record list contains superseded rows")
        if len({record.filing_record_id for record in self.records}) != len(self.records):
            raise ValueError("filing record list repeats an identity")
        expected = tuple(sorted(self.records, key=_projection_order_key))
        if self.records != expected:
            raise ValueError("filing record list is not in canonical order")
        return self


def _record_order_key(record: ModeloRecord) -> tuple[str, int, str, str, datetime, str]:
    """Retain legacy list ordering and break ties by stable receipt identity."""
    return (
        record.bucket_id,
        record.filing_year,
        str(record.modelo),
        record.period.registry_token,
        record.filed_at,
        record.filing_record_id,
    )


def _projection_order_key(
    record: ModeloFilingRecordListEntryProjection,
) -> tuple[str, int, str, str, datetime, str]:
    return (
        record.bucket_id,
        record.filing_year,
        str(record.modelo),
        record.period,
        record.filed_at,
        record.filing_record_id,
    )


def _capture(
    payload: ModeloFilingRecordListRequest,
    bundle: VerificationRepositoryBundle,
) -> ModeloFilingRecordListProjection:
    """Read the requested rows from the exact profile's filing repository."""
    profile_id = str(payload.profile_id)
    if bundle.filing.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    catalogue = bundle.filing.load()
    records = tuple(
        record
        for record in catalogue.records.values()
        if record.bucket_id == profile_id
        and (payload.modelo is None or record.modelo == payload.modelo)
        and (payload.include_superseded or record.status is ModeloRecordStatus.VIGENTE)
    )
    records = tuple(sorted(records, key=_record_order_key))
    if len(records) > MAX_MODELO_FILING_RECORD_LIST_ROWS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    projection = ModeloFilingRecordListProjection(
        profile_id=payload.profile_id,
        modelo=payload.modelo,
        include_superseded=payload.include_superseded,
        record_count=len(records),
        records=tuple(ModeloFilingRecordListEntryProjection.from_record(record) for record in records),
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return projection


class ModeloFilingRecordListExecutor:
    """Capture a bounded filing-record list within worker-owned profile custody."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        """Retain the composition-supplied exact-profile repository factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloFilingRecordListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Store one complete listing and report a nonmutating effect."""
        payload = request.payload
        subject = profile_operation_subject(str(payload.profile_id))
        if (
            request.definition_id != MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID)

        def read() -> ModeloFilingRecordListProjection:
            bundle = self._factory(str(payload.profile_id), operation=context.authority_operation)
            return _capture(payload, bundle)

        return await capture_read_result(context, read, task_name="modelo-filing-record-list")


def build_modelo_filing_record_list_definition(
    factory: VerificationRepositoryBundleFactory,
) -> OperationDefinition:
    """Declare a credential-free, recorded, nonmutating listing."""
    return OperationDefinition(
        definition_id=MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
        request_type=ModeloFilingRecordListRequest,
        result_type=ModeloFilingRecordListProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloFilingRecordListRequest,
            executor_type=ModeloFilingRecordListExecutor,
            build=lambda: ModeloFilingRecordListExecutor(factory),
        ),
        phase_codes=(MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_modelo_filing_record_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require whole-profile consent for the potentially multi-period listing."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, ModeloFilingRecordListRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            require_period_independent_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        return bind_operation_access_profile(
            context,
            LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=frozenset(),
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloFilingRecordListProjection,
        access_resolver=resolve,
    )


__all__ = [
    "MAX_MODELO_FILING_RECORD_LIST_ROWS",
    "MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID",
    "ModeloFilingRecordListEntryProjection",
    "ModeloFilingRecordListExecutor",
    "ModeloFilingRecordListProjection",
    "ModeloFilingRecordListRequest",
    "build_modelo_filing_record_list_definition",
    "build_modelo_filing_record_list_registration",
]
