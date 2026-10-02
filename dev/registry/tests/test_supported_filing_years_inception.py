"""The supported-year audit owes nothing for a year before a modelo's declared inception.

The cases come from the live declarations and editions: a modelo with a declared
inception inside the envelope, and a modelo with no declaration whose earliest
edition starts after the floor. The undeclared copy of the first proves the
omission comes from the declaration rather than from the corpus.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.modelo_inception import DeclaredInception
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, SupportedFilingYearsCatalogue

from ..conformance.registry_schema_support import committed_registry_tree
from ..supported_filing_years import audit_supported_filing_years
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _earliest_authored_year(modelo: ModeloDefinition) -> int:
    firsts = [
        min(revision.period_selector.years) if revision.period_selector.years else revision.period_selector.year_from
        for revision in modelo.revisions.values()
    ]
    return min(year for year in firsts if year is not None)


def _gap_years(modelo: ModeloDefinition, support: SupportedFilingYearsCatalogue) -> set[int]:
    _modelos, catalogues = committed_registry_tree()
    gaps = audit_supported_filing_years((modelo,), catalogue=support, sources=catalogues.sources)
    return {gap.filing_year for gap in gaps}


def test_years_before_a_declared_inception_are_not_listed_as_gaps() -> None:
    """Live declarations inside the envelope leave no gap below them, and removing one restores it."""
    support = committed_supported_filing_years()
    modelos, _catalogues = committed_registry_tree()
    declared = [
        modelo
        for modelo in modelos
        if isinstance(modelo.inception, DeclaredInception) and modelo.inception.filing_year > support.floor
    ]
    assert declared, "no live modelo declares an inception inside the support envelope"

    for modelo in declared:
        assert isinstance(modelo.inception, DeclaredInception)
        before = set(range(support.floor, modelo.inception.filing_year))
        assert not before & _gap_years(modelo, support), f"modelo {modelo.id} lists pre-inception years as gaps"
        undeclared = modelo.model_copy(update={"inception": None})
        assert before <= _gap_years(undeclared, support), f"modelo {modelo.id} without its inception lists no gap"


def test_an_undeclared_modelo_still_lists_its_unauthored_years() -> None:
    """Without a declared inception, every unauthored supported year stays on the worklist.

    Live undeclared modelos are joined by undeclared copies of every late-starting
    modelo, so the case survives the live set being authored down to the floor.
    """
    support = committed_supported_filing_years()
    modelos, _catalogues = committed_registry_tree()
    late_starting = [modelo for modelo in modelos if _earliest_authored_year(modelo) > support.floor]
    assert late_starting, "no live modelo starts after the support floor"
    cases = [modelo for modelo in late_starting if modelo.inception is None] + [
        modelo.model_copy(update={"inception": None}) for modelo in late_starting
    ]

    for modelo in cases:
        unauthored = set(range(support.floor, _earliest_authored_year(modelo)))
        assert unauthored <= _gap_years(modelo, support), f"modelo {modelo.id} lost its unauthored gaps"
