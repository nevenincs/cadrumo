"""Unit tests for :mod:`aeat.application.filing._import` (issue #271).

The suite exercises :func:`import_filing_from_justificante` against the
committed synthetic fixture PDFs under ``tests/fixtures/justificantes/``
— no mocks, no patches, no fakes.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from ...core.config import PROJECT_ROOT
from ...core.i18n import Language, get_translation
from ...domain.justificante import JustificanteParseError
from . import (
    FilingImportError,
    FilingValueKind,
    import_filing_from_justificante,
)
from ._import import _normalise_period
from .runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "justificantes"


@pytest.fixture(scope="module")
def schema_provider():
    """Build the production schema provider once per module."""
    return build_runtime_schema_provider()


class TestImportFromJustificante:
    """End-to-end reconstruction on the committed fixture corpus."""

    def test_modelo_130_reconstructs_draft_scaffold(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        result = import_filing_from_justificante(pdf, schema_provider=schema_provider)
        assert result.draft.modelo == "130"
        assert result.draft.period == "2026Q1"
        assert result.draft.profile_tax_id == "00000000T"
        # The import path supplies no inputs, so every required-input casilla
        # stays EMPTY; default/computed casillas still resolve to their
        # deterministic fallback per the builder contract.
        literal_kinds = {
            value.casilla_id: value.kind
            for value in result.draft.values
            if value.kind in {FilingValueKind.EMPTY, FilingValueKind.LITERAL}
        }
        assert literal_kinds["01"] is FilingValueKind.EMPTY
        assert literal_kinds["02"] is FilingValueKind.EMPTY

    def test_modelo_130_emits_companion_submission(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        result = import_filing_from_justificante(pdf, schema_provider=schema_provider)
        assert result.submission.draft_id == result.draft.draft_id
        assert result.submission.modelo == "130"
        assert result.submission.period == "2026Q1"
        assert result.submission.justificante_csv == "ABCD1234EFGH5678"
        assert result.submission.justificante_pdf_path == pdf.resolve()
        assert result.submission.submitted_at.tzinfo is not None
        assert result.submission.submitted_at.utcoffset() == UTC.utcoffset(None)

    def test_modelo_303_reconstructs_quarterly_period(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_303_2026Q1.pdf"
        result = import_filing_from_justificante(pdf, schema_provider=schema_provider)
        assert result.draft.modelo == "303"
        assert result.draft.period == "2026Q1"
        assert result.submission.justificante_csv == "ZZZZ9999YYYY8888"

    def test_unsupported_modelo_raises_import_error(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_100_2025A.pdf"
        with pytest.raises(FilingImportError, match="modelo '100'"):
            import_filing_from_justificante(pdf, schema_provider=schema_provider)

    def test_missing_pdf_raises_parse_error(
        self,
        tmp_path: Path,
        schema_provider,
    ) -> None:
        missing = tmp_path / "nonexistent.pdf"
        with pytest.raises(JustificanteParseError, match="not found"):
            import_filing_from_justificante(missing, schema_provider=schema_provider)

    def test_warnings_flag_empty_line_level_casillas(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        result = import_filing_from_justificante(pdf, schema_provider=schema_provider)
        assert result.warnings
        rendered = get_translation(result.warnings[0], Language.EN)
        assert "casilla" in rendered.lower()
        es_rendered = get_translation(result.warnings[0], Language.ES)
        assert "casilla" in es_rendered.lower()


class TestNormalisePeriod:
    """Unit coverage for the period canonicaliser."""

    @pytest.mark.parametrize(
        ("modelo", "ejercicio", "raw", "expected"),
        [
            ("130", "2026", "1T", "2026Q1"),
            ("130", "2026", "4T", "2026Q4"),
            ("303", "2024", "1T", "2024Q1"),
            ("303", "2024", "12", "2024-12"),
            ("303", "2024", "01", "2024-01"),
            ("100", "2025", "0A", "2025A"),
            ("130", None, "2026Q1", "2026Q1"),
            ("303", None, "2024-12", "2024-12"),
        ],
    )
    def test_canonical_forms(
        self,
        modelo: str,
        ejercicio: str | None,
        raw: str,
        expected: str,
    ) -> None:
        assert _normalise_period(modelo=modelo, ejercicio=ejercicio, raw_period=raw) == expected

    def test_malformed_period_raises(self) -> None:
        with pytest.raises(FilingImportError, match="cannot canonicalise"):
            _normalise_period(modelo="130", ejercicio="2026", raw_period="XX")

    def test_missing_ejercicio_raises(self) -> None:
        with pytest.raises(FilingImportError, match="requires an ejercicio"):
            _normalise_period(modelo="130", ejercicio=None, raw_period="1T")

    def test_bad_ejercicio_raises(self) -> None:
        with pytest.raises(FilingImportError, match="unexpected ejercicio"):
            _normalise_period(modelo="130", ejercicio="26", raw_period="1T")
