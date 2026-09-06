"""Tests for the complexity audit's classifiers, which decide its verdict.

Three functions partition every hit into new, regressed, allowed and resolved,
and the audit fails on the first two. Nothing exercised them: the module's own
test files were retired with the baseline and the allowlist they covered, and
the sibling that imports the classifiers - ``dev/audit/report.py`` - is tested
only through a stubbed dimension that never reaches them.

They are pure functions over constructed hits, so the gap costs nothing to
close, and the direction each compares in is the thing worth pinning. Cyclomatic
and cognitive scores are ceilings where higher is worse; the maintainability
index is a floor where LOWER is worse, and a classifier that compared it the
same way as the other two would report every genuine regression as allowed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import complexity
from ..complexity import (
    CcHit,
    CogHit,
    MiHit,
    _cc_key,
    _classify_cc,
    _classify_cog,
    _classify_mi,
    _cog_key,
    build_baseline,
    collect_cc,
    collect_cog,
    load_baseline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _cc(name: str = "widen", score: int = 21) -> CcHit:
    return CcHit(path="src/cadrumo/a.py", name=name, grade="C", score=score)


def _cog(name: str = "widen", score: int = 30) -> CogHit:
    return CogHit(path="src/cadrumo/a.py", name=name, score=score)


def _mi(path: str = "src/cadrumo/a.py", score: float = 18.5) -> MiHit:
    return MiHit(path=path, grade="B", score=score)


def test_a_hit_absent_from_the_baseline_is_new() -> None:
    """With the baseline retired this is every hit, which is the intended reading.

    ``load_baseline`` returns an empty mapping now, so the audit reports standing
    debt rather than a regression signal. The classifier is unchanged and still
    has to be right about which bucket that is.
    """
    verdict = _classify_cc([_cc()], {})
    assert len(verdict.new) == 1
    assert "[NEW]" in verdict.new[0]
    assert verdict.regressed == [] and verdict.allowed == []
    assert verdict.failing == verdict.new


def test_a_cyclomatic_score_above_its_ceiling_is_a_regression() -> None:
    """Higher is worse, so exceeding the baselined value fails."""
    verdict = _classify_cc([_cc(score=25)], {_cc_key(_cc()): 21})
    assert len(verdict.regressed) == 1
    assert "[REGRESSED from 21]" in verdict.regressed[0]
    assert verdict.new == []


def test_a_cyclomatic_score_at_or_below_its_ceiling_is_allowed() -> None:
    """The boundary is inclusive: equal to the baseline is not a regression."""
    key = _cc_key(_cc())
    assert _classify_cc([_cc(score=21)], {key: 21}).allowed
    assert _classify_cc([_cc(score=20)], {key: 21}).allowed
    assert _classify_cc([_cc(score=21)], {key: 21}).failing == []


def test_maintainability_compares_the_other_way_round() -> None:
    """A floor, not a ceiling: a LOWER index is worse.

    This is the one asymmetry in the three, and a classifier that copied its
    siblings would call every real maintainability regression allowed while
    failing the files that improved.
    """
    baseline = {"src/cadrumo/a.py": 18.5}
    assert _classify_mi([_mi(score=12.0)], baseline).regressed
    assert _classify_mi([_mi(score=25.0)], baseline).allowed
    assert _classify_mi([_mi(score=18.5)], baseline).allowed


def test_a_baseline_entry_with_no_current_hit_is_resolved() -> None:
    """Debt that was paid down is reported, and does not fail the run."""
    verdict = _classify_cog([], {"src/cadrumo/a.py::gone": 30})
    assert verdict.resolved == ["src/cadrumo/a.py::gone"]
    assert verdict.failing == []


def test_the_cognitive_classifier_uses_its_own_key_shape() -> None:
    """``path::name`` for both scored kinds, and the key is what the baseline holds.

    A key mismatch does not raise; it silently reclassifies every hit as new,
    which with a populated baseline would fail a clean tree.
    """
    hit = _cog()
    assert _cog_key(hit) == "src/cadrumo/a.py::widen"
    assert _classify_cog([hit], {_cog_key(hit): 30}).allowed
    assert _classify_cog([hit], {"src/cadrumo/a.py": 30}).new


def test_hits_are_ordered_worst_first_within_each_bucket() -> None:
    """The report is read from the top, so the ordering is part of the output."""
    verdict = _classify_cc([_cc(name="mild", score=21), _cc(name="severe", score=40)], {})
    assert "severe" in verdict.new[0]
    assert "mild" in verdict.new[1]

    worst_first = _classify_mi([_mi(path="better.py", score=19.0), _mi(path="worse.py", score=3.0)], {})
    assert "worse.py" in worst_first.new[0]


def test_a_built_baseline_round_trips_through_its_own_classifiers() -> None:
    """Every hit is allowed against a baseline built from exactly those hits.

    The property that made the retired ratchet meaningful, asserted here because
    ``build_baseline`` survived the retirement and a future caller may rely on
    it: capturing the current tree must produce a baseline the current tree
    passes, or the capture is not a capture.
    """
    cc, mi, cog = [_cc()], [_mi()], [_cog()]
    baseline = build_baseline(cc, mi, cog)

    assert _classify_cc(cc, baseline.cyclomatic).failing == []
    assert _classify_mi(mi, baseline.maintainability).failing == []
    assert _classify_cog(cog, baseline.cognitive).failing == []


def test_the_retired_baseline_loads_empty_for_both_scopes() -> None:
    """The audit grandfathers nothing, and says so identically for either scope.

    Pinned because the module docstring described the opposite for weeks after
    the code stopped doing it, and a reader who trusted the prose would expect a
    populated mapping here.
    """
    for is_test_run in (False, True):
        baseline = load_baseline(is_test_run)
        assert (baseline.cyclomatic, baseline.maintainability, baseline.cognitive) == ({}, {}, {})


def test_a_root_holding_no_python_files_refuses_instead_of_reporting_clean(tmp_path: Path) -> None:
    """A scan of nothing is not a clean scan.

    ``scan_directory`` returns empty for a root that does not exist, so a moved or
    misspelled product tree produced no files, no hits, and a result the report could
    not tell apart from a genuinely clean one -- measured at 101 hits for
    ``src/cadrumo`` against 0 for a name one character different. The hit count itself
    must stay free to reach zero, which is why the refusal is on the source.
    """
    with pytest.raises(FileNotFoundError):
        collect_cog(tmp_path / "absent", is_test_run=False, threshold=20)

    populated = tmp_path / "tree"
    populated.mkdir()
    (populated / "module.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    assert collect_cog(populated, is_test_run=False, threshold=20) == []


def test_a_missing_product_tree_refuses_instead_of_scanning_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """radon cannot tell an absent tree from a clean one, so the guard must.

    Pointed at a path that does not exist, radon prints nothing and exits 0 --
    measured at zero bytes on both streams, against 240693 bytes for the real
    tree. The return code carries no signal at all, so inspecting it would not
    separate the two; only the source can be checked. The scan root is a module
    constant both collectors read, so redirecting it here supplies INPUT rather
    than substituting behaviour: the refusal being exercised is the real one.
    """
    monkeypatch.setattr(complexity, "_TARGET", str(tmp_path / "absent"))

    with pytest.raises(FileNotFoundError):
        collect_cc("")
