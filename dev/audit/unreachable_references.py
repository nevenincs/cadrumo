"""Read exact syntax and shipped-data reference names without importing product code."""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterator
from typing import cast

from cadrumo.core.toml import TomlDecodeError, parse_toml
from dev._paths import UTF_8
from dev.quality.unread_inputs import format_unread_notice

from .unreachable_memo import _walked
from .unreachable_policy import _COMMAND_TOKEN, _DATA_TOKEN, _DOTTED_SPEC
from .unreachable_tree import ShippedTreeSpec

# ---------------------------------------------------------------------------
# Symbol layer: references and definitions inside reachable modules
# ---------------------------------------------------------------------------


def _skip_export_declarations(tree: ast.Module, skipped: set[int]) -> None:
    """Skip export declarations."""
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                skipped.update(id(child) for child in ast.walk(node))


def _assembled_handler_prefixes(tree: ast.Module) -> set[str]:
    """Assembled handler prefixes."""
    prefixes: set[str] = set()
    for node in _walked(tree):
        if not isinstance(node, ast.JoinedStr) or not node.values:
            continue
        head = node.values[0]
        if not (isinstance(head, ast.Constant) and isinstance(head.value, str)):
            continue
        prefix = head.value
        if prefix.endswith("_") and prefix[:-1].isidentifier():
            prefixes.add(prefix)
    return prefixes


def _assembled_handler_strippers(tree: ast.Module) -> list[tuple[str, str]]:
    """Assembled handler strippers."""
    strippers: list[tuple[str, str]] = []
    for node in _walked(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"removeprefix", "removesuffix"} or len(node.args) != 1:
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            strippers.append((node.func.attr, argument.value))
    return strippers


def _stripped_reference_names(strippers: list[tuple[str, str]], tokens: set[str]) -> Iterator[str]:
    """Stripped reference names."""
    for method, affix in strippers:
        for token in tokens:
            if method == "removeprefix" and token.startswith(affix):
                yield token[len(affix) :]
            elif method == "removesuffix" and token.endswith(affix):
                yield token[: -len(affix)]


def non_reference_nodes(tree: ast.Module) -> set[int]:
    """Nodes whose strings name nothing: ``__all__`` entries and prose.

    A docstring that happens to contain a symbol's name is describing it, not
    reaching it, and an ``__all__`` entry re-exports rather than uses. Counting
    either as a reference silently clears genuinely dead code, so both are cut
    out before any string is read as an identifier.
    """
    skipped: set[int] = set()
    _skip_export_declarations(tree, skipped)
    for node in _walked(tree):
        # A bare string expression statement is a docstring or commented-out
        # prose; it is never an expression whose value anything consumes.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            skipped.update(id(child) for child in ast.walk(node))
    return skipped


def string_reference_names(value: str) -> Iterator[str]:
    """Identifiers a string literal may address dynamically (``"mod:attr"``, ``"a.b"``)."""
    if _DOTTED_SPEC.match(value):
        for part in re.split(r"[.:]", value):
            if isinstance(part, str) and part:
                yield part


def assembled_reference_names(tree: ast.Module) -> Iterator[str]:
    """Identifiers a module BUILDS by f-string rather than spelling.

    The CLI command tables bind a handler through
    ``DeferredTarget(module, handler_name or f"work_{name}")``, where ``name``
    comes from the leaf token declared in the same table. The module string is
    a literal and is read, but the function name exists only after formatting,
    so every spec-bound command handler read as unused while its command was
    live: ``aeat app modelo work create`` runs, and ``work_create`` was a
    finding.

    The reader is deliberately narrow in three ways, because a looser one would
    SUPPRESS real findings rather than merely over-report. A prefix counts only
    when the f-string opens with a constant that is a valid identifier fragment
    ending in ``_``, so ``f"{value} rows"`` contributes nothing. Tokens are
    taken only from string literals in the SAME module, so a prefix cannot
    combine with a name declared elsewhere. And a token must look like a
    command leaf, so prose and dotted paths are excluded.
    """
    prefixes = _assembled_handler_prefixes(tree)
    # A second construction of the same kind: the handler name is derived from a
    # declared key by a string METHOD rather than by formatting, as in
    # ``DeferredTarget(_MODULE, key.removeprefix("app_"))``. Only the two affix
    # strippers are read; they are total functions of the literal they apply to,
    # so the derived name is exact rather than guessed.
    strippers = _assembled_handler_strippers(tree)
    if not prefixes and not strippers:
        return
    tokens = {
        node.value
        for node in _walked(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _COMMAND_TOKEN.fullmatch(node.value)
    }
    for prefix in prefixes:
        for token in tokens:
            yield f"{prefix}{token.replace('-', '_')}"
    yield from _stripped_reference_names(strippers, tokens)


def forward_reference_names(value: str) -> Iterator[str]:
    """Identifiers a string used in a TYPE position addresses.

    A forward reference is a type expression carried in a string, so
    ``"_AttachmentFileReader | None"`` names a class exactly as an unquoted
    annotation would. The dotted-spec form cannot reach it: a union is not a
    dotted path, so every quoted annotation carrying one read as no reference
    at all and its target was reported unused.

    Only strings the caller has already established sit in a type position are
    passed here, and the value must parse as an expression built solely from
    type syntax. Both guards matter in the same direction: a looser reader that
    treated any prose word as a reference would SUPPRESS real findings, which
    is the failure this audit must never have.
    """
    try:
        parsed = ast.parse(value, mode="eval")
    except SyntaxError:
        return
    allowed = (
        ast.Expression,
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.Tuple,
        ast.List,
        ast.Load,
        ast.Constant,
        ast.BinOp,
        ast.BitOr,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(parsed)):
        return
    for node in ast.walk(parsed):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr


def _type_position_strings(tree: ast.Module) -> Iterator[str]:
    """Yield every string literal the module places in a type position.

    Two positions are unambiguous: the first argument of a ``cast`` call, and
    an annotation written as a string literal.
    """
    for node in _walked(tree):
        yield from _cast_type_reference_strings(node)
        annotations: list[ast.expr | None] = []
        if isinstance(node, (ast.AnnAssign, ast.arg)):
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations.append(node.returns)
        for annotation in annotations:
            if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                yield annotation.value


def _references(tree: ast.Module) -> set[str]:
    """Every bare identifier the module loads, accesses, keywords, imports, or spells."""
    skipped = non_reference_nodes(tree)
    names: set[str] = set()
    for node in _walked(tree):
        if id(node) in skipped:
            continue
        _read_reference_node(node, names)
    for value in _type_position_strings(tree):
        names.update(forward_reference_names(value))
    return names


def _string_tokens(tree: ast.Module) -> set[str]:
    """Identifiers spelled inside string literals, the only dynamic reach left.

    Docstrings and ``__all__`` are excluded for the reason
    :func:`non_reference_nodes` gives: prose about a symbol is not a use of it.
    """
    skipped = non_reference_nodes(tree)
    tokens: set[str] = set()
    for node in _walked(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            tokens.update(string_reference_names(node.value))
    return tokens


def _data_tokens(spec: ShippedTreeSpec) -> frozenset[str]:
    """Identifier tokens in the shipped non-Python payloads.

    Registry declarations and locale catalogues address fields and enum values
    by name, so a member appearing there is reached by data even though no
    Python statement spells it.
    """
    package_root = spec.src_root / spec.package
    tokens: set[str] = set()
    unread: list[str] = []
    for glob in spec.data_globs:
        for path in package_root.glob(glob):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding=UTF_8)
            except (OSError, UnicodeDecodeError) as error:
                # A REFERENCE set: a token here is the evidence that a field or
                # enum value is addressed by data rather than by a Python
                # statement. Losing one makes a live member look dead, and dead
                # members here are deletion candidates. The lenient decode was
                # worse than the skip - a replaced byte can split a token so it
                # never matches, with nothing said either way.
                unread.append(f"{path}: {type(error).__name__}: {error}")
                continue
            tokens.update(_DATA_TOKEN.findall(text))
    if unread:
        raise OSError(format_unread_notice("unreachable-code data tokens", "coverage is unproven", unread).rstrip())
    return frozenset(tokens)


def _declared_data_values(spec: ShippedTreeSpec) -> frozenset[str]:
    """Mapping keys and COMPLETE string values in the shipped declarations.

    Deliberately stricter than :func:`_data_tokens`, and separate from it so
    the name match keeps its existing reach. A StrEnum member's declared value
    is matched against this set, where a loose match clears a live finding on
    a coincidence: tokenising the raw text cleared ``flows.BACK`` because a
    registry sentence reads "created and read back", and ``capabilities.
    PROCESS`` because another reads "Another process is acquiring AEAT". A key
    or a whole string value is a reference; a word inside a sentence, or in a
    comment, is prose about the domain.

    Unparseable files make the scan unavailable: a partial read would
    reintroduce exactly the prose matching this exists to exclude.
    """
    package_root = spec.src_root / spec.package
    values: set[str] = set()
    unread: list[str] = []

    for glob in spec.data_globs:
        for path in package_root.glob(glob):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding=UTF_8)
                parsed = parse_toml(text) if path.suffix == ".toml" else json.loads(text)
            except (OSError, UnicodeDecodeError, TomlDecodeError, json.JSONDecodeError) as error:
                unread.append(f"{path}: {type(error).__name__}: {error}")
                continue
            _collect_declared_strings(parsed, values)
    if unread:
        raise OSError(
            format_unread_notice("unreachable-code declared data values", "coverage is unproven", unread).rstrip()
        )
    return frozenset(values)


def _read_reference_node(node: ast.AST, names: set[str]) -> None:
    """Read one non-prose node through the existing reference syntax cases."""
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        names.add(node.id)
    elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
        names.add(node.attr)
    elif isinstance(node, ast.keyword) and node.arg is not None:
        names.add(node.arg)
    else:
        _read_literal_reference_node(node, names)


def _read_literal_reference_node(node: ast.AST, names: set[str]) -> None:
    """Read imported names and exact string references after loaded identifiers."""
    if isinstance(node, ast.ImportFrom):
        names.update(alias.name for alias in node.names)
    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        names.update(string_reference_names(node.value))


def _cast_type_reference_strings(node: ast.AST) -> Iterator[str]:
    """Read the explicit cast annotation position before other annotations."""
    if isinstance(node, ast.Call) and node.args:
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        first = node.args[0]
        if name == "cast" and isinstance(first, ast.Constant) and isinstance(first.value, str):
            yield first.value


def _collect_declared_strings(node: object, values: set[str]) -> None:
    """Collect only complete mapping keys and values from parsed declarations."""
    if isinstance(node, dict):
        for key, item in cast("dict[object, object]", node).items():
            if isinstance(key, str):
                values.add(key)
            _collect_declared_strings(item, values)
    elif isinstance(node, list):
        for item in cast("list[object]", node):
            _collect_declared_strings(item, values)
    elif isinstance(node, str):
        values.add(node)
