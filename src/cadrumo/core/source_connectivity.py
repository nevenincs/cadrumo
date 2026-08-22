"""Canonical identity and disposition vocabulary for source connectivity.

The connectivity census accounts for capabilities before legal adjudication
settles whether, and where, they feed a modelo.  Candidate identity must
therefore survive changes to source locators, discovered implementation detail,
and proposed casilla destinations.  :class:`SourceConnectivityCandidateIdentity`
holds only the stable census token; evidence and mutable adjudication facts
belong to the census row built around it.

Likewise, :class:`SourceConnectivityDisposition` is the complete vocabulary for
the outcome of that adjudication.  It distinguishes connections from candidates,
three independently actionable blocking boundaries, deliberate manual handling,
stale duplication, and genuine inapplicability.  Free-form states would make a
new capability indistinguishable from a misspelling and defeat the census
ratchet.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ._models import STRICT_FROZEN_CONFIG

__all__ = [
    "SourceConnectivityCandidateId",
    "SourceConnectivityCandidateIdentity",
    "SourceConnectivityCensusRow",
    "SourceConnectivityDisposition",
    "SourceConnectivityGrounding",
]

_BoundedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_GroundingLocator = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_048),
]


type SourceConnectivityCandidateId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9._:-]*$",
    ),
]
"""Stable, machine-readable identity of one connectivity census candidate.

The token is deliberately opaque.  It may describe a source capability or a
registry destination, but it must not encode a source-code location or a
tentative legal mapping whose later correction would manufacture a new row.
"""


class SourceConnectivityCandidateIdentity(BaseModel):
    """Location-independent identity of one connectivity census candidate."""

    model_config = STRICT_FROZEN_CONFIG

    candidate_id: SourceConnectivityCandidateId
    """Canonical token retained across discovery and adjudication revisions."""


class SourceConnectivityDisposition(StrEnum):
    """Closed adjudication state of one source-connectivity candidate."""

    CONNECTED = "connected"
    """The production calculation path carries the source into its casillas."""

    CONNECT_CANDIDATE = "connect_candidate"
    """Evidence justifies bounded adjudication of a possible connection."""

    GROUNDING_BLOCKED = "grounding_blocked"
    """Official evidence has not yet settled legal substitutability."""

    INGRESS_BLOCKED = "ingress_blocked"
    """The typed fact exists but lacks a governed calculation input path."""

    REGISTRY_BLOCKED = "registry_blocked"
    """The destination cannot yet be expressed by the validated registry."""

    MANUAL_BY_DESIGN = "manual_by_design"
    """Operator input remains authoritative by an explicit design decision."""

    DUPLICATE_OR_STALE = "duplicate_or_stale"
    """The candidate duplicates another authority or no longer exists."""

    NOT_APPLICABLE = "not_applicable"
    """The candidate does not apply to the filing connectivity boundary."""


class SourceConnectivityGrounding(BaseModel):
    """Re-fetchable evidence supporting one census adjudication."""

    model_config = STRICT_FROZEN_CONFIG

    locator: _GroundingLocator
    """Stable URL, catalogue identity, or repository locator for the evidence."""

    summary: _BoundedText
    """The fact this evidence establishes for the candidate."""


_BLOCKED_DISPOSITIONS = frozenset(
    {
        SourceConnectivityDisposition.GROUNDING_BLOCKED,
        SourceConnectivityDisposition.INGRESS_BLOCKED,
        SourceConnectivityDisposition.REGISTRY_BLOCKED,
    },
)


class SourceConnectivityCensusRow(SourceConnectivityCandidateIdentity):
    """Governed adjudication record for one stable connectivity candidate.

    Connected-slice proof is intentionally absent until its separate contract
    is introduced.  This row establishes only the evidence and accountability
    needed for every disposition, including fail-closed blocked states.
    """

    disposition: SourceConnectivityDisposition
    grounding: tuple[SourceConnectivityGrounding, ...] = Field(min_length=1)
    owner: _BoundedText
    review_condition: _BoundedText | None = None
    expires_on: date | None = None
    bounded_follow_up: _BoundedText | None = None

    @model_validator(mode="after")
    def _require_actionable_unresolved_state(self) -> SourceConnectivityCensusRow:
        """Refuse unresolved rows that cannot drive bounded follow-up."""
        if self.disposition in _BLOCKED_DISPOSITIONS:
            missing = [
                field_name
                for field_name, value in (
                    ("review_condition", self.review_condition),
                    ("expires_on", self.expires_on),
                    ("bounded_follow_up", self.bounded_follow_up),
                )
                if value is None
            ]
            if missing:
                rendered = ", ".join(missing)
                raise ValueError(f"blocked connectivity row requires {rendered}")
            if self.expires_on <= date.today():
                raise ValueError("blocked connectivity row expires_on must be in the future")
        elif self.disposition is SourceConnectivityDisposition.CONNECT_CANDIDATE:
            if self.review_condition is None or self.bounded_follow_up is None:
                raise ValueError(
                    "connectivity candidate requires review_condition and bounded_follow_up",
                )
        elif (
            self.disposition is SourceConnectivityDisposition.MANUAL_BY_DESIGN
            and self.review_condition is None
        ):
            raise ValueError("manual-by-design connectivity row requires review_condition")
        return self
