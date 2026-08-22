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

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from ._models import STRICT_FROZEN_CONFIG

__all__ = [
    "SourceConnectivityCandidateId",
    "SourceConnectivityCandidateIdentity",
    "SourceConnectivityDisposition",
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
