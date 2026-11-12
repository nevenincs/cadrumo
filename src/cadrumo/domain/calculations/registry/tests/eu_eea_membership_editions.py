"""Scope a test to the published facts with the EU/EEA membership edited into editions of its own.

The published membership authors one edition, so no country's membership
differs between dates. A test of the code that must decide such a country by
the date of the fact states its editions here; every other fact still resolves
from the published authority that the test leased.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date

from ..facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ..facts.schema import GovernedFact, GovernedFactCatalogue
from ..governed_fact_scope import (
    CandidateFactAuthority,
    GovernedFactSource,
    governed_facts_in_scope,
    validating_governed_facts,
)
from ..schema_references import TemporalSupportEnvelope

_FACT_ID = "eu-eea-country-membership"

type MembershipEdition = tuple[date, date | None, tuple[str, ...]]
"""One edition: the first day it holds, the last day (``None`` when open) and its country codes."""


class _MembershipEditionsSource:
    """Resolve the membership fact from the stated editions and every other fact from the lease."""

    def __init__(self, base: GovernedFactSource, membership: CandidateFactAuthority) -> None:
        self._base = base
        self._membership = membership

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        source = self._membership if query.fact_id == _FACT_ID else self._base
        return source.resolve_governed_fact(query)

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self._base.supported_filing_years()


def _edition_variant(valid_from: date, valid_to: date | None, countries: tuple[str, ...]) -> dict[str, object]:
    return {
        "variant_id": f"{_FACT_ID}:{valid_from.isoformat()}",
        "date_axis": "filing_period",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "payload": {"kind": "entity_set", "entities": countries},
        "legal_refs": ("test-law",),
        "source_refs": ("test-source",),
        "source_citations": ({"source_ref": "test-source", "required_text": ("test source",)},),
        "review_status": "pending_review",
        "ownership": "authored",
    }


@contextmanager
def eu_eea_membership_editions(*editions: MembershipEdition) -> Generator[GovernedFactSource]:
    """Scope the enclosed block to the leased facts with these membership editions.

    Raises:
        AssertionError: When the test holds no authority lease to take the other facts from.
    """
    base = governed_facts_in_scope()
    assert base is not None, "request the operation fixture to lease the published authority"
    fact = GovernedFact.model_validate(
        {
            "fact_id": _FACT_ID,
            "family": "entity_set",
            "variants": tuple(_edition_variant(*edition) for edition in editions),
        },
    )
    membership = CandidateFactAuthority(
        catalogue=GovernedFactCatalogue(facts={_FACT_ID: fact}),
        support=base.supported_filing_years(),
    )
    source = _MembershipEditionsSource(base, membership)
    with validating_governed_facts(source):
        yield source
