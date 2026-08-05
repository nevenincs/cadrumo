"""Typed, source-only acceptance boundary for the Rung-2 browser config.

The browser controller consumes one explicit, fail-closed configuration.  This
module mirrors that configuration as strict source data and validates its
shipping evidence against an already validated :class:`Rung2SearchBundle`.
It does not choose a model, create an artifact, derive a URL, run a sweep, or
read or write files.  Model provenance, licence, vocabulary fingerprint,
artifact hash, and the shared byte envelope remain owned by the bundle
contracts rather than being copied into a second authority.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ._model2vec_provider import (
    POTION_MODEL_DIMENSION,
    POTION_MODEL_LICENSE,
    POTION_MODEL_REPOSITORY,
    POTION_MODEL_REVISION,
)
from ._rung2_bridge import Rung2SearchBundle
from ._static_matrix import DEFAULT_MAX_SERIALIZED_BYTES, NORMALIZATION_CONTRACT_VERSION, ModelMetadata

__all__ = [
    "Rung2AcceptanceError",
    "Rung2AcceptanceEvidence",
    "Rung2BrowserConfig",
    "validate_rung2_browser_config",
]

_SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_BUNDLE_URL = Annotated[str, StringConstraints(min_length=1)]


class Rung2AcceptanceError(ValueError):
    """Raised when browser configuration is not accepted for one bundle."""


class Rung2AcceptanceEvidence(BaseModel):
    """Measured evidence required before the browser semantic tier can run."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    approved: Literal[True]
    minimum_coverage_ratio: float = Field(gt=0.0, le=1.0)
    cosine_floor: float = Field(ge=-1.0, le=1.0)
    runner_up_margin: float = Field(ge=0.0, le=2.0)
    maximum_quantization_drift: float = Field(ge=0.0, le=2.0)
    measured_quantization_drift: float = Field(ge=0.0, le=2.0)
    payload_bytes: int = Field(ge=1, le=DEFAULT_MAX_SERIALIZED_BYTES)
    quantization_accepted: Literal[True]
    held_out_top_five_loss: Literal[False]
    held_out_miss_rate: float = Field(ge=0.0, le=0.1)
    no_locale_or_kind_regression: Literal[True]

    @field_validator(
        "minimum_coverage_ratio",
        "cosine_floor",
        "runner_up_margin",
        "maximum_quantization_drift",
        "measured_quantization_drift",
        "held_out_miss_rate",
    )
    @classmethod
    def _require_finite_measurement(cls, value: float) -> float:
        """Reject non-finite measurements before they can enable the tier."""
        if not math.isfinite(value):
            raise ValueError("Rung-2 acceptance measurements must be finite")
        return value

    @model_validator(mode="after")
    def _measured_drift_is_accepted(self) -> Rung2AcceptanceEvidence:
        """Require the measured quantization drift to meet its supplied bound."""
        if self.measured_quantization_drift > self.maximum_quantization_drift:
            raise ValueError("measured quantization drift exceeds acceptance")
        return self


class Rung2BrowserConfig(BaseModel):
    """The exact fail-closed configuration shape consumed by the browser."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal["cadrumo.docs-search.rung2-config.v1"]
    enabled: Literal[True]
    normalization_version: str = Field(min_length=1)
    bundle_url: _BUNDLE_URL
    bundle_sha256: _SHA256
    acceptance: Rung2AcceptanceEvidence

    @field_validator("normalization_version")
    @classmethod
    def _uses_shared_normalization_contract(cls, value: str) -> str:
        """Keep the browser tokenization marker tied to the matrix contract."""
        if value != NORMALIZATION_CONTRACT_VERSION:
            raise ValueError("Rung-2 normalization version does not match the matrix contract")
        return value

    @field_validator("bundle_url")
    @classmethod
    def _require_non_blank_bundle_url(cls, value: str) -> str:
        """Require an operator-supplied URL without constructing or resolving it."""
        if not value.strip():
            raise ValueError("Rung-2 bundle_url must be non-blank")
        return value


def validate_rung2_browser_config(
    config: Rung2BrowserConfig | Mapping[str, object],
    bundle: Rung2SearchBundle,
) -> Rung2BrowserConfig:
    """Validate one browser config against an already validated bundle.

    ``bundle_url`` is accepted only as supplied by the caller; URL resolution
    remains the browser's same-origin policy.  The config's payload hash and
    measured byte count must identify the exact bundle and its shared bound.
    The bundle remains the sole authority for model licence/provenance and the
    matrix vocabulary fingerprint, including the bridge's hash link to it.
    """
    if not isinstance(bundle, Rung2SearchBundle):
        raise Rung2AcceptanceError("bundle must be an already validated Rung2SearchBundle")
    try:
        validated = config if isinstance(config, Rung2BrowserConfig) else Rung2BrowserConfig.model_validate(config)
    except ValueError as exc:
        raise Rung2AcceptanceError(f"invalid Rung-2 browser config: {exc}") from exc

    bundle_bytes = bundle.to_json_bytes()
    bundle_size = len(bundle_bytes)
    bundle_sha256 = sha256(bundle_bytes).hexdigest()
    if validated.bundle_sha256 != bundle_sha256:
        raise Rung2AcceptanceError("Rung-2 config bundle_sha256 does not match canonical bundle bytes")
    if validated.acceptance.payload_bytes != bundle_size or bundle.serialized_bytes != bundle_size:
        raise Rung2AcceptanceError("Rung-2 payload byte evidence does not match the validated bundle")
    if not 1 <= bundle_size <= DEFAULT_MAX_SERIALIZED_BYTES:
        raise Rung2AcceptanceError("validated Rung-2 bundle exceeds the shared byte bound")

    model = bundle.matrix.model
    try:
        ModelMetadata.model_validate(model)
    except ValueError as exc:
        raise Rung2AcceptanceError("validated Rung-2 bundle has invalid model provenance or licence") from exc
    if (
        model.repository != POTION_MODEL_REPOSITORY
        or model.revision != POTION_MODEL_REVISION
        or model.spdx_license != POTION_MODEL_LICENSE
        or model.dimension != POTION_MODEL_DIMENSION
    ):
        raise Rung2AcceptanceError("validated Rung-2 bundle does not use the ratified Potion model identity")
    if bundle.matrix.vocabulary_sha256 != bundle.bridge.matrix_vocabulary_sha256:
        raise Rung2AcceptanceError("Rung-2 bundle vocabulary fingerprint is not bridge-linked")
    if model.tokenizer.normalization.algorithm != validated.normalization_version:
        raise Rung2AcceptanceError("Rung-2 config normalization does not match the validated bundle")

    return validated
