"""Structural guard for the retrospective S175 c941 family census."""

from __future__ import annotations

from dev.quality.registry_facade_family_census import exact_relocation_candidates, generated_rows


def test_c941_registry_relocation_family_is_the_fixed_78_row_set() -> None:
    """The retrospective audit must not silently scan a different relocation family."""
    candidates = exact_relocation_candidates()

    assert len(candidates) == 78
    assert len({candidate.old_path for candidate in candidates}) == 78
    assert len({candidate.new_path for candidate in candidates}) == 78


def test_generated_rows_preserve_one_row_per_exact_c941_candidate() -> None:
    """Every template row remains tied to one historic rename and its derived census."""
    rows = generated_rows()

    assert len(rows) == 78
    assert len({(row["old_path"], row["new_path"]) for row in rows}) == 78
    assert all(set(row["consumers"]) >= {"production", "test", "documentation", "tooling"} for row in rows)
