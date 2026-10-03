"""Exact-profile borrador capture and separately authorized human/agent reads.

The canonical snapshot service owns resolution and lifecycle transitions. Agent
queries project binding values and coordinates, excluding source provenance and
document prose. Each concrete lifecycle save obtains fresh commit authority;
the existing multi-save lifecycle is not an atomic transaction.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import SnapshotId
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
from ...domain.calculations.registry.ids import BindingId
from ..ledger.commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from ..operations.access_resolution import (
    HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    OperationAccessContext,
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal, PublicNamedScalar, project_facts
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    Borrador100SnapshotService,
    BorradorSourceUrl,
)
from .borrador_100_import import prepare_borrador_100_import
from .borrador_100_operation_ports import (
    Borrador100ArtefactKind,
    Borrador100OperationPorts,
    Borrador100OperationPortsFactory,
)
from .snapshot_base import SnapshotLifecycleState, SnapshotStateFilter

BORRADOR_100_READ_OPERATION_DEFINITION_ID = "live.borrador.100.read"
BORRADOR_100_QUERY_OPERATION_DEFINITION_ID = "live.borrador.100.query"
BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID = "live.borrador.100.import"
type Borrador100ReadKind = Literal["list", "view", "latest"]
_HUMAN_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_ALL_FRONTENDS = frozenset(OperationFrontendProjection)
_IMPORT_FRONTENDS = frozenset({OperationFrontendProjection.CLI})
_BINDING_ID: TypeAdapter[BindingId] = TypeAdapter(BindingId)


class Borrador100ReadRequest(CredentialFreeOperationRequest):
    """Canonical list, unique-prefix view and latest-year selectors."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: Borrador100ReadKind
    state: SnapshotStateFilter = SnapshotStateFilter.ACTIVE
    snapshot_id: Annotated[str, Field(min_length=1)] | None = None
    filing_year: FilingYear | None = None

    @model_validator(mode="after")
    def _selector(self) -> Self:
        if (self.snapshot_id is not None) != (self.kind == "view"):
            raise ValueError("snapshot id belongs only to a view request")
        if (self.filing_year is not None) != (self.kind == "latest"):
            raise ValueError("filing year belongs only to a latest request")
        if self.kind != "list" and self.state is not SnapshotStateFilter.ACTIVE:
            raise ValueError("state filter belongs only to list requests")
        return self


class Borrador100ImportRequest(BaseModel):
    """Protected local source reference; the worker captures its bytes once."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    source_path: Path
    filing_year: FilingYear
    period: PublicPeriod

    @model_validator(mode="after")
    def _coordinate(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("borrador import period differs from filing year")
        return self


class Borrador100QuerySummary(BaseModel):
    """Reviewed metadata without source URLs or printed evidence strings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    snapshot_id: SnapshotId
    filing_year: FilingYear
    period: PublicPeriod
    captured_at: datetime
    binding_count: Annotated[int, Field(ge=0)]
    state: SnapshotLifecycleState

    @model_validator(mode="after")
    def _coordinate(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("borrador summary period differs from filing year")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("borrador capture time requires an explicit timezone")
        return self


class Borrador100SnapshotSummary(Borrador100QuerySummary):
    """Complete existing human summary, including capture provenance."""

    source_url: BorradorSourceUrl


def _validate_bindings(values: tuple[PublicNamedScalar, ...], *, count: int) -> None:
    keys = tuple(row.key for row in values)
    if keys != tuple(sorted(set(keys))) or len(values) != count:
        raise ValueError("borrador bindings must be sorted, unique and complete")
    for row in values:
        _BINDING_ID.validate_python(row.key, strict=True)
        if not isinstance(row.value, (str, PublicDecimal)):
            raise ValueError("borrador bindings preserve only decimal or text values")


def _binding_map(values: tuple[PublicNamedScalar, ...]) -> dict[str, Decimal | str]:
    result: dict[str, Decimal | str] = {}
    for row in values:
        if isinstance(row.value, PublicDecimal):
            result[row.key] = Decimal(row.value.decimal)
        elif isinstance(row.value, str):
            result[row.key] = row.value
        else:
            raise ValueError("invalid borrador binding scalar")
    return result


class Borrador100SnapshotDetail(Borrador100SnapshotSummary):
    """Existing full human view with lossless immutable binding entries."""

    binding_values: tuple[PublicNamedScalar, ...]

    @model_validator(mode="after")
    def _bindings(self) -> Self:
        _validate_bindings(self.binding_values, count=self.binding_count)
        return self

    def binding_map(self) -> dict[str, Decimal | str]:
        """Restore canonical scalar values for existing human presenters."""
        return _binding_map(self.binding_values)


class Borrador100QueryDetail(Borrador100QuerySummary):
    """Authorized binding facts without raw source provenance."""

    binding_values: tuple[PublicNamedScalar, ...]

    @model_validator(mode="after")
    def _bindings(self) -> Self:
        _validate_bindings(self.binding_values, count=self.binding_count)
        return self

    def binding_map(self) -> dict[str, Decimal | str]:
        """Restore the canonical tax/profile binding values."""
        return _binding_map(self.binding_values)


def _validate_read_shape(
    kind: Borrador100ReadKind,
    rows: tuple[Borrador100QuerySummary, ...],
    snapshot: Borrador100QuerySummary | None,
    filing_year: int | None,
) -> None:
    if kind == "list":
        if snapshot is not None or filing_year is not None:
            raise ValueError("list result has incompatible snapshot selectors")
    elif rows or (kind == "view" and (snapshot is None or filing_year is not None)):
        raise ValueError("view/latest result has incompatible rows or selectors")
    elif kind == "latest" and (
        filing_year is None
        or (
            snapshot is not None
            and (snapshot.filing_year != filing_year or snapshot.state is not SnapshotLifecycleState.ACTIVE)
        )
    ):
        raise ValueError("latest result differs from its active-year selector")


class Borrador100ReadProjection(BaseModel):
    """Full human read contract; absent latest snapshot is explicitly retained."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: Borrador100ReadKind
    rows: tuple[Borrador100SnapshotSummary, ...] = ()
    snapshot: Borrador100SnapshotDetail | None = None
    filing_year: FilingYear | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        _validate_read_shape(self.kind, self.rows, self.snapshot, self.filing_year)
        return self


class Borrador100QueryProjection(BaseModel):
    """MCP-safe result schema with no provenance/document prose fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: Borrador100ReadKind
    rows: tuple[Borrador100QuerySummary, ...] = ()
    snapshot: Borrador100QueryDetail | None = None
    filing_year: FilingYear | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        _validate_read_shape(self.kind, self.rows, self.snapshot, self.filing_year)
        return self


class Borrador100ImportProjection(BaseModel):
    """Complete human import facts and canonical parser warnings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    snapshot: Borrador100SnapshotSummary
    extraction_profile_id: str
    extraction_coverage: PublicDecimal
    artefact_kind: Borrador100ArtefactKind
    source_pdf_sha256: ContentDigest
    blank_casillas: tuple[CasillaId, ...]
    warnings: tuple[str, ...]

    @model_validator(mode="after")
    def _source_receipt(self) -> Self:
        if self.snapshot.source_url != "file-import:sha256:" + self.source_pdf_sha256:
            raise ValueError("borrador capture differs from its source digest")
        if self.blank_casillas != tuple(sorted(set(self.blank_casillas))):
            raise ValueError("blank casillas must be sorted and unique")
        if not Decimal("0") <= Decimal(self.extraction_coverage.decimal) <= Decimal("1"):
            raise ValueError("borrador coverage must be a unit fraction")
        return self


class Borrador100ReadExecutionResult(BaseModel):
    """Encrypted full human read retention."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: Borrador100ReadProjection


class Borrador100QueryExecutionResult(BaseModel):
    """Encrypted query retention already excludes source evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: Borrador100QueryProjection


class Borrador100ImportExecutionResult(BaseModel):
    """Encrypted import summary and authorized human-only warnings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: Borrador100ImportProjection


def _summary(snapshot: Borrador100Snapshot) -> Borrador100QuerySummary:
    return Borrador100QuerySummary(
        snapshot_id=snapshot.snapshot_id,
        filing_year=snapshot.filing_year,
        period=PublicPeriod.from_period(snapshot.period),
        captured_at=snapshot.captured_at,
        binding_count=len(snapshot.binding_values),
        state=snapshot.state,
    )


def _human_summary(snapshot: Borrador100Snapshot) -> Borrador100SnapshotSummary:
    return Borrador100SnapshotSummary(**_summary(snapshot).model_dump(), source_url=snapshot.source_url)


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
                        **_summary(selected).model_dump(), binding_values=project_facts(selected.binding_values)
                    )
                )
                return Borrador100QueryExecutionResult(
                    projection=Borrador100QueryProjection(
                        profile_id=payload.profile_id,
                        kind=payload.kind,
                        rows=tuple(_summary(row) for row in snapshots) if payload.kind == "list" else (),
                        snapshot=detail,
                        filing_year=payload.filing_year,
                    )
                )
            human_detail = (
                None
                if selected is None
                else Borrador100SnapshotDetail(
                    **_human_summary(selected).model_dump(), binding_values=project_facts(selected.binding_values)
                )
            )
            return Borrador100ReadExecutionResult(
                projection=Borrador100ReadProjection(
                    profile_id=payload.profile_id,
                    kind=payload.kind,
                    rows=tuple(_human_summary(row) for row in snapshots) if payload.kind == "list" else (),
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
                snapshot=_human_summary(captured),
                extraction_profile_id=prepared.extraction_profile_id,
                extraction_coverage=PublicDecimal(decimal=str(prepared.extraction_coverage)),
                artefact_kind=prepared.artefact_kind,
                source_pdf_sha256=prepared.source_pdf_sha256,
                blank_casillas=prepared.blank_casillas,
                warnings=prepared.warnings,
            )
            return await context.operands.put(Borrador100ImportExecutionResult(projection=projection), written_at=now())

        return await await_cancellation_complete(settle(), task_name="borrador-100-import-settlement")


def resolve_borrador_100_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Keep purposes, destinations and complete all-period disclosures distinct."""
    expected = request.definition_id
    importing = expected == BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID
    query = expected == BORRADOR_100_QUERY_OPERATION_DEFINITION_ID
    if expected not in {
        BORRADOR_100_READ_OPERATION_DEFINITION_ID,
        BORRADOR_100_QUERY_OPERATION_DEFINITION_ID,
        BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
    }:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if type(payload) is not (Borrador100ImportRequest if importing else Borrador100ReadRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, (Borrador100ReadRequest, Borrador100ImportRequest)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    frontends = _IMPORT_FRONTENDS if importing else _ALL_FRONTENDS if query else _HUMAN_FRONTENDS
    access_profile = (
        HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
        if importing
        else RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
        if query
        else HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
    )
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
        OperationDefinition(
            definition_id=definition_id,
            request_type=Borrador100ReadRequest,
            result_type=result_type,
            executor_factory=OperationExecutorFactory(
                request_type=Borrador100ReadRequest,
                executor_type=Borrador100ReadExecutor,
                build=lambda query=query: Borrador100ReadExecutor(factory, query=query),
            ),
            phase_codes=(definition_id,),
            interaction_kinds=frozenset(),
            capabilities=_capabilities(importing=False),
            reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
            permitted_frontends=frontends,
        )
        for definition_id, result_type, query, frontends in (
            (BORRADOR_100_READ_OPERATION_DEFINITION_ID, Borrador100ReadExecutionResult, False, _HUMAN_FRONTENDS),
            (BORRADOR_100_QUERY_OPERATION_DEFINITION_ID, Borrador100QueryExecutionResult, True, _ALL_FRONTENDS),
        )
    )
    importing = OperationDefinition(
        definition_id=BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
        request_type=Borrador100ImportRequest,
        result_type=Borrador100ImportExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=Borrador100ImportRequest,
            executor_type=Borrador100ImportExecutor,
            build=lambda: Borrador100ImportExecutor(factory),
        ),
        phase_codes=(BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(importing=True),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
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
