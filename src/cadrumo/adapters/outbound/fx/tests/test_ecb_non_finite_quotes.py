"""A non-finite or non-positive ECB quote is a gap, never a rate.

``_parse_observations`` caught only :exc:`~decimal.InvalidOperation`, so
``Decimal`` conversion SUCCESS stood in for "this is a usable quote" — and
``Decimal`` converts ``NaN`` and the infinities happily. Two failures followed,
both downstream of the parser and neither legible as a parse problem:

* ``NaN`` reached the caller's ``<= 0`` comparison, which raises
  :exc:`~decimal.InvalidOperation` for a quiet NaN, so a corrupted official
  response escaped as a raw decimal exception rather than the provider's
  promised :class:`ExchangeRateProviderError`.
* ``Infinity`` passed that comparison and inverted to an effectively-zero
  exchange rate, converting every amount to nothing at all — a wrong answer
  rather than a refusal.

The transport here is the suite's declared ECB CSV boundary, not a double of
the code under test: the provider's own parsing, window handling, fallback and
inversion all run for real.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....tests.ecb_stub import ecb_csv_fetch
from ..ecb_provider import EcbReferenceRateProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_GOOD_DAY = date(2025, 3, 13)
_BAD_DAY = date(2025, 3, 14)
_GOOD_QUOTE = Decimal("1.0830")


def _provider(quotes: dict[date, Decimal]) -> EcbReferenceRateProvider:
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch({"USD": quotes}))


_UNUSABLE = (
    pytest.param(Decimal("NaN"), id="quiet-nan"),
    pytest.param(Decimal("sNaN"), id="signalling-nan"),
    pytest.param(Decimal("Infinity"), id="positive-infinity"),
    pytest.param(Decimal("-Infinity"), id="negative-infinity"),
    pytest.param(Decimal("0"), id="zero"),
    pytest.param(Decimal("-1.0830"), id="negative"),
)


@pytest.mark.parametrize("quote", _UNUSABLE)
def test_an_unusable_quote_reports_no_rate_rather_than_raising(quote: Decimal) -> None:
    """The only unusable observation in the window yields a missing rate.

    ``None`` is the provider's declared answer for "the ECB published nothing
    usable here". What must not happen is a raw ``decimal`` exception escaping
    the typed provider boundary, or a number coming back.
    """
    provider = _provider({_BAD_DAY: quote})

    assert provider.get_eur_rate("USD", _BAD_DAY) is None


@pytest.mark.parametrize("quote", _UNUSABLE)
def test_an_unusable_latest_quote_does_not_discard_the_valid_ones_behind_it(quote: Decimal) -> None:
    """A usable earlier publication still answers.

    The usability test used to run only on the LATEST observation in the
    window, after the parser had already admitted everything convertible, so
    one bad quote at the end of the window threw away the good rates behind
    it and reported no rate at all. Deciding usability where the observation
    is built means an unusable row is simply not an observation.
    """
    provider = _provider({_GOOD_DAY: _GOOD_QUOTE, _BAD_DAY: quote})

    rate = provider.get_eur_rate("USD", _BAD_DAY)

    assert rate == Decimal("1") / _GOOD_QUOTE


def test_a_usable_quote_still_resolves() -> None:
    """The positive control: a parser that dropped everything would pass the rest."""
    provider = _provider({_GOOD_DAY: _GOOD_QUOTE})

    assert provider.get_eur_rate("USD", _GOOD_DAY) == Decimal("1") / _GOOD_QUOTE


def test_an_infinite_quote_does_not_invert_to_an_effectively_zero_rate() -> None:
    """The defect's second shape, named on its own because it is silent.

    ``Infinity`` satisfied ``ecb_rate <= 0`` being false and then inverted to
    ``0E-1000026``: a rate that converts every amount to nothing, with no
    error anywhere. It is the one case where the caller received a number and
    had no reason to doubt it.
    """
    provider = _provider({_BAD_DAY: Decimal("Infinity")})

    rate = provider.get_eur_rate("USD", _BAD_DAY)

    assert rate is None
