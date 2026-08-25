"""No developer-harness module may carry the capability to delete a GitHub release.

The evidence garbage-collector was removed rather than left dormant, and the
reason is specific: it could delete releases. A dormant destructive verb is not
harmless, because nothing about it announces itself — it sits importable and
callable behind an argument parser, and the next caller who reaches for it gets
the capability back without any decision having been taken. The retirement was
therefore a removal of the CAPABILITY, not a removal of a call site.

That distinction is what this gate enforces, and it is why it keys on the
property rather than on the module. A gate asserting "the file is absent" is
satisfied the moment someone re-lands the same call under a different name; a
gate asserting "nothing anywhere builds a release-deleting invocation" is not.
No path is named and no tally is pinned: both the corpus and the verdict are
derived at read time, so a new module joins the scan by existing.

Reading a release, downloading its assets and listing releases are all
untouched — the release flows genuinely need them. Only deletion is refused.
"""

from __future__ import annotations

import ast
from itertools import pairwise
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEV_ROOT = Path(__file__).resolve().parents[1]

#: Consecutive argv pairs that construct a release-destroying ``gh`` call.
_DESTRUCTIVE_ARGV_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {("release", "delete"), ("release", "delete-asset")},
)


def _string_runs(tree: ast.AST) -> list[list[str]]:
    """Return the ordered string constants of every list/tuple literal in the tree.

    Order is what carries the meaning: ``gh`` is addressed as an argv sequence,
    so the verb is the element following the noun. Collecting each literal as an
    ordered run lets the check ask about adjacency rather than mere membership —
    a module that mentions ``"release"`` somewhere and ``"delete"`` elsewhere is
    not building a deletion.
    """
    runs: list[list[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.List | ast.Tuple):
            continue
        runs.append([e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)])
    return runs


def release_deleting_calls_in(source: str, *, origin: str) -> list[str]:
    """Return a description of every release-deleting invocation built in ``source``.

    Takes source text rather than reading a path, so the detector can be driven
    with a constructed module and shown to report a genuine deletion. A checker
    that only ever runs over a healthy tree cannot demonstrate it is able to say
    no, and this one guards a capability whose whole point is that it is absent.
    """
    found: list[str] = []
    tree = ast.parse(source, filename=origin)
    for run in _string_runs(tree):
        for first, second in pairwise(run):
            if (first, second) in _DESTRUCTIVE_ARGV_PAIRS:
                found.append(f"{origin}: builds a `gh {first} {second}` invocation")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value.lower()
            if "release" in text and ("-x delete" in text or "--method delete" in text):
                found.append(f"{origin}: builds a DELETE request against a release endpoint")
    return found


def _harness_modules() -> list[Path]:
    """Return every developer-harness module the scan covers.

    This module is the one exclusion, and it is unavoidable: the pair table and
    the positive controls below must contain the exact shape being refused, so a
    scan including itself reports itself forever. The exemption is written
    against ``__file__`` rather than a path literal, so it cannot silently widen
    to cover a second file and cannot be inherited by a rename.
    """
    here = Path(__file__).resolve()
    return [
        p
        for p in scan_directory(_DEV_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        if p.resolve() != here
    ]


def test_the_scan_reads_a_real_non_empty_corpus_of_gh_call_sites() -> None:
    """Anti-vacuity: an empty corpus, or one with no gh argv shapes, would pass silently.

    The refusal below quantifies over the discovered modules, so a glob that
    stopped matching would make it hold over nothing. Requiring that the corpus
    still contains a real ``gh release`` argv shape is the stronger half: it
    proves the detector is looking at the kind of code it exists to judge, so a
    green verdict means "no deletion found among real release calls" rather than
    "no release calls found at all".
    """
    modules = _harness_modules()
    assert modules, f"no developer-harness modules found under {_DEV_ROOT}; every check below is vacuous"

    benign_release_argv = [
        path
        for path in modules
        if any(
            "release" in run and any(verb in run for verb in ("download", "view", "create"))
            for run in _string_runs(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        )
    ]
    assert benign_release_argv, (
        "the harness builds no `gh release <verb>` argv sequence at all, so this gate is judging a corpus "
        "that contains none of the shapes it detects"
    )


def test_no_harness_module_can_delete_a_release() -> None:
    """The capability is absent, not merely uncalled."""
    offenders: list[str] = []
    for path in _harness_modules():
        offenders += release_deleting_calls_in(
            path.read_text(encoding="utf-8"),
            origin=str(path.relative_to(_DEV_ROOT.parent)).replace("\\", "/"),
        )
    assert not offenders, (
        f"these developer-harness modules can delete a GitHub release: {offenders}. The evidence "
        "garbage-collector was removed rather than left dormant precisely because it carried this "
        "capability; a dormant destructive verb is the capability back, whatever its name. Reading, "
        "listing and downloading releases are untouched — only deletion is refused."
    )


def test_the_detector_reports_the_retired_garbage_collector_shape() -> None:
    """Positive control: the exact invocation that was retired must be caught.

    Built from the shape the removed collector actually used, so this control
    fails if the detector is narrowed to something that call would slip past.
    """
    source = (
        "def _gc(gh, tag, repository):\n"
        '    run_gh_with_retry(gh, ["release", "delete", tag, "--repo", repository, "--yes", "--cleanup-tag"])\n'
    )
    assert release_deleting_calls_in(source, origin="constructed") != []


def test_the_detector_reports_a_delete_request_against_a_release_endpoint() -> None:
    """The argv form is not the only way to reach the capability.

    A raw API call carries it just as well, so a detector keyed solely on the
    ``gh release delete`` argv pair would be defeated by rewriting the same
    deletion as a request. Controlled separately because it is a separate rule.
    """
    source = 'CALL = "api -X DELETE repos/owner/name/releases/1"\n'
    assert release_deleting_calls_in(source, origin="constructed") != []


@pytest.mark.parametrize(
    "source",
    [
        'ARGV = ["release", "download", tag, "--repo", repository]\n',
        'ARGV = ["release", "view", tag]\n',
        'WORDS = ["delete", "something", "unrelated"]\n',
        'PROSE = "the collector could delete a release, which is why it is gone"\n',
    ],
)
def test_the_detector_leaves_non_deleting_release_work_alone(source: str) -> None:
    """Downloading, viewing, and merely mentioning deletion are not the capability.

    Without this the refusal above is satisfied by a detector that flags every
    module touching releases, which would red the gate on the download path the
    release flows require and force it to be silenced. The prose case matters
    most: this gate's own rationale, and the record's, say the words next to each
    other, so a substring check over text would flag the documentation of the
    removal as the removal's reintroduction.
    """
    assert release_deleting_calls_in(source, origin="constructed") == []
