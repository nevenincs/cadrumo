"""The supervised key-derivation child must not import the persistence graph.

Every wrap, unwrap and calibration spawns a fresh interpreter that runs one
Argon2id hash and one AEAD operation. That child once paid 1.7 s importing the
storage package graph -- SQLAlchemy, the ORM, the encrypted-column helpers, the
blob store, the capsule machinery -- against 0.275 s of actual cryptography, so
roughly 86% of every supervised call was import and 11% was the hash. The cost
is paid on the production login path, not only in the suite.

This gate pins the PROPERTY that made the fix work: the worker's module graph
excludes the heavy subsystems it never uses. It deliberately does not assert a
wall-clock budget -- a timing threshold on a contended machine is flaky, and it
would fail for reasons that have nothing to do with the import graph.
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_WORKER_MODULE = "cadrumo.adapters.persistence.storage.custody._kdf_worker"

_FORBIDDEN_IN_CHILD: tuple[str, ...] = (
    # The ORM stack, reached through the encrypted-column helpers.
    "sqlalchemy",
    # The HTML corpus reader, reached through the core facade.
    "bs4",
    # Persistence subsystems the child performs no I/O against.
    "cadrumo.adapters.persistence.storage.blob_store",
    "cadrumo.adapters.persistence.storage.envelope",
    "cadrumo.adapters.persistence.storage.sql",
    "cadrumo.adapters.persistence.storage.master_key",
    # The capsule machinery: the child is handed framed bytes, never a capsule.
    "cadrumo.adapters.persistence.storage.custody.capsule",
)


def _child_modules(prelude: str = "") -> frozenset[str]:
    """Import the worker in a fresh interpreter and report its module graph.

    A real subprocess, because that is exactly how the supervisor runs it and
    it is the only way to observe a clean module table. ``prelude`` runs before
    the worker import so a caller can prove this gate still bites.
    """
    source = f"{prelude}\nimport {_WORKER_MODULE}\nimport json, sys\nprint(json.dumps(sorted(sys.modules)))"
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, interpreter is sys.executable
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    # Validated rather than cast: the child prints its own module table, so a
    # child that failed differently could print anything, and a bare cast would
    # let that reach the set comparison as a silently empty or wrong graph.
    names = json.loads(completed.stdout)
    assert isinstance(names, list), "the worker child must print a JSON list of module names"
    assert all(isinstance(name, str) for name in names), "module names must be strings"
    return frozenset(str(name) for name in names)


def test_kdf_worker_child_excludes_the_heavy_persistence_graph() -> None:
    """The worker's child interpreter imports none of the heavy subsystems."""
    modules = _child_modules()

    # Floor the observation: an empty or truncated module table would let every
    # membership test below pass while proving nothing.
    assert _WORKER_MODULE in modules, (
        f"the child did not import {_WORKER_MODULE}; the probe observed nothing, "
        "so the exclusions below would pass vacuously"
    )

    present = sorted(name for name in _FORBIDDEN_IN_CHILD if name in modules)
    assert present == [], (
        f"the supervised key-derivation child imported {present}. Every wrap and unwrap "
        "spawns this interpreter to perform one Argon2id hash, so an eager import "
        "anywhere on its path is paid on the production login path. Resolve the symbol "
        "through the owning package's lazy facade instead of binding it at import time."
    )


def test_the_exclusion_probe_still_bites() -> None:
    """Importing a forbidden subsystem first must be observable by the probe.

    Without this, a probe that silently stopped seeing the child's module table
    would report success forever. The prelude imports one forbidden subsystem
    directly, which is precisely the regression this gate exists to catch.
    """
    modules = _child_modules(prelude="import sqlalchemy")

    assert "sqlalchemy" in modules, (
        "the probe did not observe a module the child provably imported; it can no "
        "longer distinguish a clean graph from a dirty one"
    )


def test_every_forbidden_target_still_resolves() -> None:
    """Anchor the prohibition's target set, so a rename cannot empty it.

    This gate is keyed on module PATHS, and a path that no longer exists is
    trivially absent from any child's module table -- so a rename retires the
    rule silently while leaving it green. The bite-proof above cannot catch
    that: it exercises ``sqlalchemy``, a third-party name that will not move,
    so the five first-party paths could all be renamed with the proof still
    passing.

    A sibling gate in this tree lost its whole subject exactly this way -- four
    pinned custody symbols were removed, and its prohibition went on asserting
    that nobody imports names nothing has. It was visible only because it
    carried an anchor like this one.
    """
    unresolvable: list[str] = []
    for target in _FORBIDDEN_IN_CHILD:
        try:
            importlib.import_module(target)
        except ImportError:
            unresolvable.append(target)

    assert not unresolvable, (
        f"these forbidden import targets no longer resolve: {unresolvable}. A prohibition on a "
        "name nothing has is vacuous -- re-point it at whatever the subsystem is called now, or "
        "drop the entry deliberately if the subsystem is genuinely gone."
    )
