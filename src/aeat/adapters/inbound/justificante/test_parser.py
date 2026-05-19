"""Unit tests for :mod:`aeat.adapters.inbound.justificante`.

These tests exercise the parser end-to-end against the committed fixture
PDFs under ``src/aeat/tests/fixtures/justificantes/``. They use real PDF
files and real pdfplumber.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from aeat.adapters.inbound.justificante import parse_justificante
from aeat.domain.justificante import (
    Justificante,
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteParserBackend,
)
from aeat.tests import FIXTURES_DIR as _FIXTURES_ROOT
from aeat.tests._justificante_parse_cache import parse_committed_justificante_fixture

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

FIXTURES_DIR = _FIXTURES_ROOT / "justificantes"


@pytest.fixture(scope="module")
def modelo_130_pdf() -> Path:
    """Path to the committed Modelo 130 fixture."""
    return FIXTURES_DIR / "modelo_130_2026Q1.pdf"


@pytest.fixture(scope="module")
def modelo_303_pdf() -> Path:
    """Path to the committed Modelo 303 fixture."""
    return FIXTURES_DIR / "modelo_303_2026Q1.pdf"


@pytest.fixture(scope="module")
def modelo_100_pdf() -> Path:
    """Path to the committed Modelo 100 fixture."""
    return FIXTURES_DIR / "modelo_100_2025A.pdf"


class TestParseJustificante:
    """End-to-end parsing on the fixture corpus."""

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

    def test_missing_file_raises(self) -> None:
        with pytest.raises(JustificanteParseError, match="not found"):
            parse_justificante(FIXTURES_DIR / "does_not_exist.pdf")


def _real_corpus_pdfs() -> list[Path]:
    """Every sanitised real-PDF fixture under src/aeat/tests/fixtures/justificantes/{modelo}/.

    Mirrors what ``aeat sanitize check`` runs at sanitisation time, but
    pinned in the unit suite so a parser regression on the wider corpus
    surfaces immediately. Filename convention is
    ``{ejercicio}-{period}.pdf`` per the per-modelo subdirectory.
    """
    pdfs: list[Path] = []
    for modelo_dir in sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir()):
        for pdf in sorted(modelo_dir.glob("*.pdf")):
            pdfs.append(pdf)
    return pdfs


class TestRealCorpusParses:
    """Every committed sanitised fixture parses cleanly end-to-end.

    Pinned regression — ensures a parser change doesn't silently break
    historical layouts (M100/2021 English-shape, M390/2021 column-split,
    M130 quarterly positional, etc.). The expected modelo / period /
    ejercicio is derived from the fixture's filesystem location, so a
    misnamed fixture (or a mis-bound parser output) fails loudly.
    """

    @pytest.mark.parametrize(
        "fixture",
        _real_corpus_pdfs(),
        ids=lambda p: f"{p.parent.name}/{p.stem}",
    )
    def test_corpus_pdf_parses(self, fixture: Path) -> None:
        record = parse_committed_justificante_fixture(fixture)
        assert isinstance(record, Justificante)
        # Filesystem layout identifies the fixture. Annual receipt PDFs in this
        # corpus name the filing period as 0A, but several bodies print only
        # the ejercicio; the adapter preserves the observed PDF token.
        modelo_expected = fixture.parent.name
        ejercicio_expected, period_expected = fixture.stem.split("-", 1)
        observed_period_expected = _observed_period_expected(fixture, ejercicio_expected, period_expected)
        assert record.modelo == modelo_expected, f"modelo mismatch for {fixture}: got {record.modelo}"
        assert record.period == observed_period_expected, f"period mismatch for {fixture}: got {record.period}"
        assert record.ejercicio == ejercicio_expected, f"ejercicio mismatch for {fixture}: got {record.ejercicio}"
        # Redacted NIE/NIF survives the round-trip.
        assert record.tax_id == "Y0000001S", f"tax_id mismatch for {fixture}: got {record.tax_id}"
        # CSV shape always conforms to AEAT's 8-24 uppercase alphanum.
        assert record.csv.isalnum() and record.csv.isupper()
        assert 8 <= len(record.csv) <= 24, f"csv shape failure for {fixture}: got {record.csv!r}"
        # presented_at must be a real datetime — surfaces any
        # timestamp-extraction drift across the corpus's three
        # layouts (Spanish modern, Spanish column-split, English).
        # The redacted date 01-01-1900 (or 01/01/1900 for the
        # birthday-shape sub-token) appears in every sanitised PDF.
        assert record.presented_at is not None
        # source_pdf_sha256 always populated.
        assert record.source_pdf_sha256
        assert len(record.source_pdf_sha256) == 64
        # verification_url must point at the AEAT cotejo surface.
        assert "agenciatributaria.gob.es" in str(record.verification_url)


def _observed_period_expected(fixture: Path, ejercicio: str, filename_period: str) -> str:
    explicit_annual_fixtures = {
        ("100", "2021-0A"),
        ("100", "2022-0A"),
    }
    if filename_period == "0A" and (fixture.parent.name, fixture.stem) not in explicit_annual_fixtures:
        return ejercicio
    return filename_period


class TestJustificanteErrorRehome:
    """#305 — JustificanteError inherits the shared PDF-import root."""

    def test_justificante_error_is_pdf_filing_import_error(self) -> None:
        from aeat.adapters.inbound.pdf import PdfModeloImportError

        assert issubclass(JustificanteError, PdfModeloImportError)

    def test_justificante_error_still_aeat_error(self) -> None:
        from aeat.core.errors import AeatError

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
            setattr(record, "csv", "OTHER")  # noqa: B010 — exercise frozen-model __setattr__

    def test_extra_fields_rejected(self, tmp_path: Path) -> None:
        record = self._build(tmp_path)
        kwargs = record.model_dump()
        kwargs["surprise"] = "nope"
        with pytest.raises(ValidationError):
            Justificante.model_validate(kwargs)

    def test_sha256_pattern_enforced(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            self._build(tmp_path, sha256="not-a-real-hash")
