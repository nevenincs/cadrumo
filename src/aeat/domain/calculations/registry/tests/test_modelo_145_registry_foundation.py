"""Modelo 145 registry foundation tests."""

from __future__ import annotations

import json
import re

import pytest

from .....core.resources import bundled_path
from .. import CasillaFieldKind, resolve_export_layout
from .._authority import bundled_authority
from .._support_matrix import build_support_matrix

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2012-01-31-y-siguientes"
_DR145_ROW_RE = re.compile(
    r"^(?P<number>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+(?P<type>A|An|Num)\s+(?P<text>.+)$",
)
_FIELD_DR_NUMBER_RE = re.compile(r"-dr-(?P<number>\d{2})-")


def _modelo_145():
    authority = bundled_authority()
    return authority.modelo("145"), authority.catalogues


def _official_dr145_rows() -> dict[int, tuple[int, int, str]]:
    extracted_path = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_145",
        "files",
        "dr145v20.pdf.extracted.json",
    )
    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    rows: dict[int, tuple[int, int, str]] = {}
    for unit in extracted["units"]:
        for line in unit["text"].splitlines():
            match = _DR145_ROW_RE.match(line)
            if match is None:
                continue
            rows[int(match["number"])] = (int(match["offset"]), int(match["length"]), match["text"])
    return rows


def _field_dr_number(field_id: str) -> int:
    match = _FIELD_DR_NUMBER_RE.search(field_id)
    assert match is not None, field_id
    return int(match["number"])


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


def test_modelo_145_export_layout_is_grounded_in_dr145_record_design() -> None:
    authority = bundled_authority()
    modelo = authority.modelo("145")
    revision = modelo.revisions[_REVISION_ID]
    snapshot = authority.snapshot("145", filing_year=2026, period="comunicacion")
    resolved_layout = resolve_export_layout(snapshot)
    layout = resolved_layout.layout
    fields_by_dr_number = {_field_dr_number(field.id): field for field in resolved_layout.ordered_fields}
    official_rows = _official_dr145_rows()

    assert layout.id == "modelo-145-dr-v20-fixed-width"
    assert layout.source_refs == ("aeat-dr-145-v20",)
    assert len(revision.casillas) == 55
    assert set(fields_by_dr_number) == set(official_rows)
    for row_number, field in fields_by_dr_number.items():
        official_offset, official_length, _official_text = official_rows[row_number]
        assert (field.offset, field.length) == (official_offset, official_length)

    assert fields_by_dr_number[1].kind == CasillaFieldKind.LITERAL
    assert fields_by_dr_number[1].literal == "<T145010>"
    assert fields_by_dr_number[2].kind == CasillaFieldKind.HEADER
    assert fields_by_dr_number[2].header_key == "page_complementaria"
    assert fields_by_dr_number[58].kind == CasillaFieldKind.FILLER
    assert fields_by_dr_number[59].kind == CasillaFieldKind.LITERAL
    assert fields_by_dr_number[59].literal == "</T145010>"


def test_modelo_145_export_link_remains_local_communication_export() -> None:
    authority = bundled_authority()
    modelo = authority.modelo("145")
    revision = modelo.revisions[_REVISION_ID]
    export_link = next(link for link in revision.application_links if link.id == "modelo-145-export")
    support_entry = next(entry for entry in build_support_matrix(authority) if entry.modelo_id == "145")

    assert {layout.id for layout in revision.export_layouts} == {"modelo-145-dr-v20-fixed-width"}
    assert support_entry.has_fixed_width_export is True
    assert export_link.surface == "export"
    assert export_link.consumer == "aeat.application.modelo"
    assert export_link.requires_snapshot is True
    assert export_link.source_refs == ("aeat-dr-145-v20",)
