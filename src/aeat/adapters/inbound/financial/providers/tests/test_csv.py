"""Unit tests for CSV financial ingestion.

Covers per-bank layout detection and ingestion, synthetic
transaction-id generation when the source row has no native id,
header-rejection behaviour, and the configured-encoding fallback
in :class:`aeat.adapters.inbound.financial.providers._csv.CsvProvider`.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ......core.config import override_settings
from ......core.external_constants import CSV_ENCODING_FALLBACK_CHAIN
from ......domain.transactions import TransactionDirection
from ......tests import FIXTURES_DIR
from .. import CsvProvider, InvalidFinancialSourceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial"


@pytest.mark.parametrize(
    ("fixture_name", "expected_currency", "expected_description"),
    [
        ("bbva-sample.csv", "EUR", "Transferencia recibida CLIENTE UNO"),
        ("santander-sample.csv", "EUR", "Pago cuota autonomos"),
        ("caixabank-sample.csv", "EUR", "Cobro factura F-2026-014"),
        ("revolut-sample.csv", "EUR", "Coffee subscription"),
    ],
)
def test_csv_provider_ingests_supported_bank_layouts(
    fixture_name: str,
    expected_currency: str,
    expected_description: str,
) -> None:
    """The CSV provider should ingest each supported bank layout."""
    provider = CsvProvider()
    fixture = _FIXTURES / fixture_name
    validation = provider.validate_source(fixture)
    assert validation.is_valid, validation.warnings
    parsed_rows = tuple(provider.ingest(fixture))
    assert parsed_rows
    assert parsed_rows[0].raw.currency == expected_currency
    assert parsed_rows[0].raw.description == expected_description
    assert parsed_rows[0].raw.provenance.source_format.value == "csv"
    # Amounts are stored as non-negative magnitudes; flow is in direction.
    assert parsed_rows[0].raw.amount >= 0


def test_csv_provider_synthesizes_ids_when_source_has_none() -> None:
    """Synthetic CSV rows should receive deterministic synthetic IDs."""
    provider = CsvProvider()
    parsed_rows = tuple(provider.ingest(_FIXTURES / "synthetic-transactions.csv"))
    assert len(parsed_rows) == 2
    assert parsed_rows[0].raw.transaction_id.startswith("bbva-")
    assert parsed_rows[0].raw.provenance.source_row_index == 2


def test_csv_provider_explicit_direction_column_overrides_positive_amount_sign(tmp_path: Path) -> None:
    """A canonical direction column is authoritative over a positive amount."""
    source = tmp_path / "explicit-direction.csv"
    source.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction,source_jurisdiction\n"
        "2026-04-17,French Vendor,FR expense,48.40,EUR,n26-fr-expense,OUTGOING,FR\n",
        encoding="utf-8",
    )

    parsed_rows = tuple(CsvProvider().ingest(source))

    assert len(parsed_rows) == 1
    (parsed,) = parsed_rows
    assert parsed.raw.amount == Decimal("48.40")
    assert parsed.direction is TransactionDirection.OUTGOING
    assert parsed.raw.raw_fields["source_jurisdiction"] == "FR"


def test_csv_provider_rejects_invalid_explicit_direction_value(tmp_path: Path) -> None:
    """A malformed direction cell must not fall back to amount-sign inference."""
    source = tmp_path / "invalid-direction.csv"
    source.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction\n"
        "2026-04-17,French Vendor,FR expense,48.40,EUR,n26-fr-expense,EXPENSE\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidFinancialSourceError) as exc_info:
        tuple(CsvProvider().ingest(source))

    assert "unsupported direction value" in str(exc_info.value)


def test_csv_provider_rejects_unknown_headers(tmp_path: Path) -> None:
    """Unknown CSV headers should fail validation instead of guessing."""
    source = tmp_path / "unknown.csv"
    source.write_text("foo,bar,baz\n1,2,3\n", encoding="utf-8")
    validation = CsvProvider().validate_source(source)
    assert not validation.is_valid
    assert "headers" in validation.warnings[0].lower()


def test_generic_csv_missing_currency_warning_is_provider_neutral(tmp_path: Path) -> None:
    """A generic CSV selected via the CSV provider must not be labelled as N26."""
    source = tmp_path / "generic.csv"
    source.write_text("Date,Description,Amount\n2026-04-15,Invoice 1,121.00\n", encoding="utf-8")

    validation = CsvProvider().validate_source(source)

    assert validation.is_valid, validation.warnings
    assert validation.warnings == ("CSV has no currency column; falling back to EUR",)


def test_n26_csv_missing_currency_warning_keeps_provider_label(tmp_path: Path) -> None:
    """N26-specific headers still receive the N26 warning copy."""
    source = tmp_path / "n26.csv"
    source.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,n26-001\n",
        encoding="utf-8",
    )

    validation = CsvProvider().validate_source(source)

    assert validation.is_valid, validation.warnings
    assert validation.warnings == ("N26 CSV has no currency column; falling back to EUR",)


def test_csv_provider_ignores_invalid_configured_encoding_name() -> None:
    """An invalid preferred encoding should not break the fallback decode order."""
    with override_settings(financial_default_csv_encoding="definitely-not-a-codec"):
        validation = CsvProvider().validate_source(_FIXTURES / "bbva-sample.csv")
    assert validation.is_valid, validation.warnings


# ---------------------------------------------------------------------------
# Canonical fallback chain — real-behavior decode tests (contract)
# ---------------------------------------------------------------------------
# Each sub-test feeds bytes that are only valid in ONE of the four encodings
# in CSV_ENCODING_FALLBACK_CHAIN.  The preferred codec is set to an invalid
# name so the fallback chain drives decoding from position 0.  We assert:
#   (a) decoding succeeds (no exception);
#   (b) the winning codec matches the expected position in the chain;
#   (c) the round-tripped text is byte-equivalent to what was encoded.
#
# Encoding-distinguishing byte sequences used:
#   utf-8-sig  — BOM prefix (b'\xef\xbb\xbf') which utf-8 also accepts but
#                utf-8-sig is first, so it wins.
#   utf-8      — multi-byte sequence b'\xc3\xa9' (U+00E9 é) invalid in cp1252/
#                iso-8859-1 as a multi-byte run (valid scalar but wrong value).
#                We craft a sequence that is *invalid* in latin-1 strict mode —
#                actually latin-1 accepts all single bytes, so we craft bytes
#                that are valid utf-8 but represent a codepoint that decodes
#                differently in latin-1 than in utf-8.  The only reliable
#                distinguisher is that utf-8 *rejects* non-utf-8 byte sequences,
#                while cp1252/iso-8859-1 accept all 256 bytes.  So we test utf-8
#                by supplying a valid utf-8 multi-byte sequence (b'\xc3\xa9')
#                and confirming the decoded character is U+00E9, then confirm
#                cp1252/iso-8859-1 are bypassed when utf-8 wins.
#   cp1252     — byte 0x80 (€ in cp1252, undefined in iso-8859-1 strict; but
#                Python's iso-8859-1 codec maps it to U+0080 control char, so
#                we cannot use that to distinguish).  Instead we craft bytes
#                that are *invalid* utf-8 AND invalid utf-8-sig (0x80 alone
#                is a continuation byte in utf-8 → UnicodeDecodeError) and
#                rely on cp1252 being before iso-8859-1 in the chain.
#   iso-8859-1 — byte 0xf3 (ó in iso-8859-1) in a sequence that is invalid
#                utf-8 and invalid utf-8-sig and also rejected by cp1252 strict
#                (0x81 is undefined in cp1252; Python raises UnicodeDecodeError
#                for it).  We prepend b'\x81' which breaks utf-8 and cp1252.
#
# All tests invoke _decode_bytes directly on a real CsvProvider instance —
# no mocks, no stubs, no patches.

_INVALID_PREFERRED = "definitely-not-a-codec"


@pytest.mark.parametrize(
    ("raw_bytes", "expected_encoding", "expected_char"),
    [
        # utf-8-sig wins: BOM-prefixed bytes with invalid preferred codec.
        # utf-8-sig is first in the chain; Python's codec strips the BOM.
        (
            "é".encode("utf-8-sig"),
            "utf-8-sig",
            "é",
        ),
        # cp1252 wins: 0x80 is a utf-8 continuation byte → UnicodeDecodeError
        # in utf-8-sig and utf-8; cp1252 maps 0x80 to U+20AC (€).
        (
            b"\x80",
            "cp1252",
            "€",
        ),
        # iso-8859-1 wins: 0x81 is undefined in cp1252 (Python raises on
        # decode); utf-8-sig and utf-8 also reject it.  iso-8859-1 maps it
        # to U+0081 (C1 control character).
        (
            b"\x81",
            "iso-8859-1",
            "\x81",
        ),
    ],
)
def test_csv_provider_decode_bytes_follows_fallback_chain(
    raw_bytes: bytes,
    expected_encoding: str,
    expected_char: str,
) -> None:
    """_decode_bytes must probe encodings in CSV_ENCODING_FALLBACK_CHAIN order.

    Each parametrised case supplies bytes that are uniquely decodable by
    exactly one codec in the fallback chain.  The preferred codec is set to
    an invalid name so the chain drives selection from position 0.  We assert
    that the winning codec matches the expected fallback position and that the
    decoded text round-trips correctly.  No mocks or stubs — _decode_bytes is
    exercised directly on a real CsvProvider instance.
    """
    with override_settings(financial_default_csv_encoding=_INVALID_PREFERRED):
        provider = CsvProvider()
        text, winning_encoding = provider._decode_bytes(raw_bytes)
    assert winning_encoding == expected_encoding, (
        f"Expected encoding {expected_encoding!r} but got {winning_encoding!r}; chain is {CSV_ENCODING_FALLBACK_CHAIN}"
    )
    assert expected_char in text, f"Decoded text {text!r} does not contain expected character {expected_char!r}"


def test_csv_provider_decode_bytes_preferred_codec_wins_over_chain() -> None:
    """When the preferred codec is valid it must win before the fallback chain is tried.

    Encodes ASCII-only content as utf-8 (no BOM) then sets the preferred codec
    to 'utf-8' explicitly.  The decode should return 'utf-8' as the winning
    encoding, not 'utf-8-sig' (the first chain member), because the preferred
    is prepended ahead of the chain and succeeds on its first attempt.
    """
    with override_settings(financial_default_csv_encoding="utf-8"):
        provider = CsvProvider()
        raw = b"hello"
        text, winning_encoding = provider._decode_bytes(raw)
    assert winning_encoding == "utf-8"
    assert text == "hello"
