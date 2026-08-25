"""Grounding checks for the current Modelo 280 registry surface."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path, resources
from ..corpus_catalogue import verify_source_catalogue
from ..legal import verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M280_LEGAL_REFS = {
    "orden-hap-2118-2015:art-1",
    "orden-hap-2118-2015:art-2",
    "orden-hap-2118-2015:art-4",
    "orden-hap-2118-2015:art-5",
    "orden-hfp-1822-2016:art-sexto",
    "orden-hac-1276-2019:art-quinto",
    "orden-hfp-1192-2022:art-cuarto",
}
_M280_SOURCE_REFS = {
    "aeat-modelo-280-procedure",
    "aeat-dr-280-2022",
    "boe-modelo-280-base-order",
    "boe-modelo-280-2016-amendment-hfp-1822",
    "boe-modelo-280-2019-amendment-hac-1276",
    "boe-modelo-280-2022-amendment-hfp-1192",
}


def test_modelo_280_current_registry_uses_2025_sources_without_fake_calculation() -> None:
    authority = resources().modelos.authority
    modelo = authority.modelo("280")
    revision = modelo.revisions["2025"]

    assert set(modelo.revisions) == {"2025"}
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M280_LEGAL_REFS
    assert set(modelo.source_refs) == _M280_SOURCE_REFS

    assert revision.valid_from == date(2025, 1, 1)
    assert revision.period_selector.years == (2025,)
    assert set(revision.period_selector.periods) == {"0A"}
    assert set(revision.orden_aplicabilidad) == {
        "orden-hap-2118-2015:art-1",
        "orden-hfp-1822-2016:art-sexto",
        "orden-hac-1276-2019:art-quinto",
        "orden-hfp-1192-2022:art-cuarto",
    }
    assert set(revision.legal_refs) == _M280_LEGAL_REFS
    assert set(revision.source_refs) == _M280_SOURCE_REFS
    assert revision.casillas
    roles_by_id = {casilla.id: casilla.semantic_role for casilla in revision.casillas}
    assert roles_by_id["declarante-nif"] == "irpf_declarante_nif"
    assert roles_by_id["ejercicio-declaracion"] == "filing_year"
    assert {casilla.input_kind for casilla in revision.casillas} == {"manual"}
    assert not revision.formulas
    assert revision.completeness_manifest is None
    assert {window.id for window in revision.deadline_windows} == {"modelo-280-2025-0a"}
    assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {"aeat-dr-280-2022"}
    # "export" joined the surfaces when the modelo's export layout was authored;
    # the link set is a consequence of that, not a drift.
    assert {link.surface for link in revision.application_links} == {"deadline", "export", "filing"}
    assert {schedule.id for schedule in revision.filing_schedules} == {"modelo-280-anual"}

    stale_refs = {"enrolled-modelo-280-procedure", "enrolled-modelo-280-layout"}
    observed_source_refs = set(modelo.source_refs) | set(revision.source_refs)
    observed_source_refs.update(ref.workbook_source for ref in revision.workbook_parity_refs)
    observed_source_refs.update(ref for casilla in revision.casillas for ref in casilla.source_refs)
    observed_source_refs.update(ref for link in revision.application_links for ref in link.source_refs)
    assert stale_refs.isdisjoint(observed_source_refs)

    verify_legal_catalogue(
        {ref: authority.catalogues.legal[ref] for ref in _M280_LEGAL_REFS},
        source_root=bundled_path(),
    )
    verify_source_catalogue(bundled_path(), {ref: authority.catalogues.sources[ref] for ref in _M280_SOURCE_REFS})
