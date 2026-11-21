"""The persisted fact of whether one evidence record's stored bytes can be read.

A purchase-invoice evidence record names bytes held in secure custody. Whether
those bytes match a readable document shape is decided by the document-shape
probe, which needs the decrypted bytes. The add path already asks it before any
custody write, and the person can ask it again for a record that predates this
fact. The answer is kept on the record so a list can show it without decrypting
anything; a record without it was never checked.

This module imports no evidence record type, so the record and the operations
that serve it can both depend on it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, model_validator

from ...core.document_shape import DocumentShape
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import UtcInstant
from .preconditions import LedgerPreconditionCondition

__all__ = [
    "EvidenceReadability",
    "EvidenceReadabilityState",
    "EvidenceUnreadableCause",
    "readable_finding",
    "unreadable_finding",
]

EvidenceReadabilityState = Literal["readable", "unreadable", "unchecked"]
"""What a list shows for one record: checked readable, checked unreadable, or never checked."""


class EvidenceUnreadableCause(StrEnum):
    """Why a check found a record's bytes unreadable, in the read path's refusal vocabulary."""

    BYTES_UNRECOGNIZED = LedgerPreconditionCondition.EVIDENCE_BYTES_READABLE.value
    """The stored bytes match no readable document shape."""

    BYTES_UNAVAILABLE = LedgerPreconditionCondition.EVIDENCE_DOCUMENT_BYTES_AVAILABLE.value
    """Secure custody holds no bytes under the record's attachment id."""


class EvidenceReadability(BaseModel):
    """One completed check of the bytes an evidence record names.

    ``checked_sha256`` is the content address that was asked for, so a finding
    can never be read as describing other bytes than the record's own.
    """

    model_config = STRICT_FROZEN_CONFIG

    state: Literal["readable", "unreadable"]
    document_shape: DocumentShape | None = None
    unreadable_cause: EvidenceUnreadableCause | None = None
    checked_sha256: ContentDigest
    checked_at: UtcInstant

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _state_carries_its_own_facts(self) -> Self:
        if self.state == "readable":
            if self.document_shape is None or self.document_shape is DocumentShape.UNKNOWN:
                raise ValueError("a readable finding names the recognised document shape")
            if self.unreadable_cause is not None:
                raise ValueError("a readable finding carries no unreadable cause")
        elif self.document_shape is not None or self.unreadable_cause is None:
            raise ValueError("an unreadable finding names its cause and no document shape")
        return self


def readable_finding(
    *, shape: DocumentShape, checked_sha256: ContentDigest, checked_at: datetime
) -> EvidenceReadability:
    """Return the finding for bytes the probe recognised as ``shape``."""
    return EvidenceReadability(
        state="readable",
        document_shape=shape,
        checked_sha256=checked_sha256,
        checked_at=checked_at,
    )


def unreadable_finding(
    *,
    cause: EvidenceUnreadableCause,
    checked_sha256: ContentDigest,
    checked_at: datetime,
) -> EvidenceReadability:
    """Return the finding for bytes no reader can read, or that custody does not hold."""
    return EvidenceReadability(
        state="unreadable",
        unreadable_cause=cause,
        checked_sha256=checked_sha256,
        checked_at=checked_at,
    )
