"""Reclaim gate: abandoned ``var/`` build scratch goes, live gate input stays.

``var/`` interleaves the two. The readiness gate reads its cohort, smoke and
evidence trees out of the same directory a killed release build leaves a
multi-hundred-megabyte clone in, so a sweep that is merely *effective* is a
sweep that eventually deletes the input to a release. Every test here is a pair
of that shape: the abandoned thing goes, and the thing beside it does not.

Everything runs against a temporary ``var/`` built in ``tmp_path``. Nothing here
reads, writes, or lists the contributor's real ``var/``.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT, UTF_8
from ..build_scratch_reclaim import (
    RELEASE_COHORT_INTEGRATION_PREFIX,
    RELEASE_COHORT_INTEGRATION_SUFFIX,
    RELEASE_STAGING_PREFIX,
    RELEASE_STAGING_SUFFIX,
    integration_snapshot_name,
    matching_family,
    remove_tree,
    sweep_var_scratch,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DAY: Final[float] = 24 * 60 * 60

#: ``repo_root / "var" / "release-cohort"`` and ``Path("var/release-cohort")``:
#: the two spellings the development tree uses to name a real ``var/`` member.
_VAR_MEMBER_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r'"var"\s*/\s*"([A-Za-z0-9._-]+)"'),
    re.compile(r"var/([A-Za-z0-9._-]+)"),
)

#: This test and the module it exercises name the scratch families on purpose.
_DISCOVERY_EXCLUSIONS: Final[frozenset[str]] = frozenset(
    {"build_scratch_reclaim.py", "test_build_scratch_reclaim.py"},
)


def _aged(directory: Path, seconds: float) -> Path:
    """Backdate ``directory``'s modification time by ``seconds``."""
    stamp = time.time() - seconds
    os.utime(directory, (stamp, stamp))
    return directory


def _scratch_tree(var: Path, name: str, *, read_only: bool = False) -> Path:
    """Create one populated scratch directory under ``var``.

    ``read_only`` reproduces the attribute a Git clone's object files carry,
    which is the shape that makes this reclaim non-trivial on Windows: the
    unlink fails with ``[WinError 5] Access is denied``, and the obvious
    ``shutil.rmtree(..., ignore_errors=True)`` swallows that failure and reports
    a removal it did not perform.
    """
    directory = var / name
    (directory / "nested").mkdir(parents=True)
    payload = directory / "nested" / "object"
    payload.write_bytes(b"scratch")
    if read_only:
        os.chmod(payload, stat.S_IREAD)
    return directory


def _abandoned_snapshot_name() -> str:
    """Return a snapshot name owned by a process that really ran and really ended.

    A real child rather than an invented number: the liveness answer then comes
    from the operating system about a process it genuinely knew, which is the
    only way this exercises the probe rather than a guess about it.
    """
    finished = subprocess.Popen([sys.executable, "-c", "pass"])
    finished.wait()
    return f"{RELEASE_COHORT_INTEGRATION_PREFIX}{finished.pid}-abc{RELEASE_COHORT_INTEGRATION_SUFFIX}"


def _var(tmp_path: Path) -> Path:
    var = tmp_path / "var"
    var.mkdir()
    return var


def _live_var_members() -> frozenset[str]:
    """Return every ``var/`` member the development tree names as a real path.

    Discovered from the tree rather than restated here. A list written down in
    this file would be a second spelling of the readiness gate's inputs, free to
    fall behind the moment a lane adds one -- and falling behind is exactly the
    failure that ends in a sweep deleting a release's evidence.
    """
    members: set[str] = set()
    for source in REPO_ROOT.joinpath("dev").rglob("*.py"):
        if source.name in _DISCOVERY_EXCLUSIONS:
            continue
        text = source.read_text(encoding=UTF_8, errors="ignore")
        for pattern in _VAR_MEMBER_PATTERNS:
            members.update(pattern.findall(text))
    return frozenset(members)


def test_discovered_live_var_members_cover_the_readiness_gate_inputs() -> None:
    """The discovery finds the directories the release gates actually read.

    Asserted before the discovery is used as evidence anywhere else: a regex
    that silently matched nothing would make the sparing test below pass
    against an empty set, which is the classic shape of a gate that cannot
    fail.
    """
    discovered = _live_var_members()
    assert {
        "release-cohort",
        "packaging-smoke",
        "packaging-smoke-evidence",
        "distribution-install-readiness",
        "packaging-smoke-cohort",
    } <= discovered
    assert len(discovered) >= 10


def test_no_live_var_member_falls_inside_a_scratch_family() -> None:
    """No directory the development tree reads out of ``var/`` is sweepable.

    The real safety property, and the one that has to hold as the tree changes:
    a lane adding ``var/<something>`` whose name happens to sit inside a scratch
    family fails here rather than in a release.
    """
    claimed = {name: matching_family(name) for name in _live_var_members()}
    assert {name: family for name, family in claimed.items() if family is not None} == {}


def test_sweep_spares_every_live_var_member_however_old(tmp_path: Path) -> None:
    """A year-old readiness input is not scratch and is never reclaimed."""
    var = _var(tmp_path)
    live = sorted(_live_var_members())
    for name in live:
        _aged(_scratch_tree(var, name), 365 * _DAY)

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (0, 0)
    assert sorted(path.name for path in var.iterdir()) == live


def test_sweep_reclaims_an_abandoned_snapshot_holding_read_only_bytes(tmp_path: Path) -> None:
    """An abandoned clone goes, read-only object files and all.

    The read-only payload is the defect this reclaim exists to survive rather
    than decoration: it is what a Git clone stores, it is what the abandoned
    snapshots on the development box hold, and it is what makes the difference
    between a sweep that reports a reclaim and one that performs it. A
    ``shutil.rmtree(..., ignore_errors=True)`` in this position leaves the tree
    on disk on Windows and reports success.
    """
    var = _var(tmp_path)
    stale = _aged(_scratch_tree(var, _abandoned_snapshot_name(), read_only=True), 20 * 60)

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (1, 0)
    assert not stale.exists()
    assert list(var.iterdir()) == []


def test_naive_ignore_errors_removal_is_not_what_the_sweep_does(tmp_path: Path) -> None:
    """``remove_tree`` clears the attribute that blocks a plain removal.

    Stated as a property of the removal rather than of one platform's refusal:
    whatever the operating system's policy on unlinking a read-only file,
    afterwards the tree is gone and the function said so.
    """
    var = _var(tmp_path)
    tree = _scratch_tree(var, integration_snapshot_name("a" * 32), read_only=True)

    assert remove_tree(tree) is True
    assert not tree.exists()


def test_sweep_spares_a_scratch_directory_a_concurrent_build_is_writing(tmp_path: Path) -> None:
    """Freshly written scratch belongs to a running build and is left alone."""
    var = _var(tmp_path)
    running = _scratch_tree(var, f"{RELEASE_STAGING_PREFIX}release-cohort-9f{RELEASE_STAGING_SUFFIX}")

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (0, 1)
    assert running.is_dir()


def test_sweep_reclaims_an_owned_snapshot_once_its_owner_has_exited(tmp_path: Path) -> None:
    """A named owner that no longer runs reclaims in minutes, not a day.

    The owner is a real process this test starts and waits for, so the liveness
    answer comes from the operating system about a process that genuinely
    existed and genuinely ended.
    """
    var = _var(tmp_path)
    abandoned = _aged(_scratch_tree(var, _abandoned_snapshot_name()), 20 * 60)

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (1, 0)
    assert not abandoned.exists()


def test_sweep_spares_a_snapshot_whose_named_owner_is_still_running(tmp_path: Path) -> None:
    """This process is alive, so the snapshot naming it survives the same age."""
    var = _var(tmp_path)
    mine = _aged(_scratch_tree(var, integration_snapshot_name("b" * 32)), 20 * 60)

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (0, 1)
    assert mine.is_dir()


def test_an_ownerless_snapshot_is_never_reclaimed_on_the_sweep_own_initiative(tmp_path: Path) -> None:
    """No owner to ask means no automatic removal, however old the directory is.

    This is the shape of every snapshot minted before the family carried a
    process identifier -- including the ones already on the development box --
    and the shape the automatic callers must not act on: nothing observes
    whether it is abandoned, so only an operator decides.
    """
    var = _var(tmp_path)
    name = f"{RELEASE_COHORT_INTEGRATION_PREFIX}0979c0c733fe{RELEASE_COHORT_INTEGRATION_SUFFIX}"
    ownerless = _aged(_scratch_tree(var, name), 30 * _DAY)

    assert sweep_var_scratch(var, now=time.time()) == (0, 1)
    assert ownerless.is_dir()


def test_an_ownerless_snapshot_is_reclaimed_when_an_operator_asks_by_age(tmp_path: Path) -> None:
    """The day ceiling is available, and it is what ``--apply`` reaches."""
    var = _var(tmp_path)
    name = f"{RELEASE_COHORT_INTEGRATION_PREFIX}0979c0c733fe{RELEASE_COHORT_INTEGRATION_SUFFIX}"
    _aged(_scratch_tree(var, name), 20 * 60)

    assert sweep_var_scratch(var, now=time.time(), reclaim_by_age=True) == (0, 1)

    _aged(var / name, 2 * _DAY)

    assert sweep_var_scratch(var, now=time.time(), reclaim_by_age=True) == (1, 0)
    assert not (var / name).exists()


def test_a_live_owner_outranks_the_day_ceiling_even_under_reclaim_by_age(tmp_path: Path) -> None:
    """An owner that is running is spared however the caller set the ceiling.

    The ceiling is the weaker, inferred ground; it must not overrule a direct
    liveness answer, or a long-running build's own scratch is deleted beneath
    it by the next sweep to come along.
    """
    var = _var(tmp_path)
    mine = _aged(_scratch_tree(var, integration_snapshot_name("d" * 32)), 30 * _DAY)

    assert sweep_var_scratch(var, now=time.time(), reclaim_by_age=True) == (0, 1)
    assert mine.is_dir()


def test_sweep_honours_an_explicit_exclusion(tmp_path: Path) -> None:
    """A caller's own scratch is spared regardless of every other rule."""
    var = _var(tmp_path)
    own = _aged(_scratch_tree(var, _abandoned_snapshot_name()), 30 * _DAY)

    assert sweep_var_scratch(var, now=time.time(), exclude=own, reclaim_by_age=True) == (0, 1)
    assert own.is_dir()


@pytest.mark.parametrize(
    "name",
    [
        "release-cohort",
        "release-cohort-integration",
        "release-cohort-integration-abc",
        "release-python-9f",
        ".staging",
        "packaging-smoke-cohort",
        "binary-closure-real-cp313",
    ],
)
def test_names_outside_every_family_are_not_scratch(name: str) -> None:
    """Neither anchor alone admits a name; both must match, without overlapping."""
    assert matching_family(name) is None


@pytest.mark.parametrize(
    "name",
    [
        "release-cohort-integration-0979c0c733fe-source",
        "release-cohort-integration-4812-9f2a-source",
        ".release-cohort-9f2a.staging",
        ".packaging-smoke-cohort-1.staging",
    ],
)
def test_registered_scratch_names_are_recognised(name: str) -> None:
    """Every shape the mint sites actually write is inside a family."""
    assert matching_family(name) is not None


def test_sweep_leaves_a_missing_var_directory_alone(tmp_path: Path) -> None:
    """A repository with no ``var/`` yet is not an error at collection time."""
    assert sweep_var_scratch(tmp_path / "absent") == (0, 0)


def test_sweep_does_not_follow_a_link_named_like_scratch(tmp_path: Path) -> None:
    """A link is not the tree it names, and removing one must not remove that tree.

    Written with a directory junction where the platform requires elevation for
    a symbolic link, so the case is exercised rather than waved at.
    """
    var = _var(tmp_path)
    target = tmp_path / "protected"
    target.mkdir()
    (target / "keep").write_bytes(b"not scratch")
    link = var / integration_snapshot_name("c" * 32)
    try:
        if sys.platform == "win32":
            command_shell = shutil.which("cmd")
            assert command_shell is not None
            subprocess.run(  # noqa: S603 - resolved shell with a fixed, test-owned argv.
                [command_shell, "/c", "mklink", "/J", str(link), str(target)],
                check=True,
                capture_output=True,
            )
        else:
            link.symlink_to(target, target_is_directory=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.fail(f"the link case could not be constructed, so it was not exercised: {exc}")
    _aged(link, 30 * _DAY)

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (0, 0)
    assert (target / "keep").is_file()
    shutil.rmtree(link, ignore_errors=True)
