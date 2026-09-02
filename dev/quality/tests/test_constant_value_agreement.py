"""Gate: no public constant name carries more than one value.

The corpus satisfies this today, so the condition is constructed as well as
pinned. A gate that has only ever seen a clean tree has not been shown able to
refuse a dirty one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..constant_value_agreement import (
    _PACKAGE_ROOT,
    collect_constants,
    constant_census,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def constants() -> dict[str, dict[str, str]]:
    return collect_constants(_PACKAGE_ROOT)


def test_no_public_constant_name_carries_two_values(constants: dict[str, dict[str, str]]) -> None:
    """A public name meaning two values gives a consumer no signal that the import matters."""
    offenders = {
        item.name: item.detail for item in constant_census(constants) if item.kind == "value_conflict" and item.public
    }
    assert offenders == {}, f"public constants whose value depends on which module you import: {offenders}"


def test_the_gate_detects_a_public_constant_defined_with_two_values() -> None:
    """Constructed, because the corpus carries none."""
    planted = {"TIMEOUT_SECONDS": {"core/a.py": "30", "core/b.py": "5"}}
    findings = constant_census(planted)
    assert [(item.kind, item.public) for item in findings] == [("value_conflict", True)]


def test_a_private_conflict_is_reported_but_not_public(constants: dict[str, dict[str, str]]) -> None:
    """Private conflicts exist and are scoped by the underscore that names them.

    Pinned against the corpus: these are real, and they are the reason the gate
    is keyed on visibility rather than refusing every disagreement.
    """
    conflicts = [item for item in constant_census(constants) if item.kind == "value_conflict"]
    assert conflicts, "the corpus is expected to carry private value conflicts"
    assert all(not item.public for item in conflicts)


def test_agreement_and_conflict_are_separate_kinds() -> None:
    """Repetition and ambiguity are different findings and must not merge."""
    planted = {
        "SAME": {"core/a.py": "'x'", "core/b.py": "'x'"},
        "DIFFERENT": {"core/a.py": "'x'", "core/b.py": "'y'"},
    }
    kinds = {item.name: item.kind for item in constant_census(planted)}
    assert kinds == {"SAME": "value_agreement", "DIFFERENT": "value_conflict"}


def test_a_name_only_one_module_defines_is_not_reported() -> None:
    """One definition is the normal case and must never produce a row."""
    assert constant_census({"ALONE": {"core/a.py": "1"}}) == ()


def test_a_non_literal_constant_is_declined_rather_than_guessed_at(tmp_path: Path) -> None:
    """A value the screen cannot evaluate is skipped, never approximated.

    Comparing a guessed value would be worse than comparing nothing: it would
    report agreement or conflict that the source does not support.
    """
    (tmp_path / "mod.py").write_text("COMPUTED = sorted([3, 1])\nLITERAL = 'x'\n", encoding="utf-8")
    collected = collect_constants(tmp_path)
    assert "COMPUTED" not in collected
    assert collected["LITERAL"] == {"mod.py": "'x'"}


def test_a_boolean_is_not_treated_as_a_shared_value(tmp_path: Path) -> None:
    """``True`` under one name in two modules is not evidence of anything."""
    (tmp_path / "a.py").write_text("ENABLED = True\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("ENABLED = False\n", encoding="utf-8")
    assert "ENABLED" not in collect_constants(tmp_path)
