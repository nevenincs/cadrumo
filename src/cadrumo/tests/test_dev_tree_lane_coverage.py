"""Prove every test under ``dev/`` is reached by some lane.

``testpaths`` in ``pyproject.toml`` names only ``src/cadrumo`` plus a single
packaging file, and the CI dev step names only ``dev/ci``, ``dev/packaging``,
``dev/quality``, and ``dev/release``. Ten test directories under ``dev/`` were
therefore collected by NO lane and NO workflow. That is not a slow lane or a
narrow marker: those tests had never run in CI at all, and 19 of them were
failing unobserved -- the duplication-disposition gate, the Terminology
Handbook conformance gates, and the shipped documentation-search corpus gates
among them.

A directory nobody collects is worse than a missing test, because the file
exists, reads as coverage, and is counted as coverage by anyone auditing the
tree. This gate closes that path permanently: a new ``dev/**/tests`` directory
that no lane names fails HERE, immediately, instead of joining an invisible set.

Two construction details carry the gate's own honesty:

* The module lives under ``src/cadrumo/tests`` and is marked ``unit``
  DELIBERATELY. A guard against unreachable directories must itself sit inside
  the selection every lane already runs; placed in ``dev/tests`` -- which is one
  of the ten orphans -- it would have been unreachable by exactly the defect it
  exists to catch, and could never have fired.
* Both corpora are asserted non-empty and the path reader carries positive and
  negative controls. A reader that silently stopped matching would otherwise
  report an empty orphan set as full coverage, which is the precise false-green
  shape this gate exists to refuse.

The check is textual on the lane side by design. A behavioural
``--collect-only`` union would be stronger against a lane that NAMES a directory
while its marker expression deselects the whole thing, but that narrower defect
already has an owner in
:mod:`dev.packaging.tests.test_preflight_recipe_selection`, which boots real
pytest subprocesses for the mixed-marker directory where it bit. What had no
owner anywhere, and what this gate supplies, is the first-order question of
whether a directory is named at all.

KNOWN LIMIT, stated so it is not mistaken for a guarantee: a justfile recipe
satisfies this gate, and a justfile recipe is not CI. A directory reached only
by a recipe nobody invokes is still a directory whose result nobody sees --
the same defect one level up. Tightening the assertion to require a WORKFLOW
step is the stronger invariant and is deliberately not enforced yet, because
``just test-dev-tooling`` is currently red on failures inherited from the
unobserved period; enforcing CI coverage before those land would put a
knowingly-red lane in the shared pipeline. Tighten this once that lane is
green, and delete this paragraph when you do.

See Also:
    :mod:`dev.packaging.tests.test_preflight_recipe_selection`
        Sibling gate for the narrower marker-under-selection defect.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_DEV_ROOT: Final = _REPO_ROOT / "dev"
_JUSTFILE: Final = _REPO_ROOT / "justfile"
_WORKFLOWS: Final = _REPO_ROOT / ".github" / "workflows"
_PYPROJECT: Final = _REPO_ROOT / "pyproject.toml"

#: Directories known to hold tests reached by a lane. Asserted as a subset of
#: what discovery finds, so a discovery pass that stopped matching fails loudly
#: rather than reporting an empty corpus as a clean tree.
_ANCHOR_DIRECTORIES: Final = frozenset(
    {
        Path("dev/packaging/tests"),
        Path("dev/audit/tests"),
        Path("dev/docs/terminology/tests"),
    },
)

_DEV_PATH_TOKEN: Final = re.compile(r"dev/[A-Za-z0-9_./-]*")


def _tracked_dev_test_files() -> frozenset[Path]:
    """Every ``test_*.py`` under ``dev/``, repo-relative with forward slashes."""
    return frozenset(
        Path(path.relative_to(_REPO_ROOT).as_posix())
        for path in _DEV_ROOT.rglob("test_*.py")
        if path.is_file() and "__pycache__" not in path.parts
    )


def dev_paths_named_by(text: str) -> frozenset[Path]:
    """Read the ``dev/`` paths a lane definition names on its pytest lines.

    Only lines invoking pytest are read. A ``dev/`` token elsewhere in the file
    -- a ``python -m dev.packaging.source_preflight`` module path, a docs link --
    names no selection, and counting it would let an unrelated mention launder a
    directory into looking covered.

    ``/dev/null`` is excluded by the same rule that filters every other token:
    a token counts only when it resolves to a real path inside the repository.

    Args:
        text: The full text of a justfile or workflow file.

    Returns:
        Every repo-relative ``dev/`` path named on a pytest invocation line.
    """
    named: set[Path] = set()
    for line in text.splitlines():
        if "pytest" not in line:
            continue
        for token in _DEV_PATH_TOKEN.findall(line):
            candidate = Path(token)
            if (_REPO_ROOT / candidate).exists():
                named.add(candidate)
    return frozenset(named)


def _lane_named_paths() -> frozenset[Path]:
    """Every ``dev/`` path named by the justfile, a workflow, or ``testpaths``."""
    named: set[Path] = set(dev_paths_named_by(_JUSTFILE.read_text(encoding="utf-8")))
    for workflow in sorted(_WORKFLOWS.glob("*.yml")):
        named |= dev_paths_named_by(workflow.read_text(encoding="utf-8"))

    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    for entry in config["tool"]["pytest"]["ini_options"]["testpaths"]:
        candidate = Path(entry)
        if candidate.parts and candidate.parts[0] == "dev" and (_REPO_ROOT / candidate).exists():
            named.add(candidate)
    return frozenset(named)


def uncovered_files(test_files: frozenset[Path], named: frozenset[Path]) -> frozenset[Path]:
    """Return the test files no named path contains.

    A named path may be a directory or a single file; a file is covered when it
    equals a named path or lies beneath one.

    Args:
        test_files: Repo-relative test-file paths.
        named: Repo-relative paths some lane names.

    Returns:
        The subset of ``test_files`` that no entry of ``named`` covers.
    """
    return frozenset(path for path in test_files if not any(path == entry or entry in path.parents for entry in named))


def test_discovery_finds_both_corpora() -> None:
    """Neither side of the comparison may be silently empty.

    Without this the gate passes vacuously the moment either reader stops
    matching -- no test files discovered, or no lane paths parsed -- which is
    the exact failure mode the module docstring refuses.
    """
    test_files = _tracked_dev_test_files()
    named = _lane_named_paths()

    assert len(test_files) > 100, (
        f"dev/ test-file discovery returned {len(test_files)}; the reader has stopped matching"
    )
    assert named, "no dev/ path was parsed out of any lane; the lane reader has stopped matching"

    directories = {path.parent for path in test_files}
    missing_anchors = _ANCHOR_DIRECTORIES - directories
    assert not missing_anchors, (
        f"anchor directories absent from discovery: {sorted(str(path) for path in missing_anchors)}; "
        "either they moved (update the anchors) or discovery is broken"
    )


def test_every_dev_test_file_is_named_by_some_lane() -> None:
    """No test under ``dev/`` may sit outside every lane's selection.

    Fails with the orphaned directories named, so the remedy -- add them to a
    lane, or delete them -- is decidable from the message alone.
    """
    uncovered = uncovered_files(_tracked_dev_test_files(), _lane_named_paths())

    orphaned_directories = sorted({str(path.parent) for path in uncovered})
    assert not uncovered, (
        "test files under dev/ are collected by no lane and no CI workflow, so they have "
        "never run and their result has never been seen:\n\n  "
        + "\n  ".join(orphaned_directories)
        + f"\n\n({len(uncovered)} file(s).) Add them to a justfile recipe or a workflow step, "
        "or delete them. A test nobody runs reads as coverage and is not."
    )


def test_lane_reader_distinguishes_a_pytest_line_from_a_bare_mention() -> None:
    """Positive and negative controls over the lane reader.

    Anchored on real repository paths so the controls cannot pass against a
    reader that accepts anything: the positive case must be found, the three
    negative cases must not.
    """
    found = dev_paths_named_by(
        "recipe:\n"
        "    @uv run --no-sync pytest -q -m 'unit' dev/audit/tests\n"
        "    @uv run --no-sync python -m dev.packaging.source_preflight\n"
        "    @echo dev/quality/tests > /dev/null\n"
        "    @just something dev/release/tests\n",
    )

    assert Path("dev/audit/tests") in found, "the reader missed a path named on a real pytest line"
    assert Path("dev/quality/tests") not in found, "the reader counted a path from a non-pytest line"
    assert Path("dev/release/tests") not in found, "the reader counted a path from a non-pytest line"
    assert Path("dev/null") not in found, "the reader counted /dev/null as a repository path"


def test_uncovered_files_reports_exactly_the_orphans() -> None:
    """Anti-tautology proof over injected corpora, not the live tree.

    The live tree is expected to be covered, so the assertion above cannot by
    itself show the comparison can ever report anything. This drives the same
    function with a known-orphaned input and requires it to name exactly the
    orphan -- and, in the second case, nothing.
    """
    covered = Path("dev/covered/tests/test_a.py")
    orphan = Path("dev/orphan/tests/test_b.py")
    nested = Path("dev/covered/tests/deeper/test_c.py")
    named = frozenset({Path("dev/covered/tests")})

    assert uncovered_files(frozenset({covered, orphan, nested}), named) == frozenset({orphan})
    assert uncovered_files(frozenset({covered, nested}), named) == frozenset()
    assert uncovered_files(frozenset({orphan}), frozenset()) == frozenset({orphan})
