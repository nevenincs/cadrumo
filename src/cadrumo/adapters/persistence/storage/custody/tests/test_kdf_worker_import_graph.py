"""The supervised key-derivation child must not import the persistence graph.

Every wrap, unwrap and calibration spawns a fresh interpreter that runs one
Argon2id hash and one AEAD operation. That child once paid 1.7 s importing the
storage package graph -- SQLAlchemy, the ORM, the encrypted-column helpers, the
blob store, the capsule machinery -- against 0.275 s of actual cryptography, so
roughly 86% of every supervised call was import and 11% was the hash. The cost
is paid on the production login path, not only in the suite.

A second cut removed pydantic and the error hierarchy from the same closure:
the typed records, the constants catalogue and the error codes together cost
about twice the hash, for a child that only reads JSON and writes frames.

This gate pins the PROPERTY that made the fix work: the worker's module graph
excludes the heavy subsystems it never uses. It deliberately does not assert a
wall-clock budget -- a timing threshold on a contended machine is flaky, and it
would fail for reasons that have nothing to do with the import graph.
"""

from __future__ import annotations

import importlib
import json
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody._kdf_process import worker_environment, worker_interpreter
from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_WORKER_MODULE = "cadrumo.adapters.persistence.storage.custody._kdf_worker"

_FORBIDDEN_IN_CHILD: tuple[str, ...] = (
    # The ORM stack, reached through the encrypted-column helpers.
    "sqlalchemy",
    # The HTML corpus reader and its parser dependency.
    "bs4",
    # Persistence subsystems the child performs no I/O against.
    "...blob_store",
    "...envelope",
    "...sql",
    "...master_key",
    # The capsule machinery: the child is handed framed bytes, never a capsule.
    "..capsule",
    # Validation and error machinery: the child checks JSON against the
    # stdlib wire rules and reports refusal as a failure frame.
    "pydantic",
    "cadrumo.core.errors",
    "cadrumo.core.errors.error_codes",
    "cadrumo.core.external_constants",
    "cadrumo.core.models",
    "...errors",
    "..errors",
    "..records",
    "...crypto.aead",
)


_ALLOWED_FIRST_PARTY_IN_CHILD: tuple[str, ...] = (
    # Inert package initialisers on the ``-m`` path.
    "cadrumo",
    "cadrumo.adapters",
    "cadrumo.adapters.persistence",
    "cadrumo.adapters.persistence.storage",
    "cadrumo.adapters.persistence.storage.crypto",
    "cadrumo.adapters.persistence.storage.custody",
    "cadrumo.core",
    # The child itself and its stdlib-only custody leaves.
    "cadrumo.adapters.persistence.storage.custody._kdf_worker",
    "cadrumo.adapters.persistence.storage.custody._kdf_attestation",
    "cadrumo.adapters.persistence.storage.custody._kdf_codec",
    "cadrumo.adapters.persistence.storage.custody._kdf_operations",
    "cadrumo.adapters.persistence.storage.custody._kdf_records",
    "cadrumo.adapters.persistence.storage.custody._kdf_worker_limits",
    "cadrumo.adapters.persistence.storage.custody._profile_password_codec",
    "cadrumo.adapters.persistence.storage.custody._recovery_secret_codec",
    "cadrumo.adapters.persistence.storage._kdf_salt",
    "cadrumo.adapters.persistence.storage.crypto.aes_gcm",
    "cadrumo.core.base64_codec",
    "cadrumo.core.credentials",
    "cadrumo.core.descriptor_write",
    "cadrumo.core.hashing",
)
"""Every first-party module the supervised child may import, and no other.

An allow-list rather than a deny-list: the deny-list above names subsystems
that once leaked in, and cannot see the next one. Any new first-party edge
into the child must be added here deliberately, where the review sees it.
"""

_FORBIDDEN_CLOSURES_IN_CHILD: tuple[str, ...] = ("argon2", "argparse", "ctypes", "pathlib")
"""Closures the child once paid on every launch without using.

``argon2`` is the high-level package: the child calls its C binding,
``_argon2_cffi_bindings``, directly.
"""


def _launched_child_modules(neutral_root: Path, prelude: str = "") -> frozenset[str]:
    """Import the worker with the interpreter, flags and environment the supervisor launches it with."""
    neutral_root.mkdir(parents=True, exist_ok=True)
    source = f"{prelude}\nimport {_WORKER_MODULE}\nimport json, sys\nprint(json.dumps(sorted(sys.modules)))"
    environment = worker_environment(neutral_root=neutral_root)
    if sys.platform != "win32":
        # The POSIX supervisor runs this environment's own interpreter, which
        # resolves its import roots itself; the probe needs them explicitly.
        environment["PYTHONPATH"] = ":".join(entry for entry in sys.path if entry)
    completed = run_audited_process(
        [*worker_interpreter(), "-c", source],
        cwd=neutral_root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    names = json.loads(completed.stdout)
    assert isinstance(names, list), "the worker child must print a JSON list of module names"
    assert all(isinstance(name, str) for name in names), "module names must be strings"
    return frozenset(str(name) for name in names)


def _first_party(modules: frozenset[str]) -> frozenset[str]:
    return frozenset(name for name in modules if name == "cadrumo" or name.startswith("cadrumo."))


def test_kdf_worker_child_imports_only_its_allowlisted_first_party_modules(tmp_path: Path) -> None:
    """The launched child's first-party module table is exactly the allow-list."""
    modules = _launched_child_modules(tmp_path / "neutral")

    assert _WORKER_MODULE in modules, f"the child did not import {_WORKER_MODULE}; the probe observed nothing"
    unexpected = sorted(_first_party(modules).difference(_ALLOWED_FIRST_PARTY_IN_CHILD))
    assert unexpected == [], (
        f"the supervised key-derivation child imported {unexpected}, outside its allow-list. Every "
        "wrap and unwrap launches this interpreter, so each new edge is paid on the sign-in path."
    )
    unused = sorted(name for name in _FORBIDDEN_CLOSURES_IN_CHILD if name in modules)
    assert unused == [], f"the supervised key-derivation child imported {unused}, which it does not use"
    assert "_argon2_cffi_bindings" in modules, "the child must derive through the Argon2 C binding"
    if sys.platform == "win32":
        assert "site" not in modules, "the Windows child must start without site processing"


def test_the_allowlist_probe_bites_on_a_new_first_party_edge(tmp_path: Path) -> None:
    """A first-party module imported ahead of the worker is reported as outside the allow-list."""
    modules = _launched_child_modules(tmp_path / "neutral", prelude="import cadrumo.core.time.utc")

    assert "cadrumo.core.time.utc" in _first_party(modules).difference(_ALLOWED_FIRST_PARTY_IN_CHILD)


def test_every_allowlisted_module_still_resolves() -> None:
    """A renamed leaf must not leave a stale allow-list entry that silently admits a successor name."""
    unresolvable = []
    for name in _ALLOWED_FIRST_PARTY_IN_CHILD:
        try:
            importlib.import_module(name)
        except ImportError:
            unresolvable.append(name)
    assert sorted(unresolvable) == []


def _resolved_target(target: str) -> str:
    return resolve_name(target, __package__) if target.startswith(".") else target


def _child_modules(prelude: str = "") -> frozenset[str]:
    """Import the worker in a fresh interpreter and report its module graph.

    A real subprocess, because that is exactly how the supervisor runs it and
    it is the only way to observe a clean module table. ``prelude`` runs before
    the worker import so a caller can prove this gate still bites.
    """
    source = f"{prelude}\nimport {_WORKER_MODULE}\nimport json, sys\nprint(json.dumps(sorted(sys.modules)))"
    completed = run_audited_process(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        check=True,
    )
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

    present = sorted(_resolved_target(target) for target in _FORBIDDEN_IN_CHILD if _resolved_target(target) in modules)
    assert present == [], (
        f"the supervised key-derivation child imported {present}. Every wrap and unwrap "
        "spawns this interpreter to perform one Argon2id hash, so an eager import "
        "anywhere on its path is paid on the production login path. Keep the dependency "
        "outside the worker's import closure instead of hiding it behind a package facade."
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


@pytest.mark.parametrize(
    "prelude_target",
    ["cadrumo.core.external_constants", "cadrumo.adapters.persistence.storage.custody.errors"],
)
def test_the_exclusion_probe_bites_on_a_first_party_edge(prelude_target: str) -> None:
    """A first-party import re-added ahead of the worker is reported, not just a third-party one.

    The prelude stands in for a worker module that imports the target again,
    which is the regression the validation and error entries exist to catch.
    """
    modules = _child_modules(prelude=f"import {prelude_target}")

    present = sorted(_resolved_target(target) for target in _FORBIDDEN_IN_CHILD if _resolved_target(target) in modules)
    assert prelude_target in modules
    assert present, f"importing {prelude_target} first left every forbidden target absent; the gate cannot bite"


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
        resolved_target = _resolved_target(target)
        try:
            importlib.import_module(target, package=__package__)
        except ImportError:
            unresolvable.append(resolved_target)

    assert not unresolvable, (
        f"these forbidden import targets no longer resolve: {unresolvable}. A prohibition on a "
        "name nothing has is vacuous -- re-point it at whatever the subsystem is called now, or "
        "drop the entry deliberately if the subsystem is genuinely gone."
    )
