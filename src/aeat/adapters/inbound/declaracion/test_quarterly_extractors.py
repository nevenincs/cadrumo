"""Round-trip tests for the quarterly-cadence modelo extractors.

Drives every shipped Modelo 111 / 115 / 123 / 131 / 200 / 202 / 232 / 369
/ 720 / 840 extractor through the synthetic generator, asserts the
declared casillas survive the PDF round-trip, and exercises the
shared label-regex / text-value / named-field primitives that back
those extractors.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from . import ExtractionStatus, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
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
    """Render a synthetic quarterly modelo PDF and return its on-disk path."""
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
    """Round-trip coverage for the Modelo 111 v2025 extractor."""

    def test_roundtrip_all_21_casillas(self, tmp_path: Path) -> None:
        """Every Modelo 111 casilla survives the synthetic round-trip."""
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
        """Dropping casillas degrades extraction status and emits warnings."""
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
    """Round-trip coverage for the Modelo 115 v2025 extractor."""

    def test_roundtrip_all_6_casillas(self, tmp_path: Path) -> None:
        """All six Modelo 115 casillas round-trip end-to-end."""
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
    """The legacy extractor registry is no longer an authority."""

    def test_registry_dispatch_requires_registry_snapshot(self) -> None:
        """Extractor dispatch refuses legacy Python-registered model tables."""
        from ._errors import NoExtractorRegisteredError
        from ._extractors import get_extractor
        from ._schema import TemplateRevision

        revision = TemplateRevision(modelo="TEST", año=2026, revision="registry-test")
        with pytest.raises(NoExtractorRegisteredError, match="validated registry snapshots"):
            get_extractor(revision)


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
    """Render a synthetic annual modelo PDF and return its on-disk path."""
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
    """Round-trip coverage for the Modelo 180 v2025 extractor."""

    def test_roundtrip_annual_summary(self, tmp_path: Path) -> None:
        """Modelo 180 annual summary casillas round-trip end-to-end."""
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
    """Round-trip coverage for the Modelo 190 v2025 extractor."""

    def test_roundtrip_21_casillas(self, tmp_path: Path) -> None:
        """The 21 Modelo 190 casillas survive the synthetic round-trip."""
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
    """Round-trip coverage for the Modelo 347 v2025 extractor."""

    def test_roundtrip_summary(self, tmp_path: Path) -> None:
        """Modelo 347 summary totals round-trip end-to-end."""
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
    """Round-trip coverage for the Modelo 390 v2025 extractor."""

    def test_roundtrip_annual_summary(self, tmp_path: Path) -> None:
        """The 15 MVP Modelo 390 casillas survive the synthetic round-trip."""
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
    """Round-trip coverage for the Modelo 123 v2025 extractor."""

    def test_roundtrip_quarterly_summary(self, tmp_path: Path) -> None:
        """Modelo 123 quarterly summary casillas round-trip end-to-end."""
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
    """Round-trip coverage for the Modelo 193 v2025 extractor."""

    def test_roundtrip_annual_summary(self, tmp_path: Path) -> None:
        """Modelo 193 annual summary casillas round-trip end-to-end."""
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
    """Round-trip coverage for the Modelo 349 v2025 extractor."""

    def test_roundtrip_monthly_summary(self, tmp_path: Path) -> None:
        """Modelo 349 monthly summary casillas round-trip end-to-end."""
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
    """Round-trip coverage for the Modelo 131 v2025 extractor."""

    def test_roundtrip_quarterly_modulos(self, tmp_path: Path) -> None:
        """Modelo 131 (módulos) quarterly casillas round-trip end-to-end."""
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
    """Round-trip coverage for the Modelo 200 (IS anual) v2025 extractor."""

    def test_roundtrip_liquidacion_page_14(self, tmp_path: Path) -> None:
        """The five-digit Modelo 200 liquidación casillas round-trip end-to-end."""
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
        # Assert the full five-digit casilla dict — one spot-check is
        # not enough to prove the casilla_width=5 path.
        by_id = {v.casilla_id: v.printed_value for v in filing.values}
        for cid, raw in values.items():
            assert by_id[cid] == Decimal(raw), f"Casilla {cid} did not round-trip"


class TestModelo202V2025Extractor:
    """Round-trip coverage for the Modelo 202 (pago fraccionado IS) extractor."""

    def test_roundtrip_installment(self, tmp_path: Path) -> None:
        """A pago-fraccionado installment round-trips end-to-end."""
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
    """``_normalise_pdf_text`` stitches hyphenated labels.

    The normaliser must collapse letter-hyphen-newline-letter
    sequences (which pdfplumber emits on narrow AEAT columns) so the
    label-anchored regexes match, while leaving bullet-style and
    digit-boundary hyphen-newline pairs intact.
    """

    def test_hyphen_newline_stitched_before_regex(self) -> None:
        """A ``-\\n``-broken label re-stitches into a single word."""
        from ._generic_extractor import _normalise_pdf_text

        # Input as pdfplumber would emit on a narrow AEAT column:
        raw = "01 Reten-\nciones 1.234,56"
        normalised = _normalise_pdf_text(raw)
        # The hyphen-newline pair is gone; the label is one word.
        assert "Retenciones" in normalised
        assert "-\n" not in normalised

    def test_bullet_leading_dash_not_stitched(self) -> None:
        """A bullet-style ``-\\n`` must not collapse into the next word.

        A blind ``.replace("-\\n", "")`` would eat the bullet dash
        and merge it into whatever followed. The narrowed regex
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
        """Digit-boundary hyphen-newline pairs must not stitch.

        An adversarial wrap like ``9-\\n10`` would collapse to
        ``910`` under a ``\\w``-based lookaround. The tightened
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
        """Letter-on-letter hyphen stitching still works after the tightening."""
        from ._generic_extractor import _normalise_pdf_text

        # ASCII letter boundary — still stitches.
        assert _normalise_pdf_text("Reten-\nciones") == "Retenciones"
        # Unicode letter boundary (á, ñ) — still stitches.
        assert _normalise_pdf_text("actá-\nreo") == "actáreo"
        assert _normalise_pdf_text("españ-\nola") == "española"


class TestGenericExtractorInvariants:
    """Subclassing invariants enforced by :class:`GenericDeclaracionExtractor`."""

    def test_casilla_and_text_casilla_overlap_rejected(self) -> None:
        """A subclass that overlaps decimal and text casilla ids is rejected."""
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
        """Duplicate text-value lines surface ``match_count>1`` from ``apply_label_regex``."""
        import re as _re

        from ..pdf._label_regex import TEXT_VALUE_GROUP, apply_label_regex

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
    """Modelo 840 uses the text-value primitive for non-numeric casillas."""

    def test_truncation_warning_emitted_for_multi_word_value(self, tmp_path: Path) -> None:
        """Multi-word values surface a truncation warning and confidence drop."""
        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
            QuarterlyGenParams,
            generate,
        )

        labels = {"38": "Municipio"}
        # Simulate a filing for "Las Palmas" — the naive
        # TEXT_VALUE_GROUP would capture "Palmas" and silently drop
        # "Las".
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
        """A text casilla absent from the PDF surfaces as ``casilla-not-found``."""
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
        """Every Modelo 840 text-value casilla round-trips end-to-end."""
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
    """Render a bespoke named-field PDF via the generator's shared primitives.

    Args:
        tmp_path: Temporary directory pytest provides for the test.
        modelo: Modelo code printed in the PDF header.
        period_printed: Period token printed in the header
            (e.g., ``0A`` or ``1T``).
        lines: Free-form text lines to draw below the header.
        filename: Target filename within ``tmp_path``.

    Returns:
        Filesystem path of the freshly written PDF.
    """
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
    """Modelo 036 captures multi-word régimen values without truncation."""

    def test_recargo_de_equivalencia_captured_fully(self, tmp_path: Path) -> None:
        """Regimen-special values such as ``Recargo de equivalencia`` survive intact."""
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
    """The IVA soportado line must not match ``total_cuota_iva`` (devengada)."""

    def test_soportado_line_rejected(self, tmp_path: Path) -> None:
        """The devengada line wins over the soportado line in ``total_cuota_iva``."""
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
    """Modelo 369 OSS/IOSS summary totals via the named-field primitive."""

    def test_roundtrip_summary_totals(self, tmp_path: Path) -> None:
        """The Modelo 369 summary totals round-trip end-to-end."""
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
    """Modelo 720 per-clave counters via the named-field primitive."""

    def test_roundtrip_per_clave_counters(self, tmp_path: Path) -> None:
        """The per-clave counters (cuentas / valores / inmuebles) round-trip end-to-end."""
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
    """Modelo 036 censal fields via the named-field primitive."""

    def test_roundtrip_censal_fields(self, tmp_path: Path) -> None:
        """The Modelo 036 censal named fields round-trip end-to-end."""
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
    """Modelo 232 uses the named-field primitive for bloque counters."""

    def test_roundtrip_named_fields(self, tmp_path: Path) -> None:
        """Render a 232 PDF with three bloque counters and assert the round-trip."""
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
    """Identity and error-branch coverage for header-only extractor families.

    Every modelo with no numbered-casilla summary (036 / 037 / 232 /
    369 / 720 / 840) is wired onto either the text-value or
    named-field primitive so no modelo remains unconditionally
    ``UNVERIFIABLE``. This class hosts the missing-NIF error-branch
    test plus a sentinel that fires if a contributor reintroduces a
    header-only extractor.
    """

    def test_no_modelo_remains_unconditionally_header_only(self) -> None:
        """Legacy header-only registry inspection is disabled."""
        from . import DeclaracionParseError, registered_extractors

        with pytest.raises(DeclaracionParseError, match="validated registry snapshots"):
            registered_extractors()

    def test_header_only_missing_nif_raises(self, tmp_path: Path) -> None:
        """A PDF with no NIF raises :exc:`DeclaracionParseError` even for header-only modelos."""
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
    """Routing for the Modelo 303 post-HAC/819/2024 revision."""

    def test_override_routes_to_2024_orden_819(self, tmp_path: Path) -> None:
        """An explicit ``--template-revision`` override dispatches to the post-HAC extractor."""
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
    """``thousands_sep`` plumbing through the synthetic generator.

    Asserts that ``format_amount(thousands_sep=...)`` reaches the
    rendered PDF text stream via ``draw_casilla_box`` /
    ``QuarterlyGenParams``. A parametrised end-to-end NBSP
    round-trip is infeasible through reportlab + pdfplumber:
    reportlab's Helvetica font lacks a U+202F (narrow NBSP) glyph
    (substituted as literal ``"n"``), and pdfplumber silently
    canonicalises U+00A0 (NBSP) to ASCII space in its extracted
    text — which cannot be safely restitched at the normaliser
    layer without false-positives on label-embedded casilla
    references. Real Sede Electrónica PDFs render through proper
    Unicode-capable fonts and preserve NBSP through the
    pdfplumber-equivalent extraction path, so the production fix
    remains load-bearing while this synthetic test is limited to
    dot-separator + string-layer coverage.
    """

    def test_dot_separator_is_the_canonical_default(self, tmp_path: Path) -> None:
        """The dot thousands separator survives the synthetic round-trip."""
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
        """End-to-end hyphenation stitching at the extractor layer.

        AEAT multi-column templates wrap long labels as
        ``Reten-\\nciones``. The ``_normalise_pdf_text`` regex
        stitches letter-hyphen-newline-letter boundaries back
        together. This test renders a synthetic PDF with a real
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
        """``format_amount(thousands_sep="\\xa0")`` produces text the regex accepts.

        String-layer guard: ``SPANISH_AMOUNT_GROUP`` must match
        NBSP-separated output even though the full PDF round-trip is
        infeasible through reportlab + pdfplumber. This keeps the
        production fix exercised at the primitive level.
        """
        import re

        from tests.fixtures.pdf_corpus.l3_synthetic._generators._generator_shared import (
            format_amount,
        )

        from ..pdf._label_regex import (
            SPANISH_AMOUNT_GROUP,
            parse_spanish_decimal,
        )

        rendered = format_amount(Decimal("12500.00"), thousands_sep="\xa0")
        assert rendered == "12\xa0500,00"

        m = re.search(SPANISH_AMOUNT_GROUP, rendered)
        assert m is not None
        assert parse_spanish_decimal(m.group(1)) == Decimal("12500.00")
