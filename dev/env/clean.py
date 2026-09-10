"""The repository's one reclamation command, over three families with three owners.

Dispatches the worktree's own ignored output (this module), release-build
scratch under ``var/`` (:mod:`dev.packaging.build_scratch_reclaim`), and the
temp directory's pytest, session and test-run storage
(:mod:`dev.env.temp_reaper`). Each family keeps its rules where they are
reasoned about; this file decides only which sections run and in what order.

``.git`` is reported on and never modified. Loose-object accrual, stray lock
files and an interrupted rebase are all things an operator wants to know about
and none of them are things a cleanup should decide for them; the remedy for
each is a git command with its own consequences.

The command always exits 0. It is a maintenance report whose removals are a
side effect, not a gate: there is no state of a developer's worktree that this
should turn a build red over. Report by default, act under ``--apply``, one
section at a time under ``--only``.

Run ``just clean`` for the report and ``just clean-apply`` to act on it.

The worktree section, which is what the rest of this module implements, sorts
ignored paths into three populations that are not interchangeable:

**Regenerable output.** ``__pycache__``, the six tool caches, ``build/``,
``dist/``, the generated documentation trees. Every byte of it is reproduced by
a command that already exists, nothing reads it across a run boundary, and
deleting it costs a rebuild. This is the only family this module removes.

**State an operator would lose.** ``.env`` and everything under ``env/``, the
``.venv``, ``secrets/``, ``cadrumo-storage/``, the ``.vault`` and ``.vaultspec``
trees, ``.logs/``. Most of it is ignored by git for exactly
the reason it must survive a clean: it is local, it is not reproducible from
the repository, and some of it is live key material and taxpayer financial
data. This family is protected by name and is never walked, never sized and
never removed -- not even when a cache directory sits inside it.

**Everything else that is ignored.** ``scratch/``, ``.tmp/``, ``dbg/``, the
root-level one-shot dumps the ``.gitignore`` collects at its foot. It is
*probably* disposable and it is *often* the biggest thing on the disk, but the
name says "ad-hoc", not "reproducible", and an agent's half-finished capture is
indistinguishable on disk from a finished one. This family is reported with its
size and left alone. ``--include PATH`` promotes one entry into the removal set
for a single run, which is how an operator says "that one, yes" without this
module having guessed it.

Untracked files that are NOT ignored are in-flight work by definition -- git
reports them in ``status`` -- and are counted, never touched. So is anything
tracked and modified.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, TextIO

from cadrumo.core.link_safety import is_link_like

from .._paths import REPO_ROOT, UTF_8
from ..packaging.build_scratch_reclaim import report_var_scratch
from .temp_reaper import report_temporary_storage

WORKTREE_FAMILY: Final = "worktree"
VAR_SCRATCH_FAMILY: Final = "var-scratch"
TEMP_FAMILY: Final = "temp"

FAMILIES: Final[frozenset[str]] = frozenset({WORKTREE_FAMILY, VAR_SCRATCH_FAMILY, TEMP_FAMILY})
"""The three reclamation families this command dispatches, each with one owner.

Folded into one command because they were three commands an operator had to
know about separately, and the accrual they bound does not respect that split:
the biggest thing on the disk moved between ``var/`` and ``.logs/`` depending on
what had been run that week, so a report covering one of them at a time never
showed where the space actually went.

Folded as DISPATCH rather than as a merge. Each family's rules stay in the
module that owns them -- this file reasons about ignored worktree paths,
:mod:`dev.packaging.build_scratch_reclaim` about registered scratch families and
their live owners, :mod:`dev.env.temp_reaper` about session liveness and idle
ceilings. A single set of merged rules would have to be right about all three
kinds of evidence at once, and the one that got it wrong would delete something.
"""

BLOAT_THRESHOLD_BYTES: Final = 10 * 1000 * 1000
"""Size at which a spared entry is called out as suspected bloat rather than listed.

Not a deletion threshold -- nothing here deletes on size -- but the line
between "an ignored file" and "the reason the volume is full". Ten megabytes is
larger than any scratch note, any captured command output and any one-shot
script, and smaller than every accrual family that has actually filled a disk
in this repository.
"""

LOOSE_OBJECT_CEILING: Final = 5000
"""Loose objects past which the git object store is worth repacking.

Git's own automatic threshold, which it applies only when a command happens to
trigger ``gc --auto``. A worktree driven mostly by tooling can sit above it for
a long time without any command triggering that check, which is the whole
reason this report names the number instead of assuming git noticed.
"""

PROTECTED_SEGMENTS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "secrets",
        "cadrumo-storage",
        ".logs",
        ".claude",
        ".codex",
        ".agents",
        ".gemini",
        ".agent",
        ".idea",
        ".vscode",
    }
)
"""Directory names that stop this module at any depth, whatever they contain.

Matched per path segment rather than as a root-anchored prefix. A nested
``env/`` or ``secrets/`` holds the same thing a top-level one does, and the
enumeration below reports whole directories, so a segment test is what makes
the protection independent of where git happened to collapse the entry.

``var`` is deliberately absent, and its absence is the corrected version of a
mistake worth recording. It was protected here on the strength of its name and
the ignore file's warning that a local run materialises real key material and
real financial data. Looking inside showed something else: ``var/storage``
holds a ``cache/`` tree of content-addressed registry pickles, a corpus-text
extraction cache and a validation verdict -- 346 MB of pure derived output and
not one byte of taxpayer data. The store the warning is about lives at
``secrets/`` and ``cadrumo-storage/``, which are still protected by segment
wherever they appear, including underneath ``var``. Guarding a name instead of
a fact is what this module's own docstring tells its reader not to do.
"""

VAR_SCRATCH_OWNER: Final = "var"
"""The mixed root whose scratch families are judged by the packaging sweep.

Everything directly under ``var`` except :data:`VAR_APPLICATION_STORAGE` is
reported by the build-scratch section instead of here. That section knows which
names are registered scratch families and whether their owning process is still
alive; this module knows neither, and two mechanisms printing a verdict about
one directory is how an operator ends up trusting the wrong one.
"""

VAR_APPLICATION_STORAGE: Final = "var/storage"
"""The dev loop's application storage root, which is not build scratch.

``CADRUMO_LOCAL_STORAGE_ROOT`` is pointed here by the justfile, so this tree is
the application's own cache and logs rather than anything the release build
minted. It stays with the worktree section, which is what owns caches.
"""

MIXED_ROOTS: Final[frozenset[str]] = frozenset({VAR_SCRATCH_OWNER, VAR_APPLICATION_STORAGE})
"""Ignored directories whose children are classified individually.

Git collapses a wholly-ignored directory to one entry, which is normally the
saving that makes this command affordable. It is wrong for a root that holds
several unrelated things: ``var`` carries the release cohort's working trees,
an operator's long-lived probe trees, and a cache, and no single verdict is
right for all three. The packaging sweep that owns ``var`` says the same thing
in its own words -- it is a mixed directory, so the rule cannot be keyed on the
parent.

Expansion is one level per entry and recurses only while the child is itself
named here, so this stays a short, readable list rather than a general walk of
whatever git happened to collapse.
"""

PROTECTED_NAME_PREFIXES: Final[tuple[str, ...]] = (".env", "vault", ".vault")
"""Name prefixes that protect a segment: the dotenv family and every vault tree.

``vault`` is a prefix rather than an exact name on purpose. ``.vault``,
``.vaultspec`` and ``.vault-scratch`` are three different things with one
property in common -- the harness owns them, and this module has no business
deciding what inside them is disposable.
"""

PROTECTED_SUFFIXES: Final[tuple[str, ...]] = (
    ".key",
    ".kdf",
    ".pem",
    ".p12",
    ".pfx",
    ".db",
    ".sqlite3",
    ".pypirc",
    ".netrc",
)
"""File extensions that protect an entry wherever it sits.

The belt to the segment list's braces. Key material and local databases are the
two families whose accidental removal is unrecoverable rather than merely
expensive, and both have moved between directories in this repository's
history; keying on the name as well as the location means a move cannot quietly
take a file out of protection.
"""

CACHE_DIRECTORY_NAMES: Final[frozenset[str]] = frozenset(
    {
        "__pycache__",
        "__pypackages__",
        ".pytest_cache",
        ".import_linter_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".ty_cache",
        ".pyrefly_cache",
        ".complexipy_cache",
        ".hypothesis",
        ".tox",
        ".nox",
        ".pytype",
        ".pyre",
        ".scrapy",
        ".webassets-cache",
        ".ipynb_checkpoints",
        ".pdm-build",
        "cython_debug",
        "htmlcov",
    }
)
"""Tool cache directories, matched by name at any depth.

Every one is rebuilt by the tool that owns it on its next run, and none is read
by anything else. Depth-independence is the point for ``__pycache__``, which
appears beside every package in the tree.

Bare ``cache`` and ``.cache`` are deliberately absent. Both are ignored by this
repository and both are also perfectly ordinary names for a directory something
durable lives in; a name that generic earns a FLAG line, not a removal.
"""

GENERATED_PATHS: Final[frozenset[str]] = frozenset(
    {
        "build",
        "dist",
        "sdist",
        "wheels",
        "site",
        "target",
        "docs/_build",
        "docs/cli",
        "docs/_generated",
        "docs/locales/pot",
        "docs/_static/cli-tree.json",
        "docs/_static/download-latest.json",
        "playwright-report",
        "test-results",
        ".playwright-mcp",
        "var/storage/cache",
    }
)
"""Build and documentation outputs, matched as exact repository-relative paths.

Root-anchored where the cache names above are not, because these names are
generic. A ``build/`` at the repository root is a packaging artefact; a
``build/`` inside a corpus directory could be anything, and this module is not
the thing that should find out.

``var/storage/cache`` is the dev loop's own application cache, and it is here
rather than in :data:`CACHE_DIRECTORY_NAMES` for exactly that reason: the
justfile points ``CADRUMO_LOCAL_STORAGE_ROOT`` into the checkout, so this one
path is derived output by construction, while a bare ``cache`` anywhere else
still earns a report line instead of a removal.
"""

CACHE_FILE_SUFFIXES: Final[tuple[str, ...]] = (".pyc", ".pyo", ".pyd", ".pyz", ".egg-info")
"""Compiled and packaging artefacts identified by extension alone.

``.mo`` and ``.pot`` are not here even though the ignore file lists them: the
compiled catalogues are a build product of a locale pipeline this module does
not run, and mixing a translation artefact into a cache sweep is how a locale
gate starts failing for a reason nobody connects to a cleanup.
"""

CACHE_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".coverage",
        "coverage.xml",
        ".dmypy.json",
        "dmypy.json",
        "nosetests.xml",
    }
)

GIT_IN_PROGRESS_MARKERS: Final[tuple[str, ...]] = (
    "rebase-merge",
    "rebase-apply",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
    "sequencer",
)
"""Paths under the git directory that mean an operation is half-finished.

Reported, never removed. Each one is the state a git command is resuming from,
and a cleanup that deletes it turns a resumable rebase into a lost one.
"""

GIT_TIMEOUT_SECONDS: Final = 300

SPARED_LISTING_LIMIT: Final = 12
"""How many below-threshold spared entries are listed before the tail is summed.

Only the tail is folded; every entry over :data:`BLOAT_THRESHOLD_BYTES` is
printed whatever this says, because those are the lines the section exists for.
"""


class Verdict(Enum):
    """What this module has decided about one ignored entry."""

    REAP = "REAP"
    FLAG = "FLAG"
    KEEP = "KEEP"


@dataclass(frozen=True)
class Entry:
    """One ignored path, the decision made about it, and the evidence for that decision."""

    relative: str
    verdict: Verdict
    reason: str
    total_bytes: int = 0

    @property
    def bloated(self) -> bool:
        """Is this a spared entry large enough to be worth an operator's attention?"""
        return self.verdict is Verdict.FLAG and self.total_bytes >= BLOAT_THRESHOLD_BYTES


def _git(repo_root: Path, *arguments: str) -> str:
    """Return the stdout of one read-only git invocation over ``repo_root``.

    The executable is resolved rather than left to the argv shorthand, so a
    machine without git gets one sentence instead of a traceback from inside a
    reclamation pass, and no PATH entry can point the enumeration at a
    different tree than the one being cleaned.

    A non-zero status is absorbed and returns whatever was written to stdout.
    Every caller here is asking a question with a defensible empty answer -- no
    ignored files, no prunable worktrees -- and this command's contract is that
    it exits 0 and reports what it could establish.
    """
    executable = shutil.which("git")
    if executable is None:
        raise SystemExit("git is not on PATH, so the worktree cannot be enumerated")
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no caller input
        [executable, *arguments],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="replace",
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return completed.stdout


def _listing(repo_root: Path, *arguments: str) -> list[str]:
    """Return a NUL-delimited git listing as repository-relative POSIX paths."""
    return [line for line in _git(repo_root, *arguments, "-z").split("\0") if line]


def ignored_entries(repo_root: Path) -> list[str]:
    """Every ignored path, with a wholly-ignored directory collapsed to one entry.

    ``--directory`` is what keeps this affordable: without it the enumeration
    walks into ``.venv`` and returns tens of thousands of paths that the
    protection rules then discard one at a time. With it, git stops at the
    directory whose ignore rule matched, and ``.venv/`` is a single string this
    module refuses in a single comparison.
    """
    return _listing(
        repo_root,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "--directory",
        "--no-empty-directory",
    )


def in_flight(repo_root: Path) -> tuple[int, int]:
    """Return ``(untracked-but-not-ignored, tracked-and-changed)`` counts.

    Both populations are in-flight work by construction, and neither is
    reachable from the ignored enumeration above, so this is a report rather
    than a filter. It exists so an operator reading a clean result can see that
    the clean result was not achieved by removing what they were in the middle
    of.
    """
    untracked = _listing(repo_root, "ls-files", "--others", "--exclude-standard")
    changed = [line for line in _git(repo_root, "status", "--porcelain=v1").splitlines() if line]
    return len(untracked), len(changed)


def _protection(relative: str) -> str | None:
    """Return why ``relative`` is protected, or ``None`` when it is not.

    Every segment is tested, not just the first. Git may collapse a directory
    at any depth, so the segment that carries the protection is not reliably the
    one at the front of the path.
    """
    for segment in (part for part in relative.strip("/").split("/") if part):
        if segment in PROTECTED_SEGMENTS:
            return f"'{segment}' holds local state that is not reproducible from the repository"
        if segment.startswith(PROTECTED_NAME_PREFIXES):
            return f"'{segment}' belongs to the dotenv or vault family, which this command never touches"
        if segment.endswith(PROTECTED_SUFFIXES):
            return f"'{segment}' looks like key material or a local database"
    return None


def _reapable(relative: str) -> str | None:
    """Return why ``relative`` is regenerable output, or ``None`` when it is not."""
    stripped = relative.strip("/")
    segments = [part for part in stripped.split("/") if part]
    if not segments:
        return None
    if stripped in GENERATED_PATHS:
        return "a build or documentation output regenerated by its owning command"
    for segment in segments:
        if segment in CACHE_DIRECTORY_NAMES:
            return f"'{segment}' is a tool cache rebuilt on the tool's next run"
    name = segments[-1]
    if name.endswith(CACHE_FILE_SUFFIXES):
        return "a compiled or packaging artefact with no source role"
    if name in CACHE_FILE_NAMES or name.startswith(".coverage."):
        return "a measurement artefact regenerated by the run that produced it"
    return None


def holds_only_cache(path: Path) -> bool:
    """Is every file below ``path`` a tool cache or compiled artefact?

    This is what turns an orphaned package directory back into a cache. Deleting
    a module's source leaves ``fincas/__pycache__/`` and ``fincas/tests/__pycache__/``
    behind, and git then reports the whole of ``fincas/`` as ignored -- one path
    whose own name matches nothing in :data:`CACHE_DIRECTORY_NAMES`, so the name
    test alone spares a directory containing nothing but ``.pyc`` files.

    The answer is established by looking, not inferred from the name, which is
    why it is allowed to promote a removal. A link anywhere below makes the
    answer False: a link is not the thing it names, and this walk cannot speak
    for whatever is on the other side of one.
    """
    if is_link_like(path) or not path.is_dir():
        return False
    seen = False
    for parent, directories, files in os.walk(path):
        location = Path(parent)
        if location.name in CACHE_DIRECTORY_NAMES:
            directories.clear()
            seen = seen or bool(files)
            continue
        if any(is_link_like(location / name) for name in (*directories, *files)):
            return False
        for name in files:
            if _reapable(name) is None:
                return False
            seen = True
    return seen


def expand(repo_root: Path, relative: str) -> list[str]:
    """Return the entries to classify for ``relative``: itself, or its children.

    A mixed root is replaced by its immediate children, and a child that is
    itself a mixed root is replaced in turn. Everything else is returned
    unchanged, so this costs one directory listing for the two names in
    :data:`MIXED_ROOTS` and nothing at all for the rest of the enumeration.

    A listing that cannot be read yields the parent unchanged. Failing back to
    the collapsed entry is the outcome that spares: the parent is not reapable
    by name, so it becomes a report line rather than a removal.
    """
    stripped = relative.strip("/")
    if stripped not in MIXED_ROOTS:
        return [relative]
    directory = repo_root / stripped
    if is_link_like(directory):
        return [relative]
    try:
        children = sorted(entry.name for entry in directory.iterdir())
    except OSError:
        return [relative]
    if not children:
        return [relative]
    expanded: list[str] = []
    for name in children:
        child = f"{stripped}/{name}"
        expanded.extend(expand(repo_root, f"{child}/" if (directory / name).is_dir() else child))
    return expanded


def classify(repo_root: Path, relative: str, *, promoted: frozenset[str] = frozenset()) -> tuple[Verdict, str]:
    """Decide one ignored entry, protection first.

    The ordering is the whole safety property. A protected tree that happens to
    contain a cache directory is still protected, and an operator's explicit
    ``--include`` promotes only from FLAG -- never past a protection, because
    the paths protection covers are the ones whose removal cannot be undone by
    re-running a command.
    """
    protection = _protection(relative)
    if protection is not None:
        return Verdict.KEEP, protection
    stripped = relative.strip("/")
    if stripped.startswith(f"{VAR_SCRATCH_OWNER}/") and not stripped.startswith(VAR_APPLICATION_STORAGE):
        return Verdict.KEEP, "release-build scratch, judged by its owning section below"
    reason = _reapable(relative)
    if reason is not None:
        return Verdict.REAP, reason
    if holds_only_cache(repo_root / relative.strip("/")):
        return Verdict.REAP, "an orphaned directory holding nothing but tool cache output"
    if relative.strip("/") in promoted:
        return Verdict.REAP, "promoted for this run by an explicit --include"
    return Verdict.FLAG, "ignored, but not something this command can prove is regenerable"


def measure(path: Path) -> int:
    """Return the total bytes under ``path``, absorbing what cannot be read.

    Under-reporting is the safe direction for every number this module prints:
    the REAP total is a claim about what was reclaimed, and the FLAG total is an
    argument for an operator to spend attention on something. Overstating either
    is the failure mode worth designing against.

    A link is measured as zero rather than followed. Its size is the size of a
    tree this module is not looking at, and attributing that tree's bytes to an
    entry here would invite a removal decision about someone else's data.
    """
    if is_link_like(path):
        return 0
    try:
        if path.is_file():
            return path.stat().st_size
    except OSError:
        return 0
    total = 0
    stack = [path]
    while stack:
        try:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    try:
                        # `scandir` carries the kind and the size from the
                        # directory read itself on every platform this runs on,
                        # so the branch below costs no syscall where `os.walk`
                        # plus a joined `os.stat` pays for a second lookup per
                        # file. Over the 40 GB `var/` tree that is the whole
                        # difference between a command an operator runs and one
                        # they learn to skip.
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def assess(repo_root: Path, *, promoted: frozenset[str] = frozenset()) -> list[Entry]:
    """Judge every ignored entry, deleting nothing and never walking a protected tree.

    Protected entries carry no size for the same reason they carry no risk:
    sizing them means walking ``.venv`` and ``var/storage`` on every run, and
    that cost is what stops a maintenance command from being run at all.
    """
    entries: list[Entry] = []
    enumerated = [child for relative in ignored_entries(repo_root) for child in expand(repo_root, relative)]
    for relative in enumerated:
        verdict, reason = classify(repo_root, relative, promoted=promoted)
        measured = 0 if verdict is Verdict.KEEP else measure(repo_root / relative.strip("/"))
        entries.append(Entry(relative=relative, verdict=verdict, reason=reason, total_bytes=measured))
    return entries


def reclaim(repo_root: Path, entries: list[Entry]) -> tuple[int, int]:
    """Remove every REAP entry and return ``(bytes reclaimed, entries removed)``.

    Best-effort per entry, on the same reasoning the temp reaper uses: a cache
    file a live tool still holds open makes the removal fail partway, that is
    not a state anything reads, and the next run finishes the job. A link is
    skipped rather than removed, because removing a link is one operation and
    removing what it points at is a different one.
    """
    reclaimed = 0
    removed = 0
    for entry in entries:
        if entry.verdict is not Verdict.REAP:
            continue
        target = repo_root / entry.relative.strip("/")
        if is_link_like(target) or not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            try:
                target.unlink()
            except OSError:
                continue
        if target.exists():
            # The absorbed failure above is deliberate, but a partial removal
            # reclaimed no known quantity and must not be counted into a total
            # printed to the operator as 'reclaimed'.
            continue
        reclaimed += entry.total_bytes
        removed += 1
    return reclaimed, removed


def git_observations(repo_root: Path) -> list[str]:
    """Report on the git directory without modifying one byte of it.

    Every condition below has a remedy, and every remedy is a git command with
    consequences an operator should choose deliberately: repacking rewrites the
    object store, removing a lock file overrides another process's claim, and
    deleting an interrupted rebase discards the work it was resuming. Naming the
    condition is the useful half; deciding it is not this command's.
    """
    resolved = _git(repo_root, "rev-parse", "--git-dir").strip()
    if not resolved:
        return ["the git directory could not be resolved, so nothing was inspected"]
    git_dir = Path(resolved)
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir

    counts = {
        key.strip(): value.strip()
        for key, _, value in (line.partition(":") for line in _git(repo_root, "count-objects", "-v").splitlines())
        if key.strip()
    }

    def number(field: str) -> int:
        try:
            return int(counts.get(field, "0") or 0)
        except ValueError:
            return 0

    # `count-objects -v` reports every size in KiB, so each one is scaled here
    # rather than handed to a byte formatter that would divide it a second time.
    loose = number("count")
    observations = [
        f"objects: {loose} loose ({_human(number('size') * 1024)}),"
        f" {number('packs')} pack(s) ({_human(number('size-pack') * 1024)})"
    ]
    if loose > LOOSE_OBJECT_CEILING:
        observations.append(
            f"BLOAT  {loose} loose objects have accrued past git's own {LOOSE_OBJECT_CEILING} threshold;"
            " `git gc` repacks them (not run here: it rewrites the object store)"
        )
    if number("garbage") or number("size-garbage"):
        observations.append(
            f"BLOAT  {number('garbage')} unrecognised file(s)"
            f" ({_human(number('size-garbage') * 1024)}) sit in the object store"
        )
    if (git_dir / "gc.log").is_file():
        observations.append("NOTE   gc.log is present: a previous `git gc` failed and git has stopped retrying")

    locks = sorted(path.name for path in git_dir.glob("*.lock") if path.is_file())
    if locks:
        observations.append(
            f"HELD   {len(locks)} lock file(s) in the git directory ({', '.join(locks)})."
            " A live git process holds these; leftovers from a killed one look identical,"
            " and overriding another process's claim is an operator decision, so none was removed."
        )

    observations.extend(
        f"INFLGT {marker} exists: a git operation is half-finished and was left alone"
        for marker in GIT_IN_PROGRESS_MARKERS
        if (git_dir / marker).exists()
    )
    observations.extend(
        f"NOTE   {line}"
        for line in _git(repo_root, "worktree", "prune", "--dry-run", "--verbose").splitlines()
        if line.strip()
    )
    return observations


def _human(value: int) -> str:
    """Render a byte count in the largest unit that keeps it above 1.

    Fixed gigabytes read as ``0.000 GB`` for most of what this command finds,
    and a report whose sizes are all zero is a report nobody uses to decide
    anything.
    """
    for unit, scale in (("GB", 1_000_000_000), ("MB", 1_000_000), ("KB", 1_000)):
        if value >= scale:
            return f"{value / scale:6.1f} {unit}"
    return f"{value:6d}  B"


def _print_spared(spared: list[Entry], *, verbose: bool, stream: TextIO) -> None:
    """List the spared entries: every suspected bloat, then the largest of the rest.

    Bloat lines are never truncated -- they are the reason this section exists.
    Below the threshold the population is long-tailed (one entry per abandoned
    agent scratch directory, per stale transaction lock), and printing all of it
    buries the lines that need a decision. ``--verbose`` prints the inventory
    when an operator actually wants to read it.
    """
    bloated = [entry for entry in spared if entry.bloated]
    rest = [entry for entry in spared if not entry.bloated]
    for entry in bloated:
        print(f"  BLOAT {_human(entry.total_bytes)}  {entry.relative}", file=stream)
    shown = rest if verbose else rest[:SPARED_LISTING_LIMIT]
    for entry in shown:
        print(f"        {_human(entry.total_bytes)}  {entry.relative}", file=stream)
    remainder = rest[len(shown) :]
    if remainder:
        total = sum(entry.total_bytes for entry in remainder)
        print(f"        ... and {len(remainder)} smaller entries, {_human(total)} (--verbose lists them)", file=stream)
    if bloated:
        print(
            f"  {len(bloated)} entr{'y' if len(bloated) == 1 else 'ies'} above"
            f" {BLOAT_THRESHOLD_BYTES // 1_000_000} MB were NOT removed:"
            " inspect, then delete by hand or re-run with --include <path>.",
            file=stream,
        )


def _report(entries: list[Entry], *, applying: bool, verbose: bool, stream: TextIO) -> tuple[int, list[Entry]]:
    """Print the decided entries and return ``(reapable bytes, spared entries)``.

    The reap side is summarised by family rather than listed. Several hundred
    ``__pycache__`` directories are one fact about the worktree, not several
    hundred, and a per-path listing of them pushes the spared and git sections
    off the operator's screen.
    """
    reap = sorted((entry for entry in entries if entry.verdict is Verdict.REAP), key=lambda item: -item.total_bytes)
    spared = sorted((entry for entry in entries if entry.verdict is Verdict.FLAG), key=lambda item: -item.total_bytes)
    keep = [entry for entry in entries if entry.verdict is Verdict.KEEP]
    reap_bytes = sum(entry.total_bytes for entry in reap)

    print("\nRegenerable build and cache output", file=stream)
    if not reap:
        print("  none present", file=stream)
    families = {reason: [entry for entry in reap if entry.reason == reason] for reason in {e.reason for e in reap}}
    for reason, family in sorted(families.items(), key=lambda item: -sum(e.total_bytes for e in item[1])):
        total = sum(entry.total_bytes for entry in family)
        print(f"  REAP {_human(total)}  {len(family):4d} entries  {reason}", file=stream)
        if verbose:
            for entry in family:
                print(f"                  {_human(entry.total_bytes)}  {entry.relative}", file=stream)
    if reap:
        verb = "reclaimed" if applying else "reclaimable"
        print(f"  {verb}: {_human(reap_bytes)} across {len(reap)} entries", file=stream)

    total_spared = sum(entry.total_bytes for entry in spared)
    print(f"\nIgnored, spared, not provably regenerable: {len(spared)} entries, {_human(total_spared)}", file=stream)
    if spared:
        _print_spared(spared, verbose=verbose, stream=stream)
    else:
        print("  none", file=stream)

    print(
        f"\nProtected or owned elsewhere, never walked: {len(keep)} entries"
        " (dotenv, vault trees, venv, secrets, logs, agent and editor state,"
        " plus var/ scratch reported by its own section below)",
        file=stream,
    )
    return reap_bytes, spared


def main(argv: list[str] | None = None) -> int:
    """Report the worktree's reclaimable output, removing it only under ``--apply``."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove the REAP entries; without it nothing is deleted",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="PATH",
        help="promote one spared entry into the removal set for this run; never overrides a protection",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="list every entry instead of summarising the reaped families and the spared tail",
    )
    parser.add_argument(
        "--only",
        choices=sorted(FAMILIES),
        action="append",
        default=[],
        metavar="FAMILY",
        help=f"run only the named section(s): {', '.join(sorted(FAMILIES))}. Repeatable; default is all three",
    )
    arguments = parser.parse_args(argv)
    selected = frozenset(arguments.only) or FAMILIES
    promoted = frozenset(path.replace("\\", "/").strip("/") for path in arguments.include)

    repo_root = REPO_ROOT
    untracked, changed = in_flight(repo_root)
    print(f"Worktree {repo_root}", file=sys.stdout)
    print(f"  in-flight work left untouched: {untracked} untracked file(s), {changed} tracked change(s)")

    reap_bytes = 0
    spared: list[Entry] = []
    if WORKTREE_FAMILY in selected:
        entries = assess(repo_root, promoted=promoted)
        reap_bytes, spared = _report(entries, applying=arguments.apply, verbose=arguments.verbose, stream=sys.stdout)
        if arguments.apply:
            reclaimed, removed = reclaim(repo_root, entries)
            print(f"\n  removed {removed} entries, {_human(reclaimed)}", file=sys.stdout)

    if VAR_SCRATCH_FAMILY in selected:
        report_var_scratch(
            sys.stdout,
            repo_root / VAR_SCRATCH_OWNER,
            apply=arguments.apply,
            measure=measure,
            bloat_threshold=BLOAT_THRESHOLD_BYTES,
            ignore_names=frozenset({Path(VAR_APPLICATION_STORAGE).name}),
        )

    if TEMP_FAMILY in selected:
        report_temporary_storage(sys.stdout, apply=arguments.apply, verbose=arguments.verbose)

    if not arguments.apply:
        print("\nNothing was deleted; pass --apply to act on the REAP lines above.", file=sys.stdout)

    print("\nGit directory (reported only, never modified)", file=sys.stdout)
    for observation in git_observations(repo_root):
        print(f"  {observation}", file=sys.stdout)

    if WORKTREE_FAMILY in selected and not reap_bytes and not spared:
        print("\nClean: no regenerable output, and nothing ignored that needs a decision.", file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
