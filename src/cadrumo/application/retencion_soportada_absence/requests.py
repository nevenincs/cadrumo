"""Exact-profile request schemas for the suffered-withholding absence attestations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.renta.retencion_soportada_absence import ABSENCE_ATTESTATION_NOTE_MAX_LENGTH

__all__ = [
    "RetencionSoportadaAbsenceAttestRequest",
    "RetencionSoportadaAbsenceListRequest",
    "RetencionSoportadaAbsenceProfileRequest",
    "RetencionSoportadaAbsenceRequest",
    "RetencionSoportadaAbsenceWithdrawRequest",
]

type _Revision = Annotated[str, Field(min_length=1, max_length=128)]


class RetencionSoportadaAbsenceProfileRequest(BaseModel):
    """The exact profile and ejercicio an attestation operation addresses."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    ejercicio: FilingYear


class RetencionSoportadaAbsenceListRequest(RetencionSoportadaAbsenceProfileRequest):
    """Read every stored attestation of one ejercicio, active or withdrawn."""


class RetencionSoportadaAbsenceRequest(RetencionSoportadaAbsenceProfileRequest):
    """The exact profile, ejercicio and income class an attestation write addresses."""

    income_class: RetencionSoportadaClase


class RetencionSoportadaAbsenceAttestRequest(RetencionSoportadaAbsenceRequest):
    """Attest that no payer withheld on the class in the ejercicio.

    ``expected_revision_id`` is absent for a first attestation and the revision
    a withdrawn attestation was left at when one is replaced.
    """

    note: Annotated[str, Field(min_length=1, max_length=ABSENCE_ATTESTATION_NOTE_MAX_LENGTH)]
    expected_revision_id: _Revision | None = None


class RetencionSoportadaAbsenceWithdrawRequest(RetencionSoportadaAbsenceRequest):
    """Withdraw the active attestation, guarded by the revision the attestation was stored at."""

    expected_revision_id: _Revision
