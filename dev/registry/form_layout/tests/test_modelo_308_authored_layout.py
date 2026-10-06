"""The recargo grid follows printed rows, not consecutive transport fields."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_recargo_base_rate_and_quota_share_their_official_row() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308")).revisions["2019-y-siguientes"]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    section = next(s for p in layout.pages for s in p.sections if s.id == "req")
    grid = section.blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [c.key for c in grid.columns] == ["base", "tipo", "cuota"]
    assert [[c.casilla_id for c in row.cells] for row in grid.rows] == [
        ["decl.req-base-08", "decl.req-tipo-09", "decl.req-cuota-10"],
        ["decl.req-base-11", "decl.req-tipo-12", "decl.req-cuota-13"],
        ["decl.req-base-14", "decl.req-tipo-15", "decl.req-cuota-16"],
    ]
    positions = {p.casilla_id: p.box_number for p in layout.placements}
    assert positions["decl.tipo-declaracion"] is None
    assert positions["decl.tipo-tributacion"] is None
    assert positions["decl.req-cuota-13"] == "13"
    assert positions["decl.req-iva-devolver-17"] == "17"


def test_transport_families_and_purchase_sale_rows_remain_separate() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308")).revisions["2019-y-siguientes"]
    sections = {s.id: s for p in revision.form_layouts[0].pages for s in p.sections}
    assert {"vehiculo", "embarcacion", "aeronave", "adquirente", "articulo21"} <= sections.keys()
    contexts = [b for b in sections["identificacion"].blocks if isinstance(b, FormContextFieldBlock)]
    assert {b.export_field_id for b in contexts} == {"m308-2019.declaracion.f007", "m308-2019.declaracion.f008"}
    grid = sections["liquidacion-transporte"].blocks[0]
    assert isinstance(grid, FormGridBlock)
    assert [[c.casilla_id for c in row.cells] for row in grid.rows] == [
        ["decl.mtn-precio-adquisicion", "decl.mtn-tipo-01", "decl.mtn-iva-soportado"],
        ["decl.mtn-precio-venta", "decl.mtn-tipo-04", "decl.mtn-maximo-devolver"],
    ]


@pytest.mark.parametrize("amounts,expected", [(("210.25", "40.10", "0"), "250.35"), (("0", "0", "0"), "0")])
@pytest.mark.parametrize("revision_id", ["2009-2011-junio", "2011-julio-2015", "2016-2018", "2019-y-siguientes"])
def test_refund_total_uses_all_three_declared_quotas(amounts: tuple[str, ...], expected: str, revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308")).revisions[revision_id]
    formula = next(f for f in revision.formulas if f.target_casilla_id == "decl.req-iva-devolver-17")
    ids = ("decl.req-cuota-10", "decl.req-cuota-13", "decl.req-cuota-16")
    values = dict(zip(ids, map(Decimal, amounts), strict=True))
    unresolved: set[str] = set()

    def evaluate() -> Decimal:
        return evaluate_expression(
            formula.expression,
            values=values,
            binding_values={},
            parameters={},
            date_context={},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=unresolved,
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
        )

    assert evaluate() == Decimal(expected)
    assert not unresolved
    del values[ids[-1]]
    with pytest.raises(RegistryValidationError, match="referenced before evaluation"):
        evaluate()


def test_paper_signature_context_is_not_an_electronic_filing_claim() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308")).revisions["2019-y-siguientes"]
    ids = {"firma-lugar", "firma-fecha", "firma"}
    fields = [c for c in revision.casillas if c.id in ids]
    assert len(fields) == 3
    assert all(c.input_kind.value == "informational" and not c.required for c in fields)
    assert all(not c.export_refs and c.formula is None and c.binding is None for c in fields)
    sections = revision.form_layouts[0].pages[0].sections
    signature = next(section for section in sections if section.id == "firma")
    assert all(block.kind == "field" for block in signature.blocks)
    assert {block.casilla_id for block in signature.blocks if block.kind == "field"} == ids
    assert [section.id for section in sections].index("firma") < [section.id for section in sections].index(
        "devolucion"
    )
    assert form_layout_failures(revision) == ()


def test_2016_has_full_historical_fields_without_gaining_electronic_filing() -> None:
    model = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308"))
    historical = model.revisions["2016-2018"]
    current = model.revisions["2019-y-siguientes"]
    assert historical.authority_grade == "applicability"
    assert not historical.export_layouts
    assert len(historical.casillas) == 51
    assert len(current.casillas) == 50
    assert {"papel-nif", "papel-apellidos"} <= {c.id for c in historical.casillas}
    assert not {"papel-nif", "papel-apellidos"} & {c.id for c in current.casillas}
    assert historical.form_layouts[0].seed_source.value == "authored"
    assert form_layout_failures(historical) == ()
    assert historical.formulas[0].expression == current.formulas[0].expression
    assert set(historical.constructs[0].casilla_ids) == {c.id for c in historical.casillas}
    assert set(current.constructs[0].casilla_ids) == {c.id for c in current.casillas}


def test_2011_preserves_historical_account_and_identity_representation() -> None:
    model = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308"))
    revision = model.revisions["2011-julio-2015"]
    fields = {c.id: c for c in revision.casillas}
    assert len(fields) == 50
    assert revision.authority_grade == "applicability"
    assert not revision.export_layouts
    assert fields["decl.devolucion-ccc"].data_type == "text"
    assert fields["decl.mtn-adquirente-pais"].data_type == "text"
    assert fields["decl.devolucion-ccc"].number == "770-789"
    assert {"papel-nombre-completo", "decl.mtn-adquirente-nombre-completo"} <= fields.keys()
    assert not {"decl.devolucion-iban", "decl.devolucion-bic", "decl.tipo-tributacion", "decl.nombre"} & fields.keys()
    assert set(revision.constructs[0].casilla_ids) == fields.keys()
    assert revision.form_layouts[0].seed_source.value == "authored"
    assert form_layout_failures(revision) == ()
    for locale in ("es", "en", "ca", "hu"):
        assert all(c.get_label(locale) != c.id for c in fields.values())
    later = {c.id for c in model.revisions["2016-2018"].casillas}
    assert "decl.devolucion-ccc" not in later
    assert {"decl.devolucion-iban", "decl.devolucion-bic"} <= later


def test_2009_form_does_not_backdate_article21_fields_or_later_bank_offsets() -> None:
    model = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308"))
    revision = model.revisions["2009-2011-junio"]
    fields = {c.id: c for c in revision.casillas}
    assert len(fields) == 48
    assert not {"decl.mtn-iva-soportado-art21", "decl.mtn-iva-devolver-art21"} & fields.keys()
    assert fields["decl.devolucion-ccc"].number == "744-763"
    assert fields["decl.observaciones"].number == "884-1233"
    assert revision.authority_grade == "applicability"
    assert not revision.export_layouts
    assert form_layout_failures(revision) == ()
    assert revision.form_layouts[0].seed_source.value == "authored"
    placements = {p.casilla_id: p for p in revision.form_layouts[0].placements}
    # BOE printed sale-price 02 differs from record-design 04; no identity merge.
    assert placements["decl.mtn-precio-venta"].box_number == "02"
    assert placements["decl.mtn-tipo-01"].box_number == "02"
    assert fields["decl.mtn-precio-venta"].semantic_role != fields["decl.mtn-tipo-01"].semantic_role
    assert set(revision.constructs[0].casilla_ids) == fields.keys()
    for locale in ("es", "en", "ca", "hu"):
        assert all(c.get_label(locale) != c.id for c in fields.values())


@pytest.mark.parametrize("revision_id", ["2009-2011-junio", "2011-julio-2015", "2016-2018", "2019-y-siguientes"])
def test_paper_refund_amount_is_declared_and_not_an_invented_sum(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/308")).revisions[revision_id]
    amount = next(c for c in revision.casillas if c.id == "papel-importe-devolucion")
    assert amount.input_kind == "manual"
    assert amount.data_type == "money"
    assert amount.formula is None and amount.binding is None
    assert not amount.export_refs
    assert not any(f.target_casilla_id == amount.id for f in revision.formulas)
    section = next(s for p in revision.form_layouts[0].pages for s in p.sections if s.id == "devolucion")
    assert any(b.kind == "field" and b.casilla_id == amount.id for b in section.blocks)
    assert amount.id in revision.constructs[0].casilla_ids
