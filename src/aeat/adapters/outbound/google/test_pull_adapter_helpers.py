"""Pure-function contract tests for the pull adapter's coercion + classifier helpers.

Guards behaviour of two load-bearing helpers:

  * ``_coerce_value`` — turns a Sheets API cell value (which can be
    None / bool / int / float / str) into the typed
    Decimal | str | bool | None contract callers expect.
  * ``_classify_metadata_match`` — decides whether a pulled workbook's
    developer-metadata pairs identify the same snapshot as the
    caller supplied, including the registry-SHA gate that refuses a
    workbook compiled against a drifted calculation surface. The
    compute refusal path in ``compute_from_pull`` depends entirely on
    this verdict.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....application.storage.calc_sheets._engine import _registry_sha
from ....core.resources import resources
from ._calc_sheets_pull import _classify_metadata_match, _coerce_decimal, _coerce_value

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


# ---------------------------------------------------------------------------
# _coerce_value
# ---------------------------------------------------------------------------


def test_coerce_value_passes_none_through() -> None:
    assert _coerce_value(None) is None


def test_coerce_value_passes_empty_string_through_as_none() -> None:
    assert _coerce_value("") is None


def test_coerce_value_preserves_bool_true_and_false() -> None:
    """Bools must not be coerced to Decimal — they would silently become 1 / 0.

    Sheets renders a CHECKBOX cell as a Python ``bool``; the runtime
    later distinguishes operator-typed bools from numeric edits so the
    bool path must survive the helper untouched.
    """
    assert _coerce_value(True) is True
    assert _coerce_value(False) is False


def test_coerce_value_turns_int_into_decimal() -> None:
    assert _coerce_value(42) == Decimal("42")


def test_coerce_value_turns_float_into_decimal_via_str() -> None:
    """Floats arrive from Sheets numeric cells; route through str to preserve digits."""
    assert _coerce_value(1500.55) == Decimal("1500.55")


def test_coerce_value_parses_decimal_string() -> None:
    assert _coerce_value("10000.50") == Decimal("10000.50")


def test_coerce_value_returns_string_for_non_numeric_text() -> None:
    """A NIF or descriptive label stays a string."""
    assert _coerce_value("12345678A") == "12345678A"
    assert _coerce_value("Perceptor name") == "Perceptor name"


def test_coerce_decimal_returns_none_for_empty_or_invalid() -> None:
    assert _coerce_decimal(None) is None
    assert _coerce_decimal("") is None
    assert _coerce_decimal("not-a-number") is None


def test_coerce_decimal_parses_int_and_float() -> None:
    assert _coerce_decimal(42) == Decimal("42")
    assert _coerce_decimal(1500.5) == Decimal("1500.5")


# ---------------------------------------------------------------------------
# _classify_metadata_match
# ---------------------------------------------------------------------------


def _modelo_130_snapshot():
    return resources().modelos.authority.snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))


def test_classify_metadata_returns_missing_for_empty_pairs() -> None:
    snapshot = _modelo_130_snapshot()
    verdict, metadata = _classify_metadata_match({}, snapshot)
    assert verdict == "missing"
    # Missing metadata still returns a PullMetadata stub so callers can
    # render the result without None-checking every field.
    assert metadata.modelo_id == ""
    assert metadata.filing_year == 0


def test_classify_metadata_returns_matches_for_aligned_pairs() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": "2019-y-siguientes",
        "aeat_filing_year": "2025",
        "aeat_period": "1T",
        "aeat_engine_version": "calc-sheets/0.1.0",
        # The registry-SHA stamp must match the live snapshot's
        # calculation-surface hash, not just the modelo coordinates.
        "aeat_registry_sha": _registry_sha(snapshot),
    }
    verdict, metadata = _classify_metadata_match(pairs, snapshot)
    assert verdict == "matches"
    assert metadata.modelo_id == "130"
    assert metadata.filing_year == 2025


def test_classify_metadata_returns_stale_for_mismatched_modelo() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "131",  # different modelo
        "aeat_revision_id": "2019-y-siguientes",
        "aeat_filing_year": "2025",
        "aeat_period": "1T",
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_for_mismatched_period() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": "2019-y-siguientes",
        "aeat_filing_year": "2025",
        "aeat_period": "2T",  # different period
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_for_mismatched_year() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": "2019-y-siguientes",
        "aeat_filing_year": "2024",  # different year
        "aeat_period": "1T",
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_when_filing_year_is_garbage() -> None:
    """A malformed filing_year string defaults to 0 (which never matches)."""
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": "2019-y-siguientes",
        "aeat_filing_year": "not-a-year",
        "aeat_period": "1T",
    }
    verdict, metadata = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"
    assert metadata.filing_year == 0


def test_classify_metadata_returns_stale_for_drifted_registry_sha() -> None:
    """A workbook compiled against a different registry slice is stale.

    The pull module's docstring promises ``aeat_registry_sha`` is part
    of the metadata gate: a workbook whose modelo / revision / year /
    period all align but whose registry-SHA stamp diverges was compiled
    against a different calculation surface — casilla numbering, formula
    chains, and bracket tables may have shifted. ``_classify_metadata_match``
    must classify it ``stale`` so ``compute_from_pull`` refuses the
    merge. Google Sheets is an export mirror, never an authority for a
    registry slice it no longer binds.

    This is the malformed-sheet probe: before the registry-SHA gate was
    enforced, this exact workbook classified ``matches`` and a stale
    calculation surface flowed silently into the local recompute.
    """

    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": "2019-y-siguientes",
        "aeat_filing_year": "2025",
        "aeat_period": "1T",
        "aeat_engine_version": "calc-sheets/0.1.0",
        # Every modelo coordinate aligns; only the registry-SHA stamp
        # diverges from the live snapshot's calculation-surface hash.
        "aeat_registry_sha": "deadbeefdeadbeef",
    }
    verdict, metadata = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"
    assert metadata.registry_sha == "deadbeefdeadbeef"
    assert metadata.registry_sha != _registry_sha(snapshot)
