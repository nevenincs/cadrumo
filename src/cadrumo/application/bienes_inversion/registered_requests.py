"""Exact-profile request schemas for the capital-goods IVA register."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.public_scalar import PublicDecimal


class BienesInversionProfileRequest(BaseModel):
    """Common private exact-profile binding for register operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class BienesInversionListRequest(BienesInversionProfileRequest):
    """Read the complete capital-goods register for one immutable profile."""


class BienesInversionDeclareRequest(BienesInversionProfileRequest):
    """Declare one capital good using the existing operator-owned facts."""

    identifier: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acquisition_year: int = Field(ge=1, le=2099)
    acquisition_ledger_id: str = Field(min_length=1, max_length=128)
    cuota_soportada: PublicDecimal
    prorrata_inicial_pct: PublicDecimal
    kind: str = Field(min_length=1)
    art108_elegible: bool = True
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    disposal_year: int | None = Field(default=None, ge=1, le=2099)
    disposal_regime: str | None = Field(default=None, min_length=1)
