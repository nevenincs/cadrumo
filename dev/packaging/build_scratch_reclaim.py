"""Reclaim abandoned release-build scratch under the repository's ``var/``.

``var/`` is not a scratch directory. It is a mixed one: the readiness gate
reads its cohort, smoke and evidence trees out of it, an operator keeps
long-lived probe trees there, and the release build drops working copies
beside all of that. So the reclaim rule here cannot be "remove what looks
old" -- it is "remove members of the scratch families this package mints,
and nothing else". :data:`VAR_SCRATCH_FAMILIES` is that registry, every
entry anchored at both ends, and every mint site builds its name with
:func:`var_scratch_name` from the family constant it is registered under, so
a rename cannot leave the sweep looking for a name nothing writes any more.

The reclaim exists because a finalizer cannot cover the case that produces
the leak. A killed process runs no ``finally`` block and no ``atexit`` hook,
so the only moment guaranteed to execute is the START of a later run -- the
same reasoning that reclaims the abandoned per-process storage roots under the
OS temp directory. The liveness probe is imported from there rather than
written again, because a second probe is a second chance to get the Windows
failure mode wrong in the direction that deletes a live run's tree.

What the automatic callers act on is narrower than what that sweep takes, and
deliberately so. An entry is reclaimed on the sweep's own initiative only when
its name carries an owner and that process is OBSERVED to be gone. The day-long
mtime ceiling -- an INFERENCE, and the only rule available to a name carrying
no readable owner -- is applied when an operator asks for it, through
``--apply`` on this module or ``reclaim_by_age`` on the sweep. That is the same
line the temp-file reaper in this tree draws, and it matters more here: the OS
temp directory holds nothing anyone curates, and ``var/`` holds gigabytes an
operator keeps on purpose beside the scratch.

Carrying the owner is therefore what makes a family reclaimable without an
operator, and :func:`var_scratch_name` is the only mint. A family whose names
were spelled by hand at the call site could be reclaimed by nothing but an
operator, however plainly a comment beside it promised otherwise. Names minted
before that helper existed carry no readable owner and stay operator-only;
they are why the ownerless path remains a supported answer rather than an
error.

Removal is deliberately not ``shutil.rmtree(..., ignore_errors=True)``. The
largest family here is a Git clone, whose object files are read-only, and on
Windows unlinking a read-only file fails with ``[WinError 5] Access is
denied``. ``ignore_errors`` swallows exactly that error, so a sweep written
the obvious way reports success and reclaims nothing; :func:`remove_tree`
clears the attribute and retries instead.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.tests.collection_storage_root import process_is_live

from .._paths import REPO_ROOT


@dataclass(frozen=True)
class ScratchFamily:
    """One build-scratch naming family under ``var/``, anchored at both ends.

    Both anchors are required. A prefix alone would make the staging family --
    whose prefix is a single leading dot -- cover every hidden entry an
    operator ever put under ``var/``.
    """

    prefix: str
    suffix: str


RELEASE_COHORT_INTEGRATION_FAMILY: Final[ScratchFamily] = ScratchFamily(
    prefix="release-cohort-integration-",
    suffix="-source",
)
"""Bracket the source clone the real double-build integration proof works from.

That test clones the repository so both of its builds see one immovable tip,
and removes the clone in a ``finally`` block. The block covers a test that
finishes; it covers neither a killed worker nor a killed session, and this
suite's own ceiling documents that a worker parked in ``subprocess.wait()``
exits uncleanly rather than unwinding.
"""

RELEASE_STAGING_FAMILY: Final[ScratchFamily] = ScratchFamily(
    prefix=".",
    suffix=".staging",
)
"""Bracket the directory a release cohort is assembled in before it is published.

``build_release_cohort`` builds into a hidden sibling of its output and moves
it into place at the end, removing it explicitly when the build raises. A kill
lands between those two, leaving a full cohort's worth of bytes behind -- both
sdists, the wheelhouse and the several-hundred-megabyte source archive. The
name carries its owner, so the next build's sweep reclaims it on an observed
liveness answer rather than leaving it for an operator.
"""

COHORT_BUILD_TREE_FAMILY: Final[ScratchFamily] = ScratchFamily(
    prefix=".",
    suffix="-source",
)
"""Bracket the extracted Git archive ``uv build`` packages the cohort from.

Some thirty-nine thousand files, extracted beside the cohort output and removed
in a ``finally`` block -- which is the coverage this module exists because of.
"""

COHORT_SOURCE_ARCHIVE_FAMILY: Final[ScratchFamily] = ScratchFamily(
    prefix=".",
    suffix="-source.zip",
)
"""Bracket the Git archive the build tree is extracted from.

The one registered family whose member is a FILE rather than a directory: it is
moved into the cohort on the success path, so what survives a kill is a
several-hundred-megabyte archive at the working name.
"""

COMMAND_SPEC_BYTECODE_FAMILY: Final[ScratchFamily] = ScratchFamily(
    prefix=".",
    suffix="-command-spec-bytecode",
)
"""Bracket the redirected bytecode root the installed CommandSpec probe compiles into.

The probe reads a tree that defines a published artifact, so its bytecode is
written beside that tree rather than into it. Removed in a ``finally`` block on
every path the probe returns from, and left behind by every path it does not.
"""

VAR_SCRATCH_FAMILIES: Final[tuple[ScratchFamily, ...]] = (
    RELEASE_COHORT_INTEGRATION_FAMILY,
    RELEASE_STAGING_FAMILY,
    COHORT_BUILD_TREE_FAMILY,
    COHORT_SOURCE_ARCHIVE_FAMILY,
    COMMAND_SPEC_BYTECODE_FAMILY,
)
"""Every family this sweep will consider. Anything not matching one is spared.

A family added to a mint site and not to this tuple leaks without bound; a
family named here that no mint site writes reclaims nothing and costs one
string comparison. The asymmetry is why every mint site builds its name with
:func:`var_scratch_name` from one of the constants above rather than spelling
its own, and why a gate reads this tuple back against the sites.
"""

_STALE_AFTER_SECONDS: Final[float] = 24 * 60 * 60
"""Age past which a scratch entry is reclaimed on mtime alone.

Deliberately the same generous day used for the abandoned storage roots under
the OS temp directory, and for the same reason: mtime is only a PROXY for
liveness. A build that has been quiet for a while is indistinguishable on disk
from an abandoned one, so where mtime is the only signal the threshold has to
out-wait the slowest plausible quiet period. No release build runs for a day;
one that somehow did would be spared for as long as it kept writing.
"""

_ABANDONED_AFTER_SECONDS: Final[float] = 10 * 60
"""Grace applied only AFTER the owning process is confirmed gone.

Not a staleness estimate: it covers clock skew on the mtime read and a process
that has just exited whose own cleanup is still mid-removal. It applies only to
a name that carries a readable owner, which is the only case where liveness is
observed rather than inferred.
"""

_MAX_OWNER_DIGITS: Final[int] = 10
_MAX_OWNER_PID: Final[int] = 2**31
"""Bounds on the owner token a scratch name may claim to carry.

A process identifier is a small positive integer on every platform this runs
on. Refusing anything outside that range costs nothing and keeps a hand-created
directory -- whose name this module has no control over -- from reaching
:func:`int` with a thousand-digit run of decimals, which raises rather than
returning a number. The sweep runs from a session hook that suppresses only
``OSError``, so a value error there would abort collection for the whole suite
instead of sparing one directory.
"""


def var_scratch_name(family: ScratchFamily, body: str) -> str:
    """Return one ``var/`` name in ``family``, owned by this process.

    The single mint. The owner is placed immediately after the family prefix,
    which is what lets :func:`_owning_pid` read it back without knowing
    anything about the body, and what lets the sweep act on an OBSERVED
    liveness answer rather than waiting out the day-long mtime ceiling that a
    name without a readable owner leaves as the only rule.

    Args:
        family: The registered family the name must belong to.
        body: The caller's own discriminator -- an output name, a run id, or
            both. Must be non-empty: a bare prefix and suffix is the shape
            :func:`matching_family` deliberately refuses, so a name built from
            an empty body would be minted outside every family and swept by
            nothing.

    Returns:
        A name :func:`matching_family` places in ``family``.
    """
    if not body:
        raise ValueError(f"a scratch name needs a body to distinguish it: {family!r}")
    return f"{family.prefix}{os.getpid()}-{body}{family.suffix}"


def matching_family(name: str) -> ScratchFamily | None:
    """Return the scratch family ``name`` belongs to, or ``None`` for anything else.

    The single place a name is judged in or out of scope. A directory listing
    reaches this function; nothing reaches the removal without passing it.
    """
    for family in VAR_SCRATCH_FAMILIES:
        # The length test keeps the two anchors from overlapping, so a bare
        # ``.staging`` -- prefix and suffix satisfied by the same characters --
        # is not read as a member of a family whose real names carry a body
        # between them.
        if (
            name.startswith(family.prefix)
            and name.endswith(family.suffix)
            and len(name) > len(family.prefix) + len(family.suffix)
        ):
            return family
    return None


def _owning_pid(name: str, family: ScratchFamily) -> int | None:
    """Return the process identifier ``name`` carries, or ``None`` if it carries none.

    ``None`` is the answer that leaves the mtime ceiling as the only rule, and
    it covers every shape :func:`var_scratch_name` did not produce -- including
    the names minted before that helper existed, which carry a bare hex run id.

    The token is read as DECIMAL rather than as "digits". ``str.isdigit`` is
    true of characters :func:`int` refuses -- superscripts among them -- and
    imposes no magnitude, so a hand-created ``var/`` entry could reach
    :func:`int` with a value that raises. Nothing above catches that: the
    session hook this runs from suppresses ``OSError`` alone, so the refusal
    would abort collection for every packaging test rather than spare one
    directory.
    """
    owner = name.removeprefix(family.prefix).split("-", maxsplit=1)[0]
    if not owner.isdecimal() or len(owner) > _MAX_OWNER_DIGITS:
        return None
    pid = int(owner)
    return pid if 0 < pid < _MAX_OWNER_PID else None


def _is_reclaimable(
    candidate: Path,
    family: ScratchFamily,
    reference: float,
    *,
    reclaim_by_age: bool,
) -> bool:
    """Decide whether ``candidate`` may be removed, erring towards retention.

    Two independent grounds. The first is OBSERVED: the name carries an owner,
    that process no longer resolves, and the short abandonment grace has
    elapsed. The second is INFERRED: nothing is left to ask, and the directory
    has simply been quiet past the day ceiling.

    Only the observed ground is applied by default, and that split is the whole
    reason this sweep is safe to run automatically over ``var/``. The temp-file
    reaper in this tree draws the same line for the same reason: automating a
    deletion decided by observation is a different risk from automating one
    decided by inference, and ``var/`` holds operator-curated trees that the OS
    temp directory does not.

    ``reclaim_by_age`` adds the inferred ground, and belongs to an operator who
    has asked for it.

    Where both grounds are in play the ceiling is checked FIRST, so an operator
    reclaiming by age takes a day-old directory whose named owner still appears
    to be running. That ordering is deliberate, and it is the backstop for
    process-identifier reuse: a recycled identifier makes an abandoned
    directory look owned, and with the liveness answer on top it would be
    retained forever rather than for one more day. Nothing live reaches the
    ceiling -- a release build runs in minutes, and the integration proof that
    mints the largest family is capped at an hour by its own timeout -- and the
    automatic callers never apply the ceiling at all.
    """
    age = reference - candidate.stat().st_mtime
    if reclaim_by_age and age > _STALE_AFTER_SECONDS:
        return True
    if age <= _ABANDONED_AFTER_SECONDS:
        return False
    pid = _owning_pid(candidate.name, family)
    return pid is not None and not process_is_live(pid)


def remove_tree(directory: Path) -> bool:
    """Remove ``directory`` whole, clearing read-only attributes that block it.

    A Git clone -- the shape of the largest family swept here -- stores its
    objects read-only, and Windows refuses to unlink a read-only file. The
    handler clears the attribute and retries the operation that failed, which
    is what makes the difference between reporting a reclaim and performing
    one.

    Returns:
        Whether the directory is gone afterwards. ``False`` covers a tree
        another process still holds open, which is left for the next sweep.
    """

    def _clear_read_only(action: Callable[[str], object], path: str, _exc: BaseException) -> None:
        os.chmod(path, stat.S_IWRITE)
        action(path)

    try:
        shutil.rmtree(directory, onexc=_clear_read_only)
    except OSError:
        return not directory.exists()
    return True


def remove_scratch(candidate: Path) -> bool:
    """Remove one judged scratch entry, whichever kind it is.

    Most registered families name directories, but the cohort build's Git
    archive is a single several-hundred-megabyte FILE at a working name until
    the moment it is moved into the cohort. Leaving files to the next sweep
    would mean the sweep never reclaimed one.

    Returns:
        Whether the entry is gone afterwards.
    """
    if candidate.is_dir():
        return remove_tree(candidate)
    try:
        os.chmod(candidate, stat.S_IWRITE)
        candidate.unlink(missing_ok=True)
    except OSError:
        return not candidate.exists()
    return True


def reclaimable_scratch(
    var_root: Path,
    *,
    now: float | None = None,
    exclude: Path | None = None,
    reclaim_by_age: bool = False,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Judge every ``var_root`` entry, deleting nothing.

    Separated from the removal so the decision is inspectable on its own: an
    operator can read the verdicts and a test can assert them without anything
    being at risk while they do.

    Returns:
        ``(reclaimable, spared)`` -- the scratch entries that may be removed,
        and the ones a rule refused. Entries belonging to no registered family
        appear in neither: they were never candidates.
    """
    reference = time.time() if now is None else now
    spared_name = None if exclude is None else exclude.name
    reclaimable: list[Path] = []
    spared: list[Path] = []
    for candidate in scan_directory(var_root):
        family = matching_family(candidate.name)
        if family is None:
            continue
        if candidate.name == spared_name:
            spared.append(candidate)
            continue
        try:
            # A link is not the tree it names, and the families here are
            # anchored on a name rather than on an inode: removing a link
            # because its name matched would remove whatever an operator
            # pointed it at.
            if is_link_like(candidate):
                continue
            verdict = _is_reclaimable(candidate, family, reference, reclaim_by_age=reclaim_by_age)
        except OSError:
            spared.append(candidate)
            continue
        (reclaimable if verdict else spared).append(candidate)
    return tuple(reclaimable), tuple(spared)


def sweep_var_scratch(
    var_root: Path,
    *,
    now: float | None = None,
    exclude: Path | None = None,
    reclaim_by_age: bool = False,
) -> tuple[int, int]:
    """Reclaim abandoned build scratch under ``var_root``, sparing everything else.

    Safe to run concurrently and repeatedly: nothing it removes belongs to a
    live run, so two sweepers reaching one entry at once cannot make any run
    observe a difference. Every filesystem error is absorbed -- this is
    tidiness, not correctness, and a scratch entry left behind is never read by
    anything.

    Args:
        var_root: The repository's ``var/`` directory.
        now: Reference time, defaulting to the wall clock. Injectable so a test
            can age a directory rather than wait out the grace.
        exclude: An entry to leave alone regardless of every other rule,
            normally the calling run's own scratch. Its owner is live, so the
            liveness rule already spares it; naming it means the caller never
            depends on that reasoning holding.
        reclaim_by_age: Also reclaim scratch whose name carries no owner and
            which has been quiet past the day ceiling. Off for the automatic
            callers, which act only on an observed answer; see
            :func:`_is_reclaimable`.

    Returns:
        ``(removed, spared)`` -- how many scratch entries were reclaimed, and
        how many were examined and left alone. The spared count is the
        safety evidence: a sweep that took everything and a sweep that took
        only what it should both report a removal count.
    """
    reclaimable, spared = reclaimable_scratch(
        var_root,
        now=now,
        exclude=exclude,
        reclaim_by_age=reclaim_by_age,
    )
    removed = 0
    retained = len(spared)
    for candidate in reclaimable:
        if remove_scratch(candidate):
            removed += 1
        else:
            retained += 1
    return removed, retained


def _scratch_bytes(candidate: Path) -> int:
    if candidate.is_file():
        return candidate.stat().st_size
    return sum(entry.stat().st_size for entry in scan_directory(candidate, recursive=True) if entry.is_file())


def main(argv: list[str] | None = None) -> int:
    """Report abandoned ``var/`` build scratch, and reclaim it under ``--apply``.

    The operator switch for the inferred ground. Every automatic caller acts
    only on an observed one, so an entry whose name carries no readable owner
    -- the shape every snapshot minted before :func:`var_scratch_name` existed
    has -- is reported here and removed only when asked.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--var-root", type=Path, default=REPO_ROOT / "var")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove the scratch entries judged abandoned; without it nothing is deleted",
    )
    parser.add_argument(
        "--observed-only",
        action="store_true",
        help="consider only scratch whose named owner is confirmed gone, as the automatic callers do",
    )
    arguments = parser.parse_args(argv)
    var_root = arguments.var_root.resolve()
    reclaimable, spared = reclaimable_scratch(var_root, reclaim_by_age=not arguments.observed_only)

    print(f"build scratch under {var_root}", file=sys.stdout)
    for candidate in spared:
        print(f"  SPARE {candidate.name}", file=sys.stdout)
    total = 0
    for candidate in reclaimable:
        size = _scratch_bytes(candidate)
        total += size
        print(f"  REAP  {candidate.name}  {size / 1_000_000_000:.3f} GB", file=sys.stdout)
    verb = "reclaimed" if arguments.apply else "reclaimable"
    print(f"  {verb}: {total / 1_000_000_000:.3f} GB   spared: {len(spared)}", file=sys.stdout)
    if arguments.apply:
        for candidate in reclaimable:
            remove_scratch(candidate)
    else:
        print("  nothing was deleted; pass --apply to act on the REAP lines above", file=sys.stdout)
    return 0


__all__ = [
    "COHORT_BUILD_TREE_FAMILY",
    "COHORT_SOURCE_ARCHIVE_FAMILY",
    "COMMAND_SPEC_BYTECODE_FAMILY",
    "RELEASE_COHORT_INTEGRATION_FAMILY",
    "RELEASE_STAGING_FAMILY",
    "VAR_SCRATCH_FAMILIES",
    "ScratchFamily",
    "matching_family",
    "reclaimable_scratch",
    "remove_scratch",
    "remove_tree",
    "sweep_var_scratch",
    "var_scratch_name",
]


if __name__ == "__main__":
    raise SystemExit(main())
