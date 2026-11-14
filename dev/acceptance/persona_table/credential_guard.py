"""Fail a run that leaves profile-session acceleration entries behind in the OS credential store.

Every sign-in of a profile stores one ``<profile>:<session>@cadrumo:profile-session:v2`` generic credential (the session
acceleration key). A run that is killed or that never logs out leaves it, and the store is finite: leaked entries
exhausted the machine's credential store. A run records the entries it started with, and at its end the entries it
did not start with must be gone; each remaining one is named, so a leak is a failure and not a slow drift.

The listing is the Windows credential manager's (``cmdkey /list``); on another platform nothing is listed, so the
guard passes vacuously and says so.

Run as ``python -m dev.acceptance.persona_table.credential_guard snapshot FILE`` before a run and
``python -m dev.acceptance.persona_table.credential_guard check FILE`` after it; ``check`` exits 1 and names the
leaked entries when any was added and not removed, 0 otherwise.
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


def main(argv: Sequence[str] | None = None) -> int:
    """``snapshot FILE`` writes the current entries; ``check FILE`` exits 1 naming the entries added since."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "check"))
    parser.add_argument("file", type=Path)
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
    if added:
        print(f"credential guard: {len(added)} profile-session entries left behind by the run:", file=sys.stderr)
        for target in added:
            print(f"  {target}", file=sys.stderr)
        return 1
    print(f"credential guard: no profile-session entry left behind ({len(now)} present, none added)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
