"""Tests for shared checker-oracle verdict flow helpers."""

from __future__ import annotations

import pytest

from ..checker_oracle_flow import (
    CheckerObservation,
    CheckerReplayDriver,
    compare_verdict_field,
    normalize_expected_verdicts,
    normalize_verdict_mapping,
    observed_verdict,
    replay_parse_operation,
)
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_normalize_verdict_mapping_uppercases_identifiers_and_lowercases_verdicts() -> None:
    result = normalize_verdict_mapping(
        {" a28015865 ": " VALID "},
        blank_message="blank verdict mapping",
    )

    assert result == {"A28015865": "valid"}


def test_normalize_verdict_mapping_rejects_blank_identifier() -> None:
    with pytest.raises(RegistryValidationError, match="blank verdict mapping"):
        normalize_verdict_mapping({" ": "valid"}, blank_message="blank verdict mapping")


def test_normalize_expected_verdicts_stringifies_inputs_before_normalizing() -> None:
    result = normalize_expected_verdicts(
        {"123": " VALID "},
        blank_message="blank expected verdict",
    )

    assert result == {"123": "valid"}


def test_replay_parse_operation_returns_single_local_workbook_step() -> None:
    operations = replay_parse_operation("parse-groi-replay")

    assert len(operations) == 1
    assert operations[0].kind == "local_workbook"
    assert operations[0].action == "parse-groi-replay"


def test_canonical_replay_driver_decodes_real_observation() -> None:
    driver = CheckerReplayDriver(surface_label="GROI replay", replay_action="parse-groi-replay")

    observation = driver.collect_observation(
        b'{"observed": {"a28015865": "VALID"}, "raw_evidence_locator": "corpus/groi.json"}',
        expected={},
    )

    assert isinstance(observation, CheckerObservation)
    assert observation.values == {"A28015865": "valid"}
    assert observation.raw_evidence_locator == "corpus/groi.json"


def test_observed_verdict_uses_uppercase_lookup() -> None:
    assert observed_verdict({"A28015865": "valid"}, "a28015865") == "valid"


def test_compare_verdict_field_marks_missing_observation_as_mismatch() -> None:
    result = compare_verdict_field("A28015865", "valid", observed=None)

    assert result.name == "A28015865"
    assert result.observed == "<missing>"
    assert result.verdict == "mismatch"


def test_compare_verdict_field_normalizes_observed_verdict_before_matching() -> None:
    result = compare_verdict_field("A28015865", "valid", observed=" VALID ")

    assert result.observed == "valid"
    assert result.verdict == "match"
