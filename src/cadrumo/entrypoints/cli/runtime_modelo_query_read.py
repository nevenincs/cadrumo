"""Exact-profile registered transport for modelo discovery and readiness."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
from ...application.modelo.data_inventory import DataInventoryCasilla, DataInventoryChecklist
from ...application.modelo.query_read_operation import (
    MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
    MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID,
    MODELO_READINESS_OPERATION_DEFINITION_ID,
    MODELO_REQUIRES_OPERATION_DEFINITION_ID,
    ModeloBindingsListProjection,
    ModeloBindingsListRequest,
    ModeloBindingsResolveProjection,
    ModeloBindingsResolveRequest,
    ModeloInventoryCasillaV1,
    ModeloReadinessOperationRequest,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
    ModeloRequiresRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.state_projection import ProjectionModeloBindingRequirement, ProjectionModeloReadiness
from ...core.aggregation import BindingSourceKind
from ...core.identity.digest import ContentDigest
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def _client(ctx: typer.Context, profile_id: UUID) -> RuntimeFrontendClient:
    expected = UUID(active_bucket_id_or_refuse())
    if profile_id != expected:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return require_profile_client(ctx, expected_profile_id=expected)


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    client = _client(ctx, profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return completed


def read_modelo_bindings_list(
    ctx: typer.Context,
    request: ModeloBindingsListRequest,
    *,
    expected_authority_generation: ContentDigest,
) -> ModeloBindingsListProjection:
    """Return one complete listing under its registered read receipt."""
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
        result_type=ModeloBindingsListProjection,
    )
    result = completed.projection
    if (
        _bindings_list_scope_invalid(result, request, expected_authority_generation)
        or result.binding_count != len(result.bindings)
        or (result.catalogue_only and result.bindings)
    ):
        raise invalid_completion_error(completed)
    return result


def read_modelo_bindings_resolve(
    ctx: typer.Context,
    request: ModeloBindingsResolveRequest,
    *,
    expected_authority_generation: ContentDigest,
) -> ModeloBindingsResolveProjection:
    """Return one unsaved preview with its exact target and override count."""
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID,
        result_type=ModeloBindingsResolveProjection,
    )
    result = completed.projection
    if (
        result.profile_id != request.profile_id
        or result.authority_generation != expected_authority_generation
        or result.modelo != request.modelo
        or result.filing_year != request.period.filing_year
        or result.period != request.period.code
        or result.override_count != len(request.overrides)
        or result.binding_count != len(result.bindings)
    ):
        raise invalid_completion_error(completed)
    return result


def read_modelo_requires(
    ctx: typer.Context,
    request: ModeloRequiresRequest,
    *,
    expected_authority_generation: ContentDigest,
) -> ModeloRequiresProjection:
    """Return all canonical inventory sections for one exact period."""
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_REQUIRES_OPERATION_DEFINITION_ID,
        result_type=ModeloRequiresProjection,
    )
    result = completed.projection
    if (
        result.profile_id != request.profile_id
        or result.modelo != request.modelo
        or result.filing_year != request.period.filing_year
        or result.period != request.period.code
        or result.language is not request.language
        or result.authority_generation != expected_authority_generation
    ):
        raise invalid_completion_error(completed)
    return result


def read_modelo_readiness(
    ctx: typer.Context,
    request: ModeloReadinessOperationRequest,
    *,
    expected_authority_generation: ContentDigest,
) -> ModeloReadinessProjection:
    """Return the canonical readiness axes without a second service read."""
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_READINESS_OPERATION_DEFINITION_ID,
        result_type=ModeloReadinessProjection,
    )
    result = completed.projection
    if (
        result.profile_id != request.profile_id
        or result.authority_generation != expected_authority_generation
        or result.modelo != request.modelo
        or result.filing_year != request.filing_year
        or result.language is not request.language
        or (request.period is not None and result.period != request.period)
        or (request.revision_id is not None and result.revision_id != request.revision_id)
    ):
        raise invalid_completion_error(completed)
    return result


def _inventory_row(row: ModeloInventoryCasillaV1) -> DataInventoryCasilla:
    return DataInventoryCasilla(
        casilla_id=row.casilla_id,
        number=row.number,
        label=row.label,
        legal_refs=row.legal_refs,
        source_refs=row.source_refs,
        binding_id=row.binding_id,
        binding_source=row.binding_source,
    )


def to_data_inventory_checklist(result: ModeloRequiresProjection) -> DataInventoryChecklist:
    """Restore the canonical renderer input from an authenticated DTO."""

    def rows(source: tuple[ModeloInventoryCasillaV1, ...]) -> tuple[DataInventoryCasilla, ...]:
        return tuple(_inventory_row(row) for row in source)

    return DataInventoryChecklist(
        modelo=result.modelo,
        revision_id=result.revision,
        filing_year=result.filing_year,
        period=result.period,
        required_manual=rows(result.required_manual),
        optional_manual=rows(result.optional_manual),
        detail_row_fields=rows(result.detail_row_fields),
        ledger_derivable=rows(result.ledger_derivable),
        profile_derivable=rows(result.profile_derivable),
        previous_filing=rows(result.previous_filing),
        relation_prefill=rows(result.relation_prefill),
        live_observation=rows(result.live_observation),
        unbucketed_sources=rows(result.unbucketed_sources),
        unresolved_profile_bindings=result.unresolved_profile_bindings,
        unresolved_profile_keys=result.unresolved_profile_keys,
        profile_checked=result.profile_checked,
    )


def to_modelo_readiness_report(result: ModeloReadinessProjection) -> ProjectionModeloReadiness:
    """Restore the existing notice and text renderer's typed report."""
    return ProjectionModeloReadiness.model_validate(
        result.model_dump(mode="python", exclude={"result_version", "operation", "language", "authority_generation"})
        | {
            "profile_id": str(result.profile_id),
            "period": result.period.to_period(),
            "ledger_period": result.ledger_period.to_period() if result.ledger_period is not None else None,
            "profile_precondition_verdict": (
                result.profile_precondition_verdict.to_verdict()
                if result.profile_precondition_verdict is not None
                else None
            ),
            "missing_bindings": tuple(
                ProjectionModeloBindingRequirement(
                    binding_id=row.binding_id,
                    source=BindingSourceKind(row.source),
                    input_channel=row.input_channel,
                )
                for row in result.missing_bindings
            ),
            "ledger_issues": tuple(
                LedgerPreflightIssue(
                    transaction_id=row.transaction_id,
                    reason=LedgerPreflightIssueReason(row.reason),
                    detail=row.detail,
                )
                for row in result.ledger_issues
            ),
        }
    )


__all__ = [
    "read_modelo_bindings_list",
    "read_modelo_bindings_resolve",
    "read_modelo_readiness",
    "read_modelo_requires",
    "to_data_inventory_checklist",
    "to_modelo_readiness_report",
]


def _bindings_list_scope_invalid(
    result: ModeloBindingsListProjection,
    request: ModeloBindingsListRequest,
    expected_authority_generation: ContentDigest,
) -> bool:
    """Require every requested catalogue and period filter under the pinned authority generation."""
    return (
        result.profile_id != request.profile_id
        or result.authority_generation != expected_authority_generation
        or result.modelo_filter != request.modelo
        or (result.year_filter != request.year)
        or (result.period_filter != request.period_code)
        or (result.missing_filter != request.missing)
        or (result.catalogue_only != request.catalogue_only)
    )
