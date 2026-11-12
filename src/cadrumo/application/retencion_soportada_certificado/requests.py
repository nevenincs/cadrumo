"""Exact-profile request schemas for the suffered-withholding certificate operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen
from ..operations.public_scalar import PublicDecimal

type _Revision = Annotated[str, Field(min_length=1, max_length=128)]
type _Path = Annotated[str, Field(min_length=1, max_length=4_096)]


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

    The certificate is named by ``source_path`` (resolved against
    ``source_directory``, the submitting frontend's directory), which the worker
    reads and keeps in encrypted attachment custody, or by ``evidence_fingerprint``
    alone for bytes custody already holds. Given with a file, the fingerprint is
    only an integrity cross-check against the bytes read.

    ``reducciones_aplicables`` and ``gastos_deducibles`` are the two figures a
    work-income certificate states beyond the payment: the operation refuses a
    ``trabajo`` request without them and a request of any other class with them.
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
    reducciones_aplicables: PublicDecimal | None = None
    gastos_deducibles: PublicDecimal | None = None
    origin: RetencionSoportadaOrigen
    evidence_fingerprint: ContentDigest | None = None
    source_path: _Path | None = None
    source_directory: _Path | None = None
    expected_revision_id: _Revision | None = None

    @model_validator(mode="after")
    def _file_is_resolved_against_a_directory(self) -> RetencionSoportadaRecordRequest:
        if (self.source_path is None) != (self.source_directory is None):
            raise ValueError("a certificate file is named by a path and the directory it is resolved against")
        return self


class RetencionSoportadaRemoveRequest(RetencionSoportadaProfileRequest):
    """Remove the record stored under ``(ejercicio, income_class, payer_ref)``."""

    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    payer_ref: Hex64Str
    expected_revision_id: _Revision
