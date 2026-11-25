"""Closed result schemas for the suffered-withholding absence attestations."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import InternalInvariantError, pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.retencion_soportada import RetencionSoportadaClase
from ...core.retencion_soportada_label import retencion_soportada_clase_label
from ...core.time.utc import validate_utc_aware
from ...domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence, RetencionSoportadaAbsenceState
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH
from .contracts import RetencionSoportadaAbsenceOperationId, RetencionSoportadaAbsenceOperationRefusalReason

__all__ = [
    "RetencionSoportadaAbsenceExecutionResult",
    "RetencionSoportadaAbsenceListProjection",
    "RetencionSoportadaAbsenceMutationProjection",
    "RetencionSoportadaAbsenceProjection",
    "RetencionSoportadaAbsenceRefusalProjection",
    "RetencionSoportadaAbsenceRowProjection",
]


class _AbsenceFields(BaseModel):
    """The operator-visible fields every projection of a stored attestation carries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    note: str
    state: RetencionSoportadaAbsenceState
    attested_at: datetime
    withdrawn_at: datetime | None
    revision_id: str

    @field_validator("attested_at", "withdrawn_at")
    @classmethod
    @pydantic_validation_boundary
    def _instants_are_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else validate_utc_aware(value)


class RetencionSoportadaAbsenceProjection(_AbsenceFields):
    """One stored attestation as the operator sees it, beside the revision it is stored at."""

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


_STATE_LOCALE_KEYS: Final[dict[RetencionSoportadaAbsenceState, str]] = {
    RetencionSoportadaAbsenceState.ACTIVE: "aggregation.retencion_soportada.absence_state.active",
    RetencionSoportadaAbsenceState.WITHDRAWN: "aggregation.retencion_soportada.absence_state.withdrawn",
}
"""A literal table so the locale audit sees each state's word reach the translator."""
if set(_STATE_LOCALE_KEYS) != set(RetencionSoportadaAbsenceState):
    raise InternalInvariantError("every absence attestation state needs its word")


class RetencionSoportadaAbsenceRowProjection(_AbsenceFields):
    """One listed attestation: the stored fields and locale-resolved labels of its income class and state."""

    income_class_label: str
    state_label: str

    @classmethod
    def from_attestation(
        cls, attestation: RetencionSoportadaAbsence, *, revision_id: str
    ) -> RetencionSoportadaAbsenceRowProjection:
        """Project every operator-visible field of ``attestation`` and label its income class."""
        return cls(
            ejercicio=attestation.ejercicio,
            income_class=attestation.income_class,
            note=attestation.note,
            state=attestation.state,
            attested_at=attestation.attested_at,
            withdrawn_at=attestation.withdrawn_at,
            revision_id=revision_id,
            income_class_label=retencion_soportada_clase_label(attestation.income_class),
            state_label=tr(_STATE_LOCALE_KEYS[attestation.state]),
        )


class RetencionSoportadaAbsenceListProjection(BaseModel):
    """Every stored attestation of one ejercicio, active and withdrawn."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    ejercicio: FilingYear
    attestations: tuple[RetencionSoportadaAbsenceRowProjection, ...]


class RetencionSoportadaAbsenceRefusalProjection(BaseModel):
    """Safe, closed context of a refusal made before anything was stored."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["REFUSED_RETENCION_SOPORTADA_ABSENCE", "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"]
    reason: RetencionSoportadaAbsenceOperationRefusalReason
    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    #: The finished sentence a frontend shows for the refusal and the language it is in, worded by the
    #: operation error detail's rules from a key written for frontends.
    refusal_words: str | None = Field(default=None, min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    refusal_words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    def _words_name_their_language(self) -> RetencionSoportadaAbsenceRefusalProjection:
        if (self.refusal_words is None) != (self.refusal_words_language is None):
            raise ValueError("served words name the language they are in")
        return self


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
    attestations: tuple[RetencionSoportadaAbsenceRowProjection, ...] | None = None
    refusal: RetencionSoportadaAbsenceRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> RetencionSoportadaAbsenceExecutionResult:
        if self.operation_id == "list":
            closed = (
                self.outcome == "success"
                and self.attestations is not None
                and self.attestation is None
                and self.refusal is None
            )
        else:
            closed = (
                self.attestations is None
                and (self.outcome == "refused") == (self.refusal is not None)
                and (self.refusal is None) != (self.attestation is None)
            )
        if not closed:
            raise ValueError("suffered-withholding absence execution result has an incompatible payload")
        return self
