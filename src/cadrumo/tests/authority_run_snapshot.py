"""Freeze the checkout's published authority for the lifetime of one pytest run.

The checkout's authority root is also the target the registry publisher writes
to, and publishing while a suite runs is routine in a shared worktree. Every
publish rewrites the descriptor, the runtime owner notices the new descriptor
bytes and opens a fresh reader, and a fresh reader carries a fresh generation
pin. Session-scoped leases and profile record authorities minted before the
publish then disagree with everything minted after it, and the generation guard
refuses the mix -- correctly -- so a run that straddles a publish fails wholesale
for a reason that has nothing to do with the code under test.

A run therefore reads a private copy of the generation that was current when it
started. The copy keeps the ``.authority`` directory name the seed contract
checks, and it lives under the process's collection storage root so the existing
exit cleanup and stale-root sweep reclaim it.

Pure-stdlib on purpose, for the same reason as ``collection_storage_root``: it
runs before any Cadrumo import may resolve ``Settings``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

_DESCRIPTOR_NAME = "authority.current.json"
_SNAPSHOT_ATTEMPTS = 3


def freeze_authority_root(live_root: Path, snapshot_parent: Path) -> Path | None:
    """Copy the generation ``live_root`` currently selects into ``snapshot_parent``.

    Returns the frozen root, named like the live one, or ``None`` when the live
    root selects no generation -- a checkout that has never published keeps
    resolving the live root so its refusal names the path an operator can fix.
    A publish that retires the selected database mid-copy is retried against the
    descriptor it left behind.
    """
    descriptor_path = live_root / _DESCRIPTOR_NAME
    frozen_root = snapshot_parent / live_root.name
    for _ in range(_SNAPSHOT_ATTEMPTS):
        try:
            descriptor_bytes = descriptor_path.read_bytes()
        except FileNotFoundError:
            return None
        database_name = json.loads(descriptor_bytes)["database"]
        frozen_root.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(live_root / database_name, frozen_root / database_name)
        except FileNotFoundError:
            continue
        # The descriptor lands last so the frozen root never selects a database
        # it does not yet hold.
        (frozen_root / _DESCRIPTOR_NAME).write_bytes(descriptor_bytes)
        return frozen_root
    raise RuntimeError(f"the authority under {live_root} kept changing while a test run tried to freeze it")


__all__ = ["freeze_authority_root"]
