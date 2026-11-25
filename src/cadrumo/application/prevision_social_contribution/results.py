"""Closed result schemas for the pension contribution certificate operations.

No schema here carries a tax identifier: a record is named by its keyed
``issuer_ref`` and ``plan_ref``, the issuer's legal name and the plan's name.
"""

from __future__ import annotations

from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialClave, PrevisionSocialSubclave
from ...domain.renta.prevision_social_contribution import PrevisionSocialContribution
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH
from ..operations.public_scalar import PublicDecimal
from .contracts import PrevisionSocialOperationId, PrevisionSocialRefusalReason


class PrevisionSocialRowProjection(BaseModel):
    """One stored contribution record as the operator sees it, without any tax identifier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: FilingYear
    issuer_ref: Hex64Str
    issuer_legal_name: str | None
    plan_ref: Hex64Str | None
    plan_name: str | None
    clave: PrevisionSocialClave
    subclave: PrevisionSocialSubclave | None
    amount: PublicDecimal
    beneficiary: PrevisionSocialBeneficiario
    employer_contributed_to_same_plan: bool | None
    #: The Modelo 100 box the pinned edition of the record's ejercicio places it in, or ``None`` when it places
    #: it in none; the box is the registry's answer, served so a frontend never works it out.
    casilla_id: CasillaId | None
    evidence_fingerprint: Hex64Str
    replaces_evidence_fingerprint: Hex64Str | None
    revision_id: str

    @classmethod
    def from_record(
        cls, record: PrevisionSocialContribution, *, revision_id: str, casilla_id: CasillaId | None
    ) -> PrevisionSocialRowProjection:
        """Project every operator-visible field of ``record``."""
        return cls(
            ejercicio=record.ejercicio,
            issuer_ref=record.issuer_ref,
            issuer_legal_name=record.issuer_legal_name,
            plan_ref=record.plan_ref,
            plan_name=record.plan_name,
            clave=record.clave,
            subclave=record.subclave,
            amount=PublicDecimal(decimal=str(record.amount)),
            beneficiary=record.beneficiary,
            employer_contributed_to_same_plan=record.employer_contributed_to_same_plan,
            casilla_id=casilla_id,
            evidence_fingerprint=record.evidence_fingerprint,
            replaces_evidence_fingerprint=record.replaces_evidence_fingerprint,
            revision_id=revision_id,
        )


class PrevisionSocialRefusalProjection(BaseModel):
    """Safe, closed context of a refusal made before anything was stored."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal[
        "REFUSED_PREVISION_SOCIAL_CONTRIBUTION_WRITE", "REFUSED_PREVISION_SOCIAL_CONTRIBUTION_REVISION_CONFLICT"
    ]
    reason: PrevisionSocialRefusalReason
    ejercicio: FilingYear
    #: The finished sentence a frontend shows for the refusal, with its way out, and the language it is in.
    refusal_words: str = Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    refusal_words_language: OutputLanguage


class PrevisionSocialListProjection(BaseModel):
    """Every stored contribution record of one ejercicio."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    ejercicio: FilingYear
    rows: tuple[PrevisionSocialRowProjection, ...]
    #: Every ejercicio the pinned authority supports, oldest first, so a frontend holds no year list.
    ejercicios: tuple[FilingYear, ...]


class PrevisionSocialMutationProjection(BaseModel):
    """A recorded or removed contribution record, or the typed refusal that stored nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["recorded", "removed", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    row: PrevisionSocialRowProjection | None = None
    count: int | None = None
    refusal: PrevisionSocialRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> PrevisionSocialMutationProjection:
        if self.outcome == "refused":
            closed = self.row is None and self.count is None and self.refusal is not None
        else:
            closed = (
                self.refusal is None
                and self.count is not None
                and (self.outcome == "recorded") == (self.row is not None)
            )
        if not closed:
            raise ValueError("pension contribution mutation projection has an incompatible payload")
        return self


_SUCCESS_ARMS: Final[dict[PrevisionSocialOperationId, tuple[bool, bool, bool, bool]]] = {
    "list": (True, True, False, False),
    "record": (False, False, True, True),
    "remove": (False, False, False, True),
}
"""Which of rows, ejercicios, row and count a successful result of each operation states."""


class PrevisionSocialOperationExecutionResult(BaseModel):
    """Private result held in operation operand custody until projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: PrevisionSocialOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    rows: tuple[PrevisionSocialRowProjection, ...] | None = None
    ejercicios: tuple[FilingYear, ...] | None = None
    row: PrevisionSocialRowProjection | None = None
    count: int | None = None
    refusal: PrevisionSocialRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> PrevisionSocialOperationExecutionResult:
        stated = (self.rows is not None, self.ejercicios is not None, self.row is not None, self.count is not None)
        if self.outcome == "refused":
            closed = self.operation_id != "list" and not any(stated) and self.refusal is not None
        else:
            closed = self.refusal is None and stated == _SUCCESS_ARMS[self.operation_id]
        if not closed:
            raise ValueError("pension contribution execution result has an incompatible payload")
        return self


__all__ = [
    "PrevisionSocialListProjection",
    "PrevisionSocialMutationProjection",
    "PrevisionSocialOperationExecutionResult",
    "PrevisionSocialRefusalProjection",
    "PrevisionSocialRowProjection",
]
