"""Fail a run that leaves profile-session acceleration entries behind in the OS credential store.

Every sign-in of a profile stores one ``<profile>:<session>@cadrumo:profile-session:v2`` generic credential (the session
acceleration key). A run that is killed or that never logs out leaves it, and the store is finite: leaked entries
exhausted the machine's credential store. A run records the entries it started with, and at its end the entries it
did not start with must be gone; each remaining one is named, so a leak is a failure and not a slow drift.

The listing is the Windows credential manager's (``cmdkey /list``); on another platform nothing is listed, so the
guard passes vacuously and says so.

Other runs sign in and out at the same time, so an entry added during a run is not necessarily the run's own. The run
names its own storage roots (``--own-root DIR``, repeatable): an added entry whose profile id is a folder of one of
those roots' ``keystore`` or ``buckets`` is the run's own and fails the check; an entry of any other profile is listed
as not this run's and does not fail. A run that names no root owns nothing, so it only lists what was added.

Run as ``python -m dev.acceptance.persona_table.credential_guard snapshot FILE`` before a run and
``python -m dev.acceptance.persona_table.credential_guard check FILE [--own-root DIR ...]`` after it; ``check`` exits 1
and names the run's own entries when any was added and not removed, 0 otherwise. Only target names are read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from dev.packaging.command_execution import run_command

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_ROOT_DEPTH = 4
_SKIPPED = frozenset({"node_modules", ".git", ".venv", "target", "dist"})
SERVICE = "cadrumo:profile-session:v2"
"""The OS-keychain service the profile-session acceleration keys are stored under."""
_TARGET = re.compile(r"target=(?P<target>\S+@" + re.escape(SERVICE) + r")\s*$")


def entries_in(listing: str) -> frozenset[str]:
    """The profile-session targets named in a ``cmdkey /list`` listing."""
    found: set[str] = set()
    for line in listing.splitlines():
        if match := _TARGET.search(line.strip()):
            found.add(str(match["target"]))
    return frozenset(found)


def current_entries() -> frozenset[str] | None:
    """The profile-session targets in the credential store now, or ``None`` where no listing is available."""
    if sys.platform != "win32":
        return None
    tool = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "cmdkey.exe"
    result = run_command([str(tool), "/list"], cwd=Path.cwd(), timeout_seconds=60, errors="replace")
    return entries_in(result.stdout) if result.returncode == 0 else None


def leaked(before: Iterable[str], after: Iterable[str]) -> list[str]:
    """The targets present after a run that were not present before it, sorted."""
    return sorted(set(after) - set(before))


def _folders(path: Path) -> list[Path]:
    try:
        return [Path(entry.path) for entry in os.scandir(path) if entry.is_dir(follow_symlinks=False)]
    except OSError:
        return []


def owned_profile_ids(roots: Iterable[Path]) -> frozenset[str]:
    """The profile ids (``keystore`` and ``buckets`` folder names) of ``roots`` and of the storage roots under them."""
    found: set[str] = set()
    for root in roots:
        stack = [(root, 0)]
        while stack:
            path, level = stack.pop()
            if path.name in _SKIPPED:
                continue
            for folder in ("keystore", "buckets"):
                found.update(child.name.lower() for child in _folders(path / folder) if _UUID.match(child.name.lower()))
            if level < _ROOT_DEPTH:
                stack.extend(
                    (child, level + 1) for child in _folders(path) if child.name not in {"keystore", "buckets"}
                )
    return frozenset(found)


def main(argv: Sequence[str] | None = None) -> int:
    """``snapshot FILE`` writes the current entries; ``check FILE`` exits 1 naming the entries added since."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "check"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--own-root", type=Path, action="append", default=[], dest="own_roots")
    arguments = parser.parse_args(argv)
    now = current_entries()
    if now is None:
        print("credential guard: no credential listing on this platform; nothing checked", file=sys.stderr)
        return 0
    if arguments.action == "snapshot":
        arguments.file.write_text(json.dumps(sorted(now)), encoding="utf-8")
        print(f"credential guard: {len(now)} profile-session entries recorded")
        return 0
    before = json.loads(arguments.file.read_text(encoding="utf-8"))
    added = leaked(before, now)
    owned = owned_profile_ids(arguments.own_roots)
    mine = [target for target in added if target.split(":", 1)[0].lower() in owned]
    others = [target for target in added if target not in mine]
    if others:
        print(f"credential guard: {len(others)} added entries are not this run's (other roots), listed only:")
        for target in others:
            print(f"  {target}")
    if mine:
        print(f"credential guard: {len(mine)} profile-session entries left behind by the run:", file=sys.stderr)
        for target in mine:
            print(f"  {target}", file=sys.stderr)
        return 1
    print(f"credential guard: no profile-session entry of the run's own roots left behind ({len(now)} present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
