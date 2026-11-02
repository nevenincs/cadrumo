"""The operator's attestation that no payer withheld on one income class in one ejercicio.

Where the taxpayer had income of a class but no payer practised withholding or
made an ingreso a cuenta on it, there is no certificate to record. The credit
casillas of that class would otherwise stay unresolved, because a missing payer
record is never read as zero. This record is the operator's explicit,
attributable statement of that absence.

It is an operator assertion and nothing more. It is never a payer's statement,
never counted as a certificate and never filing evidence of what a payer
reported; a calculation that rests a zero on it names it as operator input.

The attestation lives in the suffered-withholding namespace under
``absence:{ejercicio}:{income_class}``, one row per class and ejercicio. A
withdrawal is a revision-guarded state change, so the row keeps when the
assertion was made and when it was taken back.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.retencion_soportada import RetencionSoportadaClase
from ...core.time.utc import UtcInstant
from .errors import RentaValidationError

__all__ = [
    "RETENCION_SOPORTADA_ABSENCE_KIND",
    "RETENCION_SOPORTADA_ABSENCE_NOTE_MAX_LENGTH",
    "RetencionSoportadaAbsence",
    "RetencionSoportadaAbsenceIdentity",
    "RetencionSoportadaAbsenceState",
]

RETENCION_SOPORTADA_ABSENCE_KIND: Final = "absence_attestation"
"""The payload marker that tells an attestation row from a payer record in the shared namespace."""

RETENCION_SOPORTADA_ABSENCE_NOTE_MAX_LENGTH: Final[int] = 500
"""The longest operator note an attestation keeps."""

type RetencionSoportadaAbsenceIdentity = tuple[int, RetencionSoportadaClase]
"""The ``(ejercicio, income class)`` an attestation is stored under."""


class RetencionSoportadaAbsenceState(StrEnum):
    """Whether an attestation currently asserts the absence."""

    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class RetencionSoportadaAbsence(BaseModel):
    """The operator's statement that no payer withheld on one class in one ejercicio (payload schema v1)."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["absence_attestation"] = RETENCION_SOPORTADA_ABSENCE_KIND
    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    note: Annotated[str, Field(min_length=1, max_length=RETENCION_SOPORTADA_ABSENCE_NOTE_MAX_LENGTH)]
    """Why the operator asserts the absence; required, because the assertion must be answerable."""
    attested_at: UtcInstant
    state: RetencionSoportadaAbsenceState = RetencionSoportadaAbsenceState.ACTIVE
    withdrawn_at: UtcInstant | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        if not self.note.strip():
            raise RentaValidationError("an absence attestation needs a non-blank operator note")
        withdrawn = self.state is RetencionSoportadaAbsenceState.WITHDRAWN
        if withdrawn != (self.withdrawn_at is not None):
            raise RentaValidationError("an absence attestation carries a withdrawal instant exactly when withdrawn")
        if self.withdrawn_at is not None and self.withdrawn_at < self.attested_at:
            raise RentaValidationError("an absence attestation cannot be withdrawn before it was made")
        return self

    @property
    def identity(self) -> RetencionSoportadaAbsenceIdentity:
        """Return the identity this attestation is stored under."""
        return (self.ejercicio, self.income_class)

    @property
    def active(self) -> bool:
        """Return whether the attestation currently asserts the absence."""
        return self.state is RetencionSoportadaAbsenceState.ACTIVE

    def withdrawn(self, at: UtcInstant) -> RetencionSoportadaAbsence:
        """Return this attestation taken back at ``at``."""
        return self.model_copy(update={"state": RetencionSoportadaAbsenceState.WITHDRAWN, "withdrawn_at": at})
