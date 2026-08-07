"""Real-behaviour checks for the strict P02.S07 standing-report contract."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from dev.docs.terminology._miss_rate import load_held_out_query_set
from dev.docs.terminology._rung2_acceptance import Rung2AcceptanceEvidence
from dev.docs.terminology._rung2_evaluation import Rung2EvaluationPolicy
from dev.docs.terminology._rung2_report import (
    RUNG2_STANDING_REPORT_SCHEMA_VERSION,
    Rung2ReportArtifactEvidence,
    Rung2ReportBaseline,
    Rung2ReportCoverage,
    Rung2ReportDecision,
    Rung2ReportMeasurement,
    Rung2ReportTopFiveLoss,
    Rung2StandingReport,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_QUERY_SET = load_held_out_query_set()
_CASE_COUNT = len(_QUERY_SET.cases)
_PRE_RUNG2_MISS_RATE = 0.1875
_POST_RUNG2_HIT_COUNT = 17
_POST_RUNG2_MISS_COUNT = _CASE_COUNT - _POST_RUNG2_HIT_COUNT


def _policy() -> Rung2EvaluationPolicy:
    """Use the explicit policy recorded with the failed measurement."""
    return Rung2EvaluationPolicy(
        minimum_coverage_ratio=0.8,
        cosine_floor=0.75,
        runner_up_margin=0.05,
        result_limit=5,
    )


def _baseline(case_count: int = _CASE_COUNT) -> Rung2ReportBaseline:
    """Build the committed pre-Rung-2 baseline with its exact arithmetic."""
    return Rung2ReportBaseline(
        case_count=case_count,
        hit_count=case_count - 6,
        miss_count=6,
        miss_rate=_PRE_RUNG2_MISS_RATE,
    )


def _measurement(
    *,
    case_count: int = _CASE_COUNT,
    hit_count: int = _POST_RUNG2_HIT_COUNT,
    miss_count: int = _POST_RUNG2_MISS_COUNT,
) -> Rung2ReportMeasurement:
    """Build a report measurement whose rate is derived from its counts."""
    return Rung2ReportMeasurement(
        case_count=case_count,
        hit_count=hit_count,
        miss_count=miss_count,
        miss_rate=miss_count / case_count,
    )


def _coverage(query_count: int = _CASE_COUNT) -> Rung2ReportCoverage:
    """Build complete coverage evidence over the committed held-out corpus."""
    return Rung2ReportCoverage(
        query_count=query_count,
        total_query_token_count=query_count,
        total_covered_token_count=query_count,
        fully_covered_query_count=query_count,
        zero_covered_query_count=0,
        below_minimum_coverage_query_count=0,
        aggregate_coverage_ratio=1.0,
    )


def _top_five_loss() -> Rung2ReportTopFiveLoss:
    """Build the measured zero-loss float32/int8 top-five evidence."""
    return Rung2ReportTopFiveLoss(
        case_count=_CASE_COUNT,
        query_count_with_loss=0,
        total_lost_record_count=0,
        query_loss_rate=0.0,
    )


def _artifact() -> Rung2ReportArtifactEvidence:
    """Build shape-valid identity evidence for the bounded report payload."""
    return Rung2ReportArtifactEvidence(
        source_relpath="dist/terminology/rung2-bundle.json",
        source_sha256="0" * 64,
        bundle_schema_version=1,
        bundle_sha256="1" * 64,
        bundle_serialized_bytes=2_130_942,
        matrix_schema_version=1,
        matrix_sha256="2" * 64,
        matrix_serialized_bytes=1_024,
        bridge_schema_version=1,
        bridge_sha256="3" * 64,
        bridge_serialized_bytes=1_024,
        manifest_schema_version=1,
        manifest_sha256="4" * 64,
        manifest_serialized_bytes=1_024,
        vocabulary_sha256="5" * 64,
        query_token_sha256="6" * 64,
        vocabulary_count=1,
        query_token_count=1,
        manifest_record_count=1,
        model_repository="minishlab/potion-multilingual-128M",
        model_revision="e7421cd79c75fc506b88bb75723ae0a234994720",
        model_license="MIT",
        model_dimension=256,
        provider_package="model2vec",
        provider_version="0.3.0",
        provider_source_sha256="7" * 64,
        model_snapshot_sha256="8" * 64,
        tokenizer_configuration_sha256="9" * 64,
        tokenizer_vocabulary_sha256="a" * 64,
    )


def _failed_report_data() -> dict[str, object]:
    """Return a failed post-Rung-2 report with all release gates explicit."""
    return {
        "schema_version": RUNG2_STANDING_REPORT_SCHEMA_VERSION,
        "query_set_version": _QUERY_SET.version,
        "baseline": _baseline(),
        "policy": _policy(),
        "miss_rate_threshold": 0.10,
        "artifact": _artifact(),
        "semantic": _measurement(),
        "ladder": _measurement(),
        "coverage": _coverage(),
        "top_five_loss": _top_five_loss(),
        "measured_quantization_drift": 0.002751,
        "maximum_quantization_drift": 0.01,
        "quantization_accepted": True,
        "acceptance_evidence_supplied": False,
        "approved": False,
        "no_locale_or_kind_regression": True,
        "browser_config_enabled": False,
        "decision": Rung2ReportDecision.REJECTED,
        "rejection_reasons": (
            "full-ladder miss rate exceeds the accepted threshold",
            "browser acceptance evidence was not supplied",
            "browser acceptance is not approved",
        ),
    }


def test_failed_measurement_remains_rejected_and_does_not_enable_rung2() -> None:
    """A failed 15/32 result cannot replace the standing baseline or enable Rung 2."""
    report = Rung2StandingReport.model_validate(_failed_report_data())

    assert report.baseline.miss_rate == pytest.approx(_PRE_RUNG2_MISS_RATE)
    assert report.ladder.hit_count == _POST_RUNG2_HIT_COUNT
    assert report.ladder.miss_rate == pytest.approx(15 / 32)
    assert report.decision is Rung2ReportDecision.REJECTED
    assert report.browser_config_enabled is False
    assert report.acceptance_evidence_supplied is False
    assert report.approved is False
    assert report.rejection_reasons


def test_failed_measurement_cannot_cross_the_acceptance_boundary() -> None:
    """The ratified miss-rate ceiling rejects evidence before browser enablement."""
    with pytest.raises(ValidationError, match="held_out_miss_rate"):
        Rung2AcceptanceEvidence.model_validate(
            {
                "approved": True,
                "minimum_coverage_ratio": 0.8,
                "cosine_floor": 0.75,
                "runner_up_margin": 0.05,
                "maximum_quantization_drift": 0.01,
                "measured_quantization_drift": 0.002751,
                "payload_bytes": 2_130_942,
                "quantization_accepted": True,
                "held_out_top_five_loss": False,
                "held_out_miss_rate": 15 / 32,
                "no_locale_or_kind_regression": True,
            },
        )


@pytest.mark.parametrize(
    ("model", "data", "message"),
    [
        (
            Rung2ReportBaseline,
            {"case_count": 32, "hit_count": 26, "miss_count": 6, "miss_rate": 0.2},
            "baseline miss rate",
        ),
        (
            Rung2ReportMeasurement,
            {"case_count": 32, "hit_count": 18, "miss_count": 15, "miss_rate": 15 / 32},
            "measurement counts",
        ),
        (
            Rung2ReportCoverage,
            {
                "query_count": 32,
                "total_query_token_count": 32,
                "total_covered_token_count": 31,
                "fully_covered_query_count": 33,
                "zero_covered_query_count": 0,
                "below_minimum_coverage_query_count": 0,
                "aggregate_coverage_ratio": 31 / 32,
            },
            "fully covered query count",
        ),
        (
            Rung2ReportCoverage,
            {
                "query_count": 32,
                "total_query_token_count": 31,
                "total_covered_token_count": 31,
                "fully_covered_query_count": 0,
                "zero_covered_query_count": 0,
                "below_minimum_coverage_query_count": 0,
                "aggregate_coverage_ratio": 1.0,
            },
            "total query token count",
        ),
        (
            Rung2ReportCoverage,
            {
                "query_count": 32,
                "total_query_token_count": 32,
                "total_covered_token_count": 32,
                "fully_covered_query_count": 32,
                "zero_covered_query_count": 1,
                "below_minimum_coverage_query_count": 1,
                "aggregate_coverage_ratio": 1.0,
            },
            "cannot overlap",
        ),
        (
            Rung2ReportTopFiveLoss,
            {"case_count": 32, "query_count_with_loss": 1, "total_lost_record_count": 0, "query_loss_rate": 0.0},
            "top-five loss rate",
        ),
    ],
)
def test_report_sections_reject_inconsistent_arithmetic(
    model: type[BaseModel], data: dict[str, object], message: str
) -> None:
    """Every public report section derives its rates and counts consistently."""
    with pytest.raises(ValidationError, match=message):
        model.model_validate(data)


def test_standing_report_rejects_mismatched_section_case_identity() -> None:
    """Coverage and measurements must refer to the same held-out case set."""
    data = _failed_report_data()
    data["coverage"] = _coverage(query_count=_CASE_COUNT - 1)

    with pytest.raises(ValidationError, match="coverage query count"):
        Rung2StandingReport.model_validate(data)


def test_standing_report_rejects_malformed_artifact_identity() -> None:
    """Artifact evidence must carry canonical SHA-256 identity fields."""
    data = _failed_report_data()
    artifact = _artifact().model_dump(mode="python")
    artifact["bundle_sha256"] = "not-a-sha256"
    data["artifact"] = artifact

    with pytest.raises(ValidationError, match="bundle_sha256"):
        Rung2StandingReport.model_validate(data)


def test_standing_report_rejects_browser_enablement_literal() -> None:
    """The standing report cannot be used as a browser configuration switch."""
    data = _failed_report_data()
    data["browser_config_enabled"] = True

    with pytest.raises(ValidationError, match="browser_config_enabled"):
        Rung2StandingReport.model_validate(data)
