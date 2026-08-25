"""Modelo 145 registry foundation tests.

See Also:
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision whose communication links, casillas, source refs, and
        export layouts are asserted here.
    :func:`~domain.calculations.registry.resolve_export_layout`
        Export-layout resolver checked against the official DR145 fixed-width
        record design.
    :func:`~domain.calculations.registry.build_support_matrix`
        Support matrix surface that reports Modelo 145 fixed-width export
        availability without filing semantics.
    :mod:`~application.modelo._m145_communication`
        Application ownership contract backed by this non-filing registry
        foundation.
    :mod:`~application.modelo._m145_communication_records`
        Local communication record lifecycle that consumes the same snapshot and
        layout authority.
"""

from __future__ import annotations

import json
import re

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .. import CasillaFieldKind, ExportFieldDefinition, resolve_export_layout
from ..authority import bundled_authority
from ..snapshot import build_snapshot
from ..support_matrix import build_support_matrix

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2012-01-31-y-siguientes"
_FORBIDDEN_M145_SURFACES = frozenset(
    {
        "aeat_electronic_tramite",
        "deadline",
        "electronic_tramite",
        "filing",
        "live_read",
        "live-read",
        "portal",
        "receipt",
        "submit",
        "tramite",
    }
)
_DR145_ROW_RE = re.compile(
    r"^(?P<number>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+(?P<type>A|An|Num)\s+(?P<text>.+)$",
)


def _modelo_145():
    # Structural declaration checks only -- no snapshot, no filing claim -- so
    # this reads the compile-only tree directly rather than through
    # ``bundled_authority()``, whose ``.load()`` validates every modelo in the
    # bundled tree before returning anything and would fail this M145-only
    # check on an unrelated modelo's missing filing capability.
    modelos, catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == "145"), catalogues


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


def _field_covering(
    fields: tuple[ExportFieldDefinition, ...],
    *,
    offset: int,
    length: int,
) -> ExportFieldDefinition:
    matches = [
        field
        for field in fields
        if field.offset is not None
        and field.length is not None
        and field.offset <= offset
        and offset + length <= field.offset + field.length
    ]
    assert len(matches) == 1, (offset, length, [field.id for field in matches])
    return matches[0]


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
    assert surfaces.isdisjoint(_FORBIDDEN_M145_SURFACES)
    for link in revision.application_links:
        surface_text = f"{link.id} {link.surface}".replace("-", "_")
        assert not any(surface.replace("-", "_") in surface_text for surface in _FORBIDDEN_M145_SURFACES)


def test_modelo_145_casillas_and_parity_cite_official_sources() -> None:
    modelo, catalogues = _modelo_145()
    revision = modelo.revisions[_REVISION_ID]

    assert len(revision.casillas) == 56
    assert {casilla.id for casilla in revision.casillas} >= {
        "comunicacion.pagina-complementaria",
        "perceptor.nif",
        "perceptor.situacion-familiar",
        "descendiente-1.anio-nacimiento",
        "ascendiente-1.anio-nacimiento",
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
    """Parses M145's fixed-width export layout, a filing-adjacent claim.

    Built directly from the compile-only tree, scoped to M145 alone, rather
    than through ``bundled_authority()`` -- see ``_modelo_145``'s docstring.
    Kept at the default FILING grade: this asserts the export layout's field
    offsets against the official DR145 record design, the same class of claim
    as parsing a fixed-width record for filing.
    """
    modelo, catalogues = _modelo_145()
    revision = modelo.revisions[_REVISION_ID]
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="comunicacion",
    )
    resolved_layout = resolve_export_layout(snapshot)
    layout = resolved_layout.layout
    fields = resolved_layout.ordered_fields
    official_rows = _official_dr145_rows()

    assert layout.id == "modelo-145-dr-v20-fixed-width"
    assert layout.source_refs == ("aeat-dr-145-v20",)
    # DR145 rows 12-14, 48-50 and 54-56 are each three independently
    # numbered Num rows (día/mes/año), not a parent field with declared
    # sub-parts, so each triad is modelled as three registry casillas and
    # three registry fields rather than one combined text slot: 50 + 6
    # casillas, 53 + 6 fields over the prior one-field-per-triad count.
    assert len(revision.casillas) == 56
    assert len(fields) == 59
    assert set(official_rows) == set(range(1, 60))

    expected_offset = 1
    for field in sorted(fields, key=lambda item: item.offset or 0):
        assert field.offset == expected_offset
        assert field.offset is not None
        assert field.length is not None
        expected_offset = field.offset + field.length
    assert expected_offset == 611

    for row_number, (offset, length, _official_text) in official_rows.items():
        field = _field_covering(fields, offset=offset, length=length)
        if row_number == 58:
            assert field.kind == CasillaFieldKind.FILLER
        else:
            assert field.kind != CasillaFieldKind.FILLER
        assert (field.offset, field.length) == (offset, length)

    record_start = resolved_layout.fields_by_id["modelo-145-dr-01-record-start"]
    assert record_start.kind == CasillaFieldKind.LITERAL
    assert record_start.literal == "<T145010>"

    page_indicator = _field_covering(
        fields,
        offset=official_rows[2][0],
        length=official_rows[2][1],
    )
    assert page_indicator.kind == CasillaFieldKind.CASILLA
    assert page_indicator.casilla_id == "comunicacion.pagina-complementaria"

    _expected_date_triad_fields = {
        12: ("modelo-145-dr-12-perceptor-movilidad-geografica-fecha-dia", "perceptor.movilidad-geografica-fecha-dia"),
        13: ("modelo-145-dr-13-perceptor-movilidad-geografica-fecha-mes", "perceptor.movilidad-geografica-fecha-mes"),
        14: (
            "modelo-145-dr-14-perceptor-movilidad-geografica-fecha-anio",
            "perceptor.movilidad-geografica-fecha-anio",
        ),
        48: ("modelo-145-dr-48-comunicacion-firma-fecha-dia", "comunicacion.firma-fecha-dia"),
        49: ("modelo-145-dr-49-comunicacion-firma-fecha-mes", "comunicacion.firma-fecha-mes"),
        50: ("modelo-145-dr-50-comunicacion-firma-fecha-anio", "comunicacion.firma-fecha-anio"),
        54: ("modelo-145-dr-54-acuse-recibo-fecha-dia", "acuse-recibo.fecha-dia"),
        55: ("modelo-145-dr-55-acuse-recibo-fecha-mes", "acuse-recibo.fecha-mes"),
        56: ("modelo-145-dr-56-acuse-recibo-fecha-anio", "acuse-recibo.fecha-anio"),
    }
    for row_number, (expected_field_id, expected_casilla_id) in _expected_date_triad_fields.items():
        field = _field_covering(fields, offset=official_rows[row_number][0], length=official_rows[row_number][1])
        assert field.id == expected_field_id
        assert field.casilla_id == expected_casilla_id

    aeat_reserved = resolved_layout.fields_by_id["modelo-145-dr-58-aeat-reservado"]
    assert aeat_reserved.kind == CasillaFieldKind.FILLER
    assert (aeat_reserved.offset, aeat_reserved.length) == (official_rows[58][0], official_rows[58][1])

    record_end = resolved_layout.fields_by_id["modelo-145-dr-59-record-end"]
    assert record_end.kind == CasillaFieldKind.LITERAL
    assert record_end.literal == "</T145010>"


def test_modelo_145_export_link_remains_local_communication_export() -> None:
    # Genuinely needs the full ``ValidatedRegistryAuthority`` -- unlike the
    # other tests in this module, ``build_support_matrix`` iterates
    # ``authority.modelos`` across the WHOLE tree, so this cannot be scoped to
    # M145 alone without changing that function's signature. Stays on
    # ``bundled_authority()`` and stays red until the tree-wide gate clears.
    authority = bundled_authority()
    modelo = authority.modelo("145")
    revision = modelo.revisions[_REVISION_ID]
    export_link = next(link for link in revision.application_links if link.id == "modelo-145-export")
    support_entry = next(entry for entry in build_support_matrix(authority) if entry.modelo_id == "145")

    assert {layout.id for layout in revision.export_layouts} == {"modelo-145-dr-v20-fixed-width"}
    assert support_entry.has_fixed_width_export is True
    assert export_link.surface == "export"
    assert export_link.consumer == "cadrumo.application.modelo"
    assert export_link.requires_snapshot is True
    assert export_link.source_refs == ("aeat-dr-145-v20",)
