"""Closed human quickfile request and stage snapshot contracts.

Exception messages and arbitrary exception context never become operation operands.
The human presenter resolves declared stage error codes and typed recovery evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.error_codes import get_registered_error_code_by_code
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ..operations.public_period import PublicPeriod
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .calculation_request_fields import ModeloCalculationInputFieldsV1, ModeloCalculationOverride
from .edit_apply_row_contracts import ModeloDetailRowWireV1
from .quickfile import QuickfileStage, QuickfileStageStatus
from .work_calculation_contracts import ModeloWorkCalculateOrdinaryM303EvidenceRequestV2

type QuickfileText = Annotated[str, Field(max_length=PROJECTION_DOCUMENT_MAX_BYTES)]
type QuickfileReference = Annotated[str, Field(min_length=1, max_length=128)]


class QuickfileCalculationInputs(BaseModel):
    """Only the three scalar input channels the current quickfile command exposes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)
    binding_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)
    relation_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)

    def to_calculation_fields(self) -> ModeloCalculationInputFieldsV1:
        """Reuse the registered grammar and canonical calculation-input assembly."""
        return ModeloCalculationInputFieldsV1(
            casilla_overrides=self.casilla_overrides,
            binding_overrides=self.binding_overrides,
            relation_overrides=self.relation_overrides,
        )

    @model_validator(mode="after")
    def _canonical_channels(self) -> Self:
        self.to_calculation_fields()
        return self


class QuickfileRequest(BaseModel):
    """One exact profile and natural filing target, retained in encrypted custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    bucket_id: UUID | None = None
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    revision_id: QuickfileReference | None = None
    output_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
    actor: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP
    ordinary_m303_filing_evidence: ModeloWorkCalculateOrdinaryM303EvidenceRequestV2 | None = None
    inputs: QuickfileCalculationInputs = QuickfileCalculationInputs()
    detail_rows: tuple[ModeloDetailRowWireV1, ...] = Field(default=(), max_length=20_000)

    @model_validator(mode="after")
    def _local_destination(self) -> Self:
        if not Path(self.output_path).is_absolute():
            raise ValueError("quickfile output path must be absolute")
        self.period.to_period()
        return self


class QuickfileReadinessSummary(BaseModel):
    """Every axis and blocker count shown by the existing human JSON output."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    ready: bool
    profile_ready: bool
    registry_ready: bool
    binding_ready: bool
    ledger_preflight_required: bool
    ledger_ready: bool | None
    missing_profile_fact_count: Annotated[int, Field(ge=0)]
    missing_binding_count: Annotated[int, Field(ge=0)]
    ledger_issue_count: Annotated[int, Field(ge=0)]


class QuickfileStageError(BaseModel):
    """A registry identity, without original exception text, arguments or context."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    code: QuickfileReference
    message_key: Annotated[str, Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def _declared_error(self) -> Self:
        if get_registered_error_code_by_code(self.code).message_key != self.message_key:
            raise ValueError("quickfile stage error must match the declared registry row")
        return self


class QuickfileStageFacts(BaseModel):
    """Only the fixed stage facts produced by the canonical quickfile orchestrator."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    work_unit_id: QuickfileReference | None = None
    calculation_revision_id: QuickfileReference | None = None
    verification_report_id: QuickfileReference | None = None
    ready: bool | None = None
    profile_ready: bool | None = None
    binding_ready: bool | None = None
    missing_bindings: Annotated[int, Field(ge=0)] | None = None
    granted_verificado_completo: bool | None = None
    blocking_finding_count: Annotated[int, Field(ge=0)] | None = None
    output_path: QuickfileText | None = None
    file_sha256: ContentDigest | None = None

    def to_context(self) -> dict[str, str]:
        """Restore the existing stage context spelling from these declared fields."""
        declared: dict[str, str | int | bool | None] = {
            "work_unit_id": self.work_unit_id,
            "calculation_revision_id": self.calculation_revision_id,
            "verification_report_id": self.verification_report_id,
            "ready": self.ready,
            "profile_ready": self.profile_ready,
            "binding_ready": self.binding_ready,
            "missing_bindings": self.missing_bindings,
            "granted_verificado_completo": self.granted_verificado_completo,
            "blocking_finding_count": self.blocking_finding_count,
            "output_path": self.output_path,
            "file_sha256": self.file_sha256,
        }
        return {
            name: str(value).lower() if isinstance(value, bool) else str(value)
            for name, value in declared.items()
            if value is not None
        }


type QuickfileStageMessage = Literal[
    "",
    "resumed",
    "created",
    "verification did not grant verificado-completo",
    "readiness could not be resolved; proceeding to calculate",
    "profile is not yet source-ready; caller-supplied inputs may still satisfy calculate",
]


class QuickfileStageSnapshot(BaseModel):
    """An ordered canonical status, fixed message, closed facts and recovery verdict."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    stage: QuickfileStage
    status: QuickfileStageStatus
    message: QuickfileStageMessage = ""
    facts: QuickfileStageFacts = QuickfileStageFacts()
    error: QuickfileStageError | None = None
    precondition_verdict: PreconditionVerdictSnapshot | None = None
