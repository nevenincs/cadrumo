"""Grounding checks for the current Modelo 280 registry surface."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from dev.registry.compiler.authority import compiled_bundled_authority

from ..compiler.corpus_catalogue import verify_source_catalogue
from ..compiler.legal_grounding import verify_legal_catalogue
from ._gate_support import (
    assert_deadline_window_for_filing_year,
    assert_edition_opens_at_filing_year,
    assert_sole_current_edition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

# The sole current edition this grounding test reviews. Its first exercise is the
# edition's identity, established by the ordenes asserted below, so it is bound once
# rather than derived from the support envelope.
_CURRENT_EDITION = 2025

_M280_LEGAL_REFS = {
    "orden-hap-2118-2015:art-1",
    "orden-hap-2118-2015:art-2",
    "orden-hap-2118-2015:art-4",
    "orden-hap-2118-2015:art-5",
    "ley-35-2006:da-26",
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


def test_modelo_280_current_registry_uses_current_edition_sources_without_fake_calculation() -> None:
    authority = compiled_bundled_authority()
    modelo = authority.modelo("280")
    revision = modelo.revisions[str(_CURRENT_EDITION)]

    assert_sole_current_edition(modelo, str(_CURRENT_EDITION))
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M280_LEGAL_REFS
    assert set(modelo.source_refs) == _M280_SOURCE_REFS

    assert revision.valid_from == date(_CURRENT_EDITION, 1, 1)
    assert_edition_opens_at_filing_year(revision, _CURRENT_EDITION)
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
    assert_deadline_window_for_filing_year(revision, _CURRENT_EDITION, f"modelo-280-{_CURRENT_EDITION}-0a")
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
