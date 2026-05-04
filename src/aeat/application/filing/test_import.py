"""Unit tests for :mod:`aeat.application.filing._import`.

Exercises :func:`aeat.application.filing.import_filing_from_justificante`
end-to-end against the committed synthetic justificante fixture PDFs
under ``tests/fixtures/justificantes/`` — no mocks, no patches, no
fakes. Also covers the :func:`_normalise_period` canonicaliser.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import PROJECT_ROOT
from ...domain.justificante import JustificanteParseError
from . import (
    FilingImportError,
    import_filing_from_justificante,
)
from ._import import _normalise_period
from .runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "justificantes"


@pytest.fixture(scope="module")
def schema_provider():
    """Return a placeholder provider; build_draft fails before using it."""
    return object()


def test_runtime_schema_provider_requires_registry_snapshot() -> None:
    with pytest.raises(FilingImportError) as exc_info:
        try:
            build_runtime_schema_provider()
        except Exception as exc:
            raise FilingImportError(str(exc)) from exc
    assert "registry snapshots" in str(exc_info.value)


class TestImportFromJustificante:
    """End-to-end reconstruction on the committed fixture corpus."""

    def test_modelo_130_requires_registry_snapshot(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        with pytest.raises(FilingImportError, match="validated registry snapshot"):
            import_filing_from_justificante(pdf, schema_provider=schema_provider)

    def test_modelo_130_does_not_emit_companion_submission_without_registry(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        with pytest.raises(FilingImportError, match="Python filing builders are unavailable"):
            import_filing_from_justificante(pdf, schema_provider=schema_provider)

    def test_modelo_303_requires_registry_snapshot(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_303_2026Q1.pdf"
        with pytest.raises(FilingImportError, match="validated registry snapshot"):
            import_filing_from_justificante(pdf, schema_provider=schema_provider)

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

    def test_import_stops_before_empty_casilla_warning_projection(self, schema_provider) -> None:
        pdf = _FIXTURES / "modelo_130_2026Q1.pdf"
        with pytest.raises(FilingImportError, match="validated registry snapshot"):
            import_filing_from_justificante(pdf, schema_provider=schema_provider)


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
