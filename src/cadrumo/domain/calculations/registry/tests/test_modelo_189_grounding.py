"""Grounding checks for the current Modelo 189 registry surface."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path, resources
from .._corpus_catalogue import verify_source_catalogue
from .._legal import verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M189_LEGAL_REFS = {
    "orden-eha-3481-2008:art-1",
    "orden-eha-3481-2008:art-5",
    "orden-hfp-1180-2023:art-primero",
    "orden-hfp-1284-2023:art-11",
    "orden-hac-132-2026:art-unico",
}
_M189_SOURCE_REFS = {
    "aeat-modelo-189-procedure",
    "boe-modelo-189-base-order",
    "boe-modelo-189-2023-amendment-hfp-1180",
    "boe-modelo-189-2023-amendment-hfp-1284",
    "boe-modelo-189-2025-values",
}


def test_modelo_189_current_registry_uses_2025_sources_without_fake_calculation() -> None:
    authority = resources().modelos.authority
    modelo = authority.modelo("189")
    revision = modelo.revisions["2025"]

    assert set(modelo.revisions) == {"2025"}
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M189_LEGAL_REFS
    assert set(modelo.source_refs) == _M189_SOURCE_REFS

    assert revision.valid_from == date(2025, 1, 1)
    assert revision.period_selector.years == (2025,)
    assert set(revision.period_selector.periods) == {"0A"}
    assert set(revision.orden_aplicabilidad) == {
        "orden-eha-3481-2008:art-1",
        "orden-hfp-1180-2023:art-primero",
        "orden-hfp-1284-2023:art-11",
        "orden-hac-132-2026:art-unico",
    }
    assert set(revision.legal_refs) == _M189_LEGAL_REFS
    # The REVISION additionally cites the official Diseno de Registro in its
    # current enrolled source set; the modelo manifest above does not, which is the
    # existing split rather than a drift. Asserted as the manifest set plus that
    # one design, so a second unexplained source would still be caught.
    assert set(revision.source_refs) == _M189_SOURCE_REFS | {"aeat-dr-189-2023"}
    assert revision.casillas
    roles_by_id = {casilla.id: casilla.semantic_role for casilla in revision.casillas}
    assert roles_by_id["declarante-nif"] == "irpf_declarante_nif"
    assert roles_by_id["ejercicio-declaracion"] == "filing_year"
    assert {casilla.input_kind for casilla in revision.casillas} == {"manual"}
    assert not revision.formulas
    assert revision.completeness_manifest is None
    assert {window.id for window in revision.deadline_windows} == {"modelo-189-2025-0a"}
    assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {
        "boe-modelo-189-2023-amendment-hfp-1284",
    }
    # "export" joined the surfaces when the modelo's export layout was authored;
    # the link set is a consequence of that, not a drift.
    assert {link.surface for link in revision.application_links} == {"deadline", "export", "filing"}
    assert {schedule.id for schedule in revision.filing_schedules} == {"modelo-189-anual"}

    stale_refs = {"enrolled-modelo-189-procedure", "enrolled-modelo-189-layout"}
    observed_source_refs = set(modelo.source_refs) | set(revision.source_refs)
    observed_source_refs.update(ref.workbook_source for ref in revision.workbook_parity_refs)
    observed_source_refs.update(ref for casilla in revision.casillas for ref in casilla.source_refs)
    observed_source_refs.update(ref for link in revision.application_links for ref in link.source_refs)
    assert stale_refs.isdisjoint(observed_source_refs)

    verify_legal_catalogue(
        {ref: authority.catalogues.legal[ref] for ref in _M189_LEGAL_REFS},
        source_root=bundled_path(),
    )
    verify_source_catalogue(bundled_path(), {ref: authority.catalogues.sources[ref] for ref in _M189_SOURCE_REFS})
