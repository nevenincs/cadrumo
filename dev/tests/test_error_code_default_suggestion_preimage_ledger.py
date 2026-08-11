"""Real-source proof for the retired error-code default-suggestion preimage."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.core.errors import ErrorCode
from dev.quality.error_code_default_suggestion_preimage_ledger import (
    DEFAULT_PREIMAGE_LEDGER_PATH,
    SOURCE_COMMIT,
    ErrorCodeDefaultPreimageError,
    extract_preimage_records,
    load_preimage_ledger,
    render_preimage_ledger,
    validate_preimage_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_checked_in_ledger_matches_the_complete_immutable_error_code_preimage() -> None:
    """All 612 source-located former declarations match their Git preimage exactly."""
    checked_in = load_preimage_ledger()
    extracted = extract_preimage_records()

    assert len(checked_in) == 612
    assert checked_in == extracted
    assert validate_preimage_ledger(checked_in) == checked_in
    assert DEFAULT_PREIMAGE_LEDGER_PATH.read_text(encoding="utf-8") == render_preimage_ledger(checked_in)
    assert {record.source_commit for record in checked_in} == {SOURCE_COMMIT}
    assert {record.disposition_owner_step for record in checked_in} == {
        "S50",
        "S51",
        "S52",
        "S53",
        "S54",
        "S55",
        "S56",
        "S57",
        "S64",
    }


def test_source_locations_keep_repeated_null_defaults_as_distinct_evidence_rows() -> None:
    """Repeated historical ``None`` expressions cannot collapse into one disposition."""
    null_rows = tuple(record for record in load_preimage_ledger() if record.old_value_source == "None")

    assert len(null_rows) > 1
    assert len({record.source_identity for record in null_rows}) == len(null_rows)
    assert len({(record.source_shard, record.source_line, record.source_column) for record in null_rows}) == len(
        null_rows,
    )


def test_exact_gate_reports_missing_extra_duplicate_and_wrong_owner_rows() -> None:
    """The historical gate compares identities, not a permissive aggregate count."""
    records = load_preimage_ledger()

    with pytest.raises(ErrorCodeDefaultPreimageError, match="missing source identities"):
        validate_preimage_ledger(records[1:])

    unexpected = replace(records[0], error_code=f"{records[0].error_code}_UNEXPECTED")
    with pytest.raises(ErrorCodeDefaultPreimageError, match="extra source identities"):
        validate_preimage_ledger((unexpected, *records[1:]))

    with pytest.raises(ErrorCodeDefaultPreimageError, match="duplicates source identity"):
        validate_preimage_ledger((*records, records[0]))

    wrong_owner = replace(records[0], disposition_owner_step="S51")
    with pytest.raises(ErrorCodeDefaultPreimageError, match="must be 'S50' for core"):
        validate_preimage_ledger((wrong_owner, *records[1:]))


def test_live_error_code_model_cannot_reacquire_preimage_policy_fields() -> None:
    """Historical evidence remains separate from the policy-free runtime schema."""
    assert {"default_suggestion", "action", "no_recovery_outcome"}.isdisjoint(ErrorCode.model_fields)
