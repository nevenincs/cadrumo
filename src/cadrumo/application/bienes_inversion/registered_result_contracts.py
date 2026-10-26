"""Closed public result schemas for capital-goods register operations."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.bienes_inversion.register import BienInversionIvaRecord
from ..operations.public_scalar import PublicDecimal
from .registered_contracts import BienesInversionRefusalReason


class BienInversionDisposalProjection(BaseModel):
    """Complete public disposal facts retained on the canonical record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    year: int
    regime: Annotated[str, Field(min_length=1, max_length=96)]


class BienInversionRecordProjection(BaseModel):
    """Untruncated CLI record projection, including its derived acquisition deduction."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    identifier: str
    description: str
    acquisition_year: int
    cuota_soportada: PublicDecimal
    prorrata_inicial_pct: PublicDecimal
    kind: Annotated[str, Field(min_length=1, max_length=96)]
    art108_elegible: bool
    acquisition_ledger_id: str
    prorrata_sector_id: str | None
    disposal: BienInversionDisposalProjection | None
    deduccion_efectuada: PublicDecimal
    schema_version: str

    @classmethod
    def from_record(cls, record: BienInversionIvaRecord) -> BienInversionRecordProjection:
        """Project every operator-visible register field without dropping identity."""
        disposal = record.disposal
        return cls(
            identifier=record.identifier,
            description=record.description,
            acquisition_year=record.acquisition_year,
            cuota_soportada=PublicDecimal(decimal=str(record.cuota_soportada)),
            prorrata_inicial_pct=PublicDecimal(decimal=str(record.prorrata_inicial_pct)),
            kind=record.kind.value,
            art108_elegible=record.art108_elegible,
            acquisition_ledger_id=record.acquisition_ledger_id,
            prorrata_sector_id=record.prorrata_sector_id,
            disposal=(
                BienInversionDisposalProjection(year=disposal.year, regime=disposal.regime.value)
                if disposal is not None
                else None
            ),
            deduccion_efectuada=PublicDecimal(decimal=str(record.deduccion_efectuada)),
            schema_version=record.schema_version,
        )


class BienesInversionRefusalProjection(BaseModel):
    """Safe, closed refusal context for a known pre-write declaration refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["REFUSED_PROFILE_BIENES_INVERSION_VALIDATION",]
    reason: BienesInversionRefusalReason
    missing: Literal["year", "regime"] | None = None
    identifier: str | None = None


class BienesInversionListProjection(BaseModel):
    """Complete result of reading the profile's capital-goods register."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: tuple[BienInversionRecordProjection, ...]


class BienesInversionDeclareProjection(BaseModel):
    """Successful declaration projection or its registered typed refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["declared", "refused"]
    profile_id: UUID
    record: BienInversionRecordProjection | None = None
    count: int | None = None
    refusal: BienesInversionRefusalProjection | None = None

    @model_validator(mode="after")
    def _projection_arm_is_closed(self) -> BienesInversionDeclareProjection:
        if self.outcome == "refused":
            if self.record is not None or self.count is not None or self.refusal is None:
                raise ValueError("capital-goods refusal projection has an incompatible payload")
        elif self.record is None or self.count is None or self.refusal is not None:
            raise ValueError("capital-goods declaration projection is incomplete")
        return self
