"""The cash-accounting catalogue is reused only for the resolved fact it came from."""

from __future__ import annotations

import gc
from dataclasses import dataclass, field
from datetime import date

import pytest

from ..authority import PinnedAuthorityOperation
from ..facts.resolution import GovernedFactQuery, MappingFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..iva_schema_vocabulary import _BY_AUTHORITY, _PROJECTIONS, resolve_iva_cash_accounting_catalogue
from ..schema import SupportedFilingYearsCatalogue
from ..schema_base import DateAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(2026, 3, 10)


@dataclass
class _FixedFact:
    resolved: ResolvedMappingFact
    support: SupportedFilingYearsCatalogue
    queries: list[GovernedFactQuery] = field(default_factory=list)

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        self.queries.append(query)
        return self.resolved

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.support


def _vocabulary(operation: PinnedAuthorityOperation) -> ResolvedMappingFact:
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-statutory-schema-vocabulary",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_ON,
        ),
    )
    assert isinstance(resolved, ResolvedMappingFact)
    return resolved


def _with_description(resolved: ResolvedMappingFact, token: str, description: str) -> ResolvedMappingFact:
    key = f"cash_accounting.{token}.description"
    entries = tuple(
        entry.model_copy(update={"value": description}) if entry.key == key else entry
        for entry in resolved.payload.entries
    )
    assert entries != resolved.payload.entries, f"vocabulary declares no {key!r}"
    return resolved.model_copy(update={"payload": resolved.payload.model_copy(update={"entries": entries})})


def test_a_repeated_resolution_reuses_the_projected_catalogue(operation: PinnedAuthorityOperation) -> None:
    first = resolve_iva_cash_accounting_catalogue(effective_date=_ON, authority=operation)
    second = resolve_iva_cash_accounting_catalogue(effective_date=_ON, authority=operation)

    assert second is first


def test_a_different_resolved_fact_is_projected_afresh(operation: PinnedAuthorityOperation) -> None:
    """STALE KEY: equal-looking inputs from another fact must not be served the cached catalogue."""
    resolved = _vocabulary(operation)
    cached = resolve_iva_cash_accounting_catalogue(effective_date=_ON, authority=operation)
    token = str(cached.none_token)
    changed = _with_description(resolved, token, "changed for the stale-key check")

    projected = resolve_iva_cash_accounting_catalogue(
        effective_date=_ON, authority=_FixedFact(changed, operation.supported_filing_years())
    )

    assert projected is not cached
    assert projected.definition(token).description == "changed for the stale-key check"
    assert cached.definition(token).description != "changed for the stale-key check"


def test_a_collected_fact_releases_its_projections(operation: PinnedAuthorityOperation) -> None:
    """A recycled identity cannot reach a dead fact's catalogue, because the entry leaves with it."""
    changed = _with_description(_vocabulary(operation), "none", "collected with its fact")
    key = id(changed)
    resolve_iva_cash_accounting_catalogue(
        effective_date=_ON, authority=_FixedFact(changed, operation.supported_filing_years())
    )
    assert key in _PROJECTIONS

    del changed
    gc.collect()

    assert key not in _PROJECTIONS


def test_the_same_authority_is_asked_again_for_another_date(operation: PinnedAuthorityOperation) -> None:
    """STALE KEY: a cached coordinate does not answer for a different one."""
    authority = _FixedFact(_vocabulary(operation), operation.supported_filing_years())
    resolve_iva_cash_accounting_catalogue(effective_date=_ON, authority=authority)
    resolve_iva_cash_accounting_catalogue(effective_date=_ON, authority=authority)
    resolve_iva_cash_accounting_catalogue(effective_date=date(2025, 6, 1), authority=authority)

    assert [query.effective_date for query in authority.queries] == [_ON, date(2025, 6, 1)]


def test_a_collected_authority_releases_its_coordinates(operation: PinnedAuthorityOperation) -> None:
    authority = _FixedFact(_vocabulary(operation), operation.supported_filing_years())
    key = (id(authority), _ON)
    resolve_iva_cash_accounting_catalogue(effective_date=_ON, authority=authority)
    assert key in _BY_AUTHORITY

    del authority
    gc.collect()

    assert key not in _BY_AUTHORITY
