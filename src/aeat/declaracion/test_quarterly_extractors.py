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
    def test_registry_lists_all_shipped_modelos(self) -> None:
        from ._extractors import _REGISTRY

        keys = set(_REGISTRY.keys())
        # Core quarterly-cadence modelos.
        assert ("111", 2025, "2025.01") in keys
        assert ("115", 2025, "2025.01") in keys
        assert ("130", 2025, "2025.01") in keys
        assert ("303", 2025, "2025.01") in keys
        # Modelo 303 post-HAC/819/2024 revision.
        assert ("303", 2024, "2024.orden-819") in keys
        # Annual informative filings.
        assert ("180", 2025, "2025.01") in keys
        assert ("190", 2025, "2025.01") in keys
        assert ("347", 2025, "2025.01") in keys
        assert ("390", 2025, "2025.01") in keys


_MODELO_180_LABELS = {
    "01": "Total perceptores",
    "02": "Total base retencion",
    "03": "Total retenciones",
    "04": "Total ingresos a cuenta",
}

_MODELO_190_LABELS = {f"{i:02d}": f"Casilla {i}" for i in range(1, 22)}

_MODELO_347_LABELS = {
    "01": "Nº total declarados",
    "02": "Importe total operaciones",
    "03": "Nº registros cobros efectivo",
    "04": "Importe cobros efectivo",
}

_MODELO_390_LABELS = {
    "01": "Regimen general 1T base",
    "04": "Regimen general 1T cuota",
    "95": "Total bases imponibles",
    "96": "Total cuotas repercutidas",
    "100": "Total IVA deducible interior",
    "101": "Total IVA deducible importaciones",
    "104": "Total IVA soportado",
    "105": "Resultado regimen general",
    "108": "Resultado simplificado",
    "109": "Otros regimenes",
    "190": "Suma resultado",
    "191": "Cuota resultante anual",
    "192": "Total a ingresar",
    "193": "Total a devolver",
    "662": "Regularizacion bienes inversion",
}


def _make_annual_pdf(
    tmp_path: Path,
    *,
    modelo: str,
    labels: Mapping[str, str],
    values: Mapping[str, str],
    filename: str,
    template_revision: str = "2025.01",
    año: int = 2025,
    ejercicio: str = "2025",
    period_printed: str = "0A",
) -> Path:
    from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
        QuarterlyGenParams,
        generate,
    )

    params = QuarterlyGenParams(
        modelo=modelo,
        año=año,
        template_revision=template_revision,
        tax_id="00000000T",
        ejercicio=ejercicio,
        period_printed=period_printed,
        labels=labels,
        casilla_values={k: Decimal(v) for k, v in values.items()},
    )
    pdf_bytes, _ = generate(params)
    path = tmp_path / filename
    path.write_bytes(pdf_bytes)
    return path


class TestModelo180V2025Extractor:
    def test_roundtrip_annual_summary(self, tmp_path: Path) -> None:
        values = {"01": "5.00", "02": "48000.00", "03": "9120.00", "04": "0.00"}
        pdf = _make_annual_pdf(
            tmp_path,
            modelo="180",
            labels=_MODELO_180_LABELS,
            values=values,
            filename="modelo_180_2025.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "180"
        assert filing.period == "2025A"
        assert filing.extraction_status is ExtractionStatus.COMPLETE
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw)


class TestModelo190V2025Extractor:
    def test_roundtrip_21_casillas(self, tmp_path: Path) -> None:
        values = {k: f"{100 * i}.00" for i, k in enumerate(_MODELO_190_LABELS, start=1)}
        pdf = _make_annual_pdf(
            tmp_path,
            modelo="190",
            labels=_MODELO_190_LABELS,
            values=values,
            filename="modelo_190_2025.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "190"
        assert filing.period == "2025A"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestModelo347V2025Extractor:
    def test_roundtrip_summary(self, tmp_path: Path) -> None:
        values = {
            "01": "12.00",
            "02": "56000.00",
            "03": "3.00",
            "04": "5000.00",
        }
        pdf = _make_annual_pdf(
            tmp_path,
            modelo="347",
            labels=_MODELO_347_LABELS,
            values=values,
            filename="modelo_347_2025.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "347"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestModelo390V2025Extractor:
    def test_roundtrip_annual_summary(self, tmp_path: Path) -> None:
        values = {k: f"{100 * (i + 1)}.00" for i, k in enumerate(_MODELO_390_LABELS)}
        pdf = _make_annual_pdf(
            tmp_path,
            modelo="390",
            labels=_MODELO_390_LABELS,
            values=values,
            filename="modelo_390_2025.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "390"
        # 390 MVP covers 15 of the form's ~680 casillas; extraction ends as
        # COMPLETE because every "required" casilla (the 15 MVP targets) is
        # resolved by the synthetic.
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestModelo303PostHAC819Extractor:
    def test_override_routes_to_2024_orden_819(self, tmp_path: Path) -> None:
        """Explicit --template-revision override dispatches to the post-HAC extractor."""
        values = {
            k: "100.00"
            for k in (
                "01",
                "03",
                "04",
                "06",
                "07",
                "09",
                "28",
                "29",
                "30",
                "31",
                "32",
                "33",
                "44",
                "45",
                "64",
                "65",
                "66",
                "67",
                "69",
                "71",
            )
        }
        labels = {k: f"Casilla {k}" for k in values}
        pdf = _make_annual_pdf(
            tmp_path,
            modelo="303",
            labels=labels,
            values=values,
            filename="modelo_303_2024Q3_orden819.pdf",
            template_revision="2024.orden-819",
            año=2024,
            ejercicio="2024",
            period_printed="3T",
        )
        filing = parse_declaracion(
            pdf,
            modelo_override="303",
            año_override=2024,
            template_revision_override="2024.orden-819",
        )
        assert filing.modelo == "303"
        assert filing.period == "2024Q3"
        assert filing.template_revision.revision == "2024.orden-819"
        # 20 of 33 casillas provided → PARTIAL.
        assert filing.extraction_status is ExtractionStatus.PARTIAL
