"""Pure-function contract tests for the pull adapter's coercion + classifier helpers.

Guards behaviour of two load-bearing helpers:

  * ``_coerce_value`` — turns a Sheets API cell value (which can be
    None / bool / int / float / str) into the typed
    Decimal | str | bool | None contract callers expect.
  * ``_classify_metadata_match`` — decides whether a pulled workbook's
    developer-metadata pairs identify the same snapshot as the
    caller supplied. The compute refusal path I added in
    `compute_from_pull` depends entirely on this verdict.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import bundled_path
from ....domain.calculations.registry._loader import load_registry_tree
from ....domain.calculations.registry._snapshot import build_snapshot
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "130")
    return build_snapshot(
        modelo=modelo,
        catalogues=catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="1T",
        on=date(2025, 4, 1),
    )


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
        "aeat_registry_sha": "abc123",
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
