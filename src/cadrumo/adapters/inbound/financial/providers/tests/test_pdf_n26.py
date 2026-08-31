"""Unit tests for the N26 PDF financial ingestion provider.

Exercises :class:`cadrumo.adapters.inbound.financial.providers.PdfN26Provider`
end-to-end against committed N26 statement fixtures. Each fixture is paired
with a manually transcribed expected-row JSON so the test asserts that the
provider's parsed transactions match the human-verified ground truth.

Detection invariant
-------------------
Every corpus PDF must be detected as ``PdfN26Provider`` by
:func:`detect_provider`. A failure here means either the detection
heuristic is broken or the fixture is not a valid N26 statement PDF —
both are loud failures rather than silent ones.

Corpus discipline
-----------------
``PdfN26Provider.verification_source`` must be
``"synthetic_from_bank_published_text"`` (fixtures generated from
portfolio-performance sanitised text) until real operator statements
replace them, at which point ``verification_source`` is upgraded to
``"real_bank_corpus_pdf"`` and ``provisional_pending_specimen`` stays
``False``.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from ......domain.transactions.enums import TransactionDirection
from ......tests import FIXTURES_DIR
from .._detection import detect_provider
from .._pdf_n26 import PdfN26Provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial" / "n26"
_N26_FIXTURE_PAIRS = (
    ("n26-savings-2024-06.pdf", "n26-savings-2024-06.expected.json"),
    ("n26-savings-2025-01.pdf", "n26-savings-2025-01.expected.json"),
    ("n26-savings-2025-05.pdf", "n26-savings-2025-05.expected.json"),
)
_EXPECTED_ROWS = TypeAdapter(list[dict[str, object]])


def _load_expected(name: str) -> list[dict[str, object]]:
    return _EXPECTED_ROWS.validate_json((_FIXTURES / name).read_text(encoding="utf-8"))


def test_pdf_n26_provider_ingests_fixture_rows() -> None:
    """The provider must emit the manually transcribed rows for each fixture."""
    for fixture_name, expected_name in _N26_FIXTURE_PAIRS:
        provider = PdfN26Provider()
        fixture = _FIXTURES / fixture_name
        validation = provider.validate_source(fixture)
        assert validation.is_valid, (fixture_name, validation.warnings)
        parsed_rows = tuple(provider.ingest(fixture))
        expected_rows = _load_expected(expected_name)
        assert len(parsed_rows) == len(expected_rows), fixture_name
        for parsed, expected in zip(parsed_rows, expected_rows, strict=True):
            transaction = parsed.raw
            assert transaction.booked_date.isoformat() == expected["booked_date"], fixture_name
            expected_value_date = expected["value_date"]
            assert (
                transaction.value_date.isoformat() if transaction.value_date is not None else None
            ) == expected_value_date, fixture_name
            # The expected JSON carries the bank statement's signed ground truth.
            # The parser stores the absolute magnitude and lifts the sign into
            # the authoritative direction at the parse boundary.
            expected_signed = Decimal(str(expected["amount"]))
            assert transaction.amount == abs(expected_signed), fixture_name
            assert parsed.direction is (
                TransactionDirection.OUTGOING if expected_signed < Decimal("0") else TransactionDirection.INCOMING
            ), fixture_name
            assert transaction.currency == expected["currency"], fixture_name
            assert transaction.counterparty == expected["counterparty"], fixture_name
            assert transaction.description == expected["description"], fixture_name
            assert transaction.provenance.source_row_index == expected["source_row_index"], fixture_name
            assert transaction.provenance.source_format.value == "pdf", fixture_name
            assert transaction.provider_transaction_id.startswith("n26-pdf-"), fixture_name
            assert transaction.provider_transaction_id.endswith(f"-{expected['source_row_index']}"), fixture_name
            assert transaction.raw_fields["statement_period"], fixture_name
            assert transaction.raw_fields["description_line"], fixture_name


def test_pdf_n26_provider_rejects_non_n26_pdf(tmp_path: Path) -> None:
    """A generic PDF should not validate as an N26 statement."""
    source = tmp_path / "generic.pdf"
    source.write_bytes((_FIXTURES / "n26-savings-2025-01.pdf").read_bytes().replace(b"N26 Bank AG", b"Other Bank "))
    validation = PdfN26Provider().validate_source(source)
    assert not validation.is_valid
    assert "n26" in validation.warnings[0].lower()


def test_pdf_n26_provider_invalid_pdf_does_not_expose_filename(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Parser teardown diagnostics must redact the caller-provided PDF path."""
    source = tmp_path / "12345678Z-private-account-statement.pdf"
    source.write_bytes(b"not a valid PDF document")

    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.inbound.financial.providers._pdf_n26"):
        validation = PdfN26Provider().validate_source(source)

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    rendered_warnings = "\n".join(validation.warnings)
    assert not validation.is_valid
    assert source.name not in rendered_logs
    assert source.name not in rendered_warnings
    assert str(source) not in rendered_logs
    assert str(source) not in rendered_warnings
    assert "<input-pdf>" in rendered_logs
    assert "<input-pdf>" in rendered_warnings
    assert all(record.exc_info is None for record in caplog.records)


# ---------------------------------------------------------------------------
# Detection invariant: every N26 corpus PDF must detect as PdfN26Provider
# ---------------------------------------------------------------------------


def test_detect_provider_identifies_n26_corpus_pdf() -> None:
    """detect_provider must return PdfN26Provider for every N26 corpus fixture.

    A mis-detection (returning None or a different provider) signals either
    that the detection heuristic is broken or the fixture is not a valid N26
    statement — both are real failures that must surface loudly.
    """
    for fixture_name, _expected_name in _N26_FIXTURE_PAIRS:
        fixture = _FIXTURES / fixture_name
        provider = detect_provider(fixture)
        assert provider is not None, f"detect_provider returned None for {fixture_name}"
        assert isinstance(provider, PdfN26Provider), (
            f"expected PdfN26Provider, got {type(provider).__name__} for {fixture_name}"
        )


# ---------------------------------------------------------------------------
# Corpus discipline: verification_source and provisional_pending_specimen
# ---------------------------------------------------------------------------


def test_pdf_n26_provider_verification_source_is_declared() -> None:
    """PdfN26Provider must declare its corpus verification source.

    The fixture corpus is synthetic PDFs generated from the
    portfolio-performance sanitised text dumps.  Until real operator
    statements are acquired and round-trip-verified, the provider's
    ``verification_source`` is ``"synthetic_from_bank_published_text"``
    and ``provisional_pending_specimen`` is ``False`` (the synthetic
    corpus is sufficient to confirm the regex family is correct; no
    round-trip gap exists — it only becomes provisional if the corpus
    is known to be structurally incompatible with real layouts).
    """
    assert PdfN26Provider.verification_source == "synthetic_from_bank_published_text"
    assert PdfN26Provider.provisional_pending_specimen is False


# ---------------------------------------------------------------------------
# DEFAULT_CURRENCY enrollment (contract)
# ---------------------------------------------------------------------------


def test_extract_statement_currency_uses_default_currency() -> None:
    """_extract_statement_currency must return DEFAULT_CURRENCY, not a bare 'EUR' literal.

    The function detects the statement currency from page text and returns it.
    Enrollment means both the pattern check and the return value must reference
    DEFAULT_CURRENCY so that the authoritative constant governs all currency logic.
    """
    from ......core.external_constants import DEFAULT_CURRENCY
    from .._pdf_n26 import _extract_statement_currency

    # A page with a EUR marker must yield DEFAULT_CURRENCY.
    pages = (("Umsatz 100,00 EUR Kontostand",),)
    result = _extract_statement_currency(pages)
    assert result == DEFAULT_CURRENCY


def test_extract_statement_currency_raises_on_missing_currency() -> None:
    """Pages with no currency marker must raise InvalidFinancialSourceError."""
    from .._base import InvalidFinancialSourceError
    from .._pdf_n26 import _extract_statement_currency

    pages = (("no currency info here",),)
    with pytest.raises(InvalidFinancialSourceError):
        _extract_statement_currency(pages)
