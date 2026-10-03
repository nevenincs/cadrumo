"""Detect translation-key declarations and references with unsafe names."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from ._ast_key_calls import _translation_call_names
from ._ast_key_dicts import _flow_confirmed_locale_key_dicts
from ._ast_key_policy import _LOCALE_KEY_CONSTANT_SUFFIXES, _UPPER_CONSTANT_NAME_RE
from ._ast_key_syntax import _callee_name, _walk_nodes
from ._ast_scanner import _iter_parseable_python_modules


def tr_constant_naming_violations_in_tree(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, constant_name)`` for a scanner-invisible ``tr(CONSTANT)`` site.

    The regex/AST scanners above resolve a ``tr(...)``/``t(...)`` call site's
    key two ways: a literal string argument (:func:`_dotted_literal_value`), or
    a bare reference to a module-level constant whose OWN NAME ends in
    ``_LOCALE_KEY``/``_LOCALE_KEYS`` (:func:`_extract_locale_constant_keys`,
    keyed on :func:`_declares_locale_key_constant`). A third shape slips past
    both: ``tr(SOME_CONSTANT)`` where ``SOME_CONSTANT`` is plainly a
    module/class-level constant by its ALL-CAPS shape, but its name carries
    none of the required suffixes. Neither resolver finds it — the call site
    is not a literal, and the constant's declaration is invisible to
    :func:`_declares_locale_key_constant` because its name does not match.
    The key becomes entirely invisible to the coverage/parity audit: a typo,
    an orphaned removal, or a missing catalogue entry on that key raises
    nothing, because the scanner never knew the key existed.

    This closes the gap by holding the CALL SITE to the same naming contract
    the DECLARATION side already enforces: any argument that looks like a
    constant reference (``^[A-Z][A-Z0-9_]*$``) must carry a
    :data:`_LOCALE_KEY_CONSTANT_SUFFIXES` suffix. A lowercase or mixed-case
    name (a local variable, loop variable, or function parameter) is a
    genuinely dynamic runtime value, not a static constant, and is out of
    scope for this check — the same distinction the naming-convention rule
    itself draws.

    Scope boundary (deliberate, not an oversight): this check is about the
    KEY EXPRESSION at the Python call site — whether ``tr()``'s argument is a
    literal the scanner can see, or a named constant whose OWN IDENTIFIER
    hides the key from every literal-key scan. It never inspects, resolves,
    or has any opinion about the STRING VALUE a locale catalogue stores under
    that key. This function does not read locale catalogue files.
    """
    tr_names = _translation_call_names(tree)
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        if _callee_name(node.func) not in tr_names:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Name):
            continue
        if not _UPPER_CONSTANT_NAME_RE.match(first.id):
            continue
        if first.id.endswith(_LOCALE_KEY_CONSTANT_SUFFIXES):
            continue
        yield node.lineno, first.id


def find_tr_constant_naming_violations(root: Path) -> list[str]:
    """Walk ``root`` for `.py` files and return formatted naming violations.

    Each returned entry is a ``path:line: 'CONSTANT_NAME'`` string naming a
    ``tr(CONSTANT_NAME)``/``t(CONSTANT_NAME)`` call site whose constant does
    not carry the ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix required for the
    declaration-side scanner to resolve it. See
    :func:`tr_constant_naming_violations_in_tree` for the full rationale.
    """
    violations: list[str] = []
    for module, tree in _iter_parseable_python_modules(root):
        for lineno, name in tr_constant_naming_violations_in_tree(tree):
            violations.append(f"{module}:{lineno}: {name!r}")
    return violations


def dict_constant_naming_violations_in_tree(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, constant_name)`` for an un-suffixed locale-key dict.

    The DECLARATION-side counterpart to
    :func:`tr_constant_naming_violations_in_tree`. That function holds a
    ``tr(CONSTANT)`` CALL SITE to the naming contract the declaration side
    already enforces; this one holds the DECLARATION itself to the same
    contract when it is a dict literal shaped as a locale-key registry AND
    actually read into a translator sink
    (:func:`_flow_confirmed_locale_key_dicts`) but named without the
    required suffix.

    Key DISCOVERY already resolves such a dict's values structurally —
    :func:`_extract_locale_constant_keys` matches the same flow-confirmed
    set, not only by name — so this is a naming HAZARD gate, not a discovery
    feed: an un-suffixed but confirmed dict is exactly the concealed form
    that let a status-token-to-key mapping orphan invisibly in production
    (the constant carried neither the suffix nor a literal ``tr()`` call
    site, so every downstream coverage/parity audit had no signal at all).
    Flagging the declaration surfaces the hazard to a human even though
    discovery no longer depends on the rename.

    Only a MODULE-LEVEL bare ``Name`` target is considered (a direct child
    of the tree's top-level ``body``, matching :func:`ast.Module`'s own
    statement list) — a dict-literal local variable declared and consumed a
    few lines apart inside one function is visibly connected to its own use
    at a glance and is not the "invisible at a distance" hazard class a
    module constant referenced from elsewhere in the file represents; a
    tuple-unpacking or attribute target likewise cannot be a module-level
    locale-key registry by this project's convention (matching
    :func:`_declares_locale_key_constant`).
    """
    flow_confirmed = _flow_confirmed_locale_key_dicts(tree)
    body = getattr(tree, "body", ())
    for node in body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        # A bare annotation carries no value, and a name that is not a
        # confirmed dict looks it up as None too; comparing the two would
        # flag every module-level ``name: T`` declaration.
        if value is None or not isinstance(target, ast.Name) or flow_confirmed.get(target.id) is not value:
            continue
        name = target.id
        if name.endswith(_LOCALE_KEY_CONSTANT_SUFFIXES):
            continue
        line = node.lineno
        if isinstance(line, int):
            yield line, name


def find_dict_constant_naming_violations(root: Path) -> list[str]:
    """Walk ``root`` for `.py` files and return formatted dict-naming violations.

    Each returned entry is a ``path:line: 'CONSTANT_NAME'`` string naming a
    dict-literal locale-key registry whose declared name does not carry the
    ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix. See
    :func:`dict_constant_naming_violations_in_tree` for the full rationale.
    """
    violations: list[str] = []
    for module, tree in _iter_parseable_python_modules(root):
        for lineno, name in dict_constant_naming_violations_in_tree(tree):
            violations.append(f"{module}:{lineno}: {name!r}")
    return violations
