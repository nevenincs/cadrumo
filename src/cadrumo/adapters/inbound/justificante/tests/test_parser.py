"""Unit tests for :mod:`cadrumo.adapters.inbound.justificante`.

These tests exercise the parser end-to-end against the committed fixture
PDFs under ``src/cadrumo/tests/fixtures/justificantes/``. They use real PDF
files and real pdfplumber.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import pytest
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from .....core import Period, is_aeat_csv
from .....core.directory_scan import scan_directory
from .....domain.justificante import (
    Justificante,
    JustificanteCsvNotFoundError,
    JustificanteError,
    JustificanteParseError,
    JustificanteParserBackend,
)
from .....tests import FIXTURES_DIR as _FIXTURES_ROOT
from .....tests import parse_committed_justificante_fixture
from .....tests.aeat_literal_fixtures import (
    JUSTIFICANTE_AYUDA_PATH_FIXTURE,
    JUSTIFICANTE_VERIFY_PATH_FIXTURE,
    aeat_host,
    aeat_url,
)
from .....tests.pdf_fixtures import text_pdf_bytes
from ...pdf import source_pdf_reference_path
from .. import parse_justificante, parse_justificante_bytes
from .._parsers import _TEXT_CACHE, extract_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

FIXTURES_DIR = _FIXTURES_ROOT / "justificantes"
_SEDE_HOST = aeat_host("sede")


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
        assert record.period == Period.from_year_and_code(2026, "1T")
        assert record.ejercicio == "2026"
        assert record.tax_id == "00000000T"
        assert record.csv == "ABCD1234EFGH5678"
        assert record.presentation_id == "13020260410ABCD1234EFGH5678"
        assert record.presented_at == datetime(2026, 4, 10, 11, 23, 45)
        assert record.total_a_ingresar == Decimal("1234.56")
        assert record.total_a_devolver is None
        assert urlparse(str(record.verification_url)).hostname == _SEDE_HOST
        assert record.source_pdf_path == source_pdf_reference_path(record.source_pdf_sha256)
        assert modelo_130_pdf.name not in str(record.source_pdf_path)

    def test_modelo_303_devolver(self, modelo_303_pdf: Path) -> None:
        record = parse_justificante(modelo_303_pdf)
        assert record.modelo == "303"
        assert record.period == Period.from_year_and_code(2026, "1T")
        assert record.ejercicio == "2026"
        assert record.csv == "ZZZZ9999YYYY8888"
        assert record.total_a_ingresar is None
        assert record.total_a_devolver == Decimal("450.00")
        assert record.presented_at == datetime(2026, 4, 11, 9, 5, 0)

    def test_modelo_100_annual(self, modelo_100_pdf: Path) -> None:
        record = parse_justificante(modelo_100_pdf)
        assert record.modelo == "100"
        assert record.period == Period.from_year_and_code(2025, "0A")
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
            assert record.source_pdf_path == source_pdf_reference_path(expected)
            assert pdf.name not in str(record.source_pdf_path)
            assert len(record.source_pdf_sha256) == 64

    def test_parser_is_deterministic(self, modelo_130_pdf: Path) -> None:
        """Two parses of the same file must produce identical records
        (modulo the volatile ``parsed_at`` timestamp)."""
        a = parse_justificante(modelo_130_pdf)
        b = parse_justificante(modelo_130_pdf)
        a_dict = a.model_dump(exclude={"parsed_at"})
        b_dict = b.model_dump(exclude={"parsed_at"})
        assert a_dict == b_dict

    def test_parse_bytes_matches_path_parser_without_plaintext_materialisation(self, modelo_130_pdf: Path) -> None:
        path_record = parse_justificante(modelo_130_pdf)
        bytes_record = parse_justificante_bytes(modelo_130_pdf.read_bytes())

        assert bytes_record.model_dump(exclude={"parsed_at"}) == path_record.model_dump(exclude={"parsed_at"})

    def test_explicit_backend_pdfplumber(self, modelo_130_pdf: Path) -> None:
        record = parse_justificante(
            modelo_130_pdf,
            backend=JustificanteParserBackend.PDFPLUMBER,
        )
        assert record.modelo == "130"

    def test_missing_file_raises_redacted_error(self, tmp_path: Path) -> None:
        source = tmp_path / "12345678Z-private-justificante.pdf"
        with pytest.raises(JustificanteParseError, match="not found") as exc_info:
            parse_justificante(source)

        rendered = str(exc_info.value)
        assert source.name not in rendered
        assert str(source) not in rendered
        assert "<input-pdf>" in rendered
        assert exc_info.value.context == {"path": "<input-pdf>"}
        assert exc_info.value.translated_message == "adapters.inbound.justificante.errors.parse_failed"
        assert exc_info.value.missing == ("source_pdf",)

    def test_parse_debug_log_redacts_pdf_path(
        self,
        modelo_130_pdf: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.inbound.justificante._parser"):
            parse_justificante(modelo_130_pdf)

        rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
        assert modelo_130_pdf.name not in rendered_logs
        assert str(modelo_130_pdf) not in rendered_logs
        assert "<input-pdf>" in rendered_logs


def _real_corpus_pdfs() -> list[Path]:
    """Every sanitised real-PDF fixture under src/cadrumo/tests/fixtures/justificantes/{modelo}/.

    Mirrors what ``aeat sanitize check`` runs at sanitisation time, but
    pinned in the unit suite so a parser regression on the wider corpus
    surfaces immediately. Filename convention is
    ``{ejercicio}-{period}.pdf`` per the per-modelo subdirectory.
    """
    pdfs: list[Path] = []
    for modelo_dir in sorted(p for p in scan_directory(FIXTURES_DIR, require_root=True) if p.is_dir()):
        for pdf in scan_directory(modelo_dir, pattern="*.pdf"):
            pdfs.append(pdf)
    return pdfs


# Spanish tax-identifier shape (NIF / NIE / CIF): an optional leading letter,
# 7-8 digits, and a trailing control character. Distinguishes the sanitiser's
# redacted tax-id replacement (Y0000001S / B00000001 / 00000000T) from the same
# sidecar's redacted date (01-01-1900) and presentation-id (SANITIZED...) values.
_SANITISED_TAX_ID_PATTERN = re.compile(r"^[A-Z]?\d{7,8}[A-Z0-9]$")


def _expected_tax_id_from_sidecar(fixture: Path) -> str:
    """Return the redacted tax id the fixture-provenance sidecar declares.

    The sidecar is the authoritative declaration of the synthetic values the
    sanitiser substituted, so the parser must reproduce the declared tax id
    exactly. A personal filer's redaction is a NIE/NIF; a sociedad's (Impuesto
    sobre Sociedades modelos such as Modelo 202) is a CIF -- both are declared
    per-fixture, so the expectation is derived here rather than hardcoded.
    """
    sidecar = json.loads(fixture.with_suffix(".json").read_text(encoding="utf-8"))
    # The sanitiser substitutes the same redacted tax id at every surface it
    # appears, so the tokens repeat; dedupe to the DISTINCT tax-id values and
    # require exactly one (the filer's).
    tax_ids = {
        str(replacement["synthetic"])
        for replacement in sidecar.get("replacements_applied", [])
        if _SANITISED_TAX_ID_PATTERN.match(str(replacement.get("synthetic", "")))
    }
    assert len(tax_ids) == 1, (
        f"expected exactly one distinct redacted tax-id in the {fixture.name} sidecar, found {sorted(tax_ids)!r}"
    )
    return next(iter(tax_ids))


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
        # the ejercicio; the adapter resolves both to the same annual Period.
        modelo_expected = fixture.parent.name
        ejercicio_expected, period_expected = fixture.stem.split("-", 1)
        expected_period = Period.from_year_and_code(
            int(ejercicio_expected),
            _expected_period_code(fixture, period_expected),
        )
        assert record.modelo == modelo_expected, f"modelo mismatch for {fixture}: got {record.modelo}"
        assert record.period == expected_period, f"period mismatch for {fixture}: got {record.period}"
        assert record.ejercicio == ejercicio_expected, f"ejercicio mismatch for {fixture}: got {record.ejercicio}"
        # The redacted identifier declared by the sidecar survives the round-trip.
        # It is a NIE/NIF for a personal filer (Y0000001S) but a CIF for a
        # sociedad's Impuesto sobre Sociedades modelo (e.g. Modelo 202 -> B00000001),
        # so the expectation is derived per-fixture from the authoritative
        # fixture-provenance sidecar rather than hardcoded to one shape.
        expected_tax_id = _expected_tax_id_from_sidecar(fixture)
        assert record.tax_id == expected_tax_id, (
            f"tax_id mismatch for {fixture}: got {record.tax_id}, sidecar declares {expected_tax_id}"
        )
        # CSV shape always conforms to AEAT's canonical contract.
        assert is_aeat_csv(record.csv), f"csv shape failure for {fixture}: got {record.csv!r}"
        # presented_at must be a real datetime — surfaces any
        # timestamp-extraction drift across the corpus's three
        # layouts (Spanish modern, Spanish column-split, English).
        # The redacted date 01-01-1900 (or 01/01/1900 for the
        # birthday-shape sub-token) appears in every sanitised PDF.
        assert record.presented_at is not None
        # source_pdf_sha256 always populated.
        assert record.source_pdf_sha256
        assert len(record.source_pdf_sha256) == 64
        assert record.source_pdf_path == source_pdf_reference_path(record.source_pdf_sha256)
        assert fixture.name not in str(record.source_pdf_path)
        # verification_url must point at the AEAT cotejo surface.
        assert urlparse(str(record.verification_url)).hostname == _SEDE_HOST


def _expected_period_code(fixture: Path, filename_period: str) -> str:
    # M036 uses event codes (alta/modificacion/baja) not calendar period codes.
    # The parser falls back to returning the ejercicio year, which the boundary
    # schema resolves to the annual Period.
    if fixture.parent.name == "036" or filename_period == "0A":
        return "0A"
    return filename_period


class TestJustificanteErrorRehome:
    """#305 — JustificanteError inherits the shared PDF-import root."""

    def test_justificante_error_is_pdf_filing_import_error(self) -> None:
        from ...pdf import PdfModeloImportError

        assert issubclass(JustificanteError, PdfModeloImportError)

    def test_justificante_error_still_cadrumo_error(self) -> None:
        from .....core.errors import CadrumoError

        assert issubclass(JustificanteError, CadrumoError)


@pytest.fixture(scope="module")
def non_justificante_pdf_bytes() -> bytes:
    """Synthesize once-per-module the trivial PDF that lacks a CSV label.

    Hoisting the build to module scope keeps the reportlab construction cost
    one-shot for this test module even if more tests are added later that
    need the same payload.
    """
    return text_pdf_bytes(
        (
            "AGENCIA TRIBUTARIA",
            "Modelo: 130",
            "Ejercicio: 2026",
            "Periodo: 1T",
            "NIF: 00000000T",
            "Numero de justificante: 1302026",
            "Fecha y hora de presentacion: 2026-04-10 11:00:00",
            aeat_url("sede", JUSTIFICANTE_AYUDA_PATH_FIXTURE),
        )
    )


class TestCsvDetection:
    """A PDF without a CSV must raise the dedicated error subclass."""

    def test_non_justificante_pdf_raises(
        self,
        tmp_path: Path,
        non_justificante_pdf_bytes: bytes,
    ) -> None:
        target = tmp_path / "not_a_justificante.pdf"
        target.write_bytes(non_justificante_pdf_bytes)
        with pytest.raises(JustificanteCsvNotFoundError) as exc_info:
            parse_justificante(target)
        rendered = str(exc_info.value)
        assert target.name not in rendered
        assert str(target) not in rendered
        assert "<input-pdf>" in rendered
        assert exc_info.value.context == {"path": "<input-pdf>"}
        assert exc_info.value.translated_message == "adapters.inbound.justificante.errors.parse_failed"


class TestParserDispatch:
    """Private parser-dispatch boundary behavior."""

    def test_extract_text_missing_file_raises_redacted_error(self, tmp_path: Path) -> None:
        source = tmp_path / "12345678Z-direct-parser.pdf"

        with pytest.raises(JustificanteParseError) as exc_info:
            extract_text(source, JustificanteParserBackend.PDFPLUMBER)

        rendered = str(exc_info.value)
        assert source.name not in rendered
        assert str(source) not in rendered
        assert "<input-pdf>" in rendered
        assert exc_info.value.context == {"path": "<input-pdf>"}
        assert exc_info.value.translated_message == "adapters.inbound.justificante.errors.parse_failed"
        assert exc_info.value.missing == ("source_pdf",)

    def test_extract_text_cache_key_omits_source_path(self, modelo_130_pdf: Path) -> None:
        _TEXT_CACHE.clear()

        text = extract_text(modelo_130_pdf, JustificanteParserBackend.PDFPLUMBER)

        rendered_keys = repr(tuple(_TEXT_CACHE.keys()))
        assert text
        assert modelo_130_pdf.name not in rendered_keys
        assert str(modelo_130_pdf.resolve()) not in rendered_keys


class TestJustificanteParseErrorStructuredAttributes:
    """JustificanteParseError mirrors DeclaracionParseError's structured attribute shape.

    Tests close the brittleness class where callers check message strings instead of
    typed attributes to determine the failure kind.
    """

    def test_default_attributes_are_empty(self) -> None:
        exc = JustificanteParseError("bare message")
        assert exc.missing == ()
        assert exc.malformed == ()
        assert exc.ambiguous == ()
        assert exc.coverage is None

    def test_missing_attribute_roundtrips(self) -> None:
        exc = JustificanteParseError("field absent", missing=("modelo", "period"))
        assert exc.missing == ("modelo", "period")
        assert exc.malformed == ()

    def test_malformed_attribute_roundtrips(self) -> None:
        from decimal import Decimal

        exc = JustificanteParseError("bad value", malformed=("total_a_ingresar",), coverage=Decimal("0.75"))
        assert exc.malformed == ("total_a_ingresar",)
        assert exc.coverage == Decimal("0.75")

    def test_ambiguous_attribute_roundtrips(self) -> None:
        exc = JustificanteParseError("ambiguous", ambiguous=("csv",))
        assert exc.ambiguous == ("csv",)

    def test_subclass_csv_not_found_inherits_structured_attributes(self) -> None:
        exc = JustificanteCsvNotFoundError("no csv", missing=("csv",))
        assert exc.missing == ("csv",)
        assert isinstance(exc, JustificanteParseError)

    def test_missing_field_raised_by_require(self, tmp_path: Path) -> None:
        """_require() populates missing=(field,) on the raised error."""
        from .._extract import _require

        with pytest.raises(JustificanteParseError) as exc_info:
            _require(None, "modelo")
        assert exc_info.value.missing == ("modelo",)

    def test_empty_text_raises_missing_text(self, tmp_path: Path) -> None:
        """Empty text raises with missing=('text',)."""
        from .._extract import extract_justificante

        pdf = tmp_path / "empty.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        with pytest.raises(JustificanteParseError) as exc_info:
            extract_justificante("", pdf)
        assert exc_info.value.missing == ("text",)


class TestJustificanteModel:
    """Strict-mode guardrails on the :class:`Justificante` pydantic model."""

    def _build(
        self,
        tmp_path: Path,
        *,
        sha256: str | None = None,
    ) -> Justificante:
        pdf = tmp_path / "source.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%EOF\n")
        return Justificante(
            csv="ABCD1234EFGH5678",
            modelo="130",
            ejercicio="2026",
            period=Period.from_year_and_code(2026, "1T"),
            presentation_id=None,
            presented_at=datetime(2026, 4, 10, 11, 23, 45),
            tax_id="00000000T",
            total_a_ingresar=Decimal("10.00"),
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(
                aeat_url("sede", JUSTIFICANTE_VERIFY_PATH_FIXTURE),
            ),
            source_pdf_path=pdf,
            source_pdf_sha256=sha256 or hashlib.sha256(pdf.read_bytes()).hexdigest(),
            parsed_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
        )

    def test_model_is_frozen(self, tmp_path: Path) -> None:
        record = self._build(tmp_path)
        with pytest.raises(ValidationError):
            record.csv = "OTHER"

    def test_extra_fields_rejected(self, tmp_path: Path) -> None:
        record = self._build(tmp_path)
        kwargs = record.model_dump()
        kwargs["surprise"] = "nope"
        with pytest.raises(ValidationError):
            Justificante.model_validate(kwargs)

    def test_sha256_pattern_enforced(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            self._build(tmp_path, sha256="not-a-real-hash")
