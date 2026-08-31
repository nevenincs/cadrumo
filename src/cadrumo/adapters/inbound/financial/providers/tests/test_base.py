"""Unit tests for financial provider boundary models and detection.

Exercises the strict + frozen :class:`RawTransaction` and
:class:`ProviderValidation` records, the
:func:`detect_provider` extension/sniff dispatch, the
:func:`parse_amount_value` decimal-separator override, and the
corpus-discipline class-variable contract on all registered providers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ......core.tabular import coerce_cell_text
from ......domain.transactions.raw_transaction import RawTransaction, SourceFormat
from ......tests import FIXTURES_DIR
from .._detection import detect_provider
from .._ofx import OfxProvider
from .._pdf_n26 import PdfN26Provider
from .._xlsx import XlsxProvider
from ..base import (
    BankStatementParseError,
    FinancialValidationError,
    ProviderValidation,
    archive_cell_text,
    parse_amount_value,
)
from ..csv import CsvProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial"


def test_raw_transaction_round_trip_uses_mapping_field() -> None:
    """RawTransaction should round-trip through JSON with immutable raw_fields."""
    original = RawTransaction.model_validate(
        {
            "provider_transaction_id": "csv-provider-deadbeef-2",
            "booked_date": date(2026, 4, 10),
            "value_date": date(2026, 4, 10),
            "amount": Decimal("123.45"),
            "currency": "eur",
            "counterparty": "Example SL",
            "description": "Consulting payment",
            "provenance": {
                "source_path": _FIXTURES / "synthetic-transactions.csv",
                "source_sha256": "a" * 64,
                "source_row_index": 2,
                "source_format": SourceFormat.CSV,
                "ingested_at": datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
                "provider_name": "CSV provider",
            },
            "raw_fields": {"Concepto": "Consulting payment"},
        },
    )
    round_tripped = RawTransaction.model_validate_json(original.model_dump_json())
    assert round_tripped == original
    assert round_tripped.currency == "EUR"


def test_provider_validation_defaults() -> None:
    """ProviderValidation should remain a strict frozen boundary record."""
    validation = ProviderValidation(is_valid=True)
    assert validation.warnings == ()
    assert validation.detected_encoding is None
    assert validation.detected_dialect is None


def test_detect_provider_uses_extension_and_validation() -> None:
    """detect_provider should select the correct provider for each fixture."""
    for fixture_name, provider_name in (
        ("synthetic-transactions.csv", "CSV provider"),
        ("synthetic-transactions.xlsx", "XLSX provider"),
        ("synthetic-transactions.ofx", "OFX provider"),
        ("n26/n26-savings-2025-01.pdf", "n26-pdf"),
    ):
        provider = detect_provider(_FIXTURES / fixture_name)
        assert provider is not None, fixture_name
        assert provider.name == provider_name, fixture_name


def test_parse_amount_value_respects_explicit_decimal_separator() -> None:
    """Explicit decimal separators should disambiguate locale-specific amounts."""
    assert parse_amount_value("1.234", decimal_separator=",") == Decimal("1234")
    assert parse_amount_value("1,234", decimal_separator=".") == Decimal("1234")
    assert parse_amount_value("1.234,56", decimal_separator=",") == Decimal("1234.56")
    assert parse_amount_value("1,234.56", decimal_separator=".") == Decimal("1234.56")


def test_financial_archive_cell_text_binds_the_canonical_temporal_policy() -> None:
    """The provider policy must delegate to the sole core coercion authority."""
    stamp = datetime(2026, 4, 17, 10, 30, 5, 123456)
    assert archive_cell_text(stamp) == coerce_cell_text(stamp, temporal_as_iso=True)
    assert archive_cell_text(stamp) == "2026-04-17 10:30:05"


# Scientific notation, with the magnitude the shape really denotes. Sanitisation
# strips non-numeric characters so a currency symbol is tolerated; for an
# exponent marker that same strip silently rewrote the magnitude instead of
# failing, so ``1.23E+05`` (123.000,00) survived as ``1.2305`` and ``2E+10``
# (20.000.000.000,00) as ``210``. A spreadsheet re-export of a large amount is a
# real source of this shape.
_SCIENTIFIC_NOTATION_AMOUNTS = (
    ("1.23E+05", Decimal("123000")),
    ("1.23e5", Decimal("123000")),
    ("2E+10", Decimal("20000000000")),
    ("1E3", Decimal("1000")),
)


@pytest.mark.parametrize(("raw", "true_magnitude"), _SCIENTIFIC_NOTATION_AMOUNTS)
def test_parse_amount_value_refuses_scientific_notation(raw: str, true_magnitude: Decimal) -> None:
    """A scientific-notation amount refuses rather than becoming a wrong number.

    The refusal is the whole point: the old strip produced a *parseable,
    plausible* value that differed from the true magnitude by orders of
    magnitude and then fed the ledger and every modelo aggregation built on it.
    """
    with pytest.raises(FinancialValidationError):
        parse_amount_value(raw)
    # Anchor the severity of the old behaviour: the silently-produced value was
    # not merely imprecise, it was a different number entirely.
    assert Decimal(raw) == true_magnitude


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Currency symbols and codes stay tolerated — the strip exists for these.
        ("100 EUR", Decimal("100")),
        ("€1.234,56", Decimal("1234.56")),
        # The three sign conventions are unaffected.
        ("(123.45)", Decimal("-123.45")),
        ("123.45-", Decimal("-123.45")),
        ("-99.99", Decimal("-99.99")),
        # Separator inference is unaffected.
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        ("0,00", Decimal("0.00")),
        ("1234", Decimal("1234")),
    ],
)
def test_parse_amount_value_tolerance_is_unchanged(raw: str, expected: Decimal) -> None:
    """The exponent refusal must not narrow the bank-export grammar elsewhere."""
    assert parse_amount_value(raw) == expected


# ---------------------------------------------------------------------------
# Corpus discipline: all registered providers must declare class-level attrs
# ---------------------------------------------------------------------------

_ALL_PROVIDERS = [CsvProvider(), OfxProvider(), XlsxProvider(), PdfN26Provider()]
_VALID_VERIFICATION_SOURCES = frozenset({"real_bank_corpus_pdf", "synthetic_from_bank_published_text", "no_corpus"})


def test_provider_declares_verification_source() -> None:
    """Every provider must declare a valid verification_source class variable.

    This is a structural gate: a newly enrolled provider that forgets to
    declare the attribute fails loudly here rather than shipping with an
    unverified corpus posture.
    """
    for provider in _ALL_PROVIDERS:
        source = getattr(type(provider), "verification_source", None)
        assert source is not None, f"{type(provider).__name__} is missing verification_source"
        assert source in _VALID_VERIFICATION_SOURCES, (
            f"{type(provider).__name__}.verification_source={source!r} "
            f"is not one of {sorted(_VALID_VERIFICATION_SOURCES)}"
        )


def test_provider_declares_provisional_pending_specimen() -> None:
    """Every provider must declare provisional_pending_specimen as a bool.

    A provider with no_corpus must set it True; a provider with a
    confirmed corpus round-trip sets it False.
    """
    for provider in _ALL_PROVIDERS:
        flag = getattr(type(provider), "provisional_pending_specimen", None)
        assert flag is not None, f"{type(provider).__name__} is missing provisional_pending_specimen"
        assert isinstance(flag, bool), (
            f"{type(provider).__name__}.provisional_pending_specimen must be bool, got {type(flag)}"
        )


def test_provider_no_corpus_implies_provisional() -> None:
    """A provider with verification_source='no_corpus' must be provisional.

    This invariant prevents a no_corpus provider from shipping with
    provisional_pending_specimen=False, which would falsely assert that
    an absent corpus has been round-trip-verified.
    """
    for provider in _ALL_PROVIDERS:
        cls = type(provider)
        if getattr(cls, "verification_source", None) == "no_corpus":
            assert getattr(cls, "provisional_pending_specimen", False) is True, (
                f"{cls.__name__}: no_corpus provider must have provisional_pending_specimen=True"
            )


# ---------------------------------------------------------------------------
# BankStatementParseError structured attributes
# ---------------------------------------------------------------------------


def test_bank_statement_parse_error_default_attributes() -> None:
    """BankStatementParseError default-constructs with empty structured attrs."""
    err = BankStatementParseError("page layout changed")
    assert err.missing == ()
    assert err.malformed == ()
    assert err.ambiguous == ()
    assert err.coverage is None
    assert str(err) == "page layout changed"


def test_bank_statement_parse_error_carries_structured_attributes() -> None:
    """BankStatementParseError exposes typed attributes callers can assert on."""
    err = BankStatementParseError(
        "extraction incomplete",
        missing=("booked_date",),
        malformed=("amount",),
        ambiguous=("currency",),
        coverage=Decimal("0.5"),
    )
    assert err.missing == ("booked_date",)
    assert err.malformed == ("amount",)
    assert err.ambiguous == ("currency",)
    assert err.coverage == Decimal("0.5")


def test_bank_statement_parse_error_is_financial_provider_error() -> None:
    """BankStatementParseError is catchable as FinancialProviderError."""
    from ..base import FinancialProviderError

    err = BankStatementParseError("layout drift")
    assert isinstance(err, FinancialProviderError)
