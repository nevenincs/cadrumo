"""Structural guard for the retrospective S175 c941 family census."""

from __future__ import annotations

import json
from collections import Counter

import pytest

from dev.quality.registry_facade_family_census import (
    MATRIX_PATH,
    check_matrix_document,
    exact_relocation_candidates,
    generated_rows,
    mechanical_relocation_pairs,
    refresh_reviewed_matrix_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_c941_registry_relocation_family_is_the_fixed_78_row_set() -> None:
    """The retrospective audit must not silently scan a different relocation family."""
    candidates = exact_relocation_candidates()

    assert len(candidates) == 78
    assert len({candidate.old_path for candidate in candidates}) == 78
    assert len({candidate.new_path for candidate in candidates}) == 78


def test_mechanical_delta_pairs_are_the_checked_matrix_denominator() -> None:
    """The matrix denominator is c941 history, not a current filename scan."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    assert mechanical_relocation_pairs() == tuple((row["old_path"], row["new_path"]) for row in document["rows"])


def test_generated_rows_preserve_one_row_per_exact_c941_candidate() -> None:
    """Every template row remains tied to one historic rename and its derived census."""
    rows = generated_rows()

    assert len(rows) == 78
    assert [row["row_id"] for row in rows] == [f"R{number:02d}" for number in range(1, 79)]
    assert len({(row["old_path"], row["new_path"]) for row in rows}) == 78
    for row in rows:
        consumers = row["consumers"]
        locators = row["current_symbol_locators"]
        exported_symbols = row["facade_exported_symbols"]

        assert isinstance(consumers, dict)
        assert isinstance(locators, dict)
        assert isinstance(exported_symbols, list)
        assert set(consumers) >= {"production", "test", "documentation", "tooling"}
        assert set(locators) == set(exported_symbols)


def test_reviewed_matrix_passes_its_exact_census_and_canonical_step_gate() -> None:
    """The checked-in adjudication remains complete and linked to real plan Steps."""
    check_matrix_document(json.loads(MATRIX_PATH.read_text(encoding="utf-8")))


def test_checked_matrix_is_byte_stable() -> None:
    """Check mode verifies the reviewed artifact without rewriting it."""
    before = MATRIX_PATH.read_bytes()

    check_matrix_document(json.loads(before))

    assert MATRIX_PATH.read_bytes() == before


def test_reviewed_refresh_preserves_every_manual_adjudication_field() -> None:
    """A census refresh cannot erase the independently reviewed row decisions."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    refreshed = refresh_reviewed_matrix_document(document)
    reviewed_fields = {
        "semantic_owner",
        "semantic_evidence",
        "disposition",
        "terminal_state",
        "follow_on_step_id",
        "follow_on_action",
        "follow_on_scope",
        "follow_on_predecessors",
    }
    reviewed_rows = document["rows"]
    refreshed_rows = refreshed["rows"]

    assert isinstance(reviewed_rows, list)
    assert isinstance(refreshed_rows, list)

    for before, after in zip(reviewed_rows, refreshed_rows, strict=True):
        assert isinstance(before, dict)
        assert isinstance(after, dict)
        assert {field: before[field] for field in reviewed_fields} == {field: after[field] for field in reviewed_fields}


def test_reviewed_rows_are_one_to_one_complete_and_not_grouped() -> None:
    """Every historical candidate has one reviewed terminal state and one Step."""
    document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    rows = document["rows"]

    assert Counter(row["disposition"] for row in rows) == {
        "keep_public": 54,
        "hard_move_complete": 9,
        "privatize_external_elimination": 13,
        "delete": 2,
    }
    assert len({row["follow_on_step_id"] for row in rows}) == 78
    assert all(row["follow_on_predecessors"] == ["W03.P20.S175"] for row in rows)
    assert all("unresolved" not in row["terminal_state"] for row in rows)
    assert all("unresolved" not in row["semantic_owner"] for row in rows)
