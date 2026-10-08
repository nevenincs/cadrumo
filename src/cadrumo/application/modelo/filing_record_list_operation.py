"""Capture registered exact-profile filing histories within worker-owned custody.

Core types: :class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ...core.hashing import canonical_json_bytes
from ...core.operations import profile_operation_subject
from ...domain.modelos.filing_record import (
    ModeloRecord,
    ModeloRecordStatus,
)
from ..operations.access_resolution import (
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filing_record_list_contracts import (
    MAX_MODELO_FILING_RECORD_LIST_ROWS,
    ModeloFilingRecordListEntryProjection,
    ModeloFilingRecordListProjection,
    ModeloFilingRecordListRequest,
)
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID = "modelo.filing_record.list"


_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096


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


def _filing_record_matches_request(
    record: ModeloRecord, payload: ModeloFilingRecordListRequest, profile_id: str
) -> bool:
    """Apply profile, modelo and status filters without changing evaluation order."""
    return (
        record.bucket_id == profile_id
        and (payload.modelo is None or record.modelo == payload.modelo)
        and (payload.include_superseded or record.status is ModeloRecordStatus.VIGENTE)
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
        record for record in catalogue.records.values() if _filing_record_matches_request(record, payload, profile_id)
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
    return build_single_phase_definition(
        definition_id=MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
        request_type=ModeloFilingRecordListRequest,
        result_type=ModeloFilingRecordListProjection,
        executor_type=ModeloFilingRecordListExecutor,
        build=lambda: ModeloFilingRecordListExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_modelo_filing_record_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require whole-profile consent for the potentially multi-period listing."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        require_access_request_profile_payload(
            request,
            definition_id=definition.definition_id,
            payload_type=ModeloFilingRecordListRequest,
            access_profile_id=context.profile_id,
        )
        return bind_replayed_period_independent_access(
            context, LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS, definition_id=request.definition_id
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloFilingRecordListProjection,
        access_resolver=resolve,
    )
