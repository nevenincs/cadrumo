"""The parser's administrative-selector routing tracks the core authority.

``_filing_period_for_observation`` decides whether a registry selector names a
registration event (stored as ``AD-HOC``) or a period a filing occupies. It used
to answer from a local ``{"ALTA", "MODIFICACION", "MODIFICACIÓN", "BAJA"}``
literal, which had already drifted two members behind
``core._ADMINISTRATIVE_PERIOD_SET`` without anyone noticing: the missing
``COMUNICACION`` / ``VARIACION`` belong to Modelo 145, which ships no extraction
profile, so no PDF can currently reach this function carrying them.

That is a latent trap rather than a live defect, and the shape of these tests is
chosen accordingly. The membership case DERIVES its parameters from the public
core accessors instead of listing tokens, so a sixth administrative token enters
this test the moment it enters the authority; a test that listed them would
reproduce exactly the drift it is meant to catch.
"""

from __future__ import annotations

import pytest

from .....core.period import Period, accepted_filing_period_codes, accepted_period_codes
from ..parser import _filing_period_for_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

#: The administrative sub-vocabulary, computed as the registry codes that are not
#: filing codes. Derived from the two public accessors rather than restated, so
#: this cannot drift behind the authority the way the parser's local set did.
_ADMINISTRATIVE_TOKENS = tuple(sorted(set(accepted_period_codes()) - set(accepted_filing_period_codes())))

#: How AEAT prints the accented members on a rendered declaration, against the
#: unaccented spelling the registry declares. Hand-written because it records real
#: print spellings, not a shadow of the core set — whose completeness is the
#: separate concern that :func:`test_every_administrative_token_routes_to_ad_hoc`
#: owns.
_ACCENTED_AEAT_SPELLINGS = (
    ("MODIFICACIÓN", "MODIFICACION"),
    ("COMUNICACIÓN", "COMUNICACION"),
    ("VARIACIÓN", "VARIACION"),
)


def test_the_administrative_set_is_the_five_tokens_two_modelos_declare() -> None:
    """Guard the derivation itself.

    Every case below is parametrised off ``_ADMINISTRATIVE_TOKENS``, so a
    derivation that silently produced an empty tuple would make them all vacuous
    while still reporting green.
    """
    assert _ADMINISTRATIVE_TOKENS == ("ALTA", "BAJA", "COMUNICACION", "MODIFICACION", "VARIACION")


@pytest.mark.parametrize("token", _ADMINISTRATIVE_TOKENS)
def test_every_administrative_token_routes_to_ad_hoc(token: str) -> None:
    """Including the two Modelo 145 tokens the parser's local set had lost."""
    for spelling in (token, token.lower(), f"  {token}  "):
        assert _filing_period_for_observation(2025, spelling) == Period.from_year_and_code(2025, "AD-HOC"), spelling


@pytest.mark.parametrize(("printed", "declared"), _ACCENTED_AEAT_SPELLINGS)
def test_aeat_accented_spellings_route_to_ad_hoc(printed: str, declared: str) -> None:
    """AEAT prints correct Spanish; the registry declares the unaccented token."""
    assert declared in _ADMINISTRATIVE_TOKENS, declared
    assert _filing_period_for_observation(2025, printed) == Period.from_year_and_code(2025, "AD-HOC")


@pytest.mark.parametrize("token", ("1T", "4T", "0A", "03", "AD-HOC", "EVENT-3"))
def test_filing_tokens_are_untouched_by_the_administrative_branch(token: str) -> None:
    """The positive control: routing must not have swallowed the filing vocabulary."""
    assert _filing_period_for_observation(2025, token) == Period.from_year_and_code(2025, token)


def test_a_bare_filing_year_still_reads_as_the_annual_period() -> None:
    """A declaration printing its ejercicio where the period belongs means ``0A``."""
    assert _filing_period_for_observation(2025, "2025") == Period.from_year_and_code(2025, "0A")


def test_an_unknown_selector_is_refused_rather_than_silently_routed() -> None:
    """A token in neither vocabulary must not fall through to ``AD-HOC``."""
    from .....core.period import PeriodError

    with pytest.raises(PeriodError):
        _filing_period_for_observation(2025, "NOT-A-PERIOD")
