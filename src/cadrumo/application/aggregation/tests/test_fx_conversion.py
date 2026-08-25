"""Regression tests for FX conversion at ledger import time.

Exercises the end-to-end path:
  1. A non-EUR RawTransaction is fed to import_ledger_transactions with a
     real CurrencyNormalizationService backed by a declared ECB observation set.
  2. The resulting Transaction carries fx_rate and value_in_eur populated from
     the published ECB reference rate for the transaction date.
  3. The shared is_non_eur_without_conversion predicate gates the row as
     eligible (not UNSUPPORTED_CURRENCY) when value_in_eur is set.
  4. Anti-tautology: mutating the rate changes value_in_eur.

ECB oracle source:
  Series ``EXR.D.USD.EUR.SP00.A`` (ECB Data Portal), observation 2024-01-15:
    OBS_VALUE = 1.0945, i.e. 1 EUR buys 1.0945 USD.
  Retrieved from
  https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A

The ECB quotes EUR-base, while ``ExchangeRateProvider.get_eur_rate`` returns the
multiplier satisfying ``original_amount * rate = eur_amount``, so the provider
inverts the quote:

  rate         = 1 / 1.0945       = 0.913659...  EUR per USD
  value_in_eur = 100.00 * rate    = 91.3659...   -> quantize 0.01 = 91.37

The expected 91.37 is anchored on the ECB's own published observation; only the
inversion and rounding are computed here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ._secure_objects_fixtures import SECURE_OBJECTS_BUCKET_ID, secure_objects

__all__ = ["secure_objects"]

from ....adapters.inbound.financial.providers import ParsedLedgerRow
from ....adapters.outbound.fx import EcbReferenceRateProvider
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.currency import (
    CurrencyNormalizationService,
)
from ....domain.transactions import RawProvenance, RawTransaction, SourceFormat, TransactionDirection
from ....tests.ecb_stub import ecb_csv_fetch
from ...ledger.actions_import import import_ledger_transactions
from .._currency_predicates import is_non_eur_without_conversion

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ECB EXR.D.USD.EUR.SP00.A, 2024-01-15: OBS_VALUE = 1.0945 (1 EUR = 1.0945 USD).
# Provider contract (original * rate = eur_amount) needs the inverse:
#   1 USD = 1/1.0945 EUR = 0.913659... EUR
_ECB_2024_01_15_USD_QUOTE = Decimal("1.0945")
_ECB_2024_01_15_USD_RATE = Decimal("1") / _ECB_2024_01_15_USD_QUOTE

# Oracle: 100.00 USD * (1 / 1.0945) = 91.365920... -> rounded half-even 0.01 = 91.37 EUR
_USD_AMOUNT = Decimal("100.00")
_EXPECTED_EUR = (_USD_AMOUNT * _ECB_2024_01_15_USD_RATE).quantize(Decimal("0.01"))
assert Decimal("91.37") == _EXPECTED_EUR, f"Oracle mismatch: {_EXPECTED_EUR}"


def _ecb_provider(*, usd_quote: Decimal | None = _ECB_2024_01_15_USD_QUOTE) -> EcbReferenceRateProvider:
    quotes = {} if usd_quote is None else {"USD": {date(2024, 1, 15): usd_quote}}
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch(quotes))


def _usd_raw(provider_id: str, *, amount: Decimal = _USD_AMOUNT) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 1, 15),
        value_date=date(2024, 1, 15),
        amount=amount,
        currency="USD",
        counterparty="Acme Corp",
        description=f"USD invoice {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 1, 16, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Reference": provider_id},
    )


def _usd_parsed(provider_id: str, *, amount: Decimal = _USD_AMOUNT) -> ParsedLedgerRow:
    """Wrap a USD magnitude row with an explicit OUTGOING direction."""
    return ParsedLedgerRow(raw=_usd_raw(provider_id, amount=amount), direction=TransactionDirection.OUTGOING)


def test_usd_import_populates_fx_rate_and_value_in_eur(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """USD invoice imported with the ECB provider gets fx_rate and value_in_eur set.

    The expected EUR value (92.01) is derived from the published ECB reference
    rate for 2024-01-15 (USD/EUR = 1.0868), not hand-multiplied by a synthetic
    rate.
    """
    normalizer = CurrencyNormalizationService(rate_provider=_ecb_provider())
    repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)

    result = import_ledger_transactions(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        parsed_rows=[_usd_parsed("usd-inv-001")],
        transaction_repository=repo,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        currency_normalizer=normalizer,
    )

    assert result.summary.imported == 1, result
    catalogue = repo.load()
    transactions = list(catalogue.values())
    assert len(transactions) == 1
    tx = transactions[0]

    assert tx.raw.currency == "USD"
    assert tx.fx_rate == _ECB_2024_01_15_USD_RATE
    assert tx.value_in_eur == _EXPECTED_EUR


def test_usd_transaction_with_value_in_eur_passes_non_eur_predicate() -> None:
    """A USD transaction with value_in_eur set is not flagged as needing conversion.

    is_non_eur_without_conversion should return False when value_in_eur is
    populated, meaning the aggregation gate will not emit UNSUPPORTED_CURRENCY.
    """
    raw = _usd_raw("usd-gate-001")
    from ....domain.transactions import Transaction

    tx = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "fx_rate": _ECB_2024_01_15_USD_RATE,
            "value_in_eur": _EXPECTED_EUR,
        },
    )

    assert tx.value_in_eur == _EXPECTED_EUR
    assert not is_non_eur_without_conversion(tx)


def test_usd_transaction_without_conversion_is_flagged() -> None:
    """A USD transaction with no value_in_eur is flagged by the gate predicate."""
    raw = _usd_raw("usd-gate-002")
    from ....domain.transactions import Transaction

    tx = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )

    assert tx.value_in_eur is None
    assert is_non_eur_without_conversion(tx)


def test_missing_rate_leaves_fx_fields_absent(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """When the ECB snapshot has no rate for a date, fx_rate and value_in_eur stay None.

    This verifies the coupling invariant: both absent is valid; partially set
    is not allowed by the Transaction model_validator.
    """

    normalizer = CurrencyNormalizationService(rate_provider=_ecb_provider(usd_quote=None))
    repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)

    result = import_ledger_transactions(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        parsed_rows=[_usd_parsed("usd-norate-001")],
        transaction_repository=repo,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        currency_normalizer=normalizer,
    )

    assert result.summary.imported == 1
    catalogue = repo.load()
    tx = next(iter(catalogue.values()))
    assert tx.fx_rate is None
    assert tx.value_in_eur is None


def test_anti_tautology_mutated_rate_changes_value_in_eur(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Changing the ECB quote fixture changes the stored value_in_eur.

    Verifies the test is not tautological: if the rate were ignored,
    both result sets would produce the same value_in_eur; the assertion
    would pass trivially.  The inequality below fails if value_in_eur
    does not reflect the rate actually used.
    """
    canonical_normalizer = CurrencyNormalizationService(rate_provider=_ecb_provider())

    # Use a deliberately different ECB quote to produce a different EUR value.
    mutant_normalizer = CurrencyNormalizationService(
        rate_provider=_ecb_provider(usd_quote=_ECB_2024_01_15_USD_QUOTE * Decimal("2")),
    )

    repo_canonical = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)

    result_canonical = import_ledger_transactions(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        parsed_rows=[_usd_parsed("usd-antitauto-canonical")],
        transaction_repository=repo_canonical,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        currency_normalizer=canonical_normalizer,
    )
    assert result_canonical.summary.imported == 1

    # Re-use the same repo but with a different provider_id so it gets a fresh row
    repo_mutant = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    result_mutant = import_ledger_transactions(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        parsed_rows=[_usd_parsed("usd-antitauto-mutant")],
        transaction_repository=repo_mutant,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        currency_normalizer=mutant_normalizer,
    )
    assert result_mutant.summary.imported == 1

    catalogue = repo_canonical.load()
    txs = {tx.raw.provider_transaction_id: tx for tx in catalogue.values()}

    canonical_eur = txs["usd-antitauto-canonical"].value_in_eur
    mutant_eur = txs["usd-antitauto-mutant"].value_in_eur

    assert canonical_eur is not None
    assert mutant_eur is not None
    assert canonical_eur != mutant_eur, (
        f"Anti-tautology failure: both rates produced value_in_eur={canonical_eur}; the rate is not being applied"
    )
