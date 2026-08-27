"""Enforce: AEAT-prefixed config READS must flow through ``Settings``.

The architectural mandate is that every AEAT-prefixed environment
variable be read through :class:`~core.config.Settings` (and its
:func:`~core.config.load_settings` accessor), not through direct
``os.environ.get`` / ``os.getenv`` / ``os.environ[...]`` access.

Direct reads bypass:
  - Pydantic-settings validation (type coercion, ``Field`` constraints).
  - The ``.env`` + ``os.environ`` merge order Pydantic-settings enforces.
  - The :func:`override_settings` context manager used by tests.

This test walks every ``.py`` file under ``src/cadrumo/`` (excluding the
test module itself), parses it into an AST, and reports any expression
that reads ``os.environ`` / ``os.getenv`` with an ``"AEAT_*"`` literal
key. The check is purely structural: a string literal inside a
docstring is *not* a function call, so the AST walk ignores it.

A short allowlist captures the documented irreducible exceptions —
subprocess-IPC WRITE sites where ``Settings`` has no write API. Each
allowlisted line is annotated in-source with a rationale comment.

See Also:
    :func:`~core.config.load_settings`
        Canonical process settings accessor that owns AEAT-prefixed
        environment reads.
    :func:`~core.config.override_settings`
        Test override seam whose behavior direct environment reads would
        bypass.
    :func:`~tests._inventory.production_ast_items`
        Shared production AST inventory scanned by this structural guard.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from ...tests import SRC_CADRUMO, aeat_relative, ast_for_path, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# Files (relative to src/cadrumo/) where direct os.environ access to an
# AEAT-prefixed variable is the only legitimate option. Each entry must
# carry its rationale inline in the source — when reviewing this list,
# verify the rationale matches "no Settings write API exists for this".
_ALLOWLIST: frozenset[str] = frozenset[str]()

_AEAT_KEY_PATTERN: re.Pattern[str] = re.compile(r"^AEAT_[A-Z0-9_]+$")


def _candidate_modules(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    return production_ast_items(source_tree_ast)


def _aeat_key_from_arg(node: ast.expr, constants: dict[str, str]) -> str | None:
    """Return the AEAT_* key string if ``node`` is a literal or a name-bound literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and _AEAT_KEY_PATTERN.fullmatch(node.value):
        return node.value
    if isinstance(node, ast.Name):
        resolved = constants.get(node.id)
        if resolved is not None and _AEAT_KEY_PATTERN.fullmatch(resolved):
            return resolved
    return None


def _collect_aeat_string_bindings(tree: ast.Module) -> dict[str, str]:
    """Map every NAME (module-level OR function-local) bound to an AEAT_* literal.

    Walks the whole tree (not just module-top) so locally-bound aliases like
    ``def f():\\n    key = "AEAT_FOO"\\n    return os.environ[key]`` are
    resolvable. The map is name -> last-bound literal; assignments later in
    source order win, which matches Python's actual binding semantics
    closely enough for the structural check this scanner performs.
    """
    constants: dict[str, str] = {}
    for node in ast.walk(tree):
        for name, value in _aeat_string_binding_pairs(node):
            constants[name] = value
    return constants


def _aeat_string_binding_pairs(node: ast.AST) -> tuple[tuple[str, str], ...]:
    """Yield every ``(name, AEAT_* literal)`` pair this AST node binds.

    ``Assign`` nodes contribute one pair per ``ast.Name`` target;
    ``AnnAssign`` nodes contribute zero or one. Any other node, any
    non-constant RHS, any non-AEAT-prefixed literal, and any
    non-string value short-circuit to the empty tuple — keeping the
    scanner's whole-tree walk uniform regardless of which node shape
    it encounters.
    """
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
        value = node.value.value
        if not (isinstance(value, str) and _AEAT_KEY_PATTERN.fullmatch(value)):
            return ()
        return tuple((target.id, value) for target in node.targets if isinstance(target, ast.Name))
    if isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.value, ast.Constant):
        value = node.value.value
        if isinstance(value, str) and _AEAT_KEY_PATTERN.fullmatch(value) and isinstance(node.target, ast.Name):
            return ((node.target.id, value),)
    return ()


def _collect_environ_aliases(tree: ast.Module) -> set[str]:
    """Find names bound to ``os.environ`` directly so aliased access is caught.

    Handles two patterns:
      - ``environ = os.environ`` (regular assignment)
      - ``from os import environ`` (import-from)

    Returns the set of NAME identifiers that — anywhere in the module —
    refer to ``os.environ``. The scanner treats reads on these aliases
    the same as direct ``os.environ`` reads. False-positives are
    acceptable here; missed bypasses are not.
    """
    aliases: set[str] = {"environ"}  # any "environ" name is suspect; the AEAT_* key gate filters noise
    for node in ast.walk(tree):
        aliases.update(_environ_alias_names(node))
    return aliases


def _environ_alias_names(node: ast.AST) -> tuple[str, ...]:
    """Return every NAME ``node`` binds to ``os.environ`` (or rebinds via ``from os import environ``).

    Two patterns yield aliases:
      - ``ast.Assign`` whose RHS resolves to ``os.environ`` — each
        ``ast.Name`` target on the LHS becomes an alias.
      - ``ast.ImportFrom`` of module ``os`` where the ``environ``
        name is imported (with or without an ``as`` rename).

    Any other node contributes nothing.
    """
    if isinstance(node, ast.Assign) and _is_os_environ(node.value):
        return tuple(target.id for target in node.targets if isinstance(target, ast.Name))
    if isinstance(node, ast.ImportFrom) and node.module == "os":
        return tuple(alias.asname or "environ" for alias in node.names if alias.name == "environ")
    return ()


def _is_string_with_aeat_format_template(node: ast.expr) -> bool:
    """Return True if a JoinedStr / Constant starts with the AEAT_ prefix.

    f-strings with dynamic suffixes are detectable when the static head
    is ``"AEAT_..."`` — those still count as AEAT-prefixed reads even
    though the full key is computed at runtime. Pure-dynamic keys with
    no static prefix escape this check (acceptable: such constructs are
    rare and audit-conspicuous).
    """
    if isinstance(node, ast.JoinedStr):
        for value in node.values:
            return isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.startswith("AEAT_")
    return False


def _violations_in(path: Path, tree: ast.AST) -> list[tuple[int, str, str]]:
    """Return (lineno, key, snippet) tuples for AEAT-prefixed env reads."""
    assert isinstance(tree, ast.Module), f"Expected a module AST for {path}, got {type(tree).__name__}"
    constants = _collect_aeat_string_bindings(tree)
    aliases = _collect_environ_aliases(tree)
    violations: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            _scan_subscript_environ_read(node, constants, aliases, violations)
        elif isinstance(node, ast.Call):
            _scan_call_environ_read(node, constants, aliases, violations)
    return violations


def _scan_subscript_environ_read(
    node: ast.Subscript,
    constants: dict[str, str],
    aliases: set[str],
    violations: list[tuple[int, str, str]],
) -> None:
    """``ENVIRON[KEY]`` form — including aliased environ names."""
    target = node.value
    if not (_is_os_environ(target) or (isinstance(target, ast.Name) and target.id in aliases)):
        return
    key = _aeat_key_from_arg(node.slice, constants)
    if key is not None:
        violations.append((node.lineno, key, f"{_target_label(target)}[...]"))
    elif _is_string_with_aeat_format_template(node.slice):
        violations.append((node.lineno, "AEAT_<dynamic>", f"{_target_label(target)}[f-string]"))


def _scan_call_environ_read(
    node: ast.Call,
    constants: dict[str, str],
    aliases: set[str],
    violations: list[tuple[int, str, str]],
) -> None:
    """``ENVIRON.get/pop/setdefault(...)`` and ``os.getenv(...)`` / bare ``getenv(...)`` calls."""
    if not node.args:
        return
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in {"get", "pop", "setdefault"}:
        target = func.value
        if _is_os_environ(target) or (isinstance(target, ast.Name) and target.id in aliases):
            _record_call_violation(node, constants, violations, label=f"{_target_label(target)}.{func.attr}")
        return
    if isinstance(func, ast.Attribute) and func.attr == "getenv":
        if isinstance(func.value, ast.Name) and func.value.id == "os":
            _record_call_violation(node, constants, violations, label="os.getenv")
        return
    if isinstance(func, ast.Name) and func.id == "getenv":
        # from os import getenv -> bare getenv("AEAT_FOO")
        key = _aeat_key_from_arg(node.args[0], constants)
        if key is not None:
            violations.append((node.lineno, key, "getenv(...)"))


def _record_call_violation(
    node: ast.Call,
    constants: dict[str, str],
    violations: list[tuple[int, str, str]],
    *,
    label: str,
) -> None:
    key = _aeat_key_from_arg(node.args[0], constants)
    if key is not None:
        violations.append((node.lineno, key, f"{label}(...)"))
    elif _is_string_with_aeat_format_template(node.args[0]):
        violations.append((node.lineno, "AEAT_<dynamic>", f"{label}(f-string)"))


def _is_os_environ(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _target_label(node: ast.expr) -> str:
    if _is_os_environ(node):
        return "os.environ"
    if isinstance(node, ast.Name):
        return node.id
    return "<environ-alias>"


def test_no_direct_aeat_env_reads_outside_allowlist(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every AEAT_* env read must flow through Settings, except allowlisted IPC writes."""
    offences: list[str] = []
    for path, tree in _candidate_modules(source_tree_ast):
        rel = aeat_relative(path)
        violations = _violations_in(path, tree)
        if not violations:
            continue
        if rel in _ALLOWLIST:
            continue  # documented IPC-write exception
        for lineno, key, snippet in violations:
            offences.append(f"{rel}:{lineno}  reads {key!r} via {snippet}")
    assert not offences, (
        "Direct os.environ / os.getenv reads of AEAT_* variables outside the allowlist. "
        "Route every read through cadrumo.core.config.load_settings() instead.\n"
        + "\n".join(f"  - {line}" for line in offences)
    )


def test_allowlisted_paths_actually_exist() -> None:
    """Allowlist must not carry stale entries that bypass the check vacuously."""
    missing = [entry for entry in _ALLOWLIST if not (SRC_CADRUMO / entry).exists()]
    assert not missing, f"Allowlist entries no longer exist on disk: {missing}"


def test_allowlisted_paths_still_contain_aeat_env_reads(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A file on the allowlist must still carry an AEAT_* os.environ read.

    Without this check the allowlist would degrade into bitrot — if the
    rationale changes and the file is refactored to route through
    Settings, the allowlist entry becomes a free pass for any future
    AEAT_* read added to that file.
    """
    stale: list[str] = []
    for entry in _ALLOWLIST:
        path = SRC_CADRUMO / entry
        if not path.exists():
            continue  # caught by the other test
        tree = ast_for_path(path, source_tree_ast)
        if tree is None or not _violations_in(path, tree):
            stale.append(entry)
    assert not stale, (
        f"Allowlisted files no longer contain any AEAT_* os.environ read — remove them from the allowlist: {stale}"
    )
