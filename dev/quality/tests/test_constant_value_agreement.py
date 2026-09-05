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
    collect_unevaluated_constants,
    constant_census,
    stem_restatements,
    unevaluated_collisions,
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


def test_a_canonical_constant_restated_under_a_decorated_name_is_detected() -> None:
    """The defect this kind exists for: the same value under a related name.

    Keying on the name alone cannot reach this. A grep for either spelling
    returns one definition and reads as canonical, which is how a restatement
    survives review and then drifts when the real constant moves.
    """
    findings = stem_restatements(
        {
            "KDF_SALT_BYTES": {"storage/_kdf_salt.py": "16"},
            "_RECOVERY_KDF_SALT_BYTES": {"user_profile/recovery.py": "16"},
        }
    )
    assert [item.kind for item in findings] == ["stem_restatement"]
    assert findings[0].sites == (
        ("storage/_kdf_salt.py", "16"),
        ("user_profile/recovery.py", "16"),
    )


def test_two_names_sharing_a_stem_but_not_a_value_are_not_restatements() -> None:
    """Disagreement is a different defect, and the name-keyed kinds own it."""
    assert (
        stem_restatements(
            {
                "KEY_SIZE": {"crypto/aead.py": "32"},
                "_RECOVERY_KEY_SIZE": {"storage/recovery.py": "16"},
            }
        )
        == ()
    )


def test_a_single_segment_stem_does_not_pair_every_length_in_the_tree() -> None:
    """``BYTES`` is a unit, not a concept; pairing on it would report noise."""
    assert (
        stem_restatements(
            {
                "BYTES": {"a.py": "16"},
                "_SALT_BYTES": {"b.py": "16"},
            }
        )
        == ()
    )


def test_two_schema_versions_that_both_start_at_one_are_not_paired() -> None:
    """Each schema owns its version, so agreeing at 1 is where both began."""
    assert (
        stem_restatements(
            {
                "_SCHEMA_VERSION": {"telemetry/schema.py": "1"},
                "_BUNDLE_SCHEMA_VERSION": {"user_profile/bundle.py": "1"},
            }
        )
        == ()
    )


def test_one_module_holding_both_names_is_not_a_cross_module_restatement() -> None:
    """A local alias beside its source is visible; the screen targets distance."""
    assert (
        stem_restatements(
            {
                "SALT_BYTES": {"a.py": "16"},
                "_LOCAL_SALT_BYTES": {"a.py": "16"},
            }
        )
        == ()
    )


def test_one_name_bound_to_the_same_call_in_two_modules_is_detected() -> None:
    """The defect: a constant the literal census cannot evaluate, redeclared.

    Three registry modules each bound `_NUMERIC_TUPLE_ADAPTER` to the same
    TypeAdapter call and two of those copies were dead. No literal-only census
    could see them, because a call has no value to compare.
    """
    findings = unevaluated_collisions(
        {
            "_NUMERIC_TUPLE_ADAPTER": {
                "registry/record_design.py": "TypeAdapter(tuple[int | float, ...])",
                "registry/record_design_pdf_state.py": "TypeAdapter(tuple[int | float, ...])",
            }
        }
    )
    assert [item.kind for item in findings] == ["unevaluated_name_collision"]


def test_a_per_module_logger_is_not_reported_however_many_modules_hold_it() -> None:
    """`get_logger(__name__)` is the correct idiom; eighty of them are not a defect."""
    assert unevaluated_collisions({"_log": {f"pkg/mod{index}.py": "get_logger(__name__)" for index in range(80)}}) == ()


def test_two_configured_instances_of_one_helper_are_not_a_redeclaration() -> None:
    """Differing arguments mean reuse is working, not that a concept was copied."""
    assert (
        unevaluated_collisions(
            {
                "_playwright_stage": {
                    "sede/groi_check.py": "build_playwright_stage_runner(surface_label='GROI')",
                    "sede/nif_iva_check.py": "build_playwright_stage_runner(surface_label='NIF-IVA')",
                }
            }
        )
        == ()
    )


def test_an_evaluable_literal_stays_with_the_literal_census(tmp_path: Path) -> None:
    """The unevaluated collector must not double-report what the census reads."""
    (tmp_path / "mod.py").write_text("_LITERAL = 16\n_CALLED = frozenset({'a'})\n", encoding="utf-8")
    collected = collect_unevaluated_constants(tmp_path)
    assert "_LITERAL" not in collected
    assert collected["_CALLED"] == {"mod.py": "frozenset({'a'})"}


def test_a_value_built_from_an_imported_authority_cannot_drift() -> None:
    """The distinction that took the collision backlog from 35 to 3.

    Four sede modules each bind SEDE_BASE to EXTERNAL.aeat.domains.www6. That is
    four local bindings of ONE value: every copy resolves to whatever the
    authority says, so no edit can leave one of them stale. Reporting it beside
    a retyped literal would bury the three findings that can actually diverge.
    """
    findings = unevaluated_collisions(
        {
            "SEDE_BASE": {
                "sede/notifications.py": "EXTERNAL.aeat.domains.www6",
                "sede/walker.py": "EXTERNAL.aeat.domains.www6",
            }
        }
    )
    assert [item.kind for item in findings] == ["derived_name_collision"]


def test_a_value_retyped_from_literals_is_a_second_source_of_truth() -> None:
    """Five modules each retyped the hex alphabet; a change to one left four stale."""
    findings = unevaluated_collisions(
        {
            "_HEX_DIGITS": {
                "storage/_integrity.py": "frozenset('0123456789abcdef')",
                "attachments/models.py": "frozenset('0123456789abcdef')",
            }
        }
    )
    assert [item.kind for item in findings] == ["unevaluated_name_collision"]


def test_a_constructor_name_does_not_make_a_literal_look_derived() -> None:
    """``frozenset`` and ``re.compile`` build a value; they do not read one.

    Counting them as authorities would reclassify every literal set and pattern
    in the tree as safe, which is the failure direction that hides real drift.
    """
    for expression in (
        "frozenset({'.csv', '.txt'})",
        "re.compile('[^a-z0-9]+')",
        "Decimal('3005.06')",
    ):
        findings = unevaluated_collisions({"_X": {"a.py": expression, "b.py": expression}})
        assert [item.kind for item in findings] == ["unevaluated_name_collision"], expression
