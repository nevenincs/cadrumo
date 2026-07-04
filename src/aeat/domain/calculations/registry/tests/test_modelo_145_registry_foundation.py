"""Modelo 145 registry foundation tests."""

from __future__ import annotations

import pytest

from .._authority import bundled_authority
from .._support_matrix import build_support_matrix

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2012-01-31-y-siguientes"


def _modelo_145():
    authority = bundled_authority()
    return authority.modelo("145"), authority.catalogues


def test_modelo_145_loads_as_local_payer_communication_not_filing() -> None:
    modelo, _catalogues = _modelo_145()
    revision = modelo.revisions[_REVISION_ID]
    surfaces = {link.surface for link in revision.application_links}

    assert modelo.calculation_class == "informative"
    assert modelo.cadence == "ad_hoc"
    assert surfaces == {"communication", "payer_delivery", "export"}
    assert {link.id for link in revision.application_links} == {
        "modelo-145-communication",
        "modelo-145-payer-delivery",
        "modelo-145-export",
    }
    assert not revision.filing_schedules
    assert not revision.deadline_windows
    assert not revision.live_cross_references
    assert "filing" not in surfaces
    assert "deadline" not in surfaces
    assert "portal" not in surfaces


def test_modelo_145_casillas_and_parity_cite_official_sources() -> None:
    modelo, catalogues = _modelo_145()
    revision = modelo.revisions[_REVISION_ID]

    assert {casilla.id for casilla in revision.casillas} >= {
        "perceptor.nif",
        "perceptor.situacion-familiar",
        "pension-compensatoria.importe-anual",
        "anualidades-alimentos.importe-anual",
        "vivienda-habitual.financiacion-ajena",
        "acuse-recibo.empresa-entidad",
    }
    for casilla in revision.casillas:
        assert "rd-439-2007:art-88" in casilla.legal_refs
        assert "aeat-modelo-145-form" in casilla.source_refs
        assert "aeat-dr-145-v20" in casilla.source_refs
        assert catalogues.sources["aeat-modelo-145-form"].evidence_tier == "official_source_guidance"
        assert catalogues.sources["aeat-dr-145-v20"].evidence_tier == "layout_authority"

    (parity,) = revision.workbook_parity_refs
    assert parity.id == "modelo-145-dr-v20"
    assert parity.workbook_source == "aeat-dr-145-v20"
    assert parity.formula_coverage == "record_design_layout"
    assert not parity.runner_required
    assert parity.source_refs == ("aeat-dr-145-v20",)


def test_modelo_145_export_link_does_not_claim_completed_fichero_layout() -> None:
    authority = bundled_authority()
    modelo = authority.modelo("145")
    revision = modelo.revisions[_REVISION_ID]
    export_link = next(link for link in revision.application_links if link.id == "modelo-145-export")
    support_entry = next(entry for entry in build_support_matrix(authority) if entry.modelo_id == "145")

    assert not revision.export_layouts
    assert support_entry.has_fixed_width_export is False
    assert export_link.surface == "export"
    assert export_link.consumer == "aeat.application.modelo"
    assert export_link.requires_snapshot is True
    assert export_link.source_refs == ("aeat-dr-145-v20",)
