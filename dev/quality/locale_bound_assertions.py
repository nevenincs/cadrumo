"""Detect unpinned output-absence assertions bound to exactly one locale."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, override

import yaml

__all__ = [
    "LanguagePinning",
    "LocaleBoundAssertion",
    "declared_language_pinning",
    "load_catalogue_strings",
    "scan_locale_bound_assertions",
]

_UNTRANSLATED_CLICK_LITERALS = frozenset(
    {
        "Invalid value",
        "Missing argument",
        "Missing option",
        "No such command",
        "No such option",
        "Usage:",
        "is not a valid integer",
    },
)


@dataclass(frozen=True, slots=True)
class LanguagePinning:
    """The argv and environment pinning forms declared by production."""

    flags: tuple[str, ...]
    prefixes: tuple[str, ...]
    environment_variable: str


@dataclass(frozen=True, slots=True)
class LocaleBoundAssertion:
    """One unpinned absence assertion whose literal belongs to one locale."""

    path: Path
    lineno: int
    literal: str
    polarity: str
    locales: frozenset[str]
    haystack: str

    @override
    def __str__(self) -> str:
        """Render an openable locator and the locale binding."""
        locales = ",".join(sorted(self.locales))
        return (
            f"{self.path}:{self.lineno} {self.polarity} {self.literal!r} in "
            f"{self.haystack} is bound to locales [{locales}] without a pin"
        )


def _literal_assignment(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            if node.value is None:
                break
            return ast.literal_eval(node.value)
    msg = f"declaration {name!r} is absent"
    raise ValueError(msg)


def declared_language_pinning(
    language_argv_source: str,
    external_constants_source: str,
) -> LanguagePinning:
    """Read every pinning spelling from its production declaration."""
    argv_tree = ast.parse(language_argv_source)
    constants_tree = ast.parse(external_constants_source)
    flags = _literal_assignment(argv_tree, "_LANGUAGE_FLAGS")
    prefixes = _literal_assignment(argv_tree, "_LANGUAGE_FLAG_PREFIXES")
    environment_variable = _literal_assignment(constants_tree, "OUTPUT_LANGUAGE_ENV_VAR")
    if not (
        isinstance(flags, tuple)
        and all(isinstance(flag, str) for flag in flags)
        and isinstance(prefixes, tuple)
        and all(isinstance(prefix, str) for prefix in prefixes)
        and isinstance(environment_variable, str)
    ):
        msg = "language pinning declarations must contain only strings"
        raise ValueError(msg)
    return LanguagePinning(
        flags=flags,
        prefixes=prefixes,
        environment_variable=environment_variable,
    )


def _flatten_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(text for child in value.values() for text in _flatten_strings(child))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(text for child in value for text in _flatten_strings(child))
    return ()


def load_catalogue_strings(catalogues: Mapping[str, Sequence[Path]]) -> dict[str, tuple[str, ...]]:
    """Load every translated scalar from each declared locale catalogue."""
    loaded: dict[str, tuple[str, ...]] = {}
    for locale, paths in catalogues.items():
        strings: list[str] = []
        for path in paths:
            parsed: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
            strings.extend(_flatten_strings(parsed))
        loaded[locale] = tuple(strings)
    return loaded


def _argv_elements(call: ast.Call) -> tuple[ast.expr, ...]:
    if not call.args or not isinstance(call.args[0], (ast.List, ast.Tuple)):
        return ()
    return tuple(call.args[0].elts)


def _literal_string(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _joined_literal(node: ast.expr) -> str | None:
    if not isinstance(node, ast.JoinedStr):
        return None
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif (
            isinstance(value, ast.FormattedValue)
            and isinstance(value.value, ast.Constant)
            and isinstance(value.value.value, str)
        ):
            parts.append(value.value.value)
        else:
            return None
    return "".join(parts)


def _call_has_pin(
    call: ast.Call,
    pinning: LanguagePinning,
    supported_locales: frozenset[str],
    pinned_output_helpers: frozenset[str],
    pinned_environment_helpers: frozenset[str],
) -> bool:
    if isinstance(call.func, ast.Name) and call.func.id in pinned_output_helpers:
        return True
    argv = _argv_elements(call)
    for index, element in enumerate(argv):
        token = _literal_string(element)
        if token in pinning.flags and index + 1 < len(argv) and _literal_string(argv[index + 1]) in supported_locales:
            return True
        candidate = token or _joined_literal(element)
        if candidate is None:
            continue
        for prefix in pinning.prefixes:
            if candidate.startswith(prefix) and candidate.removeprefix(prefix) in supported_locales:
                return True
    for keyword in call.keywords:
        if keyword.arg != "env":
            continue
        if (
            isinstance(keyword.value, ast.Call)
            and isinstance(keyword.value.func, ast.Name)
            and keyword.value.func.id in pinned_environment_helpers
        ):
            return True
        if _dict_has_environment_pin(keyword.value, pinning, supported_locales):
            return True
    return False


def _dict_has_environment_pin(
    node: ast.expr,
    pinning: LanguagePinning,
    supported_locales: frozenset[str],
) -> bool:
    if not isinstance(node, ast.Dict):
        return False
    return any(
        isinstance(key, ast.Constant)
        and key.value == pinning.environment_variable
        and isinstance(value, ast.Constant)
        and value.value in supported_locales
        for key, value in zip(node.keys, node.values, strict=True)
    )


def _return_values(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ast.expr, ...]:
    """Return expressions from one helper without borrowing nested scopes."""
    pending: list[ast.AST] = list(function.body)
    values: list[ast.expr] = []
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            values.append(node.value)
            continue
        pending.extend(ast.iter_child_nodes(node))
    return tuple(values)


def _returns_environment_pin(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    pinning: LanguagePinning,
    supported_locales: frozenset[str],
    pinned_environment_helpers: frozenset[str],
) -> bool:
    """Whether a helper returns a mapping carrying the declared env pin."""
    returned_values = _return_values(function)
    return bool(returned_values) and all(
        _dict_has_environment_pin(returned, pinning, supported_locales)
        or (
            isinstance(returned, ast.Call)
            and isinstance(returned.func, ast.Name)
            and returned.func.id in pinned_environment_helpers
        )
        for returned in returned_values
    )


def _environment_helpers(
    tree: ast.Module,
    pinning: LanguagePinning,
    supported_locales: frozenset[str],
) -> frozenset[str]:
    pinned: set[str] = set()
    changed = True
    while changed:
        changed = False
        for function in (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if function.name in pinned:
                continue
            if _returns_environment_pin(function, pinning, supported_locales, frozenset(pinned)):
                pinned.add(function.name)
                changed = True
    return frozenset(pinned)


def _output_helpers(
    tree: ast.Module,
    pinning: LanguagePinning,
    supported_locales: frozenset[str],
    pinned_environment_helpers: frozenset[str],
) -> frozenset[str]:
    pinned: set[str] = set()
    changed = True
    while changed:
        changed = False
        for function in (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if function.name in pinned:
                continue
            returned = _return_values(function)
            if returned and all(
                (
                    isinstance(node, ast.Call)
                    and _call_has_pin(
                        node,
                        pinning,
                        supported_locales,
                        frozenset(pinned),
                        pinned_environment_helpers,
                    )
                )
                or (
                    isinstance(node, ast.Name)
                    and _pin_state_by_name(
                        function,
                        pinning,
                        supported_locales,
                        frozenset(pinned),
                        pinned_environment_helpers,
                        before_node=expression,
                    ).get(node.id, False)
                )
                for expression in returned
                for node in (expression,)
            ):
                pinned.add(function.name)
                changed = True
    return frozenset(pinned)


def _assigned_name(node: ast.Assign | ast.AnnAssign) -> str | None:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names = [target.id for target in targets if isinstance(target, ast.Name)]
    return names[0] if len(names) == 1 else None


def _same_scope_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.AST, ...]:
    """Return source-ordered nodes without crossing a nested lexical scope."""
    nodes: list[ast.AST] = []

    def descend(node: ast.AST) -> None:
        nodes.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        for child in ast.iter_child_nodes(node):
            descend(child)

    for statement in function.body:
        descend(statement)
    return tuple(nodes)


def _root_name(node: ast.expr) -> str | None:
    """Return the simple root of a name or attribute chain."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _call_receiver_name(call: ast.Call) -> str | None:
    """Return the root whose method produces a call result, never argument names."""
    return _root_name(call.func.value) if isinstance(call.func, ast.Attribute) else None


def _all_named_inputs_pinned(node: ast.expr, states: Mapping[str, bool]) -> bool:
    """Whether a non-call expression is derived only from pinned named values."""
    names = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
    return bool(names) and all(states.get(name, False) for name in names)


def _pin_state_by_name(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    pinning: LanguagePinning,
    supported_locales: frozenset[str],
    pinned_output_helpers: frozenset[str],
    pinned_environment_helpers: frozenset[str],
    *,
    before_node: ast.AST | None = None,
) -> dict[str, bool]:
    output_states: dict[str, bool] = {}
    environment_states: dict[str, bool] = {}
    scope_nodes = _same_scope_nodes(function)
    before_position = len(scope_nodes) if before_node is None else scope_nodes.index(before_node)
    statements = (node for node in scope_nodes[:before_position] if isinstance(node, (ast.Assign, ast.AnnAssign)))
    for statement in statements:
        name = _assigned_name(statement)
        if name is None:
            continue
        value = statement.value
        if value is None:
            continue
        if isinstance(value, ast.Call):
            direct = _call_has_pin(
                value,
                pinning,
                supported_locales,
                pinned_output_helpers,
                pinned_environment_helpers,
            )
            inherited_environment = any(
                keyword.arg == "env"
                and isinstance(keyword.value, ast.Name)
                and environment_states.get(keyword.value.id, False)
                for keyword in value.keywords
            )
            receiver_name = _call_receiver_name(value)
            inherited_receiver = receiver_name is not None and output_states.get(receiver_name, False)
            output_states[name] = direct or inherited_environment or inherited_receiver
            environment_states[name] = bool(
                isinstance(value.func, ast.Name) and value.func.id in pinned_environment_helpers
            )
            continue
        root_name = _root_name(value)
        output_states[name] = _all_named_inputs_pinned(value, output_states)
        environment_states[name] = _dict_has_environment_pin(value, pinning, supported_locales) or (
            root_name is not None and environment_states.get(root_name, False)
        )
    return output_states


def _asserted_membership(node: ast.Assert) -> tuple[str, str, ast.expr] | None:
    test = node.test
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], (ast.In, ast.NotIn))
        and len(test.comparators) == 1
        and isinstance(test.left, ast.Constant)
        and isinstance(test.left.value, str)
    ):
        return None
    polarity = "presence" if isinstance(test.ops[0], ast.In) else "absence"
    return test.left.value, polarity, test.comparators[0]


def _mentions_output(node: ast.expr) -> bool:
    """Whether the asserted haystack names an output capture."""
    return any(
        (isinstance(child, ast.Name) and "output" in child.id.casefold())
        or (isinstance(child, ast.Attribute) and "output" in child.attr.casefold())
        for child in ast.walk(node)
    )


def scan_locale_bound_assertions(
    path: Path,
    source: str,
    catalogue_strings: Mapping[str, Sequence[str]],
    pinning: LanguagePinning,
    *,
    ambient_locale: str,
) -> tuple[LocaleBoundAssertion, ...]:
    """Return unpinned output-absence literals bound to exactly one locale."""
    tree = ast.parse(source, filename=str(path))
    supported_locales = frozenset(catalogue_strings)
    if ambient_locale not in supported_locales:
        msg = f"ambient locale {ambient_locale!r} has no catalogue"
        raise ValueError(msg)
    pinned_environment_helpers = _environment_helpers(tree, pinning, supported_locales)
    pinned_output_helpers = _output_helpers(tree, pinning, supported_locales, pinned_environment_helpers)
    findings: list[LocaleBoundAssertion] = []
    for function in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        for node in _same_scope_nodes(function):
            if not isinstance(node, ast.Assert):
                continue
            membership = _asserted_membership(node)
            if membership is None:
                continue
            literal, polarity, haystack_node = membership
            if not _mentions_output(haystack_node):
                continue
            if literal in _UNTRANSLATED_CLICK_LITERALS:
                continue
            locales = frozenset(
                locale
                for locale, strings in catalogue_strings.items()
                if any(literal in translated for translated in strings)
            )
            if polarity != "absence" or len(locales) != 1 or ambient_locale in locales:
                continue
            if any(
                _call_has_pin(
                    call,
                    pinning,
                    supported_locales,
                    pinned_output_helpers,
                    pinned_environment_helpers,
                )
                for call in ast.walk(haystack_node)
                if isinstance(call, ast.Call)
            ):
                continue
            states = _pin_state_by_name(
                function,
                pinning,
                supported_locales,
                pinned_output_helpers,
                pinned_environment_helpers,
                before_node=node,
            )
            haystack_names = {child.id for child in ast.walk(haystack_node) if isinstance(child, ast.Name)}
            if any(states.get(name, False) for name in haystack_names):
                continue
            findings.append(
                LocaleBoundAssertion(
                    path=path,
                    lineno=node.lineno,
                    literal=literal,
                    polarity=polarity,
                    locales=locales,
                    haystack=ast.unparse(haystack_node),
                ),
            )
    return tuple(findings)
