"""Grounding checks for the current Modelo 189 registry surface."""

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
    authority = compiled_bundled_authority()
    modelo = authority.modelo("189")
    revision = modelo.revisions["2025"]

    assert_sole_current_edition(modelo, "2025")
    assert modelo.calculation_class == "informative"
    assert set(modelo.legal_refs) == _M189_LEGAL_REFS
    assert set(modelo.source_refs) == _M189_SOURCE_REFS

    assert revision.valid_from == date(2025, 1, 1)
    assert_edition_opens_at_filing_year(revision, 2025)
    assert set(revision.period_selector.periods) == {"0A"}
    assert set(revision.orden_aplicabilidad) == {
        "orden-eha-3481-2008:art-1",
        "orden-hfp-1180-2023:art-primero",
        "orden-hfp-1284-2023:art-11",
        # Orden HAC/132/2026 is carried in this edition's legal_refs, which set
        # the 2026 values it publishes, but not in orden_aplicabilidad: the
        # edition's applicability is still established by the 2008 base orden
        # and the two 2023 amendments.
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
    assert_deadline_window_for_filing_year(revision, 2025, "modelo-189-2025-0a")
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
