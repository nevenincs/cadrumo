"""Canonical supervised Google Sheets calculation-workbook export.

This module owns the application sequence for a Google calculation-workbook
export: exact active-profile admission, registry snapshot selection, plan
construction, effect truth, and encrypted settlement. The remote transport is
an injected port. Its concrete Google credentials, Drive-root configuration,
preview/apply adapter calls, and sync-run repository are deliberately composed
outside this application package by the authorised production composition step.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    Period,
    require_active_bucket_id,
)
from ...core.time import now
from ...domain.calculations.registry import ModeloId, RegistrySnapshot, RevisionId, bundled_authority
from ..calculations import resolve_relations_from_local_store
from ..operations import (
    CredentialFreeOperationRequest,
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.owner import OperationExecutorContext
from ..storage.calc_sheets import (
    OperatorInputs,
    RelationValues,
    SheetExportPlan,
    build_export_plan,
)

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
_PUBLIC_REQUEST_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

type GoogleSnapshotResolver = Callable[[ModeloId, Period], RegistrySnapshot]
type GoogleExportPlanBuilder = Callable[..., SheetExportPlan]
type GoogleSheetsExportPort = Callable[[str, SheetExportPlan, bool], "GoogleSheetsExportRemoteResult"]


class GoogleSheetsExportOperationRequest(CredentialFreeOperationRequest):
    """Immutable target for one active-profile Google Sheets export."""

    model_config = _PUBLIC_REQUEST_CONFIG

    profile_id: UUID
    modelo: ModeloId
    filing_year: int = Field(ge=1980, le=2200)
    period: str = Field(min_length=1, max_length=32)
    prefill_relations: bool = False
    dry_run: bool = False

    @model_validator(mode="after")
    def _require_canonical_filing_period(self) -> Self:
        Period.from_year_and_code(self.filing_year, self.period)
        return self

    @property
    def filing_period(self) -> Period:
        """Build the typed period at the canonical core boundary."""
        return Period.from_year_and_code(self.filing_year, self.period)


class GoogleSheetsExportRemoteResult(BaseModel):
    """Safe normalized facts returned by the injected remote export port.

    This is the sole application-side translation boundary for concrete Google
    preview and apply records. The port must return ``dry_run`` exactly as it
    received it, so an accidentally inverted composition cannot be settled as
    a successful operation.
    """

    model_config = STRICT_FROZEN_CONFIG

    dry_run: bool
    spreadsheet_exists: bool | None = None
    folder_id: str | None = None
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    value_cells_written: int = Field(ge=0)
    formula_cells_written: int = Field(ge=0)
    protected_ranges_written: int = Field(ge=0)
    tab_count: int = Field(ge=1)
    ranges_to_clear: tuple[str, ...] = ()
    value_cells_changed: int | None = Field(default=None, ge=0)
    value_cells_unchanged: int | None = Field(default=None, ge=0)
    formula_cells_to_write: int | None = Field(default=None, ge=0)


class GoogleSheetsExportOperationResult(BaseModel):
    """Safe completed or previewed workbook facts retained in encrypted custody."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    modelo: ModeloId
    revision: RevisionId
    period: Period
    engine_version: str = Field(min_length=1, max_length=128)
    registry_sha: str = Field(min_length=1, max_length=128)
    dry_run: bool
    spreadsheet_exists: bool | None = None
    folder_id: str | None = None
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    value_cells_written: int = Field(ge=0)
    formula_cells_written: int = Field(ge=0)
    protected_ranges_written: int = Field(ge=0)
    tab_count: int = Field(ge=1)
    ranges_to_clear: tuple[str, ...] = ()
    value_cells_changed: int | None = Field(default=None, ge=0)
    value_cells_unchanged: int | None = Field(default=None, ge=0)
    formula_cells_to_write: int | None = Field(default=None, ge=0)


def _profile_subject(profile_id: UUID) -> str:
    return f"profile:{profile_id}"


def _require_active_profile_subject(
    request: OperationRequest[GoogleSheetsExportOperationRequest],
) -> str:
    """Bind the external write to the exact selected active profile."""
    expected_subject = _profile_subject(request.payload.profile_id)
    if request.subject_ref != expected_subject:
        raise ValueError("Google Sheets export subject does not match its exact profile")
    active_bucket_id = require_active_bucket_id()
    if active_bucket_id != str(request.payload.profile_id):
        raise ValueError("Google Sheets export requires its profile to be active")
    return active_bucket_id


def _resolve_snapshot(modelo: ModeloId, period: Period) -> RegistrySnapshot:
    """Use the one registry authority for temporal snapshot selection."""
    return bundled_authority().snapshot(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
    )


def _unconfigured_google_sheets_export_port(
    _profile_id: str,
    _plan: SheetExportPlan,
    _dry_run: bool,
) -> GoogleSheetsExportRemoteResult:
    """Refuse accidental execution before the production composition binds a port."""
    raise RuntimeError("Google Sheets export transport has not been composed")


class GoogleSheetsExportOperationExecutor:
    """Run the sole Google calculation-workbook export composition."""

    def __init__(
        self,
        *,
        export_port: GoogleSheetsExportPort = _unconfigured_google_sheets_export_port,
        snapshot_resolver: GoogleSnapshotResolver = _resolve_snapshot,
        plan_builder: GoogleExportPlanBuilder = build_export_plan,
    ) -> None:
        self._export_port = export_port
        self._snapshot_resolver = snapshot_resolver
        self._plan_builder = plan_builder

    async def execute(
        self,
        request: OperationRequest[GoogleSheetsExportOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Plan, preview, or apply one export while preserving effect truth."""
        payload = request.payload
        active_bucket_id = _require_active_profile_subject(request)
        await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT)

        snapshot = self._snapshot_resolver(payload.modelo, payload.filing_period)
        await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_PLAN)
        plan = self._build_plan(snapshot, prefill_relations=payload.prefill_relations)

        if payload.dry_run:
            await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW)
            remote = self._export_port(active_bucket_id, plan, True)
            await context.events.effect(OperationEffect.NONE)
        else:
            await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_APPLY)
            await context.events.effect(OperationEffect.UNKNOWN)
            async with context.cancellation.irreversible_section():
                remote = self._export_port(active_bucket_id, plan, False)
            await context.events.effect(OperationEffect.UPDATED)

        if remote.dry_run is not payload.dry_run:
            raise ValueError("Google Sheets export port returned a mismatched dry-run result")
        result = _result(payload, snapshot, plan, remote)
        result_ref = await context.operands.put(result, written_at=now())
        await context.events.phase(GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT)
        return result_ref

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
    export_port: GoogleSheetsExportPort = _unconfigured_google_sheets_export_port,
    snapshot_resolver: GoogleSnapshotResolver = _resolve_snapshot,
    plan_builder: GoogleExportPlanBuilder = build_export_plan,
) -> OperationDefinition:
    """Bind an injected remote-export port without importing concrete adapters."""

    def build() -> GoogleSheetsExportOperationExecutor:
        return GoogleSheetsExportOperationExecutor(
            export_port=export_port,
            snapshot_resolver=snapshot_resolver,
            plan_builder=plan_builder,
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
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP, OperationFrontendProjection.TUI}
        ),
    )


def build_google_sheets_export_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the operation request to its stable public schema identity."""
    return OperationPublicDefinitionRegistrationV1.compose_request_only(
        definition=definition,
        request_schema_id=f"{GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID}.request",
    )


__all__ = [
    "GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID",
    "GOOGLE_SHEETS_EXPORT_PHASE_APPLY",
    "GOOGLE_SHEETS_EXPORT_PHASE_PLAN",
    "GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT",
    "GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW",
    "GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT",
    "GoogleExportPlanBuilder",
    "GoogleSheetsExportOperationExecutor",
    "GoogleSheetsExportOperationRequest",
    "GoogleSheetsExportOperationResult",
    "GoogleSheetsExportPort",
    "GoogleSheetsExportRemoteResult",
    "GoogleSnapshotResolver",
    "build_google_sheets_export_operation_definition",
    "build_google_sheets_export_operation_registration",
]
