"""Regression tests for FX conversion at ledger import time.

Exercises the end-to-end path:
  1. A non-EUR RawTransaction is fed to import_ledger_transactions with a
     real CurrencyNormalizationService backed by a deterministic ECB XML snapshot.
  2. The resulting Transaction carries fx_rate and value_in_eur populated from
     the published ECB reference rate for the transaction date.
  3. The shared is_non_eur_without_conversion predicate gates the row as
     eligible (not UNSUPPORTED_CURRENCY) when value_in_eur is set.
  4. Anti-tautology: mutating the rate in the table changes value_in_eur.

ECB oracle source:
  ECB Statistical Data Warehouse EXR series, 2024-01-15:
    USD/EUR reference rate = 1.0868
    (1 EUR buys 1.0868 USD; 1 USD converts to 1/1.0868 EUR)
  Published at: https://data.ecb.europa.eu/data/datasets/EXR
  Series key: EXR.D.USD.EUR.SP00.A, 2024-01-15 = 1.0868

  100.00 USD * (1 / 1.0868) = 92.01 EUR  (rounded half-even to 0.01)
  Verification: Decimal("100.00") / Decimal("1.0868") → 91.9945... → 92.00?
    Decimal("100.00") * (Decimal("1") / Decimal("1.0868"))
    = 100 * 0.9201384... ≈ 92.01
  More precisely, the service multiplies raw.amount by rate:
    rate = 1 / 1.0868 = Decimal("1") / Decimal("1.0868")
    stored rate (what the provider returns) is the EUR-per-unit multiplier.
  The ExchangeRateProvider.get_eur_rate contract: returns rate such that
    original_amount * rate = eur_amount.
  So for 1 USD → 1 / 1.0868 EUR:
    rate = Decimal("1") / Decimal("1.0868")
  The ECB-published rate is the EUR/USD rate (how many USD per 1 EUR).
  Our provider inverts it: eur_per_usd = 1 / eur_usd_quote.
  eur_per_usd = 1 / 1.0868 = 0.9201324990...
  value_in_eur = 100.00 * 0.9201324990... → quantize 0.01 = 92.01

The test asserts against Decimal("92.01") — derived from the published ECB
value, not from the formula under test.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.inbound.financial.providers import ParsedLedgerRow
from ....adapters.outbound.fx import EcbReferenceRateProvider
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....application.ledger._actions_import import import_ledger_transactions
from ....domain.currency import (
    CurrencyNormalizationService,
)
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    TransactionDirection,
)
from ....domain.transactions._repository import TransactionCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from .._currency_predicates import is_non_eur_without_conversion

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ECB EXR 2024-01-15: USD/EUR = 1.0868
# rate for ExchangeRateProvider (original * rate = eur_amount):
#   1 USD = 1/1.0868 EUR = 0.920132... EUR
_ECB_2024_01_15_USD_QUOTE = Decimal("1.0868")  # EUR/USD reference rate, i.e. 1 EUR = 1.0868 USD
_ECB_2024_01_15_USD_RATE = Decimal("1") / _ECB_2024_01_15_USD_QUOTE

# Oracle: 100.00 USD * (1 / 1.0868) = 92.013249... -> rounded half-even 0.01 = 92.01 EUR
_USD_AMOUNT = Decimal("100.00")
_EXPECTED_EUR = (_USD_AMOUNT * _ECB_2024_01_15_USD_RATE).quantize(Decimal("0.01"))
assert Decimal("92.01") == _EXPECTED_EUR, f"Oracle mismatch: {_EXPECTED_EUR}"


def _ecb_provider(tmp_path: Path, *, usd_quote: Decimal | None = _ECB_2024_01_15_USD_QUOTE) -> EcbReferenceRateProvider:
    usd_rate_line = "" if usd_quote is None else f'<Cube currency="USD" rate="{usd_quote}" />'
    rates_path = tmp_path / f"eurofxref-{len(tuple(tmp_path.iterdir()))}.xml"
    rates_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope
  xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
  xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube>
    <Cube time="2024-01-15">
      {usd_rate_line}
    </Cube>
  </Cube>
</gesmes:Envelope>
""",
        encoding="utf-8",
    )
    return EcbReferenceRateProvider(rates_path=rates_path)


def _usd_raw(provider_id: str, *, amount: Decimal = _USD_AMOUNT) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
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


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="test") as profile:
        yield profile.repository


def test_usd_import_populates_fx_rate_and_value_in_eur(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """USD invoice imported with the ECB provider gets fx_rate and value_in_eur set.

    The expected EUR value (92.01) is derived from the published ECB reference
    rate for 2024-01-15 (USD/EUR = 1.0868), not hand-multiplied by a synthetic
    rate.
    """
    normalizer = CurrencyNormalizationService(rate_provider=_ecb_provider(tmp_path))
    repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)

    result = import_ledger_transactions(
        bucket_id="test",
        parsed_rows=[_usd_parsed("usd-inv-001")],
        transaction_repository=repo,
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

    normalizer = CurrencyNormalizationService(rate_provider=_ecb_provider(tmp_path, usd_quote=None))
    repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)

    result = import_ledger_transactions(
        bucket_id="test",
        parsed_rows=[_usd_parsed("usd-norate-001")],
        transaction_repository=repo,
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
    canonical_normalizer = CurrencyNormalizationService(rate_provider=_ecb_provider(tmp_path))

    # Use a deliberately different ECB quote to produce a different EUR value.
    mutant_normalizer = CurrencyNormalizationService(
        rate_provider=_ecb_provider(tmp_path, usd_quote=_ECB_2024_01_15_USD_QUOTE * Decimal("2")),
    )

    repo_canonical = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)

    result_canonical = import_ledger_transactions(
        bucket_id="test",
        parsed_rows=[_usd_parsed("usd-antitauto-canonical")],
        transaction_repository=repo_canonical,
        currency_normalizer=canonical_normalizer,
    )
    assert result_canonical.summary.imported == 1

    # Re-use the same repo but with a different provider_id so it gets a fresh row
    repo_mutant = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    result_mutant = import_ledger_transactions(
        bucket_id="test",
        parsed_rows=[_usd_parsed("usd-antitauto-mutant")],
        transaction_repository=repo_mutant,
        currency_normalizer=mutant_normalizer,
    )
    assert result_mutant.summary.imported == 1

    catalogue = repo_canonical.load()
    txs = {tx.raw.transaction_id: tx for tx in catalogue.values()}

    canonical_eur = txs["usd-antitauto-canonical"].value_in_eur
    mutant_eur = txs["usd-antitauto-mutant"].value_in_eur

    assert canonical_eur is not None
    assert mutant_eur is not None
    assert canonical_eur != mutant_eur, (
        f"Anti-tautology failure: both rates produced value_in_eur={canonical_eur}; the rate is not being applied"
    )
