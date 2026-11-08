"""Membership of a taxpayer's declared activities in a registry-declared IAE group set.

The IAE tariffs (RDLeg 1175/1990) classify every business activity under a
three-digit group, optionally refined by one epigraph digit. Several rules key
off that classification rather than off a yes/no profile answer: whether a
declared rental is carried on as an activity, and whether the declarant runs a
teaching centre. Each such rule names the groups it means in its own governed
entity-set fact; this module owns reading that fact and judging the profile's
activities against it, so a group list never appears in Python.

Three outcomes, kept apart on purpose. An activity in a declared group is
:attr:`ActivityGroupMembership.DECLARED`. Activities that all parse and all
fall outside the set are :attr:`ActivityGroupMembership.DECLARED_ABSENT`, a
positive no. No activity at all, or any epigraph that does not parse, is
:attr:`ActivityGroupMembership.UNKNOWN`: an unanswered classification must
never read as an absence, because the consumers of an absence stop asking.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Final

from .errors import RegistryValidationError
from .facts.resolution import EntitySetFactQuery, ResolvedEntitySetFact
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

__all__ = [
    "ActivityGroupMembership",
    "activity_group_membership",
    "iae_activity_groups",
]

IAE_GROUP: Final[re.Pattern[str]] = re.compile(r"[0-9]{3}")
"""A three-digit IAE group, the only shape a group-set fact entity may take."""

IAE_EPIGRAPH: Final[re.Pattern[str]] = re.compile(r"(?P<group>[0-9]{3})(?:\.[0-9])?")
"""A three-digit IAE group, optionally followed by one epigraph digit; nothing else parses."""


class ActivityGroupMembership(StrEnum):
    """What the profile's declared activities say about one IAE group set."""

    DECLARED = "declared"
    """At least one declared activity is classified in a group the fact names."""
    DECLARED_ABSENT = "declared_absent"
    """Every declared activity parses and none is classified in the fact's groups."""
    UNKNOWN = "unknown"
    """No activity is declared, or an epigraph does not parse as an IAE classification."""


def iae_activity_groups(
    fact_id: str,
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> frozenset[str]:
    """Return the IAE groups the named entity-set fact declares on ``effective_date``.

    Raises:
        InternalInvariantError: When no authority is supplied and no scope is active.
        GovernedFactNotApplicableError: When the fact does not reach ``effective_date``.
        RegistryValidationError: When the fact is not a non-empty set of three-digit groups.
    """
    selected = require_governed_fact_authority(authority, subject=fact_id)
    resolved = selected.resolve_governed_fact(
        EntitySetFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise RegistryValidationError(f"{fact_id} must resolve as an entity-set fact")
    groups = frozenset(resolved.payload.entities)
    if not groups or any(IAE_GROUP.fullmatch(group) is None for group in groups):
        raise RegistryValidationError(f"{fact_id} must declare three-digit IAE groups")
    return groups


def activity_group_membership(
    activity_epigraphs: Sequence[str | None] | None,
    *,
    fact_id: str,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ActivityGroupMembership:
    """Return whether the declared activities fall in the named IAE group set.

    ``activity_epigraphs`` holds the IAE epigraph of each declared activity, or
    ``None`` for an activity that records none. The group is read exactly: a
    prefix of a declared group is not that group. The fact is read only once an
    activity is declared, so an empty profile costs no resolution.
    """
    if activity_epigraphs is None or len(activity_epigraphs) == 0:
        return ActivityGroupMembership.UNKNOWN
    groups = iae_activity_groups(fact_id, effective_date=effective_date, authority=authority)
    matches = [
        None if epigraph is None else IAE_EPIGRAPH.fullmatch(epigraph.strip()) for epigraph in activity_epigraphs
    ]
    if any(match is not None and match.group("group") in groups for match in matches):
        return ActivityGroupMembership.DECLARED
    if any(match is None for match in matches):
        return ActivityGroupMembership.UNKNOWN
    return ActivityGroupMembership.DECLARED_ABSENT
