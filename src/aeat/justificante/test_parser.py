"""Unit tests for :mod:`aeat.justificante` (#44).

These tests exercise the parser end-to-end against the committed synthetic
fixture PDFs under ``tests/fixtures/justificantes/``. They use *real* PDF
files and *real* pdfplumber — no mocks, no patches, no fakes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from ..config import PROJECT_ROOT
from . import (
    Justificante,
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteParserBackend,
    parse_justificante,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "justificantes"


@pytest.fixture(scope="module")
def modelo_130_pdf() -> Path:
    """Path to the committed Modelo 130 synthetic fixture."""
    return FIXTURES_DIR / "modelo_130_2026Q1.pdf"


@pytest.fixture(scope="module")
def modelo_303_pdf() -> Path:
    """Path to the committed Modelo 303 synthetic fixture."""
    return FIXTURES_DIR / "modelo_303_2026Q1.pdf"


@pytest.fixture(scope="module")
def modelo_100_pdf() -> Path:
    """Path to the committed Modelo 100 synthetic fixture."""
    return FIXTURES_DIR / "modelo_100_2025A.pdf"


class TestParseJustificante:
    """End-to-end parsing on the synthetic fixture corpus."""

    def test_modelo_130(self, modelo_130_pdf: Path) -> None:
        record = parse_justificante(modelo_130_pdf)
        assert isinstance(record, Justificante)
        assert record.modelo == "130"
        assert record.period == "1T"
        assert record.ejercicio == "2026"
        assert record.tax_id == "00000000T"
        assert record.csv == "ABCD1234EFGH5678"
        assert record.presentation_id == "13020260410ABCD1234EFGH5678"
        assert record.presented_at == datetime(2026, 4, 10, 11, 23, 45)
        assert record.total_a_ingresar == Decimal("1234.56")
        assert record.total_a_devolver is None
        assert str(record.verification_url).startswith("https://sede.agenciatributaria.gob.es/")
        assert record.source_pdf_path == modelo_130_pdf.resolve()

    def test_modelo_303_devolver(self, modelo_303_pdf: Path) -> None:
        record = parse_justificante(modelo_303_pdf)
        assert record.modelo == "303"
        assert record.period == "1T"
        assert record.ejercicio == "2026"
        assert record.csv == "ZZZZ9999YYYY8888"
        assert record.total_a_ingresar is None
        assert record.total_a_devolver == Decimal("450.00")
        assert record.presented_at == datetime(2026, 4, 11, 9, 5, 0)

    def test_modelo_100_annual(self, modelo_100_pdf: Path) -> None:
        record = parse_justificante(modelo_100_pdf)
        assert record.modelo == "100"
        assert record.period == "0A"
        assert record.ejercicio == "2025"
        assert record.csv == "MNOP4321QRST8765"
        assert record.total_a_ingresar == Decimal("780.40")
        assert record.presented_at == datetime(2026, 6, 20, 17, 45, 12)

    def test_all_fixtures_capture_sha256(
        self,
        modelo_130_pdf: Path,
        modelo_303_pdf: Path,
        modelo_100_pdf: Path,
    ) -> None:
        """Every record must carry the sha-256 of its source PDF bytes."""
        for pdf in (modelo_130_pdf, modelo_303_pdf, modelo_100_pdf):
            expected = hashlib.sha256(pdf.read_bytes()).hexdigest()
            record = parse_justificante(pdf)
            assert record.source_pdf_sha256 == expected
            assert len(record.source_pdf_sha256) == 64

    def test_parser_is_deterministic(self, modelo_130_pdf: Path) -> None:
        """Two parses of the same file must produce identical records
        (modulo the volatile ``parsed_at`` timestamp)."""
        a = parse_justificante(modelo_130_pdf)
        b = parse_justificante(modelo_130_pdf)
        a_dict = a.model_dump(exclude={"parsed_at"})
        b_dict = b.model_dump(exclude={"parsed_at"})
        assert a_dict == b_dict

    def test_explicit_backend_pdfplumber(self, modelo_130_pdf: Path) -> None:
        record = parse_justificante(
            modelo_130_pdf,
            backend=JustificanteParserBackend.PDFPLUMBER,
        )
        assert record.modelo == "130"

    def test_pymupdf_backend_not_implemented(self, modelo_130_pdf: Path) -> None:
        with pytest.raises(JustificanteParseError, match="PYMUPDF"):
            parse_justificante(
                modelo_130_pdf,
                backend=JustificanteParserBackend.PYMUPDF,
            )

    def test_missing_file_raises(self) -> None:
        with pytest.raises(JustificanteParseError, match="not found"):
            parse_justificante(FIXTURES_DIR / "does_not_exist.pdf")


class TestJustificanteErrorRehome:
    """#305 cluster A — JustificanteError inherits the shared PDF-import root."""

    def test_justificante_error_is_pdf_filing_import_error(self) -> None:
        from .._pdf_import import PdfFilingImportError

        assert issubclass(JustificanteError, PdfFilingImportError)

    def test_justificante_error_still_aeat_error(self) -> None:
        from ..errors import AeatError

        assert issubclass(JustificanteError, AeatError)


class TestCsvDetection:
    """A PDF without a CSV must raise the dedicated error subclass."""

    def test_non_justificante_pdf_raises(self, tmp_path: Path) -> None:
        # Build a trivial PDF that contains no CSV label.
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        target = tmp_path / "not_a_justificante.pdf"
        c = canvas.Canvas(str(target), pagesize=A4)
        c.drawString(100, 700, "AGENCIA TRIBUTARIA")
        c.drawString(100, 680, "Modelo: 130")
        c.drawString(100, 660, "Ejercicio: 2026")
        c.drawString(100, 640, "Periodo: 1T")
        c.drawString(100, 620, "NIF: 00000000T")
        c.drawString(100, 600, "Numero de justificante: 1302026")
        c.drawString(100, 580, "Fecha y hora de presentacion: 2026-04-10 11:00:00")
        c.drawString(100, 560, "https://sede.agenciatributaria.gob.es/ayuda")
        c.showPage()
        c.save()
        with pytest.raises(JustificanteCsvNotFoundError):
            parse_justificante(target)


class TestJustificanteModel:
    """Strict-mode guardrails on the :class:`Justificante` pydantic model."""

    def _build(
        self,
        tmp_path: Path,
        *,
        sha256: str | None = None,
    ) -> Justificante:
        pdf = tmp_path / "dummy.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
        return Justificante(
            csv="ABCD1234EFGH5678",
            modelo="130",
            period="1T",
            presentation_id=None,
            presented_at=datetime(2026, 4, 10, 11, 23, 45),
            tax_id="00000000T",
            total_a_ingresar=Decimal("10.00"),
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python("https://sede.agenciatributaria.gob.es/verify"),
            source_pdf_path=pdf,
            source_pdf_sha256=sha256 or hashlib.sha256(pdf.read_bytes()).hexdigest(),
            parsed_at=datetime(2026, 4, 12, 0, 0, 0),
        )

    def test_model_is_frozen(self, tmp_path: Path) -> None:
        record = self._build(tmp_path)
        with pytest.raises(ValidationError):
            record.csv = "OTHER"  # type: ignore[misc]

    def test_extra_fields_rejected(self, tmp_path: Path) -> None:
        record = self._build(tmp_path)
        kwargs = record.model_dump()
        kwargs["surprise"] = "nope"
        with pytest.raises(ValidationError):
            Justificante.model_validate(kwargs)

    def test_sha256_pattern_enforced(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            self._build(tmp_path, sha256="not-a-real-hash")
