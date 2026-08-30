"""Real-behaviour tests for the canonical ISO code normalisers.

Contract under test:

* :func:`normalise_iso_4217_currency` trims and uppercases *before* the shape
  check, so a padded or lowercase source cell normalises rather than being
  refused for its padding.
* :func:`normalise_iso_3166_alpha2_jurisdiction` trims, then requires an
  already-uppercase two-letter code — it deliberately refuses a lowercase
  token rather than folding it, because the jurisdiction axis selects the
  regulatory-source treatment of a ledger row.
"""

from __future__ import annotations

import pytest

from ....core.errors.hierarchy import CoreValidationError
from .. import normalise_iso_3166_alpha2_jurisdiction, normalise_iso_4217_currency

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("EUR", "EUR"),
        ("eur", "EUR"),
        ("usd", "USD"),
        (" usd ", "USD"),
        ("\tUSD\n", "USD"),
        ("  eUr  ", "EUR"),
    ],
)
def test_currency_normalises_padding_and_case(raw: str, expected: str) -> None:
    """Padding and case are normalised away before the three-letter shape check.

    DISCRIMINATING for the padded parameters: dropping the ``strip()`` makes
    them refuse instead of normalise.
    SUPPORTING for the unpadded parameters (``"EUR"``, ``"eur"``, ``"usd"``).
    """
    assert normalise_iso_4217_currency(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["US", "USDX", "U$D", "12", "EU1", "", "   ", "€UR"],
)
def test_currency_refuses_non_iso_4217_shapes(raw: str) -> None:
    """Short, long, and non-alphabetic tokens are refused after trimming.

    DISCRIMINATING for the whitespace-only parameter (``"   "``), which a
    non-trimming implementation would treat as length-3 and could admit.
    SUPPORTING for the rest, refused under either implementation.
    """
    with pytest.raises(CoreValidationError, match="three-letter ISO 4217"):
        normalise_iso_4217_currency(raw)


def test_currency_error_is_a_value_error_so_pydantic_reports_it() -> None:
    """The raised error must be a ``ValueError`` so a delegating validator reports cleanly.

    SUPPORTING. Pins the base-class contract the Pydantic delegation relies
    on; it cannot flip under a normaliser-logic mutation.
    """
    assert issubclass(CoreValidationError, ValueError)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("ES", "ES"),
        (" ES ", "ES"),
        ("\tDE\n", "DE"),
    ],
)
def test_jurisdiction_accepts_uppercase_alpha2_and_trims(raw: str | None, expected: str | None) -> None:
    """``None`` passes through; a padded uppercase alpha-2 code is trimmed.

    DISCRIMINATING for the padded parameters; SUPPORTING for ``None`` and the
    already-canonical ``"ES"``.
    """
    assert normalise_iso_3166_alpha2_jurisdiction(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["es", "Es", "eS", "E", "ESP", "E1", "", "  ", "É S"],
)
def test_jurisdiction_refuses_non_canonical_alpha2(raw: str) -> None:
    """Lowercase, wrong-length, and non-alphabetic jurisdictions are refused.

    DISCRIMINATING for the lowercase parameters (``"es"``, ``"Es"``, ``"eS"``):
    an implementation that folds case instead of refusing it admits them.
    SUPPORTING for the wrong-length and non-alphabetic parameters.

    Lowercase is refused rather than folded: the caller must declare the
    canonical code instead of having one guessed for it.
    """
    with pytest.raises(CoreValidationError, match="ISO 3166-1 alpha-2 uppercase"):
        normalise_iso_3166_alpha2_jurisdiction(raw)
