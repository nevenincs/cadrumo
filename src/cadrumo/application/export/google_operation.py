"""Canonical supervised Google Sheets calculation-workbook export.

This module owns the application sequence for a Google calculation-workbook
export: exact active-profile admission, registry snapshot selection, plan
construction, effect truth, and encrypted settlement. The remote transport is
an injected port. Its concrete Google credentials, Drive-root configuration,
preview/apply adapter calls, and sync-run repository are deliberately composed
outside this application package by the authorised production composition step.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.bucket_pointer import require_active_bucket_id
from ...core.capabilities import ServiceCapability
from ...core.errors.hierarchy import CadrumoError, InternalInvariantError, pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect, OperationInteractionKind
from ...core.operations import profile_operation_subject as _profile_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.ids import (
    ModeloId,
    RevisionId,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..calculations.relation_prefill import resolve_relations_from_local_store
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..storage.calc_sheets.engine import build_export_plan
from ..storage.calc_sheets.records import OperatorInputs, RelationValues, SheetExportPlan, SheetReviewMetadata
from ..storage.calc_sheets.review_workbook import ReviewLabelResolver, build_review_workbook
from ..user_profile.capabilities import resolve_active_capability
from .managed_artifact_ports import ManagedArtifactKind
from .publication_receipt import (
    PublicationReceipt,
    PublicationState,
    ReadableExportAuthorization,
    ReadablePayloadCategory,
)
from .review_snapshot import CalculationReviewSelection, ReviewSelection, ReviewSnapshot

GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID = "export.google-sheets"
GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT = "export.google-sheets.preflight"
GOOGLE_SHEETS_EXPORT_PHASE_PLAN = "export.google-sheets.plan"
GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW = "export.google-sheets.preview"
GOOGLE_SHEETS_EXPORT_PHASE_APPLY = "export.google-sheets.apply"
GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT = "export.google-sheets.settlement"
_GOOGLE_SHEETS_EXPORT_PHASES = (
    GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
    GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
    GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW,
    GOOGLE_SHEETS_EXPORT_PHASE_APPLY,
    GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT,
)

type GoogleSnapshotResolver = Callable[[ModeloId, Period], RegistrySnapshot]
type GoogleExportPlanBuilder = Callable[..., SheetExportPlan]


class GoogleSheetsExportCapabilityDisabledError(CadrumoError):
    """The active profile has not admitted Google workbook export."""


class GoogleSheetsExportRootFolderRequiredError(CadrumoError):
    """The composed transport has no configured Drive root folder."""


class GoogleSheetsExportClientMissingError(CadrumoError):
    """This installation carries no usable Google OAuth client metadata."""


class GoogleSheetsExportTokenMissingError(CadrumoError):
    """The active profile has no persisted Google OAuth token."""


class GoogleSheetsExportAuthDependencyError(CadrumoError):
    """The Google authentication dependency is unavailable."""


class GoogleSheetsExportActiveProfileRequiredError(CadrumoError):
    """The requested export profile is no longer the active profile."""


class GoogleSheetsExportSubjectMismatchError(CadrumoError):
    """The supervised subject contradicts the export payload profile."""


class GoogleSheetsExportOperationRequest(CredentialFreeOperationRequest):
    """Immutable target for one active-profile Google Sheets export."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    modelo: ModeloId
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=32)
    prefill_relations: bool = False
    dry_run: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_canonical_filing_period(self) -> Self:
        Period.from_year_and_code(self.filing_year, self.period)
        return self

    @property
    def filing_period(self) -> Period:
        """Build the typed period at the canonical core boundary."""
        return Period.from_year_and_code(self.filing_year, self.period)


class GoogleSheetsWorkbookWriteFacts(BaseModel):
    """What one Google Sheets workbook write did, previewed or applied.

    One concept with two carriers: the port returns these facts, and the
    operation retains them in encrypted custody alongside the provenance
    identifying which calculation produced them. Declaring them once keeps the
    carriers from drifting field by field -- a counter added to the port's
    return and not to the retained record would read as a silent zero
    downstream.

    ``dry_run`` belongs here rather than to either carrier because the port
    must return it exactly as received, so a preview can never be settled as an
    applied write.
    """

    model_config = STRICT_FROZEN_CONFIG

    dry_run: bool
    root_folder_id: str | None = None
    spreadsheet_exists: bool | None = None
    folder_id: str | None = None
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    value_cells_written: NonNegativeInt
    formula_cells_written: NonNegativeInt
    protected_ranges_written: NonNegativeInt
    tab_count: int = Field(ge=1)
    ranges_to_clear: tuple[str, ...] = ()
    value_cells_changed: int | None = Field(default=None, ge=0)
    value_cells_unchanged: int | None = Field(default=None, ge=0)
    formula_cells_to_write: int | None = Field(default=None, ge=0)


class GoogleSheetsExportRemoteResult(GoogleSheetsWorkbookWriteFacts):
    """Safe normalized facts returned by the injected remote export port.

    This is the sole application-side translation boundary for concrete Google
    preview and apply records. The port must return ``dry_run`` exactly as it
    received it, so an accidentally inverted composition cannot be settled as
    a successful operation.
    """

    model_config = STRICT_FROZEN_CONFIG


class GoogleSheetsExportOperationResult(GoogleSheetsWorkbookWriteFacts):
    """Safe completed or previewed workbook facts retained in encrypted custody."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    modelo: ModeloId
    revision: RevisionId
    period: Period
    engine_version: str = Field(min_length=1, max_length=128)
    registry_sha: str = Field(min_length=1, max_length=128)


class GoogleSheetsExportPublicResultV1(GoogleSheetsWorkbookWriteFacts):
    """Renderer-neutral settled export result with no domain-only field types."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    modelo: ModeloId
    revision: RevisionId
    period: str = Field(min_length=1, max_length=32)
    filing_year: FilingYear
    engine_version: str = Field(min_length=1, max_length=128)
    registry_sha: str = Field(min_length=1, max_length=128)


class GoogleSheetsExportPreparedPort(Protocol):
    """In-memory prepared transport whose remaining call may mutate remotely."""

    def execute(self, plan: SheetExportPlan, dry_run: bool) -> GoogleSheetsExportRemoteResult:
        """Preview or apply the plan after configuration and authentication succeeded."""
        ...


type GoogleSheetsExportPreparePort = Callable[[str], GoogleSheetsExportPreparedPort]


def project_google_sheets_export_result(
    result: BaseModel,
    _terminal_receipt: object,
) -> BaseModel:
    """Project the private settled result into its strict public V1 shape."""
    if not isinstance(result, GoogleSheetsExportOperationResult):
        raise TypeError("Google Sheets export result projector received the wrong result type")
    return GoogleSheetsExportPublicResultV1(
        **result.model_dump(exclude={"period"}),
        period=result.period.registry_token,
        filing_year=result.period.filing_year,
    )


def _require_active_profile(profile_id: UUID) -> str:
    """Bind an export to the exact selected active profile."""
    active_bucket_id = require_active_bucket_id()
    if active_bucket_id != str(profile_id):
        raise GoogleSheetsExportActiveProfileRequiredError("Google Sheets export requires its profile to be active")
    return active_bucket_id


def _require_active_profile_subject(
    request: OperationRequest[GoogleSheetsExportOperationRequest],
) -> None:
    """Bind the supervised request subject to the selected active profile."""
    if request.subject_ref != _profile_subject(str(request.payload.profile_id)):
        raise GoogleSheetsExportSubjectMismatchError("Google Sheets export subject does not match its exact profile")


def _resolve_snapshot(modelo: ModeloId, period: Period) -> RegistrySnapshot:
    """Use the one registry authority for temporal snapshot selection."""
    with bundled_indexed_authority().operation() as operation:
        return operation.snapshot(
            modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
        )


def _unconfigured_google_sheets_export_prepare_port(_profile_id: str) -> GoogleSheetsExportPreparedPort:
    """Refuse accidental execution before the production composition binds a port."""
    raise InternalInvariantError("Google Sheets export transport has not been composed")


def prepare_google_review_plan(
    snapshot: ReviewSnapshot,
    *,
    selection: ReviewSelection,
    publication: PublicationReceipt,
    authorization: ReadableExportAuthorization,
    exported_at: datetime,
    label: ReviewLabelResolver,
) -> SheetExportPlan[SheetReviewMetadata]:
    """Prepare a new review after runtime disclosure, without any provider access.

    The caller resolves the selected saved snapshot once and admits disclosure
    through the runtime. These correlation checks cannot grant that authority.
    Published or uncertain receipts belong to reconciliation, never population.
    """
    if not resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled:
        raise GoogleSheetsExportCapabilityDisabledError("Google Sheets export capability is disabled")
    _require_active_profile(selection.profile_id)
    if (
        snapshot.selection != selection
        or publication.profile_id != selection.profile_id
        or publication.snapshot_digest != snapshot.snapshot_digest
        or authorization.profile_id != selection.profile_id
        or authorization.publication_id != publication.publication_id
        or authorization.root_folder_id != publication.root.artifact_id
        or authorization.snapshot_digest != snapshot.snapshot_digest
    ):
        raise GoogleSheetsExportSubjectMismatchError("Review snapshot, publication and disclosure identities differ")
    if publication.state is not PublicationState.PREPARED or publication.artifacts:
        raise GoogleSheetsExportSubjectMismatchError("Existing publication requires reconciliation, not population")
    categories = set(authorization.payload_categories)
    required: set[ReadablePayloadCategory] = (
        {ReadablePayloadCategory.CALCULATION} if isinstance(selection, CalculationReviewSelection) else set()
    )
    if selection.kind == "ledger" or snapshot.ledger_rows:
        required.add(ReadablePayloadCategory.LEDGER)
    if not required <= categories:
        raise GoogleSheetsExportSubjectMismatchError("Review content exceeds the admitted disclosure categories")
    return build_review_workbook(
        snapshot,
        publication_id=publication.publication_id,
        exported_at=exported_at,
        label=label,
    )


class GoogleSheetsReviewPreparedPort(Protocol):
    """Receipt-bound transport composed after profile and destination admission."""

    def execute(
        self,
        plan: SheetExportPlan[SheetReviewMetadata],
        publication: PublicationReceipt,
    ) -> PublicationReceipt:
        """Populate only this new publication and return acknowledged checkpoints."""
        ...


def publish_google_review(
    snapshot: ReviewSnapshot,
    *,
    selection: ReviewSelection,
    publication: PublicationReceipt,
    authorization: ReadableExportAuthorization,
    prepared: GoogleSheetsReviewPreparedPort,
    exported_at: datetime,
    label: ReviewLabelResolver,
) -> PublicationReceipt:
    """Hand a new baseline to admitted transport inside the supervisor's effect guard.

    The caller must retain UNKNOWN until transport settlement and persist the
    returned receipt, including partial/uncertain outcomes. A completed remote
    document is never selected by workbook name or used for a second population.
    """
    plan = prepare_google_review_plan(
        snapshot,
        selection=selection,
        publication=publication,
        authorization=authorization,
        exported_at=exported_at,
        label=label,
    )
    result = prepared.execute(plan, publication)
    if (
        result.publication_id != publication.publication_id
        or result.profile_id != publication.profile_id
        or result.root != publication.root
        or result.snapshot_digest != publication.snapshot_digest
        or result.predecessor_publication_id != publication.predecessor_publication_id
        or result.package_digest != publication.package_digest
    ):
        raise InternalInvariantError("Review transport returned an unrelated publication receipt")
    if result.state not in {PublicationState.PUBLISHED, PublicationState.PARTIAL, PublicationState.UNCERTAIN}:
        raise InternalInvariantError("Review transport returned an unfinished publication checkpoint")
    if result.state is PublicationState.PUBLISHED:
        sheets = tuple(item for item in result.artifacts if item.kind is ManagedArtifactKind.REVIEW_SHEET)
        if len(sheets) != 1:
            raise InternalInvariantError("Published review requires exactly one native workbook receipt")
    return result


class GoogleSheetsExportService:
    """Canonical application planning and remote handoff for one workbook export."""

    def __init__(
        self,
        *,
        prepare_port: GoogleSheetsExportPreparePort = _unconfigured_google_sheets_export_prepare_port,
        snapshot_resolver: GoogleSnapshotResolver = _resolve_snapshot,
        plan_builder: GoogleExportPlanBuilder = build_export_plan,
    ) -> None:
        """Bind the ports and policies this export service resolves through."""
        self._prepare_port = prepare_port
        self._snapshot_resolver = snapshot_resolver
        self._plan_builder = plan_builder

    def execute(self, payload: GoogleSheetsExportOperationRequest) -> GoogleSheetsExportOperationResult:
        """Perform the synchronous application service for a frontend consumer.

        The registered executor below owns supervision, durability, and effect
        truth. This service is deliberately the one reusable business path for
        legacy synchronous frontends while they are migrated to the supervisor;
        it never imports an adapter or constructs a concrete transport.
        """
        active_bucket_id = self.admit(payload)
        snapshot = self.snapshot(payload)
        plan = self.plan(snapshot, prefill_relations=payload.prefill_relations)
        prepared = self.prepare(active_bucket_id)
        remote = self.remote(prepared, plan, dry_run=payload.dry_run)
        return self.result(payload, snapshot, plan, remote)

    def admit(self, payload: GoogleSheetsExportOperationRequest) -> str:
        """Apply the active-profile and egress-capability admissions once."""
        if not resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled:
            raise GoogleSheetsExportCapabilityDisabledError("Google Sheets export capability is disabled")
        return _require_active_profile(payload.profile_id)

    def snapshot(self, payload: GoogleSheetsExportOperationRequest) -> RegistrySnapshot:
        """Resolve the exact temporal registry authority snapshot."""
        return self._snapshot_resolver(payload.modelo, payload.filing_period)

    def plan(self, snapshot: RegistrySnapshot, *, prefill_relations: bool) -> SheetExportPlan:
        """Build one canonical workbook plan from the resolved snapshot.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
        """
        return self._build_plan(snapshot, prefill_relations=prefill_relations)

    def prepare(self, active_bucket_id: str) -> GoogleSheetsExportPreparedPort:
        """Resolve credentials and mandatory root configuration before mutation."""
        return self._prepare_port(active_bucket_id)

    def remote(
        self,
        prepared: GoogleSheetsExportPreparedPort,
        plan: SheetExportPlan,
        *,
        dry_run: bool,
    ) -> GoogleSheetsExportRemoteResult:
        """Cross the injected remote boundary without choosing an adapter."""
        remote = prepared.execute(plan, dry_run)
        if remote.dry_run is not dry_run:
            raise ValueError("Google Sheets export port returned a mismatched dry-run result")
        return remote

    @staticmethod
    def result(
        payload: GoogleSheetsExportOperationRequest,
        snapshot: RegistrySnapshot,
        plan: SheetExportPlan,
        remote: GoogleSheetsExportRemoteResult,
    ) -> GoogleSheetsExportOperationResult:
        """Normalize the safe, durable application result once.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
        """
        return _result(payload, snapshot, plan, remote)

    def _build_plan(self, snapshot: RegistrySnapshot, *, prefill_relations: bool) -> SheetExportPlan:
        if prefill_relations:
            return self._plan_builder(
                snapshot,
                operator_inputs=OperatorInputs(),
                relation_resolver=resolve_relations_from_local_store,
            )
        return self._plan_builder(
            snapshot,
            operator_inputs=OperatorInputs(),
            relation_values=RelationValues(),
        )


class GoogleSheetsExportOperationExecutor:
    """Run the sole Google calculation-workbook export under supervision."""

    def __init__(
        self,
        *,
        service: GoogleSheetsExportService,
    ) -> None:
        """Bind the service and supervision this executor runs the export under."""
        self._service = service

    async def execute(
        self,
        request: OperationRequest[GoogleSheetsExportOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Plan, preview, or apply one export while preserving effect truth."""
        payload = request.payload
        _require_active_profile_subject(request)
        await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT)

        active_bucket_id = self._service.admit(payload)
        snapshot = self._service.snapshot(payload)
        await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_PLAN)
        plan = self._service.plan(snapshot, prefill_relations=payload.prefill_relations)
        prepared = await asyncio.to_thread(self._service.prepare, active_bucket_id)

        if payload.dry_run:
            await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW)
            remote = await asyncio.to_thread(self._service.remote, prepared, plan, dry_run=True)
            await context.events.effect(OperationEffect.NONE)
        else:
            await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_APPLY)
            await context.events.effect(OperationEffect.UNKNOWN)
            async with context.cancellation.irreversible_section():
                remote = await asyncio.to_thread(self._service.remote, prepared, plan, dry_run=False)
            await context.events.effect(OperationEffect.UPDATED)

        result = self._service.result(payload, snapshot, plan, remote)
        result_ref = await context.operands.put(result, written_at=now())
        await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT)
        return result_ref


def _result(
    payload: GoogleSheetsExportOperationRequest,
    snapshot: RegistrySnapshot,
    plan: SheetExportPlan,
    remote: GoogleSheetsExportRemoteResult,
) -> GoogleSheetsExportOperationResult:
    return GoogleSheetsExportOperationResult(
        profile_id=payload.profile_id,
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        period=payload.filing_period,
        engine_version=plan.metadata.engine_version,
        registry_sha=plan.metadata.registry_sha,
        dry_run=remote.dry_run,
        root_folder_id=remote.root_folder_id,
        spreadsheet_exists=remote.spreadsheet_exists,
        folder_id=remote.folder_id,
        spreadsheet_id=remote.spreadsheet_id,
        spreadsheet_url=remote.spreadsheet_url,
        value_cells_written=remote.value_cells_written,
        formula_cells_written=remote.formula_cells_written,
        protected_ranges_written=remote.protected_ranges_written,
        tab_count=remote.tab_count,
        ranges_to_clear=remote.ranges_to_clear,
        value_cells_changed=remote.value_cells_changed,
        value_cells_unchanged=remote.value_cells_unchanged,
        formula_cells_to_write=remote.formula_cells_to_write,
    )


def build_google_sheets_export_operation_definition(
    *,
    prepare_port: GoogleSheetsExportPreparePort = _unconfigured_google_sheets_export_prepare_port,
    snapshot_resolver: GoogleSnapshotResolver = _resolve_snapshot,
    plan_builder: GoogleExportPlanBuilder = build_export_plan,
) -> OperationDefinition:
    """Bind an injected remote-export port without importing concrete adapters."""

    def build() -> GoogleSheetsExportOperationExecutor:
        return GoogleSheetsExportOperationExecutor(
            service=build_google_sheets_export_service(
                prepare_port=prepare_port,
                snapshot_resolver=snapshot_resolver,
                plan_builder=plan_builder,
            ),
        )

    return OperationDefinition(
        definition_id=GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
        request_type=GoogleSheetsExportOperationRequest,
        result_type=GoogleSheetsExportOperationResult,
        executor_factory=OperationExecutorFactory(
            request_type=GoogleSheetsExportOperationRequest,
            executor_type=GoogleSheetsExportOperationExecutor,
            build=build,
        ),
        phase_codes=_GOOGLE_SHEETS_EXPORT_PHASES,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_google_sheets_export_service(
    *,
    prepare_port: GoogleSheetsExportPreparePort = _unconfigured_google_sheets_export_prepare_port,
    snapshot_resolver: GoogleSnapshotResolver = _resolve_snapshot,
    plan_builder: GoogleExportPlanBuilder = build_export_plan,
) -> GoogleSheetsExportService:
    """Build the reusable application service from injected boundary ports."""
    return GoogleSheetsExportService(
        prepare_port=prepare_port,
        snapshot_resolver=snapshot_resolver,
        plan_builder=plan_builder,
    )


def build_google_sheets_export_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the operation request and safe settled result to public identities."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID}.request",
            schema_version=1,
            model_type=GoogleSheetsExportOperationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID}.result",
            schema_version=1,
            model_type=GoogleSheetsExportPublicResultV1,
        ),
        result_projector=project_google_sheets_export_result,
    )


__all__ = [
    "GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID",
    "GOOGLE_SHEETS_EXPORT_PHASE_APPLY",
    "GOOGLE_SHEETS_EXPORT_PHASE_PLAN",
    "GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT",
    "GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW",
    "GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT",
    "GoogleExportPlanBuilder",
    "GoogleSheetsExportActiveProfileRequiredError",
    "GoogleSheetsExportAuthDependencyError",
    "GoogleSheetsExportCapabilityDisabledError",
    "GoogleSheetsExportClientMissingError",
    "GoogleSheetsExportOperationExecutor",
    "GoogleSheetsExportOperationRequest",
    "GoogleSheetsExportOperationResult",
    "GoogleSheetsExportPreparePort",
    "GoogleSheetsExportPreparedPort",
    "GoogleSheetsExportPublicResultV1",
    "GoogleSheetsExportRemoteResult",
    "GoogleSheetsExportRootFolderRequiredError",
    "GoogleSheetsExportService",
    "GoogleSheetsExportSubjectMismatchError",
    "GoogleSheetsExportTokenMissingError",
    "GoogleSnapshotResolver",
    "build_google_sheets_export_operation_definition",
    "build_google_sheets_export_operation_registration",
    "build_google_sheets_export_service",
    "project_google_sheets_export_result",
]
