"""Modelo 156 keeps printed boxes distinct from electronic record positions."""

from hashlib import sha256
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory
from ...compiler.record_design import extract_record_design

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ROOT = Path("src/cadrumo/_data")
_MONTHS = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


def test_summary_uses_official_box_and_exact_export_context_without_wire_numbers() -> None:
    revision = load_modelo_directory(_ROOT / "registry/aeat/modelos/156").revisions["2003-y-siguientes"]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    assert layout.seed_source.value == "authored"
    assert layout.review.state.value == "generated"
    assert revision.authority_grade is not None and revision.authority_grade.value == "applicability"
    assert len(layout.placements) == len(revision.casillas) == 46
    assert {p.casilla_id: p.box_number for p in layout.placements if p.box_number} == {"numero-total-afiliados": "01"}
    summary, detail = layout.pages
    assert [s.id for s in summary.sections] == [
        "identificacion",
        "domicilio",
        "contacto",
        "declaracion",
        "resumen",
        "firma",
    ]
    contexts = [b for s in summary.sections for b in s.blocks if isinstance(b, FormContextFieldBlock)]
    assert {b.export_field_id for b in contexts} == {
        "modelo-156-t1-nif-declarante",
        "modelo-156-t1-ejercicio",
        "modelo-156-t1-contacto-telefono",
        "modelo-156-t1-contacto-nombre",
    }
    assert all(b.export_record_id == "modelo-156-declarante" for b in contexts)
    (members,) = detail.sections[0].blocks
    assert isinstance(members, FormRepeatingGroupBlock)
    assert members.export_record_id == "modelo-156-afiliado" and len(members.columns) == 27
    (calendar,) = members.grids
    assert isinstance(calendar, FormGridBlock)
    assert [row.key for row in calendar.rows] == _MONTHS
    assert [[cell.casilla_id for cell in row.cells] for row in calendar.rows] == [
        [f"cotizacion-{month}-situacion", f"cotizacion-{month}"] for month in _MONTHS
    ]
    casillas = {str(c.id): c for c in revision.casillas}
    for month in _MONTHS:
        assert casillas[f"cotizacion-{month}"].data_type.value == "money"
        status = casillas[f"cotizacion-{month}-situacion"]
        assert status.constraints is not None and status.constraints.enum == ("S", "N")
        assert status.constraints.violates_text("X") is not None
    assert layout.review.notes is not None and "typed status and money" in layout.review.notes
    pdf = _ROOT / "corpus/normatives/pdf/boe-a-2003-23509.pdf"
    assert sha256(pdf.read_bytes()).hexdigest() == "725580675df1b483d5cd270e804c1e00038977b673270104049123a3fe728313"


def test_official_month_fields_require_separate_status_and_amount() -> None:
    pdf = _ROOT / "corpus/aeat_official/disenos_registro/modelo_156/files/01-156-diseno-de-registro-vigente.pdf"
    _, members = extract_record_design(pdf).require_complete()
    fields = {field.offset: field for field in members.fields}
    for index in range(12):
        start = 88 + index * 9
        month = fields[start]
        assert month.length == 9
        assert month.content is not None
        assert "SITUACIÓN MENSUAL" in month.content
        assert "IMPORTE CUOTA" in month.content
        assert "S o una N" in month.content


def test_paper_address_and_signatory_fields_never_claim_electronic_slots() -> None:
    revision = load_modelo_directory(_ROOT / "registry/aeat/modelos/156").revisions["2003-y-siguientes"]
    paper = [c for c in revision.casillas if str(c.id).startswith(("domicilio-", "firma-"))]
    assert len(paper) == 11
    assert all(
        c.input_kind.value == "informational" and not c.export_refs and c.binding is None and c.formula is None
        for c in paper
    )
    assert all("boe-modelo-156-form-layout" in c.source_refs for c in paper)
    assert {str(c.id): c.data_type.value for c in paper}["firma-fecha"] == "date"
    assert {str(c.id): c.data_type.value for c in paper}["domicilio-codigo-postal"] == "postal_code"
    signature = revision.form_layouts[0].pages[0].sections[-1].blocks[-1]
    assert isinstance(signature, FormGridBlock)
    assert all(cell.kind.value == "blank" for row in signature.rows for cell in row.cells)
    assert [column.key for column in signature.columns] == ["firma", "administracion"]
    for page in revision.form_layouts[0].pages:
        for section in page.sections:
            assert "\u00c3" not in (section.official_heading or "")


def test_amendment_choices_share_exact_two_character_domain() -> None:
    revision = load_modelo_directory(_ROOT / "registry/aeat/modelos/156").revisions["2003-y-siguientes"]
    casilla = next(c for c in revision.casillas if c.id == "declaracion-complementaria-sustitutiva")
    assert casilla.constraints is not None and casilla.constraints.enum == ("C ", " S", "  ")
    for invalid in ("C", "S", "CS", "SC", "S ", " C", "XX", "c "):
        assert casilla.constraints.violates_text(invalid) is not None
    block = next(b for s in revision.form_layouts[0].pages[0].sections for b in s.blocks if b.id == str(casilla.id))
    assert isinstance(block, FormFieldBlock)
    assert [choice.value for choice in block.choices] == ["C ", " S"]
    # A presentation option must be backed by the owning field's actual domain.
    changed = casilla.model_copy(update={"constraints": casilla.constraints.model_copy(update={"enum": ("C ",)})})
    invalid = revision.model_copy(
        update={"casillas": tuple(changed if c.id == casilla.id else c for c in revision.casillas)}
    )
    assert any("outside its casilla domain" in failure for failure in form_layout_failures(invalid))


def test_prior_receipt_rules_use_the_exact_amendment_values() -> None:
    from decimal import Decimal

    from cadrumo.domain.calculations.registry.schema_verification import parse_verification_predicate_expression

    revision = load_modelo_directory(_ROOT / "registry/aeat/modelos/156").revisions["2003-y-siguientes"]
    predicates = revision.verification_predicates
    assert len(predicates) == 3
    assert all(p.finding_kind.value == "BLOCKING_RULE" for p in predicates)
    parsed = [parse_verification_predicate_expression(p.expression) for p in predicates]
    assert all(
        p is not None and p.casilla_ids == ("declaracion-complementaria-sustitutiva", "numero-identificativo-anterior")
        for p in parsed
    )
    assert {p.literal for p in parsed if p is not None} == {"C ", " S", "  "}
    receipt = next(c for c in revision.casillas if c.id == "numero-identificativo-anterior")
    assert receipt.constraints is not None
    assert receipt.constraints.violates(Decimal("-1")) is not None
    assert receipt.constraints.violates(Decimal("10000000000000")) is not None
    assert receipt.constraints.violates(Decimal("1560000000001")) is None


def test_amendment_receipt_requirements_are_grounded_in_enrolled_record_design() -> None:
    pdf = _ROOT / "corpus/aeat_official/disenos_registro/modelo_156/files/01-156-diseno-de-registro-vigente.pdf"
    assert sha256(pdf.read_bytes()).hexdigest() == "d387cfeb7254e49d539d5c3a731c0bd6bf275c8c1fdae80e6faa5a1006d5d068"
    declarant, _ = extract_record_design(pdf).require_complete()
    fields = {field.offset: field for field in declarant.fields}
    amendment, receipt = fields[121], fields[123]
    assert amendment.length == 2 and receipt.length == 13
    assert amendment.content is not None and receipt.content is not None
    assert "121 DECLARACIÓN COMPLEMENTARIA" in amendment.content
    assert "122 DECLARACIÓN SUSTITUTIVA" in amendment.content
    assert "una única declaración anterior" in amendment.content
    assert "declaración a la que sustituye o complementa" in receipt.content
    # Preserve the separate ordinary-declaration requirement in the evidence:
    # the implemented nonzero implications alone do not establish this rule.
    assert "En cualquier otro caso deberá rellenarse a CEROS" in receipt.content


def test_member_repeat_requires_an_actual_repeating_export_source() -> None:
    """Presentation alone cannot turn singleton casillas into member records."""
    revision = load_modelo_directory(_ROOT / "registry/aeat/modelos/156").revisions["2003-y-siguientes"]
    revision = revision.model_copy(
        update={
            "export_layouts": tuple(
                export.model_copy(
                    update={
                        "records": tuple(
                            record.model_copy(update={"repeat": None}) if record.id == "modelo-156-afiliado" else record
                            for record in export.records
                        )
                    }
                )
                for export in revision.export_layouts
            )
        }
    )
    layout = revision.form_layouts[0]
    summary, member = layout.pages
    (identity,) = member.sections
    proposed_group = FormRepeatingGroupBlock(
        id="afiliados",
        row_source="export_record",
        export_record_id="modelo-156-afiliado",
        columns=(
            FormRepeatingColumn(
                key="nif",
                heading_key="modelo.schema.156.form.context.nif.heading",
                casilla_id="afiliado-nif",
            ),
        ),
    )
    member = member.model_copy(update={"sections": (identity.model_copy(update={"blocks": (proposed_group,)}),)})
    proposed = revision.model_copy(update={"form_layouts": (layout.model_copy(update={"pages": (summary, member)}),)})
    assert any("which is not a repeating export record" in failure for failure in form_layout_failures(proposed))
