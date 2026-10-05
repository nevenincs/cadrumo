"""Confirm locale-shaped mapping declarations reach translator sinks."""

from __future__ import annotations

import ast

from ._ast_key_calls import _call_site_key_argument_exprs, _translation_call_names
from ._ast_key_syntax import _dict_access_source, _is_locale_key_dict_literal, _walk_nodes


def _shape_candidate_locale_key_dicts(tree: ast.AST) -> dict[str, ast.expr]:
    """Return every ``Name -> dict-literal-value`` pair shaped as a locale-key registry.

    Shape alone (:func:`_is_locale_key_dict_literal`) is necessary but not
    sufficient: many dicts in this codebase map one dotted-namespaced
    identifier to another WITHOUT either side being a translation key (a
    casilla-to-casilla reconciliation map, a ``Notice.code`` machine-routing
    table). :func:`_flow_confirmed_locale_key_dicts` narrows this candidate
    set down to the ones actually read into a recognized locale-key sink.
    """
    candidates: dict[str, ast.expr] = {}
    for node in _walk_nodes(tree):
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and value is not None and _is_locale_key_dict_literal(value):
            candidates[target.id] = value
    return candidates


def _locale_key_dict_names_read_into_a_sink(
    tree: ast.AST, candidate_names: frozenset[str], wrappers: frozenset[str] = frozenset()
) -> frozenset[str]:
    """Return the candidate dict names actually read into a recognized locale-key sink.

    Tracks the ``local = SOME_DICT.get(...)`` / ``local = SOME_DICT[...]``
    indirection one hop per function/method body — the exact shape the
    concealed incident used (``setup_state_key =
    _PROFILE_SETUP_STATE_KEYS.get(...)``; ``tr(setup_state_key)``) — plus the
    direct ``tr(SOME_DICT.get(...))``/``tr(SOME_DICT[...])`` shape. This is
    what tells a dict that is genuinely a locale-key source apart from a
    same-shaped lookup table for an unrelated domain that never reaches a
    translation-key sink: a casilla-to-casilla reconciliation map or a
    ``Notice.code`` machine-routing table both use the identical
    dict-of-dotted-strings SHAPE without ever being read by ``tr()``.

    Each function/method body is walked in two passes so confirmation never
    depends on AST traversal order (``ast.walk`` is breadth-first, not
    textual order): the first pass fully populates the local-to-dict map,
    the second checks every call against it.
    """
    tr_names = _translation_call_names(tree) | wrappers
    confirmed: set[str] = set()
    for func in _walk_nodes(tree):
        if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        local_to_dict: dict[str, str] = {}
        for node in ast.walk(func):
            bind_local_locale_dict_access(node, candidate_names, local_to_dict)
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            for argument in _call_site_key_argument_exprs(node, tr_names):
                direct = _dict_access_source(argument)
                if direct in candidate_names:
                    confirmed.add(direct)
                elif isinstance(argument, ast.Name) and argument.id in local_to_dict:
                    confirmed.add(local_to_dict[argument.id])
    return frozenset(confirmed)


def _flow_confirmed_locale_key_dicts(tree: ast.AST, wrappers: frozenset[str] = frozenset()) -> dict[str, ast.expr]:
    """Return shape-candidate locale-key dicts actually read into a translator sink.

    Combines :func:`_shape_candidate_locale_key_dicts` (structural
    candidacy) with :func:`_locale_key_dict_names_read_into_a_sink` (real
    usage confirmation) so neither signal alone decides: shape alone
    over-fires on same-shaped unrelated lookup tables, and usage alone
    cannot be checked without first knowing which names are dict-shaped
    candidates.
    """
    candidates = _shape_candidate_locale_key_dicts(tree)
    confirmed_names = _locale_key_dict_names_read_into_a_sink(tree, frozenset(candidates), wrappers)
    return {name: value for name, value in candidates.items() if name in confirmed_names}


def bind_local_locale_dict_access(
    node: ast.AST, candidate_names: frozenset[str], local_to_dict: dict[str, str]
) -> None:
    """Bind local locale dict access."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        source = _dict_access_source(node.value)
        if source in candidate_names:
            local_to_dict[node.targets[0].id] = source
