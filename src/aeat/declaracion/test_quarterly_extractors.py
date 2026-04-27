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
    thousands_sep: str = ".",
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
        thousands_sep=thousands_sep,
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
        assert ("123", 2024, "2024.01") in keys  # issue #320
        assert ("123", 2025, "2025.01") in keys
        assert ("123", 2026, "2026.01") in keys  # issue #320
        assert ("130", 2024, "2024.01") in keys  # issue #321
        assert ("130", 2025, "2025.01") in keys
        assert ("130", 2026, "2026.01") in keys  # issue #321
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
    "00547": "Compensacion BINs periodos anteriores",
    "00550": "Base imponible antes reserva capitalizacion",
    "00552": "Base imponible",
    "00558": "Tipo de gravamen",
    "00560": "Cuota integra previa",
    "00562": "Cuota integra",
    "00582": "Cuota integra ajustada positiva",
    "00592": "Cuota liquida",
    "00599": "Retenciones ingresos cuenta",
    "00601": "Pago fraccionado 1P",
    "00603": "Pago fraccionado 2P",
    "00605": "Pago fraccionado 3P",
    "00615": "Abono de deducciones",
    "00619": "Incremento perdida beneficios fiscales",
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
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw)


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
        # Wave 23 MEDIUM-2 + 4: assert the full five-digit casilla dict —
        # one spot-check is not enough to prove the casilla_width=5 path.
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw), f"Casilla {cid} did not round-trip"


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


_MODELO_840_LABELS = {
    "14": "Ejercicio",
    "15": "Causa presentacion",
    "33": "Clase de cuota",
    "34": "Tipo actividad",
    "37": "Grupo o epigrafe",
    "38": "Municipio",
    "40": "Provincia",
    "62": "Fecha de efectos",
}

_MODELO_840_VALUES = {
    "14": "2025",
    "15": "Alta",
    "33": "Municipal",
    "34": "Profesional",
    "37": "722",
    "38": "Madrid",
    "40": "Madrid",
    "62": "2025-04-21",
}


class TestSoftHyphenLineBreakNormalisation:
    """Wave 51 H2: `_normalise_pdf_text` stitches hyphenated labels."""

    def test_hyphen_newline_stitched_before_regex(self) -> None:
        """A label broken across a line by `-\\n` re-stitches so the
        label-anchored regex still matches."""
        from ._generic_extractor import _normalise_pdf_text

        # Input as pdfplumber would emit on a narrow AEAT column:
        raw = "01 Reten-\nciones 1.234,56"
        normalised = _normalise_pdf_text(raw)
        # The hyphen-newline pair is gone; the label is one word.
        assert "Retenciones" in normalised
        assert "-\n" not in normalised

    def test_bullet_leading_dash_not_stitched(self) -> None:
        """Wave 56 M1: a line that starts with `-\\n` (bullet-style) must
        NOT collapse into the following word.

        Pre-wave-56 `_normalise_pdf_text` used a blind
        `.replace("-\\n", "")` which would eat the bullet dash and
        merge it into whatever followed. The narrowed regex now
        requires alphanumeric context on BOTH sides.
        """
        from ._generic_extractor import _normalise_pdf_text

        # Bullet at start of line, nothing to the left of the dash.
        raw = "Lista:\n-\nelemento uno"
        normalised = _normalise_pdf_text(raw)
        # The bullet must survive — no merge into "elemento".
        assert "-\nelemento" in normalised or "-\n" in normalised

    def test_word_boundary_required_on_both_sides(self) -> None:
        """A `-\\n` with whitespace on either side is not a continuation."""
        from ._generic_extractor import _normalise_pdf_text

        raw = "A -\n B"  # space + dash + newline + space: not a word break
        normalised = _normalise_pdf_text(raw)
        # Should remain intact.
        assert "-\n" in normalised

    def test_digit_boundary_not_stitched(self) -> None:
        """Wave 59a H1: digit-boundary hyphen-newline pairs MUST NOT stitch.

        An adversarial wrap like ``9-\\n10`` would collapse to
        ``910`` under the pre-59a `\\w`-based lookaround. The tightened
        letters-only lookaround preserves the original boundary.
        """
        from ._generic_extractor import _normalise_pdf_text

        # Digit-boundary cases — MUST remain intact.
        assert _normalise_pdf_text("9-\n10") == "9-\n10"
        assert _normalise_pdf_text("03-\ntotal") == "03-\ntotal"
        assert _normalise_pdf_text("importe 9-\n10 euros") == "importe 9-\n10 euros"

        # Underscore boundary (part of \w in pre-59a regex) — MUST remain intact.
        assert _normalise_pdf_text("foo_-\n_bar") == "foo_-\n_bar"

    def test_letter_boundary_still_stitches(self) -> None:
        """Wave 59a H1: letter-on-letter hyphen stitching still works."""
        from ._generic_extractor import _normalise_pdf_text

        # ASCII letter boundary — still stitches.
        assert _normalise_pdf_text("Reten-\nciones") == "Retenciones"
        # Unicode letter boundary (á, ñ) — still stitches.
        assert _normalise_pdf_text("actá-\nreo") == "actáreo"
        assert _normalise_pdf_text("españ-\nola") == "española"


class TestGenericExtractorInvariants:
    def test_casilla_and_text_casilla_overlap_rejected(self) -> None:
        from typing import ClassVar

        from ._generic_extractor import GenericDeclaracionExtractor
        from ._schema import TemplateRevision

        with pytest.raises(ValueError, match="disjoint"):

            class _Bad(GenericDeclaracionExtractor):
                template_revision: ClassVar[TemplateRevision] = TemplateRevision(
                    modelo="999", año=2025, revision="2025.01"
                )
                casilla_ids: ClassVar[tuple[str, ...]] = ("01",)
                text_casilla_ids: ClassVar[tuple[str, ...]] = ("01",)

    def test_ambiguous_text_label_primitive_match_count(self) -> None:
        """Duplicate text-value lines surface match_count>1 from apply_label_regex."""
        import re as _re

        from .._pdf_import._label_regex import TEXT_VALUE_GROUP, apply_label_regex

        text = (
            "14 Ejercicio 2025\n"
            "99 Otra cosa 1234\n"
            "14 Ejercicio 2026\n"  # duplicate label → ambiguity
        )
        pattern = _re.compile(
            rf"(?m)^\s*14\s+\S[^\n]{{0,80}}\s{TEXT_VALUE_GROUP}",
            _re.IGNORECASE,
        )
        hits = apply_label_regex(text, {"14": pattern})
        assert hits["14"].match_count == 2
        assert hits["14"].raw_value == "2025"  # first-hit wins


class TestModelo840TextCasillas:
    """Modelo 840 uses the text-value primitive (wave 24)."""

    def test_truncation_warning_emitted_for_multi_word_value(self, tmp_path: Path) -> None:
        """Wave 29 HIGH-3: multi-word values surface a truncation warning + confidence drop."""
        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
            QuarterlyGenParams,
            generate,
        )

        labels = {"38": "Municipio"}
        # Simulate Kent filing for "Las Palmas" — the naive TEXT_VALUE_GROUP
        # would capture "Palmas" and silently drop "Las"; wave 29 flags it.
        values = {"38": "Las Palmas"}
        params = QuarterlyGenParams(
            modelo="840",
            año=2025,
            template_revision="2025.01",
            tax_id="00000000T",
            ejercicio="2025",
            period_printed="0A",
            labels=labels,
            casilla_values=values,
        )
        pdf_bytes, _ = generate(params)
        pdf = tmp_path / "modelo_840_truncated.pdf"
        pdf.write_bytes(pdf_bytes)
        filing = parse_declaracion(pdf)
        by_id = {v.casilla_id: v for v in filing.values}
        # Last-token capture still wins; but confidence drops to 0.5 and
        # a truncation warning is emitted.
        assert by_id["38"].printed_value == "Palmas"
        assert by_id["38"].extraction_confidence == 0.5
        assert any(w.casilla_id == "38" and w.code == "text-value-possibly-truncated" for w in filing.warnings)

    def test_missing_text_casilla_emits_not_found_warning(self, tmp_path: Path) -> None:
        """Wave 29 MEDIUM-1: a text casilla absent from the PDF surfaces as `casilla-not-found`."""
        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
            QuarterlyGenParams,
            generate,
        )

        # Render 840 with only casilla 14 present; the other 7 are missing.
        labels = {"14": "Ejercicio"}
        values: dict[str, str] = {"14": "2025"}
        params = QuarterlyGenParams(
            modelo="840",
            año=2025,
            template_revision="2025.01",
            tax_id="00000000T",
            ejercicio="2025",
            period_printed="0A",
            labels=labels,
            casilla_values=values,
        )
        pdf_bytes, _ = generate(params)
        pdf = tmp_path / "modelo_840_partial.pdf"
        pdf.write_bytes(pdf_bytes)
        filing = parse_declaracion(pdf)
        missing = {w.casilla_id for w in filing.warnings if w.code == "casilla-not-found"}
        # All text casillas except 14 should be missing.
        assert "15" in missing and "33" in missing and "62" in missing
        # Extraction status degrades (1 of 8 < 50% coverage).
        assert filing.extraction_status is ExtractionStatus.FAILED

    def test_text_payload_roundtrip(self, tmp_path: Path) -> None:
        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
            QuarterlyGenParams,
            generate,
        )

        params = QuarterlyGenParams(
            modelo="840",
            año=2025,
            template_revision="2025.01",
            tax_id="00000000T",
            ejercicio="2025",
            period_printed="0A",
            labels=_MODELO_840_LABELS,
            casilla_values=_MODELO_840_VALUES,
        )
        pdf_bytes, _ = generate(params)
        pdf = tmp_path / "modelo_840_2025.pdf"
        pdf.write_bytes(pdf_bytes)
        filing = parse_declaracion(pdf)
        assert filing.modelo == "840"
        assert filing.extraction_status is ExtractionStatus.COMPLETE
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, expected in _MODELO_840_VALUES.items():
            assert by_id[cid] == expected, f"Casilla {cid}: {by_id.get(cid)!r} != {expected!r}"


def _draw_named_pdf(
    tmp_path: Path,
    *,
    modelo: str,
    period_printed: str,
    lines: list[str],
    filename: str,
) -> Path:
    """Render a bespoke named-field PDF via the generator's shared primitives."""
    import io

    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from tests.fixtures.pdf_corpus.l3_synthetic._generators._generator_shared import (
        A4_HEIGHT,
        A4_WIDTH,
        MARGIN_LEFT,
        MARGIN_TOP,
        VALUE_FONT,
        VALUE_FONT_SIZE,
        draw_footer,
        draw_header,
    )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(A4_WIDTH, A4_HEIGHT))
    c.setTitle(f"Modelo {modelo} 2025")
    draw_header(c, modelo=modelo, ejercicio="2025", periodo=period_printed, page_num=1, page_count=1)
    c.setFont(VALUE_FONT, VALUE_FONT_SIZE)
    y = A4_HEIGHT - MARGIN_TOP - 50 * mm
    for i, line in enumerate(lines):
        c.drawString(MARGIN_LEFT, y - i * 6 * mm, line)
    draw_footer(c, tax_id="00000000T", presented_at="2025-11-20 10:00:00")
    c.showPage()
    c.save()
    path = tmp_path / filename
    path.write_bytes(buffer.getvalue())
    return path


class TestModelo036MultiWordValues:
    """Wave 33 H2: 036 captures multi-word régimen values without truncation."""

    def test_recargo_de_equivalencia_captured_fully(self, tmp_path: Path) -> None:
        pdf = _draw_named_pdf(
            tmp_path,
            modelo="036",
            period_printed="0A",
            lines=[
                "Causa de presentacion: Alta",
                "Regimen especial IVA: Recargo de equivalencia",
                "Regimen estimacion IRPF: Estimacion directa simplificada",
                "Epigrafe IAE: 722",
                "Fecha de efectos: 2025-04-22",
            ],
            filename="modelo_036_multiword.pdf",
        )
        filing = parse_declaracion(pdf)
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        # Pre-fix these were "Recargo" / "Estimacion" (single token).
        assert by_id["regimen_iva"] == "Recargo de equivalencia"
        assert by_id["regimen_irpf"] == "Estimacion directa simplificada"


class TestModelo369SoportadoExclusion:
    """Wave 33 M2: IVA soportado line must NOT match total_cuota_iva (devengada)."""

    def test_soportado_line_rejected(self, tmp_path: Path) -> None:
        pdf = _draw_named_pdf(
            tmp_path,
            modelo="369",
            period_printed="1T",
            lines=[
                "Total bases imponibles    45.200,00",
                "Total cuotas IVA soportado    3.000,00",  # deducible — NOT devengada
                "Total cuotas IVA devengadas    9.492,00",
                "Total a ingresar    6.492,00",
            ],
            filename="modelo_369_soportado.pdf",
        )
        filing = parse_declaracion(pdf)
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        # Must pick the devengada line (9.492), not the soportado line (3.000).
        assert by_id["total_cuota_iva"] == "9.492,00"


class TestModelo369NamedFieldExtraction:
    """Wave 27: Modelo 369 OSS/IOSS summary totals via named-field primitive."""

    def test_roundtrip_summary_totals(self, tmp_path: Path) -> None:
        pdf = _draw_named_pdf(
            tmp_path,
            modelo="369",
            period_printed="1T",
            lines=[
                "Total bases imponibles    45.200,00",
                "Total cuotas IVA    9.492,00",
                "Total a ingresar    9.492,00",
            ],
            filename="modelo_369_named.pdf",
        )
        filing = parse_declaracion(pdf)
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        assert by_id["total_base_imponible"] == "45.200,00"
        assert by_id["total_cuota_iva"] == "9.492,00"
        assert by_id["total_a_ingresar"] == "9.492,00"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestModelo720NamedFieldExtraction:
    """Wave 27: Modelo 720 per-clave counters via named-field primitive."""

    def test_roundtrip_per_clave_counters(self, tmp_path: Path) -> None:
        pdf = _draw_named_pdf(
            tmp_path,
            modelo="720",
            period_printed="0A",
            lines=[
                "Clave C cuentas    3 registros",
                "Clave V valores    2 registros",
                "Clave I inmuebles    1 registros",
            ],
            filename="modelo_720_named.pdf",
        )
        filing = parse_declaracion(pdf)
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        assert by_id["num_registros_cuentas"] == "3"
        assert by_id["num_registros_valores"] == "2"
        assert by_id["num_registros_inmuebles"] == "1"


class TestModelo036NamedFieldExtraction:
    """Wave 27: Modelo 036 censal fields via named-field primitive."""

    def test_roundtrip_censal_fields(self, tmp_path: Path) -> None:
        pdf = _draw_named_pdf(
            tmp_path,
            modelo="036",
            period_printed="0A",
            lines=[
                "Causa de presentacion: Alta",
                "Regimen especial IVA: General",
                "Regimen estimacion IRPF: Directa",
                "Epigrafe IAE: 722",
                "Fecha de efectos: 2025-04-22",
            ],
            filename="modelo_036_named.pdf",
        )
        filing = parse_declaracion(pdf)
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        assert by_id["causa_presentacion"] == "Alta"
        assert by_id["regimen_iva"] == "General"
        assert by_id["regimen_irpf"] == "Directa"
        assert by_id["epigrafe_iae"] == "722"
        assert by_id["fecha_efectos"] == "2025-04-22"


class TestModelo232NamedFieldExtraction:
    """Wave 27: Modelo 232 uses the named-field primitive."""

    def test_roundtrip_named_fields(self, tmp_path: Path) -> None:
        """Render a 232 PDF with the three bloque counters in the synthetic text layer."""
        import io

        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generator_shared import (
            A4_HEIGHT,
            A4_WIDTH,
            MARGIN_LEFT,
            MARGIN_TOP,
            VALUE_FONT,
            VALUE_FONT_SIZE,
            draw_footer,
            draw_header,
        )

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(A4_WIDTH, A4_HEIGHT))
        c.setTitle("Modelo 232 2025")
        draw_header(c, modelo="232", ejercicio="2025", periodo="0A", page_num=1, page_count=1)
        c.setFont(VALUE_FONT, VALUE_FONT_SIZE)
        y = A4_HEIGHT - MARGIN_TOP - 50 * mm
        c.drawString(MARGIN_LEFT, y, "Nº registros vinculadas    12")
        c.drawString(MARGIN_LEFT, y - 6 * mm, "Nº registros intangibles    3")
        c.drawString(MARGIN_LEFT, y - 12 * mm, "Nº registros paraísos    1")
        draw_footer(c, tax_id="00000000T", presented_at="2025-11-20 10:00:00")
        c.showPage()
        c.save()
        pdf = tmp_path / "modelo_232_named.pdf"
        pdf.write_bytes(buffer.getvalue())

        filing = parse_declaracion(pdf)
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        assert by_id["num_registros_vinculadas"] == "12"
        assert by_id["num_registros_intangibles"] == "3"
        assert by_id["num_registros_paraisos"] == "1"
        assert filing.extraction_status is ExtractionStatus.COMPLETE


class TestHeaderOnlyExtractors:
    """Identity / error-branch coverage for extractors with no content primitive.

    Wave 27 migrated all modelos with no numbered-casilla summary
    (036/037/232/369/720/840) onto the text-value or named-field
    primitive, so no modelo remains unconditionally UNVERIFIABLE. This
    class now hosts the missing-NIF error-branch test; the sentinel
    below lets a future regression surface if anyone reintroduces a
    header-only-only extractor.
    """

    def test_no_modelo_remains_unconditionally_header_only(self) -> None:
        """Sentinel: every GenericDeclaracionExtractor subclass has a content primitive.

        Modelo 130 and Modelo 303 (v2025) extend ``DeclaracionExtractor``
        directly with their own bespoke casilla sets — this sentinel
        targets the generic base only, which is the MVP pattern for
        every other modelo.
        """
        from ._extractors import _REGISTRY
        from ._generic_extractor import GenericDeclaracionExtractor

        header_only: list[str] = []
        for (modelo, _a, _r), cls in _REGISTRY.items():
            if not issubclass(cls, GenericDeclaracionExtractor):
                continue
            decimal = getattr(cls, "casilla_ids", ())
            text = getattr(cls, "text_casilla_ids", ())
            named = getattr(cls, "named_field_patterns", {})
            if not decimal and not text and not named:
                header_only.append(modelo)
        assert not header_only, (
            f"These GenericDeclaracionExtractor subclasses still expose no "
            f"content primitive: {header_only}. "
            f"Add casilla_ids, text_casilla_ids, or named_field_patterns."
        )

    def test_header_only_missing_nif_raises(self, tmp_path: Path) -> None:
        """A PDF with no NIF surfaces DeclaracionParseError even for header-only modelos."""
        # Render a Modelo 232 PDF with an empty tax_id — the _TAX_ID_RE regex
        # requires 8+ chars, so an empty id produces no header match.
        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
            QuarterlyGenParams,
            generate,
        )

        from ._errors import DeclaracionParseError

        params = QuarterlyGenParams(
            modelo="232",
            año=2025,
            template_revision="2025.01",
            tax_id="XYZ!",  # 4 chars: passes fixture ≥4 check, fails _TAX_ID_RE ≥8
            ejercicio="2025",
            period_printed="0A",
            labels={},
            casilla_values={},
        )
        pdf_bytes, _ = generate(params)
        pdf = tmp_path / "modelo_232_no_nif.pdf"
        pdf.write_bytes(pdf_bytes)
        with pytest.raises(DeclaracionParseError, match="tax_id"):
            parse_declaracion(pdf)


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


class TestThousandsSeparatorThreading:
    """Wave 61d: thousands_sep plumbing through the synthetic generator.

    Wave 60 H3 claimed the wave-56 ``format_amount(thousands_sep=...)``
    opt-in was never threaded through ``draw_casilla_box`` /
    ``QuarterlyGenParams``. Wave 61d threads it through, and this test
    asserts the param reaches the rendered PDF text stream.

    Scope clarification (wave 61d closure). A parametrized end-to-end
    NBSP round-trip test was prototyped and found infeasible via the
    reportlab synthetic-PDF pipeline: reportlab's Helvetica font lacks
    a U+202F (narrow NBSP) glyph (substituted as literal ``"n"``), and
    pdfplumber silently canonicalises U+00A0 (NBSP) to ASCII space in
    its extracted text — which cannot be safely restitched at the
    normaliser layer without false-positives on label-embedded casilla
    references. Real Sede Electrónica PDFs render through proper
    Unicode-capable fonts and preserve NBSP through the
    pdfplumber-equivalent extraction path, so the wave-51 regex fix
    remains load-bearing in production while this synthetic test is
    limited to the dot-separator + string-layer coverage.
    """

    def test_dot_separator_is_the_canonical_default(self, tmp_path: Path) -> None:
        values = {
            "01": "5.00",
            "02": "12500.00",
            "03": "2625.00",
            "04": "3.00",
            "05": "8750.50",
            "06": "1837.61",
            "28": "4462.61",
            "29": "0.00",
            "30": "4462.61",
        }
        pdf = _make_pdf(
            tmp_path,
            modelo="111",
            labels=_MODELO_111_LABELS,
            values=values,
            filename="modelo_111_2025Q1_dot.pdf",
            thousands_sep=".",
        )
        filing = parse_declaracion(pdf)
        assert filing.modelo == "111"
        assert filing.period == "2025Q1"
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw), f"mismatch on casilla {cid}: expected {raw}, got {by_id[cid]}"

    def test_hyphenated_label_stitched_by_normaliser(self, tmp_path: Path) -> None:
        """Wave 61e H4 closure: end-to-end hyphenation at extractor layer.

        AEAT multi-column templates wrap long labels as
        ``Reten-\\nciones``. The wave-51 / wave-56 / wave-59a
        ``_normalise_pdf_text`` regex stitches letter-hyphen-newline-
        letter boundaries back together. Prior coverage was string-
        transform only; this test renders a synthetic PDF with a real
        wrapped label, streams it through pdfplumber and the
        extractor, and asserts the casilla value is captured.
        """
        import io as _io

        from reportlab.lib.units import mm as _mm
        from reportlab.pdfgen import canvas as _canvas_module
        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generator_shared import (
            A4_HEIGHT,
            LABEL_FONT,
            LABEL_FONT_SIZE,
            MARGIN_LEFT,
            VALUE_FONT,
            VALUE_FONT_SIZE,
        )

        buffer = _io.BytesIO()
        c = _canvas_module.Canvas(buffer, pagesize=(210 * _mm, 297 * _mm))
        # AEAT-style header the extractor expects.
        y_header = A4_HEIGHT - 20 * _mm
        c.setFont(LABEL_FONT, LABEL_FONT_SIZE)
        c.drawString(MARGIN_LEFT, y_header, "AGENCIA TRIBUTARIA")
        c.drawString(MARGIN_LEFT, y_header - 5 * _mm, "Declaracion - Modelo 115 Pagina 1 de 1")
        c.drawString(MARGIN_LEFT, y_header - 10 * _mm, "Ejercicio: 2025   Periodo: 1T")
        # Casilla 03 with a wrapped label: ``Reten-\nciones`` — the
        # label-regex would fail without the letter-hyphen-newline-
        # letter stitching performed by _normalise_pdf_text.
        c.setFont(VALUE_FONT, VALUE_FONT_SIZE)
        # Reportlab y grows upward from the page bottom: y-30mm is ABOVE
        # y-35mm. pdfplumber sorts top-to-bottom, so the resulting text
        # stream is ``"03 Reten-\nciones 2.280,00"`` — exactly the
        # letter-hyphen-newline-letter shape that _SOFT_HYPHEN_BREAK_RE
        # stitches. DO NOT invert these two y offsets.
        c.drawString(15 * _mm, y_header - 30 * _mm, "03 Reten-")
        c.drawString(15 * _mm, y_header - 35 * _mm, "ciones 2.280,00")
        # Footer the extractor needs for NIF / timestamp parsing.
        y_footer = 15 * _mm
        c.setFont(LABEL_FONT, LABEL_FONT_SIZE)
        c.drawString(MARGIN_LEFT, y_footer, "NIF: 00000000T")
        c.drawString(MARGIN_LEFT, y_footer - 4 * _mm, "Fecha y hora: 2025-04-20 10:00:00")
        c.showPage()
        c.save()
        pdf_path = tmp_path / "modelo_115_hyphenated_label.pdf"
        pdf_path.write_bytes(buffer.getvalue())

        filing = parse_declaracion(pdf_path)
        assert filing.modelo == "115"
        assert filing.period == "2025Q1"
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        assert by_id.get("03") == Decimal("2280.00"), (
            f"Hyphenated label ``Reten-\\nciones`` did not stitch: casilla 03 extracted as {by_id.get('03')!r}"
        )

    def test_format_amount_nbsp_matches_spanish_amount_regex(self) -> None:
        """String-layer threading: ``format_amount(thousands_sep="\\xa0")``
        MUST produce NBSP-separated output that ``SPANISH_AMOUNT_GROUP``
        accepts, so the wave-51 regex fix remains exercised at the
        primitive level even though the full PDF round-trip is
        infeasible through reportlab+pdfplumber.

        Wave 63d L4 rename: previously named
        ``test_thousands_sep_reaches_draw_casilla_box`` which implied
        generator-level coverage it did not deliver.
        """
        import re

        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generator_shared import (
            format_amount,
        )

        from .._pdf_import._label_regex import (
            SPANISH_AMOUNT_GROUP,
            parse_spanish_decimal,
        )

        rendered = format_amount(Decimal("12500.00"), thousands_sep="\xa0")
        assert rendered == "12\xa0500,00"

        m = re.search(SPANISH_AMOUNT_GROUP, rendered)
        assert m is not None
        assert parse_spanish_decimal(m.group(1)) == Decimal("12500.00")
