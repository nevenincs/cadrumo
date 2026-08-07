"""Strict standing-report evidence for the Rung-2 held-out measurement.

The Rung-2 evaluator deliberately stops at source-only measurements.  This
module is the narrow report boundary that records those measurements beside
the pre-Rung-2 baseline.  It does not load a provider, run Pagefind, write a
file, or enable browser configuration.  Acceptance remains fail-closed and
must be proven by the existing browser-config acceptance contract.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ._miss_rate import DEFAULT_RUNG2_MISS_RATE_THRESHOLD
from ._rung2_evaluation import Rung2EvaluationPolicy
from ._static_matrix import DEFAULT_MAX_SERIALIZED_BYTES

__all__ = [
    "RUNG2_STANDING_REPORT_SCHEMA_VERSION",
    "Rung2ReportArtifactEvidence",
    "Rung2ReportBaseline",
    "Rung2ReportCoverage",
    "Rung2ReportDecision",
    "Rung2ReportMeasurement",
    "Rung2ReportTopFiveLoss",
    "Rung2StandingReport",
]

_SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_NON_BLANK = Annotated[str, StringConstraints(min_length=1)]
RUNG2_STANDING_REPORT_SCHEMA_VERSION: Final[str] = "cadrumo.docs-search.rung2-standing-report.v1"


class Rung2ReportDecision(StrEnum):
    """Report decision; this is not a browser configuration switch."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Rung2ReportBaseline(BaseModel):
    """The prior held-out baseline retained for comparison."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    case_count: int = Field(gt=0)
    hit_count: int = Field(ge=0)
    miss_count: int = Field(ge=0)
    miss_rate: float = Field(ge=0.0, le=1.0)

    @field_validator("miss_rate")
    @classmethod
    def _require_finite_rate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Rung-2 baseline miss rate must be finite")
        return value

    @model_validator(mode="after")
    def _enforce_arithmetic(self) -> Rung2ReportBaseline:
        if self.hit_count + self.miss_count != self.case_count:
            raise ValueError("Rung-2 baseline counts do not partition the cases")
        if self.miss_rate != self.miss_count / self.case_count:
            raise ValueError("Rung-2 baseline miss rate does not match its counts")
        return self


class Rung2ReportMeasurement(BaseModel):
    """One semantic or composed-ladder held-out measurement."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    case_count: int = Field(gt=0)
    hit_count: int = Field(ge=0)
    miss_count: int = Field(ge=0)
    miss_rate: float = Field(ge=0.0, le=1.0)

    @field_validator("miss_rate")
    @classmethod
    def _require_finite_rate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Rung-2 measurement miss rate must be finite")
        return value

    @model_validator(mode="after")
    def _enforce_arithmetic(self) -> Rung2ReportMeasurement:
        if self.hit_count + self.miss_count != self.case_count:
            raise ValueError("Rung-2 measurement counts do not partition the cases")
        if self.miss_rate != self.miss_count / self.case_count:
            raise ValueError("Rung-2 measurement miss rate does not match its counts")
        return self


class Rung2ReportCoverage(BaseModel):
    """Aggregate query-token coverage bound to the report's query set."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    query_count: int = Field(gt=0)
    total_query_token_count: int = Field(gt=0)
    total_covered_token_count: int = Field(ge=0)
    fully_covered_query_count: int = Field(ge=0)
    zero_covered_query_count: int = Field(ge=0)
    below_minimum_coverage_query_count: int = Field(ge=0)
    aggregate_coverage_ratio: float = Field(ge=0.0, le=1.0)

    @field_validator("aggregate_coverage_ratio")
    @classmethod
    def _require_finite_ratio(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Rung-2 coverage ratio must be finite")
        return value

    @model_validator(mode="after")
    def _enforce_arithmetic(self) -> Rung2ReportCoverage:
        if self.total_query_token_count < self.query_count:
            raise ValueError("total query token count cannot be below query count")
        if self.total_covered_token_count > self.total_query_token_count:
            raise ValueError("covered token count cannot exceed query token count")
        if self.fully_covered_query_count > self.query_count:
            raise ValueError("fully covered query count cannot exceed query count")
        if self.zero_covered_query_count > self.query_count:
            raise ValueError("zero-covered query count cannot exceed query count")
        if self.below_minimum_coverage_query_count > self.query_count:
            raise ValueError("below-minimum query count cannot exceed query count")
        if self.fully_covered_query_count + self.zero_covered_query_count > self.query_count:
            raise ValueError("fully covered and zero-covered queries cannot overlap")
        if self.zero_covered_query_count > self.below_minimum_coverage_query_count:
            raise ValueError("zero-covered queries must be below the minimum coverage threshold")
        expected_ratio = self.total_covered_token_count / self.total_query_token_count
        if self.aggregate_coverage_ratio != expected_ratio:
            raise ValueError("aggregate coverage ratio does not match its token counts")
        return self


class Rung2ReportTopFiveLoss(BaseModel):
    """Aggregate float32-versus-int8 membership-loss evidence."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    case_count: int = Field(gt=0)
    query_count_with_loss: int = Field(ge=0)
    total_lost_record_count: int = Field(ge=0)
    query_loss_rate: float = Field(ge=0.0, le=1.0)

    @field_validator("query_loss_rate")
    @classmethod
    def _require_finite_rate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Rung-2 top-five loss rate must be finite")
        return value

    @model_validator(mode="after")
    def _enforce_arithmetic(self) -> Rung2ReportTopFiveLoss:
        if self.query_count_with_loss > self.case_count:
            raise ValueError("top-five loss query count cannot exceed cases")
        if self.query_loss_rate != self.query_count_with_loss / self.case_count:
            raise ValueError("top-five loss rate does not match its counts")
        return self


class Rung2ReportArtifactEvidence(BaseModel):
    """Identity and byte evidence for the exact compiled bundle."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_relpath: _NON_BLANK
    source_sha256: _SHA256
    bundle_schema_version: int = Field(ge=1)
    bundle_sha256: _SHA256
    bundle_serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)
    matrix_schema_version: int = Field(ge=1)
    matrix_sha256: _SHA256
    matrix_serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)
    bridge_schema_version: int = Field(ge=1)
    bridge_sha256: _SHA256
    bridge_serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)
    manifest_schema_version: int = Field(ge=1)
    manifest_sha256: _SHA256
    manifest_serialized_bytes: int = Field(gt=0, le=DEFAULT_MAX_SERIALIZED_BYTES)
    vocabulary_sha256: _SHA256
    query_token_sha256: _SHA256
    vocabulary_count: int = Field(gt=0)
    query_token_count: int = Field(gt=0)
    manifest_record_count: int = Field(gt=0)
    model_repository: _NON_BLANK
    model_revision: _NON_BLANK
    model_license: _NON_BLANK
    model_dimension: int = Field(gt=0)
    provider_package: _NON_BLANK
    provider_version: _NON_BLANK
    provider_source_sha256: _SHA256
    model_snapshot_sha256: _SHA256
    tokenizer_configuration_sha256: _SHA256
    tokenizer_vocabulary_sha256: _SHA256


class Rung2StandingReport(BaseModel):
    """Auditable held-out report; it never enables the browser tier."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal["cadrumo.docs-search.rung2-standing-report.v1"]
    query_set_version: int = Field(ge=1)
    baseline: Rung2ReportBaseline
    policy: Rung2EvaluationPolicy
    miss_rate_threshold: float = Field(ge=0.0, le=1.0)
    artifact: Rung2ReportArtifactEvidence
    semantic: Rung2ReportMeasurement
    ladder: Rung2ReportMeasurement
    coverage: Rung2ReportCoverage
    top_five_loss: Rung2ReportTopFiveLoss
    measured_quantization_drift: float = Field(ge=0.0, le=2.0)
    maximum_quantization_drift: float = Field(ge=0.0, le=2.0)
    quantization_accepted: bool
    acceptance_evidence_supplied: bool
    approved: bool
    no_locale_or_kind_regression: bool
    browser_config_enabled: Literal[False]
    decision: Rung2ReportDecision
    rejection_reasons: tuple[_NON_BLANK, ...]

    @field_validator(
        "miss_rate_threshold",
        "measured_quantization_drift",
        "maximum_quantization_drift",
    )
    @classmethod
    def _require_finite_measurement(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Rung-2 report measurements must be finite")
        return value

    @field_validator("miss_rate_threshold")
    @classmethod
    def _use_ratified_threshold(cls, value: float) -> float:
        if value != DEFAULT_RUNG2_MISS_RATE_THRESHOLD:
            raise ValueError("Rung-2 report must use the ratified miss-rate threshold")
        return value

    @model_validator(mode="after")
    def _enforce_decision_boundary(self) -> Rung2StandingReport:
        if self.measured_quantization_drift > self.maximum_quantization_drift:
            raise ValueError("measured quantization drift exceeds the report bound")
        if self.coverage.query_count != self.query_set_case_count:
            raise ValueError("coverage query count must match the held-out report cases")
        if self.semantic.case_count != self.query_set_case_count:
            raise ValueError("semantic measurement case count must match the held-out report cases")
        if self.ladder.case_count != self.query_set_case_count:
            raise ValueError("ladder measurement case count must match the held-out report cases")
        failures = self._release_failures()
        if self.decision is Rung2ReportDecision.ACCEPTED:
            if failures:
                raise ValueError("accepted Rung-2 report has unmet gates: " + "; ".join(failures))
            if self.rejection_reasons:
                raise ValueError("accepted Rung-2 report cannot contain rejection reasons")
        elif not self.rejection_reasons:
            raise ValueError("rejected Rung-2 report must record rejection reasons")
        return self

    @property
    def query_set_case_count(self) -> int:
        """Return the common held-out case count used by report sections."""

        return self.baseline.case_count

    def _release_failures(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.ladder.miss_rate > self.miss_rate_threshold:
            failures.append("full-ladder miss rate exceeds the accepted threshold")
        if self.coverage.aggregate_coverage_ratio < self.policy.minimum_coverage_ratio:
            failures.append("aggregate query-token coverage is below the policy minimum")
        if self.top_five_loss.query_count_with_loss:
            failures.append("float32-to-int8 top-five membership loss is non-zero")
        if self.measured_quantization_drift > self.maximum_quantization_drift:
            failures.append("quantization drift exceeds the supplied bound")
        if self.artifact.bundle_serialized_bytes > DEFAULT_MAX_SERIALIZED_BYTES:
            failures.append("bundle exceeds the shared serialized-byte bound")
        if not self.quantization_accepted:
            failures.append("quantization evidence is not accepted")
        if not self.acceptance_evidence_supplied:
            failures.append("browser acceptance evidence was not supplied")
        if not self.approved:
            failures.append("browser acceptance is not approved")
        if not self.no_locale_or_kind_regression:
            failures.append("locale or record-kind parity is not proven")
        return tuple(failures)
