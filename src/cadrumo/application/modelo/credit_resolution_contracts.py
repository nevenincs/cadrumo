"""Operation identifiers, requests and closed result schemas for the operator's resolutions of disputed figures.

The operator accepts a source disagreement by the finding id the refusal or the
form showed, takes an acceptance back, or lists the acceptances a declaration
holds. A request names the exact profile and the persisted calculation revision
whose findings it answers; a result restates the amounts it answers and the
operator's reason, so it is held only in encrypted operation custody.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.hex import Hex16Str
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.modelos.credit_resolution import (
    CREDIT_RESOLUTION_REASON_MAX_LENGTH,
    CreditResolutionRecord,
    CreditResolutionState,
)
from ...domain.modelos.source_disagreement import SourceDisagreementRole
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH
from .calculation_note_gate import SOURCE_DISAGREEMENT_FINDING_ID_LENGTH
from .credit_resolution_words import credit_resolution_answer_words
from .disagreement_words import disagreement_value_text

__all__ = [
    "MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID",
    "MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID",
    "MODELO_CREDIT_RESOLUTION_REFUSAL_CODE",
    "MODELO_CREDIT_RESOLUTION_REFUSAL_CODES",
    "MODELO_CREDIT_RESOLUTION_REVISION_REFUSAL_CODE",
    "MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID",
    "CreditResolutionAcceptRequest",
    "CreditResolutionExecutionResult",
    "CreditResolutionListProjection",
    "CreditResolutionListRequest",
    "CreditResolutionMutationProjection",
    "CreditResolutionOperationId",
    "CreditResolutionOperationRefusalReason",
    "CreditResolutionRefusalProjection",
    "CreditResolutionRequest",
    "CreditResolutionRevokeRequest",
    "CreditResolutionRowProjection",
    "CreditResolutionSourceProjection",
]

MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID: Final = "modelo.work.accept_disagreement"
MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID: Final = "modelo.work.revoke_disagreement"
MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID: Final = "modelo.work.disagreements"

MODELO_CREDIT_RESOLUTION_REFUSAL_CODE: Final = "REFUSED_CREDIT_RESOLUTION"
"""The registered code of every refusal except a stale revision."""

MODELO_CREDIT_RESOLUTION_REVISION_REFUSAL_CODE: Final = "REFUSED_CREDIT_RESOLUTION_REVISION_CONFLICT"
"""The registered code of a write prepared against a revision that moved."""

MODELO_CREDIT_RESOLUTION_REFUSAL_CODES: Final[frozenset[str]] = frozenset(
    {MODELO_CREDIT_RESOLUTION_REFUSAL_CODE, MODELO_CREDIT_RESOLUTION_REVISION_REFUSAL_CODE}
)

type CreditResolutionOperationId = Literal["accept", "revoke", "list"]

type CreditResolutionOperationRefusalReason = Literal[
    "already_resolved", "not_resolved", "unknown_finding", "calculation_not_current", "stale_revision"
]
"""Why an acceptance or its revocation was refused before any change was stored."""

type _Revision = Annotated[str, Field(min_length=1, max_length=128)]


class CreditResolutionRequest(BaseModel):
    """The exact profile and persisted calculation revision whose findings a request answers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId
    #: The language the resolution's sentence is said in.
    output_language: OutputLanguage


class CreditResolutionListRequest(CreditResolutionRequest):
    """Read every resolution the revision's declaration holds, active or revoked."""


class CreditResolutionAcceptRequest(CreditResolutionRequest):
    """Accept the value the calculation used for one disagreement of the revision, by its finding id.

    The acceptance is recorded under the label of the session that admitted the
    execution; no request field names who acted, because nothing would
    authenticate it.
    """

    finding_id: Hex16Str
    reason: Annotated[str, Field(min_length=1, max_length=CREDIT_RESOLUTION_REASON_MAX_LENGTH, pattern=r"\S")]


class CreditResolutionRevokeRequest(CreditResolutionRequest):
    """Take back the active resolution of one finding, guarded by the revision it is stored at."""

    finding_id: Hex16Str
    expected_revision_id: _Revision


class CreditResolutionSourceProjection(BaseModel):
    """One source of a disagreement and what it stated, as the operator sees it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: SourceDisagreementRole
    source_family: str
    value: str


class CreditResolutionRowProjection(BaseModel):
    """One stored resolution beside the revision it is stored at, with the sources it answers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    finding_id: Hex16Str
    key: str
    reached_casillas: tuple[CasillaId, ...]
    sources: tuple[CreditResolutionSourceProjection, ...]
    accepted_role: SourceDisagreementRole
    reason: str
    state: CreditResolutionState
    resolved_at: datetime
    resolved_by_session: str
    revoked_at: datetime | None
    revoked_by_session: str | None
    revision_id: str
    applies: bool
    """Whether the addressed calculation revision persisted this very disagreement."""
    answer_words: str = Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    """The sentence saying which figure the resolution answers, the amount accepted and what each source stated."""
    answer_words_language: OutputLanguage

    @field_validator("resolved_at", "revoked_at")
    @classmethod
    @pydantic_validation_boundary
    def _instants_are_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else validate_utc_aware(value)

    @classmethod
    def of(cls, record: CreditResolutionRecord, *, revision_id: str, applies: bool, language: OutputLanguage) -> Self:
        """Project every operator-visible field of ``record``."""
        fact = record.disagreement
        return cls(
            finding_id=record.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH],
            key=fact.key,
            reached_casillas=fact.reached_casillas,
            sources=tuple(
                CreditResolutionSourceProjection(
                    role=source.role, source_family=source.source_family, value=disagreement_value_text(source.value)
                )
                for source in fact.sources
            ),
            accepted_role=record.accepted_role,
            reason=record.reason,
            state=record.state,
            resolved_at=record.resolved_at,
            resolved_by_session=record.resolved_by_session,
            revoked_at=record.revoked_at,
            revoked_by_session=record.revoked_by_session,
            revision_id=revision_id,
            applies=applies,
            answer_words=credit_resolution_answer_words(record, language),
            answer_words_language=language,
        )


class CreditResolutionRefusalProjection(BaseModel):
    """Safe, closed context of a refusal made before anything was stored."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["REFUSED_CREDIT_RESOLUTION", "REFUSED_CREDIT_RESOLUTION_REVISION_CONFLICT"]
    reason: CreditResolutionOperationRefusalReason
    finding_id: Hex16Str
    #: The finished sentence a frontend shows for the refusal and the language it is in, worded by the
    #: operation error detail's rules from a key written for frontends.
    refusal_words: str | None = Field(default=None, min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    refusal_words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    def _words_name_their_language(self) -> CreditResolutionRefusalProjection:
        if (self.refusal_words is None) != (self.refusal_words_language is None):
            raise ValueError("served words name the language they are in")
        return self


class CreditResolutionListProjection(BaseModel):
    """Every resolution one declaration holds, active and revoked."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId
    resolutions: tuple[CreditResolutionRowProjection, ...]


class CreditResolutionMutationProjection(BaseModel):
    """An accepted or revoked resolution, or the typed refusal that stored nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["accepted", "revoked", "refused"]
    profile_id: UUID
    calculation_revision_id: CalculationRevisionId
    resolution: CreditResolutionRowProjection | None = None
    refusal: CreditResolutionRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> CreditResolutionMutationProjection:
        if (self.outcome == "refused") != (self.refusal is not None) or (self.refusal is None) == (
            self.resolution is None
        ):
            raise ValueError("credit resolution projection has an incompatible payload")
        return self


class CreditResolutionExecutionResult(BaseModel):
    """Private result held in operation operand custody until projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: CreditResolutionOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    work_unit_id: str = Field(min_length=1, max_length=256)
    calculation_revision_id: CalculationRevisionId
    resolution: CreditResolutionRowProjection | None = None
    resolutions: tuple[CreditResolutionRowProjection, ...] | None = None
    refusal: CreditResolutionRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> CreditResolutionExecutionResult:
        if self.operation_id == "list":
            closed = (
                self.outcome == "success"
                and self.resolutions is not None
                and self.resolution is None
                and self.refusal is None
            )
        else:
            closed = (
                self.resolutions is None
                and (self.outcome == "refused") == (self.refusal is not None)
                and (self.refusal is None) != (self.resolution is None)
            )
        if not closed:
            raise ValueError("credit resolution execution result has an incompatible payload")
        return self
