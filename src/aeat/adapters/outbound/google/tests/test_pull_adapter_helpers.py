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

from .....application.storage.calc_sheets import registry_sha
from .....core.decimal import coerce_decimal as _coerce_decimal
from .....core.i18n import tr
from .....core.resources import resources
from ....outbound.storage._errors import OutboundStorageConflictError, OutboundStorageValidationError
from .._calc_sheets_pull import (
    MetadataMatchState,
    _classify_metadata_match,
    _coerce_value,
    _merge_developer_metadata_entries,
    pull_operator_edits,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


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
    assert verdict is MetadataMatchState.MISSING
    # Missing metadata still returns a PullMetadata stub so callers can
    # render the result without None-checking every field.
    assert metadata.modelo_id == "missing"
    assert metadata.revision_id == "missing"
    assert metadata.filing_year == 0
    assert metadata.period == "missing"
    assert metadata.engine_version == "missing"
    assert metadata.registry_sha == "missing"


def test_classify_metadata_returns_matches_for_aligned_pairs() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": snapshot.revision.id,
        "aeat_filing_year": "2025",
        "aeat_period": "1T",
        "aeat_engine_version": "calc-sheets/0.1.0",
        # The registry-SHA stamp must match the live snapshot's
        # calculation-surface hash, not just the modelo coordinates.
        "aeat_registry_sha": registry_sha(snapshot),
    }
    verdict, metadata = _classify_metadata_match(pairs, snapshot)
    assert verdict == "matches"
    assert metadata.modelo_id == "130"
    assert metadata.filing_year == 2025


def test_classify_metadata_returns_stale_for_mismatched_modelo() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "131",  # different modelo
        "aeat_revision_id": snapshot.revision.id,
        "aeat_filing_year": "2025",
        "aeat_period": "1T",
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_for_mismatched_period() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": snapshot.revision.id,
        "aeat_filing_year": "2025",
        "aeat_period": "2T",  # different period
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_for_mismatched_year() -> None:
    snapshot = _modelo_130_snapshot()
    pairs = {
        "aeat_modelo_id": "130",
        "aeat_revision_id": snapshot.revision.id,
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
        "aeat_revision_id": snapshot.revision.id,
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
        "aeat_revision_id": snapshot.revision.id,
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
    assert metadata.registry_sha != registry_sha(snapshot)


# ---------------------------------------------------------------------------
# Public pull validation
# ---------------------------------------------------------------------------


def test_pull_operator_edits_refuses_blank_spreadsheet_id_before_service_build() -> None:
    snapshot = _modelo_130_snapshot()

    with pytest.raises(OutboundStorageValidationError) as raised:
        pull_operator_edits(snapshot=snapshot, spreadsheet_id="  ", credentials=object())

    assert raised.value.context == {"spreadsheet_id": "  "}
    assert raised.value.translated_message == "adapters.google.calc_sheets.errors.spreadsheet_id_blank"


# ---------------------------------------------------------------------------
# Duplicate developer metadata merge
# ---------------------------------------------------------------------------


def test_merge_developer_metadata_refuses_conflicting_registry_identity_duplicates() -> None:
    """Duplicate identity stamps with different values must not collapse by API order."""

    entries = (
        {"metadataKey": "aeat_registry_sha", "metadataValue": "old-registry-sha"},
        {"metadataKey": "aeat_registry_sha", "metadataValue": "new-registry-sha"},
    )

    with pytest.raises(OutboundStorageConflictError) as raised:
        _merge_developer_metadata_entries(entries)

    assert raised.value.context == {"conflicting_metadata_keys": ["aeat_registry_sha"]}
    assert raised.value.translated_message == "adapters.google.calc_sheets.errors.conflicting_duplicate_metadata"
    assert raised.value.suggestion == tr("adapters.google.calc_sheets.suggestions.reexport_workbook")


def test_merge_developer_metadata_allows_duplicate_exported_at_for_reapplied_same_slice() -> None:
    """Repeated exports of the same registry slice legitimately carry newer timestamps."""

    pairs = _merge_developer_metadata_entries(
        (
            {"metadataKey": "aeat_registry_sha", "metadataValue": "da9952e1610f7db6"},
            {"metadataKey": "aeat_registry_sha", "metadataValue": "da9952e1610f7db6"},
            {"metadataKey": "aeat_exported_at", "metadataValue": "2026-06-02T17:54:13+00:00"},
            {"metadataKey": "aeat_exported_at", "metadataValue": "2026-06-02T17:55:32+00:00"},
        ),
    )

    assert pairs["aeat_registry_sha"] == "da9952e1610f7db6"
    assert pairs["aeat_exported_at"] == "2026-06-02T17:55:32+00:00"
