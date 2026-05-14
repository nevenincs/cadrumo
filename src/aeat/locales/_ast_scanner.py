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
    """Find positional and ``message_key=``/``translated_message=`` translation
    keys passed to classes whose name ends with ``Error``/``Exception``, plus
    direct ``tr("dotted.key")``/``t("dotted.key")`` calls anywhere in the
    module, plus dotted-literal defaults for kw-only ``translated_message``/
    ``message_key`` parameters and module-level ALL_CAPS sentinels."""

    findings: set[str] = set()
    # FunctionDef defaults for kw-only translated_message / message_key.
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        kw_defaults = list(zip(node.args.kwonlyargs, node.args.kw_defaults, strict=False))
        for arg, default in kw_defaults:
            if default is None or arg.arg not in {"translated_message", "message_key"}:
                continue
            if (
                isinstance(default, ast.Constant)
                and isinstance(default.value, str)
                and _is_dotted_literal(default.value)
            ):
                findings.add(default.value)
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
        # Direct tr("dotted.key") / t("dotted.key") calls.
        if name in {"tr", "t"} and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and _is_dotted_literal(first.value):
                findings.add(first.value)
            continue
        if not (name.endswith("Error") or name.endswith("Exception")):
            continue
        # Positional first argument as literal dotted string.
        if node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and _is_dotted_literal(first.value):
                findings.add(first.value)
        # ``message_key=`` / ``translated_message=`` keyword.
        for kw in node.keywords:
            if kw.arg not in {"message_key", "translated_message"}:
                continue
            value = kw.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and _is_dotted_literal(value.value):
                findings.add(value.value)
    return findings


_KEY_PREFIX_RE = re.compile(r"^\w+(?:\.\w+)*\.$", re.UNICODE)
"""An f-string literal head qualifies as a key prefix when it ends in a
dot and carries at least one word segment before it (e.g. ``topic.``,
``cli.registry.metrics.``)."""


def _extract_fstring_prefixes(tree: ast.AST) -> set[str]:
    """Walk every f-string literal whose leading segment matches the
    dotted-key shape and emit ``<prefix>.*`` namespace markers.

    Covers both inline call sites (``tr(f"cli.registry.metrics.{x}")``)
    and the assignment form (``key = f"wizard.errors.{reason}"``)
    that the runtime then passes to a downstream call.

    The head literal must end in a dot — that's the explicit
    key-segment marker. ``f"topic.{slug}.title"`` qualifies because
    the head ``topic.`` ends in a dot; ``f"plain text {value}"``
    does not.
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
        if not _KEY_PREFIX_RE.match(head.value):
            continue
        prefix = head.value.rstrip(".")
        findings.add(f"{prefix}.*")
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
    """Walk ``root`` for `.py` files and emit concrete dotted locale keys.

    Concrete keys are literal translation keys passed to error
    constructors (positional first argument or ``message_key=`` kwarg).
    Dynamic namespaces (f-string and concatenation patterns) are
    returned by :func:`scan_namespace_markers` and routed through a
    separate parity check that asserts at least one concrete locale
    entry exists under each declared namespace prefix.
    """

    findings: set[str] = set()
    for module in root.rglob("*.py"):
        if module.name in {"test_parity.py", "manager.py", "_ast_scanner.py"}:
            continue
        if module.name.startswith("test_") or module.name.startswith("_test_") or "/tests/" in module.as_posix():
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
    return findings


def scan_namespace_markers(root: Path) -> set[str]:
    """Walk ``root`` for `.py` files and emit dynamic-namespace markers.

    A namespace marker is a ``<prefix>.*`` string identifying a
    family of keys whose tail is computed at runtime (f-string
    interpolation or string concatenation). Each marker passes the
    parity check when at least one concrete locale key starts with
    its prefix.
    """

    findings: set[str] = set()
    for module in root.rglob("*.py"):
        if module.name in {"test_parity.py", "manager.py", "_ast_scanner.py"}:
            continue
        if module.name.startswith("test_") or module.name.startswith("_test_") or "/tests/" in module.as_posix():
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
        findings.update(_extract_fstring_prefixes(tree))
        findings.update(_extract_concat_prefixes(tree))
    return findings


__all__ = ["scan_namespace_markers", "scan_source_tree"]
