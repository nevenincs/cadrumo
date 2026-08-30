"""Focused unit tests for the profile-key normaliser.

`normalise_key` is the SOLE canonical-form rule for profile-key
lookups. The docstring of `_normalise.py` is explicit: callers
import this function (or `ProfileKey.normalise`, which forwards
here) and never re-implement the rule. Every profile-key lookup
across the codebase (user-CLI store, deadline engine, profile
validators) consumes this normaliser.

The rule:
1. Strip surrounding whitespace.
2. Lowercase everything.
3. Replace ``-`` with ``.``.
4. Preserve underscores verbatim — registry-canonical keys
   like ``does_intracomunitario`` and ``iva.roi_enrolled`` must
   survive the round-trip through the user-CLI store and reach
   the deadline engine, which looks values up by exact key.

A regression in any branch would silently break key lookups
across the entire profile-resolution chain.
"""

from __future__ import annotations

import pytest

from ..normalise import normalise_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_normalise_key_is_idempotent_on_already_canonical_input() -> None:
    assert normalise_key("tax.id") == "tax.id"
    assert normalise_key("tax.residence.ccaa") == "tax.residence.ccaa"


def test_normalise_key_strips_surrounding_whitespace() -> None:
    assert normalise_key("  tax.id  ") == "tax.id"
    assert normalise_key("\ttax.id\n") == "tax.id"


def test_normalise_key_lowercases_uppercase_characters() -> None:
    assert normalise_key("TAX.ID") == "tax.id"
    assert normalise_key("Tax.Id") == "tax.id"


def test_normalise_key_folds_dashes_into_dots() -> None:
    assert normalise_key("tax-id") == "tax.id"
    assert normalise_key("tax-residence-ccaa") == "tax.residence.ccaa"


def test_normalise_key_preserves_underscores_verbatim() -> None:
    """Documented load-bearing invariant: registry-canonical keys
    with underscores must survive the round-trip. Folding underscores
    into dots would silently break the deadline engine's exact-key
    lookups for these specific profile fields."""
    assert normalise_key("does_intracomunitario") == "does_intracomunitario"
    assert normalise_key("iva.roi_enrolled") == "iva.roi_enrolled"


def test_normalise_key_combines_strip_lowercase_and_dash_fold() -> None:
    """The composite case: surrounding whitespace + mixed case + dashes.
    Output is the documented canonical form."""
    assert normalise_key("  TAX-ID  ") == "tax.id"
    assert normalise_key("  Tax-Residence-CCAA  ") == "tax.residence.ccaa"


def test_normalise_key_empty_string_passes_through_as_empty() -> None:
    assert normalise_key("") == ""


def test_normalise_key_whitespace_only_string_strips_to_empty() -> None:
    assert normalise_key("   ") == ""
    assert normalise_key("\t\n") == ""


def test_normalise_key_preserves_multiple_dashes_as_multiple_dots() -> None:
    """No collapsing: each dash becomes a separate dot in the output.
    Consecutive dashes become consecutive dots."""
    assert normalise_key("a-b-c-d") == "a.b.c.d"
    assert normalise_key("a--b") == "a..b"


def test_normalise_key_mixes_underscore_and_dash_correctly() -> None:
    """The two replacement classes are independent: dashes always
    fold; underscores never fold. A key with both characters is
    handled per-character without interaction."""
    assert normalise_key("iva-roi_enrolled") == "iva.roi_enrolled"
    assert normalise_key("does_intracomunitario-flag") == "does_intracomunitario.flag"
