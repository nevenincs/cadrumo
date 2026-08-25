"""Codebase-wide module and callable size ratchets, against a generated band.

The limits live in the committed, GENERATED table
``dev/audit/size_budget_baseline.json`` rather than in a hand-maintained dict
here. That is the whole point of this module's current shape: the predecessor
kept per-module pins inline, each documented in prose as sitting at exactly the
present size with no headroom, and peers then split or shrank those modules
without lowering the pins. The mechanism kept working while its numbers rotted —
aggregate positive slack reached 9139 lines, the widest single entry permitted
1261 lines of regrowth, and thirteen entries had fallen below the DEFAULT limit,
making the override pure dead weight. Every one of those gates reported green.

So the ratchet is now two-sided and its numbers are machine-written:

* an entry that GROWS past its limit fails, as before, and
* a limit that DRIFTS above its subject past the declared slack tolerance also
  fails, because that gap is exactly the window of invisible regrowth.

A stale limit is therefore self-reporting instead of silently permissive, and the
remedy is one command rather than a hand-edit whose prose decays again:
``python -m dev.audit.size_budget --write-baseline``, reviewed and committed.

Headroom policy is declared once, in :mod:`._size_budget`, not restated in
comments that can go stale: a limit is the measured size plus five percent, and
the tolerated slack is ten percent of the limit, each with a small absolute
floor. Zero-headroom pinning was the predecessor's stated policy and is what
produced the churn, because in a tree with many concurrent authors it reds on the
next landing and gets hand-raised.

Both scans refuse an under-populated corpus, and both ratchet directions carry a
positive control that drives the real production scanner over a real temporary
tree, so a pass here cannot be a pass by measuring nothing. No mocks or skips.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.core import scan_directory
from cadrumo.tests._size_budget import (
    CALLABLE_POLICY,
    MIN_SCANNED_CALLABLES,
    MIN_SCANNED_MODULES,
    MODULE_POLICY,
    EmptyScanError,
    assert_real_corpus,
    build_limits,
    callable_key,
    evaluate_budget,
    measure_callable_lines,
    measure_module_lines,
    scan_callable_lines,
    scan_module_lines,
)

from ..._paths import REPO_ROOT
from ..size_budget import (
    SIZE_BUDGET_BASELINE_PATH,
    load_size_budget_baseline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REGENERATE = "python -m dev.audit.size_budget --write-baseline"


def _write_module(root: Path, name: str, lines: int) -> Path:
    """Write a real module of exactly *lines* physical lines and return its path."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"x{index} = {index}" for index in range(lines)) + "\n", encoding="utf-8")
    return path


def _write_callable_module(root: Path, name: str, function: str, body_lines: int) -> Path:
    """Write a real module holding one function whose body spans *body_lines* lines."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"    x{index} = {index}" for index in range(body_lines))
    path.write_text(f"def {function}() -> None:\n{body}\n", encoding="utf-8")
    return path


def test_size_budget_baseline_is_committed_and_populated() -> None:
    """The generated limit table exists and carries real entries.

    An absent or empty baseline would silently degrade both ratchets to their
    default limits, which is a quiet loosening rather than a loud failure.
    """
    assert SIZE_BUDGET_BASELINE_PATH.is_file(), (
        f"missing generated size baseline: {SIZE_BUDGET_BASELINE_PATH}. Regenerate it with `{_REGENERATE}`."
    )
    baseline = load_size_budget_baseline()
    assert baseline.modules, "the generated size baseline declares no module limits"
    assert baseline.callables, "the generated size baseline declares no callable limits"


def test_measured_corpus_is_populated() -> None:
    """The source and AST walks really reach the tree before anything is judged."""
    modules = measure_module_lines()
    callables = measure_callable_lines()
    assert_real_corpus(modules, callables)
    assert len(modules) >= MIN_SCANNED_MODULES
    assert len(callables) >= MIN_SCANNED_CALLABLES


def _synthetic_corpus(count: int) -> dict[str, int]:
    """Return a populated ``count``-entry stand-in corpus for guard controls."""
    return {f"m{index}.py": 1 for index in range(count)}


def test_empty_corpus_is_refused_rather_than_reported_clean() -> None:
    """The corpus guard discriminates: a near-empty scan raises instead of passing."""
    populated_callables = _synthetic_corpus(MIN_SCANNED_CALLABLES)
    populated_modules = _synthetic_corpus(MIN_SCANNED_MODULES)

    with pytest.raises(EmptyScanError, match="modules"):
        assert_real_corpus({"a.py": 1}, populated_callables)
    with pytest.raises(EmptyScanError, match="callables"):
        assert_real_corpus(populated_modules, {"a.py::f": 1})

    assert_real_corpus(populated_modules, populated_callables)


def test_tracked_python_modules_stay_inside_their_declared_band() -> None:
    """No module grows past its limit, and no module limit outlives its subject."""
    actuals = measure_module_lines()
    callables = measure_callable_lines()
    assert_real_corpus(actuals, callables)

    verdict = evaluate_budget(actuals, load_size_budget_baseline().modules, MODULE_POLICY)
    assert verdict.over_budget == (), (
        "Python module size budget exceeded. Extract a cohesive concern into a sibling module; "
        f"a plain `{_REGENERATE}` will NOT lift a ceiling you broke through:\n  " + "\n  ".join(verdict.over_budget)
    )
    assert verdict.stale == (), (
        "Python module size limits have drifted above their subject, permitting silent regrowth. "
        f"Re-measure the band with `{_REGENERATE}`:\n  " + "\n  ".join(verdict.stale)
    )


def test_tracked_production_callables_stay_inside_their_declared_band() -> None:
    """No production callable grows past its limit, and no limit outlives its subject."""
    modules = measure_module_lines()
    actuals = measure_callable_lines()
    assert_real_corpus(modules, actuals)

    verdict = evaluate_budget(actuals, load_size_budget_baseline().callables, CALLABLE_POLICY)
    assert verdict.over_budget == (), (
        "Python callable size budget exceeded. Extract named helpers; "
        f"a plain `{_REGENERATE}` will NOT lift a ceiling you broke through:\n  " + "\n  ".join(verdict.over_budget)
    )
    assert verdict.stale == (), (
        "Python callable size limits have drifted above their subject, permitting silent regrowth. "
        f"Re-measure the band with `{_REGENERATE}`:\n  " + "\n  ".join(verdict.stale)
    )


def test_module_ratchet_reports_growth_past_its_limit(tmp_path: Path) -> None:
    """Positive control: the real module scanner names an oversize module and its count.

    The production scan function is driven over a real on-disk tree rather than a
    stand-in, so this proves the shipped measurement path discriminates, not that
    a test-local reimplementation of it does.
    """
    over = MODULE_POLICY.default_limit + 40
    _write_module(tmp_path, "grew.py", over)
    _write_module(tmp_path, "held.py", MODULE_POLICY.default_limit)

    actuals = scan_module_lines(files=scan_directory(tmp_path, pattern="*.py", recursive=True), root=tmp_path)
    assert actuals == {"grew.py": over, "held.py": MODULE_POLICY.default_limit}

    verdict = evaluate_budget(actuals, {}, MODULE_POLICY)
    assert verdict.over_budget == (f"grew.py: {over} lines > limit {MODULE_POLICY.default_limit}",)
    assert verdict.stale == ()


def test_module_ratchet_reports_a_limit_that_drifted_above_its_subject(tmp_path: Path) -> None:
    """Positive control: a limit further above actual than tolerated is itself a finding.

    This is the property the predecessor lacked. A shrunk module whose pin was
    never lowered passed silently; here it is named, with the exact regrowth
    window it was permitting.
    """
    actual = MODULE_POLICY.default_limit + 10
    _write_module(tmp_path, "shrank.py", actual)
    actuals = scan_module_lines(files=scan_directory(tmp_path, pattern="*.py", recursive=True), root=tmp_path)

    inside = MODULE_POLICY.limit_for(actual)
    assert evaluate_budget(actuals, {"shrank.py": inside}, MODULE_POLICY).stale == ()

    drifted = actual + MODULE_POLICY.max_slack_for(actual) + 200
    stale = evaluate_budget(actuals, {"shrank.py": drifted}, MODULE_POLICY).stale
    assert len(stale) == 1
    assert stale[0].startswith(f"shrank.py: pinned at {drifted} but measures {actual}")
    assert "invisible regrowth" in stale[0]


def test_module_ratchet_reports_a_limit_the_default_already_covers(tmp_path: Path) -> None:
    """Positive control: an override for a module now under the default is dead weight."""
    actual = MODULE_POLICY.default_limit - 300
    _write_module(tmp_path, "split.py", actual)
    actuals = scan_module_lines(files=scan_directory(tmp_path, pattern="*.py", recursive=True), root=tmp_path)

    stale = evaluate_budget(actuals, {"split.py": MODULE_POLICY.default_limit + 400}, MODULE_POLICY).stale
    assert len(stale) == 1
    assert "dead weight" in stale[0]


def test_module_ratchet_reports_a_limit_whose_subject_left_the_tree(tmp_path: Path) -> None:
    """Positive control: a limit naming a vanished module is reported, not ignored."""
    _write_module(tmp_path, "present.py", 10)
    actuals = scan_module_lines(files=scan_directory(tmp_path, pattern="*.py", recursive=True), root=tmp_path)

    stale = evaluate_budget(actuals, {"deleted.py": 1400}, MODULE_POLICY).stale
    assert stale == ("deleted.py: pinned at 1400 but absent from the scanned corpus",)


def test_callable_ratchet_reports_growth_past_its_limit(tmp_path: Path) -> None:
    """Positive control: the real callable scanner names an oversize body and its count."""
    body = CALLABLE_POLICY.default_limit + 20
    path = _write_callable_module(tmp_path, "grew.py", "grew", body)
    _write_callable_module(tmp_path, "held.py", "held", CALLABLE_POLICY.default_limit - 1)

    items = tuple(
        (candidate, ast.parse(candidate.read_text(encoding="utf-8")))
        for candidate in scan_directory(tmp_path, pattern="*.py", recursive=True)
    )
    actuals = scan_callable_lines(items=items, root=tmp_path)
    measured = len(path.read_text(encoding="utf-8").splitlines())
    assert actuals[callable_key("grew.py", "grew")] == measured

    verdict = evaluate_budget(actuals, {}, CALLABLE_POLICY)
    assert verdict.over_budget == (f"grew.py::grew: {measured} lines > limit {CALLABLE_POLICY.default_limit}",)


def test_generated_limits_sit_above_their_measured_subject() -> None:
    """The generator's band is coherent: every generated limit exceeds its actual.

    Guards the arithmetic itself, so a policy edit that inverted the band (a
    limit at or below the size it was taken from) fails here rather than reddening
    the whole fleet on the next landing.
    """
    actuals = measure_module_lines()
    limits = build_limits(actuals, MODULE_POLICY)
    assert limits, "the module limit table generated from the real tree is empty"
    for key, limit in limits.items():
        assert limit > actuals[key], f"{key}: generated limit {limit} does not exceed measured {actuals[key]}"
        assert actuals[key] > MODULE_POLICY.default_limit, f"{key}: generated a limit the default already covers"


def test_regeneration_refuses_to_launder_a_live_offender() -> None:
    """Positive control: re-measuring never lifts a ceiling a subject broke through.

    This is the property that keeps a staleness fix from becoming the very thing
    the accepted size-budget decision rejected -- raising a ceiling in place of
    refactoring. A compliant subject is re-banded; an offender keeps its ceiling
    and stays red until its owner extracts or growth is explicitly accepted.
    """
    default = MODULE_POLICY.default_limit
    actuals = {"offender.py": default + 400, "compliant.py": default + 100}
    previous = {"offender.py": default + 200, "compliant.py": default + 900}

    clamped = build_limits(actuals, MODULE_POLICY, previous=previous)
    assert clamped["offender.py"] == default + 200, "an offender's broken ceiling must not be raised"
    assert evaluate_budget(actuals, clamped, MODULE_POLICY).over_budget == (
        f"offender.py: {default + 400} lines > limit {default + 200}",
    )

    assert clamped["compliant.py"] == MODULE_POLICY.limit_for(default + 100), (
        "a compliant subject is re-banded to its measured size"
    )
    assert clamped["compliant.py"] < previous["compliant.py"], "re-banding a compliant subject lowers its ceiling"

    accepted = build_limits(actuals, MODULE_POLICY, previous=previous, accept_growth=True)
    assert accepted["offender.py"] == MODULE_POLICY.limit_for(default + 400), (
        "explicit growth acceptance is the only path that raises a broken ceiling"
    )


def test_committed_baseline_matches_a_regeneration_of_itself() -> None:
    """The committed table is reachable from the tree it claims to describe.

    Not a byte-equality check against current actuals -- peers land continuously,
    so that would red constantly. This asserts the weaker, durable property: every
    committed key is one the generator would still emit, so the table cannot carry
    an entry for a subject the generator no longer considers over budget.
    """
    committed = load_size_budget_baseline()
    module_keys = set(build_limits(measure_module_lines(), MODULE_POLICY))
    orphans = sorted(set(committed.modules) - module_keys)
    assert orphans == [], (
        f"committed module limits no longer generated from the tree; re-measure with `{_REGENERATE}`:\n  "
        + "\n  ".join(orphans)
    )


def test_baseline_notes_stay_attached_to_a_live_limit() -> None:
    """Prose notes are the one hand-maintained surface; none may outlive its key."""
    baseline = load_size_budget_baseline()
    live = set(baseline.modules) | set(baseline.callables)
    orphans = sorted(key for key in baseline.notes if key not in live)
    assert orphans == [], "baseline notes reference keys that carry no limit:\n  " + "\n  ".join(orphans)


def test_baseline_notes_carry_no_pinned_numbers() -> None:
    """Notes are prose only, so they cannot go numerically stale the way pins did.

    The predecessor's decay was numeric claims embedded in prose ("pinned at
    EXACTLY the present size"). Keeping digits out of the note surface removes
    the class rather than trusting authors to keep it true.
    """
    offenders = [
        f"{key}: {value}"
        for key, value in load_size_budget_baseline().notes.items()
        if any(token.isdigit() and len(token) >= 3 for token in value.replace(",", " ").split())
    ]
    assert offenders == [], (
        "baseline notes must not restate line counts; they decay while the generated limits do not:\n  "
        + "\n  ".join(offenders)
    )


def test_baseline_path_resolves_under_the_repository() -> None:
    """The gate reads the same committed artifact the generator writes."""
    assert SIZE_BUDGET_BASELINE_PATH == REPO_ROOT / "dev" / "audit" / "size_budget_baseline.json"
