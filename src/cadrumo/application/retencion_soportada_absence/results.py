"""Closed result schemas for the suffered-withholding absence attestations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.retencion_soportada import RetencionSoportadaClase
from ...core.time.utc import UtcInstant
from ...domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence, RetencionSoportadaAbsenceState
from .contracts import RetencionSoportadaAbsenceOperationId, RetencionSoportadaAbsenceOperationRefusalReason

__all__ = [
    "RetencionSoportadaAbsenceExecutionResult",
    "RetencionSoportadaAbsenceMutationProjection",
    "RetencionSoportadaAbsenceProjection",
    "RetencionSoportadaAbsenceRefusalProjection",
]


class RetencionSoportadaAbsenceProjection(BaseModel):
    """One stored attestation as the operator sees it, beside the revision it is stored at."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    note: str
    state: RetencionSoportadaAbsenceState
    attested_at: UtcInstant
    withdrawn_at: UtcInstant | None
    revision_id: str

    @classmethod
    def from_attestation(
        cls, attestation: RetencionSoportadaAbsence, *, revision_id: str
    ) -> RetencionSoportadaAbsenceProjection:
        """Project every operator-visible field of ``attestation``."""
        return cls(
            ejercicio=attestation.ejercicio,
            income_class=attestation.income_class,
            note=attestation.note,
            state=attestation.state,
            attested_at=attestation.attested_at,
            withdrawn_at=attestation.withdrawn_at,
            revision_id=revision_id,
        )


class RetencionSoportadaAbsenceRefusalProjection(BaseModel):
    """Safe, closed context of a refusal made before anything was stored."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["REFUSED_RETENCION_SOPORTADA_ABSENCE", "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"]
    reason: RetencionSoportadaAbsenceOperationRefusalReason
    ejercicio: FilingYear
    income_class: RetencionSoportadaClase


class RetencionSoportadaAbsenceMutationProjection(BaseModel):
    """An attested or withdrawn attestation, or the typed refusal that stored nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["attested", "withdrawn", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    attestation: RetencionSoportadaAbsenceProjection | None = None
    refusal: RetencionSoportadaAbsenceRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> RetencionSoportadaAbsenceMutationProjection:
        if (self.outcome == "refused") != (self.refusal is not None) or (self.refusal is None) == (
            self.attestation is None
        ):
            raise ValueError("suffered-withholding absence projection has an incompatible payload")
        return self


class RetencionSoportadaAbsenceExecutionResult(BaseModel):
    """Private result held in operation operand custody until projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: RetencionSoportadaAbsenceOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    attestation: RetencionSoportadaAbsenceProjection | None = None
    refusal: RetencionSoportadaAbsenceRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> RetencionSoportadaAbsenceExecutionResult:
        if (self.outcome == "refused") != (self.refusal is not None) or (self.refusal is None) == (
            self.attestation is None
        ):
            raise ValueError("suffered-withholding absence execution result has an incompatible payload")
        return self
