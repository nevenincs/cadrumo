"""Grounding checks for the current Modelo 379 registry surface."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path, resources
from .._corpus_catalogue import verify_source_catalogue
from .._legal import verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M379_LEGAL_REFS = {
    "orden-hfp-1415-2023:art-1",
    "orden-hfp-1415-2023:art-2",
    "orden-hfp-1415-2023:art-3",
    "orden-hfp-1415-2023:art-4",
    "orden-hfp-1415-2023:art-5",
}
_M379_SOURCE_REFS = {
    "aeat-modelo-379-procedure",
    "boe-modelo-379-form",
}


def test_modelo_379_current_registry_uses_2024_cesop_sources_without_fake_calculation() -> None:
    authority = resources().modelos.authority
    modelo = authority.modelo("379")

    assert set(modelo.revisions) == {"2024-y-siguientes"}
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M379_LEGAL_REFS
    assert set(modelo.source_refs) == _M379_SOURCE_REFS

    revision = modelo.revisions["2024-y-siguientes"]

    assert revision.valid_from == date(2024, 1, 1)
    assert revision.period_selector.year_from == 2024
    assert set(revision.period_selector.periods) == {"1T", "2T", "3T", "4T"}
    assert set(revision.orden_aplicabilidad) == {"orden-hfp-1415-2023:art-1"}
    assert set(revision.legal_refs) == _M379_LEGAL_REFS
    assert set(revision.source_refs) == _M379_SOURCE_REFS
    assert revision.casillas
    assert {casilla.input_kind for casilla in revision.casillas} == {"manual"}
    assert not revision.formulas
    assert revision.completeness_manifest is None
    assert not revision.deadline_windows
    assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {"boe-modelo-379-form"}
    assert {link.surface for link in revision.application_links} == {"filing", "deadline"}
    assert {schedule.id for schedule in revision.filing_schedules} == {"modelo-379-trimestral"}

    stale_refs = {"enrolled-modelo-379-procedure", "enrolled-modelo-379-layout"}
    observed_source_refs = set(modelo.source_refs) | set(revision.source_refs)
    observed_source_refs.update(ref.workbook_source for ref in revision.workbook_parity_refs)
    observed_source_refs.update(ref for casilla in revision.casillas for ref in casilla.source_refs)
    assert stale_refs.isdisjoint(observed_source_refs)

    verify_legal_catalogue(
        {ref: authority.catalogues.legal[ref] for ref in _M379_LEGAL_REFS},
        source_root=bundled_path(),
    )
    verify_source_catalogue(bundled_path(), {ref: authority.catalogues.sources[ref] for ref in _M379_SOURCE_REFS})
