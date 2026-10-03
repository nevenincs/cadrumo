"""The IVA category catalogue's per-modelo exclusion keys.

Fact 0084 carries ``category_exclusion.<modelo>.<category>`` entries whose
value is a typed verdict: ``excluded`` when the governing text settles that the
modelo does not declare that category's operations, ``unsettled`` when the
exclusion is arguable and the operations stay declared with an advisory. For
Modelo 347 they encode RD 1065/2007 art. 33.2.g, "Las importaciones y
exportaciones de mercancías".

The refusal tests feed deliberately malformed entries through a fact source
that extends the published catalogue's own entries for that one query and
delegates every other query to the published authority.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

import pytest

from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..errors import RegistryValidationError
from ..facts.payloads import MappingFactEntry, MappingFactPayload
from ..facts.resolution import GovernedFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..iva_category_catalogue import IvaCategoryCatalogue, IvaCategoryExclusion, resolve_iva_category_catalogue
from ..schema import SupportedFilingYearsCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON_DATE = date(2025, 12, 31)
_CATALOGUE_FACT_ID = "iva-category-component-catalogue"


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Run every test inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


def test_modelo_347_excludes_goods_exports_and_imports_and_leaves_assimilated_exports_unsettled() -> None:
    catalogue = resolve_iva_category_catalogue(effective_date=_ON_DATE)

    assert catalogue.exclusion("347", "export_third_country_zero_rated") is IvaCategoryExclusion.EXCLUDED
    assert catalogue.exclusion("347", "import_third_country") is IvaCategoryExclusion.EXCLUDED
    assert catalogue.exclusion("347", "export_assimilated_zero_rated") is IvaCategoryExclusion.UNSETTLED
    assert catalogue.exclusion("347", "domestic_general") is None
    assert catalogue.exclusion("347", "operacion_no_sujeta") is None
    assert catalogue.exclusion("349", "export_third_country_zero_rated") is None


@dataclass(frozen=True, slots=True)
class _ExtendedCatalogueSource:
    """Answer the catalogue query with its published entries plus ``extra``; delegate everything else."""

    base: PinnedAuthorityOperation
    extra: tuple[tuple[str, str], ...]

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        resolved = self.base.resolve_governed_fact(query)
        if query.fact_id != _CATALOGUE_FACT_ID or not isinstance(resolved, ResolvedMappingFact):
            return resolved
        entries = (*resolved.payload.entries, *(MappingFactEntry(key=key, value=value) for key, value in self.extra))
        return resolved.model_copy(update={"payload": MappingFactPayload(entries=entries)})

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.base.supported_filing_years()


def _resolve_with(extra: tuple[tuple[str, str], ...]) -> IvaCategoryCatalogue:
    with bundled_indexed_authority().operation() as operation:
        return resolve_iva_category_catalogue(
            effective_date=_ON_DATE,
            authority=_ExtendedCatalogueSource(base=operation, extra=extra),
        )


def test_the_extended_source_resolves_a_well_formed_exclusion() -> None:
    """The refusals below are meaningful only because this same source accepts a valid entry."""
    catalogue = _resolve_with((("category_exclusion.190.domestic_general", "unsettled"),))

    assert catalogue.exclusion("190", "domestic_general") is IvaCategoryExclusion.UNSETTLED


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        pytest.param(
            (("category_exclusion.190.mercancias_exportadas", "excluded"),),
            "undeclared category",
            id="undeclared-category",
        ),
        pytest.param(
            (("category_exclusion..domestic_general", "excluded"),),
            "names no modelo",
            id="no-modelo",
        ),
        pytest.param(
            (("category_exclusion.190.domestic_general", "excluida"),),
            "unknown verdict",
            id="unknown-verdict",
        ),
    ],
)
def test_a_malformed_exclusion_entry_is_refused(extra: tuple[tuple[str, str], ...], message: str) -> None:
    with pytest.raises(RegistryValidationError, match=message):
        _resolve_with(extra)
