"""Non-tax register records: an element's descriptor and the ordered event log.

Neither takes part in revision or claim identity, so nothing written here can
change a schedule fingerprint or make a calculation stale.  The descriptor holds
what a libro registro de bienes de inversion needs beyond the tax facts (Orden
HAC/773/2019 art. 4.3 letters a, c and d); the other letters are derived from the
revision and its claims.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from functools import cached_property
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from .identity_cache import CachedIdentityModel


class AcquisitionDocumentKind(StrEnum):
    """The document art. 4.3.a accepts: an invoice, a customs document or else a reception number."""

    INVOICE = "invoice"
    CUSTOMS_DOCUMENT = "customs_document"
    RECEPTION = "reception"


class ActivityAssetDescriptorFacts(BaseModel):
    """What an operator states about an element, none of it a tax fact."""

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1, max_length=256)
    serial_number: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, min_length=1, max_length=2048)
    document_kind: AcquisitionDocumentKind | None = None
    document_number: str | None = Field(default=None, min_length=1, max_length=128)
    supplier_name: str | None = Field(default=None, min_length=1, max_length=256)
    supplier_tax_id: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("name")
    @classmethod
    def _require_visible_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("an element's name must not be blank")
        return normalized

    @model_validator(mode="after")
    def _document_kind_names_a_number(self) -> Self:
        if (self.document_kind is None) != (self.document_number is None):
            raise ValueError("a document number and its kind are stated together")
        return self


class ActivityAssetDescriptor(CachedIdentityModel):
    """One appended statement of an element's descriptive facts; the latest is current."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    descriptor_number: int = Field(ge=1)
    facts: ActivityAssetDescriptorFacts

    @cached_property
    def descriptor_id(self) -> str:
        """Return the identity of this statement, distinct even when an earlier wording returns."""
        return content_hash_hex(self.model_dump(mode="json"))


class ActivityAssetEventKind(StrEnum):
    """The kinds of record the register's history orders."""

    REVISION = "revision"
    BAJA = "baja"
    CLAIM = "claim"
    DESCRIPTOR = "descriptor"


class ActivityAssetHistoryEvent(BaseModel):
    """Where one record sits in the history's order, kept outside that record's identity.

    ``recorded_at`` is null for a record written without a clock.  ``origin`` is
    the operation that wrote the record, or null when none was stated.
    """

    model_config = STRICT_FROZEN_CONFIG

    sequence: int = Field(ge=1)
    kind: ActivityAssetEventKind
    asset_id: str = Field(min_length=1, max_length=128)
    record_id: str = Field(min_length=1, max_length=128)
    recorded_at: datetime | None = None
    origin: str | None = Field(default=None, min_length=1, max_length=256)


__all__ = [
    "AcquisitionDocumentKind",
    "ActivityAssetDescriptor",
    "ActivityAssetDescriptorFacts",
    "ActivityAssetEventKind",
    "ActivityAssetHistoryEvent",
]
