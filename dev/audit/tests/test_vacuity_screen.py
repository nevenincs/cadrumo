"""Prove the vacuity screen reports the shape it claims and not its opposite.

The screen had no test. It shipped as a worklist generator whose output was read
and acted on, while nothing established that it distinguished an unguarded
corpus scan from a paired detector control -- which is the same class of
unproven instrument the screen itself exists to hunt.

Every case here drives the real :func:`screen` over a synthetic tree written to
a temporary root, so the assertions are about behaviour rather than about the
shape of the source. An injectable root is used deliberately in preference to
patching module state: the production entry point already takes a root, so the
test exercises the real call path rather than a rearranged one.

The regression pinned by ``test_a_literal_input_control_does_not_exempt_its
_module`` is not hypothetical. Teaching :func:`proves_it_scanned` to accept
equality against a non-empty literal removed 14 false positives and, in the same
change, silenced a genuine finding: that predicate governs the MODULE-level
exemption, so a control running on a planted dictionary began vouching for
sibling gates that walk four shipped catalogues. Proving a detector works says
nothing about whether the corpus it is pointed at exists. The two signals are
now separate functions, and this case is what keeps them separate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from ..vacuity_screen import screen

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_screened_tree(root: Path, module_name: str, source: str) -> None:
    """Materialise a synthetic screened tree containing one test module.

    Both screened trees are created because the screen refuses a missing one,
    which is itself a property worth not tripping over accidentally here.

    The tree is also made a git repository and the module staged, because the
    screen derives its denominator from ``git ls-files`` and RAISES when git is
    absent - deliberately, since an untracked tree would silently inflate the
    denominator and report a healthier ratio over files no reviewer can act on.
    Every case here drove the screen over a bare temporary directory and every
    one failed with exit 128 from git; sixteen tests were asserting nothing.

    The repository is created inside the pytest temporary root and never
    touches the one this file lives in.
    """
    package = root / "src" / "cadrumo" / "tests"
    package.mkdir(parents=True, exist_ok=True)
    (root / "dev").mkdir(parents=True, exist_ok=True)
    (package / module_name).write_text(dedent(source), encoding="utf-8")
    _track_in_a_scratch_repository(root)


def _track_in_a_scratch_repository(root: Path) -> None:
    """Initialise a repository at ``root`` if needed and stage what is there.

    Staging is enough: ``git ls-files`` reports the index, so no commit and no
    identity configuration are required.
    """
    if not (root / ".git").is_dir():
        subprocess.run(("git", "init", "-q"), cwd=root, check=True, capture_output=True)  # noqa: S603, S607
    subprocess.run(("git", "add", "-A"), cwd=root, check=True, capture_output=True)  # noqa: S603, S607


def _flagged_names(root: Path) -> set[str]:
    scanned, flagged = screen(root)
    assert scanned > 0, "the screen walked no modules, so its verdict would be meaningless"
    return {name for _, name, _ in flagged}


def test_an_unguarded_corpus_scan_is_flagged(tmp_path: Path) -> None:
    """The defect shape must be reported: empty assertion, nothing proving a walk."""
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_no_offenders_anywhere() -> None:
            failures = [path for path in walk_the_tree() if is_bad(path)]
            assert failures == []
        """,
    )

    assert "test_no_offenders_anywhere" in _flagged_names(tmp_path)


def test_a_paired_detector_control_is_not_flagged(tmp_path: Path) -> None:
    """The quiet half of a control is not an unguarded scan.

    Its empty assertion is the point of the test, and the non-empty assertion
    beside it proves the detector ran.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_detector_discriminates() -> None:
            assert offenders({"a.b": "bad"}) == ["a.b"]
            assert offenders({"c.d": "fine"}) == []
        """,
    )

    assert _flagged_names(tmp_path) == set()


def test_a_module_level_corpus_proof_exempts_its_siblings(tmp_path: Path) -> None:
    """A lower bound on the shared substrate vouches for the whole module.

    This is the off-module guard the screen's docstring sanctions: emptiness of
    the substrate would fail loudly in the sibling assertion.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_corpus_is_present() -> None:
            assert len(CATALOGUE) >= 100

        def test_no_offenders_anywhere() -> None:
            assert [key for key in CATALOGUE if is_bad(key)] == []
        """,
    )

    assert _flagged_names(tmp_path) == set()


def test_a_literal_input_control_does_not_exempt_its_module(tmp_path: Path) -> None:
    """A control on planted input must not vouch for a real corpus scan.

    The regression this pins: folding the literal-input signal into the
    module-level predicate silences every genuine finding in any file that also
    contains a detector control, which is most gate modules in the tree. The
    control itself stays unflagged; its sibling corpus scan must not.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_detector_discriminates() -> None:
            assert offenders({"a.b": "bad"}) == ["a.b"]
            assert offenders({"c.d": "fine"}) == []

        def test_no_offenders_in_the_shipped_catalogue() -> None:
            assert [key for key in load_catalogue() if is_bad(key)] == []
        """,
    )

    flagged = _flagged_names(tmp_path)
    assert "test_no_offenders_in_the_shipped_catalogue" in flagged, (
        "a corpus scan was exempted by a sibling control that only ever ran on planted input"
    )
    assert "test_detector_discriminates" not in flagged, "the control itself is not vacuity and must stay unflagged"


@pytest.mark.parametrize("empty", ["set()", "frozenset()", "list()", "dict()", "tuple()"])
def test_a_constructed_empty_counts_as_emptiness(tmp_path: Path, empty: str) -> None:
    """A constructed empty is the same claim as a literal one.

    An empty set has no literal spelling in Python, so a reader matching only
    literals is structurally blind to it rather than merely incomplete. This
    blind spot was found by the screen failing to flag a test in this very
    module that used ``== set()``; without these cases the branch closing it
    would ship unexercised, since no module in the tree currently writes an
    unguarded scan that way.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        f"""
        def test_no_offenders_anywhere() -> None:
            assert collect_offenders() == {empty}
        """,
    )

    assert "test_no_offenders_anywhere" in _flagged_names(tmp_path)


def test_a_populated_constructor_call_is_not_emptiness(tmp_path: Path) -> None:
    """``set(["a"])`` asserts a non-empty result and must not read as emptiness.

    The negative control for the case above: matching a bare constructor NAME
    rather than an argument-free CALL would swallow every populated one too, and
    the screen would flag tests that prove exactly what it wants proven.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_offenders_are_found() -> None:
            assert collect_offenders() == set(["a"])
        """,
    )

    assert _flagged_names(tmp_path) == set()


def test_a_zero_count_assertion_counts_as_emptiness(tmp_path: Path) -> None:
    """``== 0`` is the same defect wearing a different spelling."""
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_count_is_zero() -> None:
            assert len(collect_offenders()) == 0
        """,
    )

    assert "test_count_is_zero" in _flagged_names(tmp_path)


def test_a_missing_screened_tree_refuses_rather_than_reporting_clean(tmp_path: Path) -> None:
    """A screen that walked nothing must never look like a clean tree.

    Without this the instrument's own worst failure mode -- reporting zero
    findings because it scanned zero files -- is indistinguishable from success.
    """
    (tmp_path / "src" / "cadrumo" / "tests").mkdir(parents=True)

    with pytest.raises(SystemExit, match="screened tree is missing"):
        screen(tmp_path)


def test_a_proof_about_another_corpus_does_not_exempt_a_scan(tmp_path: Path) -> None:
    """Module-level credit is same-corpus, not module-wide.

    The sibling above vouches for ``CATALOGUE`` and is credited to a scan over
    ``CATALOGUE``. It must NOT be credited to a scan over ``PAGES``, which
    nothing has established is non-empty: that scan reports exactly what a
    clean corpus reports and exactly what an empty one reports.

    Crediting module-wide was the original shape and it laundered 110 functions
    tree-wide -- more than five times the worklist it was hiding them behind.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_catalogue_is_present() -> None:
            assert len(CATALOGUE) >= 100

        def test_no_offenders_in_pages() -> None:
            assert [page for page in PAGES if is_bad(page)] == []
        """,
    )

    assert _flagged_names(tmp_path) == {"test_no_offenders_in_pages"}


def test_an_attribute_corpus_guard_clears_the_hit(tmp_path: Path) -> None:
    """A corpus reached as an attribute proves the scan as well as a bare name.

    ``assert Model.model_fields`` is the same claim as ``assert rows``. Reading
    only names and calls made the screen re-flag a gate immediately after it was
    correctly guarded, which trains its reader that guarding does not clear the
    hit -- the fastest way to make a screen ignored.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def test_every_field_is_described() -> None:
            assert Settings.model_fields
            assert [n for n, f in Settings.model_fields.items() if not f.description] == []
        """,
    )

    assert _flagged_names(tmp_path) == set()


def test_a_guard_inside_a_called_helper_clears_the_hit(tmp_path: Path) -> None:
    """A proof placed at the corpus source counts for the gates that call it.

    Guarding the helper is the better shape when several gates share one corpus:
    a consumer added later inherits the proof instead of forgetting it. Reading
    only the test body would re-flag a gate that had just been correctly
    guarded, which teaches its reader that guarding does not clear the hit.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def _pages():
            found = discover()
            assert found
            return found

        def test_no_offenders() -> None:
            assert [p for p in _pages() if is_bad(p)] == []
        """,
    )

    assert _flagged_names(tmp_path) == set()


def test_a_guard_in_an_uncalled_helper_does_not_clear_the_hit(tmp_path: Path) -> None:
    """Helper credit is for helpers the test actually calls, not any helper.

    Without this the credit degenerates back toward module-wide: an unrelated
    helper carrying a proof would vouch for every scan in the file.
    """
    _write_screened_tree(
        tmp_path,
        "test_probe.py",
        """
        def _unrelated():
            found = discover()
            assert found
            return found

        def test_no_offenders() -> None:
            assert [p for p in walk_somewhere_else() if is_bad(p)] == []
        """,
    )

    assert _flagged_names(tmp_path) == {"test_no_offenders"}
