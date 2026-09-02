"""Inventory test: no production CadrumoError subclass raise may use tr() as positional arg.

Rule
----
For every ``raise SomeError(tr(...))`` pattern in a non-test production module
under ``src/cadrumo/``, the first positional argument to the error constructor
must NOT be a ``tr()`` call result.

The canonical form is::

    raise SomeError(
        translated_message="some.locale.key",
        context={...},
    )

NOT::

    raise SomeError(tr("some.locale.key"))   # WRONG — eager resolution

Rationale
---------
Passing ``tr()`` as the positional ``message`` argument resolves the locale
string eagerly at raise time using the ambient output language, rather than
deferring resolution to the CLI render layer where the operator's chosen
``--output-language`` is active.  The ``translated_message`` keyword preserves
deferred, per-render resolution across all output languages.

Exclusions
----------
- ``test_*.py`` files: tests may call tr() freely.
- Lines where ``tr(`` appears only inside a Python string literal are excluded.
- Calls where ``tr(...)`` is passed to Typer/Click (``help=``, ``typer.*``,
  ``click.*``) or to non-CadrumoError standard-library exceptions (e.g.
  ``typer.BadParameter``, ``ValueError``) are out-of-scope; the rule targets
  CadrumoError subclass constructors only.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from .inventory import production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Exception class names that are NOT CadrumoError subclasses and therefore
# do not need the translated_message pattern (Typer/Click/stdlib classes).
_NON_AEAT_EXCEPTION_CLASSES = frozenset(
    {
        "BadParameter",
        "ValueError",
        "TypeError",
        "KeyError",
        "RuntimeError",
        "AssertionError",
        "NotImplementedError",
        "ClickException",
        "Exit",
        "Abort",
    },
)

# Factory function names that return non-CadrumoError exceptions (e.g. typer.BadParameter
# wrappers). Raising ``_bad(tr(...))`` is not the CadrumoError anti-pattern because
# ``_bad`` wraps ``typer.BadParameter``, not an CadrumoError subclass.
_NON_AEAT_FACTORY_FUNCTIONS = frozenset(
    {
        "_bad",  # cli/_common.py factory for typer.BadParameter
        "google_refusal",  # cli/config/_google.py factory for CliRefusedBoundaryError — has its own correct pattern
    },
)


def _is_tr_call(node: ast.expr) -> bool:
    """Return True if *node* is a bare ``tr(...)`` or ``Translatable(...)`` call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in ("tr", "Translatable"):
        return True
    if isinstance(func, ast.Attribute) and func.attr in ("tr", "Translatable"):
        return True
    return False


def _raise_positional_tr_violations(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield (lineno, description) for raise statements where the first positional
    arg to an exception constructor is a tr() call."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        exc = node.exc
        if exc is None:
            continue
        # ``raise SomeError(...)``
        if not isinstance(exc, ast.Call):
            continue
        # Identify the class name being raised.
        func = exc.func
        if isinstance(func, ast.Name):
            class_name = func.id
        elif isinstance(func, ast.Attribute):
            class_name = func.attr
        else:
            continue
        # Skip non-CadrumoError exception classes and factory functions that wrap
        # non-CadrumoError types (e.g. _bad() returns typer.BadParameter).
        if class_name in _NON_AEAT_EXCEPTION_CLASSES or class_name in _NON_AEAT_FACTORY_FUNCTIONS:
            continue
        # Check: does the call have at least one positional arg that is tr()?
        args = exc.args
        if args and _is_tr_call(args[0]):
            yield exc.lineno, f"raise {class_name}(tr(...))"


def _collect_violations(
    source_tree_ast: Mapping[Path, ast.AST] | None = None,
) -> list[str]:
    """Walk every production module under ``src/cadrumo/`` and collect violations.

    The invariant is applied unconditionally: every non-test module that
    raises an :class:`CadrumoError` subclass must use the
    ``translated_message=`` keyword rather than passing ``tr(...)`` as
    the positional ``message`` argument.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file. When omitted, fall back to walk-and-parse so
    the helper's no-arg signature stays compatible with importlib
    callers.
    """
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        for lineno, description in _raise_positional_tr_violations(tree):
            violations.append(f"{repo_relative(path)}:{lineno} — {description}")
    return violations


def test_no_cadrumo_error_raise_with_positional_tr(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every production module must have zero raise-with-positional-tr() violations.

    The invariant applies unconditionally to every non-test module under
    ``src/cadrumo/``.  Passing ``tr(...)`` as the positional ``message``
    argument resolves the locale string eagerly at raise time using the
    ambient output language, rather than deferring resolution to the CLI
    render layer where the operator's chosen ``--output-language`` is
    active.

    The canonical pattern is::

        raise SomeError(translated_message="key", context={...})

    NOT::

        raise SomeError(tr("key"))   # WRONG — eager resolution

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations = _collect_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} raise(s) pass tr() as a positional CadrumoError arg:\n"
            f"  {joined}\n\n"
            "Convert to: raise SomeError(translated_message='key', context={{...}})",
        )
