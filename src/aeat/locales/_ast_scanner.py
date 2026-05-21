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
    """Find translation keys declared anywhere in the module.

    Collects positional translation keys passed to classes whose name
    ends with ``Error``/``Exception``, ``message_key=``/
    ``translated_message=`` dotted-literal kwargs on any callee
    (exception constructors, ``ErrorCode`` registry rows,
    ``WizardCheckFinding`` verifier findings), direct
    ``tr("dotted.key")``/``t("dotted.key")`` calls, ``build_entry``
    portal-catalogue keys, and dotted-literal defaults for kw-only
    ``translated_message``/``message_key`` parameters."""

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
        value = _dotted_literal_value(default)
        if value is not None:
            findings.add(value)


def _collect_call_site_keys(node: ast.Call, findings: set[str]) -> None:
    """Pick up ``tr(...)`` / ``t(...)`` direct calls, ``*Error``/``*Exception``
    constructor translation keys, ``build_entry(...)`` portal-catalogue
    translation keys, and ``message_key=`` / ``translated_message=``
    dotted-literal kwargs on any callee.

    The translation-key kwargs (``message_key=`` / ``translated_message=``)
    are collected callee-agnostically: any call that names one of those
    kwargs with a dotted-literal value declares a live operator-facing
    translation key. This covers the ``ErrorCode(message_key=...)``
    registry rows and ``WizardCheckFinding(message_key=...)`` verifier
    findings, neither of which carries an ``*Error`` callee name."""

    name = _callee_name(node.func)
    if name is None:
        return
    _collect_translation_key_kwargs(node, findings)
    if name in {"tr", "t"}:
        _add_first_dotted_arg(node, findings)
        return
    if name == "build_entry":
        _collect_build_entry_keys(node, findings)
        return
    if name.endswith("Error") or name.endswith("Exception"):
        _add_first_dotted_arg(node, findings)


def _collect_translation_key_kwargs(node: ast.Call, findings: set[str]) -> None:
    """Collect ``message_key=`` / ``translated_message=`` dotted-literal kwargs.

    The kwarg name alone identifies a translation key, so this is
    callee-agnostic: it covers exception constructors,
    ``super().__init__(...)`` delegations, ``ErrorCode(...)`` registry
    declarations, and ``WizardCheckFinding(...)`` verifier findings
    alike."""

    for kw in node.keywords:
        if kw.arg not in {"message_key", "translated_message"}:
            continue
        value = _dotted_literal_value(kw.value)
        if value is not None:
            findings.add(value)


def _collect_build_entry_keys(node: ast.Call, findings: set[str]) -> None:
    """Pick up portal-catalogue translation keys passed to ``build_entry``.

    ``aeat.domain.portals._entries`` modules construct each portal entry
    through :func:`build_entry`, passing the multilingual ``label`` and
    ``purpose`` keys (and an optional ``notes`` tuple of keys) as keyword
    arguments rather than through a ``tr(...)`` call. The regex scanner
    and the ``tr``/``t`` call-site path both miss them, so resolve those
    keyword arguments explicitly here."""

    for kw in node.keywords:
        if kw.arg in {"label", "purpose"}:
            value = _dotted_literal_value(kw.value)
            if value is not None:
                findings.add(value)
        elif kw.arg == "notes" and isinstance(kw.value, ast.Tuple | ast.List):
            for element in kw.value.elts:
                element_value = _dotted_literal_value(element)
                if element_value is not None:
                    findings.add(element_value)


def _callee_name(callee: ast.expr) -> str | None:
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def _dotted_literal_value(node: ast.expr | None) -> str | None:
    """Return the dotted-literal key string ``node`` carries, else ``None``.

    Returns the resolved ``str`` directly so callers obtain a typed
    value without a separate ``node.value`` access — ``ast.Constant.value``
    is a broad ``str | bytes | int | ...`` union the type system cannot
    narrow through a predicate. The runtime check is unchanged: the node
    must be a Constant, its value must be a string, and the string must
    match the dotted-literal shape.
    """

    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _is_dotted_literal(node.value)
    ):
        return node.value
    return None


def _add_first_dotted_arg(node: ast.Call, findings: set[str]) -> None:
    if not node.args:
        return
    value = _dotted_literal_value(node.args[0])
    if value is not None:
        findings.add(value)


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
