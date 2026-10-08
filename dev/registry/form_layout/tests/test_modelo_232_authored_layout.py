"""Modelo 232 keeps each counterparty and amount in its own official table row."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("revision_id", ["2016-2017", "2018-y-siguientes"])
def test_232_official_groups_preserve_every_record_and_binding(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/232")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.placements) == len(revision.casillas) == 48
    blocks = [b for p in layout.pages for s in p.sections for b in s.blocks]
    grids = {b.id: b for b in blocks if isinstance(b, FormGridBlock)}
    assert {k: (len(g.rows), len(g.columns)) for k, g in grids.items()} == {
        "related": (5, 9),
        "intangibles": (3, 6),
        "haven": (12, 5),
        "securities": (12, 5),
    }
    for i, row in enumerate(grids["related"].rows, 1):
        assert [str(c.casilla_id) for c in row.cells] == [
            f"vinculada-{i}-{suffix}"
            for suffix in (
                "nif",
                "fjo",
                "razon-social",
                "tipo-vinculacion",
                "provincia-pais",
                "tipo-operacion",
                "ingreso-pago",
                "metodo-valoracion",
                "importe",
            )
        ]
    for group, prefix, suffixes in (
        (
            "intangibles",
            "page_01.vinculada-metodo",
            ("nif", "fjo", "razon-social", "provincia-pais", "tipo-vinculacion", "importe"),
        ),
        ("haven", "page_02.paraiso-operacion", ("descripcion", "persona", "fjo", "clave-pais", "importe")),
        (
            "securities",
            "page_02.paraiso-valor",
            ("tipo", "entidad", "clave-pais", "valor-adquisicion", "porcentaje-participacion"),
        ),
    ):
        for i, row in enumerate(grids[group].rows, 1):
            assert [str(c.binding_id) for c in row.cells] == [f"modelo-232.{prefix}-{i}-{s}" for s in suffixes]
    context = [b for b in blocks if isinstance(b, FormContextFieldBlock)]
    assert len(context) == 7
    fields = [resolve_form_context_field(revision, b) for b in context]
    assert {str(f.producer_key) for f in fields if f.producer_key is not None} == {
        "taxpayer.tax_id",
        "taxpayer.surnames_or_legal_name",
        "taxpayer.given_name",
        "amendment_evidence.sustitutiva_or_complementaria_marker",
        "amendment_evidence.original_aeat_receipt",
    }
    assert {str(f.draft_attribute) for f in fields if f.draft_attribute is not None} == {
        "period_start_date",
        "period_end_date",
    }
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert layout.review.notes and "Country-name display remains absent" in layout.review.notes
    assert any(s.source_ref == "boe-2017-10042-modelo-232-form-pdf" for s in layout.design_sources)
