"""Unit tests for the N26 PDF financial ingestion provider.

Exercises :class:`aeat.adapters.inbound.financial.providers.PdfN26Provider`
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

import json
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.tests import FIXTURES_DIR

from .. import PdfN26Provider
from ._detection import detect_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_FIXTURES = FIXTURES_DIR / "financial" / "n26"


def _load_expected(name: str) -> list[dict[str, object]]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "expected_name"),
    [
        ("n26-savings-2024-06.pdf", "n26-savings-2024-06.expected.json"),
        ("n26-savings-2025-01.pdf", "n26-savings-2025-01.expected.json"),
        ("n26-savings-2025-05.pdf", "n26-savings-2025-05.expected.json"),
    ],
)
def test_pdf_n26_provider_ingests_fixture_rows(
    fixture_name: str,
    expected_name: str,
) -> None:
    """The provider must emit the manually transcribed rows for each fixture."""
    provider = PdfN26Provider()
    fixture = _FIXTURES / fixture_name
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    transactions = tuple(provider.ingest(fixture))
    expected_rows = _load_expected(expected_name)
    assert len(transactions) == len(expected_rows)
    for transaction, expected in zip(transactions, expected_rows, strict=True):
        assert transaction.booked_date.isoformat() == expected["booked_date"]
        expected_value_date = expected["value_date"]
        assert (
            transaction.value_date.isoformat() if transaction.value_date is not None else None
        ) == expected_value_date
        assert transaction.amount == Decimal(str(expected["amount"]))
        assert transaction.currency == expected["currency"]
        assert transaction.counterparty == expected["counterparty"]
        assert transaction.description == expected["description"]
        assert transaction.provenance.source_row_index == expected["source_row_index"]
        assert transaction.provenance.source_format.value == "pdf"
        assert transaction.transaction_id.startswith("n26-pdf-")
        assert transaction.transaction_id.endswith(f"-{expected['source_row_index']}")
        assert transaction.raw_fields["statement_period"]
        assert transaction.raw_fields["description_line"]


def test_pdf_n26_provider_rejects_non_n26_pdf(tmp_path: Path) -> None:
    """A generic PDF should not validate as an N26 statement."""
    source = tmp_path / "generic.pdf"
    source.write_bytes((_FIXTURES / "n26-savings-2025-01.pdf").read_bytes().replace(b"N26 Bank AG", b"Other Bank "))
    validation = PdfN26Provider().validate_source(source)
    assert not validation.is_valid
    assert "n26" in validation.warnings[0].lower()


# ---------------------------------------------------------------------------
# Detection invariant: every N26 corpus PDF must detect as PdfN26Provider
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "n26-savings-2024-06.pdf",
        "n26-savings-2025-01.pdf",
        "n26-savings-2025-05.pdf",
    ],
)
def test_detect_provider_identifies_n26_corpus_pdf(fixture_name: str) -> None:
    """detect_provider must return PdfN26Provider for every N26 corpus fixture.

    A mis-detection (returning None or a different provider) signals either
    that the detection heuristic is broken or the fixture is not a valid N26
    statement — both are real failures that must surface loudly.
    """
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
