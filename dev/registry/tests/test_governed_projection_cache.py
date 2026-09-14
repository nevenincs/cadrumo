"""Regression coverage for authority-generation-aware projection caching."""

from __future__ import annotations

from datetime import date
from types import MappingProxyType

import pytest

from cadrumo.domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    cache_governed_projection,
    governed_facts_in_scope,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_ID = "test-projection-cache"
_EFFECTIVE_DATE = date(2025, 6, 30)


def _candidate(value: str) -> CandidateFactAuthority:
    fact = GovernedFact.model_validate(
        {
            "fact_id": _FACT_ID,
            "family": "mapping",
            "provider_id": "projection-cache-fixture",
            "variants": (
                {
                    "variant_id": f"{_FACT_ID}:{value}",
                    "date_axis": "filing_period",
                    "valid_from": date(2025, 1, 1),
                    "legal_refs": ("test-law",),
                    "review_status": "agent_reviewed",
                    "ownership": "authored",
                    "payload": {"kind": "mapping", "entries": ({"key": "value", "value": value},)},
                },
            ),
        },
    )
    return CandidateFactAuthority(GovernedFactCatalogue(facts={fact.fact_id: fact}))


@cache_governed_projection()
def _project_mapping(effective_date: date) -> MappingProxyType[str, str]:
    owner = governed_facts_in_scope()
    assert owner is not None
    resolved = owner.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    assert isinstance(resolved, ResolvedMappingFact)
    return MappingProxyType({entry.key: entry.value for entry in resolved.payload.entries})


def test_projection_cache_is_scoped_to_candidate_authority_incarnation() -> None:
    """Equal unpublished digests must not merge distinct candidate projections."""
    first_candidate = _candidate("first")
    second_candidate = _candidate("second")
    assert first_candidate.authority_digest == second_candidate.authority_digest

    with validating_governed_facts(first_candidate):
        first = _project_mapping(_EFFECTIVE_DATE)
        first_repeat = _project_mapping(_EFFECTIVE_DATE)
    with validating_governed_facts(second_candidate):
        second = _project_mapping(_EFFECTIVE_DATE)

    assert first is first_repeat
    assert first == {"value": "first"}
    assert second == {"value": "second"}
    assert second is not first
