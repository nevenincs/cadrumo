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
        # Censo (header-only MVP).
        assert ("036", 2025, "2025.01") in keys
        assert ("037", 2025, "2025.01") in keys
        # Core quarterly-cadence modelos.
        assert ("111", 2025, "2025.01") in keys
        assert ("115", 2025, "2025.01") in keys
        assert ("123", 2025, "2025.01") in keys
        assert ("130", 2025, "2025.01") in keys
        assert ("131", 2025, "2025.01") in keys
        assert ("200", 2025, "2025.01") in keys
        assert ("202", 2025, "2025.01") in keys
        assert ("232", 2025, "2025.01") in keys
        assert ("303", 2025, "2025.01") in keys
        # Modelo 303 post-HAC/819/2024 revision.
        assert ("303", 2024, "2024.orden-819") in keys
        # Annual informative filings.
        assert ("180", 2025, "2025.01") in keys
        assert ("190", 2025, "2025.01") in keys
        assert ("193", 2025, "2025.01") in keys
        assert ("347", 2025, "2025.01") in keys
        assert ("349", 2025, "2025.01") in keys
        assert ("369", 2025, "2025.01") in keys
        assert ("390", 2025, "2025.01") in keys
        assert ("720", 2025, "2025.01") in keys
        assert ("840", 2025, "2025.01") in keys


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


_MODELO_123_LABELS = {
    "01": "Perceptores dividendos",
    "02": "Perceptores otras rentas",
    "03": "Perceptores total",
    "04": "Base dividendos",
    "05": "Base otras rentas",
    "06": "Base total",
    "07": "Retenciones dividendos",
    "08": "Retenciones otras rentas",
    "09": "Retenciones total",
    "10": "Resultado declaracion anterior",
    "11": "Resultado a ingresar",
}

_MODELO_193_LABELS = {
    "01": "Total perceptores",
    "02": "Base total retenciones",
    "03": "Retenciones totales",
}

_MODELO_349_LABELS = {
    "01": "Total operadores",
    "02": "Importe total operaciones",
    "03": "Operadores con rectificaciones",
    "04": "Importe rectificaciones",
}


class TestModelo123V2025Extractor:
    def test_roundtrip_quarterly_summary(self, tmp_path: Path) -> None:
        values = {
            "01": "1.00",
            "02": "4.00",
            "03": "5.00",
            "04": "1500.00",
            "05": "8000.00",
            "06": "9500.00",
            "07": "285.00",
            "08": "1520.00",
            "09": "1805.00",
            "10": "0.00",
            "11": "1805.00",
        }
        pdf = _make_pdf(
            tmp_path,
            modelo="123",
            labels=_MODELO_123_LABELS,
            values=values,
            filename="modelo_123_2025Q1.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "123"
        assert filing.period == "2025Q1"
        assert filing.extraction_status is ExtractionStatus.COMPLETE
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw)


class TestModelo193V2025Extractor:
    def test_roundtrip_annual_summary(self, tmp_path: Path) -> None:
        values = {"01": "12.00", "02": "45000.00", "03": "8550.00"}
        pdf = _make_annual_pdf(
            tmp_path,
            modelo="193",
            labels=_MODELO_193_LABELS,
            values=values,
            filename="modelo_193_2025.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "193"
        assert filing.period == "2025A"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestModelo349V2025Extractor:
    def test_roundtrip_monthly_summary(self, tmp_path: Path) -> None:
        values = {
            "01": "7.00",
            "02": "36000.00",
            "03": "1.00",
            "04": "-500.00",
        }
        pdf = _make_pdf(
            tmp_path,
            modelo="349",
            labels=_MODELO_349_LABELS,
            values=values,
            filename="modelo_349_2025_01.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "349"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


_MODELO_131_LABELS = {
    "01": "Suma rendimientos netos modulos",
    "02": "Pago fraccionado del trimestre",
    "03": "Volumen ventas sin datos-base",
    "04": "2 por ciento s/casilla 03",
    "05": "Volumen ingresos agricolas",
    "06": "2 por ciento s/casilla 05",
    "07": "Total 02+04+06",
    "08": "Retenciones e ingresos a cuenta",
    "09": "Minoracion rendimientos ano anterior",
    "10": "Resultado 07-08-09",
    "11": "Negativos trimestres anteriores",
    "12": "Deduccion vivienda habitual",
    "13": "Resultado 10-11-12",
    "14": "Deducir declaracion complementaria",
    "15": "Resultado a ingresar",
}

_MODELO_200_LABELS = {
    "00550": "Base imponible previa",
    "01032": "Reduccion reserva capitalizacion",
    "00547": "Compensacion BINs",
    "00552": "Base imponible",
    "00558": "Tipo de gravamen",
    "00560": "Cuota integra previa",
    "00562": "Cuota integra",
    "00582": "Cuota integra ajustada positiva",
    "00592": "Cuota liquida positiva",
    "00599": "Retenciones ingresos cuenta",
    "00601": "Pago fraccionado 1P",
    "00603": "Pago fraccionado 2P",
    "00605": "Pago fraccionado 3P",
    "00611": "Cuota diferencial",
    "00621": "Liquido a ingresar o devolver",
}

_MODELO_202_LABELS = {
    "16": "Base del pago fraccionado",
    "17": "Tipo de gravamen",
    "18": "Cuota integra",
    "27": "Bonificaciones",
    "28": "Retenciones e ingresos a cuenta",
    "30": "Pagos fraccionados anteriores",
    "32": "Resultado",
    "33": "Minimo a ingresar",
    "34": "Cantidad a ingresar",
}


class TestModelo131V2025Extractor:
    def test_roundtrip_quarterly_modulos(self, tmp_path: Path) -> None:
        values = {k: f"{100 * i}.00" for i, k in enumerate(_MODELO_131_LABELS, start=1)}
        pdf = _make_pdf(
            tmp_path,
            modelo="131",
            labels=_MODELO_131_LABELS,
            values=values,
            filename="modelo_131_2025Q1.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "131"
        assert filing.period == "2025Q1"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestModelo200V2025Extractor:
    def test_roundtrip_liquidacion_page_14(self, tmp_path: Path) -> None:
        values = {k: f"{100 * (i + 1)}.00" for i, k in enumerate(_MODELO_200_LABELS)}
        pdf = _make_annual_pdf(
            tmp_path,
            modelo="200",
            labels=_MODELO_200_LABELS,
            values=values,
            filename="modelo_200_2025.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "200"
        assert filing.period == "2025A"
        assert filing.extraction_status is ExtractionStatus.COMPLETE
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        # Spot-check one five-digit casilla survived the wider prefix.
        assert by_id["00552"] == Decimal(values["00552"])


class TestModelo202V2025Extractor:
    def test_roundtrip_installment(self, tmp_path: Path) -> None:
        values = {
            "16": "100000.00",
            "17": "25.00",
            "18": "25000.00",
            "27": "0.00",
            "28": "2500.00",
            "30": "0.00",
            "32": "22500.00",
            "33": "0.00",
            "34": "22500.00",
        }
        pdf = _make_pdf(
            tmp_path,
            modelo="202",
            labels=_MODELO_202_LABELS,
            values=values,
            filename="modelo_202_2025_1P.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "202"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestHeaderOnlyExtractors:
    """232/369/720/840 recognise the document but expose no casillas.

    The numeric-decimal primitive cannot parse their text-value payloads.
    These extractors act as identity probes until a text-value primitive
    lands in sub-EPIC #305-textual-casillas.
    """

    @pytest.mark.parametrize(
        "modelo",
        ["036", "037", "232", "369", "720", "840"],
        ids=["036", "037", "232", "369", "720", "840"],
    )
    def test_header_only_modelo_exposes_empty_casillas(self, tmp_path: Path, modelo: str) -> None:
        pdf = _make_annual_pdf(
            tmp_path,
            modelo=modelo,
            labels={},
            values={},
            filename=f"modelo_{modelo}_2025.pdf",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == modelo
        assert filing.period == "2025A"
        assert len(filing.values) == 0
        # Empty required-set ⇒ reliable_ids ≥ required_set ⇒ COMPLETE.
        # Upstream classifier still flags zero-casilla filings for review.
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
