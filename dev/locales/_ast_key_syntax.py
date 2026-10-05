"""Literal and container syntax used by locale-key data-flow discovery."""

from __future__ import annotations

import ast
from contextlib import suppress

from ._ast_key_policy import (
    _AST_WALK_CACHE_ATTR,
    _DYNAMIC_TRANSLATION_ROOTS,
    _KEY_LITERAL_RE,
    _KEY_WRAPPER_CALLS,
    _LOCALE_KEY_CONSTANT_SUFFIXES,
)


def _is_dotted_literal(value: str) -> bool:
    """Return True when ``value`` matches the dot-notation key shape."""
    return bool(_KEY_LITERAL_RE.match(value))


def _is_dynamic_translation_prefix(prefix: str) -> bool:
    """Return True when a dynamic dotted prefix belongs to the i18n catalogue."""
    root = prefix.split(".", 1)[0]
    return root in _DYNAMIC_TRANSLATION_ROOTS


def _collect_declared_locale_keys(value: ast.expr, findings: set[str]) -> None:
    """Collect the locale keys a declared registry holds, and not its lookup tokens.

    A locale-key MAPPING is keyed by whatever the runtime selects on -- an enum
    value, a route identity, an action id -- and only its VALUES are locale
    keys. Sweeping the whole literal in claims those tokens as keys too, and
    they are dotted often enough to look the part: `workbench.home` and
    `operator.profile.edit` are a TUI route and a catalogue action, and the
    parity gate reported all of them as missing translations that no catalogue
    should ever have carried.

    Every other shape -- a tuple, list or set of keys, or a bare string -- has
    no such distinction, so it is collected whole as before.
    """
    if isinstance(value, ast.Dict):
        for item in value.values:
            _collect_dotted_literals(item, findings)
        return
    _collect_dotted_literals(value, findings)


def _declares_locale_key_constant(target: ast.expr) -> bool:
    """Return True when ``target`` names an explicit locale-key registry."""
    if not isinstance(target, ast.Name):
        return False
    return target.id.endswith(_LOCALE_KEY_CONSTANT_SUFFIXES)


def _is_locale_key_dict_literal(node: ast.expr | None) -> bool:
    """Return True when ``node`` is a dict literal shaped as a locale-key registry.

    Structural, not name-based: a dict literal mapping arbitrary keys (often
    short status/enum tokens resolved only at runtime) to translation keys is
    unambiguously a locale-key registry BY SHAPE alone, independent of what
    its assignment target is named. Requires at least one entry and EVERY
    value to be a dotted-key-shaped string constant — a dict with even one
    non-matching value is not treated as a locale-key mapping, which keeps
    the false-positive rate low against an ordinary lookup table that merely
    happens to carry one dotted-looking string.

    This is the exact shape that orphaned invisibly in production: a dict
    constant named without the ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix,
    read through a lowercase local variable (``SOME_DICT.get(token)``) into
    ``tr(...)``. Neither the declaration-side suffix check nor the call-site
    naming gate (which explicitly excludes lowercase/mixed-case arguments as
    genuinely dynamic values) can see it; recognizing the dict BY SHAPE closes
    the discovery gap without requiring any rename.
    """
    if not isinstance(node, ast.Dict) or not node.values:
        return False
    return all(_dotted_literal_value(value) is not None for value in node.values)


def _dict_access_source(value: ast.expr | None) -> str | None:
    """Return the dict-constant ``Name`` a ``.get(...)``/subscript access reads.

    Recognizes ``SOME_DICT.get(...)`` and ``SOME_DICT[...]`` where
    ``SOME_DICT`` is a bare name — the two lookup shapes both real incidents
    and every judged-legitimate lookup table in this codebase use.
    """
    if value is None:
        return None
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "get":
        base = value.func.value
        return base.id if isinstance(base, ast.Name) else None
    if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
        return value.value.id
    return None


def _literal_row_grid(node: ast.expr | None) -> list[list[str | None]] | None:
    """Return the table's cells by position, or ``None`` when it is not a literal grid.

    A cell need not be a string, or even a literal. These are all one shape::

        ("date", "tui.ledger.column.date", 10)
        (BusinessClassification.BUSINESS, "tui.ledger.classification.business")

    Demanding all-string rows rejected the first outright and demanding literal
    constants rejected the second, so in both cases the keys were never even
    candidates. Anything that is not a string literal is carried as ``None``,
    a position that can never BE a key column: the positional signal the shape
    test relies on is unchanged, and a width or an enum member is no more a key
    than a prose sibling is. What keeps this from over-firing is not the cell
    types but the confirmation that follows -- the table must be iterated into
    a translator, and the bound name must sit at a key column.
    """
    if not isinstance(node, ast.Tuple | ast.List) or not node.elts:
        return None
    rows: list[list[str | None]] = []
    for element in node.elts:
        if not isinstance(element, ast.Tuple | ast.List) or not element.elts:
            return None
        rows.append([literal_grid_cell(item) for item in element.elts])
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        return None
    return rows


def _is_locale_key_row_table_literal(node: ast.expr | None) -> bool:
    """Return True when ``node`` is a table of string ROWS carrying a key column.

    The dict shape above covers ``{token: "some.key"}``. A second table shape
    ships in this codebase and the dict test cannot see it: a tuple of
    equal-width tuples where one COLUMN holds the translation key and the
    others hold the framework's English source strings and defaults, iterated
    as ``for prefix, key, default, _ in TABLE`` and reaching ``tr(key)``.
    Requiring every value to be a dotted key -- as the dict shape does -- is
    exactly wrong here, because the sibling columns are prose by design.

    The signal is POSITIONAL instead: every row is all-string, every row has
    the same width, and there is at least one index where EVERY row carries a
    dotted-key-shaped string. A column that is a key in one row and prose in
    the next is not a key column, so an ordinary table of English pairs cannot
    qualify. Prose does not collide with the key shape in any case, since
    :data:`_KEY_LITERAL_RE` admits no spaces.
    """
    rows = _literal_row_grid(node)
    if rows is None:
        return False
    return any(
        all(cell is not None and _is_dotted_literal(cell) for cell in column) for column in zip(*rows, strict=True)
    )


def _row_table_key_columns(node: ast.expr | None) -> frozenset[int]:
    """Return the column indices where EVERY row carries a dotted key.

    The shape test asks whether such a column exists; confirmation needs to
    know WHICH, because the sibling columns are prose by design and a name
    bound to one of those reaching a sink says nothing about the table.
    """
    rows = _literal_row_grid(node)
    if rows is None:
        return frozenset[int]()
    return frozenset(
        index
        for index, column in enumerate(zip(*rows, strict=True))
        if all(cell is not None and _is_dotted_literal(cell) for cell in column)
    )


def _row_subscript_sources(node: ast.expr, bound_to_table: dict[str, set[str]]) -> list[tuple[str, int]]:
    """Return ``(table, index)`` pairs when ``node`` indexes a bound whole row."""
    if not isinstance(node, ast.Subscript):
        return []
    if not (isinstance(node.value, ast.Name) and node.value.id in bound_to_table):
        return []
    if not (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int)):
        return []
    return [(table, node.slice.value) for table in bound_to_table[node.value.id]]


def _collect_dotted_literals(node: ast.expr | None, findings: set[str]) -> None:
    """Collect dotted string literals nested under ``node``.

    An interpolating f-string is not descended into: its literal head, such as
    ``"application.workflow.errors.resume_refused_"``, is a fragment of a key
    whose tail is computed, never a key of its own, so enrolling it would report
    a key no catalogue can carry. Its family belongs to the f-string registry.
    """
    if node is None:
        return
    if isinstance(node, ast.JoinedStr):
        collect_noninterpolating_joined_literal(node, findings)
        return
    value = _dotted_literal_value(node)
    if value is not None:
        findings.add(value)
        return
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            _collect_dotted_literals(child, findings)


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
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and _is_dotted_literal(node.value):
        return node.value
    return _unwrapped_key_literal(node)


def _unwrapped_key_literal(node: ast.expr | None) -> str | None:
    """Return the key inside a single-argument key wrapper, else ``None``.

    ``TranslationKey("cli.app.ledger.x_help")`` and ``_key("cli.app.live.y_help")``
    denote exactly the string they wrap; the wrapper is a typing newtype and a local
    shorthand, not a transformation. Restricted to a known callee set and to a lone
    positional Constant argument, so a call that COMPUTES a key is still correctly
    left to the dynamic-prefix machinery rather than being read as a literal.
    """
    if not isinstance(node, ast.Call) or node.keywords or len(node.args) != 1:
        return None
    if _callee_name(node.func) not in _KEY_WRAPPER_CALLS:
        return None
    argument = node.args[0]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str) and _is_dotted_literal(argument.value):
        return argument.value
    return None


def _walk_nodes(root: ast.AST) -> tuple[ast.AST, ...]:
    """Return ``ast.walk(root)``'s breadth-first order, cached on *root*.

    The locale scanner asks several independent structural predicates the same
    question about each parsed module.  Rebuilding ``ast.walk``'s deque for
    every predicate was the dominant cost once the source tree grew beyond two
    thousand modules.  AST nodes accept private attributes, so keeping the
    immutable traversal tuple on the root avoids a process-global cache (and
    therefore avoids retaining temporary fixture trees or crossing manager
    boundaries).  If a caller supplies an AST implementation that does not
    allow attributes, the uncached walk remains the safe fallback.

    No scanner mutates AST structure while collecting findings; adding the
    private cache attribute is not part of ``ast.iter_child_nodes`` and cannot
    affect the traversal or its order.
    """
    cached = getattr(root, _AST_WALK_CACHE_ATTR, None)
    if isinstance(cached, tuple):
        cached_nodes: list[ast.AST] = []
        for cached_node in cached:
            if not isinstance(cached_node, ast.AST):
                break
            cached_nodes.append(cached_node)
        else:
            return tuple(cached_nodes)
    nodes = tuple(ast.walk(root))
    with suppress(AttributeError, TypeError):
        setattr(root, _AST_WALK_CACHE_ATTR, nodes)
    return nodes


def literal_grid_cell(item: ast.expr) -> str | None:
    """Read only a literal string cell while retaining every other column position."""
    return item.value if isinstance(item, ast.Constant) and isinstance(item.value, str) else None


def collect_noninterpolating_joined_literal(node: ast.JoinedStr, findings: set[str]) -> None:
    """Collect noninterpolating joined literal."""
    literal_parts = [
        part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str)
    ]
    whole = "".join(literal_parts)
    if len(literal_parts) == len(node.values) and _is_dotted_literal(whole):
        findings.add(whole)
