"""End-to-end tests for :class:`aeat.adapters.inbound.schema.BoeOrdenExtractor`.

The synthetic fixture PDF is generated with :mod:`reportlab` â€” the
same pattern as :mod:`aeat.justificante.test_parser`. It mimics the
BOE Orden annex layout the extractor pattern library targets; it is
NOT a real BOE document, and a live probe against the real
BOE-published Orden HAC/665/2023 is tracked as a follow-up.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....domain.modelos import ModeloCode
from ....domain.schema import (
    BinaryFormulaOp,
    BinaryOp,
    CasillaDataType,
    SchemaCasillaRef,
    LiteralFormula,
    SchemaExtractionError,
    SchemaSource,
    evaluate,
)
from . import BoeOrdenExtractor, FetchedSchemaSource
from .testing import build_synthetic_boe_pdf

pytestmark = [pytest.mark.unit, pytest.mark.domain_inbound]

_ANNEX_LINES: tuple[str, ...] = (
    "# Rendimiento de la actividad",
    "01 Base imponible 1T",
    "03 Ingresos computables 1T",
    "07 Rendimiento neto 1T",
    "13 Pago fraccionado 1T",
    "Casilla 07 = Casilla 01 - Casilla 03",
    "Casilla 13 = Casilla 07 x 0,20",
)
_PREAMBLE_LINES: tuple[str, ...] = (
    "Orden HAC/665/2023, de 12 de junio",
    "Ministerio de Hacienda y Funcion Publica",
)


def _build_source(pdf_path: Path) -> FetchedSchemaSource:
    pdf_bytes = pdf_path.read_bytes()
    return FetchedSchemaSource(
        modelo_code=ModeloCode.MODELO_130,
        boe_ref="BOE-A-SYNTHETIC",
        origin_url=TypeAdapter(AnyHttpUrl).validate_python("https://www.boe.es/synthetic.pdf"),
        pdf_path=pdf_path,
        sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        content_length=len(pdf_bytes),
        fetched_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
    )


@pytest.fixture
def boe_pdf_fixture(tmp_path: Path) -> Path:
    """Write a synthetic BOE-shaped PDF under ``tmp_path`` and return its path."""
    path = tmp_path / "boe.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=_ANNEX_LINES,
        preamble_lines=_PREAMBLE_LINES,
    )
    return path


def test_extractor_rejects_source_with_mismatched_modelo(boe_pdf_fixture: Path) -> None:
    source = _build_source(boe_pdf_fixture)
    with pytest.raises(SchemaExtractionError):
        BoeOrdenExtractor(
            source=source,
            modelo_code=ModeloCode.MODELO_303,
            period="2025Q4",
        )


def test_extractor_happy_path(boe_pdf_fixture: Path) -> None:
    source = _build_source(boe_pdf_fixture)
    extractor = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    )
    modelo = extractor.extract()

    assert modelo.modelo_code is ModeloCode.MODELO_130
    assert modelo.period == "2025Q4"
    assert modelo.provenance.source is SchemaSource.BOE_ORDEN
    assert modelo.provenance.document_ref == "BOE-A-SYNTHETIC"
    assert modelo.provenance.sha256 == source.sha256

    by_id = {c.casilla_id: c for c in modelo.casillas}
    assert set(by_id) == {"01", "03", "07", "13"}

    casilla_01 = by_id["01"]
    assert casilla_01.formula is None
    assert casilla_01.required is True
    assert casilla_01.computed is False
    assert casilla_01.data_type is CasillaDataType.CURRENCY_EUR
    assert casilla_01.label["es"] == "Base imponible 1T"
    assert casilla_01.block is not None
    assert casilla_01.block["es"] == "Rendimiento de la actividad"
    assert casilla_01.source_page is not None
    assert casilla_01.source_page >= 1

    casilla_07 = by_id["07"]
    assert casilla_07.computed is True
    assert isinstance(casilla_07.formula, BinaryOp)
    assert casilla_07.formula.op is BinaryFormulaOp.SUB
    assert isinstance(casilla_07.formula.left, SchemaCasillaRef)
    assert casilla_07.formula.left.casilla_id == "01"
    assert isinstance(casilla_07.formula.right, SchemaCasillaRef)
    assert casilla_07.formula.right.casilla_id == "03"
    assert set(casilla_07.references_casillas) == {"01", "03"}

    casilla_13 = by_id["13"]
    assert casilla_13.computed is True
    assert isinstance(casilla_13.formula, BinaryOp)
    assert casilla_13.formula.op is BinaryFormulaOp.MUL
    assert isinstance(casilla_13.formula.right, LiteralFormula)
    assert casilla_13.formula.right.value == Decimal("0.20")

    result = evaluate(
        casilla_13.formula,
        {"07": Decimal("600.00")},
    )
    assert result == Decimal("120")


def test_extractor_raises_on_missing_annex(tmp_path: Path) -> None:
    # build_synthetic_boe_pdf always injects "ANEXO I"; to simulate a doc
    # without an annex we write a PDF directly via reportlab that
    # contains no heading and no casilla lines.
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path = tmp_path / "no-annex.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawString(72, 720, "Documento sin anexo")
    pdf.showPage()
    pdf.save()

    source = _build_source(path)
    extractor = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    )
    with pytest.raises(SchemaExtractionError):
        extractor.extract()


def test_extractor_collects_same_page_annex_content(tmp_path: Path) -> None:
    """Regression: lines after the ANEXO heading on the same page must be parsed."""
    path = tmp_path / "same-page.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=_ANNEX_LINES,
        preamble_lines=_PREAMBLE_LINES,
        same_page_layout=True,
    )
    source = _build_source(path)
    extractor = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    )
    modelo = extractor.extract()
    assert {c.casilla_id for c in modelo.casillas} == {"01", "03", "07", "13"}


def test_extractor_mixed_plus_minus_chain(tmp_path: Path) -> None:
    """Mixed +/- chains are preserved as a signed SumFormula."""
    from ....domain.schema import BinaryFormulaOp as _BinaryFormulaOp
    from ....domain.schema import BinaryOp as _BinaryOp
    from ....domain.schema import SchemaCasillaRef as _SchemaCasillaRef
    from ....domain.schema import SumFormula as _SumFormula

    path = tmp_path / "mixed.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            "01 Base imponible 1T",
            "03 Ingresos computables 1T",
            "07 Gastos deducibles 1T",
            "13 Rendimiento neto 1T",
            "Casilla 13 = Casilla 01 + Casilla 03 \u2212 Casilla 07",
        ),
    )
    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    by_id = {c.casilla_id: c for c in modelo.casillas}
    formula = by_id["13"].formula
    assert isinstance(formula, _SumFormula)
    assert len(formula.terms) == 3
    assert isinstance(formula.terms[0], _SchemaCasillaRef)
    assert isinstance(formula.terms[1], _SchemaCasillaRef)
    assert isinstance(formula.terms[2], _BinaryOp)
    assert formula.terms[2].op == _BinaryFormulaOp.SUB


def test_guess_data_type_respects_word_boundaries(tmp_path: Path) -> None:
    """A currency label with 'ejercicios' stays currency, not integer."""
    path = tmp_path / "boundary.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=("11 Cuota a compensar de ejercicios anteriores",),
    )
    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    assert modelo.casillas[0].data_type is CasillaDataType.CURRENCY_EUR


def test_extractor_tolerates_trailing_punctuation(tmp_path: Path) -> None:
    """Formula bodies ending in `.` or `;` (BOE prose punctuation) still parse."""
    path = tmp_path / "trailing-punct.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            "01 Base imponible 1T",
            "03 Ingresos computables 1T",
            "07 Rendimiento neto 1T",
            "Casilla 07 = Casilla 01 - Casilla 03.",
        ),
    )
    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    casilla_07 = next(c for c in modelo.casillas if c.casilla_id == "07")
    assert isinstance(casilla_07.formula, BinaryOp)
    assert casilla_07.formula.op == BinaryFormulaOp.SUB


def test_extractor_accepts_interrogative_and_parenthesised_labels(tmp_path: Path) -> None:
    """Labels starting with `Â¿` or `(` are still recognised as casilla declarations."""
    path = tmp_path / "interrogative.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            "15 Â¿Ha obtenido rendimientos en el extranjero?",
            "21 (Antes: Casilla 9a) Rendimientos del trabajo",
        ),
    )
    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    ids = {c.casilla_id for c in modelo.casillas}
    assert ids == {"15", "21"}


def test_extractor_handles_four_digit_casilla_ids(tmp_path: Path) -> None:
    """4-digit casilla IDs (legitimate on Modelo 390) parse correctly."""
    path = tmp_path / "four-digit.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            "0001 Ejercicio de referencia",
            "1000 Base imponible al 4% anual",
            "1001 Cuota devengada anual al 4%",
            "Casilla 1001 = Casilla 1000 x 0,04",
        ),
    )
    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    ids = {c.casilla_id for c in modelo.casillas}
    assert ids == {"0001", "1000", "1001"}
    casilla_1001 = next(c for c in modelo.casillas if c.casilla_id == "1001")
    assert isinstance(casilla_1001.formula, BinaryOp)
    assert casilla_1001.formula.op == BinaryFormulaOp.MUL


def test_extractor_handles_compact_anexo_same_line(tmp_path: Path) -> None:
    """``ANEXO I 01 Base imponible`` on one line â€” the post-heading content is kept."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path = tmp_path / "compact.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica", 10)
    # Heading + first casilla on the same physical line.
    pdf.drawString(72, 720, "ANEXO I 01 Base imponible 1T")
    pdf.drawString(72, 700, "03 Ingresos computables 1T")
    pdf.showPage()
    pdf.save()

    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    ids = {c.casilla_id for c in modelo.casillas}
    assert ids == {"01", "03"}


def test_extractor_tolerates_identical_duplicate_declarations(tmp_path: Path) -> None:
    """Benign repeated layouts (multilingual annex, summary page) are ignored."""
    path = tmp_path / "dup.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            "01 Base imponible 1T",
            "03 Ingresos computables 1T",
            # Repeated layout further down the annex.
            "01 Base imponible 1T",
            "03 Ingresos computables 1T",
        ),
    )
    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    ids = [c.casilla_id for c in modelo.casillas]
    assert ids == ["01", "03"]


def test_extractor_rejects_conflicting_duplicate_declarations(tmp_path: Path) -> None:
    """A second declaration with a different label raises, not silently wins."""
    path = tmp_path / "conflict.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            "01 Base imponible 1T",
            "01 Otro valor inesperado",
        ),
    )
    source = _build_source(path)
    with pytest.raises(SchemaExtractionError, match="conflicting duplicate"):
        BoeOrdenExtractor(
            source=source,
            modelo_code=ModeloCode.MODELO_130,
            period="2025Q4",
        ).extract()


def test_extractor_accepts_formula_before_declaration(tmp_path: Path) -> None:
    """Two-pass parser allows a formula to appear before its casilla declaration."""
    path = tmp_path / "out-of-order.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            # Formula appears first â€” column-layout PDFs sometimes do this.
            "Casilla 07 = Casilla 01 - Casilla 03",
            "01 Base imponible 1T",
            "03 Ingresos computables 1T",
            "07 Rendimiento neto 1T",
        ),
    )
    source = _build_source(path)
    modelo = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    ).extract()
    casilla_07 = next(c for c in modelo.casillas if c.casilla_id == "07")
    assert isinstance(casilla_07.formula, BinaryOp)
    assert casilla_07.formula.op == BinaryFormulaOp.SUB


def test_extractor_raises_on_unparseable_formula(tmp_path: Path) -> None:
    path = tmp_path / "bad-formula.pdf"
    build_synthetic_boe_pdf(
        path,
        annex_lines=(
            "01 Base imponible",
            "Casilla 01 = elevar al cuadrado",
        ),
    )
    source = _build_source(path)
    extractor = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    )
    with pytest.raises(SchemaExtractionError):
        extractor.extract()
