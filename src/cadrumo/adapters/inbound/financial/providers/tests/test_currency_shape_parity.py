"""Cross-surface parity for inbound ISO 4217 currency shape.

Three surfaces read a currency token off the wire and one persists it: the
CSV column resolver, the OFX statement ``CURDEF``, and the
:class:`~domain.transactions.RawTransaction` the parsers emit. They
previously disagreed — the CSV resolver validated a three-alpha shape, OFX
validated nothing at all, and ``RawTransaction`` refused a *padded* token
outright because its ``min_length`` / ``max_length`` field constraint fired
before its own normaliser ran.

These tests pin the agreement: every surface accepts the same tokens and
refuses the same tokens, and each refusal still carries its own
boundary-specific wording.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.config import override_settings
from ......core.parsing import normalise_iso_4217_currency
from ......domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._base import FinancialValidationError, default_currency
from .._csv import _currency_from_aliases
from .._ofx import _resolve_statement_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

#: Tokens every inbound surface must normalise to the same canonical code.
_ACCEPTED: tuple[tuple[str, str], ...] = (
    ("EUR", "EUR"),
    ("eur", "EUR"),
    (" usd ", "USD"),
    ("\tGBP\n", "GBP"),
)

#: Tokens every inbound surface must refuse.
_REFUSED: tuple[str, ...] = ("US", "USDX", "U$D", "E1")


def _raw_transaction(currency: str) -> RawTransaction:
    """Build a real ``RawTransaction`` differing only in ``currency``."""
    return RawTransaction(
        provider_transaction_id="tx-1",
        booked_date=date(2026, 4, 10),
        amount=Decimal("10.00"),
        currency=currency,
        description="parity probe",
        provenance=RawProvenance(
            source_path=Path("statement.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 10, tzinfo=UTC),
            provider_name="parity",
        ),
        raw_fields={},
    )


def _csv_currency(raw: str) -> str:
    """Resolve ``raw`` through the real CSV currency-column resolver."""
    return _currency_from_aliases(
        {"Divisa": raw},
        {"divisa": "Divisa"},
        ("divisa",),
        "test layout row 1",
    )


@pytest.mark.parametrize(("raw", "expected"), _ACCEPTED)
def test_csv_and_raw_transaction_accept_the_same_currency_tokens(raw: str, expected: str) -> None:
    """A token accepted by the CSV column must be accepted by the persisted record.

    DISCRIMINATING for the padded parameters (``" usd "``, ``"\\tGBP\\n"``):
    before the fix the record refused them on a length constraint while the
    CSV column accepted them.
    SUPPORTING for the unpadded parameters (``"EUR"``, ``"eur"``): both
    implementations already agreed on those, so they cannot flip.
    """
    assert _csv_currency(raw) == expected
    assert _raw_transaction(raw).currency == expected


@pytest.mark.parametrize("raw", _REFUSED)
def test_csv_and_raw_transaction_refuse_the_same_currency_tokens(raw: str) -> None:
    """A token refused by the CSV column must be refused by the persisted record.

    DISCRIMINATING on the *error identity*, not merely on "something raised".
    Before the fix ``"US"`` / ``"USDX"`` / ``"E1"`` raised the Pydantic
    ``string_too_short`` / ``string_too_long`` length error rather than the
    shared ISO 4217 shape refusal, so the message match is what flips.
    SUPPORTING for ``"U$D"``, which is length-3 and therefore already reached
    the shape check before the fix.
    """
    with pytest.raises(FinancialValidationError, match="three-letter ISO 4217"):
        _csv_currency(raw)
    with pytest.raises(ValidationError, match="three-letter ISO 4217"):
        _raw_transaction(raw)


def test_padded_currency_reaches_the_normaliser_not_the_length_constraint() -> None:
    """``" usd "`` must normalise, not trip a bare length constraint.

    DISCRIMINATING. This is the concrete divergence the parity contract
    closes: the ingest boundaries have always trimmed before validating, so a
    padded source cell that every parser accepted must not be refused by the
    record it is persisted into. Before the fix this raised
    ``string_too_long``.
    """
    assert _csv_currency(" usd ") == "USD"
    assert _raw_transaction(" usd ").currency == "USD"


@pytest.mark.parametrize("configured", ["EURO", "e", "", "12", " u$d "])
def test_misconfigured_default_currency_is_refused_at_its_owner(configured: str) -> None:
    """A malformed ``financial_base_currency`` must be refused, not copied onto a row.

    DISCRIMINATING. Every provider falls back to :func:`default_currency`
    when a source omits a per-row currency, and the setting declares no shape
    of its own. Before this gate the raw setting value flowed unchecked
    through the CSV no-currency-column branch and onto the parsed row, so
    every parameter here returned a malformed code instead of raising.
    """
    with override_settings(financial_base_currency=configured):
        with pytest.raises(FinancialValidationError, match="financial_base_currency"):
            default_currency()
        with pytest.raises(FinancialValidationError, match="financial_base_currency"):
            _currency_from_aliases({"Importe": "10"}, {"importe": "Importe"}, ("divisa",), "ctx")


def test_valid_default_currency_still_normalises() -> None:
    """A padded/lowercase but well-formed setting still resolves.

    SUPPORTING. The retired implementation also stripped and uppercased, so
    this passes on both sides; it exists to pin that the new gate did not
    tighten the accepted set for well-formed settings.
    """
    with override_settings(financial_base_currency=" usd "):
        assert default_currency() == "USD"
        assert _currency_from_aliases({"Importe": "10"}, {"importe": "Importe"}, ("divisa",), "ctx") == "USD"


def test_every_currency_surface_is_wired_to_the_one_shared_normaliser() -> None:
    """Each currency surface must *delegate* to the core helper, not merely agree today.

    DISCRIMINATING for the dedup itself. Re-inlining a behaviourally identical
    shape check into any one of these surfaces leaves every behavioural
    assertion in this file green, so behaviour alone cannot prove the
    duplication stayed removed. Asserting the module namespace merely resolves
    the helper is also insufficient — a re-inlined copy that leaves the unused
    import behind still satisfies that.

    So this inspects each call site's compiled ``co_names``, which names the
    globals the function body actually references, and flips the moment a
    surface stops calling the shared helper.
    """
    helper_name = normalise_iso_4217_currency.__name__
    call_sites = {
        "default_currency (shared fallback)": default_currency,
        "_currency_from_aliases (CSV column)": _currency_from_aliases,
        "_resolve_statement_context (OFX header)": _resolve_statement_context,
        "RawTransaction._normalize_currency (persisted record)": (
            RawTransaction.__dict__["_normalize_currency"].__func__
        ),
    }
    for label, function in call_sites.items():
        assert helper_name in function.__code__.co_names, f"{label} must call the shared core currency normaliser"


def test_refused_currency_keeps_boundary_specific_diagnostics() -> None:
    """Shared shape policy must not flatten the per-boundary error context.

    SUPPORTING. The retired inline check built the same message, so this
    passes on both sides; it guards against a future consolidation that
    replaces the CSV wording with the bare core message.
    """
    with pytest.raises(FinancialValidationError) as csv_exc:
        _csv_currency("U$D")
    message = str(csv_exc.value)
    assert "test layout row 1" in message, "CSV refusal must name the row context"
    assert "'Divisa'" in message, "CSV refusal must name the offending column"
