"""Real-behaviour tests for the pre-artifact Rung-2 acceptance boundary."""

from __future__ import annotations

import math
from typing import cast

import pytest
from pydantic import ValidationError

from dev.docs.terminology._rung2_acceptance import (
    Rung2AcceptanceError,
    Rung2AcceptanceEvidence,
    Rung2BrowserConfig,
    validate_rung2_browser_config,
)
from dev.docs.terminology._rung2_bridge import Rung2SearchBundle
from dev.docs.terminology._static_matrix import NORMALIZATION_CONTRACT_VERSION

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _acceptance_evidence_data() -> dict[str, object]:
    """Return schema-shaped evidence values for validation-only cases."""
    return {
        "approved": True,
        "minimum_coverage_ratio": 0.8,
        "cosine_floor": 0.75,
        "runner_up_margin": 0.05,
        "maximum_quantization_drift": 0.02,
        "measured_quantization_drift": 0.01,
        "payload_bytes": 1024,
        "quantization_accepted": True,
        "held_out_top_five_loss": False,
        "held_out_miss_rate": 0.0,
        "no_locale_or_kind_regression": True,
    }


def _browser_config_data() -> dict[str, object]:
    """Return a config-only payload without creating or loading an artifact."""
    return {
        "schema_version": "cadrumo.docs-search.rung2-config.v1",
        "enabled": True,
        "normalization_version": NORMALIZATION_CONTRACT_VERSION,
        "bundle_url": "bundle.json",
        # This digest is shape-valid evidence only; no bundle is created or read.
        "bundle_sha256": "0" * 64,
        "acceptance": _acceptance_evidence_data(),
    }


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("minimum_coverage_ratio", math.nan),
        ("cosine_floor", math.inf),
        ("runner_up_margin", -math.inf),
        ("maximum_quantization_drift", math.nan),
        ("measured_quantization_drift", math.inf),
        ("held_out_miss_rate", math.nan),
    ],
)
def test_acceptance_evidence_rejects_non_finite_measurements(field_name: str, value: float) -> None:
    """Non-finite measurements cannot cross the acceptance boundary."""
    data = _acceptance_evidence_data()
    data[field_name] = value

    with pytest.raises(ValidationError) as exc_info:
        Rung2AcceptanceEvidence.model_validate(data)

    assert field_name in str(exc_info.value)


def test_acceptance_evidence_rejects_drift_above_supplied_bound() -> None:
    """Measured quantization drift must not exceed its declared maximum."""
    data = _acceptance_evidence_data()
    data["maximum_quantization_drift"] = 0.01
    data["measured_quantization_drift"] = 0.011

    with pytest.raises(ValidationError, match="drift exceeds acceptance"):
        Rung2AcceptanceEvidence.model_validate(data)


@pytest.mark.parametrize("field_name", ["maximum_quantization_drift", "measured_quantization_drift"])
def test_acceptance_evidence_rejects_drift_outside_absolute_bound(field_name: str) -> None:
    """Drift evidence cannot exceed the shared [0, 2] metric domain."""
    data = _acceptance_evidence_data()
    data[field_name] = 2.001

    with pytest.raises(ValidationError, match=field_name):
        Rung2AcceptanceEvidence.model_validate(data)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("approved", False),
        ("quantization_accepted", False),
        ("held_out_top_five_loss", True),
        ("no_locale_or_kind_regression", False),
    ],
)
def test_acceptance_evidence_rejects_wrong_approval_flags(field_name: str, value: bool) -> None:
    """Every approval flag must carry its exact ratified literal value."""
    data = _acceptance_evidence_data()
    data[field_name] = value

    with pytest.raises(ValidationError) as exc_info:
        Rung2AcceptanceEvidence.model_validate(data)

    assert field_name in str(exc_info.value)


def test_browser_config_rejects_disabled_config() -> None:
    """The browser tier cannot be enabled by a false or missing enablement flag."""
    data = _browser_config_data()
    data["enabled"] = False

    with pytest.raises(ValidationError):
        Rung2BrowserConfig.model_validate(data)


def test_browser_config_rejects_wrong_normalization_contract() -> None:
    """Browser tokenization must use the shared normalization contract."""
    data = _browser_config_data()
    data["normalization_version"] = "not-the-shared-normalization-contract"

    with pytest.raises(ValidationError, match="normalization version"):
        Rung2BrowserConfig.model_validate(data)


def test_browser_config_rejects_extra_fields() -> None:
    """Unknown config fields cannot silently widen the browser contract."""
    data = _browser_config_data()
    data["unexpected"] = True

    with pytest.raises(ValidationError):
        Rung2BrowserConfig.model_validate(data)


def test_validate_browser_config_rejects_non_bundle_without_mutating_config() -> None:
    """The bundle type guard runs before any bundle-dependent acceptance work."""
    config = Rung2BrowserConfig.model_validate(_browser_config_data())
    before = config.model_dump(mode="json")
    non_bundle = cast(Rung2SearchBundle, object())

    with pytest.raises(Rung2AcceptanceError, match="already validated Rung2SearchBundle"):
        validate_rung2_browser_config(config, non_bundle)

    assert config.model_dump(mode="json") == before
