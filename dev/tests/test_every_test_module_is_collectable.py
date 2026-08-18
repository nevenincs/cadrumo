"""Bounded real-subprocess controls for the collectability detector.

The expensive full-corpus collection proof lives in
:mod:`cadrumo.tests.test_full_corpus_collectability_harness`, where the
dedicated outer-serial harness verdict runs it explicitly.  These controls
remain in the routine unit lane: they use small malformed source trees to
prove that the detector reports import failures, and they verify that source
discovery cannot collapse to an empty corpus.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Final

import pytest
from dev._paths import REPO_ROOT
from dev.ci.lane_reachability import tracked_test_files

from cadrumo.core import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final = REPO_ROOT

_UTF_8: Final = "utf-8"

#: The short-summary form pytest uses for a module it could not import.
_COLLECT_ERROR = re.compile(r"^ERROR (\S+)")

#: The tally line, e.g. ``1571/2035 tests collected`` or ``4 tests collected``.
_COLLECTED_TALLY = re.compile(r"(\d+)(?:/\d+)? tests? collected")

#: A floor, never an expected count. Its only job is to red when discovery
#: silently finds nothing or almost nothing, which would otherwise present as
#: a green gate over an empty corpus. The real corpus is an order of
#: magnitude above this, so ordinary churn cannot approach it.
_MINIMUM_PLAUSIBLE_MODULE_COUNT: Final = 500


def discover_test_roots() -> tuple[Path, ...]:
    """Return every top-level directory that carries a git-tracked test module.

    Discovered rather than listed, in both directions. A hardcoded set of
    INCLUDED roots would silently miss the next ``dev/<thing>/tests`` somebody
    adds; a hardcoded set of EXCLUDED directory names rots the same way, and
    did. Scratch trees are gitignored but were not on that name list, so a
    campaign that copied the whole repository under ``tmp/`` was walked as
    first-party corpus and reported roughly two thousand of its own modules as
    uncollectable -- a red verdict that said nothing about this repository's
    tests, and, in the other direction, a plausibility floor a scratch copy
    could satisfy on its own.

    The predicate is therefore what the repository itself declares, via the
    same ``git ls-files`` question :func:`~dev.ci.lane_reachability.tracked_test_files`
    already answers precisely: a top-level directory counts only when it holds
    at least one test module git actually tracks. Neither an inclusion nor an
    exclusion list can drift out of date, because there is no list.
    """
    top_level_names = {module.parts[0] for module in tracked_test_files(_REPO_ROOT) if module.parts}
    return tuple(sorted(_REPO_ROOT / name for name in top_level_names))


def discovered_test_modules(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return every git-tracked test module beneath ``roots``, repo-relative.

    Filtered from :func:`~dev.ci.lane_reachability.tracked_test_files` rather
    than walked with ``rglob``: a filesystem walk would offer an untracked
    scratch directory nested INSIDE a tracked root (a peer's uncommitted work
    under ``src/cadrumo/something-untracked/``, say) as first-party corpus,
    exactly the failure mode :func:`discover_test_roots` closes at the
    top level. Deriving the module list from git's own record closes it at
    every level, not only the top one.
    """
    root_names = {root.name for root in roots}
    return tuple(module for module in tracked_test_files(_REPO_ROOT) if module.parts and module.parts[0] in root_names)


def _nested_untracked_test_directories(targets: tuple[Path, ...]) -> tuple[str, ...]:
    """Return directories STRICTLY below ``targets`` that hold an untracked test module.

    ``discovered_test_modules`` answers the counting question entirely from
    git, so it cannot be fooled by a scratch directory nested inside a tracked
    root. But :func:`collection_report` hands pytest the ROOT DIRECTORY, and
    pytest walks whatever is on disk beneath it -- so an untracked directory
    nested inside a tracked root (``src/cadrumo/something-untracked/``, say)
    would still be walked into and collected. This computes ``--ignore``
    targets for exactly that gap.

    A target itself is never reported, even when the target sits under a
    gitignored path (a planted sample directory under ``var/`` always does):
    only genuine descendants below a target are in scope, so a caller's
    intended corpus can never exclude itself.
    """
    tracked = frozenset(tracked_test_files(_REPO_ROOT))
    directories: set[Path] = set()
    for target in targets:
        if not target.is_dir():
            continue
        for on_disk in scan_directory(target, pattern="test_*.py", recursive=True):
            if on_disk.parent == target:
                continue
            if on_disk.relative_to(_REPO_ROOT) not in tracked:
                directories.add(on_disk.parent)
    return tuple(str(directory) for directory in sorted(directories))


def collection_report(targets: tuple[Path, ...]) -> tuple[tuple[str, ...], int]:
    """Return the uncollectable modules under ``targets`` and how many collected.

    The count is returned because the error list alone cannot distinguish a
    clean corpus from a collection that never happened. A mistyped target
    yields a usage error rather than an ``ERROR`` line, so an errors-only
    reading of a run that collected nothing is indistinguishable from a run
    that collected everything cleanly — the gate would pass on having looked
    at nothing, which is the failure it exists to catch, one level up.

    Reports all failures, not the first. ``--collect-only`` lists every
    failing module in its short summary even though it also prints
    ``Interrupted``; ``--continue-on-collection-errors`` is passed so the
    intent is explicit rather than resting on that observed behaviour.

    ``-n0`` matters: this runs inside a pytest process that is itself under
    ``-n auto``, and inheriting that would fan out a second worker pool.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            "-q",
            "--no-header",
            "-n0",
            "--continue-on-collection-errors",
            *(f"--ignore={directory}" for directory in _nested_untracked_test_directories(targets)),
            *(str(target) for target in targets),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    found: list[str] = []
    collected = 0
    for line in result.stdout.splitlines():
        stripped = line.strip()
        match = _COLLECT_ERROR.match(stripped)
        if match is not None:
            found.append(match.group(1).replace("\\", "/"))
            continue
        tally = _COLLECTED_TALLY.search(stripped)
        if tally is not None:
            collected = int(tally.group(1))
    return tuple(sorted(set(found))), collected


def uncollectable_modules(targets: tuple[Path, ...]) -> tuple[str, ...]:
    """Return every module under ``targets`` that pytest cannot import."""
    broken, _collected = collection_report(targets)
    return broken


def _plant(directory: Path, stem: str, body: str) -> Path:
    """Write a sample module and return its repo-relative path.

    Samples live under ``var/`` INSIDE the repo rather than in ``tmp_path``:
    collection resolves modules against the rootdir, and a file outside it
    imports under different rules, so an out-of-tree sample would not
    exercise the behaviour being proved.
    """
    module = directory / f"{stem}.py"
    module.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return module.relative_to(_REPO_ROOT)


def test_discovery_finds_the_real_corpus() -> None:
    """Anti-vacuity: a discovery bug that finds nothing must red, not pass.

    Without this, a mistake in :func:`discover_test_roots` would hand the
    collector an empty target list, which reports no errors and presents as a
    clean gate over nothing at all. The self-reference is the part that cannot
    rot: this module is a test module, so any discovery that cannot see it is
    broken by construction, regardless of how the corpus is laid out.
    """
    roots = discover_test_roots()
    modules = discovered_test_modules(roots)
    this_module = Path(__file__).resolve().relative_to(_REPO_ROOT)

    assert roots, "discovered no test roots at all"
    assert this_module in modules, f"discovery cannot see its own module {this_module}"
    assert len(modules) >= _MINIMUM_PLAUSIBLE_MODULE_COUNT, (
        f"discovery found only {len(modules)} test modules, below the plausibility floor "
        f"of {_MINIMUM_PLAUSIBLE_MODULE_COUNT} — discovery is probably broken rather than the corpus shrunk"
    )


def test_discovery_excludes_a_real_gitignored_scratch_tree() -> None:
    """A gitignored top-level tree carrying test modules is not first-party corpus.

    Planted for real rather than simulated: the tree is created under a
    genuinely gitignored path, carries a genuinely broken test module, and the
    assertion is that discovery does not offer it to the collector. Without
    this, the boundary would be a claim in a docstring -- and the name list it
    replaced failed in exactly this way, silently, for as long as a scratch
    copy sat in the tree.
    """
    scratch_root = _REPO_ROOT / "tmp" / f"corpus-boundary-sample-{uuid.uuid4().hex[:8]}"
    scratch_root.mkdir(parents=True)
    try:
        git = shutil.which("git")
        assert git is not None, "the control requires git to confirm the planted tree is genuinely ignored"
        ignore_check = subprocess.run(
            [git, "check-ignore", str(scratch_root)],
            cwd=_REPO_ROOT,
            capture_output=True,
            check=False,
        )
        # `git check-ignore` exits 0 when the path IS ignored -- the control is
        # void unless the planted tree is genuinely gitignored, not merely new.
        assert ignore_check.returncode == 0, "the control is void unless the planted tree is genuinely gitignored"
        planted = _plant(
            scratch_root,
            "test_scratch_copy_is_not_corpus",
            """
            from cadrumo.a_module_that_does_not_exist import missing

            def test_never_reached() -> None:
                assert missing
            """,
        )

        roots = discover_test_roots()
        modules = discovered_test_modules(roots)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    assert scratch_root.name not in {root.name for root in roots}
    assert planted not in modules, "discovery offered a gitignored scratch tree to the collector as first-party corpus"
    assert not [module for module in modules if module.parts and module.parts[0] == "tmp"], (
        "discovery offered a gitignored scratch tree to the collector as first-party corpus"
    )
    assert roots, "the exclusion must not have emptied discovery"


def test_detector_reports_a_module_it_cannot_import() -> None:
    """Mutation proof: a planted uncollectable module is reported.

    The gate above is only meaningful if a green result can be distinguished
    from a detector that reports nothing whatever it is given.
    """
    sample_dir = _REPO_ROOT / "var" / f"collectable-gate-sample-{uuid.uuid4().hex[:8]}"
    sample_dir.mkdir(parents=True)
    try:
        healthy = _plant(
            sample_dir,
            "test_collectable_sample",
            """
            import pytest

            pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


            def test_imports_cleanly() -> None:
                assert True
            """,
        )
        broken = _plant(
            sample_dir,
            "test_uncollectable_sample",
            """
            import pytest

            from cadrumo.a_module_that_does_not_exist import missing

            pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


            def test_never_reached() -> None:
                assert missing
            """,
        )
        reported = uncollectable_modules((sample_dir,))
    finally:
        shutil.rmtree(sample_dir, ignore_errors=True)

    assert broken.as_posix() in reported, f"planted uncollectable module went unreported: {reported}"
    assert healthy.as_posix() not in reported, "a module that imports cleanly was reported as uncollectable"


def test_detector_reports_every_broken_module_not_only_the_first() -> None:
    """Two planted failures are both reported in one pass.

    Reporting only the first would make a sweep iterative: fix, re-run,
    discover the next. It would also under-report the blast radius of the
    rename class this gate exists to catch, which typically breaks several
    modules at once.
    """
    sample_dir = _REPO_ROOT / "var" / f"collectable-gate-multi-{uuid.uuid4().hex[:8]}"
    sample_dir.mkdir(parents=True)
    try:
        planted = [
            _plant(
                sample_dir,
                f"test_uncollectable_{index}",
                f"""
                import pytest

                from cadrumo.missing_module_{index} import absent

                pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


                def test_never_reached_{index}() -> None:
                    assert absent
                """,
            )
            for index in range(2)
        ]
        reported = uncollectable_modules((sample_dir,))
    finally:
        shutil.rmtree(sample_dir, ignore_errors=True)

    missing = [module.as_posix() for module in planted if module.as_posix() not in reported]
    assert not missing, f"detector reported only some broken modules; missed {missing}"
