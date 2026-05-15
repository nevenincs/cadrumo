"""Enforce: AEAT-prefixed config READS must flow through ``Settings``.

The architectural mandate is that every AEAT-prefixed environment
variable be read through :class:`aeat.core.config.Settings` (and its
:func:`aeat.core.config.load_settings` accessor), not through direct
``os.environ.get`` / ``os.getenv`` / ``os.environ[...]`` access.

Direct reads bypass:
  - Pydantic-settings validation (type coercion, ``Field`` constraints).
  - The ``.env`` + ``os.environ`` merge order Pydantic-settings enforces.
  - The :func:`override_settings` context manager used by tests.

This test walks every ``.py`` file under ``src/aeat/`` (excluding the
test module itself), parses it into an AST, and reports any expression
that reads ``os.environ`` / ``os.getenv`` with an ``"AEAT_*"`` literal
key. The check is purely structural: a string literal inside a
docstring is *not* a function call, so the AST walk ignores it.

A short allowlist captures the documented irreducible exceptions —
subprocess-IPC WRITE sites where ``Settings`` has no write API. Each
allowlisted line is annotated in-source with a rationale comment.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


# Files (relative to src/aeat/) where direct os.environ access to an
# AEAT-prefixed variable is the only legitimate option. Each entry must
# carry its rationale inline in the source — when reviewing this list,
# verify the rationale matches "no Settings write API exists for this".
_ALLOWLIST: frozenset[str] = frozenset(
    {
        # WRITE side of REPLAY_ACTIVE_ENV_VAR (subprocess-IPC). The READ
        # side flows through Settings (see _context.py — already routed
        # via load_settings().aeat_replay_active). Settings is read-only
        # so the WRITE has no Settings equivalent; the os.environ mutation
        # is observed by the child invocation's subsequent Settings load.
        "core/observability/_replay.py",
    }
)

_AEAT_KEY_PATTERN: re.Pattern[str] = re.compile(r"^AEAT_[A-Z0-9_]+$")


def _candidate_files() -> list[Path]:
    src_root = PROJECT_ROOT / "src" / "aeat"
    candidates: list[Path] = []
    for path in src_root.rglob("*.py"):
        rel = path.relative_to(src_root).as_posix()
        # Exclude this test itself + pytest test files (test reads are
        # expected to use monkeypatch / fresh-Settings fixtures rather
        # than Settings directly, and validation happens elsewhere).
        if rel == "core/test_settings_single_surface_invariant.py":
            continue
        if path.name.startswith("test_") or path.name.startswith("_test_"):
            continue
        if "/tests/" in rel or rel.startswith("tests/"):
            continue
        candidates.append(path)
    return candidates


def _aeat_key_from_arg(node: ast.expr, constants: dict[str, str]) -> str | None:
    """Return the AEAT_* key string if ``node`` is a literal or a name-bound literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if _AEAT_KEY_PATTERN.fullmatch(node.value):
            return node.value
    if isinstance(node, ast.Name):
        resolved = constants.get(node.id)
        if resolved is not None and _AEAT_KEY_PATTERN.fullmatch(resolved):
            return resolved
    return None


def _collect_aeat_constants(tree: ast.Module) -> dict[str, str]:
    """Map module-level NAME bindings whose value is an AEAT_* string literal."""
    constants: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
            value = stmt.value.value
            if isinstance(value, str) and _AEAT_KEY_PATTERN.fullmatch(value):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None and isinstance(stmt.value, ast.Constant):
            value = stmt.value.value
            if isinstance(value, str) and _AEAT_KEY_PATTERN.fullmatch(value):
                if isinstance(stmt.target, ast.Name):
                    constants[stmt.target.id] = value
    return constants


def _violations_in(path: Path) -> list[tuple[int, str, str]]:
    """Return (lineno, key, snippet) tuples for AEAT-prefixed env reads."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants = _collect_aeat_constants(tree)
    violations: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        # os.environ[KEY] or os.environ.get(KEY, ...)
        if isinstance(node, ast.Subscript):
            if _is_os_environ(node.value):
                key = _aeat_key_from_arg(node.slice, constants)
                if key is not None:
                    violations.append((node.lineno, key, "os.environ[...]"))
        elif isinstance(node, ast.Call):
            func = node.func
            # os.environ.{get,pop,setdefault}(KEY, ...) — read or read+mutate
            if (
                isinstance(func, ast.Attribute)
                and func.attr in {"get", "pop", "setdefault"}
                and _is_os_environ(func.value)
                and node.args
            ):
                key = _aeat_key_from_arg(node.args[0], constants)
                if key is not None:
                    violations.append((node.lineno, key, f"os.environ.{func.attr}(...)"))
            # os.getenv(KEY, ...)
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "getenv"
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
                and node.args
            ):
                key = _aeat_key_from_arg(node.args[0], constants)
                if key is not None:
                    violations.append((node.lineno, key, "os.getenv(...)"))
    return violations


def _is_os_environ(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def test_no_direct_aeat_env_reads_outside_allowlist() -> None:
    """Every AEAT_* env read must flow through Settings, except allowlisted IPC writes."""
    src_root = PROJECT_ROOT / "src" / "aeat"
    offences: list[str] = []
    for path in _candidate_files():
        rel = path.relative_to(src_root).as_posix()
        violations = _violations_in(path)
        if not violations:
            continue
        if rel in _ALLOWLIST:
            continue  # documented IPC-write exception
        for lineno, key, snippet in violations:
            offences.append(f"{rel}:{lineno}  reads {key!r} via {snippet}")
    assert not offences, (
        "Direct os.environ / os.getenv reads of AEAT_* variables outside the allowlist. "
        "Route every read through aeat.core.config.load_settings() instead.\n"
        + "\n".join(f"  - {line}" for line in offences)
    )


def test_allowlisted_paths_actually_exist() -> None:
    """Allowlist must not carry stale entries that bypass the check vacuously."""
    src_root = PROJECT_ROOT / "src" / "aeat"
    missing = [entry for entry in _ALLOWLIST if not (src_root / entry).exists()]
    assert not missing, f"Allowlist entries no longer exist on disk: {missing}"


def test_allowlisted_paths_still_contain_aeat_env_reads() -> None:
    """A file on the allowlist must still carry an AEAT_* os.environ read.

    Without this check the allowlist would degrade into bitrot — if the
    rationale changes and the file is refactored to route through
    Settings, the allowlist entry becomes a free pass for any future
    AEAT_* read added to that file.
    """
    src_root = PROJECT_ROOT / "src" / "aeat"
    stale: list[str] = []
    for entry in _ALLOWLIST:
        path = src_root / entry
        if not path.exists():
            continue  # caught by the other test
        if not _violations_in(path):
            stale.append(entry)
    assert not stale, (
        "Allowlisted files no longer contain any AEAT_* os.environ read — "
        f"remove them from the allowlist: {stale}"
    )
