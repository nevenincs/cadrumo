"""Bounded aggregate summaries and proof of their settled terminal receipts."""

from __future__ import annotations

import re
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.hashing import canonical_json_bytes
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..aggregation.service import (
    PerModeloAggregationContributor,
)
from ..aggregation.withholding_observation_service import (
    WithholdingGenerationAudit,
    WithholdingMutationMode,
    WithholdingWindowBaseline,
)
from ..operations.models import (
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
    terminal_receipt_matches,
)
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal
from .aggregate_contracts import (
    AGGREGATE_MAX_CLAVE_ROWS,
    AGGREGATE_MAX_RESULT_BYTES,
    AGGREGATE_SAFE_REFUSAL_REASON,
    AGGREGATE_WITHHOLDING_MODELOS,
    MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
    MODELO_AGGREGATE_REFUSAL_CODES,
)
from .aggregate_public import PublicModeloAggregateCommand


class ModeloAggregateWindowBaseline(BaseModel):
    """Metadata-only generation coordinates for one active withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    scope_token: str = Field(min_length=1, max_length=256)
    generation_id: Hex64Str


class ModeloAggregateGenerationAudit(BaseModel):
    """Bounded lineage metadata without withholding evidence rows."""

    model_config = STRICT_FROZEN_CONFIG

    parent_generation_id: Hex64Str
    mode: WithholdingMutationMode
    supersedes_generation_id: str | None = Field(default=None, min_length=64, max_length=64)


class ModeloAggregateWindow(BaseModel):
    """CLI-compatible metadata-only readback of one withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    baseline: ModeloAggregateWindowBaseline
    generation: NonNegativeInt
    generation_audit: ModeloAggregateGenerationAudit | None = None


class ModeloAggregateClaveTotals(BaseModel):
    """One clave's reconciliation totals; perceptor identities never leave custody."""

    model_config = STRICT_FROZEN_CONFIG

    clave: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9]+$")
    percepcion_count: NonNegativeInt
    percibido_total: PublicDecimal
    retencion_total: PublicDecimal


class ModeloAggregateProjection(BaseModel):
    """Allowlisted aggregation summary; raw observation rows never leave custody.

    ``absent_source_families`` names each stored source an annual summary's
    calculation reads that holds no row, so an empty summary reads as missing
    data rather than as a proven zero. ``calculation_revision_id`` identifies the
    revision whose calculation rows were read and is present whenever any are.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: Literal["aggregated", "refused"]
    profile_id: UUID
    modelo: str = Field(min_length=1, max_length=16)
    period: PublicPeriod
    provider: PerModeloAggregationContributor | None = None
    observation_count: NonNegativeInt | None = None
    source_kinds: tuple[BindingSourceKind, ...] | None = None
    result_row_count: NonNegativeInt | None = None
    clave_breakdown: tuple[ModeloAggregateClaveTotals, ...] | None = Field(
        default=None, max_length=AGGREGATE_MAX_CLAVE_ROWS
    )
    absent_source_families: tuple[BindingSourceKind, ...] | None = None
    calculation_revision_id: str | None = Field(default=None, min_length=1, max_length=128)
    withholding_window: ModeloAggregateWindow | None = None
    refusal_reason: AGGREGATE_SAFE_REFUSAL_REASON | None = None

    @model_validator(mode="after")
    def _outcome_shape(self) -> Self:
        aggregate_fields = (
            self.provider,
            self.observation_count,
            self.source_kinds,
            self.result_row_count,
            self.clave_breakdown,
            self.absent_source_families,
        )
        if self.outcome == "aggregated":
            _require_aggregated_summary_fields(self, aggregate_fields)
            _require_aggregate_row_metadata(self)
        elif self.refusal_reason is None or any(value is not None for value in aggregate_fields):
            raise ValueError("refused result requires only a bounded refusal reason")
        elif self.withholding_window is not None or self.calculation_revision_id is not None:
            raise ValueError("refused result cannot carry a withholding window or calculation rows")
        return self


class ModeloAggregateReport(BaseModel):
    """Private result operand correlated with the settled operation receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloAggregateProjection
    local_write_performed: bool
    refusal_code: str | None = None


def project_aggregate_window(
    *,
    baseline: WithholdingWindowBaseline,
    generation: int,
    audit: WithholdingGenerationAudit | None,
) -> ModeloAggregateWindow:
    """Project only lineage coordinates from one exact stored withholding window."""
    return ModeloAggregateWindow(
        baseline=ModeloAggregateWindowBaseline(
            scope_token=baseline.scope_token,
            generation_id=baseline.generation_id,
        ),
        generation=generation,
        generation_audit=(
            None
            if audit is None
            else ModeloAggregateGenerationAudit(
                parent_generation_id=audit.parent_generation_id,
                mode=audit.mode,
                supersedes_generation_id=audit.supersedes_generation_id,
            )
        ),
    )


def bounded_aggregate_refusal_reason(error: Exception) -> str:
    """Select a stable reason token without copying exception prose or private facts."""
    candidate: object = getattr(error, "refusal_code", None)
    if candidate is None:
        refusal = getattr(error, "refusal", None)
        candidate = getattr(refusal, "value", refusal)
    if not isinstance(candidate, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,95}", candidate) is None:
        return "invalid_aggregate_input"
    return candidate


def project_refused_aggregate(
    *,
    profile_id: UUID,
    command: PublicModeloAggregateCommand,
    reason: str,
) -> ModeloAggregateProjection:
    """Build a bounded refusal summary for the original profile and command."""
    return ModeloAggregateProjection(
        outcome="refused",
        profile_id=profile_id,
        modelo=command.modelo,
        period=command.period,
        refusal_reason=reason,
    )


def project_modelo_aggregate_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the bounded summary whose identity and effect match its receipt."""
    if type(result) is not ModeloAggregateReport:
        raise ValueError("invalid modelo-aggregate operation result")
    report = ModeloAggregateReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    _require_aggregate_receipt_identity(projection, receipt)
    if projection.outcome == "refused":
        _require_refused_aggregate_receipt(report, receipt)
    else:
        _require_successful_aggregate_receipt(report, receipt)
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > AGGREGATE_MAX_RESULT_BYTES:
        raise ValueError("modelo-aggregate projection exceeds its public result limit")
    return projection


def _require_aggregated_summary_fields(self: ModeloAggregateProjection, aggregate_fields: tuple[object, ...]) -> None:
    """Require complete summary fields and the exact periodic withholding window."""
    if self.refusal_reason is not None or any(value is None for value in aggregate_fields):
        raise ValueError("aggregated result requires the canonical summary fields")
    if self.modelo in AGGREGATE_WITHHOLDING_MODELOS and self.withholding_window is None:
        raise ValueError("withholding aggregate requires its exact window readback")


def _require_aggregate_row_metadata(self: ModeloAggregateProjection) -> None:
    """Require annual source revisions and refuse annual detail on periodic results."""
    if (self.clave_breakdown or self.absent_source_families) and self.calculation_revision_id is None:
        raise ValueError("calculation rows require the revision they were read for")
    if self.modelo in AGGREGATE_WITHHOLDING_MODELOS and (
        self.clave_breakdown or self.calculation_revision_id is not None or self.absent_source_families
    ):
        raise ValueError("periodic withholding aggregate cannot carry annual detail metadata")


def _require_aggregate_receipt_identity(
    projection: ModeloAggregateProjection, receipt: OperationTerminalReceipt
) -> None:
    """Require one exact operation and profile with no failure diagnostics."""
    if (
        receipt.identity.definition_id != MODELO_AGGREGATE_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("modelo-aggregate result differs from its terminal receipt")


def _require_refused_aggregate_receipt(report: ModeloAggregateReport, receipt: OperationTerminalReceipt) -> None:
    """Release a refusal only when no write, result or success effect is claimed."""
    if (
        report.local_write_performed
        or not terminal_receipt_matches(
            receipt,
            definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(report.projection.profile_id)),
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
        )
        or report.refusal_code not in MODELO_AGGREGATE_REFUSAL_CODES
        or receipt.refusal_ref != report.refusal_code
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
    ):
        raise ValueError("modelo-aggregate refusal contradicts its terminal receipt")


def _require_successful_aggregate_receipt(report: ModeloAggregateReport, receipt: OperationTerminalReceipt) -> None:
    """Require the result reference and exact settled write or read-only effect."""
    message = "modelo-aggregate result contradicts its terminal receipt"
    if report.refusal_code is not None:
        raise ValueError(message)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(report.projection.profile_id)),
        effect=OperationEffect.UPDATED if report.local_write_performed else OperationEffect.NONE,
        message=message,
    )
