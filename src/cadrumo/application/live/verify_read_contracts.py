"""Typed contracts for exact-profile verify observation reads."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity_check_verdict import IdentityCheckVerdictValue
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from .verify import VerifyObservation, VerifySurface

_OBSERVATION_ID_PREFIX = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[0-9a-f]+$"),
]
_NIF = Annotated[str, Field(min_length=1, max_length=32)]


class VerifyListRequest(BaseModel):
    """Filter one exact profile's local verify history."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    surface: VerifySurface | None = None
    nif: _NIF | None = None


class VerifyViewRequest(BaseModel):
    """Resolve one local verify observation by full digest or unambiguous prefix."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    observation_id: _OBSERVATION_ID_PREFIX


class VerifyLatestRequest(BaseModel):
    """Read the latest stored observation for an exact surface and NIF."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    surface: VerifySurface
    nif: _NIF


class VerifyObservationSummaryPublicV1(BaseModel):
    """Allowlisted fields already present in the existing verify list row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observation_id: ContentDigest
    surface: VerifySurface
    nif: _NIF
    verdict: IdentityCheckVerdictValue
    expected: IdentityCheckVerdictValue | None
    matched_expectation: bool | None
    checked_at: datetime

    @field_validator("checked_at")
    @classmethod
    @pydantic_validation_boundary
    def _checked_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _expectation_matches_verdict(self) -> Self:
        if self.expected is None and self.matched_expectation is not None:
            raise ValueError("verify observation without an expectation carries a match result")
        if self.expected is not None and self.matched_expectation is not (self.expected == self.verdict):
            raise ValueError("verify observation expectation result disagrees with its verdict")
        return self


class VerifyListOperationReport(BaseModel):
    """Private, profile-scoped list operand with only existing list summary fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    rows: tuple[VerifyObservationSummaryPublicV1, ...]


class VerifyViewOperationReport(BaseModel):
    """Selected encrypted observation retained inside operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observation: VerifyObservation


class VerifyLatestOperationReport(BaseModel):
    """Private latest row and its lookup coordinates, including an empty state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    surface: VerifySurface
    nif: _NIF
    observation: VerifyObservation | None

    @model_validator(mode="after")
    def _observation_matches_query(self) -> Self:
        if self.observation is not None and (
            self.observation.bucket_id != self.bucket_id
            or self.observation.surface is not self.surface
            or self.observation.nif != self.nif
        ):
            raise ValueError("latest verify observation differs from its bucket or lookup coordinates")
        return self


class VerifyObservationPublicV1(VerifyObservationSummaryPublicV1):
    """Detail row with the existing verify view's exact bucket field."""

    bucket_id: BucketId


class VerifyListPublicResultV1(BaseModel):
    """Closed local verify inventory for an authorized whole-profile read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    count: NonNegativeInt
    rows: tuple[VerifyObservationSummaryPublicV1, ...]

    @model_validator(mode="after")
    def _count_matches_rows(self) -> Self:
        if self.count != len(self.rows):
            raise ValueError("verify observation count disagrees with its rows")
        return self


def _require_latest_empty_fields_agree(
    observation_id: ContentDigest | None,
    row_fields: tuple[object | None, ...],
) -> None:
    if observation_id is None and any(value is not None for value in row_fields):
        raise ValueError("empty latest verify result carries observation fields")


def _require_latest_observation_fields_present(
    observation_id: ContentDigest | None,
    verdict: IdentityCheckVerdictValue | None,
    checked_at: datetime | None,
) -> None:
    if observation_id is not None and (verdict is None or checked_at is None):
        raise ValueError("latest verify result lacks observation fields")


def _require_latest_expectation_agrees(
    expected: IdentityCheckVerdictValue | None,
    matched_expectation: bool | None,
    verdict: IdentityCheckVerdictValue | None,
) -> None:
    if expected is None and matched_expectation is not None:
        raise ValueError("latest verify result without an expectation carries a match result")
    if expected is not None and matched_expectation is not (expected == verdict):
        raise ValueError("latest verify expectation result disagrees with its verdict")


class VerifyLatestPublicResultV1(BaseModel):
    """Latest observation fields or the existing all-empty observation state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    observation_id: ContentDigest | None
    surface: VerifySurface
    nif: _NIF
    verdict: IdentityCheckVerdictValue | None = None
    expected: IdentityCheckVerdictValue | None = None
    matched_expectation: bool | None = None
    checked_at: datetime | None = None

    @field_validator("checked_at")
    @classmethod
    @pydantic_validation_boundary
    def _checked_at_is_utc(cls, value: datetime | None) -> datetime | None:
        return validate_utc_aware(value) if value is not None else None

    @model_validator(mode="after")
    def _optional_fields_agree(self) -> Self:
        row_fields = (self.verdict, self.expected, self.matched_expectation, self.checked_at)
        _require_latest_empty_fields_agree(self.observation_id, row_fields)
        _require_latest_observation_fields_present(self.observation_id, self.verdict, self.checked_at)
        _require_latest_expectation_agrees(self.expected, self.matched_expectation, self.verdict)
        return self
