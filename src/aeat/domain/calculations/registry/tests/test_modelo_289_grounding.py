"""Grounding checks for the current Modelo 289 registry surface."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path, resources
from .._corpus_catalogue import verify_source_catalogue
from .._legal import verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M289_LEGAL_REFS = {
    "rd-1021-2015:art-3",
    "rd-1021-2015:art-4",
    "rd-1021-2015:art-5",
    "orden-hap-1695-2016:art-1",
    "orden-hap-1695-2016:art-2",
    "orden-hap-1695-2016:art-3",
    "orden-hap-1695-2016:art-4",
    "orden-hap-1695-2016:art-5",
    "orden-hap-1695-2016:art-6",
    "orden-hfp-1308-2017:art-sexto",
    "orden-hac-1417-2018:art-sexto",
    "orden-hac-1276-2019:art-septimo",
    "orden-hac-1276-2020:art-sexto",
    "orden-hfp-1351-2021:art-octavo",
    "orden-hfp-1192-2022:art-sexto",
    "orden-hfp-1284-2023:art-15",
    "orden-hfp-1397-2023:art-quinto",
    "orden-hac-1504-2024:art-septimo",
    "orden-hac-1430-2025:art-sexto",
    "orden-hac-1430-2025:df-unica",
}
_M289_SOURCE_REFS = {
    "aeat-modelo-289-procedure",
    "aeat-modelo-289-webservice",
    "aeat-modelo-289-xsd-wsdl",
    "boe-rd-1021-2015",
    "boe-modelo-289-base-order",
    "boe-modelo-289-2017-amendment-hfp-1308",
    "boe-modelo-289-2018-amendment-hac-1417",
    "boe-modelo-289-2019-amendment-hac-1276",
    "boe-modelo-289-2020-amendment-hac-1276",
    "boe-modelo-289-2021-amendment-hfp-1351",
    "boe-modelo-289-2022-amendment-hfp-1192",
    "boe-modelo-289-2023-amendment-hfp-1284",
    "boe-modelo-289-2024-amendment-hfp-1397",
    "boe-modelo-289-2024-amendment-hac-1504",
    "boe-modelo-289-2025-amendment-hac-1430",
}


def test_modelo_289_current_registry_uses_2025_sources_without_fake_calculation() -> None:
    authority = resources().modelos.authority
    modelo = authority.modelo("289")
    revision = modelo.revisions["2025"]

    assert set(modelo.revisions) == {"2025"}
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M289_LEGAL_REFS
    assert set(modelo.source_refs) == _M289_SOURCE_REFS

    assert revision.valid_from == date(2025, 1, 1)
    assert revision.period_selector.years == (2025,)
    assert set(revision.period_selector.periods) == {"0A"}
    assert set(revision.orden_aplicabilidad) == {
        "rd-1021-2015:art-4",
        "orden-hap-1695-2016:art-1",
        "orden-hap-1695-2016:art-6",
        "orden-hac-1430-2025:art-sexto",
        "orden-hac-1430-2025:df-unica",
    }
    assert set(revision.legal_refs) == _M289_LEGAL_REFS
    assert set(revision.source_refs) == _M289_SOURCE_REFS
    assert revision.casillas
    roles_by_id = {casilla.id: casilla.semantic_role for casilla in revision.casillas}
    assert roles_by_id["declarante-nif"] == "irpf_declarante_nif"
    assert roles_by_id["ejercicio-declaracion"] == "filing_year"
    assert {casilla.input_kind for casilla in revision.casillas} == {"manual"}
    assert not revision.formulas
    assert revision.completeness_manifest is None
    assert {window.id for window in revision.deadline_windows} == {"modelo-289-2025-0a"}
    assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {"aeat-modelo-289-xsd-wsdl"}
    assert {link.surface for link in revision.application_links} == {"filing", "deadline"}
    assert {schedule.id for schedule in revision.filing_schedules} == {"modelo-289-anual"}

    stale_refs = {"enrolled-modelo-289-procedure", "enrolled-modelo-289-layout"}
    observed_source_refs = set(modelo.source_refs) | set(revision.source_refs)
    observed_source_refs.update(ref.workbook_source for ref in revision.workbook_parity_refs)
    observed_source_refs.update(ref for casilla in revision.casillas for ref in casilla.source_refs)
    observed_source_refs.update(ref for link in revision.application_links for ref in link.source_refs)
    assert stale_refs.isdisjoint(observed_source_refs)

    verify_legal_catalogue(
        {ref: authority.catalogues.legal[ref] for ref in _M289_LEGAL_REFS},
        source_root=bundled_path(),
    )
    verify_source_catalogue(bundled_path(), {ref: authority.catalogues.sources[ref] for ref in _M289_SOURCE_REFS})
