"""Static guard: monkeypatch use classification in production tests.

Walks every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/`` via AST
and classifies ``monkeypatch`` usage.

Classification rules:
- **Legitimate test-isolation fixture**: ``monkeypatch.setenv``,
  ``monkeypatch.delenv``, ``monkeypatch.chdir``, ``monkeypatch.syspath_prepend``,
  ``monkeypatch.setattr("sys.stdout", ...)``, ``monkeypatch.setattr("sys.stderr", ...)``,
  ``monkeypatch.setattr("sys.argv", ...)`` — these patch process-global state
  (env vars, cwd, streams, argv) to isolate test execution from the ambient
  environment.  These are unconditionally allowed and not tracked individually.
- **Documented production-state mutation**: ``monkeypatch.setattr`` targeting
  a production module attribute (e.g. injecting a fake browser factory or
  raising callable to test error branches).  Each site is documented in
  ``_DOCUMENTED_SETATTR_MOCKS`` with a justification.
- **Drift**: any ``monkeypatch.setattr`` / ``monkeypatch.setitem`` /
  ``monkeypatch.delattr`` call that is not in the documented set.

Campaign #72 closed every documented production-state
``monkeypatch.setattr`` site from the source tree:

  - sede/test_browser_errors.py (``browser_session_factory`` kwarg)
  - verify/test_verify.py (``factory`` kwarg)
  - master_key/test_recovery_facade.py (``decoder`` kwarg)
  - cli/_config/test_config.py (real on-disk DB corruption triggers
    SQLAlchemy ``DatabaseError`` — the same catch-all branch the
    prior synthetic ``RuntimeError`` injection exercised)

The drift gate (``test_monkeypatch_setattr_sites_are_documented``)
now enforces an empty baseline: any new ``monkeypatch.setattr``
landing in production tests fails the gate until added with an
explicit justification.

``sys.*`` patches in ``test_stdio.py`` are unconditionally allowed
(process-global isolation).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aeat.core.logging import get_logger

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_logger = get_logger(__name__)

_SRC_AEAT = Path(__file__).resolve().parent
_REPO_ROOT = _SRC_AEAT.parents[1]  # chore-476-restructure-execution
_FIXTURES_DIR = _SRC_AEAT / "tests" / "fixtures"

# Process-global targets that are unconditionally accepted as isolation fixtures.
_ALLOWED_SETATTR_TARGETS_PREFIXES = (
    "sys.stdout",
    "sys.stderr",
    "sys.argv",
    "sys.stdin",
)

# Documented production-state setattr sites.
# Format: (repo-relative path, target description).
#
# Campaign #72 cleared every production-state ``monkeypatch.setattr``
# site from the source tree:
#  - sede/test_browser_errors.py — replaced by ``browser_session_factory`` DI parameter
#  - verify/test_verify.py — replaced by ``factory`` DI parameter on _build_default_browser_session
#  - master_key/test_recovery_facade.py — replaced by ``decoder`` DI parameter on unwrap_recovery_envelope
#  - cli/_config/test_config.py — replaced by real on-disk DB corruption triggering SQLAlchemy DatabaseError
#
# The empty set is the standing baseline — any new entry must justify
# itself, and ``test_monkeypatch_setattr_sites_are_documented`` enforces
# that no undocumented sites can slip in.
_DOCUMENTED_SETATTR_MOCKS: frozenset[tuple[str, str]] = frozenset()

# Mutating monkeypatch verbs to track (beyond setenv/delenv which are always OK).
_MUTATION_VERBS = frozenset({"setattr", "setitem", "delattr"})


def _discover_test_modules() -> list[Path]:
    globs = ("**/test_*.py", "**/_test_*.py")
    collected: set[Path] = set()
    for glob in globs:
        for path in _SRC_AEAT.glob(glob):
            if path.name == "__init__.py":
                continue
            try:
                path.relative_to(_FIXTURES_DIR)
            except ValueError:
                collected.add(path)
    return sorted(collected)


def _target_name_from_args(call_node: ast.Call) -> str | None:
    """Extract the attribute name being patched from a ``monkeypatch.setattr`` call.

    Handles both ``monkeypatch.setattr(module, "name", value)`` (positional)
    and string-path form ``monkeypatch.setattr("pkg.module.name", value)``.
    Returns the final segment of the target name for documentation matching.
    """
    args = call_node.args
    if not args:
        return None
    first = args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        # String-path form: "sys.stdout", "pkg.module.name"
        return first.value.split(".")[-1]
    if len(args) >= 2:
        second = args[1]
        if isinstance(second, ast.Constant) and isinstance(second.value, str):
            return second.value
    return None


def _is_allowed_sys_target(call_node: ast.Call) -> bool:
    """Return True if the setattr target is a process-global sys.* allowed prefix."""
    args = call_node.args
    if not args:
        return False
    first = args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        for prefix in _ALLOWED_SETATTR_TARGETS_PREFIXES:
            if first.value == prefix or first.value.startswith(prefix):
                return True
    return False


def _setattr_sites(path: Path) -> list[tuple[int, str | None]]:
    """Return ``(lineno, target)`` for production-state monkeypatch calls in *path*."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    hits: list[tuple[int, str | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _MUTATION_VERBS:
            continue
        caller = func.value
        if not (isinstance(caller, ast.Name) and caller.id == "monkeypatch"):
            continue
        if func.attr == "setattr" and _is_allowed_sys_target(node):
            continue
        target = _target_name_from_args(node)
        hits.append((node.lineno, target))
    return hits


def test_monkeypatch_setattr_sites_are_documented() -> None:
    """Every non-trivial monkeypatch.setattr must appear in the documented inventory."""
    modules = _discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = str(module_path.relative_to(_REPO_ROOT)).replace("\\", "/")
        for lineno, target in _setattr_sites(module_path):
            # Check if this file+target combination is documented.
            matched = any(
                rel == relative and (tgt == target or target is None)
                for rel, tgt in _DOCUMENTED_SETATTR_MOCKS
            )
            if matched:
                _logger.debug(
                    "documented setattr mock: %s:%d target=%r",
                    relative,
                    lineno,
                    target,
                )
                continue
            violations.append(
                f"{relative}:{lineno}: monkeypatch.setattr(target={target!r})"
            )

    assert not violations, (
        "Undocumented monkeypatch.setattr/setitem/delattr sites found "
        "(add to _DOCUMENTED_SETATTR_MOCKS with justification, or remove):\n"
        + "\n".join(violations)
    )


def test_documented_setattr_mocks_files_exist() -> None:
    """Every documented entry must reference an existing file."""
    for rel_path, _target in _DOCUMENTED_SETATTR_MOCKS:
        path = _REPO_ROOT / rel_path
        assert path.exists(), f"Documented setattr mock references non-existent file: {rel_path}"


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = _discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
