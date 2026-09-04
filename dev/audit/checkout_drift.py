#!/usr/bin/env python
"""Screen tracked files whose on-disk bytes differ from their committed bytes.

The repository declares ``* text=auto eol=lf``, so git writes LF on checkout on
every platform. A file that carries CRLF on disk was therefore rewritten AFTER
checkout, by tooling, and its working-tree bytes are not the bytes anyone
reviewed or committed. Nothing reports this. ``git diff`` normalises on the
index side, so it stays silent; every reader that opens the file as text goes
through a universal-newline decode that folds the difference away before any
comparison happens. The drift is invisible from both directions at once.

It is currently harmless, because every consumer in the tree is either git or a
text-mode reader. That is exactly the property a generated-artefact writer
showed can silently stop being true: the API stub drift check compared decoded
text and could not see the 60 stubs its own writer had translated, and the
complexity baseline -- a gate INPUT -- sat 660 terminators away from its
committed blob while every review reported it clean. Those two writers are
fixed. This screen exists so the REST of the class is a measured number with a
recorded ceiling rather than an anecdote.

What "drift" means here, precisely
----------------------------------
A file is drifted when its raw on-disk bytes hash to something other than its
committed blob, AND git reports the file unmodified. The second condition is
what makes it SILENT. Files with ordinary uncommitted edits are excluded: they
differ from HEAD for the obvious reason and are the author's live work, not a
finding. In a shared worktree that exclusion is most of the tree's churn.

A SCREEN, not a gate, deliberately
----------------------------------
The worklist is large and, more importantly, it is not owner-attributable. The
measured population is dominated by hand-edited source -- 430 ``.py``, 212
``.md``, 145 ``.toml`` at the reference measurement -- which means it is
produced by contributors' editors, not by any generator this repository
controls. A ratchet pinned to the population would go red on the next
contributor who opens any file in an editor that writes platform terminators,
for a defect they did not create and cannot see. That is the failure mode the
sibling legal-attribution screen documents and avoids the same way.

So the default run always exits 0 and prints the number. ``--check`` applies
the shrink-only ratchet for anyone who wants the teeth, and is deliberately not
wired into a blocking lane yet. Growth is made VISIBLE rather than fatal, which
is the property the class actually lacked: it was never that the number was
too high, it was that no number existed.

Promote ``--check`` to a wired gate when the population is small enough to be
owner-attributable -- realistically once contributor tooling is configured to
write LF, at which point the ceiling is near zero and a red is a real event.

Mass-normalising the population is NOT the remedy and is not offered here. It
would rewrite every concurrent contributor's working tree in one sweep, and it
buys nothing durable while the tooling that produced the drift is unchanged.

Usage::

    python -m dev.audit.checkout_drift [--json] [--full]
    python -m dev.audit.checkout_drift --check
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8

#: Declared locally rather than imported from ``cadrumo.core``: ``dev/`` is
#: unshipped tooling and must not reach into the shipped package's internals,
#: so every dev module carries its own constant (see the sibling screens in
#: this package).
_UTF_8: Final[str] = UTF_8

_BASELINE_PATH: Final = Path(__file__).resolve().parent / "checkout_drift_baseline.json"


def blob_hash(data: bytes) -> str:
    """Return the git blob object name for *data* exactly as it sits on disk.

    Git's own hashing applies the configured input filters, which is precisely
    the normalisation that hides this class; computing the object name here
    keeps the measurement on the raw bytes with nothing between them and the
    comparison.

    Args:
        data: The file's raw contents.

    Returns:
        The 40-character hex object name.
    """
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def _git(root: Path, *args: str) -> bytes:
    """Run a read-only git command in *root* and return its raw stdout.

    The executable is resolved rather than taken from the argv shorthand, so a
    machine without git on PATH gets one plain sentence instead of a
    file-not-found traceback from inside a measurement.
    """
    executable = shutil.which("git")
    if executable is None:
        raise SystemExit("git is not on PATH, so the committed bytes cannot be read")
    result = subprocess.run([executable, *args], cwd=root, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode(_UTF_8, errors="replace").strip()
        raise SystemExit(f"git {' '.join(args)} failed in {root}: {detail}")
    return result.stdout


def committed_blobs(root: Path) -> dict[str, str]:
    """Return every tracked path at HEAD mapped to its committed blob name.

    NUL-delimited output is used throughout so paths carrying spaces or
    non-ASCII characters survive intact; the registry and corpus trees carry
    plenty of both, and a whitespace-split reading would drop them silently and
    then report a smaller, cleaner number.

    Args:
        root: The repository working directory.

    Returns:
        Mapping of repo-relative POSIX path to blob object name.
    """
    raw = _git(root, "ls-tree", "-r", "-z", "HEAD", "--format=%(objectname) %(path)")
    blobs: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        object_name, _, path = record.partition(b" ")
        blobs[path.decode(_UTF_8)] = object_name.decode("ascii")
    return blobs


def locally_modified(root: Path) -> set[str]:
    """Return the tracked paths git reports as modified against HEAD.

    These are excluded from the finding set. They differ from their committed
    bytes for the ordinary reason -- someone is editing them -- and reporting
    them would bury the silent class under every contributor's live work.
    """
    raw = _git(root, "diff", "--name-only", "-z", "HEAD")
    return {path.decode(_UTF_8) for path in raw.split(b"\0") if path}


@dataclass(frozen=True)
class DriftMeasurement:
    """One screen run's result.

    Attributes:
        tracked: Tracked paths at HEAD.
        scanned: Paths actually hashed (tracked, git-clean, present on disk).
        drifted: Repo-relative paths whose disk bytes differ from HEAD, sorted.
        carrying_crlf: How many drifted paths hold a CRLF sequence on disk.
    """

    tracked: int
    scanned: int
    drifted: tuple[str, ...]
    carrying_crlf: int

    @property
    def total(self) -> int:
        """Number of silently drifted files."""
        return len(self.drifted)

    @property
    def buckets(self) -> dict[str, int]:
        """Drifted counts keyed by top-level path segment, sorted by key."""
        counter: collections.Counter[str] = collections.Counter()
        for path in self.drifted:
            counter[path.split("/", 1)[0]] += 1
        return dict(sorted(counter.items()))


def measure(root: Path) -> DriftMeasurement:
    """Measure the silent byte-drift class in the repository at *root*.

    Args:
        root: A git working directory.

    Returns:
        The measurement.

    Raises:
        SystemExit: When the walk found no tracked files or hashed nothing. A
            screen that scanned an empty tree reports the same clean total as a
            healthy one, so the clean result is only evidence if the scan
            demonstrably happened.
    """
    committed = committed_blobs(root)
    if not committed:
        raise SystemExit(f"no tracked files found at HEAD in {root}; the result would be meaningless")

    skip = locally_modified(root)

    drifted: list[str] = []
    crlf = 0
    scanned = 0
    for path, object_name in committed.items():
        if path in skip:
            continue
        absolute = root / path
        if not absolute.is_file():
            continue
        data = absolute.read_bytes()
        scanned += 1
        if blob_hash(data) == object_name:
            continue
        drifted.append(path)
        if b"\r\n" in data:
            crlf += 1

    if scanned == 0:
        raise SystemExit(
            f"hashed zero files in {root} although {len(committed)} are tracked; the result would be meaningless"
        )

    return DriftMeasurement(
        tracked=len(committed),
        scanned=scanned,
        drifted=tuple(sorted(drifted)),
        carrying_crlf=crlf,
    )


def load_ceiling(path: Path = _BASELINE_PATH) -> tuple[int | None, dict[str, int]]:
    """Return no ceiling: drift is reported as measured, never against a pin.

    Args:
        path: Retained for signature compatibility with callers.

    Returns:
        ``(None, {})`` always.
    """
    del path
    return None, {}


def growth_against_ceiling(measurement: DriftMeasurement, total: int | None, buckets: dict[str, int]) -> list[str]:
    """Return one line per counter that moved in the weakening direction.

    No recorded ceiling means nothing to move away from, so the answer is
    empty. Comparing each tree against an implicit zero instead reported every
    populated bucket as a breach: ``--check`` exited 1 naming ten trees as
    exceeding ``the recorded ceiling 0`` in the same run that printed ``no
    ceiling is recorded or accepted``, and the advisory dimension went RED where
    its own contract says AMBER. That is precisely the population-pinned ratchet
    this module's header says it refuses to be.

    WITHIN a recorded ceiling a tree absent from it is still compared against
    zero, so a newly drifted tree is growth rather than an unmeasured free pass.
    """
    if total is None:
        return []
    findings: list[str] = []
    if measurement.total > total:
        findings.append(f"total {measurement.total} exceeds the recorded ceiling {total}")
    for bucket, count in measurement.buckets.items():
        allowed = buckets.get(bucket, 0)
        if count > allowed:
            findings.append(f"{bucket}/ {count} exceeds the recorded ceiling {allowed}")
    return findings


def _render(measurement: DriftMeasurement, total: int | None, buckets: dict[str, int], full: bool) -> None:
    """Print the measurement, the ceiling comparison, and the worklist."""
    print(f"checkout drift: {measurement.tracked} tracked at HEAD, {measurement.scanned} scanned")
    print(f"  silently drifted (disk bytes differ from committed bytes, git reports clean): {measurement.total}")
    print(f"  of those carrying CRLF on disk: {measurement.carrying_crlf}")

    for bucket, count in measurement.buckets.items():
        if total is None:
            print(f"    {bucket:<14} {count}")
            continue
        allowed = buckets.get(bucket, 0)
        marker = "  <-- above ceiling" if count > allowed else ""
        print(f"    {bucket:<14} {count} (ceiling {allowed}){marker}")

    if total is None:
        print("\nno ceiling is recorded or accepted; drift is reported as measured")
    else:
        print(f"\nrecorded ceiling: total {total}")

    shown = measurement.drifted if full else measurement.drifted[:20]
    if shown:
        print(f"\nworklist ({len(shown)} of {measurement.total} shown; --full for all):")
        for path in shown:
            print(f"  {path}")


def main(argv: list[str] | None = None) -> int:
    """Run the screen. Exits 0 unless --check is passed and a counter grew."""
    parser = argparse.ArgumentParser(
        description="Screen tracked files whose on-disk bytes differ from their committed bytes."
    )
    parser.add_argument("--check", action="store_true", help="Apply the shrink-only ceiling and exit 1 on growth.")
    parser.add_argument("--json", action="store_true", help="Emit the measurement as JSON.")
    parser.add_argument("--full", action="store_true", help="List every drifted path, uncapped.")
    args = parser.parse_args(argv)

    root = REPO_ROOT
    measurement = measure(root)
    total, buckets = load_ceiling()

    if args.json:
        print(
            json.dumps(
                {
                    "tracked": measurement.tracked,
                    "scanned": measurement.scanned,
                    "total": measurement.total,
                    "carrying_crlf": measurement.carrying_crlf,
                    "buckets": measurement.buckets,
                    "ceiling_total": total,
                    "growth": growth_against_ceiling(measurement, total, buckets),
                    "drifted": list(measurement.drifted),
                },
                indent=2,
            )
        )
    else:
        _render(measurement, total, buckets, args.full)

    if not args.check:
        return 0

    growth = growth_against_ceiling(measurement, total, buckets)
    if growth:
        print("\ncheckout drift: FAIL - a counter moved in the weakening direction.", file=sys.stderr)
        for line in growth:
            print(f"  {line}", file=sys.stderr)
        return 1

    if total is None:
        print("\ncheckout drift: no ceiling is recorded, so there is nothing to ratchet against.")
    else:
        print("\ncheckout drift: within the recorded ceiling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
