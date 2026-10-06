"""Keep the two independent base-sign rows from the official summary."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormCellKind, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("revision_id", ["2022", "2023-y-siguientes"])
def test_summary_preserves_sign_rows_and_has_no_negative_retention_box(revision_id: str) -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/188"))
    revision = modelo.revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    grid = next(s for s in layout.pages[0].sections if s.id == "resumen").blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [c.casilla_id for c in grid.rows[0].cells] == ["01", "02", "03"]
    assert [c.casilla_id for c in grid.rows[1].cells] == ["04", "05", None]
    assert grid.rows[1].cells[2].kind is FormCellKind.BLANK
    assert layout.design_sources[0].source_ref == "boe-1999-22372-modelo-188-form-pdf"


def test_nonpositive_recipient_count_label_includes_zero_bases() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/188"))
    revision = modelo.revisions["2023-y-siguientes"]
    count = next(c for c in revision.casillas if c.id == "04")
    assert "negativa o cero" in count.get_label("es")
    assert "una vez por cada registro" in (count.get_help("es") or "")


def test_recipient_values_preserve_signed_money_and_reject_invalid_codes() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/188"))
    revision = modelo.revisions["2023-y-siguientes"]
    fields = {str(c.id): c for c in revision.casillas}
    assert len(fields) == 32
    assert {str(c.id) for c in modelo.revisions["2022"].casillas} == set(fields)
    for identifier in ("rentas", "informacion-adicional", "base-retenciones"):
        field = fields[f"perceptor.{identifier}"]
        assert field.data_type.value == "money"
        assert field.constraints is None or field.constraints.violates(Decimal("-150.25")) is None
    for identifier in ("reducciones", "retenciones", "prima", "rendimiento-acreedor-hipotecario"):
        constraints = fields[f"perceptor.{identifier}"].constraints
        assert constraints is not None
        assert constraints.violates(Decimal("-0.01")) is not None
        assert constraints.violates(Decimal("0")) is None
    modality = fields["perceptor.modalidad"].constraints
    assert modality is not None
    assert modality.violates_text("1") is None
    assert modality.violates_text("2") is None
    assert modality.violates_text("3") is not None
    assert fields["perceptor.provincia"].data_type.value == "province_code"
    assert fields["perceptor.renta-vitalicia-identificacion"].data_type.value == "text"
    placements = revision.form_layouts[0].placements
    assert all(p.box_number is None for p in placements if str(p.casilla_id).startswith("perceptor."))
    assert set(fields) <= {str(c) for c in revision.constructs[0].casilla_ids}


def test_declarant_identity_and_amendments_are_typed_without_invented_receipts() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/188")).revisions["2023-y-siguientes"]
    fields = {str(c.id): c for c in revision.casillas}
    assert fields["decl.nif"].data_type.value == "nif"
    assert fields["decl.ejercicio"].data_type.value == "year"
    for identifier, valid, invalid in (
        ("telefono", "012345678", ("12345678", "1234567890", "abcdefghi")),
        ("numero-justificante", "1880000000001", ("1870000000001", "188000000000", "188abcdefghij")),
        ("justificante-anterior", "1880000000001", ("188000000000", "abcdefghijklm")),
        ("complementaria", "C", ("c", "S")),
        ("sustitutiva", "S", ("s", "C")),
    ):
        constraint = fields[f"decl.{identifier}"].constraints
        assert constraint is not None
        assert constraint.violates_text(valid) is None
        assert all(constraint.violates_text(value) is not None for value in invalid)
    layout = revision.form_layouts[0]
    assert [s.id for s in layout.pages[0].sections] == ["declarante", "declaracion", "resumen"]
    assert all(p.box_number is None for p in layout.placements if str(p.casilla_id).startswith("decl."))
    assert all(
        fields[p.casilla_id].continuidad_id is not None
        for p in layout.placements
        if str(p.casilla_id).startswith("decl.")
    )


def test_2022_does_not_import_2023_province_or_minor_identification_rules() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/188"))
    historical = {str(c.id): c for c in modelo.revisions["2022"].casillas}
    current = {str(c.id): c for c in modelo.revisions["2023-y-siguientes"].casillas}
    for fields, accepts_la_palma in ((historical, False), (current, True)):
        constraint = fields["perceptor.provincia"].constraints
        assert constraint is not None
        assert constraint.violates_text("08") is None
        assert constraint.violates_text("52") is None
        assert (constraint.violates_text("53") is None) is accepts_la_palma
        assert constraint.violates_text("54") is not None
        assert constraint.violates_text("8") is not None
        assert fields["perceptor.clave"].constraints is not None
        assert fields["perceptor.clave"].constraints.enum == ("B",)
    assert "menor de edad" in (historical["perceptor.representante-nif"].get_help("es") or "")
    assert "menor de 14" in (current["perceptor.representante-nif"].get_help("es") or "")
    for identifier in historical:
        assert historical[identifier].continuidad_id == current[identifier].continuidad_id
        assert "aeat-dr-188-2023" not in historical[identifier].source_refs
    assert modelo.revisions["2022"].form_layouts[0].design_sources[1].source_ref == "aeat-dr-188-2017"
