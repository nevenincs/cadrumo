"""Strict pydantic v2 wire payload schemas for the sync runner.

Every schema is frozen + strict + ``extra="forbid"``. These are the
only shapes that cross the boundary from the live AEAT browser session
into the sync pipeline. If a fetch cannot be coerced into one of these
shapes, the runner raises :class:`WireValidationError`.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from ...core.i18n import Translatable
from ._protocols import ModeloIdentifier, PortalIdentifier


class WirePayloadBase(BaseModel):
    """Base for every wire payload. Strict, frozen, no extras."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class WireCasilla(WirePayloadBase):
    """A single casilla (form cell) as it appears live on AEAT."""

    id: str = Field(min_length=1, max_length=32)
    label: Translatable
    type_: str = Field(min_length=1, max_length=64, alias="type")
    default: str | None = None
    formula: str | None = None

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )


class WireModeloDefinition(WirePayloadBase):
    """A live modelo definition: identifier, vigencia range, casillas."""

    modelo: ModeloIdentifier
    vigencia_start: date
    vigencia_end: date
    casillas: tuple[WireCasilla, ...]


class WireFilingEntry(WirePayloadBase):
    """A single filing history row."""

    modelo: ModeloIdentifier
    period: str = Field(min_length=1, max_length=16)
    submitted_at: datetime
    status: str = Field(min_length=1, max_length=32)


class WireFilingHistory(WirePayloadBase):
    """A sequence of filing history rows."""

    entries: tuple[WireFilingEntry, ...]


class WirePortalLink(WirePayloadBase):
    """A single entry in the live portal manifest."""

    url: AnyHttpUrl
    label: Translatable
    modelo: ModeloIdentifier | None = None


class WirePortalManifest(WirePayloadBase):
    """The live portal link manifest."""

    portal: PortalIdentifier
    links: tuple[WirePortalLink, ...]
