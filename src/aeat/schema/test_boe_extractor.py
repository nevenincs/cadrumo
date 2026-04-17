"""End-to-end tests for :class:`aeat.schema.BoeOrdenExtractor`.

The synthetic fixture PDF is generated with :mod:`reportlab` — the
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

from ..models import ModeloCode
from . import (
    BinaryFormulaOp,
    BinaryOp,
    BoeOrdenExtractor,
    CasillaDataType,
    CasillaRef,
    FetchedSchemaSource,
    LiteralFormula,
    SchemaExtractionError,
    SchemaSource,
    evaluate,
)
from .testing import build_fake_boe_pdf

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

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
        boe_ref="BOE-A-FAKE",
        origin_url=TypeAdapter(AnyHttpUrl).validate_python("https://www.boe.es/fake.pdf"),
        pdf_path=pdf_path,
        sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        content_length=len(pdf_bytes),
        fetched_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
    )


@pytest.fixture
def fake_boe_pdf(tmp_path: Path) -> Path:
    """Write a synthetic BOE-shaped PDF under ``tmp_path`` and return its path."""
    path = tmp_path / "boe.pdf"
    build_fake_boe_pdf(
        path,
        annex_lines=_ANNEX_LINES,
        preamble_lines=_PREAMBLE_LINES,
    )
    return path


def test_extractor_rejects_source_with_mismatched_modelo(fake_boe_pdf: Path) -> None:
    source = _build_source(fake_boe_pdf)
    with pytest.raises(SchemaExtractionError):
        BoeOrdenExtractor(
            source=source,
            modelo_code=ModeloCode.MODELO_303,
            period="2025Q4",
        )


def test_extractor_happy_path(fake_boe_pdf: Path) -> None:
    source = _build_source(fake_boe_pdf)
    extractor = BoeOrdenExtractor(
        source=source,
        modelo_code=ModeloCode.MODELO_130,
        period="2025Q4",
    )
    modelo = extractor.extract()

    assert modelo.modelo_code is ModeloCode.MODELO_130
    assert modelo.period == "2025Q4"
    assert modelo.provenance.source is SchemaSource.BOE_ORDEN
    assert modelo.provenance.document_ref == "BOE-A-FAKE"
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
    assert isinstance(casilla_07.formula.left, CasillaRef)
    assert casilla_07.formula.left.casilla_id == "01"
    assert isinstance(casilla_07.formula.right, CasillaRef)
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
    # build_fake_boe_pdf always injects "ANEXO I"; to simulate a doc
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


def test_extractor_raises_on_unparseable_formula(tmp_path: Path) -> None:
    path = tmp_path / "bad-formula.pdf"
    build_fake_boe_pdf(
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
