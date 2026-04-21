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

from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.cli import app
from tests.fixtures.pdf_corpus.l3_synthetic._generators.modelo_130_generator import (
    Modelo130GenParams,
    generate,
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
    """Render a synthetic Modelo 130 declaración + return the on-disk path."""
    defaults = {
        "01": "12500.00",
        "02": "3500.00",
        "03": "9000.00",
        "04": "1800.00",
        "05": "400.00",
        "06": "0.00",
        "07": "1400.00",
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
        assert "7 of 7 casillas extracted" in result.output
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
