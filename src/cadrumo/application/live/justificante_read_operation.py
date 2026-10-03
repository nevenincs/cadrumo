"""Registered exact-profile reads of locally stored justificante captures."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    NonNegativeInt,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

from ...core.aeat_csv import AEAT_CSV_MAX_LENGTH, AEAT_CSV_MIN_LENGTH
from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN, FilingYear
from ...core.hex import Hex64Str
from ...core.identity.aeat_csv import AeatCsv
from ...core.identity.aeat_expediente import (
    AEAT_EXPEDIENTE_ID_MAX_LENGTH,
    AEAT_EXPEDIENTE_ID_MIN_LENGTH,
    AEAT_EXPEDIENTE_ID_PATTERN,
    AeatExpedienteId,
)
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import SnapshotId
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ..calculations.observations_repository import ObservationSourceKind
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES, OperationCapabilities
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_terminal_receipt_match,
)
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .justificante import JustificanteCaptureSnapshot, JustificanteCaptureSnapshotService
from .snapshot_base import SnapshotLifecycleState

JUSTIFICANTE_LIST_DEFINITION_ID = "live.justificante.list"
JUSTIFICANTE_SHOW_DEFINITION_ID = "live.justificante.show"
_LIST_PHASES = ("justificante-list.read", "justificante-list.result")
_SHOW_PHASES = ("justificante-show.read", "justificante-show.result")
_SnapshotIdPrefix = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
]
_BUCKET_ID: TypeAdapter[str] = TypeAdapter(BucketId)
_SNAPSHOT_ID: TypeAdapter[str] = TypeAdapter(SnapshotId)
_MODELO: TypeAdapter[Modelo] = TypeAdapter(Modelo)
_FILING_YEAR: TypeAdapter[int] = TypeAdapter(FilingYear)
_CSV: TypeAdapter[str] = TypeAdapter(AeatCsv)
_EXPEDIENTE_ID: TypeAdapter[str] = TypeAdapter(AeatExpedienteId)
_CONTENT_DIGEST: TypeAdapter[str] = TypeAdapter(ContentDigest)


class JustificanteListRequest(CredentialFreeOperationRequest):
    """List active receipt snapshots from one immutable profile worker."""

    profile_id: UUID


class JustificanteShowRequest(CredentialFreeOperationRequest):
    """Resolve one locally stored receipt by full digest or unambiguous prefix."""

    profile_id: UUID
    snapshot_id: _SnapshotIdPrefix


class JustificanteSnapshotSummaryPublicV1(BaseModel):
    """Allowlisted summary fields already present in the list command result."""

    model_config = STRICT_FROZEN_CONFIG
    snapshot_id: Hex64Str
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=FILING_YEAR_MIN, le=FILING_YEAR_MAX)
    period: str = Field(min_length=1, max_length=16)
    pdf_sha256: ContentDigest
    state: str = Field(min_length=1, max_length=16)
    captured_at: datetime


class JustificanteListOperationReport(BaseModel):
    """Private encrypted list operand scoped to the operation's profile."""

    model_config = STRICT_FROZEN_CONFIG
    bucket_id: str = Field(min_length=1, max_length=128)
    rows: tuple[JustificanteSnapshotSummaryPublicV1, ...]


class JustificanteShowOperationReport(BaseModel):
    """Keep the full stored capture inside encrypted operation custody."""

    model_config = STRICT_FROZEN_CONFIG
    snapshot: JustificanteCaptureSnapshot


class JustificanteListPublicResultV1(BaseModel):
    """Closed active-capture inventory for an authorized whole-profile read."""

    model_config = STRICT_FROZEN_CONFIG
    bucket_id: str = Field(min_length=1, max_length=128)
    count: NonNegativeInt
    rows: tuple[JustificanteSnapshotSummaryPublicV1, ...]

    @model_validator(mode="after")
    def _count_matches_rows(self) -> JustificanteListPublicResultV1:
        if self.count != len(self.rows):
            raise ValueError("justificante count disagrees with its snapshot rows")
        return self


class JustificanteShowPublicResultV1(BaseModel):
    """Bounded detail projection that never returns the stored PDF body."""

    model_config = STRICT_FROZEN_CONFIG
    bucket_id: str = Field(min_length=1, max_length=128)
    snapshot_id: Hex64Str
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=FILING_YEAR_MIN, le=FILING_YEAR_MAX)
    period: str = Field(min_length=1, max_length=16)
    expediente_id: str = Field(
        min_length=AEAT_EXPEDIENTE_ID_MIN_LENGTH,
        max_length=AEAT_EXPEDIENTE_ID_MAX_LENGTH,
        pattern=AEAT_EXPEDIENTE_ID_PATTERN,
    )
    csv: str = Field(
        min_length=AEAT_CSV_MIN_LENGTH,
        max_length=AEAT_CSV_MAX_LENGTH,
        pattern=rf"^[A-Z0-9]{{{AEAT_CSV_MIN_LENGTH},{AEAT_CSV_MAX_LENGTH}}}$",
    )
    pdf_sha256: ContentDigest
    source_kind: str = Field(min_length=1, max_length=64)
    state: str = Field(min_length=1, max_length=16)
    captured_at: datetime


JustificanteCaptureSnapshotServiceFactory = Callable[[str], JustificanteCaptureSnapshotService]


def _exact_bucket(profile_id: UUID, subject_ref: str) -> str:
    bucket_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != bucket_id or subject_ref != profile_operation_subject(bucket_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def _summary(snapshot: JustificanteCaptureSnapshot) -> JustificanteSnapshotSummaryPublicV1:
    return JustificanteSnapshotSummaryPublicV1(
        snapshot_id=_SNAPSHOT_ID.validate_python(str(snapshot.snapshot_id), strict=True),
        modelo=str(_MODELO.validate_python(snapshot.modelo)),
        filing_year=_FILING_YEAR.validate_python(int(snapshot.filing_year), strict=True),
        period=_validated_period_token(snapshot),
        pdf_sha256=_CONTENT_DIGEST.validate_python(str(snapshot.pdf_sha256), strict=True),
        state=SnapshotLifecycleState(snapshot.state).value,
        captured_at=snapshot.captured_at,
    )


def _require_bucket(snapshot: JustificanteCaptureSnapshot, bucket_id: str) -> None:
    stored_bucket_id = _BUCKET_ID.validate_python(str(snapshot.bucket_id), strict=True)
    if stored_bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _validated_period_token(snapshot: JustificanteCaptureSnapshot) -> str:
    """Validate the scalar period at the public projection boundary."""
    token = snapshot.period.registry_token
    Period.from_year_and_code(snapshot.filing_year, token)
    return token


class JustificanteListExecutor:
    """Read local active receipt summaries without browser resources."""

    def __init__(self, service_factory: JustificanteCaptureSnapshotServiceFactory) -> None:
        self._service_factory = service_factory

    async def execute(
        self, request: OperationRequest[JustificanteListRequest], context: OperationExecutorContext
    ) -> str:
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
        if request.definition_id != JUSTIFICANTE_LIST_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, request.payload.profile_id)
        await context.events.phase(_LIST_PHASES[0])

        def read() -> JustificanteListOperationReport:
            snapshots = self._service_factory(bucket_id).list_snapshots()
            for snapshot in snapshots:
                _require_bucket(snapshot, bucket_id)
            return JustificanteListOperationReport(
                bucket_id=bucket_id,
                rows=tuple(_summary(snapshot) for snapshot in snapshots),
            )

        report = await asyncio.to_thread(read)
        await context.events.phase(_LIST_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="justificante-list-result"
        )


class JustificanteShowExecutor:
    """Read one local encrypted capture while keeping receipt bytes private."""

    def __init__(self, service_factory: JustificanteCaptureSnapshotServiceFactory) -> None:
        self._service_factory = service_factory

    async def execute(
        self, request: OperationRequest[JustificanteShowRequest], context: OperationExecutorContext
    ) -> str:
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
        if request.definition_id != JUSTIFICANTE_SHOW_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, request.payload.profile_id)
        await context.events.phase(_SHOW_PHASES[0])

        def read() -> JustificanteShowOperationReport:
            snapshot = self._service_factory(bucket_id).show(request.payload.snapshot_id)
            _require_bucket(snapshot, bucket_id)
            return JustificanteShowOperationReport(snapshot=snapshot)

        report = await asyncio.to_thread(read)
        await context.events.phase(_SHOW_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="justificante-show-result"
        )


def _capabilities() -> OperationCapabilities:
    return RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES


def build_justificante_list_definition(
    service_factory: JustificanteCaptureSnapshotServiceFactory,
) -> OperationDefinition:
    """Declare an encrypted, profile-bound local receipt inventory."""
    return OperationDefinition(
        definition_id=JUSTIFICANTE_LIST_DEFINITION_ID,
        request_type=JustificanteListRequest,
        result_type=JustificanteListOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=JustificanteListRequest,
            executor_type=JustificanteListExecutor,
            build=lambda: JustificanteListExecutor(service_factory),
        ),
        phase_codes=_LIST_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_justificante_show_definition(
    service_factory: JustificanteCaptureSnapshotServiceFactory,
) -> OperationDefinition:
    """Declare a local exact-profile detail read with a closed result projection."""
    return OperationDefinition(
        definition_id=JUSTIFICANTE_SHOW_DEFINITION_ID,
        request_type=JustificanteShowRequest,
        result_type=JustificanteShowOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=JustificanteShowRequest,
            executor_type=JustificanteShowExecutor,
            build=lambda: JustificanteShowExecutor(service_factory),
        ),
        phase_codes=_SHOW_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


_RECEIPT_CONTRADICTION = "justificante read result contradicts its terminal receipt"


def _project_list(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not JustificanteListOperationReport:
        raise ValueError("invalid justificante list report")
    report = JustificanteListOperationReport.model_validate(result, strict=True)
    require_terminal_receipt_match(
        receipt,
        definition_id=JUSTIFICANTE_LIST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(report.bucket_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message=_RECEIPT_CONTRADICTION,
    )
    return JustificanteListPublicResultV1(bucket_id=report.bucket_id, count=len(report.rows), rows=report.rows)


def _project_show(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not JustificanteShowOperationReport:
        raise ValueError("invalid justificante show report")
    report = JustificanteShowOperationReport.model_validate(result, strict=True)
    snapshot = report.snapshot
    require_terminal_receipt_match(
        receipt,
        definition_id=JUSTIFICANTE_SHOW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(snapshot.bucket_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message=_RECEIPT_CONTRADICTION,
    )
    return JustificanteShowPublicResultV1(
        bucket_id=_BUCKET_ID.validate_python(str(snapshot.bucket_id), strict=True),
        snapshot_id=_SNAPSHOT_ID.validate_python(str(snapshot.snapshot_id), strict=True),
        modelo=str(_MODELO.validate_python(snapshot.modelo)),
        filing_year=_FILING_YEAR.validate_python(int(snapshot.filing_year), strict=True),
        period=_validated_period_token(snapshot),
        expediente_id=_EXPEDIENTE_ID.validate_python(str(snapshot.expediente_id), strict=True),
        csv=_CSV.validate_python(str(snapshot.csv), strict=True),
        pdf_sha256=_CONTENT_DIGEST.validate_python(str(snapshot.pdf_sha256), strict=True),
        source_kind=ObservationSourceKind(snapshot.source_kind).value,
        state=SnapshotLifecycleState(snapshot.state).value,
        captured_at=snapshot.captured_at,
    )


def _resolve_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, definition_id: str
) -> ResolvedOperationAccess:
    expected_type = (
        JustificanteListRequest if definition_id == JUSTIFICANTE_LIST_DEFINITION_ID else JustificanteShowRequest
    )
    if request.definition_id != definition_id or not isinstance(request.payload, expected_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def resolve_justificante_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile authority for the local receipt inventory."""
    return _resolve_read_access(request, context, JUSTIFICANTE_LIST_DEFINITION_ID)


def resolve_justificante_show_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile authority for one local receipt detail."""
    return _resolve_read_access(request, context, JUSTIFICANTE_SHOW_DEFINITION_ID)


def build_justificante_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list request to its profile-scoped closed projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=JustificanteListPublicResultV1,
        result_projector=_project_list,
        access_resolver=resolve_justificante_list_access,
    )


def build_justificante_show_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the detail request to its profile-scoped closed projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=JustificanteShowPublicResultV1,
        result_projector=_project_show,
        access_resolver=resolve_justificante_show_access,
    )


__all__ = [
    "JUSTIFICANTE_LIST_DEFINITION_ID",
    "JUSTIFICANTE_SHOW_DEFINITION_ID",
    "JustificanteCaptureSnapshotServiceFactory",
    "JustificanteListPublicResultV1",
    "JustificanteListRequest",
    "JustificanteShowPublicResultV1",
    "JustificanteShowRequest",
    "JustificanteSnapshotSummaryPublicV1",
    "build_justificante_list_definition",
    "build_justificante_list_registration",
    "build_justificante_show_definition",
    "build_justificante_show_registration",
    "resolve_justificante_list_access",
    "resolve_justificante_show_access",
]
