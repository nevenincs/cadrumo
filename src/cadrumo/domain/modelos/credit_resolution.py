"""The operator's acceptance of one disputed figure, kept apart from the calculation it answers.

Two sources of one figure can state different values: a credit casilla and the
payer records or the borrador it is cross-checked with, or a precedence tier that
replaced a different lower-tier value. The calculation states the disagreement
as a :class:`~.source_disagreement.SourceDisagreementFact` and withholds
checking, export and local filing. This record is the operator's explicit,
attributable statement that the value the calculation used stands.

A resolution accepts and never selects. ``accepted_role`` is always the role the
calculation selected, so a resolution cannot change a figure; it only lifts the
hold on that exact figure. It is keyed by the disagreement's own finding key,
which digests every source's value, the registry revision and the declaration
that was compared. Any changed amount, an added or removed source, a different
registry revision or a changed declaration is a different finding that no
earlier resolution covers.

The record restates the amounts it answers, so it holds financial data and lives
in the profile's encrypted storage. Its reason is the operator's own words and
is never logged.

A revocation is a state change of the same row, so the row keeps when the
acceptance was made and when it was taken back.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import NoRecoveryOutcome
from ...core.time.utc import UtcInstant
from .errors import ModeloValidatedRecord, ModeloValidationError
from .source_disagreement import SourceDisagreementFact, SourceDisagreementRole

__all__ = [
    "CREDIT_RESOLUTION_REASON_MAX_LENGTH",
    "CREDIT_RESOLUTION_SESSION_MAX_LENGTH",
    "CreditResolutionIdentity",
    "CreditResolutionRecord",
    "CreditResolutionState",
]

CREDIT_RESOLUTION_REASON_MAX_LENGTH: Final[int] = 512
"""The longest reason an operator can give for accepting a disputed figure."""

CREDIT_RESOLUTION_SESSION_MAX_LENGTH: Final[int] = 128
"""The longest session label a resolution records for its author."""

type CreditResolutionIdentity = tuple[str, FilingYear, str, str]
"""The ``(modelo, filing year, period, finding key)`` a resolution is stored under."""


class CreditResolutionState(StrEnum):
    """Whether a resolution currently lifts the hold on its figure."""

    ACTIVE = "active"
    REVOKED = "revoked"


class CreditResolutionRecord(BaseModel):
    """The operator's acceptance of one source disagreement (payload schema v1)."""

    model_config = STRICT_FROZEN_CONFIG

    disagreement: SourceDisagreementFact
    """The full finding this resolution answers, as the calculation stated it."""
    accepted_role: SourceDisagreementRole
    """The role whose value is accepted; always the role the calculation selected."""
    reason: Annotated[str, Field(min_length=1, max_length=CREDIT_RESOLUTION_REASON_MAX_LENGTH)]
    """Why the operator accepts the figure; required, because the acceptance must be answerable."""
    resolved_at: UtcInstant
    resolved_by_session: Annotated[str, Field(min_length=1, max_length=CREDIT_RESOLUTION_SESSION_MAX_LENGTH)]
    state: CreditResolutionState = CreditResolutionState.ACTIVE
    revoked_at: UtcInstant | None = None
    revoked_by_session: Annotated[str, Field(min_length=1, max_length=CREDIT_RESOLUTION_SESSION_MAX_LENGTH)] | None = (
        None
    )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        if self.accepted_role is not self.disagreement.selected_role:
            raise ModeloValidationError(
                "a resolution accepts the role the calculation selected and no other",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CREDIT_RESOLUTION,
            )
        if not self.reason.strip():
            raise ModeloValidationError(
                "a resolution needs a non-blank operator reason",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CREDIT_RESOLUTION,
            )
        revoked = self.state is CreditResolutionState.REVOKED
        if revoked != (self.revoked_at is not None) or revoked != (self.revoked_by_session is not None):
            raise ModeloValidationError(
                "a resolution carries its revocation exactly when it is revoked",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CREDIT_RESOLUTION,
            )
        if self.revoked_at is not None and self.revoked_at < self.resolved_at:
            raise ModeloValidationError(
                "a resolution cannot be revoked before it was made",
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                record=ModeloValidatedRecord.CREDIT_RESOLUTION,
            )
        return self

    @property
    def finding_key(self) -> str:
        """Return the digest of the disagreement this resolution answers."""
        return self.disagreement.finding_key

    @property
    def identity(self) -> CreditResolutionIdentity:
        """Return the identity this resolution is stored under."""
        fact = self.disagreement
        return (fact.modelo, fact.filing_year, fact.period, fact.finding_key)

    @property
    def active(self) -> bool:
        """Return whether the resolution currently lifts the hold on its figure."""
        return self.state is CreditResolutionState.ACTIVE

    def revoked(self, at: UtcInstant, *, by_session: str) -> Self:
        """Return this resolution taken back at ``at`` by ``by_session``."""
        return self.model_copy(
            update={"state": CreditResolutionState.REVOKED, "revoked_at": at, "revoked_by_session": by_session}
        )
