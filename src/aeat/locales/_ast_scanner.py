"""AST-based locale-key discovery for sites the regex scanner misses.

The regex scanner under :class:`aeat.locales.manager.LocaleManager`
captures `tr("…")` and `t("…")` literal call sites. Two surfaces slip
past that contract:

* Programmatic errors that pass a translation key to an exception
  constructor through a ``message_key=`` kwarg rather than a
  :func:`tr` call (for example
  ``WizardValidationError("wizard.errors.select_unknown")``).
* f-string call sites whose JoinedStr starts with a literal
  dot-notation prefix matching the translation-key shape (for example
  ``tr(f"cli.registry.metrics.{key}")``) — the regex sees the prefix
  but cannot tell what follows. The scanner emits a
  ``<prefix>.*`` marker that the parity check treats as a namespace
  declaration rather than a single key.

Both findings feed into
:meth:`aeat.locales.manager.LocaleManager.get_codebase_keys` so the
parity audit covers programmatic emissions and dynamic namespaces.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from aeat.core.logging import get_logger

_log = get_logger(__name__)

_KEY_PATTERN_PREFIX_MIN_PARTS = 2
"""A discovered f-string key prefix must carry at least two dotted
segments before the dynamic tail (e.g. ``cli.registry.metrics``)."""

_KEY_LITERAL_RE = re.compile(r"^\w+(?:\.\w+)+$", re.UNICODE)
"""A literal that qualifies as a translation-key prefix: word chars and
dots only, at least two dotted segments, no whitespace, slashes,
operators, or punctuation."""


def _is_dotted_literal(value: str) -> bool:
    """Return True when ``value`` matches the dot-notation key shape."""

    return bool(_KEY_LITERAL_RE.match(value))


def _extract_error_constructor_keys(tree: ast.AST) -> set[str]:
    """Find positional and ``message_key=`` translation keys passed to
    classes whose name ends with ``Error`` or ``Exception``."""

    findings: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name: str | None = None
        if isinstance(callee, ast.Name):
            name = callee.id
        elif isinstance(callee, ast.Attribute):
            name = callee.attr
        if name is None:
            continue
        if not (name.endswith("Error") or name.endswith("Exception")):
            continue
        # Positional first argument as literal dotted string.
        if node.args:
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and _is_dotted_literal(first.value)
            ):
                findings.add(first.value)
        # ``message_key=`` keyword.
        for kw in node.keywords:
            if kw.arg != "message_key":
                continue
            value = kw.value
            if (
                isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and _is_dotted_literal(value.value)
            ):
                findings.add(value.value)
    return findings


def _extract_fstring_prefixes(tree: ast.AST) -> set[str]:
    """Walk every f-string literal whose leading segment matches the
    dotted-key shape and emit ``<prefix>.*`` namespace markers.

    Covers both inline call sites (``tr(f"cli.registry.metrics.{x}")``)
    and the assignment form (``key = f"wizard.errors.{reason}"``)
    that the runtime then passes to a downstream call.
    """

    findings: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        if not node.values:
            continue
        head = node.values[0]
        if not isinstance(head, ast.Constant) or not isinstance(head.value, str):
            continue
        literal = head.value.rstrip(".")
        if not _is_dotted_literal(literal):
            continue
        if len(literal.split(".")) < _KEY_PATTERN_PREFIX_MIN_PARTS:
            continue
        findings.add(f"{literal}.*")
    return findings


def _extract_concat_prefixes(tree: ast.AST) -> set[str]:
    """Walk ``tr(<literal> + <expr>)`` and ``t(<literal> + <expr>)``
    concatenations and emit the literal-prefix ``.*`` marker.

    Matches the dynamic-key pattern ``tr("cli.registry.metrics." + key)``
    where the literal carries the registered key prefix.
    """

    findings: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name: str | None = None
        if isinstance(callee, ast.Name):
            name = callee.id
        elif isinstance(callee, ast.Attribute):
            name = callee.attr
        if name not in {"tr", "t"}:
            continue
        for argument in node.args:
            if not isinstance(argument, ast.BinOp) or not isinstance(argument.op, ast.Add):
                continue
            left = argument.left
            if not isinstance(left, ast.Constant) or not isinstance(left.value, str):
                continue
            literal = left.value.rstrip(".")
            if not _is_dotted_literal(literal):
                continue
            if len(literal.split(".")) < _KEY_PATTERN_PREFIX_MIN_PARTS:
                continue
            findings.add(f"{literal}.*")
    return findings


def scan_source_tree(root: Path) -> set[str]:
    """Walk ``root`` for `.py` files and emit discovered locale keys."""

    findings: set[str] = set()
    for module in root.rglob("*.py"):
        if module.name in {"test_parity.py", "manager.py", "_ast_scanner.py"}:
            continue
        try:
            source = module.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            _log.debug("locale ast scan: skipping %s (%s)", module, exc)
            continue
        try:
            tree = ast.parse(source, filename=str(module))
        except SyntaxError as exc:
            _log.debug("locale ast scan: parse failure %s (%s)", module, exc)
            continue
        findings.update(_extract_error_constructor_keys(tree))
        findings.update(_extract_fstring_prefixes(tree))
        findings.update(_extract_concat_prefixes(tree))
    return findings


__all__ = ["scan_source_tree"]
