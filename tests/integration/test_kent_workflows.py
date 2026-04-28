"""Kent workflow integration tests — CI regression gate (#305 cluster H).

Each test drives ``aeat filing import --from-declaracion`` or
``aeat filing import --from-justificante`` via Typer's ``CliRunner`` and
asserts on Kent-visible output. Regressions in extraction, verification,
or CLI rendering light up here before they reach a user.

All tests are ``fixture_tier_l3`` — they generate their PDFs in-test
from the synthetic corpus generators. L1 / L2 regressions land in their
own fixture-tier-specific files as anchors accrue.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.cli import app
from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
    QuarterlyGenParams,
)
from tests.fixtures.pdf_corpus.l3_synthetic._generators._generic_quarterly_generator import (
    generate as generate_quarterly,
)
from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_100_generator import (
    Modelo100GenParams,
)
from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_100_generator import (
    generate as generate_modelo_100,
)
from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_130_generator import (
    Modelo130GenParams,
    generate,
)
from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_303_generator import (
    Modelo303GenParams,
)
from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_303_generator import (
    generate as generate_modelo_303,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_financial_input,
    pytest.mark.fixture_tier_l3,
]

runner = CliRunner()


def _synth_modelo_130_pdf(
    tmp_path: Path,
    *,
    ejercicio: str = "2025",
    period_printed: str = "1T",
    casilla_values: dict[str, str] | None = None,
) -> Path:
    """Render a synthetic Modelo 130 declaración + return the on-disk path.

    Issue #321: the M130 generator now renders the full 19-casilla
    liquidación block (casillas 08-19 newly added). Defaults below
    cover all 19 casillas with zeros for the new ones so a caller
    overriding only Apartado I (01-07) still produces a synthetic PDF
    where every casilla prints an amount the extractor can find.
    """
    defaults = {
        "01": "12500.00",
        "02": "3500.00",
        "03": "9000.00",
        "04": "1800.00",
        "05": "400.00",
        "06": "0.00",
        "07": "1400.00",
        # Issue #321: Apartado II + minoración + diferencia.
        # Default to all-zeros for non-agraria autónomos with no
        # minoración, no carryover, and no vivienda deduction.
        "08": "0.00",
        "09": "0.00",
        "10": "0.00",
        "11": "0.00",
        "12": "1400.00",  # max(0, 07 + 11) = max(0, 1400 + 0)
        "13": "0.00",
        "14": "1400.00",  # 12 - 13
        "15": "0.00",
        "16": "0.00",
        "17": "1400.00",  # 14 - 15 - 16
        "18": "0.00",
        "19": "1400.00",  # 17 - 18
    }
    merged = {**defaults, **(casilla_values or {})}
    params = Modelo130GenParams(
        año=int(ejercicio),
        template_revision=f"{ejercicio}.01",
        tax_id="00000000T",
        ejercicio=ejercicio,
        period_printed=period_printed,
        csv="ABCD1234EFGH5678",
        presented_at="2025-04-20 10:00:00",
        casilla_values={k: Decimal(v) for k, v in merged.items()},
    )
    pdf_bytes, _ = generate(params)
    target = tmp_path / f"modelo_130_{ejercicio}_{period_printed}_synth.pdf"
    target.write_bytes(pdf_bytes)
    return target


@pytest.fixture()
def drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "drafts"
    target.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(target))
    return target


@pytest.fixture()
def submissions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "submissions"
    target.mkdir()
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(target))
    return target


@pytest.fixture()
def spanish_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "es")


@pytest.fixture()
def english_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")


class TestKentImportsModelo130Declaracion:
    """Kent's primary Modelo 130 import + verification loop."""

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Kent drops a clean Modelo 130 PDF → VERIFIED verdict in English."""
        del drafts_dir, submissions_dir, english_output  # fixtures with side effects
        pdf = _synth_modelo_130_pdf(tmp_path)
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        # Regex-match rather than a fixed count because the declaration
        # extractor can expand its casilla set as coverage grows;
        # happy path should remain green as long as N-of-N = COMPLETE.
        match = re.search(r"(\d+) of (\d+) casillas extracted", result.output)
        assert match is not None, result.output
        assert match.group(1) == match.group(2), result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verified" in result.output.lower()

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Project-default Spanish output surfaces Kent's verdict in Spanish."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_modelo_130_pdf(tmp_path)
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        # Spanish narrative appears at least once.
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Missing casillas must surface as NEEDS_REVIEW via casilla-not-found."""
        del drafts_dir, submissions_dir, english_output
        # Generate a PDF with 4 of 7 casillas populated (≥50% → PARTIAL).
        params = Modelo130GenParams(
            año=2025,
            template_revision="2025.01",
            tax_id="00000000T",
            ejercicio="2025",
            period_printed="1T",
            csv="ABCD1234EFGH5678",
            presented_at="2025-04-20 10:00:00",
            casilla_values={
                "01": Decimal("1000.00"),
                "02": Decimal("500.00"),
                "03": Decimal("500.00"),
                "04": Decimal("100.00"),
            },
        )
        pdf_bytes, _ = generate(params)
        pdf = tmp_path / "partial.pdf"
        pdf.write_bytes(pdf_bytes)

        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        # Missing casillas must surface in the warnings block.
        assert "casilla 05" in result.output and "casilla 06" in result.output

    @pytest.mark.parametrize("ejercicio", ["2024", "2025", "2026"])
    def test_per_year_happy_path_verified(
        self,
        ejercicio: str,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Issue #321: each of 2024 / 2025 / 2026 declaraciones returns VERIFIED.

        Gemini PR-440 review surfaced that the registry only resolved
        2025 declaraciones; 2024 / 2026 raised NoExtractorRegisteredError.
        This case asserts that a clean synthetic PDF for each of the
        three Tier-L years drives the full
        ``aeat filing import --from-declaracion`` flow to a
        ``VERIFIED`` verdict (extraction status COMPLETE, no
        discrepancies).

        Asserts on stable substrings only — forward-compatible with
        future envelope evolution.
        """
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_modelo_130_pdf(tmp_path, ejercicio=ejercicio)
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output
        # The resolved ruleset matches the year on the PDF.
        assert f"Modelo 130 {ejercicio}Q1" in result.output, result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Issue #321 4th case: a printed casilla disagrees with the engine.

        Generates a PDF where casilla 04 prints 1 800,00 EUR while the
        engine re-derives 04 = 20% of (10 000 - 0) = 2 000,00. The
        verification pass must surface a CORRECTNESS_DIVERGENCE on
        casilla 04 (not on the cross-quarter pool surface, since 05/06
        are zero in this fixture). Kent's verdict should be
        NEEDS_REVIEW with a discrepancy line naming casilla 04 and
        the magnitudes.

        Asserts on stable substrings only (status marker, casilla id,
        cause-classification token) — forward-compatible with future
        envelope evolution.
        """
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_modelo_130_pdf(
            tmp_path,
            casilla_values={
                "01": "10000.00",
                "02": "0.00",
                "03": "10000.00",
                "04": "1800.00",  # engine re-derives 2 000,00 — 200,00 € drift
                "05": "0.00",
                "06": "0.00",
                "07": "1800.00",  # 04 - 05 - 06 (consistent with the printed 04)
                "12": "1800.00",
                "14": "1800.00",
                "17": "1800.00",
                "19": "1800.00",
            },
        )
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output, result.output
        # The classifier must surface casilla 04 as a divergence and
        # cite its cause token. Use stable substrings only.
        assert "casilla 04" in result.output, result.output
        assert "CORRECTNESS_DIVERGENCE" in result.output, result.output


class TestKentImportsModelo130Justificante:
    """Kent's original #271 justificante-import flow must still work."""

    def test_justificante_scaffold_still_produced(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Shipped #271 contract: aeat filing import --from-justificante still works."""
        del drafts_dir, submissions_dir, english_output
        from aeat.config import PROJECT_ROOT

        pdf = PROJECT_ROOT / "tests" / "fixtures" / "justificantes" / "modelo_130_2026Q1.pdf"
        if not pdf.exists():
            pytest.skip(f"justificante fixture missing: {pdf}")

        result = runner.invoke(
            app,
            ["filing", "import", "--from-justificante", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Imported draft" in result.output
        assert "warning" in result.output.lower()


class TestKentCliInvariants:
    """CLI-level invariants that protect Kent's expected developer experience."""

    def test_import_requires_exactly_one_source(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        """aeat filing import without any --from-* flag must error cleanly."""
        del drafts_dir, submissions_dir
        result = runner.invoke(app, ["filing", "import"])
        assert result.exit_code != 0
        combined = (result.output or "") + (str(result.exception) if result.exception else "")
        assert "exactly one of" in combined.lower()

    def test_import_rejects_dual_sources(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        """Passing both --from-justificante and --from-declaracion must fail cleanly."""
        del drafts_dir, submissions_dir
        pdf = _synth_modelo_130_pdf(tmp_path)
        result = runner.invoke(
            app,
            [
                "filing",
                "import",
                "--from-declaracion",
                str(pdf),
                "--from-justificante",
                str(pdf),
            ],
        )
        assert result.exit_code != 0
        combined = (result.output or "") + (str(result.exception) if result.exception else "")
        assert "only one" in combined.lower()


# =============================================================================
# Tier-L Kent CLI integration coverage (#340 / EPIC #316).
#
# Each TestKentImportsModelo{MODELO}* class below exercises the full
# `aeat filing import` chain via Typer's CliRunner for one Tier-L modelo:
# parse_declaracion (or parse_borrador for Modelo 100) → ruleset resolve
# → verify_declaracion (or Engine.audit_against for the borrador path).
# Modelo 130 already covered above (template).
#
# Assertion strategy is stable-marker-only (forward-compat with #398 / #399):
# substring matches on `Extraction status:`, `Verification status:`,
# `cause=...`, casilla ids, and language-probe substrings. NO full output
# equality and NO chrome / emoji / ordering assumptions.
# =============================================================================


# Label maps (mirroring `aeat.declaracion.test_quarterly_extractors`) keep
# integration coverage aligned with parser-test ground truth.
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

_MODELO_123_LABELS: Mapping[str, str] = {
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

_MODELO_131_LABELS: Mapping[str, str] = {
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

_MODELO_180_LABELS: Mapping[str, str] = {
    "01": "Total perceptores",
    "02": "Total base retencion",
    "03": "Total retenciones",
    "04": "Total ingresos a cuenta",
}

_MODELO_200_LABELS: Mapping[str, str] = {
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

_MODELO_202_LABELS: Mapping[str, str] = {
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

_MODELO_390_LABELS: Mapping[str, str] = {
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


# Happy-path values — every formula in the corresponding ruleset evaluates
# clean (verified manually against `aeat.formulas.Engine.audit_against`).
_M111_HAPPY: Mapping[str, str] = {
    "01": "5",
    "02": "50000",
    "03": "7500",
    "04": "2",
    "05": "20000",
    "06": "4000",
    "07": "1",
    "08": "1000",
    "09": "190",
    "10": "1",
    "11": "1000",
    "12": "190",
    "13": "0",
    "14": "0",
    "15": "100",
    "16": "0",
    "17": "0",
    "18": "50",
    "28": "12030",
    "29": "0",
    "30": "12030",
}

_M115_HAPPY: Mapping[str, str] = {
    "01": "2",
    "02": "10000",
    "03": "1900",
    "04": "0",
    "05": "0",
    "06": "1900",
}

_M123_HAPPY: Mapping[str, str] = {
    "01": "2",
    "02": "3",
    "03": "5",
    "04": "1500",
    "05": "8000",
    "06": "9500",
    "07": "285",
    "08": "1520",
    "09": "1805",
    "10": "0",
    "11": "1805",
}

_M131_HAPPY: Mapping[str, str] = {
    "01": "10000",
    "02": "200",
    "03": "5000",
    "04": "100",
    "05": "2000",
    "06": "40",
    "07": "340",
    "08": "0",
    "09": "0",
    "10": "340",
    "11": "0",
    "12": "0",
    "13": "340",
    "14": "0",
    "15": "340",
}

_M180_HAPPY: Mapping[str, str] = {
    "01": "5",
    "02": "48000",
    "03": "9120",
    "04": "0",
}

_M200_VALUES: Mapping[str, str] = {
    # Modelo 200 has only a 2024 ruleset on main but the registered extractor
    # is template_revision="2025.01" with año=2025 → CLI verdict is
    # UNVERIFIABLE for any 2025-rendered PDF today. Values are arbitrary
    # but plausible per AEAT IS liquidación page-14 layout.
    "00547": "0",
    "00550": "100000",
    "00552": "100000",
    "00558": "25",
    "00560": "25000",
    "00562": "25000",
    "00582": "25000",
    "00592": "25000",
    "00599": "0",
    "00601": "5000",
    "00603": "5000",
    "00605": "5000",
    "00615": "0",
    "00619": "0",
    "00611": "10000",
    "00621": "10000",
}

_M202_HAPPY: Mapping[str, str] = {
    "16": "100000",
    "17": "25",
    "18": "25000",
    "27": "0",
    "28": "2500",
    "30": "0",
    "32": "22500",
    "33": "0",
    "34": "22500",
}

_M390_HAPPY: Mapping[str, str] = {
    "01": "50000",
    "04": "10500",
    "95": "50000",
    "96": "10500",
    "100": "4000",
    "101": "500",
    "104": "4500",
    "105": "6000",
    "108": "0",
    "109": "0",
    "190": "6000",
    "191": "6000",
    "192": "6000",
    "193": "0",
    "662": "0",
}

_M303_HAPPY: Mapping[str, str] = {
    "01": "1000",
    "02": "4",
    "03": "40",
    "04": "2000",
    "05": "10",
    "06": "200",
    "07": "10000",
    "08": "21",
    "09": "2100",
    "28": "0",
    "29": "0",
    "30": "0",
    "31": "0",
    "32": "0",
    "33": "0",
    "34": "0",
    "35": "100",
    "36": "0",
    "37": "0",
    "38": "0",
    "39": "0",
    "40": "0",
    "41": "0",
    "42": "0",
    "43": "0",
    "44": "100",
    "45": "2240",
    "64": "2240",
    "65": "100",
    "66": "2240",
    "67": "0",
    "69": "2240",
    "71": "2240",
}

# Modelo 100-summary uses the borrador path; values audit against
# `MODELO_100_SUMMARY_2025`.
_M100_SUMMARY_HAPPY: Mapping[str, str] = {
    "0022": "40000",
    "0049": "500",
    "0107": "300",
    "0175": "15000",
    "0400": "0",
    "0435": "55800",
    "0460": "500",
    "0500": "5550",
    "0505": "5550",
    "0510": "0",
    "0515": "0",
    "0520": "0",
    "0545": "50250",
    "0555": "500",
    "0550": "5000",
    "0551": "5000",
    "0560": "50",
    "0561": "50",
    "0595": "10100",
    "0620": "0",
    "0622": "0",
    "0630": "0",
    "0698": "10100",
    "0699": "8000",
    "0700": "500",
    "0720": "1600",
    "0721": "1600",
}


def _synth_quarterly_pdf(
    tmp_path: Path,
    *,
    modelo: str,
    labels: Mapping[str, str],
    values: Mapping[str, str],
    filename: str,
    año: int = 2025,
    ejercicio: str = "2025",
    period_printed: str = "1T",
    template_revision: str = "2025.01",
) -> Path:
    """Render a quarterly synthetic declaración PDF + return its on-disk path."""
    params = QuarterlyGenParams(
        modelo=modelo,
        año=año,
        template_revision=template_revision,
        tax_id="00000000T",
        ejercicio=ejercicio,
        period_printed=period_printed,
        labels=labels,
        casilla_values={k: Decimal(v) for k, v in values.items()},
        csv="ABCD1234EFGH5678",
    )
    pdf_bytes, _ = generate_quarterly(params)
    target = tmp_path / filename
    target.write_bytes(pdf_bytes)
    return target


def _synth_annual_pdf(
    tmp_path: Path,
    *,
    modelo: str,
    labels: Mapping[str, str],
    values: Mapping[str, str],
    filename: str,
    año: int = 2025,
    ejercicio: str = "2025",
    template_revision: str = "2025.01",
) -> Path:
    """Render an annual (period_printed='0A') synthetic PDF."""
    return _synth_quarterly_pdf(
        tmp_path,
        modelo=modelo,
        labels=labels,
        values=values,
        filename=filename,
        año=año,
        ejercicio=ejercicio,
        period_printed="0A",
        template_revision=template_revision,
    )


def _synth_modelo_303_pdf(
    tmp_path: Path,
    *,
    values: Mapping[str, str],
    filename: str = "modelo_303_2025Q1_synth.pdf",
    period_printed: str = "1T",
    año: int = 2025,
    ejercicio: str = "2025",
    template_revision: str = "2025.01",
) -> Path:
    """Render a synthetic Modelo 303 declaración PDF via its dedicated generator."""
    params = Modelo303GenParams(
        año=año,
        template_revision=template_revision,
        tax_id="00000000T",
        ejercicio=ejercicio,
        period_printed=period_printed,
        casilla_values={k: Decimal(v) for k, v in values.items()},
        csv="ABCD1234EFGH5678",
    )
    pdf_bytes, _ = generate_modelo_303(params)
    target = tmp_path / filename
    target.write_bytes(pdf_bytes)
    return target


def _synth_modelo_100_summary_pdf(
    tmp_path: Path,
    *,
    values: Mapping[str, str],
    filename: str = "modelo_100_2025_synth.pdf",
    artefact_kind: str = "DECLARACION",
) -> Path:
    """Render a synthetic Modelo 100 (Renta) summary-block PDF."""
    params = Modelo100GenParams(
        año=2025,
        ejercicio="2025",
        tax_id="00000000T",
        casilla_values={k: Decimal(v) for k, v in values.items()},
        artefact_kind=artefact_kind,
        csv="ABCD1234EFGH5678",
    )
    pdf_bytes, _ = generate_modelo_100(params)
    target = tmp_path / filename
    target.write_bytes(pdf_bytes)
    return target


def _partial_subset(values: Mapping[str, str], keep_first: int) -> Mapping[str, str]:
    """Return the first ``keep_first`` (id → str) entries of ``values``."""
    items = list(values.items())
    return dict(items[:keep_first])


class TestKentImportsModelo111Declaracion:
    """Kent imports a Modelo 111 (IRPF retenciones trimestrales) for 2025.

    Year 2025 is the most recent landed ruleset (2024 also exists). The
    formulas exercised: c09 = 19% x c08, c12 = 19% x c11,
    c28 = c03+c06+c09+c12+c15+c18, c30 = c28-c29.
    """

    _LABELS = _MODELO_111_LABELS

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 111 PDF → VERIFIED verdict in English."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="111",
            labels=self._LABELS,
            values=_M111_HAPPY,
            filename="modelo_111_2025Q1_happy.pdf",
        )
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verified" in result.output.lower()

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Project-default Spanish output emits Kent's verdict in Spanish."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="111",
            labels=self._LABELS,
            values=_M111_HAPPY,
            filename="modelo_111_2025Q1_happy_es.pdf",
        )
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """A subset PDF surfaces PARTIAL + casilla-not-found warnings."""
        del drafts_dir, submissions_dir, english_output
        # 11 of 21 → ≥50% → PARTIAL; remaining 10 surface as warnings.
        partial = _partial_subset(_M111_HAPPY, 11)
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="111",
            labels=self._LABELS,
            values=partial,
            filename="modelo_111_2025Q1_partial.pdf",
        )
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        # At least one missing casilla should appear as a warning.
        assert "casilla 28" in result.output or "casilla 30" in result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """A drifted computed casilla → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        # c09 should be 190 (19% of c08=1000); printed value 999 drifts by ≥1 €.
        tampered = dict(_M111_HAPPY) | {"09": "999"}
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="111",
            labels=self._LABELS,
            values=tampered,
            filename="modelo_111_2025Q1_drift.pdf",
        )
        result = runner.invoke(
            app,
            ["filing", "import", "--from-declaracion", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 09" in result.output


class TestKentImportsModelo115Declaracion:
    """Kent imports a Modelo 115 (retenciones arrendamientos urbanos) 2025.

    Year 2025 is the most recent landed ruleset. Formulas:
    c03 = 19% x c02, c06 = c03 + c04 - c05.
    """

    _LABELS = _MODELO_115_LABELS

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 115 PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="115",
            labels=self._LABELS,
            values=_M115_HAPPY,
            filename="modelo_115_2025Q1_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish (default) verdict surfaces."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="115",
            labels=self._LABELS,
            values=_M115_HAPPY,
            filename="modelo_115_2025Q1_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """4 of 6 casillas → PARTIAL + missing casillas in warnings."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M115_HAPPY, 4)
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="115",
            labels=self._LABELS,
            values=partial,
            filename="modelo_115_2025Q1_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "casilla 05" in result.output or "casilla 06" in result.output

    @pytest.mark.parametrize("ejercicio", ["2024", "2025", "2026"])
    def test_per_year_happy_path_verified(
        self,
        ejercicio: str,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Issue #319: each of 2024 / 2025 / 2026 declaraciones returns VERIFIED.

        Mirrors the M130 per-year case introduced under #321: the
        extractor registry must resolve a 2024 or 2026 PDF to a
        working extractor (Modelo115V2024Extractor /
        Modelo115V2026Extractor sibling classes) and the formula
        engine must resolve to the matching per-annum ruleset
        (MODELO_115_2024 / MODELO_115_2026). A clean synthetic
        PDF for each of the three Tier-L years drives the full
        ``aeat filing import --from-declaracion`` flow to a
        ``VERIFIED`` verdict.

        Asserts on stable substrings only — forward-compatible
        with future envelope evolution.
        """
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="115",
            labels=self._LABELS,
            values=_M115_HAPPY,
            filename=f"modelo_115_{ejercicio}Q1_happy.pdf",
            año=int(ejercicio),
            ejercicio=ejercicio,
            template_revision=f"{ejercicio}.01",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output
        # The resolved ruleset matches the year on the PDF.
        assert f"Modelo 115 {ejercicio}Q1" in result.output, result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted c03 (= 19% x c02) → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        tampered = dict(_M115_HAPPY) | {"03": "9999"}
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="115",
            labels=self._LABELS,
            values=tampered,
            filename="modelo_115_2025Q1_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 03" in result.output


class TestKentImportsModelo123Declaracion:
    """Kent imports Modelo 123 retenciones rendimientos capital mobiliario.

    c03 = c01+c02, c06 = c04+c05, c09 = c07+c08, c11 = c09 - c10.
    """

    _LABELS = _MODELO_123_LABELS

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 123 PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="123",
            labels=self._LABELS,
            values=_M123_HAPPY,
            filename="modelo_123_2025Q1_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish (default) verdict surfaces."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="123",
            labels=self._LABELS,
            values=_M123_HAPPY,
            filename="modelo_123_2025Q1_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """6 of 11 casillas → PARTIAL."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M123_HAPPY, 6)
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="123",
            labels=self._LABELS,
            values=partial,
            filename="modelo_123_2025Q1_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "casilla 11" in result.output or "casilla 09" in result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted c11 (= c09 - c10) → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        tampered = dict(_M123_HAPPY) | {"11": "9999"}
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="123",
            labels=self._LABELS,
            values=tampered,
            filename="modelo_123_2025Q1_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 11" in result.output

    @pytest.mark.parametrize(
        ("ejercicio", "template_revision"),
        [
            ("2024", "2024.01"),
            ("2025", "2025.01"),
            ("2026", "2026.01"),
        ],
    )
    def test_per_year_happy_path_is_verified(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
        ejercicio: str,
        template_revision: str,
    ) -> None:
        """Each M123 ruleset year resolves through declaración import."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="123",
            labels=self._LABELS,
            values=_M123_HAPPY,
            filename=f"modelo_123_{ejercicio}Q1_happy.pdf",
            año=int(ejercicio),
            ejercicio=ejercicio,
            template_revision=template_revision,
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output
        assert f"Modelo 123 {ejercicio}Q1" in result.output, result.output


class TestKentImportsModelo131Declaracion:
    """Kent imports a Modelo 131 (pago fraccionado IRPF módulos) 2025.

    Year 2025 is the most recent landed ruleset. Six computed casillas.
    """

    _LABELS = _MODELO_131_LABELS

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 131 PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="131",
            labels=self._LABELS,
            values=_M131_HAPPY,
            filename="modelo_131_2025Q1_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish (default) verdict."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="131",
            labels=self._LABELS,
            values=_M131_HAPPY,
            filename="modelo_131_2025Q1_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """8 of 15 casillas → PARTIAL."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M131_HAPPY, 8)
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="131",
            labels=self._LABELS,
            values=partial,
            filename="modelo_131_2025Q1_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "casilla 15" in result.output or "casilla 13" in result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted c15 → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        tampered = dict(_M131_HAPPY) | {"15": "9999"}
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="131",
            labels=self._LABELS,
            values=tampered,
            filename="modelo_131_2025Q1_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 15" in result.output


class TestKentImportsModelo180Declaracion:
    """Kent imports Modelo 180 annual rental-withholding summaries.

    Single computed casilla: c03 = 19% x c02.
    """

    _LABELS = _MODELO_180_LABELS

    @pytest.mark.parametrize("ejercicio", ["2024", "2025", "2026"])
    def test_per_year_happy_path_verified(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
        ejercicio: str,
    ) -> None:
        """Clean annual PDF resolves to the matching year ruleset and verifies."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="180",
            labels=self._LABELS,
            values=_M180_HAPPY,
            filename=f"modelo_180_{ejercicio}_happy.pdf",
            año=int(ejercicio),
            ejercicio=ejercicio,
            template_revision=f"{ejercicio}.01",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 180 annual PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="180",
            labels=self._LABELS,
            values=_M180_HAPPY,
            filename="modelo_180_2025_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish (default) verdict."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="180",
            labels=self._LABELS,
            values=_M180_HAPPY,
            filename="modelo_180_2025_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """2 of 4 → PARTIAL."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M180_HAPPY, 2)
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="180",
            labels=self._LABELS,
            values=partial,
            filename="modelo_180_2025_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "casilla 03" in result.output or "casilla 04" in result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted c03 (= 19% x c02) → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        tampered = dict(_M180_HAPPY) | {"03": "5000"}
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="180",
            labels=self._LABELS,
            values=tampered,
            filename="modelo_180_2025_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 03" in result.output


class TestKentImportsModelo200Declaracion:
    """Kent imports a Modelo 200 (Impuesto sobre Sociedades) 2025.

    Year 2025 is the only year with a registered extractor; the only
    landed ruleset is for 2024. The CLI verdict for any 2025-rendered
    Modelo 200 PDF is therefore UNVERIFIABLE today — locked in here so
    the future ramp to a 2025 ruleset is a deliberate test update. The
    discrepancy classification 4th case is omitted (no ruleset → no
    formula divergence).
    """

    _LABELS = _MODELO_200_LABELS

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 200 PDF → UNVERIFIABLE (no 2025 ruleset)."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="200",
            labels=self._LABELS,
            values=_M200_VALUES,
            filename="modelo_200_2025_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: UNVERIFIABLE" in result.output
        assert "no ruleset registered" in result.output.lower()

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish UNVERIFIABLE narrative."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="200",
            labels=self._LABELS,
            values=_M200_VALUES,
            filename="modelo_200_2025_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: UNVERIFIABLE" in result.output
        assert "no hay ruleset registrado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """8 of 16 casillas → PARTIAL (still UNVERIFIABLE downstream)."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M200_VALUES, 8)
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="200",
            labels=self._LABELS,
            values=partial,
            filename="modelo_200_2025_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        # Even partial extraction terminates as UNVERIFIABLE because no 2025 ruleset.
        assert "Verification status: UNVERIFIABLE" in result.output


class TestKentImportsModelo202Declaracion:
    """Kent imports a Modelo 202 (pago fraccionado IS) 2025.

    Year 2025 is the only landed ruleset. Three computed casillas:
    c18 = (c17/100) x c16, c32 = c18-c27-c28-c30, c34 = max(c32, c33).
    """

    _LABELS = _MODELO_202_LABELS

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 202 PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="202",
            labels=self._LABELS,
            values=_M202_HAPPY,
            filename="modelo_202_2025_1P_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish verdict."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="202",
            labels=self._LABELS,
            values=_M202_HAPPY,
            filename="modelo_202_2025_1P_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """5 of 9 casillas → PARTIAL."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M202_HAPPY, 5)
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="202",
            labels=self._LABELS,
            values=partial,
            filename="modelo_202_2025_1P_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "casilla 32" in result.output or "casilla 34" in result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted c34 (= max(c32, c33)) → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        tampered = dict(_M202_HAPPY) | {"34": "99999"}
        pdf = _synth_quarterly_pdf(
            tmp_path,
            modelo="202",
            labels=self._LABELS,
            values=tampered,
            filename="modelo_202_2025_1P_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 34" in result.output


class TestKentImportsModelo303Declaracion:
    """Kent imports a Modelo 303 (autoliquidación IVA) 2025.

    Year 2025 is the most recent landed ruleset (2024-orden-819 also
    exists). Twelve computed casillas span apartados 1, 2 IVA-soportado
    sum, and the resultado chain. Uses the dedicated 303 generator (33
    casillas).
    """

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 303 PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_modelo_303_pdf(
            tmp_path,
            values=_M303_HAPPY,
            filename="modelo_303_2025Q1_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish verdict."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_modelo_303_pdf(
            tmp_path,
            values=_M303_HAPPY,
            filename="modelo_303_2025Q1_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """20 of 33 casillas → PARTIAL."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M303_HAPPY, 20)
        pdf = _synth_modelo_303_pdf(
            tmp_path,
            values=partial,
            filename="modelo_303_2025Q1_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "casilla 71" in result.output or "casilla 69" in result.output

    def test_happy_path_2026_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 303 2026 PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_modelo_303_pdf(
            tmp_path,
            values=_M303_HAPPY,
            filename="modelo_303_2026Q1_happy.pdf",
            año=2026,
            ejercicio="2026",
            template_revision="2026.01",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted c71 → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        tampered = dict(_M303_HAPPY) | {"71": "99999"}
        pdf = _synth_modelo_303_pdf(
            tmp_path,
            values=tampered,
            filename="modelo_303_2025Q1_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 71" in result.output


class TestKentImportsModelo390Declaracion:
    """Kent imports a Modelo 390 (resumen anual IVA).

    Three rulesets ship (2024 / 2025 / 2026); the integration class
    exercises 2025 happy-path / partial-extraction / discrepancy
    cases. Six computed casillas: c104 = c100+c101, c105 = c96-c104,
    c190 = c105+c108+c109, c191 = c190-c662, c192 = clamp_pos(c191),
    c193 = clamp_pos(0-c191).
    """

    _LABELS = _MODELO_390_LABELS

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 390 annual PDF → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="390",
            labels=self._LABELS,
            values=_M390_HAPPY,
            filename="modelo_390_2025_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: COMPLETE" in result.output
        assert "Verification status: VERIFIED" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish verdict."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="390",
            labels=self._LABELS,
            values=_M390_HAPPY,
            filename="modelo_390_2025_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        assert "verificado" in result.output.lower()

    def test_partial_extraction_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """8 of 15 casillas → PARTIAL."""
        del drafts_dir, submissions_dir, english_output
        partial = _partial_subset(_M390_HAPPY, 8)
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="390",
            labels=self._LABELS,
            values=partial,
            filename="modelo_390_2025_partial.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Extraction status: PARTIAL" in result.output
        assert "casilla 190" in result.output or "casilla 192" in result.output

    def test_discrepancy_classified_correctly(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted c190 → CORRECTNESS_DIVERGENCE."""
        del drafts_dir, submissions_dir, english_output
        tampered = dict(_M390_HAPPY) | {"190": "99999"}
        pdf = _synth_annual_pdf(
            tmp_path,
            modelo="390",
            labels=self._LABELS,
            values=tampered,
            filename="modelo_390_2025_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-declaracion", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "cause=CORRECTNESS_DIVERGENCE" in result.output
        assert "casilla 190" in result.output


class TestKentImportsModelo100SummaryBorrador:
    """Kent imports a Modelo 100 (Renta) summary-block PDF for 2025.

    Modelo 100 dispatches via ``aeat filing import --from-borrador`` (NOT
    ``--from-declaracion``) — the Renta artefact pipeline runs through
    `parse_borrador` and audits against MODELO_100_SUMMARY_2025 directly.
    The CLI emits ``Parsed Modelo 100 Renta ...`` (no
    ``Extraction status:`` prefix) and ``Verification status: VERIFIED
    (ruleset=modelo_100.summary.2025)``. Year 2025 is the only landed
    ruleset.

    Borrador-specific scope:
    - There is no `Extraction status:` line on this CLI path, so the
      conventional "partial extraction" case is meaningless here.
    - In its place, the third method exercises the borrador-equivalent
      Kent-observable failure mode: a drifted computed casilla causes
      `Engine.audit_against` to surface a discrepancy and the verdict
      to drop to `NEEDS_REVIEW`. This is the exact regression target
      the audit (EPIC #316) cares about for the Renta path.
    """

    def test_happy_path_english(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Clean Modelo 100 declaración → VERIFIED."""
        del drafts_dir, submissions_dir, english_output
        pdf = _synth_modelo_100_summary_pdf(
            tmp_path,
            values=_M100_SUMMARY_HAPPY,
            filename="modelo_100_2025_happy.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-borrador", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Parsed Modelo 100 Renta" in result.output
        assert "Verification status: VERIFIED" in result.output
        assert "ruleset=modelo_100.summary.2025" in result.output

    def test_happy_path_spanish_default(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        spanish_output: None,
    ) -> None:
        """Spanish (default) — verdict still surfaces VERIFIED."""
        del drafts_dir, submissions_dir, spanish_output
        pdf = _synth_modelo_100_summary_pdf(
            tmp_path,
            values=_M100_SUMMARY_HAPPY,
            filename="modelo_100_2025_happy_es.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-borrador", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: VERIFIED" in result.output
        # The borrador path emits the ruleset-id suffix; the verdict-token is
        # the stable contract regardless of locale.
        assert "ruleset=modelo_100.summary.2025" in result.output

    def test_discrepancy_triggers_needs_review(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        english_output: None,
    ) -> None:
        """Drifted computed casilla → NEEDS_REVIEW with classified discrepancies.

        The borrador CLI does not expose ``Extraction status: PARTIAL`` —
        ``aeat.borrador`` reports its own structure. The Kent-observable
        ``NEEDS_REVIEW`` outcome is reached by tampering with one of the
        four computed casillas (c0595 = c0550+c0551+c0560+c0561). A
        printed value that drifts from the engine-computed sum surfaces
        through ``Engine.audit_against`` and lights up the discrepancy
        list.
        """
        del drafts_dir, submissions_dir, english_output
        # Drift c0698 (= clamp_positive(c0595 - c0630)) by ≥ 1 € so the
        # Engine.audit_against report flags it.
        tampered = dict(_M100_SUMMARY_HAPPY) | {"0698": "99999"}
        pdf = _synth_modelo_100_summary_pdf(
            tmp_path,
            values=tampered,
            filename="modelo_100_2025_drift.pdf",
        )
        result = runner.invoke(app, ["filing", "import", "--from-borrador", str(pdf)])
        assert result.exit_code == 0, result.output
        assert "Verification status: NEEDS_REVIEW" in result.output
        assert "discrepancies" in result.output.lower()
        assert "casilla 0698" in result.output
