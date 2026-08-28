"""Runtime-only transient financial operand contracts for operation execution.

A transient financial operand is an amount an operator supplies while one
operation is already running: a figure the executor needs once, that belongs to
no ledger record and outlives nothing. It is deliberately not an ephemeral
secret and not a persistent secure reference, and the three must not be
collapsed.

An ephemeral secret is credential material the runtime holds under exact
custody; a secure reference names bytes that live encrypted in the store. An
operand is neither. It is a financial quantity with real declarative meaning -
a currency, a scale, a bounded magnitude - which is exactly why it needs its
own declaration rather than being smuggled through a secret port that treats
its payload as opaque bytes.

The value never appears as a field on any model in this module. Every record
here describes an operand - which one, for which interaction, until when, and
what became of it - while the amount itself crosses only as a call argument, so
there is no shape in this contract that a caller could serialize, log, or
persist by accident.

Hashing is prohibited outright rather than discouraged. A digest of a financial
amount over a known scale is not an anonymization: the domain is small enough
to invert by enumeration, so a stored digest is a stored amount wearing a
disguise. No record here carries a digest, fingerprint, or any other durable
derivative of an operand.

See Also:
    :class:`~cadrumo.application.operations.secret_submission.EphemeralSecretSubmission`
        The distinct one-shot port for credential material, not for amounts.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.time import validate_utc_aware
from .interactions import OperationInteractionId
from .models import OperationIdentity, OperationRevision

type OperationFinancialOperandKind = Annotated[
    str,
    Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"),
]

_MAX_OPERAND_LIFETIME = timedelta(minutes=30)
_MAX_OPERAND_SCALE = 6


class OperationFinancialOperandRefusalReason(StrEnum):
    """Why one operand wait ended without a delivered amount."""

    EXPIRED = "expired"
    CANCELLED = "cancelled"
    OUT_OF_DECLARED_RANGE = "out_of_declared_range"
    SCALE_NOT_REPRESENTABLE = "scale_not_representable"
    UNKNOWN_REQUIREMENT = "unknown_requirement"
    ALREADY_SETTLED = "already_settled"


class _OperandModel(BaseModel):
    """Common strict, immutable posture for operand records."""

    model_config = STRICT_FROZEN_CONFIG


class OperationTransientFinancialOperandDeclaration(_OperandModel):
    """Registry declaration of one operand an operation may ask for mid-flight.

    The declaration is what makes an operand different from an opaque secret:
    it states the currency, the representable scale and the accepted magnitude
    up front, so a submitted amount can be refused on its own terms instead of
    failing somewhere inside the executor.
    """

    operand_kind: OperationFinancialOperandKind
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    scale: Annotated[int, Field(ge=0, le=_MAX_OPERAND_SCALE)]
    minimum: Decimal
    maximum: Decimal
    lifetime: timedelta

    @model_validator(mode="after")
    def _validate_declared_range(self) -> OperationTransientFinancialOperandDeclaration:
        if self.lifetime <= timedelta() or self.lifetime > _MAX_OPERAND_LIFETIME:
            raise ValueError("transient financial operand lifetime must be positive and no longer than 30 minutes")
        if self.minimum > self.maximum:
            raise ValueError("transient financial operand minimum cannot exceed its maximum")
        return self

    def admits(self, amount: Decimal) -> bool:
        """Report whether one amount is representable and within the declared range."""
        exponent = amount.as_tuple().exponent
        if not isinstance(exponent, int):
            # NaN / infinite Decimals carry a sentinel string exponent and are
            # never representable at a finite declared scale.
            return False
        if -exponent > self.scale:
            return False
        return self.minimum <= amount <= self.maximum


class OperationTransientFinancialOperandRequirement(_OperandModel):
    """Durable identity of one exact runtime-only operand wait.

    This record is safe to hold and to show: it names which operand an
    interaction is waiting for and until when, and carries no amount.
    """

    identity: OperationIdentity
    interaction_id: OperationInteractionId
    revision: OperationRevision
    operand_kind: OperationFinancialOperandKind
    expires_at: datetime

    @model_validator(mode="after")
    def _validate_expiry(self) -> OperationTransientFinancialOperandRequirement:
        validate_utc_aware(self.expires_at)
        return self


class OperationTransientFinancialOperandAcknowledgement(_OperandModel):
    """Confirmation that one submitted operand was accepted into runtime custody."""

    outcome: Literal["accepted"] = "accepted"
    requirement: OperationTransientFinancialOperandRequirement
    accepted_at: datetime

    @model_validator(mode="after")
    def _validate_accepted_at(self) -> OperationTransientFinancialOperandAcknowledgement:
        validate_utc_aware(self.accepted_at)
        return self


class OperationTransientFinancialOperandRefusal(_OperandModel):
    """Refusal of one operand submission, naming the requirement it answered."""

    outcome: Literal["refused"] = "refused"
    requirement: OperationTransientFinancialOperandRequirement
    reason: OperationFinancialOperandRefusalReason
    refused_at: datetime

    @model_validator(mode="after")
    def _validate_refused_at(self) -> OperationTransientFinancialOperandRefusal:
        validate_utc_aware(self.refused_at)
        return self


class OperationTransientFinancialOperandExpiry(_OperandModel):
    """Record that one operand wait lapsed before any amount arrived."""

    outcome: Literal["expired"] = "expired"
    requirement: OperationTransientFinancialOperandRequirement
    expired_at: datetime

    @model_validator(mode="after")
    def _validate_expired_at(self) -> OperationTransientFinancialOperandExpiry:
        validate_utc_aware(self.expired_at)
        return self


class OperationTransientFinancialOperandRelease(_OperandModel):
    """Record that runtime custody of one operand ended and its buffer was cleared."""

    outcome: Literal["released"] = "released"
    requirement: OperationTransientFinancialOperandRequirement
    released_at: datetime

    @model_validator(mode="after")
    def _validate_released_at(self) -> OperationTransientFinancialOperandRelease:
        validate_utc_aware(self.released_at)
        return self


type OperationTransientFinancialOperandDelivery = (
    OperationTransientFinancialOperandAcknowledgement | OperationTransientFinancialOperandRefusal
)
"""The settled outcome of one operand submission, accepted or refused."""


@runtime_checkable
class OperationTransientFinancialOperandSubmission(Protocol):
    """One-shot submission port for a transient financial operand.

    The amount is a parameter and never a field, so nothing in this contract
    can carry it out of the call it was supplied to.
    """

    async def submit_transient_financial_operand(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
        amount: Decimal,
    ) -> OperationTransientFinancialOperandDelivery:
        """Transfer one declared amount into exact-bound runtime custody."""
        ...


@runtime_checkable
class OperationTransientFinancialOperandAccess(Protocol):
    """Executor-only scoped read of the operand its own definition declared."""

    def declared_operand(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> Decimal:
        """Return the amount in custody for one requirement this executor owns."""
        ...


@runtime_checkable
class OperationTransientFinancialOperandProtocolV1(Protocol):
    """The sole broker contract binding an operand wait to its settlement.

    A broker opens exactly one wait per requirement, settles it once, and
    releases custody. It never stores an amount beyond the release, and it
    exposes no method that would return a durable derivative of one.
    """

    def declare_requirement(
        self,
        declaration: OperationTransientFinancialOperandDeclaration,
        *,
        identity: OperationIdentity,
        interaction_id: OperationInteractionId,
        revision: OperationRevision,
    ) -> OperationTransientFinancialOperandRequirement:
        """Open one bounded wait for the operand this declaration describes."""
        ...

    def grant_access(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> OperationTransientFinancialOperandAccess:
        """Return executor-scoped access to one accepted operand."""
        ...

    def release(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> OperationTransientFinancialOperandRelease:
        """End custody of one operand and clear the buffer holding it."""
        ...

    def expire_lapsed(
        self,
        *,
        now: datetime,
    ) -> tuple[OperationTransientFinancialOperandExpiry, ...]:
        """Settle every wait whose declared lifetime has elapsed."""
        ...


__all__ = [
    "OperationFinancialOperandKind",
    "OperationFinancialOperandRefusalReason",
    "OperationTransientFinancialOperandAccess",
    "OperationTransientFinancialOperandAcknowledgement",
    "OperationTransientFinancialOperandDeclaration",
    "OperationTransientFinancialOperandDelivery",
    "OperationTransientFinancialOperandExpiry",
    "OperationTransientFinancialOperandProtocolV1",
    "OperationTransientFinancialOperandRefusal",
    "OperationTransientFinancialOperandRelease",
    "OperationTransientFinancialOperandRequirement",
    "OperationTransientFinancialOperandSubmission",
]
