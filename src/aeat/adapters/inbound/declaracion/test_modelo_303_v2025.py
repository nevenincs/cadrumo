"""Round-trip extractor test against the synthetic Modelo 303 generator."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ..pdf._shared import ExtractedCasilla
from . import (
    DeclaracionFiling,
    ExtractionStatus,
    parse_declaracion,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
    pytest.mark.fixture_tier_l3,
]


_ALL_CASILLAS_HAPPY: dict[str, str] = {
    # Apartado 1 — régimen general
    "01": "10000.00",
    "02": "21.00",
    "03": "2100.00",
    "04": "5000.00",
    "05": "10.00",
    "06": "500.00",
    "07": "2000.00",
    "08": "4.00",
    "09": "80.00",
    # Apartado 2 — operaciones asimiladas + IVA soportado
    "28": "0.00",
    "29": "0.00",
    "30": "500.00",
    "31": "105.00",
    "32": "0.00",
    "33": "0.00",
    "34": "3000.00",
    "35": "630.00",
    "36": "0.00",
    "37": "0.00",
    "38": "500.00",
    "39": "105.00",
    "40": "0.00",
    "41": "0.00",
    "42": "0.00",
    "43": "0.00",
    "44": "840.00",
    "45": "1945.00",
    # Apartado 3 — resultado
    "64": "1945.00",
    "65": "0.00",
    "66": "1945.00",
    "67": "0.00",
    "69": "1945.00",
    "71": "1945.00",
}


def _generate_pdf(
    tmp_path: Path,
    casilla_values: dict[str, str] | None = None,
    *,
    año: int = 2025,
    ejercicio: str = "2025",
    template_revision: str = "2025.01",
) -> Path:
    from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_303_generator import (
        Modelo303GenParams,
        generate,
    )

    values = casilla_values if casilla_values is not None else _ALL_CASILLAS_HAPPY
    params = Modelo303GenParams(
        año=año,
        template_revision=template_revision,
        tax_id="00000000T",
        ejercicio=ejercicio,
        period_printed="1T",
        csv="ZZZZ9999YYYY8888",
        presented_at="2025-04-20 10:00:00",
        casilla_values={k: Decimal(v) for k, v in values.items()},
    )
    pdf_bytes, _ = generate(params)
    path = tmp_path / f"modelo_303_{ejercicio}Q1_synth.pdf"
    path.write_bytes(pdf_bytes)
    return path


def _values_by_id(filing: DeclaracionFiling) -> dict[str, ExtractedCasilla]:
    return {v.casilla_id: v for v in filing.values}


def test_roundtrip_extract_all_33_casillas(tmp_path: Path) -> None:
    pdf_path = _generate_pdf(tmp_path)
    filing = parse_declaracion(pdf_path)

    assert filing.modelo == "303"
    assert filing.period == "2025Q1"
    assert filing.ejercicio == "2025"
    assert filing.tax_id == "00000000T"
    assert filing.extraction_status is ExtractionStatus.COMPLETE

    by_id = _values_by_id(filing)
    for casilla_id, expected_raw in _ALL_CASILLAS_HAPPY.items():
        assert casilla_id in by_id, f"casilla {casilla_id} not extracted"
        assert by_id[casilla_id].printed_value == Decimal(expected_raw)


def test_roundtrip_template_detected_as_303_2025(tmp_path: Path) -> None:
    pdf_path = _generate_pdf(tmp_path)
    filing = parse_declaracion(pdf_path)
    assert filing.template_revision.modelo == "303"
    assert filing.template_revision.año == 2025
    assert filing.template_revision.revision == "2025.01"


def test_roundtrip_template_detected_as_303_2026(tmp_path: Path) -> None:
    pdf_path = _generate_pdf(
        tmp_path,
        año=2026,
        ejercicio="2026",
        template_revision="2026.01",
    )
    filing = parse_declaracion(pdf_path)
    assert filing.template_revision.modelo == "303"
    assert filing.template_revision.año == 2026
    assert filing.template_revision.revision == "2026.01"


def test_partial_extraction_surfaces_warnings(tmp_path: Path) -> None:
    """Dropping 10 casillas leaves 23 of 33 → PARTIAL."""
    sparse = {k: "100.00" for k in list(_ALL_CASILLAS_HAPPY)[:23]}
    pdf_path = _generate_pdf(tmp_path, casilla_values=sparse)
    filing = parse_declaracion(pdf_path)
    assert filing.extraction_status is ExtractionStatus.PARTIAL
    assert len(filing.values) == 23
    assert len(filing.warnings) == 10
