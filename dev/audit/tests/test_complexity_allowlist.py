"""The reviewed complexity allowlist refuses to become a mute button.

Two properties make this file an allowlist rather than a silencer, and both are
pinned here because either one lapsing turns it into the thing it replaced:

* an entry with no reason is REFUSED, so the judgement cannot be omitted;
* an entry pins the score it was accepted AT, so a row that grows past the
  reviewed value fails again instead of riding the old acceptance.

The committed file is checked too, because a mechanism that only holds for
synthetic input says nothing about the acceptances actually in the tree.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from ..complexity_allowlist import ALLOWLIST_PATH, ComplexityAllowlistError, load_allowlist

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    target = tmp_path / "complexity_allowlist.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_an_entry_without_a_reason_is_refused(tmp_path: Path) -> None:
    """A reasonless acceptance is the mute button this file exists to prevent."""
    target = _write(tmp_path, {"production": {"cyclomatic": {"a.py::f": {"score": 12}}}})

    with pytest.raises(ComplexityAllowlistError, match="must state a non-empty reason"):
        load_allowlist(is_test_run=False, path=target)


def test_a_blank_reason_is_refused_too(tmp_path: Path) -> None:
    """Whitespace is not a reason; the check is on content, not presence."""
    target = _write(tmp_path, {"production": {"cyclomatic": {"a.py::f": {"score": 12, "reason": "   "}}}})

    with pytest.raises(ComplexityAllowlistError, match="must state a non-empty reason"):
        load_allowlist(is_test_run=False, path=target)


def test_an_entry_without_a_score_is_refused(tmp_path: Path) -> None:
    """Acceptance is pinned to a value, so an entry that names none is meaningless."""
    target = _write(tmp_path, {"production": {"cyclomatic": {"a.py::f": {"reason": "flat chain"}}}})

    with pytest.raises(ComplexityAllowlistError, match="must state the numeric score"):
        load_allowlist(is_test_run=False, path=target)


def test_the_accepted_score_is_what_a_later_run_is_measured_against(tmp_path: Path) -> None:
    """The ceiling is the reviewed value, which is what makes further growth fail.

    Anti-vacuity: the assertion would hold for any number if the loader dropped
    the score, so it is compared against the value written rather than merely
    checked non-empty.
    """
    target = _write(
        tmp_path,
        {"production": {"cyclomatic": {"a.py::f": {"score": 12, "reason": "flat guard chain, depth 2"}}}},
    )

    allowlist = load_allowlist(is_test_run=False, path=target)

    assert allowlist.ceilings("cyclomatic") == {"a.py::f": 12.0}
    assert allowlist.cyclomatic["a.py::f"].reason == "flat guard chain, depth 2"


def test_a_missing_file_accepts_nothing(tmp_path: Path) -> None:
    """Absence must mean "no acceptances", never "accept everything"."""
    allowlist = load_allowlist(is_test_run=False, path=tmp_path / "absent.json")

    assert allowlist.ceilings("cyclomatic") == {}
    assert allowlist.ceilings("maintainability") == {}
    assert allowlist.ceilings("cognitive") == {}


def test_the_committed_allowlist_states_a_reason_for_every_entry() -> None:
    """The real file, not a fixture: every acceptance in the tree is justified."""
    allowlist = load_allowlist(is_test_run=False, path=ALLOWLIST_PATH)

    entries = {
        **allowlist.cyclomatic,
        **allowlist.maintainability,
        **allowlist.cognitive,
    }
    assert entries, "the committed allowlist is empty; this gate would pass vacuously"
    unreasoned = sorted(key for key, entry in entries.items() if len(entry.reason) < 20)
    assert unreasoned == [], f"acceptances whose reason is too short to be one: {unreasoned}"


#: ``dev/audit/complexity_allowlist.json`` -> the checkout root the keys are relative to.
_REPO_ROOT = ALLOWLIST_PATH.resolve().parents[2]


def _committed_keys() -> list[str]:
    """Every ``path::function`` key in the committed file, across scopes and metrics."""
    raw = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    keys: list[str] = []
    for scope, metrics in raw.items():
        if not isinstance(metrics, dict):
            continue
        for entries in metrics.values():
            if isinstance(entries, dict):
                keys.extend(str(key) for key in entries)
    assert keys, f"no allowlist keys found across scopes {sorted(raw)}; the walk is wrong, not the file"
    return keys


def _defined_names(source: str) -> set[str]:
    """Every definition in one module, as the dotted name the allowlist keys use.

    Keys address methods as ``Class.method``, so a bare-name set would report
    every method key as missing. The walk therefore carries the enclosing
    qualifier, and emits both the qualified and the bare form so a key written
    either way resolves.
    """
    names: set[str] = set()

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                qualified = f"{prefix}{child.name}"
                names.add(qualified)
                names.add(child.name)
                visit(child, f"{qualified}.")
            else:
                visit(child, prefix)

    visit(ast.parse(source), "")
    return names


def test_every_committed_allowlist_key_still_resolves_to_something_that_exists() -> None:
    """An acceptance must not outlive its subject.

    The other gates in this module enforce that an entry states a reason and a
    score. None of them asks whether the thing being accepted is still there, so
    a key could outlive the function it names indefinitely while presenting as a
    reviewed, justified acceptance -- and whatever later took that name would
    inherit a silent exemption nobody granted it. That is not hypothetical: one
    such entry was found in this file, naming a function that had been renamed.

    The resolver is AST-name-based, so a DECORATED target still resolves: the
    decorator does not change the ``def``. A target that exists only at runtime
    -- generated, or bound dynamically -- would not resolve, and would red here
    while being perfectly legitimate. No such entry exists today. If one is ever
    added, the fix is to distinguish STALE from UNRESOLVABLE rather than to
    delete the honest entry or to weaken this gate.
    """
    missing_files: list[str] = []
    stale: list[str] = []
    inherited: list[str] = []

    for key in _committed_keys():
        path_part, _, symbol = key.partition("::")
        target = _REPO_ROOT / path_part
        if not target.is_file():
            missing_files.append(key)
            continue
        if not symbol:
            continue
        defined = _defined_names(target.read_text(encoding="utf-8"))
        if symbol in defined:
            continue
        # STALE versus UNRESOLVABLE, and the difference is the whole gate. A
        # dotted key whose leading qualifier IS defined here names a member the
        # complexity tool attributed to that class while the definition lives on
        # a base in another module -- absent from this file and entirely
        # legitimate. A key whose qualifier is also absent, or which carries no
        # qualifier at all, names nothing this file has: that is an acceptance
        # that outlived its subject.
        qualifier = symbol.rpartition(".")[0]
        if qualifier and qualifier in defined:
            inherited.append(key)
        else:
            stale.append(key)

    assert missing_files == [], (
        "allowlist acceptances whose FILE no longer exists, so the acceptance can never be "
        f"re-examined and silently exempts nothing: {sorted(missing_files)}"
    )
    assert stale == [], (
        "allowlist acceptances naming a function, method or class this file does not define and "
        "whose qualifier it does not define either: the acceptance has outlived its subject, and "
        f"whatever later takes that name inherits an exemption nobody reviewed: {sorted(stale)}"
    )
    for key in inherited:
        qualifier = key.partition("::")[2].rpartition(".")[0]
        assert qualifier, f"classified {key!r} as inherited without a qualifier, so the classifier is wrong"
