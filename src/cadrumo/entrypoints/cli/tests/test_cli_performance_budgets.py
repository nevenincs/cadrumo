"""Noise-resistant contracts for CLI latency calibration and budgets."""

from __future__ import annotations

import pytest

from cadrumo.tests.cli_performance import (
    LatencyBudget,
    LatencyDistribution,
    PerformanceCalibrationPolicy,
    evaluate_latency_budget,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_calibration_rejects_single_sample_and_missing_warmup() -> None:
    with pytest.raises(ValueError, match="three measured samples"):
        PerformanceCalibrationPolicy(sample_count=1)
    with pytest.raises(ValueError, match="one warmup"):
        PerformanceCalibrationPolicy(warmup_runs=0)
    with pytest.raises(ValueError, match="three samples"):
        LatencyDistribution.from_samples((0.01,))


def test_one_fast_sample_cannot_rescue_a_slow_distribution() -> None:
    distribution = LatencyDistribution.from_samples((0.01, 2.0, 2.1, 2.2, 2.3))

    result = evaluate_latency_budget(distribution, LatencyBudget(maximum_median_seconds=1.0))

    assert distribution.median_seconds == 2.1
    assert result.passed is False
    assert result.violations == ("absolute-median",)
    assert result.outlier_samples_seconds == (2.0, 2.1, 2.2, 2.3)


def test_absolute_and_control_ratio_limits_are_independent_and_composable() -> None:
    observed = LatencyDistribution.from_samples((0.38, 0.4, 0.42))
    control = LatencyDistribution.from_samples((0.09, 0.1, 0.11))

    ratio_failure = evaluate_latency_budget(
        observed,
        LatencyBudget(maximum_median_seconds=0.5, maximum_control_ratio=3.0),
        control=control,
    )
    absolute_failure = evaluate_latency_budget(observed, LatencyBudget(maximum_median_seconds=0.3))

    assert ratio_failure.control_ratio == 4.0
    assert ratio_failure.violations == ("control-ratio",)
    assert absolute_failure.control_ratio is None
    assert absolute_failure.violations == ("absolute-median",)


def test_ratio_budget_requires_a_positive_control_distribution() -> None:
    observed = LatencyDistribution.from_samples((0.1, 0.1, 0.1))

    with pytest.raises(ValueError, match="control distribution"):
        evaluate_latency_budget(observed, LatencyBudget(maximum_control_ratio=2.0))
    with pytest.raises(ValueError, match="control median"):
        evaluate_latency_budget(
            observed,
            LatencyBudget(maximum_control_ratio=2.0),
            control=LatencyDistribution.from_samples((0.0, 0.0, 0.0)),
        )


@pytest.mark.parametrize("samples", [(1.0, float("nan"), 2.0), (1.0, -0.1, 2.0)])
def test_distribution_rejects_invalid_measurements(samples: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        LatencyDistribution.from_samples(samples)
