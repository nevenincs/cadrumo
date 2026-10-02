"""Registered exact-profile modelo binding and readiness reads.

The registry and state-projection services remain the only authorities for
these answers. This module owns their operation custody and public wire form.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.query_reports import ModeloBindingQueryRow, ModeloBindingsReport
from ...domain.user_profile.errors import ProfileNotFoundError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
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
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..state_projection import (
    CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS,
    ModeloReadinessRequest,
    ProjectionModeloReadiness,
    build_modelo_readiness_reports,
)
from ..state_projection_ports import StateProjectionReadPorts
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .binding_readiness import profile_resolvable_binding_ids
from .data_inventory import DataInventoryCasilla, DataInventoryChecklist, data_inventory_checklist
from .registry_discovery import (
    registry_bindings,
    registry_bindings_for_scope,
    registry_bindings_for_year,
    registry_modelo_codes,
)
from .work_addressing import law_selected_revision_for_work_target

MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID = "modelo.bindings.list"
MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID = "modelo.bindings.resolve"
MODELO_REQUIRES_OPERATION_DEFINITION_ID = "modelo.requires"
MODELO_READINESS_OPERATION_DEFINITION_ID = "modelo.readiness"

_Modelo = Annotated[str, Field(min_length=1, max_length=16)]
_Token = Annotated[str, Field(min_length=1, max_length=128)]
_Value = Annotated[str, Field(max_length=16_384)]


@dataclass(frozen=True, slots=True)
class ModeloQueryReadPorts:
    """Read capability for one admitted profile."""

    bucket_id: str
    read_ports: StateProjectionReadPorts


class ModeloQueryReadPortsFactory(Protocol):
    """Executable composition binds the readiness reader to a profile."""

    def __call__(self, *, bucket_id: str) -> ModeloQueryReadPorts:
        """Return the reader for the exact requested profile."""
        ...


class ModeloBindingsListRequest(CredentialFreeOperationRequest):
    """Registry filters; an omitted modelo retains registry order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo | None = None
    year: FilingYear | None = None
    period_code: _Token | None = None
    missing: bool = False
    as_of: date | None = None
    catalogue_only: bool = False

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if self.catalogue_only and (
            self.modelo is not None
            or self.year is not None
            or self.period_code is not None
            or self.missing
            or self.as_of is not None
        ):
            raise ValueError("catalogue-only listing cannot carry binding filters")
        if self.as_of is not None and self.year is None:
            raise ValueError("as_of requires a filing year")
        if self.year is not None and self.period_code is not None:
            Period.from_year_and_code(self.year, self.period_code)
        return self


class ModeloBindingOverride(BaseModel):
    """One temporary preview value, never a saved binding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding_id: _Token
    value: _Value


class ModeloBindingsResolveRequest(CredentialFreeOperationRequest):
    """One exact target and temporary overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo
    period: PublicPeriod
    as_of: date | None = None
    overrides: tuple[ModeloBindingOverride, ...] = ()

    @model_validator(mode="after")
    def _unique_overrides(self) -> Self:
        ids = tuple(row.binding_id for row in self.overrides)
        if len(set(ids)) != len(ids):
            raise ValueError("binding overrides must have unique ids")
        return self


class ModeloRequiresRequest(CredentialFreeOperationRequest):
    """One exact data-inventory target."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo
    period: PublicPeriod
    language: OutputLanguage = OutputLanguage.ES


class ModeloReadinessOperationRequest(CredentialFreeOperationRequest):
    """One readiness target; absent period means the annual 0A preflight."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo
    filing_year: FilingYear
    period: PublicPeriod | None = None
    revision_id: _Token | None = None
    language: OutputLanguage = OutputLanguage.ES

    @model_validator(mode="after")
    def _matching_period(self) -> Self:
        if self.period is not None and self.period.filing_year != self.filing_year:
            raise ValueError("readiness period must match filing year")
        return self


class ModeloBindingEncodedOptionV1(BaseModel):
    """One complete registry boolean encoding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    encoded_value: str
    boolean_meaning: bool
    registry_value: str


class ModeloBindingRowV1(BaseModel):
    """Grounded binding row shared by list and preview."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    binding_id: str
    source: str
    readiness_locale_key: str
    typed_enum: str | None
    input_channel: str
    borrador_capable: bool
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    relation_inputs: tuple[str, ...]
    encoded_options: tuple[ModeloBindingEncodedOptionV1, ...]
    override: str | None = None

    @classmethod
    def from_report_row(
        cls, report: ModeloBindingsReport, row: ModeloBindingQueryRow, *, override: str | None = None
    ) -> Self:
        """Copy one registry row with its scope and complete legal grounding."""
        return cls(
            modelo=report.code,
            revision=report.revision,
            filing_year=report.filing_year,
            period=report.period,
            binding_id=row.binding_id,
            source=row.provider.kind,
            readiness_locale_key=CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[row.provider.kind],
            typed_enum=row.typed_enum,
            input_channel=row.input_channel,
            borrador_capable=row.borrador_capable,
            legal_refs=row.legal_refs,
            source_refs=row.source_refs,
            relation_inputs=row.relation_inputs,
            encoded_options=tuple(
                ModeloBindingEncodedOptionV1(
                    encoded_value=item.encoded_value,
                    boolean_meaning=item.boolean_meaning,
                    registry_value=item.registry_value,
                )
                for item in row.encoded_options
            ),
            override=override,
        )


class ModeloBindingsListProjection(BaseModel):
    """Full ordered registry listing with explicit filters and count."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.bindings.list"] = "modelo.bindings.list"
    authority_generation: ContentDigest
    profile_id: UUID
    modelo_filter: str | None
    year_filter: int | None
    period_filter: str | None
    missing_filter: bool
    catalogue_only: bool
    known_modelos: tuple[str, ...]
    binding_count: int
    bindings: tuple[ModeloBindingRowV1, ...]


class ModeloBindingsResolveProjection(BaseModel):
    """Full ordered exact-scope preview with unsaved overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.bindings.resolve"] = "modelo.bindings.resolve"
    authority_generation: ContentDigest
    profile_id: UUID
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    override_count: int
    binding_count: int
    bindings: tuple[ModeloBindingRowV1, ...]


class ModeloInventoryCasillaV1(BaseModel):
    """One canonical checklist row and its provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: str
    number: str
    label: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    binding_id: str | None
    binding_source: str | None

    @classmethod
    def from_casilla(cls, row: DataInventoryCasilla) -> Self:
        """Copy one canonical checklist row without shortening its references."""
        return cls(
            casilla_id=row.casilla_id,
            number=row.number,
            label=row.label,
            legal_refs=row.legal_refs,
            source_refs=row.source_refs,
            binding_id=row.binding_id,
            binding_source=row.binding_source,
        )


class ModeloRequiresProjection(BaseModel):
    """Every canonical checklist bucket and profile gap, in source order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.requires"] = "modelo.requires"
    authority_generation: ContentDigest
    profile_id: UUID
    language: OutputLanguage
    modelo: str
    revision: str
    filing_year: int
    period: str
    required_manual: tuple[ModeloInventoryCasillaV1, ...]
    optional_manual: tuple[ModeloInventoryCasillaV1, ...]
    detail_row_fields: tuple[ModeloInventoryCasillaV1, ...]
    ledger_derivable: tuple[ModeloInventoryCasillaV1, ...]
    profile_derivable: tuple[ModeloInventoryCasillaV1, ...]
    previous_filing: tuple[ModeloInventoryCasillaV1, ...]
    relation_prefill: tuple[ModeloInventoryCasillaV1, ...]
    live_observation: tuple[ModeloInventoryCasillaV1, ...]
    unbucketed_sources: tuple[ModeloInventoryCasillaV1, ...]
    unresolved_profile_bindings: tuple[str, ...]
    unresolved_profile_keys: tuple[str, ...]
    profile_checked: bool

    @classmethod
    def from_checklist(
        cls,
        profile_id: UUID,
        checklist: DataInventoryChecklist,
        *,
        language: OutputLanguage,
        authority_generation: ContentDigest,
    ) -> Self:
        """Preserve every canonical checklist section in declaration order."""

        def rows(source: tuple[DataInventoryCasilla, ...]) -> tuple[ModeloInventoryCasillaV1, ...]:
            return tuple(ModeloInventoryCasillaV1.from_casilla(row) for row in source)

        return cls(
            authority_generation=authority_generation,
            profile_id=profile_id,
            language=language,
            modelo=checklist.modelo,
            revision=checklist.revision_id,
            filing_year=checklist.filing_year,
            period=checklist.period,
            required_manual=rows(checklist.required_manual),
            optional_manual=rows(checklist.optional_manual),
            detail_row_fields=rows(checklist.detail_row_fields),
            ledger_derivable=rows(checklist.ledger_derivable),
            profile_derivable=rows(checklist.profile_derivable),
            previous_filing=rows(checklist.previous_filing),
            relation_prefill=rows(checklist.relation_prefill),
            live_observation=rows(checklist.live_observation),
            unbucketed_sources=rows(checklist.unbucketed_sources),
            unresolved_profile_bindings=checklist.unresolved_profile_bindings,
            unresolved_profile_keys=checklist.unresolved_profile_keys,
            profile_checked=checklist.profile_checked,
        )


class ModeloReadinessMissingRequirementV1(BaseModel):
    """One missing profile requirement and its legal grounding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    section_key: str
    field_key: str
    selector: str
    label: str
    legal_refs: tuple[str, ...]
    modelos: tuple[str, ...]


class ModeloReadinessMissingBindingV1(BaseModel):
    """One unresolved calculation binding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding_id: str
    source: str
    input_channel: str


class ModeloReadinessLedgerIssueV1(BaseModel):
    """One ledger preflight issue with its transaction address."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    transaction_id: str
    reason: str
    detail: str


class ModeloReadinessProjection(BaseModel):
    """All canonical readiness axes, including unassessed and recovery facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.readiness"] = "modelo.readiness"
    authority_generation: ContentDigest
    profile_id: UUID
    language: OutputLanguage
    modelo: str
    revision_id: str
    filing_year: int
    period: PublicPeriod
    ready: bool
    profile_ready: bool
    per_operation_requirements_assessed: bool
    profile_refusal: str
    profile_precondition_verdict: PreconditionVerdictSnapshot | None
    registry_ready: bool
    registry_refusal: str
    binding_ready: bool
    missing: tuple[ModeloReadinessMissingRequirementV1, ...]
    missing_bindings: tuple[ModeloReadinessMissingBindingV1, ...]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: PublicPeriod | None
    ledger_checked_transaction_count: int
    ledger_issues: tuple[ModeloReadinessLedgerIssueV1, ...]

    @classmethod
    def from_report(
        cls,
        profile_id: UUID,
        report: ProjectionModeloReadiness,
        *,
        language: OutputLanguage,
        authority_generation: ContentDigest,
    ) -> Self:
        """Copy all readiness axes from the canonical report."""
        if str(report.profile_id) != str(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return cls(
            authority_generation=authority_generation,
            profile_id=profile_id,
            language=language,
            modelo=report.modelo,
            revision_id=report.revision_id,
            filing_year=report.filing_year,
            period=PublicPeriod.from_period(report.period),
            ready=report.ready,
            profile_ready=report.profile_ready,
            per_operation_requirements_assessed=report.per_operation_requirements_assessed,
            profile_refusal=report.profile_refusal,
            profile_precondition_verdict=(
                PreconditionVerdictSnapshot.from_verdict(report.profile_precondition_verdict)
                if report.profile_precondition_verdict is not None
                else None
            ),
            registry_ready=report.registry_ready,
            registry_refusal=report.registry_refusal,
            binding_ready=report.binding_ready,
            missing=tuple(
                ModeloReadinessMissingRequirementV1(
                    section_key=row.section_key,
                    field_key=row.field_key,
                    selector=row.selector,
                    label=row.label,
                    legal_refs=row.legal_refs,
                    modelos=row.modelos,
                )
                for row in report.missing
            ),
            missing_bindings=tuple(
                ModeloReadinessMissingBindingV1(
                    binding_id=row.binding_id,
                    source=row.source.value,
                    input_channel=row.input_channel,
                )
                for row in report.missing_bindings
            ),
            ledger_preflight_required=report.ledger_preflight_required,
            ledger_ready=report.ledger_ready,
            ledger_period=(
                PublicPeriod.from_period(report.ledger_period) if report.ledger_period is not None else None
            ),
            ledger_checked_transaction_count=report.ledger_checked_transaction_count,
            ledger_issues=tuple(
                ModeloReadinessLedgerIssueV1(
                    transaction_id=row.transaction_id,
                    reason=row.reason.value,
                    detail=row.detail,
                )
                for row in report.ledger_issues
            ),
        )


def require_modelo_query_worker_identity[PayloadT: BaseModel](
    definition_id: str, profile_id: UUID, request: OperationRequest[PayloadT], context: OperationExecutorContext
) -> str:
    """Require one exact-profile subject and active bucket for a query executor."""
    bucket_id = str(profile_id)
    if (
        request.definition_id != definition_id
        or request.subject_ref != profile_operation_subject(bucket_id)
        or context.identity.subject_ref != request.subject_ref
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def _binding_report(
    modelo: str,
    *,
    year: int | None,
    period_code: str | None,
    as_of: date | None,
    operation: PinnedAuthorityOperation,
) -> ModeloBindingsReport:
    if year is not None and period_code is not None:
        return registry_bindings_for_scope(
            modelo, period=Period.from_year_and_code(year, period_code), as_of=as_of, operation=operation
        )
    if year is not None:
        return registry_bindings_for_year(modelo, filing_year=year, as_of=as_of, operation=operation)
    return registry_bindings(modelo, period=period_code, as_of=as_of, operation=operation)


def _read_bindings_list(
    payload: ModeloBindingsListRequest, *, operation: PinnedAuthorityOperation
) -> ModeloBindingsListProjection:
    known_codes = registry_modelo_codes(operation=operation)
    if payload.catalogue_only:
        return ModeloBindingsListProjection(
            authority_generation=operation.generation.logical_generation,
            profile_id=payload.profile_id,
            modelo_filter=None,
            year_filter=None,
            period_filter=None,
            missing_filter=False,
            catalogue_only=True,
            known_modelos=known_codes,
            binding_count=0,
            bindings=(),
        )
    if payload.modelo is not None and payload.modelo not in known_codes:
        raise RegistryValidationError(
            f"modelo {payload.modelo!r} is not in the calculation registry; accepted: {', '.join(known_codes)}",
            translated_message="errors.error.error_calculations_registry_validation",
            context={"modelo": payload.modelo, "accepted": ", ".join(known_codes)},
        )
    rows: list[ModeloBindingRowV1] = []
    for modelo in (payload.modelo,) if payload.modelo is not None else known_codes:
        try:
            report = _binding_report(
                modelo, year=payload.year, period_code=payload.period_code, as_of=payload.as_of, operation=operation
            )
        except (RegistrySnapshotError, RegistryValidationError):
            if payload.modelo is not None:
                raise
            continue
        resolved = frozenset[str]()
        if payload.missing and report.filing_year is not None:
            try:
                resolved = profile_resolvable_binding_ids(
                    modelo=report.code,
                    bucket_id=str(payload.profile_id),
                    filing_year=report.filing_year,
                    period=report.filing_period,
                    as_of=payload.as_of,
                    revision_id=report.revision,
                    operation=operation,
                )
            except (RegistrySnapshotError, RegistryValidationError, ProfileNotFoundError):
                resolved = frozenset[str]()
        for row in report.rows:
            if payload.missing and (not row.operator_input_required or row.binding_id in resolved):
                continue
            rows.append(ModeloBindingRowV1.from_report_row(report, row))
    return ModeloBindingsListProjection(
        authority_generation=operation.generation.logical_generation,
        profile_id=payload.profile_id,
        modelo_filter=payload.modelo,
        year_filter=payload.year,
        period_filter=payload.period_code,
        missing_filter=payload.missing,
        catalogue_only=False,
        known_modelos=known_codes,
        binding_count=len(rows),
        bindings=tuple(rows),
    )


def read_modelo_bindings_resolve(
    payload: ModeloBindingsResolveRequest, *, operation: PinnedAuthorityOperation
) -> ModeloBindingsResolveProjection:
    """Read the complete canonical unsaved binding preview once."""
    report = registry_bindings_for_scope(
        payload.modelo, period=payload.period.to_period(), as_of=payload.as_of, operation=operation
    )
    overrides = {row.binding_id: row.value for row in payload.overrides}
    if set(overrides) - {row.binding_id for row in report.rows}:
        unknown = sorted(set(overrides) - {row.binding_id for row in report.rows})
        accepted = ", ".join(row.binding_id for row in report.rows)
        raise RegistryValidationError(
            f"unknown binding overrides: {', '.join(unknown)}; accepted: {accepted}",
            translated_message="errors.error.error_calculations_registry_validation",
            context={
                "modelo": report.code,
                "revision": report.revision,
                "period": report.period or "",
                "unknown": ", ".join(unknown),
                "accepted": accepted,
            },
        )
    rows = tuple(
        ModeloBindingRowV1.from_report_row(report, row, override=overrides.get(row.binding_id)) for row in report.rows
    )
    return ModeloBindingsResolveProjection(
        authority_generation=operation.generation.logical_generation,
        profile_id=payload.profile_id,
        modelo=report.code,
        revision=report.revision,
        filing_year=report.filing_year,
        period=report.period,
        override_count=len(overrides),
        binding_count=len(rows),
        bindings=rows,
    )


def _read_requires(payload: ModeloRequiresRequest, *, operation: PinnedAuthorityOperation) -> ModeloRequiresProjection:
    with override_settings(cadrumo_output_language=payload.language):
        checklist = data_inventory_checklist(
            modelo=payload.modelo,
            filing_year=payload.period.filing_year,
            period=payload.period.to_period(),
            bucket_id=str(payload.profile_id),
            operation=operation,
        )
    return ModeloRequiresProjection.from_checklist(
        payload.profile_id,
        checklist,
        language=payload.language,
        authority_generation=operation.generation.logical_generation,
    )


def read_modelo_readiness(
    payload: ModeloReadinessOperationRequest,
    factory: ModeloQueryReadPortsFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> ProjectionModeloReadiness:
    """Evaluate one canonical readiness report under the retained authority pin."""
    bucket_id = str(payload.profile_id)
    ports = factory(bucket_id=bucket_id)
    if ports.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    profile = ports.read_ports.profile.read_profile(profile_id=bucket_id)
    if profile is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if profile.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    period = payload.period.to_period() if payload.period is not None else None
    with override_settings(cadrumo_output_language=payload.language):
        revision_id = law_selected_revision_for_work_target(
            modelo=payload.modelo,
            filing_year=payload.filing_year,
            period=period or Period.from_year_and_code(payload.filing_year, "0A"),
            requested_revision_id=payload.revision_id,
            operation=operation,
        )
        reports = build_modelo_readiness_reports(
            (
                ModeloReadinessRequest(
                    modelo=payload.modelo,
                    revision_id=revision_id,
                    filing_year=payload.filing_year,
                    period=period,
                ),
            ),
            active_profile_id=bucket_id,
            read_ports=ports.read_ports,
            operation=operation,
        )
    if len(reports) != 1:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return reports[0]


class ModeloBindingsListExecutor:
    """Capture a complete ordered binding listing in encrypted custody."""

    async def execute(
        self, request: OperationRequest[ModeloBindingsListRequest], context: OperationExecutorContext
    ) -> str:
        """Read through the retained authority and publish a NONE-effect result."""
        require_modelo_query_worker_identity(
            MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(
                _read_bindings_list, request.payload, operation=context.authority_operation
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-bindings-list")


class ModeloBindingsResolveExecutor:
    """Capture a temporary exact-scope binding preview."""

    async def execute(
        self, request: OperationRequest[ModeloBindingsResolveRequest], context: OperationExecutorContext
    ) -> str:
        """Read the preview without saving its temporary values."""
        require_modelo_query_worker_identity(
            MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(
                read_modelo_bindings_resolve, request.payload, operation=context.authority_operation
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-bindings-resolve")


class ModeloRequiresExecutor:
    """Capture the canonical one-period data inventory."""

    async def execute(self, request: OperationRequest[ModeloRequiresRequest], context: OperationExecutorContext) -> str:
        """Read one canonical inventory without a write section."""
        require_modelo_query_worker_identity(
            MODELO_REQUIRES_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_REQUIRES_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(_read_requires, request.payload, operation=context.authority_operation)
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-requires")


class ModeloReadinessExecutor:
    """Capture all canonical profile, registry, binding and ledger axes."""

    def __init__(self, factory: ModeloQueryReadPortsFactory) -> None:
        """Bind a profile-specific state projection reader."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloReadinessOperationRequest], context: OperationExecutorContext
    ) -> str:
        """Read every readiness axis under the retained authority pin."""
        require_modelo_query_worker_identity(
            MODELO_READINESS_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_READINESS_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            report = await asyncio.to_thread(
                read_modelo_readiness, request.payload, self._factory, operation=context.authority_operation
            )
            result = ModeloReadinessProjection.from_report(
                request.payload.profile_id,
                report,
                language=request.payload.language,
                authority_generation=context.authority_operation.generation.logical_generation,
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-readiness")


def modelo_query_read_capabilities(*, sensitive: bool = False) -> OperationCapabilities:
    """Keep all read-only modelo query custody and effect guarantees aligned."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.NONE,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=(
            OperationRequestStoragePolicy.SECURE_REFERENCE
            if sensitive
            else OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
        ),
        sensitive_input=(
            OperationSensitiveInputPolicy.SECURE_REFERENCE if sensitive else OperationSensitiveInputPolicy.NONE
        ),
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _read_definition(
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build_executor: Callable[[], object],
    *,
    sensitive: bool = False,
    permitted_frontends: frozenset[OperationFrontendProjection] = frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
    ),
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=build_executor,
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=modelo_query_read_capabilities(sensitive=sensitive),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=permitted_frontends,
    )


def build_modelo_bindings_list_definition() -> OperationDefinition:
    """Define the read-only bindings list operation."""
    return _read_definition(
        MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
        ModeloBindingsListRequest,
        ModeloBindingsListProjection,
        ModeloBindingsListExecutor,
        ModeloBindingsListExecutor,
        permitted_frontends=frozenset(
            {
                OperationFrontendProjection.CLI,
                OperationFrontendProjection.TUI,
                OperationFrontendProjection.MCP,
            }
        ),
    )


def build_modelo_bindings_resolve_definition() -> OperationDefinition:
    """Define the unsaved binding preview operation."""
    return _read_definition(
        MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID,
        ModeloBindingsResolveRequest,
        ModeloBindingsResolveProjection,
        ModeloBindingsResolveExecutor,
        ModeloBindingsResolveExecutor,
        sensitive=True,
    )


def build_modelo_requires_definition() -> OperationDefinition:
    """Define the read-only data inventory operation."""
    return _read_definition(
        MODELO_REQUIRES_OPERATION_DEFINITION_ID,
        ModeloRequiresRequest,
        ModeloRequiresProjection,
        ModeloRequiresExecutor,
        ModeloRequiresExecutor,
        permitted_frontends=frozenset(
            {
                OperationFrontendProjection.CLI,
                OperationFrontendProjection.TUI,
                OperationFrontendProjection.MCP,
            }
        ),
    )


def build_modelo_readiness_definition(factory: ModeloQueryReadPortsFactory) -> OperationDefinition:
    """Define the read-only canonical readiness operation."""
    return _read_definition(
        MODELO_READINESS_OPERATION_DEFINITION_ID,
        ModeloReadinessOperationRequest,
        ModeloReadinessProjection,
        ModeloReadinessExecutor,
        lambda: ModeloReadinessExecutor(factory),
    )


def _requested_scope(payload: BaseModel) -> tuple[frozenset[Period], bool, bool]:
    """Return exact period, independence and all-period requirement."""
    if type(payload) is ModeloBindingsListRequest:
        if payload.year is not None and payload.period_code is not None:
            return frozenset({Period.from_year_and_code(payload.year, payload.period_code)}), False, False
        return frozenset[Period](), True, payload.missing
    if type(payload) is ModeloBindingsResolveRequest or type(payload) is ModeloRequiresRequest:
        return frozenset({payload.period.to_period()}), False, False
    if type(payload) is ModeloReadinessOperationRequest:
        if payload.period is not None:
            return frozenset({payload.period.to_period()}), False, False
        return frozenset[Period](), True, True
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def resolve_modelo_query_read_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[BaseModel],
    result_category: DisclosureCategory,
) -> ResolvedOperationAccess:
    """Resolve an exact modelo query scope and public result category."""
    payload = request.payload
    if (
        request.definition_id != definition_id
        or context.contract.definition_id != definition_id
        or type(payload) is not payload_type
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(
        payload,
        (
            ModeloBindingsListRequest,
            ModeloBindingsResolveRequest,
            ModeloRequiresRequest,
            ModeloReadinessOperationRequest,
        ),
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    periods, period_independent, requires_all_periods = _requested_scope(payload)
    admitted = context.admitted_request
    if admitted is not None and context.action in {
        AccessAction.OBSERVE,
        AccessAction.RESULT,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }:
        if (
            admitted.profile_id != context.profile_id
            or admitted.definition_id != definition_id
            or admitted.action is not AccessAction.SUBMIT
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        periods = admitted.periods
        period_independent = admitted.period_independent
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=result_category,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
            definition_id=definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=periods,
            period_independent=period_independent,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=periods,
            allow_period_independent=period_independent,
            requires_all_periods=requires_all_periods,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def _read_registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    category: DisclosureCategory,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=result_type,
        ),
        access_resolver=lambda request, context: resolve_modelo_query_read_access(
            request,
            context,
            definition_id=definition.definition_id,
            payload_type=request_type,
            result_category=category,
        ),
    )


def build_modelo_bindings_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed list contract and scoped authorization."""
    return _read_registration(
        definition,
        request_type=ModeloBindingsListRequest,
        result_type=ModeloBindingsListProjection,
        category=DisclosureCategory.PROFILE_VALUES,
    )


def build_modelo_bindings_resolve_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed unsaved preview contract."""
    return _read_registration(
        definition,
        request_type=ModeloBindingsResolveRequest,
        result_type=ModeloBindingsResolveProjection,
        category=DisclosureCategory.TAX_VALUES,
    )


def build_modelo_requires_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the complete checklist contract."""
    return _read_registration(
        definition,
        request_type=ModeloRequiresRequest,
        result_type=ModeloRequiresProjection,
        category=DisclosureCategory.PROFILE_VALUES,
    )


def build_modelo_readiness_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the canonical readiness axes and all-period rule."""
    return _read_registration(
        definition,
        request_type=ModeloReadinessOperationRequest,
        result_type=ModeloReadinessProjection,
        category=DisclosureCategory.TAX_VALUES,
    )
