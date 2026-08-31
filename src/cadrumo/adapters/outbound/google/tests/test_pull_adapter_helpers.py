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

from .....application.storage.calc_sheets._engine import CALC_SHEETS_ENGINE_VERSION, build_export_plan, registry_sha
from .....core.decimal._coerce import coerce_decimal as _coerce_decimal
from .....domain.calculations.registry.authority import bundled_authority
from ...storage.errors import OutboundStorageConflictError, OutboundStorageValidationError
from ..calc_sheets_pull import (
    _classify_metadata_match,
    _coerce_value,
    _merge_developer_metadata_entries,
    _parse_relation_metadata,
    _require_matching_metadata,
    pull_operator_edits,
)
from ..calc_sheets_pull_records import MetadataMatchState
from ._calc_sheets_support import modelo_130_2025_1t_snapshot

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


def test_parse_relation_metadata_preserves_relation_grounding() -> None:
    """Pull metadata parser keeps source modelo, source casilla, and registry refs."""

    parsed = _parse_relation_metadata(
        "value=190.00; provenance=local_filing; source_modelo=115; source_filing_year=2026; "
        "source_periods=1T+2T+3T+4T; source_casilla_ids=02; legal_refs=ley-35-2006:art-99; "
        "source_refs=boe-modelo-180-2023-form; resolved_at=2026-06-30T12:00:00+00:00",
    )

    (
        provenance,
        source_modelo,
        source_filing_year,
        source_periods,
        source_casilla_ids,
        legal_refs,
        source_refs,
        resolved_at,
    ) = parsed
    assert provenance == "local_filing"
    assert source_modelo == "115"
    assert source_filing_year == 2026
    assert source_periods == ("1T", "2T", "3T", "4T")
    assert source_casilla_ids == ("02",)
    assert legal_refs == ("ley-35-2006:art-99",)
    assert source_refs == ("boe-modelo-180-2023-form",)
    assert resolved_at is not None and resolved_at.isoformat() == "2026-06-30T12:00:00+00:00"


def test_parse_relation_metadata_refuses_malformed_legal_ref() -> None:
    """Relation metadata must preserve legal ref ids under the registry id contract."""

    with pytest.raises(OutboundStorageValidationError) as raised:
        _parse_relation_metadata(
            "provenance=local_filing; legal_refs=Ley-35-2006:art-99; source_refs=boe-modelo-180-2023-form",
        )

    assert raised.value.context == {
        "metadata_key": "legal_refs",
        "metadata_value": "Ley-35-2006:art-99",
    }


def test_parse_relation_metadata_refuses_malformed_source_ref() -> None:
    """Relation metadata must preserve source ref ids under the registry id contract."""

    with pytest.raises(OutboundStorageValidationError) as raised:
        _parse_relation_metadata(
            "provenance=local_filing; legal_refs=ley-35-2006:art-99; source_refs=ley-35-2006:art-99",
        )

    assert raised.value.context == {
        "metadata_key": "source_refs",
        "metadata_value": "ley-35-2006:art-99",
    }


# ---------------------------------------------------------------------------
# _classify_metadata_match
# ---------------------------------------------------------------------------


def test_classify_metadata_returns_missing_for_empty_pairs() -> None:
    snapshot = modelo_130_2025_1t_snapshot()
    verdict, metadata = _classify_metadata_match({}, snapshot)
    assert verdict is MetadataMatchState.MISSING
    # Missing metadata still returns a PullMetadata placeholder so callers can
    # render the result without None-checking every field.
    assert metadata.modelo_id == "missing"
    assert metadata.revision_id == "missing"
    assert metadata.filing_year == 0
    assert metadata.period == "missing"
    assert metadata.engine_version == "missing"
    assert metadata.registry_sha == "missing"


def test_classify_metadata_returns_matches_for_aligned_pairs() -> None:
    snapshot = modelo_130_2025_1t_snapshot()
    pairs = {
        "cadrumo_modelo_id": "130",
        "cadrumo_revision_id": snapshot.revision.id,
        "cadrumo_filing_year": "2025",
        "cadrumo_period": "1T",
        "cadrumo_engine_version": CALC_SHEETS_ENGINE_VERSION,
        # The registry-SHA stamp must match the live snapshot's
        # calculation-surface hash, not just the modelo coordinates.
        "cadrumo_registry_sha": registry_sha(snapshot),
    }
    verdict, metadata = _classify_metadata_match(pairs, snapshot)
    assert verdict == "matches"
    assert metadata.modelo_id == "130"
    assert metadata.filing_year == 2025


def test_classify_metadata_returns_stale_for_mismatched_modelo() -> None:
    snapshot = modelo_130_2025_1t_snapshot()
    pairs = {
        "cadrumo_modelo_id": "131",  # different modelo
        "cadrumo_revision_id": snapshot.revision.id,
        "cadrumo_filing_year": "2025",
        "cadrumo_period": "1T",
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_for_mismatched_period() -> None:
    snapshot = modelo_130_2025_1t_snapshot()
    pairs = {
        "cadrumo_modelo_id": "130",
        "cadrumo_revision_id": snapshot.revision.id,
        "cadrumo_filing_year": "2025",
        "cadrumo_period": "2T",  # different period
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_for_mismatched_year() -> None:
    snapshot = modelo_130_2025_1t_snapshot()
    pairs = {
        "cadrumo_modelo_id": "130",
        "cadrumo_revision_id": snapshot.revision.id,
        "cadrumo_filing_year": "2024",  # different year
        "cadrumo_period": "1T",
    }
    verdict, _ = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"


def test_classify_metadata_returns_stale_when_filing_year_is_garbage() -> None:
    """A malformed filing_year string defaults to 0 (which never matches)."""
    snapshot = modelo_130_2025_1t_snapshot()
    pairs = {
        "cadrumo_modelo_id": "130",
        "cadrumo_revision_id": snapshot.revision.id,
        "cadrumo_filing_year": "not-a-year",
        "cadrumo_period": "1T",
    }
    verdict, metadata = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"
    assert metadata.filing_year == 0


def test_classify_metadata_returns_stale_for_drifted_registry_sha() -> None:
    """A workbook compiled against a different registry slice is stale.

    The pull module's docstring promises ``cadrumo_registry_sha`` is part
    of the metadata gate: a workbook whose modelo / revision / year /
    period all align but whose registry-SHA stamp diverges was compiled
    against a different calculation surface — casilla identity/layout, formula
    chains, and bracket tables may have shifted. ``_classify_metadata_match``
    must classify it ``stale`` so ``compute_from_pull`` refuses the
    merge. Google Sheets is an export mirror, never an authority for a
    registry slice it no longer binds.

    This is the malformed-sheet probe: before the registry-SHA gate was
    enforced, this exact workbook classified ``matches`` and a stale
    calculation surface flowed silently into the local recompute.
    """

    snapshot = modelo_130_2025_1t_snapshot()
    pairs = {
        "cadrumo_modelo_id": "130",
        "cadrumo_revision_id": snapshot.revision.id,
        "cadrumo_filing_year": "2025",
        "cadrumo_period": "1T",
        "cadrumo_engine_version": CALC_SHEETS_ENGINE_VERSION,
        # Every modelo coordinate aligns; only the registry-SHA stamp
        # diverges from the live snapshot's calculation-surface hash.
        "cadrumo_registry_sha": "deadbeefdeadbeef",
    }
    verdict, metadata = _classify_metadata_match(pairs, snapshot)
    assert verdict == "stale"
    assert metadata.registry_sha == "deadbeefdeadbeef"
    assert metadata.registry_sha != registry_sha(snapshot)


def test_prechange_exterior_workbook_layout_stamp_is_refused_before_pull_layout() -> None:
    """A real M369 exterior export from the preceding layout compiler is refused.

    Modelo 369's ``EXT-1T`` period is the concrete surface where the later
    filing-date correction can move tariff rows. The check is the exact guard
    called by ``pull_operator_edits`` directly after metadata readback and
    before it calls ``plan_layout`` or requests any coordinate range.
    """

    snapshot = bundled_authority().snapshot("369", filing_year=2026, period="EXT-1T", on=date(2026, 3, 31))
    exported_metadata = build_export_plan(snapshot).metadata
    prechange_pairs = {
        "cadrumo_modelo_id": exported_metadata.modelo_id,
        "cadrumo_revision_id": exported_metadata.revision_id,
        "cadrumo_filing_year": str(exported_metadata.filing_year),
        "cadrumo_period": exported_metadata.period.registry_token,
        "cadrumo_engine_version": "calc-sheets/0.1.0",
        "cadrumo_registry_sha": exported_metadata.registry_sha,
    }

    verdict, metadata = _classify_metadata_match(prechange_pairs, snapshot)

    assert verdict is MetadataMatchState.STALE
    with pytest.raises(OutboundStorageConflictError) as raised:
        _require_matching_metadata(
            spreadsheet_id="real-modelo-369-exterior-workbook",
            metadata_match=verdict,
            metadata=metadata,
            snapshot=snapshot,
        )

    assert raised.value.context is not None
    assert raised.value.context["workbook_engine_version"] == "calc-sheets/0.1.0"
    assert raised.value.context["expected_engine_version"] == CALC_SHEETS_ENGINE_VERSION
    assert raised.value.translated_message == "adapters.google.calc_sheets.errors.workbook_snapshot_mismatch"


def test_current_exterior_workbook_layout_stamp_is_accepted_before_pull_layout() -> None:
    """The matching live M369 exterior export remains eligible for pull."""

    snapshot = bundled_authority().snapshot("369", filing_year=2026, period="EXT-1T", on=date(2026, 3, 31))
    exported_metadata = build_export_plan(snapshot).metadata
    current_pairs = {
        "cadrumo_modelo_id": exported_metadata.modelo_id,
        "cadrumo_revision_id": exported_metadata.revision_id,
        "cadrumo_filing_year": str(exported_metadata.filing_year),
        "cadrumo_period": exported_metadata.period.registry_token,
        "cadrumo_engine_version": exported_metadata.engine_version,
        "cadrumo_registry_sha": exported_metadata.registry_sha,
    }

    verdict, metadata = _classify_metadata_match(current_pairs, snapshot)

    assert exported_metadata.engine_version == CALC_SHEETS_ENGINE_VERSION
    assert verdict is MetadataMatchState.MATCHES
    _require_matching_metadata(
        spreadsheet_id="real-modelo-369-exterior-workbook",
        metadata_match=verdict,
        metadata=metadata,
        snapshot=snapshot,
    )


# ---------------------------------------------------------------------------
# Public pull validation
# ---------------------------------------------------------------------------


def test_pull_operator_edits_refuses_blank_spreadsheet_id_before_service_build() -> None:
    snapshot = modelo_130_2025_1t_snapshot()

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
        {"metadataKey": "cadrumo_registry_sha", "metadataValue": "old-registry-sha"},
        {"metadataKey": "cadrumo_registry_sha", "metadataValue": "new-registry-sha"},
    )

    with pytest.raises(OutboundStorageConflictError) as raised:
        _merge_developer_metadata_entries(entries)

    assert raised.value.context == {"conflicting_metadata_keys": ["cadrumo_registry_sha"]}
    assert raised.value.translated_message == "adapters.google.calc_sheets.errors.conflicting_duplicate_metadata"
    assert not hasattr(raised.value, "suggestion")


def test_merge_developer_metadata_allows_duplicate_exported_at_for_reapplied_same_slice() -> None:
    """Repeated exports of the same registry slice legitimately carry newer timestamps."""

    pairs = _merge_developer_metadata_entries(
        (
            {"metadataKey": "cadrumo_registry_sha", "metadataValue": "da9952e1610f7db6"},
            {"metadataKey": "cadrumo_registry_sha", "metadataValue": "da9952e1610f7db6"},
            {"metadataKey": "cadrumo_exported_at", "metadataValue": "2026-06-02T17:54:13+00:00"},
            {"metadataKey": "cadrumo_exported_at", "metadataValue": "2026-06-02T17:55:32+00:00"},
        ),
    )

    assert pairs["cadrumo_registry_sha"] == "da9952e1610f7db6"
    assert pairs["cadrumo_exported_at"] == "2026-06-02T17:55:32+00:00"
