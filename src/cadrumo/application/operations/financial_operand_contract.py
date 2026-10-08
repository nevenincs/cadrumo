"""Exact typed batch identity and runtime-only financial operand handoff.

The declared model is an in-memory domain model. Its validation schema names
that model; it is not an operation request serialization schema. Values and
content-derived fingerprints never enter any record defined here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.hashing import content_hash_hex
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect
from ...core.time.utc import validate_utc_aware
from .models import CredentialFreeOperationRequest, OperationIdentity, OperationReference, OperationRevision
from .schema_identity import OperationSchemaIdentityV1


class CredentialFreeFinancialOperationRequest(CredentialFreeOperationRequest):
    """Amount-free request binding one exact transient domain baseline."""

    financial_baseline_ref: Hex64Str


class OperationFinancialOperandRefusalCode(StrEnum):
    """Bounded reasons for refusing a typed custody transition."""

    EXPIRED = "expired"
    CANCELLED = "cancelled"
    UNKNOWN_REQUIREMENT = "unknown_requirement"
    TERMINAL_OPERATION = "terminal_operation"
    WRONG_MODEL = "wrong_model"
    WRONG_BASELINE = "wrong_baseline"
    WRONG_GRANT = "wrong_grant"
    STALE_REVISION = "stale_revision"
    DUPLICATE_SUBMISSION = "duplicate_submission"
    DUPLICATE_CONSUMPTION = "duplicate_consumption"
    OWNER_LOST = "owner_lost"


class OperationFinancialOperandRefusedError(CadrumoError):
    """A custody refusal carrying a closed code and no financial input."""

    def __init__(self, reason: OperationFinancialOperandRefusalCode) -> None:
        """Retain only the safe refusal code."""
        self.reason = reason
        super().__init__(f"financial operand handoff refused: {reason.value}")


class OperationTransientFinancialOperandRequirementV1(BaseModel):
    """The amount-free exact identity of one private runtime handoff."""

    model_config = STRICT_FROZEN_CONFIG

    protocol_version: Literal[1] = 1
    identity: OperationIdentity
    invocation_revision: OperationRevision
    handoff_id: Hex64Str
    grant_fingerprint: ContentDigest
    operand_schema: OperationSchemaIdentityV1
    baseline_schema: OperationSchemaIdentityV1
    domain_baseline_ref: Hex64Str
    expires_at: datetime

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_expiry(self) -> OperationTransientFinancialOperandRequirementV1:
        validate_utc_aware(self.expires_at)
        return self


class OperationFinancialOperandEffectReceiptV1(BaseModel):
    """A value-free authoritative domain effect proof for the exact handoff."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    handoff_id: Hex64Str
    domain_baseline_ref: Hex64Str
    effect: OperationEffect
    result_ref: OperationReference | None = None


type OperationFinancialOperandEffectReceiptResolver = Callable[
    [OperationTransientFinancialOperandRequirementV1],
    Awaitable[OperationFinancialOperandEffectReceiptV1 | None],
]


class OperationTransientFinancialOperandPublicDeclarationV1(BaseModel):
    """Published typed custody policy, without private Python bindings or values."""

    model_config = STRICT_FROZEN_CONFIG
    protocol_version: Literal[1] = 1
    operand_schema: OperationSchemaIdentityV1
    baseline_schema: OperationSchemaIdentityV1
    lifetime_seconds: float = Field(gt=0, le=1800, allow_inf_nan=False)


class OperationTransientFinancialOperandDeclarationV1(BaseModel):
    """Trusted registration of the single exact typed operand and its baseline."""

    model_config = STRICT_FROZEN_CONFIG

    protocol_version: Literal[1] = 1
    operand_type: type[BaseModel]
    operand_schema: OperationSchemaIdentityV1
    baseline_type: type[BaseModel]
    baseline_schema: OperationSchemaIdentityV1
    baseline_accessor: Callable[[BaseModel], BaseModel]
    baseline_reference: Callable[[BaseModel], Hex64Str]
    lifetime: timedelta
    effect_receipt_resolver: OperationFinancialOperandEffectReceiptResolver

    @model_validator(mode="after")
    def _validate_declaration(self) -> OperationTransientFinancialOperandDeclarationV1:
        if self.lifetime <= timedelta() or self.lifetime > timedelta(minutes=30):
            raise ValueError("financial operand lifetime must be positive and at most 30 minutes")
        for model_type, identity in (
            (self.operand_type, self.operand_schema),
            (self.baseline_type, self.baseline_schema),
        ):
            configuration = model_type.model_config
            if (
                not configuration.get("frozen")
                or not configuration.get("strict")
                or configuration.get("extra") != "forbid"
            ):
                raise ValueError("financial operand and baseline models must be strict frozen and closed")
            expected = financial_operand_model_identity(
                schema_id=identity.schema_id, schema_version=identity.schema_version, model_type=model_type
            )
            if identity != expected:
                raise ValueError("financial operand model schema identity does not reproduce")
        return self


@dataclass(slots=True)
class OperationTransientFinancialOperandSubmissionV1:
    """Private call-scoped transfer, deliberately outside every serializable DTO.

    The service discards this object after the broker accepts or refuses it.
    Mutable grant buffers can be cleared; immutable domain values are released
    by dropping references, with no claim of erasing Python object memory.
    """

    requirement: OperationTransientFinancialOperandRequirementV1
    grant: bytearray = field(repr=False)
    operand: BaseModel | None = field(repr=False)

    def release(self) -> None:
        """Clear the mutable bearer and drop the submitting scope's operand."""
        self.grant[:] = b"\x00" * len(self.grant)
        self.operand = None


def financial_operand_model_identity(
    *, schema_id: str, schema_version: int, model_type: type[BaseModel]
) -> OperationSchemaIdentityV1:
    """Name an in-memory validation contract without exposing its Python type.

    The private declaration binds the concrete model. The public identity
    contains only the stable identifier, version and authored schema digest.
    No domain instance is serialized or hashed to create this identity.
    """
    return OperationSchemaIdentityV1(
        schema_id=schema_id,
        schema_version=schema_version,
        schema_fingerprint=content_hash_hex(model_type.model_json_schema(mode="validation")),
    )
