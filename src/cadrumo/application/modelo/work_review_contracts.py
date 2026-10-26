"""Canonical exact-profile work review request and result contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.modelo_work_progress_state import ModeloWorkProgressState
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operator_action_enums import OperatorActionAxis
from ...domain.calculations.registry.ids import LegalRefId, RevisionId, SourceRefId, VerificationExpectationId
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ..operations.models import (
    CredentialFreeOperationRequest,
)
from ..operations.public_period import PublicPeriod
from .work_review import BlockerRef, ModeloWorkProgress, ModeloWorkReview

MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID = "modelo.work.review"


class ModeloWorkReviewRequest(CredentialFreeOperationRequest):
    """Identify a work unit without placing its private metadata in the journal."""

    profile_id: UUID
    work_unit_id: WorkUnitId


class ModeloWorkReviewProgressSnapshot(BaseModel):
    """Schema-safe representation of canonical measured progress."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    state: ModeloWorkProgressState
    materialised_count: int | None = Field(default=None, ge=0)
    target_count: int | None = Field(default=None, gt=0)
    denominator_kind: Literal["calculation_completeness_manifest"] | None = None
    denominator_revision_id: RevisionId | None = None
    denominator_source_ref: SourceRefId | None = None

    @classmethod
    def from_progress(cls, progress: ModeloWorkProgress) -> Self:
        """Copy canonical progress into a schema-safe snapshot."""
        denominator = progress.denominator
        return cls(
            state=progress.state,
            materialised_count=progress.materialised_count,
            target_count=progress.target_count,
            denominator_kind=denominator.kind if denominator else None,
            denominator_revision_id=denominator.registry_revision_id if denominator else None,
            denominator_source_ref=denominator.source_ref if denominator else None,
        )

    def to_progress(self) -> ModeloWorkProgress:
        """Revalidate the complete canonical progress invariant."""
        from .work_review import ModeloWorkProgressDenominator

        fields = (self.denominator_kind, self.denominator_revision_id, self.denominator_source_ref)
        if any(value is not None for value in fields) and not all(value is not None for value in fields):
            raise ValueError("work review progress denominator is incomplete")
        denominator = None
        if (
            self.denominator_kind is not None
            and self.denominator_revision_id is not None
            and self.denominator_source_ref is not None
        ):
            denominator = ModeloWorkProgressDenominator(
                kind=self.denominator_kind,
                registry_revision_id=self.denominator_revision_id,
                source_ref=self.denominator_source_ref,
            )
        return ModeloWorkProgress(
            state=self.state,
            materialised_count=self.materialised_count,
            target_count=self.target_count,
            denominator=denominator,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_progress()
        return self


def _validate_review_fact_scalar(kind: Literal["str", "int", "bool", "decimal", "none"], value: str) -> None:
    """Validate the admitted scalar's exact canonical lexical representation."""
    if kind == "bool" and value not in {"true", "false"}:
        raise ValueError("review boolean fact must be canonical")
    if kind == "int" and str(int(value)) != value:
        raise ValueError("review integer fact must be canonical")
    if kind == "decimal":
        decimal = Decimal(value)
        if not decimal.is_finite() or str(decimal) != value:
            raise ValueError("review decimal fact must be finite and canonical")


class ModeloWorkReviewFact(BaseModel):
    """One tagged factual scalar in a schema-visible immutable sequence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    key: str = Field(min_length=1, max_length=128)
    kind: Literal["str", "int", "bool", "decimal", "none"]
    value: str | None = Field(max_length=4096)

    @classmethod
    def from_value(cls, key: str, value: str | int | bool | Decimal | None) -> Self:
        """Preserve the precise canonical scalar type in an explicit tag."""
        if value is None:
            return cls(key=key, kind="none", value=None)
        if isinstance(value, bool):
            return cls(key=key, kind="bool", value="true" if value else "false")
        if isinstance(value, int):
            return cls(key=key, kind="int", value=str(value))
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError("review decimal fact must be finite")
            return cls(key=key, kind="decimal", value=str(value))
        return cls(key=key, kind="str", value=value)

    def to_value(self) -> str | int | bool | Decimal | None:
        """Decode one exact factual scalar without a generic object payload."""
        if self.kind == "none":
            return None
        if self.value is None:
            raise ValueError("review fact value is missing")
        if self.kind == "bool":
            return self.value == "true"
        if self.kind == "int":
            return int(self.value)
        if self.kind == "decimal":
            return Decimal(self.value)
        return self.value

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        if self.kind == "none":
            if self.value is not None:
                raise ValueError("none review fact must have no value")
        elif self.value is None:
            raise ValueError("review fact value is required")
        else:
            _validate_review_fact_scalar(self.kind, self.value)
        return self


class ModeloWorkReviewFindingSnapshot(BaseModel):
    """Validated locale-neutral finding with bounded factual values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: CasillaId | None = None
    expectation_id: VerificationExpectationId | None = None
    message_locale_key: str = Field(min_length=1, max_length=200)
    message_facts: tuple[ModeloWorkReviewFact, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = ()

    @classmethod
    def from_finding(cls, finding: ModeloVerificationFinding) -> Self:
        """Copy a domain finding without its custom serializer."""
        return cls.model_validate(
            finding.model_dump(mode="python")
            | {
                "message_facts": tuple(
                    ModeloWorkReviewFact.from_value(key, value) for key, value in finding.message_facts.items()
                )
            }
        )

    def to_finding(self) -> ModeloVerificationFinding:
        """Revalidate the finding's canonical locale and factual rules."""
        if len({fact.key for fact in self.message_facts}) != len(self.message_facts):
            raise ValueError("work review finding repeats a fact key")
        return ModeloVerificationFinding.model_validate(
            self.model_dump(mode="python")
            | {"message_facts": {fact.key: fact.to_value() for fact in self.message_facts}}
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_finding()
        return self


class ModeloWorkReviewBlockerSnapshot(BaseModel):
    """Canonical blocker code and factual tokens, without review casilla values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    axis: OperatorActionAxis
    native_code: str = Field(min_length=1, max_length=200)
    facts: tuple[ModeloWorkReviewFact, ...] = ()

    @classmethod
    def from_blocker(cls, blocker: BlockerRef) -> Self:
        """Copy one canonical blocker and its typed facts."""
        return cls.model_validate(
            blocker.model_dump(mode="python")
            | {"facts": tuple(ModeloWorkReviewFact.from_value(key, value) for key, value in blocker.facts.items())}
        )

    def to_blocker(self) -> BlockerRef:
        """Revalidate the canonical blocker."""
        if len({fact.key for fact in self.facts}) != len(self.facts):
            raise ValueError("work review blocker repeats a fact key")
        return BlockerRef.model_validate(
            self.model_dump(mode="python") | {"facts": {fact.key: fact.to_value() for fact in self.facts}}
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_blocker()
        return self


class ModeloWorkReviewSnapshot(BaseModel):
    """The exact established compact CLI review, excluding detailed private rows."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bucket_id: BucketId
    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    filing_year: FilingYear
    period: PublicPeriod
    registry_revision_id: RevisionId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None
    lifecycle_state: CalculationRevisionState | None
    verification_outcome: VerificationCompletenessStatus | None
    progress: ModeloWorkReviewProgressSnapshot
    casilla_count: int = Field(ge=0)
    findings: tuple[ModeloWorkReviewFindingSnapshot, ...]
    blockers: tuple[ModeloWorkReviewBlockerSnapshot, ...]
    row_source_fingerprint_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _canonical_coordinates(self) -> Self:
        if self.filing_year != self.period.filing_year:
            raise ValueError("work review year does not match its period")
        return self

    @classmethod
    def from_review(cls, review: ModeloWorkReview) -> Self:
        """Project only fields already emitted by the established CLI result."""
        return cls(
            bucket_id=review.bucket_id,
            modelo=str(review.modelo),
            filing_year=review.filing_year,
            period=PublicPeriod.from_period(review.period),
            registry_revision_id=review.registry_revision_id,
            work_unit_id=review.work_unit_id,
            calculation_revision_id=review.calculation_revision_id,
            lifecycle_state=review.lifecycle_state,
            verification_outcome=review.verification_outcome,
            progress=ModeloWorkReviewProgressSnapshot.from_progress(review.progress),
            casilla_count=len(review.casillas),
            findings=tuple(ModeloWorkReviewFindingSnapshot.from_finding(item) for item in review.findings),
            blockers=tuple(ModeloWorkReviewBlockerSnapshot.from_blocker(item) for item in review.blockers),
            row_source_fingerprint_count=len(review.row_source_fingerprints),
        )


class ModeloWorkReviewResult(BaseModel):
    """Encrypted worker operand, independently projected for frontend disclosure."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    review: ModeloWorkReviewSnapshot

    @model_validator(mode="after")
    def _bound(self) -> Self:
        if self.review.bucket_id != str(self.profile_id):
            raise ValueError("work review belongs to another profile")
        return self


class ModeloWorkReviewProjection(BaseModel):
    """Closed public result; private operand fields cannot flow through inheritance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    review: ModeloWorkReviewSnapshot

    @model_validator(mode="after")
    def _bound(self) -> Self:
        if self.review.bucket_id != str(self.profile_id):
            raise ValueError("work review belongs to another profile")
        return self
