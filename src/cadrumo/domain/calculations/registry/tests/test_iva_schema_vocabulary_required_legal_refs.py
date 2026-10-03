"""Required legal references in the IVA schema vocabulary fail closed when they name none."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pytest

from ..authority import PinnedAuthorityOperation
from ..errors import RegistryValidationError
from ..facts.resolution import GovernedFactQuery, MappingFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..governed_fact_scope import GovernedFactSource
from ..iva_legal_vocabulary import resolve_iva_art69_dos_service_catalogue, resolve_iva_exemption_article_catalogue
from ..m303_schema_vocabulary import resolve_m303_regime_composition_catalogue, resolve_m303_tax_territory_catalogue
from ..schema import SupportedFilingYearsCatalogue
from ..schema_base import DateAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(2026, 3, 10)


class _Definition(Protocol):
    @property
    def legal_refs(self) -> tuple[str, ...]: ...


class _Catalogue(Protocol):
    @property
    def definitions(self) -> Sequence[_Definition]: ...


type _Resolver = Callable[..., _Catalogue]

_CONSUMERS: tuple[tuple[str, _Resolver], ...] = (
    ("exemption_article.", resolve_iva_exemption_article_catalogue),
    ("art_69_dos_service.", resolve_iva_art69_dos_service_catalogue),
    ("tax_territory.", resolve_m303_tax_territory_catalogue),
    ("m303_regime_composition.", resolve_m303_regime_composition_catalogue),
)


@dataclass
class _FixedFact:
    resolved: ResolvedMappingFact
    support: SupportedFilingYearsCatalogue

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
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


def _with_value(resolved: ResolvedMappingFact, key: str, value: str) -> ResolvedMappingFact:
    entries = tuple(
        entry.model_copy(update={"value": value}) if entry.key == key else entry for entry in resolved.payload.entries
    )
    return resolved.model_copy(update={"payload": resolved.payload.model_copy(update={"entries": entries})})


def _first_legal_refs_key(resolved: ResolvedMappingFact, prefix: str) -> str:
    keys = [
        entry.key
        for entry in resolved.payload.entries
        if isinstance(entry.key, str) and entry.key.startswith(prefix) and entry.key.endswith(".legal_refs")
    ]
    assert keys, f"the vocabulary declares no {prefix}*.legal_refs entry"
    return keys[0]


@pytest.mark.parametrize(("prefix", "resolve"), _CONSUMERS, ids=[prefix for prefix, _ in _CONSUMERS])
def test_authored_legal_references_resolve_non_empty(
    operation: PinnedAuthorityOperation, prefix: str, resolve: _Resolver
) -> None:
    catalogue = resolve(effective_date=_ON, authority=operation)

    assert catalogue.definitions
    assert all(definition.legal_refs for definition in catalogue.definitions)


@pytest.mark.parametrize("separators", [",,", " , "])
@pytest.mark.parametrize(("prefix", "resolve"), _CONSUMERS, ids=[prefix for prefix, _ in _CONSUMERS])
def test_a_required_legal_reference_entry_of_only_separators_is_refused(
    operation: PinnedAuthorityOperation, prefix: str, resolve: _Resolver, separators: str
) -> None:
    resolved = _vocabulary(operation)
    key = _first_legal_refs_key(resolved, prefix)
    authority: GovernedFactSource = _FixedFact(
        _with_value(resolved, key, separators), operation.supported_filing_years()
    )

    with pytest.raises(RegistryValidationError) as raised:
        resolve(effective_date=_ON, authority=authority)

    assert str(raised.value) == f"IVA schema vocabulary {key!r} must contain unique references"
