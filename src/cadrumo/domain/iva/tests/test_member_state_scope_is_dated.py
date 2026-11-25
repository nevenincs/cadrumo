"""A Member State's intra-community status is decided by the operation date.

Membership of the Union changes over time, so the territorial scope a country code
establishes must come from the catalogue in force on the operation's own date. The
published catalogue authors one edition, so the authority here serves a two-edition
fact 0131 split at a change in which one state leaves, and the real resolver answers
for dates on both sides of it.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import cast

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedGovernedFact,
    ResolvedMappingFact,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..establishment import territorial_scope_for_country
from ..schema import IvaTerritorialScope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_ID = "eu-member-state-catalogue"
_LEAVING = "se"
_STAYING = "de"
_CHANGE = date(filing_year_envelope().horizon, 7, 1)


class _TwoMembershipEditions:
    """The pinned authority, with the member-state fact split at ``_CHANGE`` into two editions."""

    def __init__(self, operation: PinnedAuthorityOperation, base: ResolvedMappingFact) -> None:
        self._operation = operation
        self._base = base

    def __getattr__(self, name: str) -> object:
        return getattr(self._operation, name)

    def _edition(self, *, older: bool, on: date) -> ResolvedMappingFact:
        entries = tuple(
            entry if older else entry.model_copy(update={"value": _without_leaving_state(str(entry.value))})
            for entry in self._base.payload.entries
        )
        return self._base.model_copy(
            update={
                "payload": self._base.payload.model_copy(update={"entries": entries}),
                "variant_id": f"{_FACT_ID}:{'older' if older else 'newer'}",
                "effective_date": on,
                "valid_from": date(filing_year_envelope().floor, 1, 1) if older else _CHANGE,
                "valid_to": _CHANGE - timedelta(days=1) if older else None,
            },
        )

    def resolve_governed_fact(self, query: MappingFactQuery) -> ResolvedGovernedFact:
        if query.fact_id != _FACT_ID:
            return self._operation.resolve_governed_fact(query)
        return self._edition(older=query.effective_date < _CHANGE, on=query.effective_date)


def _without_leaving_state(value: str) -> str:
    kept = [
        part
        for part in value.split(",")
        if part.strip().lower() != _LEAVING and not part.strip().lower().endswith(f"={_LEAVING}")
    ]
    return ",".join(kept)


def _scope(editions: _TwoMembershipEditions, code: str, on: date) -> IvaTerritorialScope | None:
    return territorial_scope_for_country(code, effective_date=on, operation=cast(PinnedAuthorityOperation, editions))


def test_a_state_is_a_member_only_on_the_dates_its_edition_carries() -> None:
    with bundled_indexed_authority().operation() as operation:
        base = operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id=_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=_CHANGE,
            ),
        )
        assert isinstance(base, ResolvedMappingFact)
        editions = _TwoMembershipEditions(operation, base)
        member = IvaTerritorialScope.from_registry("eu_member")
        third = IvaTerritorialScope.from_registry("third_country")
        before = _CHANGE - timedelta(days=1)

        assert _scope(editions, "SE", before) == member
        assert _scope(editions, "SE", _CHANGE) == third
        assert _scope(editions, "DE", before) == member
        assert _scope(editions, "DE", _CHANGE) == member
