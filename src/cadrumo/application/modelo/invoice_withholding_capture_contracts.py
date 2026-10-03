"""Typed request, port and result contracts for invoice withholding capture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.invoices.models import InvoiceCatalogue
from ..aggregation.invoice_retencion import InvoiceRetencionProjectionDefect, InvoiceWithholdingEvidenceRequest
from ..aggregation.retencion_observations_repository import RetencionObservationRepository
from ..aggregation.service import PerModeloAggregationCommand, PerModeloAggregationContributor
from ..aggregation.withholding_observation_service import WithholdingMutationMode, WithholdingObservationService
from ..operations.public_period import PublicPeriod
from .invoice_withholding_capture_public import PublicInvoiceWithholdingCommand, PublicInvoiceWithholdingEvidence

MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID = "modelo.aggregate.capture_received_invoice_retencion"

MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE = "REFUSED_INVOICE_WITHHOLDING_EVIDENCE"

MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE = "REFUSED_INVOICE_WITHHOLDING_DEFECTS"

MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES = frozenset(
    {MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE, MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE}
)

MODELO_INVOICE_WITHHOLDING_PREPARE_PHASE = "modelo-invoice-withholding-capture.prepare"

MODELO_INVOICE_WITHHOLDING_COMMIT_PHASE = "modelo-invoice-withholding-capture.commit"

MODELO_INVOICE_WITHHOLDING_RESULT_PHASE = "modelo-invoice-withholding-capture.result"

MODELO_INVOICE_WITHHOLDING_CAPTURE_PHASES = (
    MODELO_INVOICE_WITHHOLDING_PREPARE_PHASE,
    MODELO_INVOICE_WITHHOLDING_COMMIT_PHASE,
    MODELO_INVOICE_WITHHOLDING_RESULT_PHASE,
)

MODELO_INVOICE_WITHHOLDING_CAPTURE_MAX_RESULT_BYTES = 16 * 1024

_SAFE_REFUSAL_REASON = Annotated[
    str,
    Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_]*$"),
]


class InvoiceCatalogueRevisionReadPort(Protocol):
    """Minimal application-owned view of one profile's revisioned invoice catalogue."""

    @property
    def bucket_id(self) -> str | None:
        """Return the immutable profile binding of this reader."""
        ...

    def load_revisioned(self) -> tuple[InvoiceCatalogue, str]:
        """Return the decrypted catalogue and its opaque read revision."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloInvoiceWithholdingCapturePorts:
    """Canonical application services and repositories for one exact profile."""

    profile_id: str
    invoice_catalogue_repository: InvoiceCatalogueRevisionReadPort
    retencion_observation_repository: RetencionObservationRepository
    withholding_observation_service: WithholdingObservationService


class ModeloInvoiceWithholdingCapturePortsFactory(Protocol):
    """Build capture capabilities already bound to the requested profile."""

    def __call__(self, *, profile_id: str) -> ModeloInvoiceWithholdingCapturePorts:
        """Return the exact profile's invoice, retención and window capabilities."""
        ...


class ModeloInvoiceWithholdingCaptureRequest(BaseModel):
    """Confidential typed operands with canonical service conversion."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    command: PublicInvoiceWithholdingCommand = Field(repr=False)
    evidence: PublicInvoiceWithholdingEvidence = Field(repr=False)

    @model_validator(mode="after")
    def _closed_capture_scope(self) -> Self:
        self.command.to_domain()
        return self

    @classmethod
    def from_inputs(
        cls,
        *,
        profile_id: UUID,
        command: PerModeloAggregationCommand,
        evidence: InvoiceWithholdingEvidenceRequest,
    ) -> Self:
        """Store the exact typed CLI inputs in the encrypted operation operand."""
        return cls(
            profile_id=profile_id,
            command=PublicInvoiceWithholdingCommand.from_domain(command),
            evidence=PublicInvoiceWithholdingEvidence.from_domain(evidence),
        )


class ModeloInvoiceWithholdingWindowBaseline(BaseModel):
    """Safe generation coordinates for one active withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    scope_token: str = Field(min_length=1, max_length=256)
    generation_id: Hex64Str


class ModeloInvoiceWithholdingGenerationAudit(BaseModel):
    """Bounded lineage metadata that carries no source evidence."""

    model_config = STRICT_FROZEN_CONFIG

    parent_generation_id: Hex64Str
    mode: WithholdingMutationMode
    supersedes_generation_id: str | None = Field(default=None, min_length=64, max_length=64)


class ModeloInvoiceWithholdingWindow(BaseModel):
    """CLI-compatible metadata-only readback of the active withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    baseline: ModeloInvoiceWithholdingWindowBaseline
    generation: NonNegativeInt
    generation_audit: ModeloInvoiceWithholdingGenerationAudit | None = None


class ModeloInvoiceWithholdingCaptureProjection(BaseModel):
    """Closed CLI-safe aggregate summary or bounded refusal outcome.

    ``refusal_defects`` names every defect that keeps the invoice's retención
    out of capture, as stable untranslated tokens in the projection's sweep
    order; a frontend renders their explanations in the operator's language.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["captured", "refused"]
    profile_id: UUID
    modelo: Literal["111", "115"]
    period: PublicPeriod
    provider: Literal[PerModeloAggregationContributor.RETENCIONES] | None = None
    observation_count: NonNegativeInt | None = None
    source_kinds: tuple[BindingSourceKind, ...] | None = None
    result_row_count: NonNegativeInt | None = None
    withholding_window: ModeloInvoiceWithholdingWindow | None = None
    refusal_reason: _SAFE_REFUSAL_REASON | None = None
    refusal_defects: tuple[InvoiceRetencionProjectionDefect, ...] | None = Field(
        default=None,
        min_length=1,
        max_length=len(InvoiceRetencionProjectionDefect),
    )

    @model_validator(mode="after")
    def _outcome_shape(self) -> Self:
        if self.outcome == "captured":
            _require_captured_projection_shape(self)
        else:
            _require_refused_projection_shape(self)
        return self

    @property
    def refusal_code(self) -> str | None:
        """Return the registered refusal code this refused outcome settles under."""
        if self.outcome != "refused":
            return None
        if self.refusal_defects is not None:
            return MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE
        return MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE


def _require_captured_projection_shape(projection: ModeloInvoiceWithholdingCaptureProjection) -> None:
    captured_fields = (
        projection.provider,
        projection.observation_count,
        projection.source_kinds,
        projection.result_row_count,
        projection.withholding_window,
    )
    if (
        projection.refusal_reason is not None
        or projection.refusal_defects is not None
        or any(value is None for value in captured_fields)
    ):
        raise ValueError("captured result requires aggregate and withholding-window summary fields")


def _require_refused_projection_shape(projection: ModeloInvoiceWithholdingCaptureProjection) -> None:
    captured_fields = (
        projection.provider,
        projection.observation_count,
        projection.source_kinds,
        projection.result_row_count,
        projection.withholding_window,
    )
    if projection.refusal_reason is None or any(value is not None for value in captured_fields):
        raise ValueError("refused result requires only a bounded refusal reason")
    if projection.refusal_defects is not None and len(set(projection.refusal_defects)) != len(
        projection.refusal_defects
    ):
        raise ValueError("refused result repeats an invoice withholding defect")


class ModeloInvoiceWithholdingCaptureReport(BaseModel):
    """Private executor operand correlated with the settled effect and receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloInvoiceWithholdingCaptureProjection
    local_write_performed: bool


__all__ = [
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_MAX_RESULT_BYTES",
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID",
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_PHASES",
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE",
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES",
    "MODELO_INVOICE_WITHHOLDING_COMMIT_PHASE",
    "MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE",
    "MODELO_INVOICE_WITHHOLDING_PREPARE_PHASE",
    "MODELO_INVOICE_WITHHOLDING_RESULT_PHASE",
    "InvoiceCatalogueRevisionReadPort",
    "ModeloInvoiceWithholdingCapturePorts",
    "ModeloInvoiceWithholdingCapturePortsFactory",
    "ModeloInvoiceWithholdingCaptureProjection",
    "ModeloInvoiceWithholdingCaptureReport",
    "ModeloInvoiceWithholdingCaptureRequest",
    "ModeloInvoiceWithholdingGenerationAudit",
    "ModeloInvoiceWithholdingWindow",
    "ModeloInvoiceWithholdingWindowBaseline",
]
