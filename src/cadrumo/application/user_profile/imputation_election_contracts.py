"""Public contracts for reading and stating the RIRPF art. 7 election for one ejercicio.

The election is a dated profile fact, one statement per ejercicio, and absence
means undeclared. These contracts carry it with the setup wizard's own words, so
a surface shows and edits it without wording or deciding anything itself.
"""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import profile_operation_subject
from ..operations.models import CredentialFreeOperationRequest, OperationTerminalReceipt
from .field_help import ProfileFieldEjercicioStatement
from .question_view import ProfileQuestionChoice

PROFILE_IMPUTATION_ELECTION_READ_OPERATION_DEFINITION_ID = "user-profile.imputation-election.read"

PROFILE_IMPUTATION_ELECTION_SET_OPERATION_DEFINITION_ID = "user-profile.imputation-election.set"

PROFILE_IMPUTATION_ELECTION_READ_PHASES = (
    "user-profile.imputation-election.read.read",
    "user-profile.imputation-election.read.project",
)

PROFILE_IMPUTATION_ELECTION_SET_PHASES = (
    "user-profile.imputation-election.set.preflight",
    "user-profile.imputation-election.set.execute",
    "user-profile.imputation-election.set.settlement",
)

_EJERCICIO_FLOOR = 1
_EJERCICIO_CEILING = 9999

type ProfileImputationStatementState = Literal["declared", "undeclared", "contradictory"]
"""What the profile states for one ejercicio: one value, nothing, or more than one value."""


class ProfileImputationElectionReadRequest(CredentialFreeOperationRequest):
    """Read what the active profile states about the election for one ejercicio."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    tax_year: int = Field(ge=_EJERCICIO_FLOOR, le=_EJERCICIO_CEILING)
    output_language: OutputLanguage = OutputLanguage.ES


class ProfileImputationElectionSetRequest(BaseModel):
    """State or clear one ejercicio's election at an exact profile revision.

    Each answer is the token a served choice carries. ``None`` leaves what the
    profile states for that question; an empty token clears this ejercicio only.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    expected_revision: int = Field(ge=1)
    expected_content_digest: ContentDigest
    tax_year: int = Field(ge=_EJERCICIO_FLOOR, le=_EJERCICIO_CEILING)
    criterion: str | None = Field(default=None, max_length=64)
    codigo_comercio_accounting: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_an_answer(self) -> Self:
        if self.criterion is None and self.codigo_comercio_accounting is None:
            raise ValueError("an imputation election change must state or clear at least one answer")
        return self


class ProfileImputationElectionQuestion(BaseModel):
    """One setup question in the words the setup wizard asks it."""

    model_config = STRICT_FROZEN_CONFIG

    question_id: str
    path: str | None
    prompt: str
    help: str | None
    choices: tuple[ProfileQuestionChoice, ...]


class ProfileImputationElectionAnswer(BaseModel):
    """What the profile states for one question in the requested ejercicio.

    ``value`` is the stated choice token only when ``state`` is ``declared``. An
    undeclared answer is never read as either choice.
    """

    model_config = STRICT_FROZEN_CONFIG

    state: ProfileImputationStatementState
    value: str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _value_only_when_declared(self) -> Self:
        if (self.state == "declared") != (self.value is not None):
            raise ValueError("an election answer carries a value exactly when it is declared")
        return self


class ProfileImputationElectionReadResult(BaseModel):
    """The election for one ejercicio, every ejercicio's stated criterion, and the wizard's words."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest
    tax_year: int = Field(ge=_EJERCICIO_FLOOR, le=_EJERCICIO_CEILING)
    criterion: ProfileImputationElectionAnswer
    codigo_comercio_accounting: ProfileImputationElectionAnswer
    criterion_statements: tuple[ProfileFieldEjercicioStatement, ...]
    """The criterion each ejercicio states, in ejercicio order, so the three-year run is visible."""
    criterion_question: ProfileImputationElectionQuestion
    year_question: ProfileImputationElectionQuestion
    accounting_question: ProfileImputationElectionQuestion
    accounting_asked_for_criteria: tuple[str, ...]
    """The criterion tokens under which the setup wizard asks the accounting question."""
    words_language: OutputLanguage


class ProfileImputationElectionReadProjection(ProfileImputationElectionReadResult):
    """The registered read result, released only after PROFILE_VALUES disclosure."""


class ProfileImputationElectionSetResult(BaseModel):
    """Encrypted revision witness for one ejercicio's election change."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest
    tax_year: int = Field(ge=_EJERCICIO_FLOOR, le=_EJERCICIO_CEILING)
    changed: bool


class ProfileImputationElectionSetProjection(BaseModel):
    """Public settled ejercicio and revision, without the private content fingerprint."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    record_revision: int = Field(ge=1)
    tax_year: int = Field(ge=_EJERCICIO_FLOOR, le=_EJERCICIO_CEILING)
    changed: bool


def _require_settled_subject(profile_id: UUID, receipt: OperationTerminalReceipt, definition_id: str) -> None:
    if receipt.identity.definition_id != definition_id or receipt.identity.subject_ref != profile_operation_subject(
        str(profile_id)
    ):
        raise ValueError("imputation election result does not match its settled subject")


def project_imputation_election_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the read only for its exact settled profile subject."""
    if not isinstance(result, ProfileImputationElectionReadResult):
        raise TypeError("unexpected imputation election read result")
    _require_settled_subject(result.profile_id, receipt, PROFILE_IMPUTATION_ELECTION_READ_OPERATION_DEFINITION_ID)
    return ProfileImputationElectionReadProjection.model_validate(result.model_dump(mode="python"))


def project_imputation_election_set_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the change witness only for its exact settled profile subject."""
    if not isinstance(result, ProfileImputationElectionSetResult):
        raise TypeError("unexpected imputation election change result")
    _require_settled_subject(result.profile_id, receipt, PROFILE_IMPUTATION_ELECTION_SET_OPERATION_DEFINITION_ID)
    return ProfileImputationElectionSetProjection(
        profile_id=result.profile_id,
        record_revision=result.record_revision,
        tax_year=result.tax_year,
        changed=result.changed,
    )


__all__ = [
    "PROFILE_IMPUTATION_ELECTION_READ_OPERATION_DEFINITION_ID",
    "PROFILE_IMPUTATION_ELECTION_READ_PHASES",
    "PROFILE_IMPUTATION_ELECTION_SET_OPERATION_DEFINITION_ID",
    "PROFILE_IMPUTATION_ELECTION_SET_PHASES",
    "ProfileImputationElectionAnswer",
    "ProfileImputationElectionQuestion",
    "ProfileImputationElectionReadProjection",
    "ProfileImputationElectionReadRequest",
    "ProfileImputationElectionReadResult",
    "ProfileImputationElectionSetProjection",
    "ProfileImputationElectionSetRequest",
    "ProfileImputationElectionSetResult",
    "ProfileImputationStatementState",
    "project_imputation_election_read_result",
    "project_imputation_election_set_result",
]
