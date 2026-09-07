"""Gate disjunctions satisfied by a CLI token the test supplied itself."""

from __future__ import annotations

import tomllib
from dataclasses import astuple
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..self_echoing_tokens import scan_self_echoing_tokens

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIXTURE = Path("fixture.py")
_TEST_ROOTS = (REPO_ROOT / "src" / "cadrumo", REPO_ROOT / "dev")
_CASES = tomllib.loads(
    (Path(__file__).parent / "fixtures" / "self_echoing_token_cases.toml").read_text(encoding="utf-8")
)


def _case(name: str) -> str:
    """Return one named, non-collected Python specimen."""
    source = _CASES[name]["source"]
    assert isinstance(source, str)
    return source


def _test_modules() -> tuple[Path, ...]:
    """Return every test module, refusing either declared root collapsing."""
    by_root = {root: tuple(root.rglob("test_*.py")) for root in _TEST_ROOTS}
    starved = {root: len(paths) for root, paths in by_root.items() if len(paths) < 500}
    assert not starved, (
        "the self-echoing-token sweep reached fewer than 500 test modules in a "
        f"declared root; modules found per starved root: {starved}"
    )
    return tuple(path for paths in by_root.values() for path in paths)


def _scan(source: str):
    """Scan one synthetic module through the production detector."""
    return scan_self_echoing_tokens(_FIXTURE, source)


def test_the_detector_catches_the_supplied_evidence_flag() -> None:
    """Positive control: reproduce the flag echo that founded the gate."""
    findings = _scan(
        _case("supplied_evidence_flag"),
    )

    assert len(findings) == 1, f"the planted evidence-id echo produced {findings!r}"
    assert astuple(findings[0]) == (
        _FIXTURE,
        3,
        "--evidence-id",
        "--evidence-id",
        "result.output",
    )


def test_the_detector_catches_a_key_rendering_of_a_supplied_value() -> None:
    """The lowercase classification echo is the other supported exact form."""
    findings = _scan(
        _case("supplied_value_rendering"),
    )

    assert len(findings) == 1, f"the planted classification echo produced {findings!r}"
    assert astuple(findings[0]) == (
        _FIXTURE,
        3,
        "classification=business",
        "business",
        "result.output",
    )


def test_four_character_tokens_remain_decidable() -> None:
    """The declared four-character boundary is included, not rounded upward."""
    findings = _scan(
        _case("four_character_token"),
    )

    assert len(findings) == 1
    assert astuple(findings[0])[3] == "show"


def test_overlapping_tokens_report_the_longest_supplied_token() -> None:
    """A nested echo is attributed deterministically to its most specific input."""
    findings = _scan(
        _case("overlapping_tokens"),
    )

    assert len(findings) == 1
    assert astuple(findings[0])[3] == "a=zzzz"


def test_a_function_without_cli_tokens_does_not_end_the_module_sweep() -> None:
    """An irrelevant earlier function cannot hide a later positive instance."""
    findings = _scan(
        _case("preceding_function_without_tokens"),
    )

    assert len(findings) == 1
    assert findings[0].echoed_needle == "--evidence-id"


def test_an_unsupported_operand_does_not_end_the_disjunction_sweep() -> None:
    """A non-membership operand cannot hide a later self-echoing operand."""
    findings = _scan(
        _case("preceding_unsupported_operand"),
    )

    assert len(findings) == 1
    assert findings[0].echoed_needle == "--evidence-id"


@pytest.mark.parametrize(
    "case_name",
    [
        "unbound_haystack_before_echo",
        "bare_haystack_before_echo",
        "missing_preceding_assignment_before_echo",
        "barrier_before_other_echo",
    ],
)
def test_an_unbound_or_overwritten_operand_does_not_hide_a_later_echo(case_name: str) -> None:
    """A rejected membership cannot terminate the remaining disjunction operands."""
    findings = _scan(_case(case_name))

    assert len(findings) == 1
    assert findings[0].echoed_needle == "show"


def test_an_invocation_and_assertion_on_one_line_remain_ordered() -> None:
    """Binding order follows syntax traversal rather than shared line numbers."""
    findings = _scan(_case("same_line_invocation"))

    assert len(findings) == 1
    assert findings[0].echoed_needle == "show"


@pytest.mark.parametrize(
    "case_name",
    [
        "distinct_token",
        "conjunction",
        "short_token",
        "other_caller",
        "dynamic_argv",
        "unrelated_invocation_result",
        "intervening_unsupported_reassignment",
        "intervening_annotated_reassignment",
        "nested_scope_assignment",
        "unbound_result",
        "unrelated_result_attribute",
        "tuple_unpack_reassignment",
        "loop_target_reassignment",
        "starred_unpack_reassignment",
        "with_target_reassignment",
        "except_target_reassignment",
        "dotted_import_reassignment",
        "aliased_import_reassignment",
    ],
)
def test_legitimate_or_mismatched_shapes_are_left_alone(case_name: str) -> None:
    """Only an exact supported invocation and membership disjunction are claimed."""
    findings = _scan(_case(case_name))

    assert findings == (), f"the detector exceeded its closed AST claim: {findings!r}"


def test_no_self_echoing_membership_disjunct_survives_in_the_real_tree() -> None:
    """Sweep every test module under both declared roots."""
    findings = tuple(
        finding
        for path in _test_modules()
        for finding in scan_self_echoing_tokens(path, path.read_text(encoding="utf-8"))
    )

    assert not findings, "disjunctions accept tokens supplied by their own invocation:\n" + "\n".join(
        f"  {finding}" for finding in findings
    )
