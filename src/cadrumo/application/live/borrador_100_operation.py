"""Exact-profile borrador capture and separately authorized human/agent reads.

The canonical snapshot service owns resolution and lifecycle transitions. Agent
queries project binding values and coordinates, excluding source provenance and
document prose. Each concrete lifecycle save obtains fresh commit authority;
the existing multi-save lifecycle is not an atomic transaction.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
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
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_scalar import PublicDecimal, project_facts
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .borrador_100 import Borrador100Snapshot, Borrador100SnapshotRepository, Borrador100SnapshotService
from .borrador_100_contracts import (
    Borrador100ImportExecutionResult,
    Borrador100ImportProjection,
    Borrador100ImportRequest,
    Borrador100QueryDetail,
    Borrador100QueryExecutionResult,
    Borrador100QueryProjection,
    Borrador100ReadExecutionResult,
    Borrador100ReadProjection,
    Borrador100ReadRequest,
    Borrador100SnapshotDetail,
    summarize_borrador_100,
    summarize_borrador_100_for_human,
)
from .borrador_100_import import prepare_borrador_100_import
from .borrador_100_operation_ports import Borrador100OperationPorts, Borrador100OperationPortsFactory

BORRADOR_100_READ_OPERATION_DEFINITION_ID = "live.borrador.100.read"
BORRADOR_100_QUERY_OPERATION_DEFINITION_ID = "live.borrador.100.query"
BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID = "live.borrador.100.import"
_HUMAN_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_IMPORT_FRONTENDS = frozenset({OperationFrontendProjection.CLI})


def _compose[T: BaseModel](
    factory: Borrador100OperationPortsFactory,
    request: OperationRequest[T],
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
) -> Borrador100OperationPorts:
    require_operation_profile(request, context, profile_id)
    operation = context.authority_operation
    ports = factory(profile_id=profile_id, operation=operation)
    if (
        ports.profile_id != profile_id
        or ports.operation is not operation
        or ports.repository.bucket_id != str(profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _read_snapshots(
    payload: Borrador100ReadRequest, ports: Borrador100OperationPorts
) -> tuple[Borrador100Snapshot, ...]:
    service = Borrador100SnapshotService(bucket_id=str(payload.profile_id), repository=ports.repository)
    if payload.kind == "list":
        snapshots = service.list_snapshots(state=payload.state.as_lifecycle_state(), operation=ports.operation)
    elif payload.kind == "view":
        if payload.snapshot_id is None:
            raise ValueError("missing borrador snapshot selector")
        snapshots = (service.show(payload.snapshot_id, operation=ports.operation),)
    else:
        if payload.filing_year is None:
            raise ValueError("missing borrador filing year selector")
        latest = service.latest_for_year(filing_year=payload.filing_year, operation=ports.operation)
        snapshots = () if latest is None else (latest,)
    if any(snapshot.bucket_id != str(payload.profile_id) for snapshot in snapshots):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return snapshots


class Borrador100ReadExecutor:
    """Share canonical resolution while retaining distinct reviewed projections."""

    def __init__(self, factory: Borrador100OperationPortsFactory, *, query: bool) -> None:
        """Bind the trusted composition and the registered purpose."""
        self._factory = factory
        self._query = query

    async def execute(
        self, request: OperationRequest[Borrador100ReadRequest], context: OperationExecutorContext
    ) -> str:
        """Read the pinned exact-profile repository without writes or provider calls."""
        expected = (
            BORRADOR_100_QUERY_OPERATION_DEFINITION_ID if self._query else BORRADOR_100_READ_OPERATION_DEFINITION_ID
        )
        if request.definition_id != expected:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(expected)

        def read() -> Borrador100ReadExecutionResult | Borrador100QueryExecutionResult:
            ports = _compose(self._factory, request, context, profile_id=payload.profile_id)
            snapshots = _read_snapshots(payload, ports)
            selected = snapshots[0] if payload.kind != "list" and snapshots else None
            if self._query:
                detail = (
                    None
                    if selected is None
                    else Borrador100QueryDetail(
                        **summarize_borrador_100(selected).model_dump(),
                        binding_values=project_facts(selected.binding_values),
                    )
                )
                return Borrador100QueryExecutionResult(
                    projection=Borrador100QueryProjection(
                        profile_id=payload.profile_id,
                        kind=payload.kind,
                        rows=tuple(summarize_borrador_100(row) for row in snapshots) if payload.kind == "list" else (),
                        snapshot=detail,
                        filing_year=payload.filing_year,
                    )
                )
            human_detail = (
                None
                if selected is None
                else Borrador100SnapshotDetail(
                    **summarize_borrador_100_for_human(selected).model_dump(),
                    binding_values=project_facts(selected.binding_values),
                )
            )
            return Borrador100ReadExecutionResult(
                projection=Borrador100ReadProjection(
                    profile_id=payload.profile_id,
                    kind=payload.kind,
                    rows=tuple(summarize_borrador_100_for_human(row) for row in snapshots)
                    if payload.kind == "list"
                    else (),
                    snapshot=human_detail,
                    filing_year=payload.filing_year,
                )
            )

        result = await await_cancellation_complete(asyncio.to_thread(read), task_name=expected)
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())


class _TrackedBorradorRepository:
    """Delegate all lifecycle reads and fence only actual persistence entry."""

    def __init__(self, repository: Borrador100SnapshotRepository, tracker: LedgerCommitAttemptTracker) -> None:
        self._repository = repository
        self._tracker = tracker

    @property
    def bucket_id(self) -> str:
        return self._repository.bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._repository.exists(snapshot_id)

    def load(self, snapshot_id: str) -> Borrador100Snapshot:
        return self._repository.load(snapshot_id)

    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        return self._repository.list_snapshots()

    def resolve(self, snapshot_id: str) -> Borrador100Snapshot:
        return self._repository.resolve(snapshot_id)

    def save(self, snapshot: Borrador100Snapshot) -> None:
        self._tracker.call_writer(lambda: self._repository.save(snapshot))


class Borrador100ImportExecutor:
    """Prepare once, then run the canonical non-atomic snapshot lifecycle."""

    def __init__(self, factory: Borrador100OperationPortsFactory) -> None:
        """Retain exact-profile composition until admitted worker execution."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[Borrador100ImportRequest], context: OperationExecutorContext
    ) -> str:
        """Persist a validated capture with truthful concrete-writer effects."""
        if request.definition_id != BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID)

        async def settle() -> str:
            ports = await asyncio.to_thread(_compose, self._factory, request, context, profile_id=payload.profile_id)
            prepared = await asyncio.to_thread(
                prepare_borrador_100_import,
                payload.source_path,
                filing_year=payload.filing_year,
                period=payload.period.to_period(),
                operation=ports.operation,
                parser=ports.parser,
            )
            tracker = LedgerCommitAttemptTracker()
            service = Borrador100SnapshotService(
                bucket_id=str(payload.profile_id), repository=_TrackedBorradorRepository(ports.repository, tracker)
            )
            try:
                captured = await run_with_ledger_commit_fence(
                    lambda: service.capture(
                        filing_year=payload.filing_year,
                        period=payload.period.to_period(),
                        captured_at=now(),
                        source_url=prepared.source_url,
                        binding_values=prepared.binding_values,
                        operation=ports.operation,
                    ),
                    tracker=tracker,
                    context=context,
                    task_name=BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
                )
            except BaseException:
                effect = (
                    OperationEffect.UNKNOWN
                    if tracker.has_uncertain_write
                    else OperationEffect.PARTIAL
                    if tracker.confirmed_write
                    else OperationEffect.NONE
                )
                await context.events.effect(effect)
                raise
            if captured.bucket_id != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            effect = OperationEffect.UPDATED if tracker.confirmed_write else OperationEffect.NONE
            await context.events.effect(effect)
            projection = Borrador100ImportProjection(
                profile_id=payload.profile_id,
                snapshot=summarize_borrador_100_for_human(captured),
                extraction_profile_id=prepared.extraction_profile_id,
                extraction_coverage=PublicDecimal(decimal=str(prepared.extraction_coverage)),
                artefact_kind=prepared.artefact_kind,
                source_pdf_sha256=prepared.source_pdf_sha256,
                blank_casillas=prepared.blank_casillas,
                warnings=prepared.warnings,
            )
            return await context.operands.put(Borrador100ImportExecutionResult(projection=projection), written_at=now())

        return await await_cancellation_complete(settle(), task_name="borrador-100-import-settlement")


def _borrador_access_policy(
    definition_id: str,
) -> tuple[bool, frozenset[OperationFrontendProjection], OperationAccessProfile]:
    if definition_id == BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID:
        return (
            True,
            _IMPORT_FRONTENDS,
            HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
        )
    if definition_id == BORRADOR_100_QUERY_OPERATION_DEFINITION_ID:
        return (
            False,
            ALL_OPERATION_FRONTENDS,
            RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
        )
    if definition_id == BORRADOR_100_READ_OPERATION_DEFINITION_ID:
        return (
            False,
            _HUMAN_FRONTENDS,
            HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
        )
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _require_borrador_payload(
    request: OperationRequest[BaseModel], *, importing: bool
) -> Borrador100ReadRequest | Borrador100ImportRequest:
    payload = request.payload
    if type(payload) is not (Borrador100ImportRequest if importing else Borrador100ReadRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, (Borrador100ReadRequest, Borrador100ImportRequest)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return payload


def _require_borrador_subject(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    payload: Borrador100ReadRequest | Borrador100ImportRequest,
) -> None:
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def resolve_borrador_100_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Keep purposes, destinations and complete all-period disclosures distinct."""
    expected = request.definition_id
    importing, frontends, access_profile = _borrador_access_policy(expected)
    payload = _require_borrador_payload(request, importing=importing)
    _require_borrador_subject(request, context, payload)
    require_declared_frontend_and_action(context, frontends=frontends, actions=access_profile.actions)
    require_period_independent_replay_or_authority(context, profile_id=payload.profile_id, definition_id=expected)
    return bind_operation_access_profile(
        context, access_profile, profile_id=payload.profile_id, definition_id=expected, periods=frozenset()
    )


def project_borrador_100_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the registered purpose's exact successful protected result."""
    if type(result) is Borrador100ReadExecutionResult:
        expected = BORRADOR_100_READ_OPERATION_DEFINITION_ID
        projection: Borrador100ReadProjection | Borrador100QueryProjection | Borrador100ImportProjection = (
            result.projection
        )
        effects = frozenset({OperationEffect.NONE})
    elif type(result) is Borrador100QueryExecutionResult:
        expected = BORRADOR_100_QUERY_OPERATION_DEFINITION_ID
        projection = result.projection
        effects = frozenset({OperationEffect.NONE})
    elif type(result) is Borrador100ImportExecutionResult:
        expected = BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID
        projection = result.projection
        effects = frozenset({OperationEffect.NONE, OperationEffect.UPDATED})
    else:
        raise ValueError("invalid borrador result")
    if (
        receipt.identity.definition_id != expected
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect not in effects
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("borrador result differs from its exact-purpose terminal receipt")
    return type(projection).model_validate_json(projection.model_dump_json(), strict=True)


def _capabilities(*, importing: bool) -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE
        if importing
        else OperationSensitiveInputPolicy.NONE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=(
            frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN})
            if importing
            else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
        ),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def build_borrador_100_operation_definitions(
    factory: Borrador100OperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Declare full human reads, safe agent queries and human local PDF import."""
    reads = tuple(
        build_single_phase_definition(
            definition_id=definition_id,
            request_type=Borrador100ReadRequest,
            result_type=result_type,
            executor_type=Borrador100ReadExecutor,
            build=lambda query=query: Borrador100ReadExecutor(factory, query=query),
            capabilities=_capabilities(importing=False),
            permitted_frontends=frontends,
        )
        for definition_id, result_type, query, frontends in (
            (BORRADOR_100_READ_OPERATION_DEFINITION_ID, Borrador100ReadExecutionResult, False, _HUMAN_FRONTENDS),
            (
                BORRADOR_100_QUERY_OPERATION_DEFINITION_ID,
                Borrador100QueryExecutionResult,
                True,
                ALL_OPERATION_FRONTENDS,
            ),
        )
    )
    importing = build_single_phase_definition(
        definition_id=BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
        request_type=Borrador100ImportRequest,
        result_type=Borrador100ImportExecutionResult,
        executor_type=Borrador100ImportExecutor,
        build=lambda: Borrador100ImportExecutor(factory),
        capabilities=_capabilities(importing=True),
        permitted_frontends=_IMPORT_FRONTENDS,
    )
    return (*reads, importing)


def build_borrador_100_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind separate schemas and consent scopes for the three reviewed purposes."""
    models: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
        BORRADOR_100_READ_OPERATION_DEFINITION_ID: (Borrador100ReadRequest, Borrador100ReadProjection),
        BORRADOR_100_QUERY_OPERATION_DEFINITION_ID: (Borrador100ReadRequest, Borrador100QueryProjection),
        BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID: (Borrador100ImportRequest, Borrador100ImportProjection),
    }
    if len(definitions) != len(models) or {definition.definition_id for definition in definitions} != set(models):
        raise ValueError("incomplete borrador operation family")
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=models[definition.definition_id][1],
            result_projector=project_borrador_100_result,
            access_resolver=resolve_borrador_100_access,
        )
        for definition in definitions
    )
