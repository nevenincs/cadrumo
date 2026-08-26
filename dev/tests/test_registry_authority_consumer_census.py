"""Conformance tests for the generated registry-authority consumer census."""

from __future__ import annotations

import json

import pytest

from dev.quality.registry_authority_consumer_census import (
    CATEGORIES,
    OUTPUT_PATH,
    SCHEMA_VERSION,
    TARGET_MODULE,
    TARGET_PATH,
    census_document,
    check_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_authority_consumer_census_matches_current_tree() -> None:
    """Checked bytes must equal the deterministic current-source derivation."""
    checked = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    assert checked == census_document()
    assert checked["schema_version"] == SCHEMA_VERSION
    assert checked["target_module"] == TARGET_MODULE
    assert checked["target_path"] == TARGET_PATH
    assert checked["consumer_categories"] == list(CATEGORIES)
    assert set(checked["consumers"]) == set(CATEGORIES)
    assert checked["definitions"]


def test_registry_authority_consumer_census_refuses_drift() -> None:
    """Check mode rejects a missing consumer rather than trusting fixed counts."""
    drifted = census_document()
    drifted["consumers"] = dict(drifted["consumers"])
    populated_category = next(category for category in CATEGORIES if drifted["consumers"][category])
    drifted["consumers"][populated_category] = drifted["consumers"][populated_category][1:]

    with pytest.raises(RuntimeError, match="consumer census drifted"):
        check_document(drifted)
