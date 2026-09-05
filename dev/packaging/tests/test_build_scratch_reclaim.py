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
    COHORT_BUILD_TREE_FAMILY,
    COHORT_SOURCE_ARCHIVE_FAMILY,
    COMMAND_SPEC_BYTECODE_FAMILY,
    RELEASE_COHORT_INTEGRATION_FAMILY,
    RELEASE_STAGING_FAMILY,
    VAR_SCRATCH_FAMILIES,
    ScratchFamily,
    _owning_pid,
    matching_family,
    remove_scratch,
    remove_tree,
    sweep_var_scratch,
    var_scratch_name,
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


def _aged(entry: Path, seconds: float) -> Path:
    """Backdate ``entry``'s modification time by ``seconds``."""
    stamp = time.time() - seconds
    os.utime(entry, (stamp, stamp))
    return entry


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


def _scratch_file(var: Path, name: str) -> Path:
    """Create one scratch FILE under ``var``.

    The cohort build's Git archive is a file at a working name until the moment
    it is moved into the cohort, so a sweep that considered directories alone
    left several hundred megabytes of it behind after every kill.
    """
    path = var / name
    path.write_bytes(b"archive bytes")
    return path


def _foreign_owner_name(family: ScratchFamily, body: str) -> str:
    """Return a ``family`` name owned by a process that really ran and really ended.

    A real child rather than an invented number: the liveness answer then comes
    from the operating system about a process it genuinely knew, which is the
    only way this exercises the probe rather than a guess about it.
    """
    finished = subprocess.Popen([sys.executable, "-c", "pass"])
    # Bounded: an interpreter that does nothing exits at once, but a bare wait()
    # is unbounded, and a test blocked in wait() is the one shape the repository's
    # per-test ceiling cannot interrupt - the thread method cannot unwind it, so
    # the worker exits uncleanly and --max-worker-restart=0 stops the session
    # naming a test that was never the defect. TimeoutExpired here is loud and
    # attributable instead.
    finished.wait(timeout=60)
    return f"{family.prefix}{finished.pid}-{body}{family.suffix}"


def _abandoned_snapshot_name() -> str:
    """Return an integration snapshot name whose owner has exited."""
    return _foreign_owner_name(RELEASE_COHORT_INTEGRATION_FAMILY, "abc")


def _legacy_ownerless_name() -> str:
    """Return an integration snapshot name from before the mint carried an owner.

    A bare hex run id where the owner token would now be, which is the shape
    already sitting in the development box's ``var/`` and the shape the
    automatic callers must not act on.
    """
    family = RELEASE_COHORT_INTEGRATION_FAMILY
    return f"{family.prefix}0979c0c733fe{family.suffix}"


def _var(tmp_path: Path) -> Path:
    var = tmp_path / "var"
    var.mkdir()
    return var


def _var_naming_surfaces() -> list[Path]:
    """Return every tracked surface that can name a ``var/`` member.

    Not just Python. A lane's ``var/`` directory is as often named in the
    workflow that runs it or in the recipe that invokes it as in the module
    that reads it, and a discovery that saw only ``dev/**/*.py`` would judge
    the sweep safe against a fraction of its real inputs. The names those two
    surfaces contribute today fall inside no family, so this widening changes
    no verdict -- it removes the case where a lane adds one that does and
    nothing notices.
    """
    return [
        *(path for path in REPO_ROOT.joinpath("dev").rglob("*.py") if path.name not in _DISCOVERY_EXCLUSIONS),
        *sorted(REPO_ROOT.joinpath(".github", "workflows").glob("*.yml")),
        REPO_ROOT / "justfile",
    ]


def _live_var_members() -> frozenset[str]:
    """Return every ``var/`` member the development tree names as a real path.

    Discovered from the tree rather than restated here. A list written down in
    this file would be a second spelling of the readiness gate's inputs, free to
    fall behind the moment a lane adds one -- and falling behind is exactly the
    failure that ends in a sweep deleting a release's evidence.
    """
    members: set[str] = set()
    for source in _var_naming_surfaces():
        try:
            text = source.read_text(encoding=UTF_8, errors="ignore")
        except OSError:
            continue
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


def test_discovery_reaches_the_surfaces_outside_the_python_tree() -> None:
    """A ``var/`` name only a workflow or the justfile carries is still discovered.

    The teeth for the widening. Each name below appears in exactly one of the
    two non-Python surfaces and nowhere under ``dev/**/*.py``, so a discovery
    narrowed back to the Python tree fails here rather than silently judging
    the sweep against a fraction of its inputs.
    """
    python_only: set[str] = set()
    for source in REPO_ROOT.joinpath("dev").rglob("*.py"):
        if source.name in _DISCOVERY_EXCLUSIONS:
            continue
        text = source.read_text(encoding=UTF_8, errors="ignore")
        for pattern in _VAR_MEMBER_PATTERNS:
            python_only.update(pattern.findall(text))

    beyond_python = _live_var_members() - python_only

    assert {"distributions", "oracle-emit-work", "release"} <= beyond_python


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
    tree = _scratch_tree(var, var_scratch_name(RELEASE_COHORT_INTEGRATION_FAMILY, "a" * 32), read_only=True)

    assert remove_tree(tree) is True
    assert not tree.exists()


def test_sweep_spares_a_scratch_directory_a_concurrent_build_is_writing(tmp_path: Path) -> None:
    """Freshly written scratch belongs to a running build and is left alone."""
    var = _var(tmp_path)
    running = _scratch_tree(var, var_scratch_name(RELEASE_STAGING_FAMILY, "release-cohort-9f"))

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
    mine = _aged(_scratch_tree(var, var_scratch_name(RELEASE_COHORT_INTEGRATION_FAMILY, "b" * 32)), 20 * 60)

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
    name = _legacy_ownerless_name()
    ownerless = _aged(_scratch_tree(var, name), 30 * _DAY)

    assert sweep_var_scratch(var, now=time.time()) == (0, 1)
    assert ownerless.is_dir()


def test_an_ownerless_snapshot_is_reclaimed_when_an_operator_asks_by_age(tmp_path: Path) -> None:
    """The day ceiling is available, and it is what ``--apply`` reaches."""
    var = _var(tmp_path)
    name = _legacy_ownerless_name()
    _aged(_scratch_tree(var, name), 20 * 60)

    assert sweep_var_scratch(var, now=time.time(), reclaim_by_age=True) == (0, 1)

    _aged(var / name, 2 * _DAY)

    assert sweep_var_scratch(var, now=time.time(), reclaim_by_age=True) == (1, 0)
    assert not (var / name).exists()


def test_a_live_owner_is_spared_by_the_automatic_sweep_however_old(tmp_path: Path) -> None:
    """Age alone never reclaims on the sweep's own initiative, at any age.

    The safety property the automatic callers rest on. A build writes deep
    inside its scratch without touching the top-level directory, so that
    directory's timestamp stops moving early in a run and says nothing about
    whether the run is still going -- which is why nothing the sweep does by
    itself is allowed to turn on that timestamp.
    """
    var = _var(tmp_path)
    mine = _aged(_scratch_tree(var, var_scratch_name(RELEASE_COHORT_INTEGRATION_FAMILY, "d" * 32)), 30 * _DAY)

    assert sweep_var_scratch(var, now=time.time()) == (0, 1)
    assert mine.is_dir()


def test_the_day_ceiling_is_the_backstop_for_a_recycled_identifier(tmp_path: Path) -> None:
    """Under an operator's age reclaim the ceiling outranks the liveness answer.

    Deliberate, and the reason is identifier reuse: a recycled process id makes
    an abandoned directory look owned, and with liveness on top of the ceiling
    that directory would be retained forever instead of for one more day.
    Nothing live reaches a day -- the integration proof that mints this family
    caps itself at an hour.
    """
    var = _var(tmp_path)
    looks_owned = _aged(_scratch_tree(var, var_scratch_name(RELEASE_COHORT_INTEGRATION_FAMILY, "e" * 32)), 2 * _DAY)

    assert sweep_var_scratch(var, now=time.time(), reclaim_by_age=True) == (1, 0)
    assert not looks_owned.exists()


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
        ".4812-release-cohort-9f2a.staging",
        ".4812-release-python-9f2a-source",
        ".4812-release-python-9f2a-source.zip",
        ".4812-probe-command-spec-bytecode",
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
    link = var / var_scratch_name(RELEASE_COHORT_INTEGRATION_FAMILY, "c" * 32)
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


def test_an_abandoned_release_staging_directory_is_reclaimed(tmp_path: Path) -> None:
    """A killed release build's staging cohort goes without an operator asking.

    The property the call site's comment claims. Staging names carry their
    owner, so a build that died leaves a name the sweep can resolve a liveness
    answer for -- and a full cohort's worth of bytes is reclaimed at the start
    of the next build rather than sitting until someone runs ``--apply`` a day
    later.
    """
    var = _var(tmp_path)
    abandoned = _aged(_scratch_tree(var, _foreign_owner_name(RELEASE_STAGING_FAMILY, "release-cohort-9f2a")), 20 * 60)

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (1, 0)
    assert not abandoned.exists()


def test_an_abandoned_cohort_build_tree_and_its_archive_are_reclaimed(tmp_path: Path) -> None:
    """The extracted source tree and the Git archive beside it both go.

    Thirty-nine thousand files and a several-hundred-megabyte zip, removed by
    the cohort build in a ``finally`` block that a kill never reaches. The
    archive is the registered family whose member is a FILE, so this is also
    the proof that the sweep is not directory-only.
    """
    var = _var(tmp_path)
    tree = _aged(
        _scratch_tree(var, _foreign_owner_name(COHORT_BUILD_TREE_FAMILY, "release-python-9f2a")),
        20 * 60,
    )
    archive = _aged(
        _scratch_file(var, _foreign_owner_name(COHORT_SOURCE_ARCHIVE_FAMILY, "release-python-9f2a")),
        20 * 60,
    )

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (2, 0)
    assert not tree.exists()
    assert not archive.exists()


def test_an_abandoned_probe_bytecode_root_is_reclaimed(tmp_path: Path) -> None:
    """The attestation probe's redirected bytecode root is registered scratch too."""
    var = _var(tmp_path)
    bytecode = _aged(_scratch_tree(var, _foreign_owner_name(COMMAND_SPEC_BYTECODE_FAMILY, "probe")), 20 * 60)

    removed, spared = sweep_var_scratch(var, now=time.time())

    assert (removed, spared) == (1, 0)
    assert not bytecode.exists()


def test_a_live_owner_spares_every_registered_family(tmp_path: Path) -> None:
    """This process's own scratch survives in every family, at any age.

    Parametrised over the registry rather than over a written list, so a family
    added to :data:`VAR_SCRATCH_FAMILIES` is covered by this safety property the
    moment it is registered.
    """
    var = _var(tmp_path)
    mine = [_aged(_scratch_tree(var, var_scratch_name(family, "body")), 30 * _DAY) for family in VAR_SCRATCH_FAMILIES]

    assert sweep_var_scratch(var, now=time.time()) == (0, len(VAR_SCRATCH_FAMILIES))
    assert all(entry.is_dir() for entry in mine)


def test_every_minted_name_lands_in_the_family_it_was_minted_from() -> None:
    """The mint and the judge agree, family by family.

    The single-sourcing this module rests on: a name built from a family
    constant must be recognised as belonging to that same family, or the mint
    sites and the sweep are describing different things.
    """
    minted = {family: var_scratch_name(family, "body") for family in VAR_SCRATCH_FAMILIES}

    assert {family: matching_family(name) for family, name in minted.items()} == {
        family: family for family in VAR_SCRATCH_FAMILIES
    }
    assert {_owning_pid(name, family) for family, name in minted.items()} == {os.getpid()}


def test_a_minted_name_needs_a_body_to_distinguish_it() -> None:
    """A bare prefix and suffix is the shape the judge refuses, so the mint refuses it.

    Without this the caller would receive a name no sweep would ever consider
    and no error would say so.
    """
    with pytest.raises(ValueError, match="needs a body"):
        var_scratch_name(RELEASE_STAGING_FAMILY, "")


@pytest.mark.parametrize(
    "owner",
    [
        "\N{SUPERSCRIPT TWO}",
        "9" * 5000,
        "0",
        "-4",
        str(2**31),
    ],
)
def test_an_unreadable_owner_token_is_no_owner_rather_than_a_refusal(owner: str) -> None:
    """A name this module did not mint cannot abort the session that reads it.

    ``str.isdigit`` is true of characters :func:`int` refuses and imposes no
    magnitude, and the sweep runs from a session hook that suppresses only
    ``OSError``. A hand-created ``var/`` entry carrying any of these would have
    ended collection for every packaging test rather than being spared.
    """
    family = RELEASE_STAGING_FAMILY
    name = f"{family.prefix}{owner}-body{family.suffix}"

    assert matching_family(name) is family
    assert _owning_pid(name, family) is None


def test_a_legacy_ownerless_name_is_read_as_carrying_no_owner() -> None:
    """The hex run ids minted before the owner existed stay operator-only."""
    family = RELEASE_COHORT_INTEGRATION_FAMILY
    name = _legacy_ownerless_name()

    assert matching_family(name) is family
    assert _owning_pid(name, family) is None


def test_remove_scratch_takes_a_file_as_well_as_a_tree(tmp_path: Path) -> None:
    """Stated as a property of the removal, since one registered family is a file."""
    var = _var(tmp_path)
    archive = _scratch_file(var, _foreign_owner_name(COHORT_SOURCE_ARCHIVE_FAMILY, "release-python-9f2a"))
    tree = _scratch_tree(var, _foreign_owner_name(COHORT_BUILD_TREE_FAMILY, "release-python-9f2a"))

    assert remove_scratch(archive) is True
    assert remove_scratch(tree) is True
    assert list(var.iterdir()) == []
