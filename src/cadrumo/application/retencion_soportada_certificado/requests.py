"""Exact-profile request schemas for the suffered-withholding certificate operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen
from ..operations.public_scalar import PublicDecimal

type _Revision = Annotated[str, Field(min_length=1, max_length=128)]


class RetencionSoportadaProfileRequest(BaseModel):
    """Common private exact-profile binding for the certificate operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class RetencionSoportadaListRequest(RetencionSoportadaProfileRequest):
    """Read every stored payer record of one ejercicio."""

    ejercicio: FilingYear


class RetencionSoportadaRecordRequest(RetencionSoportadaProfileRequest):
    """Add or replace one payer's certificate figures for an ejercicio and income class.

    ``payer_tax_id`` is a sensitive input: the model never echoes it in a
    validation error. ``expected_revision_id`` is absent for a first record and
    the revision a prior list showed for a replacement.
    """

    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    payer_tax_id: Annotated[str, Field(min_length=1, max_length=32)]
    payer_legal_name: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    importe_integro_dinerario: PublicDecimal
    valoracion_especie: PublicDecimal
    retencion: PublicDecimal
    ingreso_a_cuenta: PublicDecimal
    ingreso_a_cuenta_repercutido: PublicDecimal
    origin: RetencionSoportadaOrigen
    evidence_fingerprint: ContentDigest | None = None
    expected_revision_id: _Revision | None = None


class RetencionSoportadaRemoveRequest(RetencionSoportadaProfileRequest):
    """Remove the record stored under ``(ejercicio, income_class, payer_ref)``."""

    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    payer_ref: Hex64Str
    expected_revision_id: _Revision
