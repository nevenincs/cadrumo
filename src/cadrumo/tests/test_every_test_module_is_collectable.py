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

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]

#: Directories that carry no first-party test corpus. ``var`` is excluded
#: because this module plants deliberately-broken samples there; the others
#: are dependency, tooling, or build output.
_NON_CORPUS_DIRECTORIES: Final = frozenset(
    {".git", ".venv", ".vault", ".vaultspec", ".ruff_cache", ".pytest_cache", "node_modules", "var", "htmlcov"},
)

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
    """Return every top-level directory that carries a test module.

    Discovered rather than listed. A hardcoded set would silently exclude the
    next ``dev/<thing>/tests`` somebody adds, which is the same shape of
    invisibility this gate exists to close — a new corpus would sit outside
    the gate reporting nothing.
    """
    roots: list[Path] = []
    for entry in sorted(_REPO_ROOT.iterdir()):
        if not entry.is_dir() or entry.name in _NON_CORPUS_DIRECTORIES or entry.name.startswith("."):
            continue
        if next(entry.rglob("test_*.py"), None) is not None:
            roots.append(entry)
    return tuple(roots)


def discovered_test_modules(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return every ``test_*.py`` beneath ``roots``, repo-relative."""
    modules: list[Path] = []
    for root in roots:
        modules.extend(path.relative_to(_REPO_ROOT) for path in root.rglob("test_*.py"))
    return tuple(sorted(modules))


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
