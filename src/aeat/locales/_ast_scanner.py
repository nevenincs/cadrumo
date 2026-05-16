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
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            _collect_kwonly_default_keys(node, findings)
        elif isinstance(node, ast.Call):
            _collect_call_site_keys(node, findings)
    return findings


def _collect_kwonly_default_keys(node: ast.FunctionDef, findings: set[str]) -> None:
    """Pick up dotted-literal defaults for ``translated_message`` / ``message_key`` kwonly args."""

    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=False):
        if default is None or arg.arg not in {"translated_message", "message_key"}:
            continue
        if _is_dotted_literal_constant(default):
            findings.add(default.value)  # type: ignore[attr-defined]


def _collect_call_site_keys(node: ast.Call, findings: set[str]) -> None:
    """Pick up ``tr(...)`` / ``t(...)`` direct calls and ``*Error``/``*Exception``
    constructor positional / keyword translation keys."""

    name = _callee_name(node.func)
    if name is None:
        return
    if name in {"tr", "t"}:
        _add_first_dotted_arg(node, findings)
        return
    if not (name.endswith("Error") or name.endswith("Exception")):
        return
    _add_first_dotted_arg(node, findings)
    for kw in node.keywords:
        if kw.arg in {"message_key", "translated_message"} and _is_dotted_literal_constant(kw.value):
            findings.add(kw.value.value)  # type: ignore[attr-defined]


def _callee_name(callee: ast.expr) -> str | None:
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def _is_dotted_literal_constant(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _is_dotted_literal(node.value)
    )


def _add_first_dotted_arg(node: ast.Call, findings: set[str]) -> None:
    if not node.args:
        return
    first = node.args[0]
    if _is_dotted_literal_constant(first):
        findings.add(first.value)  # type: ignore[attr-defined]


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
        if _callee_name(node.func) not in {"tr", "t"}:
            continue
        for argument in node.args:
            prefix = _concat_prefix_marker(argument)
            if prefix is not None:
                findings.add(prefix)
    return findings


def _concat_prefix_marker(argument: ast.expr) -> str | None:
    """Return the ``<prefix>.*`` marker for a ``"<literal>" + <expr>`` arg, or None."""
    if not isinstance(argument, ast.BinOp) or not isinstance(argument.op, ast.Add):
        return None
    left = argument.left
    if not isinstance(left, ast.Constant) or not isinstance(left.value, str):
        return None
    literal = left.value.rstrip(".")
    if not _is_dotted_literal(literal):
        return None
    if len(literal.split(".")) < _KEY_PATTERN_PREFIX_MIN_PARTS:
        return None
    return f"{literal}.*"


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
