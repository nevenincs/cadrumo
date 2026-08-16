"""Grounding checks for the current Modelo 361 registry surface."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path, resources
from .._corpus_catalogue import verify_source_catalogue
from .._legal import verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M361_LEGAL_REFS = {
    "orden-eha-789-2010:art-7",
    "orden-eha-789-2010:art-8",
    "orden-eha-789-2010:art-9",
    "orden-eha-789-2010:art-10",
}
_M361_SOURCE_REFS = {
    "aeat-modelo-361-procedure",
    "aeat-modelo-361-devolucion-solicitada",
    "aeat-modelo-361-lista-operaciones",
    "boe-modelo-361-form",
}


def test_modelo_361_current_registry_uses_361_articles_without_fake_calculation() -> None:
    authority = resources().modelos.authority
    modelo = authority.modelo("361")
    revision = modelo.revisions["2010-y-siguientes"]

    assert modelo.cadence == "ad_hoc"
    assert set(modelo.legal_refs) == _M361_LEGAL_REFS
    assert set(revision.legal_refs) == _M361_LEGAL_REFS
    assert set(revision.orden_aplicabilidad) == {"orden-eha-789-2010:art-7"}
    assert set(modelo.source_refs) == _M361_SOURCE_REFS
    assert set(revision.source_refs) == _M361_SOURCE_REFS
    assert revision.casillas
    assert {casilla.input_kind for casilla in revision.casillas} == {"manual"}
    assert not revision.formulas
    assert revision.completeness_manifest is None
    assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {"boe-modelo-361-form"}
    assert {link.surface for link in revision.application_links} == {"filing", "deadline"}
    assert {schedule.id for schedule in revision.filing_schedules} == {"modelo-361-ad-hoc"}

    windows = {window.id: window for window in revision.deadline_windows}
    assert set(windows) == {"modelo-361-2024-ad-hoc", "modelo-361-2025-ad-hoc"}
    assert windows["modelo-361-2024-ad-hoc"].opens_on == date(2025, 1, 1)
    assert windows["modelo-361-2024-ad-hoc"].closes_on == date(2025, 9, 30)
    assert windows["modelo-361-2025-ad-hoc"].opens_on == date(2026, 1, 1)
    assert windows["modelo-361-2025-ad-hoc"].closes_on == date(2026, 9, 30)
    assert all("orden-eha-789-2010:art-10" in window.legal_refs for window in windows.values())

    stale_refs = {
        "orden-eha-789-2010:art-1",
        "orden-eha-789-2010:art-4",
        "enrolled-modelo-361-procedure",
    }
    assert stale_refs.isdisjoint(modelo.legal_refs)
    assert stale_refs.isdisjoint(modelo.source_refs)

    verify_legal_catalogue(
        {ref: authority.catalogues.legal[ref] for ref in _M361_LEGAL_REFS},
        source_root=bundled_path(),
    )
    verify_source_catalogue(bundled_path(), {ref: authority.catalogues.sources[ref] for ref in _M361_SOURCE_REFS})
