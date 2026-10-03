"""Closed apoderado operation requests, result shapes, and receipt validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ..operations.models import OperationTerminalReceipt, require_succeeded_receipt_references
from .apoderado_service import (
    ApoderadoConfiguration,
    ApoderadoStatus,
)
from .apoderado_text import ApoderadoNotes

APODERADO_STATUS_OPERATION_DEFINITION_ID = "auth.apoderado.status"


APODERADO_CONFIGURE_OPERATION_DEFINITION_ID = "auth.apoderado.configure"


APODERADO_CLEAR_OPERATION_DEFINITION_ID = "auth.apoderado.clear"


APODERADO_CHECK_OPERATION_DEFINITION_ID = "auth.apoderado.check"


APODERADO_REPRESENTED_NIF_SECRET_KIND = "auth.apoderado.represented-nif"  # noqa: S105 - protocol kind, not a secret


type ApoderadoOperationId = Literal[
    "auth.apoderado.status", "auth.apoderado.configure", "auth.apoderado.clear", "auth.apoderado.check"
]


_REFUSAL_CODES = frozenset(
    {
        "REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE",
        "REFUSED_APODERADO_INVALID_REPRESENTED_NIF",
        "REFUSED_APODERADO_UNKNOWN_SCOPE",
    }
)


class ApoderadoStatusRequest(BaseModel):
    """Read one exact profile's offline delegation configuration."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ApoderadoConfigureRequest(BaseModel):
    """Nonidentity choices; represented tax identity uses a one-use secret slot."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    scope_tokens: tuple[str, ...] = Field(min_length=1, max_length=64)
    notes: ApoderadoNotes = ""


class ApoderadoClearRequest(BaseModel):
    """Retire only the named profile's encrypted configuration."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ApoderadoCheckRequest(BaseModel):
    """Request the sealed live-read path, which currently refuses."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


type ApoderadoOperationRequest = (
    ApoderadoStatusRequest | ApoderadoConfigureRequest | ApoderadoClearRequest | ApoderadoCheckRequest
)


class ApoderadoStatusSnapshot(BaseModel):
    """Closed wire copy of every offline status field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bucket_id: UUID
    configured: bool
    represented_nif: str | None = Field(default=None, max_length=16)
    granted_scopes: tuple[str, ...] = ()
    catalogue_version: str | None = None
    configured_at: datetime | None = None

    @classmethod
    def from_status(cls, status: ApoderadoStatus) -> ApoderadoStatusSnapshot:
        """Copy canonical status without a coercive bucket ID validator."""
        return cls(
            bucket_id=UUID(str(status.bucket_id)),
            configured=status.configured,
            represented_nif=status.represented_nif,
            granted_scopes=status.granted_scopes,
            catalogue_version=status.catalogue_version,
            configured_at=status.configured_at,
        )


class ApoderadoConfigurationSnapshot(BaseModel):
    """Closed wire copy of every configured delegation field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bucket_id: UUID
    represented_nif: str = Field(min_length=1, max_length=16)
    granted_scopes: tuple[str, ...]
    catalogue_version: str = Field(min_length=1)
    configured_at: datetime
    notes: ApoderadoNotes = ""

    @classmethod
    def from_configuration(cls, configuration: ApoderadoConfiguration) -> ApoderadoConfigurationSnapshot:
        """Copy the full canonical encrypted record into its public result."""
        return cls(
            bucket_id=UUID(str(configuration.bucket_id)),
            represented_nif=configuration.represented_nif,
            granted_scopes=configuration.granted_scopes,
            catalogue_version=configuration.catalogue_version,
            configured_at=configuration.configured_at,
            notes=configuration.notes,
        )


class ApoderadoOperationProjection(BaseModel):
    """Complete CLI facts or a typed, prewrite refusal for one verb."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    operation_id: ApoderadoOperationId
    outcome: Literal["completed", "prewrite_refusal"]
    effect: OperationEffect
    status: ApoderadoStatusSnapshot | None = None
    configuration: ApoderadoConfigurationSnapshot | None = None
    cleared: bool | None = None
    refusal_code: str | None = None

    @model_validator(mode="after")
    def _one_outcome(self) -> Self:
        if self.outcome == "prewrite_refusal":
            _validate_apoderado_refusal_projection(self)
        else:
            _validate_apoderado_success_projection(self)
        return self


def _validate_apoderado_refusal_projection(projection: ApoderadoOperationProjection) -> None:
    if (
        projection.effect is not OperationEffect.NONE
        or projection.refusal_code not in _REFUSAL_CODES
        or projection.status is not None
        or projection.configuration is not None
        or projection.cleared is not None
    ):
        raise ValueError("apoderado refusal has an invalid effect or payload")


def _validate_apoderado_success_projection(projection: ApoderadoOperationProjection) -> None:
    if projection.refusal_code is not None:
        raise ValueError("apoderado success cannot carry refusal evidence")
    validators = {
        APODERADO_STATUS_OPERATION_DEFINITION_ID: _valid_status_projection,
        APODERADO_CONFIGURE_OPERATION_DEFINITION_ID: _valid_configure_projection,
        APODERADO_CLEAR_OPERATION_DEFINITION_ID: _valid_clear_projection,
    }
    validator = validators.get(projection.operation_id)
    if validator is None or not validator(projection):
        raise ValueError("apoderado success differs from the requested verb or profile")


def _valid_status_projection(projection: ApoderadoOperationProjection) -> bool:
    return (
        projection.status is not None
        and projection.configuration is None
        and projection.cleared is None
        and projection.effect is OperationEffect.NONE
        and projection.status.bucket_id == projection.profile_id
    )


def _valid_configure_projection(projection: ApoderadoOperationProjection) -> bool:
    return (
        projection.configuration is not None
        and projection.status is None
        and projection.cleared is None
        and projection.effect is OperationEffect.UPDATED
        and projection.configuration.bucket_id == projection.profile_id
    )


def _valid_clear_projection(projection: ApoderadoOperationProjection) -> bool:
    return (
        projection.cleared is not None
        and projection.status is None
        and projection.configuration is None
        and projection.effect is (OperationEffect.UPDATED if projection.cleared else OperationEffect.NONE)
    )


class ApoderadoExecutionResult(BaseModel):
    """Encrypted result retained until exact-profile disclosure is authorized."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ApoderadoOperationProjection


def project_apoderado_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the projection matching the terminal receipt and profile."""
    if type(result) is not ApoderadoExecutionResult:
        raise ValueError("invalid private apoderado result")
    projection = result.projection
    if (
        receipt.identity.definition_id != projection.operation_id
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.effect is not projection.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("apoderado result differs from its terminal receipt")
    if projection.outcome == "completed":
        _require_apoderado_success_receipt(receipt)
    else:
        _require_apoderado_refusal_receipt(projection, receipt)
    return projection


def _require_apoderado_success_receipt(receipt: OperationTerminalReceipt) -> None:
    message = "apoderado success has incompatible terminal evidence"
    if receipt.condition is not OperationTerminalCondition.SUCCEEDED:
        raise ValueError(message)
    require_succeeded_receipt_references(receipt, message=message)


def _require_apoderado_refusal_receipt(
    projection: ApoderadoOperationProjection, receipt: OperationTerminalReceipt
) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.result_ref is not None
        or receipt.refusal_ref != projection.refusal_code
        or receipt.refusal_detail_ref is None
    ):
        raise ValueError("apoderado refusal has incompatible terminal evidence")
