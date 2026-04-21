"""Round-trip tests for the quarterly-modelo extractors (#305)."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from . import ExtractionStatus, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_financial_input,
    pytest.mark.fixture_tier_l3,
]


_MODELO_111_LABELS: Mapping[str, str] = {
    "01": "Rendimientos del trabajo - perceptores",
    "02": "Rendimientos del trabajo - percepciones",
    "03": "Rendimientos del trabajo - retenciones",
    "04": "Actividades economicas - perceptores",
    "05": "Actividades economicas - percepciones",
    "06": "Actividades economicas - retenciones",
    "07": "Premios - perceptores",
    "08": "Premios - percepciones",
    "09": "Premios - retenciones",
    "10": "Ganancias patrimoniales - perceptores",
    "11": "Ganancias patrimoniales - percepciones",
    "12": "Ganancias patrimoniales - retenciones",
    "13": "Contraprestaciones en especie - perceptores",
    "14": "Contraprestaciones en especie - percepciones",
    "15": "Contraprestaciones en especie - retenciones",
    "16": "Cesion de imagen - perceptores",
    "17": "Cesion de imagen - percepciones",
    "18": "Cesion de imagen - retenciones",
    "28": "Total ingresos a cuenta",
    "29": "Resultados negativos anteriores",
    "30": "Resultado a ingresar",
}

_MODELO_115_LABELS: Mapping[str, str] = {
    "01": "Numero de arrendadores",
    "02": "Base de retencion",
    "03": "Retenciones",
    "04": "Ingresos a cuenta",
    "05": "Resultados negativos anteriores",
    "06": "Resultado a ingresar",
}


def _make_pdf(
    tmp_path: Path,
    *,
    modelo: str,
    labels: Mapping[str, str],
    values: Mapping[str, str],
    filename: str,
) -> Path:
    from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
        QuarterlyGenParams,
        generate,
    )

    params = QuarterlyGenParams(
        modelo=modelo,
        año=2025,
        template_revision="2025.01",
        tax_id="00000000T",
        ejercicio="2025",
        period_printed="1T",
        labels=labels,
        casilla_values={k: Decimal(v) for k, v in values.items()},
        csv="ABCD1234EFGH5678",
    )
    pdf_bytes, _ = generate(params)
    path = tmp_path / filename
    path.write_bytes(pdf_bytes)
    return path


class TestModelo111V2025Extractor:
    def test_roundtrip_all_21_casillas(self, tmp_path: Path) -> None:
        values = {k: f"{100 * i + 50}.00" for i, k in enumerate(_MODELO_111_LABELS, start=1)}
        pdf = _make_pdf(
            tmp_path,
            modelo="111",
            labels=_MODELO_111_LABELS,
            values=values,
            filename="modelo_111_2025Q1.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "111"
        assert filing.period == "2025Q1"
        assert filing.extraction_status is ExtractionStatus.COMPLETE
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw)

    def test_partial_extraction_emits_warnings(self, tmp_path: Path) -> None:
        sparse = {k: "1.00" for k in list(_MODELO_111_LABELS)[:11]}
        pdf = _make_pdf(
            tmp_path,
            modelo="111",
            labels=_MODELO_111_LABELS,
            values=sparse,
            filename="modelo_111_partial.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.extraction_status in {ExtractionStatus.PARTIAL, ExtractionStatus.FAILED}
        assert len(filing.warnings) >= 10


class TestModelo115V2025Extractor:
    def test_roundtrip_all_6_casillas(self, tmp_path: Path) -> None:
        values = {
            "01": "2.00",
            "02": "12000.00",
            "03": "2280.00",
            "04": "0.00",
            "05": "0.00",
            "06": "2280.00",
        }
        pdf = _make_pdf(
            tmp_path,
            modelo="115",
            labels=_MODELO_115_LABELS,
            values=values,
            filename="modelo_115_2025Q1.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "115"
        assert filing.extraction_status is ExtractionStatus.COMPLETE
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw)


class TestRegistryKnowsNewExtractors:
    def test_registry_lists_new_modelos(self) -> None:
        from ._extractors import _REGISTRY

        keys = set(_REGISTRY.keys())
        assert ("111", 2025, "2025.01") in keys
        assert ("115", 2025, "2025.01") in keys
        assert ("130", 2025, "2025.01") in keys
        assert ("303", 2025, "2025.01") in keys
