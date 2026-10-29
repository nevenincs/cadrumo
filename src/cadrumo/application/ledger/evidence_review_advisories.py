"""Typed party and country advisory projections for evidence review."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.iva.establishment import StatedCountryCodeStatus
from .evidence_followup_types import EvidenceFollowupText


class PartyAttributionWarningProjection(BaseModel):
    """Public party warning with the canonical territory token as a string."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: EvidenceFollowupText
    fields: Annotated[tuple[EvidenceFollowupText, ...], Field(max_length=16)] = ()
    scope_if_attributed: EvidenceFollowupText | None = None


class PartyAttributionAdvisoryProjection(BaseModel):
    """Closed public projection of all party attribution warnings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    parties: Annotated[tuple[PartyAttributionWarningProjection, ...], Field(min_length=1, max_length=2)]

    @property
    def fields(self) -> tuple[str, ...]:
        """Return all unverified address fields in party order."""
        return tuple(field for party in self.parties for field in party.fields)


class CountryVocabularyWarningProjection(BaseModel):
    """Public country warning retaining its closed status and exact finding text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: EvidenceFollowupText
    field: EvidenceFollowupText
    stated_code: EvidenceFollowupText
    status: StatedCountryCodeStatus
    detail: EvidenceFollowupText


class CountryVocabularyAdvisoryProjection(BaseModel):
    """Closed public projection of every country-vocabulary warning."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    parties: Annotated[tuple[CountryVocabularyWarningProjection, ...], Field(min_length=1, max_length=2)]

    def by_status(self, status: StatedCountryCodeStatus) -> tuple[CountryVocabularyWarningProjection, ...]:
        """Return the warnings for one exact canonical country-code status."""
        return tuple(party for party in self.parties if party.status is status)
