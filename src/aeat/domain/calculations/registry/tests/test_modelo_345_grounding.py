"""Grounding checks for the current Modelo 345 registry surface."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path, resources
from .._corpus_catalogue import verify_source_catalogue
from .._legal import verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M345_LEGAL_REFS = {
    "orden-hfp-823-2022:art-1",
    "orden-hfp-823-2022:art-2",
    "orden-hfp-823-2022:art-3",
    "orden-hfp-823-2022:art-4",
    "orden-hfp-823-2022:art-5",
    "orden-hfp-528-2023:art-unico",
    "orden-hfp-528-2023:df-unica",
    "orden-hfp-1397-2023:art-sexto",
    "orden-hfp-1397-2023:df-unica",
    "orden-hac-1504-2024:art-octavo",
    "orden-hac-1504-2024:df-unica",
    "orden-hac-1430-2025:art-septimo",
    "orden-hac-1430-2025:df-unica",
}
_M345_SOURCE_REFS = {
    "aeat-modelo-345-procedure",
    "aeat-modelo-345-deadlines",
    "aeat-dr-345-2025",
    "boe-modelo-345-base-order",
    "boe-modelo-345-2023-amendment-hfp-528",
    "boe-modelo-345-2023-amendment-hfp-1397",
    "boe-modelo-345-2024-amendment-hac-1504",
    "boe-modelo-345-2025-amendment-hac-1430",
}


def test_modelo_345_current_registry_uses_2025_sources_without_fake_calculation() -> None:
    authority = resources().modelos.authority
    modelo = authority.modelo("345")
    revision = modelo.revisions["2025"]

    assert set(modelo.revisions) == {"2025"}
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M345_LEGAL_REFS
    assert set(modelo.source_refs) == _M345_SOURCE_REFS

    assert revision.valid_from == date(2025, 1, 1)
    assert revision.period_selector.years == (2025,)
    assert set(revision.period_selector.periods) == {"0A"}
    assert set(revision.orden_aplicabilidad) == {
        "orden-hfp-823-2022:art-1",
        "orden-hfp-823-2022:art-3",
        "orden-hfp-823-2022:art-4",
        "orden-hac-1430-2025:art-septimo",
        "orden-hac-1430-2025:df-unica",
    }
    assert set(revision.legal_refs) == _M345_LEGAL_REFS
    assert set(revision.source_refs) == _M345_SOURCE_REFS
    assert revision.casillas
    assert {casilla.input_kind for casilla in revision.casillas} == {"manual"}
    assert not revision.formulas
    assert revision.completeness_manifest is None
    assert {window.id for window in revision.deadline_windows} == {"modelo-345-2025-0a"}
    assert {window.closes_on for window in revision.deadline_windows} == {date(2026, 2, 2)}
    assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {"aeat-dr-345-2025"}
    assert {link.surface for link in revision.application_links} == {"filing", "deadline"}
    assert {schedule.id for schedule in revision.filing_schedules} == {"modelo-345-anual"}

    stale_refs = {"enrolled-modelo-345-procedure", "enrolled-modelo-345-layout"}
    observed_source_refs = set(modelo.source_refs) | set(revision.source_refs)
    observed_source_refs.update(ref.workbook_source for ref in revision.workbook_parity_refs)
    observed_source_refs.update(ref for casilla in revision.casillas for ref in casilla.source_refs)
    observed_source_refs.update(ref for link in revision.application_links for ref in link.source_refs)
    assert stale_refs.isdisjoint(observed_source_refs)

    verify_legal_catalogue(
        {ref: authority.catalogues.legal[ref] for ref in _M345_LEGAL_REFS},
        source_root=bundled_path(),
    )
    verify_source_catalogue(bundled_path(), {ref: authority.catalogues.sources[ref] for ref in _M345_SOURCE_REFS})
