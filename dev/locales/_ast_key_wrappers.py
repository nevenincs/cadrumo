"""Resolve cross-module translator wrappers, guards, and key parameters."""

from __future__ import annotations

import ast
from pathlib import Path

from ._ast_key_calls import _call_site_key_argument_exprs, _translation_call_names
from ._ast_key_policy import _TRANSLATION_KEY_KWARGS
from ._ast_key_syntax import _collect_dotted_literals, _walk_nodes


def _translation_wrapper_names(modules: list[tuple[Path, ast.Module]]) -> frozenset[str]:
    """Return functions that forward their own first parameter to a translator.

    Every TUI surface routes its copy through one boundary helper --
    ``def aeat_sync_copy(key, **values): return tr(key, **values)`` -- so the
    call sites read ``aeat_sync_copy("tui.aeat_sync.column.area")`` and never
    ``tr(...)``. The scanner resolved aliased IMPORTS of ``tr`` but not a
    wrapper defined as a function, so every key reaching the catalogue through
    one of these boundaries read as an orphan.

    The shape is deliberately tight: the function must pass its OWN first
    parameter as the first positional argument to something already known to
    translate. A helper that merely calls ``tr`` on some other value is not a
    key channel and does not qualify.

    Resolved to a fixpoint across the whole tree, because a wrapper may be
    imported from another module and may itself wrap a wrapper.
    """
    definitions: list[tuple[str, str, ast.AST]] = []
    for _path, tree in modules:
        for node in _walk_nodes(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            parameters = [*node.args.posonlyargs, *node.args.args]
            if parameters and parameters[0].arg in {"self", "cls"}:
                parameters = parameters[1:]
            if parameters:
                definitions.append((node.name, parameters[0].arg, node))

    known = {"tr", "t"}
    while True:
        discovered = set()
        for name, first, node in definitions:
            discover_translator_wrapper(name, first, node, known, discovered)
        if not discovered:
            return frozenset[str](known - {"tr", "t"})
        known |= discovered


def _translated_value_names(
    modules: list[tuple[Path, ast.Module]], wrappers: frozenset[str] = frozenset()
) -> frozenset[str]:
    """Return the names whose value is passed to a translator somewhere in the tree.

    ``ledger_copy(choice.source_label_key)`` proves that whatever
    ``source_label_key`` holds is copy. The proof lives in the SCREEN, while
    the values it can hold are declared in the model module beside it, so this
    is collected across the whole tree rather than per module.

    A name, not a value: this says nothing about what any particular
    ``source_label_key`` contains, only that a value reaching a translator is
    what that name is for.

    The sink set carries the boundary wrappers, because every screen renders
    through one. Reading only ``tr`` found nothing here at all -- the third
    time in this campaign that following the project's own boundary convention
    is what made a key invisible.
    """
    names: set[str] = set()
    for _module, tree in modules:
        tr_names = _translation_call_names(tree) | wrappers
        for node in _walk_nodes(tree):
            if not isinstance(node, ast.Call):
                continue
            for argument in _call_site_key_argument_exprs(node, tr_names):
                if isinstance(argument, ast.Attribute):
                    names.add(argument.attr)
                elif isinstance(argument, ast.Name):
                    names.add(argument.id)
    return frozenset(names)


def _membership_guard_keys(tree: ast.AST, translated_names: frozenset[str]) -> set[str]:
    """Return dotted literals a guard admits for a name that is then translated.

    A boundary that will not render an arbitrary string states the keys it
    accepts and refuses everything else::

        _SAFE_SOURCE_KEYS = frozenset({"tui.ledger.import.source.prepared"})
        ...
        if source_label_key not in _SAFE_SOURCE_KEYS:
            raise ...

    The admitted value is later rendered by the screen as
    ``ledger_copy(choice.source_label_key)``. Nothing in the module that
    DECLARES the keys translates them, and nothing in the module that
    translates them mentions a literal, so each half looked inert on its own.

    The link is a membership test, not a naming convention: the guarded name
    must be one this tree actually passes to a translator, and the container
    must be a collection of dotted literals. A guard over some other name --
    an allow-list of choice ids, say -- proves nothing about copy and is not
    admitted.
    """
    if not translated_names:
        return set()
    containers: dict[str, set[str]] = {}
    for node in _walk_nodes(tree):
        collect_guard_literal_container(node, containers)

    findings: set[str] = set()
    for node in _walk_nodes(tree):
        collect_translated_membership_guard(node, translated_names, containers, findings)
    return findings


def _translation_key_parameter_positions(
    modules: list[tuple[Path, ast.Module]],
) -> dict[str, frozenset[int]]:
    """Map a function name to the CALL-SITE indices that carry a translation key.

    Built across every scanned module, because the helper that names its
    parameter ``help_key`` and the command spec that fills it positionally are
    routinely in different files. A per-module view sees the call and not the
    signature, which is why 192 live keys read as orphans.

    Keyed by bare function name, which collides: eight different ``_leaf``
    helpers ship here, carrying ``help_key`` at index 3, 1 or 2, and one whose
    index 1 is ``module``. Taking the union of those positions and applying it
    to every ``_leaf`` call collected module import paths as translation keys.

    So a position counts only when EVERY definition of that name carries a
    translation-key parameter there. A name whose definitions disagree yields
    nothing, which loses the keys it would have contributed rather than
    inventing keys it would not -- the safe direction, because an uncollected
    key reads as an unused catalogue entry while an invented one reads as a
    missing translation somebody has to chase.

    ``self`` and ``cls`` are dropped, since a bound call omits them and the
    index would otherwise be off by one for every method.
    """
    per_definition: dict[str, list[set[int]]] = {}
    for _path, tree in modules:
        for node in _walk_nodes(tree):
            collect_translation_key_parameter_positions(node, per_definition)
    agreed: dict[str, frozenset[int]] = {}
    for name, definitions in per_definition.items():
        shared = set.intersection(*definitions) if definitions else set()
        if shared:
            agreed[name] = frozenset(shared)
    return agreed


def _extract_positional_translation_key_arguments(
    tree: ast.AST,
    positions: dict[str, frozenset[int]],
) -> set[str]:
    """Collect dotted literals filled positionally into a translation-key parameter."""
    findings: set[str] = set()
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", getattr(node.func, "attr", None))
        if not isinstance(name, str):
            continue
        for index in positions.get(name, frozenset()):
            if index < len(node.args):
                _collect_dotted_literals(node.args[index], findings)
    return findings


def discover_translator_wrapper(name: str, first: str, node: ast.AST, known: set[str], discovered: set[str]) -> None:
    """Discover translator wrapper."""
    if name in known:
        return
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call) or not inner.args:
            continue
        callee = getattr(inner.func, "id", getattr(inner.func, "attr", None))
        argument = inner.args[0]
        if callee in known and isinstance(argument, ast.Name) and argument.id == first:
            discovered.add(name)
            break


def collect_guard_literal_container(node: ast.AST, containers: dict[str, set[str]]) -> None:
    """Collect guard literal container."""
    target: ast.expr | None = None
    value: ast.expr | None = None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    if not isinstance(target, ast.Name) or value is None:
        return
    if not isinstance(value, ast.Set | ast.List | ast.Tuple | ast.Call):
        return
    literals: set[str] = set()
    _collect_dotted_literals(value, literals)
    if literals:
        containers[target.id] = literals


def collect_translated_membership_guard(
    node: ast.AST, translated_names: frozenset[str], containers: dict[str, set[str]], findings: set[str]
) -> None:
    """Collect translated membership guard."""
    if not isinstance(node, ast.Compare):
        return
    if not any(isinstance(operator, ast.In | ast.NotIn) for operator in node.ops):
        return
    guarded = node.left
    name = guarded.attr if isinstance(guarded, ast.Attribute) else getattr(guarded, "id", None)
    # A generic name (``name``, ``code``) is translated somewhere for unrelated
    # reasons, so only a name that says it holds a key or a translated message
    # links a guard to copy.
    if name not in translated_names or not str(name).lower().endswith(("key", "message")):
        return
    for comparator in node.comparators:
        if isinstance(comparator, ast.Name) and comparator.id in containers:
            findings |= containers[comparator.id]


def collect_translation_key_parameter_positions(node: ast.AST, per_definition: dict[str, list[set[int]]]) -> None:
    """Collect translation key parameter positions."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return
    parameters = [*node.args.posonlyargs, *node.args.args]
    if parameters and parameters[0].arg in {"self", "cls"}:
        parameters = parameters[1:]
    per_definition.setdefault(node.name, []).append(
        {index for index, arg in enumerate(parameters) if arg.arg in _TRANSLATION_KEY_KWARGS},
    )
