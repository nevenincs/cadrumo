"""Registered local Modelo 036 recording and separately authorized reads.

The existing lifecycle service records an operator's prior external filing;
these operations never file with AEAT. Full human results retain the existing
receipt identifier and note. Agent queries contain closed lifecycle facts and
presence indicators, excluding those raw strings. The canonical declaration
and event write remains one atomic persistence unit.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.clock import now
from ...domain.calculations.registry.censo_modelos import CensoModeloEventKind, active_036_ownership_from_registry
from ..ledger.commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from ..operations.access_resolution import (
    HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    OperationAccessContext,
    OperationAccessProfile,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_frontend_and_action,
    require_period_independent_replay_or_authority,
)
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
)
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_terminal_receipt_match,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .m036_lifecycle import (
    M036DeclarationCommand,
    M036DeclarationResult,
    list_m036_declarations,
    read_m036_declaration,
    record_m036_declaration,
)
from .m036_lifecycle_ports import M036DeclarationRepositoryPort
from .m036_operation_ports import M036OperationPorts, M036OperationPortsFactory

M036_READ_OPERATION_DEFINITION_ID = "modelo.036.read"
M036_QUERY_OPERATION_DEFINITION_ID = "modelo.036.query"
M036_RECORD_OPERATION_DEFINITION_ID = "modelo.036.record"
_HUMAN_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_RECORD_FRONTENDS = frozenset({OperationFrontendProjection.CLI})
type M036ReadKind = Literal["list", "view"]


class M036ReadRequest(CredentialFreeOperationRequest):
    """List every declaration or resolve one canonical id/unique prefix."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: M036ReadKind
    declaration_id: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def _selector(self) -> Self:
        if (self.declaration_id is not None) != (self.kind == "view"):
            raise ValueError("declaration id belongs only to a Modelo 036 view")
        return self


class M036RecordRequest(BaseModel):
    """Protected human declaration of a filing already made externally."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    event_kind: CensoModeloEventKind
    declared_on: date
    sede_justificante: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    note: Annotated[str, Field(max_length=512)] | None = None


class M036DeclarationSnapshot(M036DeclarationResult):
    """Full canonical human record without changing its persisted field meaning."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    def to_declaration(self) -> M036DeclarationResult:
        """Restore the canonical service record for existing human presenters."""
        return M036DeclarationResult.model_validate(self.model_dump())


class M036QueryDeclaration(BaseModel):
    """Closed lifecycle facts; no taxpayer NIF, receipt text or arbitrary note."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    declaration_id: ContentDigest
    event_kind: CensoModeloEventKind
    declared_on: date
    recorded_at: datetime
    justificante_present: bool
    note_present: bool


class M036ReadProjection(BaseModel):
    """Full human list/view preserving canonical order and optional values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: M036ReadKind
    declarations: tuple[M036DeclarationSnapshot, ...]

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if self.kind == "view" and len(self.declarations) != 1:
            raise ValueError("Modelo 036 view must contain exactly one record")
        if any(
            row.profile_id != str(self.profile_id) or row.bucket_id != str(self.profile_id) for row in self.declarations
        ):
            raise ValueError("Modelo 036 records differ from their exact profile")
        return self


class M036QueryProjection(BaseModel):
    """Reviewed agent list/view with one immutable profile identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: M036ReadKind
    declarations: tuple[M036QueryDeclaration, ...]

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if self.kind == "view" and len(self.declarations) != 1:
            raise ValueError("Modelo 036 query view must contain exactly one record")
        if any(row.profile_id != self.profile_id for row in self.declarations):
            raise ValueError("Modelo 036 query records differ from their exact profile")
        return self


class M036RecordProjection(BaseModel):
    """Full protected human receipt of the canonical local atomic record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    declaration: M036DeclarationSnapshot

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if self.declaration.profile_id != str(self.profile_id) or self.declaration.bucket_id != str(self.profile_id):
            raise ValueError("Modelo 036 recorded declaration differs from its profile")
        return self


class M036ReadExecutionResult(BaseModel):
    """Encrypted full human declaration retention."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: M036ReadProjection


class M036QueryExecutionResult(BaseModel):
    """Encrypted agent retention already excludes raw human evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: M036QueryProjection


class M036RecordExecutionResult(BaseModel):
    """Encrypted local record outcome with full authorized human facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: M036RecordProjection


def _compose[T: BaseModel](
    factory: M036OperationPortsFactory,
    request: OperationRequest[T],
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
) -> M036OperationPorts:
    require_operation_profile(request, context, profile_id)
    operation = context.authority_operation
    active_036_ownership_from_registry(operation)
    ports = factory(profile_id=profile_id, operation=operation)
    if ports.profile_id != profile_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _require_row_profile(row: M036DeclarationResult, profile_id: UUID) -> None:
    if row.bucket_id != str(profile_id) or row.profile_id != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _read_declarations(payload: M036ReadRequest, ports: M036OperationPorts) -> tuple[M036DeclarationResult, ...]:
    if payload.kind == "list":
        rows = list_m036_declarations(bucket_id=str(payload.profile_id), ports=ports.lifecycle_ports)
    else:
        if payload.declaration_id is None:
            raise ValueError("missing Modelo 036 declaration selector")
        rows = (
            read_m036_declaration(
                payload.declaration_id, bucket_id=str(payload.profile_id), ports=ports.lifecycle_ports
            ),
        )
    for row in rows:
        _require_row_profile(row, payload.profile_id)
    return rows


class M036ReadExecutor:
    """Run the one canonical read implementation for two reviewed purposes."""

    def __init__(self, factory: M036OperationPortsFactory, *, query: bool) -> None:
        """Bind composition and the exact registered result purpose."""
        self._factory = factory
        self._query = query

    async def execute(self, request: OperationRequest[M036ReadRequest], context: OperationExecutorContext) -> str:
        """Read local encrypted declarations without filing or mutation."""
        expected = M036_QUERY_OPERATION_DEFINITION_ID if self._query else M036_READ_OPERATION_DEFINITION_ID
        if request.definition_id != expected:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(expected)

        def read() -> M036ReadExecutionResult | M036QueryExecutionResult:
            ports = _compose(self._factory, request, context, profile_id=payload.profile_id)
            rows = _read_declarations(payload, ports)
            if self._query:
                return M036QueryExecutionResult(
                    projection=M036QueryProjection(
                        profile_id=payload.profile_id,
                        kind=payload.kind,
                        declarations=tuple(
                            M036QueryDeclaration(
                                profile_id=payload.profile_id,
                                declaration_id=row.declaration_id,
                                event_kind=row.event_kind,
                                declared_on=row.declared_on,
                                recorded_at=row.recorded_at,
                                justificante_present=row.sede_justificante is not None,
                                note_present=row.note is not None,
                            )
                            for row in rows
                        ),
                    )
                )
            return M036ReadExecutionResult(
                projection=M036ReadProjection(
                    profile_id=payload.profile_id,
                    kind=payload.kind,
                    declarations=tuple(M036DeclarationSnapshot.model_validate(row.model_dump()) for row in rows),
                )
            )

        result = await await_cancellation_complete(asyncio.to_thread(read), task_name=expected)
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())


class _TrackedDeclarationRepository:
    """Fence concrete persistence while canonical preparation remains outside COMMIT."""

    def __init__(
        self, repository: M036DeclarationRepositoryPort, tracker: LedgerCommitAttemptTracker, profile_id: UUID
    ) -> None:
        self._repository = repository
        self._tracker = tracker
        self._profile_id = profile_id

    def exists(self, declaration_id: str) -> bool:
        return self._repository.exists(declaration_id)

    def load(self, declaration_id: str) -> M036DeclarationResult:
        row = self._repository.load(declaration_id)
        _require_row_profile(row, self._profile_id)
        return row

    def list_snapshots(self) -> tuple[M036DeclarationResult, ...]:
        rows = self._repository.list_snapshots()
        for row in rows:
            _require_row_profile(row, self._profile_id)
        return rows

    def resolve(self, declaration_id: str) -> M036DeclarationResult:
        row = self._repository.resolve(declaration_id)
        _require_row_profile(row, self._profile_id)
        return row

    def save(self, declaration: M036DeclarationResult) -> None:
        _require_row_profile(declaration, self._profile_id)
        self._tracker.call_writer(lambda: self._repository.save(declaration))

    def save_with_secure_object_writes(
        self, declaration: M036DeclarationResult, extra_writes: tuple[SecureObjectWrite, ...]
    ) -> None:
        _require_row_profile(declaration, self._profile_id)
        self._tracker.call_writer(lambda: self._repository.save_with_secure_object_writes(declaration, extra_writes))


class M036RecordExecutor:
    """Keep canonical sequencing, record identity and event co-commit intact."""

    def __init__(self, factory: M036OperationPortsFactory) -> None:
        """Retain the trusted local lifecycle composition."""
        self._factory = factory

    async def execute(self, request: OperationRequest[M036RecordRequest], context: OperationExecutorContext) -> str:
        """Record a prior external filing under actual atomic writer authority."""
        if request.definition_id != M036_RECORD_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(M036_RECORD_OPERATION_DEFINITION_ID)

        async def settle() -> str:
            ports = await asyncio.to_thread(_compose, self._factory, request, context, profile_id=payload.profile_id)
            tracker = LedgerCommitAttemptTracker()
            tracked = replace(
                ports.lifecycle_ports,
                declaration_repository=_TrackedDeclarationRepository(
                    ports.lifecycle_ports.declaration_repository,
                    tracker,
                    payload.profile_id,
                ),
            )
            command = M036DeclarationCommand(
                profile_id=str(payload.profile_id),
                event_kind=payload.event_kind,
                declared_on=payload.declared_on,
                sede_justificante=payload.sede_justificante,
                note=payload.note,
            )
            try:
                result = await run_with_ledger_commit_fence(
                    lambda: record_m036_declaration(command, bucket_id=str(payload.profile_id), ports=tracked),
                    tracker=tracker,
                    context=context,
                    task_name=M036_RECORD_OPERATION_DEFINITION_ID,
                )
            except BaseException:
                await context.events.effect(
                    OperationEffect.UNKNOWN if tracker.has_possible_write else OperationEffect.NONE
                )
                raise
            _require_row_profile(result, payload.profile_id)
            if not tracker.confirmed_write or tracker.has_uncertain_write or tracker.attempt_count != 1:
                raise ValueError("Modelo 036 lifecycle disagrees with its atomic writer receipt")
            await context.events.effect(OperationEffect.UPDATED)
            return await context.operands.put(
                M036RecordExecutionResult(
                    projection=M036RecordProjection(
                        profile_id=payload.profile_id,
                        declaration=M036DeclarationSnapshot.model_validate(result.model_dump()),
                    )
                ),
                written_at=now(),
            )

        return await await_cancellation_complete(settle(), task_name="m036-record-settlement")


def resolve_m036_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize exact purpose/profile and complete reviewed destination disclosure."""
    expected = request.definition_id
    recording, query = _m036_access_mode(expected)
    payload = require_access_request_profile_payload(
        request,
        definition_id=expected,
        payload_type=M036RecordRequest if recording else M036ReadRequest,
        access_profile_id=context.profile_id,
    )
    frontends, access_profile = _m036_access_policy(recording=recording, query=query)
    require_declared_frontend_and_action(context, frontends=frontends, actions=access_profile.actions)
    require_period_independent_replay_or_authority(context, profile_id=payload.profile_id, definition_id=expected)
    return bind_operation_access_profile(
        context, access_profile, profile_id=payload.profile_id, definition_id=expected, periods=frozenset()
    )


def _m036_access_mode(expected: str) -> tuple[bool, bool]:
    if expected not in {
        M036_READ_OPERATION_DEFINITION_ID,
        M036_QUERY_OPERATION_DEFINITION_ID,
        M036_RECORD_OPERATION_DEFINITION_ID,
    }:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return expected == M036_RECORD_OPERATION_DEFINITION_ID, expected == M036_QUERY_OPERATION_DEFINITION_ID


def _m036_access_policy(
    *,
    recording: bool,
    query: bool,
) -> tuple[frozenset[OperationFrontendProjection], OperationAccessProfile]:
    frontends = _RECORD_FRONTENDS if recording else ALL_OPERATION_FRONTENDS if query else _HUMAN_FRONTENDS
    access_profile = (
        HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
        if recording
        else RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
        if query
        else HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
    )
    return frontends, access_profile


def project_m036_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the matching settled purpose's complete typed result."""
    if type(result) is M036ReadExecutionResult:
        expected = M036_READ_OPERATION_DEFINITION_ID
        projection: M036ReadProjection | M036QueryProjection | M036RecordProjection = result.projection
        effect = OperationEffect.NONE
    elif type(result) is M036QueryExecutionResult:
        expected = M036_QUERY_OPERATION_DEFINITION_ID
        projection = result.projection
        effect = OperationEffect.NONE
    elif type(result) is M036RecordExecutionResult:
        expected = M036_RECORD_OPERATION_DEFINITION_ID
        projection = result.projection
        effect = OperationEffect.UPDATED
    else:
        raise ValueError("invalid Modelo 036 execution result")
    require_terminal_receipt_match(
        receipt,
        definition_id=expected,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        message="Modelo 036 result differs from its exact-purpose terminal receipt",
    )
    return type(projection).model_validate_json(projection.model_dump_json(), strict=True)


def build_m036_operation_definitions(factory: M036OperationPortsFactory) -> tuple[OperationDefinition, ...]:
    """Enroll the complete local recording and separately reviewed read family."""
    reads = tuple(
        build_single_phase_definition(
            definition_id=definition_id,
            request_type=M036ReadRequest,
            result_type=result_type,
            executor_type=M036ReadExecutor,
            build=lambda query=query: M036ReadExecutor(factory, query=query),
            capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
            permitted_frontends=frontends,
        )
        for definition_id, result_type, query, frontends in (
            (M036_READ_OPERATION_DEFINITION_ID, M036ReadExecutionResult, False, _HUMAN_FRONTENDS),
            (M036_QUERY_OPERATION_DEFINITION_ID, M036QueryExecutionResult, True, ALL_OPERATION_FRONTENDS),
        )
    )
    recording = build_single_phase_definition(
        definition_id=M036_RECORD_OPERATION_DEFINITION_ID,
        request_type=M036RecordRequest,
        result_type=M036RecordExecutionResult,
        executor_type=M036RecordExecutor,
        build=lambda: M036RecordExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=_RECORD_FRONTENDS,
    )
    return (*reads, recording)


def build_m036_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind closed schemas and independent human/query result consent scopes."""
    models: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
        M036_READ_OPERATION_DEFINITION_ID: (M036ReadRequest, M036ReadProjection),
        M036_QUERY_OPERATION_DEFINITION_ID: (M036ReadRequest, M036QueryProjection),
        M036_RECORD_OPERATION_DEFINITION_ID: (M036RecordRequest, M036RecordProjection),
    }
    if len(definitions) != len(models) or {definition.definition_id for definition in definitions} != set(models):
        raise ValueError("incomplete Modelo 036 operation family")
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=models[definition.definition_id][1],
            result_projector=project_m036_operation_result,
            access_resolver=resolve_m036_operation_access,
        )
        for definition in definitions
    )
