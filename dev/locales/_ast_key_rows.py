"""Confirm table columns reach translators through iteration and parameter binding."""

from __future__ import annotations

import ast
from collections.abc import Iterator

from ._ast_key_calls import _call_site_key_argument_exprs, _translation_call_names
from ._ast_key_policy import _ANONYMOUS_TABLE
from ._ast_key_syntax import (
    _callee_name,
    _collect_declared_locale_keys,
    _is_locale_key_row_table_literal,
    _literal_row_grid,
    _row_subscript_sources,
    _row_table_key_columns,
    _walk_nodes,
)


def _collect_row_table_key_column_literals(
    tree: ast.AST,
    value: ast.expr,
    findings: set[str],
    wrappers: frozenset[str],
) -> None:
    """Collect only the row-table columns whose bindings reach a key sink."""
    rows = _literal_row_grid(value)
    if rows is None:
        return
    tr_names = _translation_call_names(tree) | wrappers
    bound_columns: dict[str, int] = {}
    for binding in _iteration_bindings(tree):
        bind_literal_row_columns(binding, value, bound_columns)
    if not bound_columns:
        # Anonymous tables passed into a helper are iterated through the
        # helper parameter rather than the literal expression itself. Their
        # flow was already confirmed by the parameter-alias pass above; retain
        # the established collection path for that distinct inline shape.
        _collect_declared_locale_keys(value, findings)
        return
    key_columns: set[int] = set()
    for node in _walk_nodes(tree):
        collect_row_column_sink(node, tr_names, bound_columns, key_columns)
    for row in rows:
        for index in key_columns:
            literal = row[index]
            if literal is not None:
                findings.add(literal)


def _shape_candidate_locale_key_row_tables(tree: ast.AST) -> dict[str, ast.expr]:
    """Return every ``Name -> row-table-literal`` pair shaped as a locale-key registry."""
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
        if isinstance(target, ast.Name) and value is not None and _is_locale_key_row_table_literal(value):
            candidates[target.id] = value
    return candidates


def _row_table_names_iterated_into_a_sink(
    tree: ast.AST, candidates: dict[str, ast.expr], wrappers: frozenset[str] = frozenset()
) -> frozenset[str]:
    """Return the candidate row-table names whose loop variable reaches a translator.

    The dict sink tracks ``.get(...)``/subscript access. A row table is not
    read that way -- it is ITERATED, and the key arrives at ``tr`` as one of
    the loop's unpacked target names. Confirming through that binding is what
    separates a genuine locale-key table from a same-shaped table of unrelated
    string tuples that never reaches the translator.
    """
    tr_names = _translation_call_names(tree) | wrappers
    # The alias pass runs FIRST because it registers inline tables into
    # `candidates`, and a key-column map built before that would not carry them.
    aliases = _parameters_bound_to_a_candidate_table(tree, candidates)
    key_columns = {name: _row_table_key_columns(value) for name, value in candidates.items()}
    bound_to_table: dict[str, set[str]] = {}
    for node in _iteration_bindings(tree):
        bind_row_table_iteration(node, candidates, aliases, key_columns, bound_to_table)
    confirmed: set[str] = set()
    for node in _walk_nodes(tree):
        confirm_row_table_sink(node, tr_names, bound_to_table, key_columns, confirmed)
    return frozenset(confirmed)


def _iteration_bindings(tree: ast.AST) -> Iterator[ast.For | ast.AsyncFor | ast.comprehension]:
    """Yield every construct that binds names by iterating something.

    A ``for`` statement and a comprehension's generator bind identically, and
    reading only the statement form missed the table iterated inside a
    generator expression -- which is how the widest screen sizes its columns.
    """
    for node in _walk_nodes(tree):
        if isinstance(node, ast.For | ast.AsyncFor):
            yield node
        elif isinstance(node, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp):
            yield from node.generators


def _parameters_bound_to_a_candidate_table(tree: ast.AST, candidates: dict[str, ast.expr]) -> dict[str, frozenset[str]]:
    """Map a local function's parameter name to the candidate table passed into it.

    A screen shares its column-fitting rule rather than repeating it, so the
    table is not iterated where it is declared -- it is handed to a helper::

        _fit_columns(self.app.size.width, self._COLUMNS, self._VALUE_COLUMNS)

    Inside that helper the parameter is iterated and its rows translated, but
    the confirmation walk saw only a parameter name and could not tell it was
    this table. One hop is enough here because the analysis is name-based
    within the module, so a row bound in the helper is already followed into
    the nested function it is handed to.

    A parameter filled by SEVERAL tables confirms all of them, and that is
    not a guess: one shared helper is called by every screen with its own
    columns, so if the parameter's rows reach a translator then every table
    handed to it is translated. Dropping the name as ambiguous would fail the
    common case for being common.
    """
    parameters: dict[str, ast.arguments] = {}
    for node in _walk_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            parameters[node.name] = node.args
    seen: dict[str, set[str]] = {}
    for node in _walk_nodes(tree):
        bind_call_table_parameters(node, parameters, candidates, seen)
    return {name: frozenset(tables) for name, tables in seen.items()}


def _iterated_candidate_tables(
    node: ast.expr, candidates: dict[str, ast.expr], aliases: dict[str, frozenset[str]] | None = None
) -> frozenset[str]:
    """Resolve the candidate table a ``for`` statement iterates.

    A screen holds its column table as a ``ClassVar`` and reads it back as
    ``self._COLUMNS``, so requiring a bare name saw no iteration at all and
    left every heading key in the table unconfirmed. The attribute's own name
    is what identifies the candidate; the declaration it was collected from is
    already in this module.
    """
    if isinstance(node, ast.Name) and node.id in candidates:
        return frozenset({node.id})
    if isinstance(node, ast.Attribute) and node.attr in candidates:
        return frozenset({node.attr})
    if aliases is not None and isinstance(node, ast.Name):
        return aliases.get(node.id, frozenset[str]())
    return frozenset[str]()


def _flow_confirmed_locale_key_row_tables(tree: ast.AST, wrappers: frozenset[str] = frozenset()) -> dict[str, ast.expr]:
    """Return shape-candidate row tables actually iterated into a translator sink."""
    candidates = _shape_candidate_locale_key_row_tables(tree)
    confirmed_names = _row_table_names_iterated_into_a_sink(tree, candidates, wrappers)
    return {name: value for name, value in candidates.items() if name in confirmed_names}


def bind_literal_row_columns(
    binding: ast.For | ast.AsyncFor | ast.comprehension, value: ast.expr, bound_columns: dict[str, int]
) -> None:
    """Bind literal row columns."""
    if binding.iter is not value:
        return
    for index, target in enumerate(getattr(binding.target, "elts", ())):
        if isinstance(target, ast.Name):
            bound_columns[target.id] = index


def collect_row_column_sink(
    node: ast.AST, tr_names: frozenset[str], bound_columns: dict[str, int], key_columns: set[int]
) -> None:
    """Collect row column sink."""
    if not isinstance(node, ast.Call):
        return
    for argument in _call_site_key_argument_exprs(node, tr_names):
        if isinstance(argument, ast.Name) and argument.id in bound_columns:
            key_columns.add(bound_columns[argument.id])


def bind_row_table_iteration(
    node: ast.For | ast.AsyncFor | ast.comprehension,
    candidates: dict[str, ast.expr],
    aliases: dict[str, frozenset[str]],
    key_columns: dict[str, frozenset[int]],
    bound_to_table: dict[str, set[str]],
) -> None:
    """Bind row table iteration."""
    tables = _iterated_candidate_tables(node.iter, candidates, aliases)
    if not tables and _is_locale_key_row_table_literal(node.iter):
        # A table written directly in ``for ... in (...)`` has no
        # assignment target to enter the candidate map. It is the same
        # semantic shape as a named table or one passed inline to a helper,
        # so register the expression itself and keep the existing
        # key-column and sink-flow checks authoritative.
        synthetic = f"{_ANONYMOUS_TABLE}{len(candidates)}"
        candidates[synthetic] = node.iter
        key_columns[synthetic] = _row_table_key_columns(node.iter)
        tables = frozenset({synthetic})
    for table in tables:
        columns = key_columns[table]
        if isinstance(node.target, ast.Name):
            # A whole-row binding cannot say which column reaches the sink,
            # so it stays confirmable as before.
            bound_to_table.setdefault(node.target.id, set()).add(table)
            continue
        # Unpacked: only the KEY column binding confirms. A name bound to a
        # prose column reaching a sink is the framework passing its English
        # source string, which says nothing about whether the table holds
        # keys.
        for index, target in enumerate(getattr(node.target, "elts", [])):
            if isinstance(target, ast.Name) and index in columns:
                bound_to_table.setdefault(target.id, set()).add(table)


def confirm_row_table_sink(
    node: ast.AST,
    tr_names: frozenset[str],
    bound_to_table: dict[str, set[str]],
    key_columns: dict[str, frozenset[int]],
    confirmed: set[str],
) -> None:
    """Confirm row table sink."""
    if not isinstance(node, ast.Call):
        return
    for argument in _call_site_key_argument_exprs(node, tr_names):
        if isinstance(argument, ast.Name) and argument.id in bound_to_table:
            confirmed |= bound_to_table[argument.id]
            continue
        # `for column in TABLE: tr(column[1])` -- the row is bound whole and
        # the key taken by index. The index must BE a key column: a prose
        # sibling reaching the sink says nothing about the table, exactly as
        # it does not when the row is unpacked.
        for table, index in _row_subscript_sources(argument, bound_to_table):
            if index in key_columns[table]:
                confirmed.add(table)


def bind_call_table_parameters(
    node: ast.AST, parameters: dict[str, ast.arguments], candidates: dict[str, ast.expr], seen: dict[str, set[str]]
) -> None:
    """Bind call table parameters."""
    if not isinstance(node, ast.Call):
        return
    signature = parameters.get(_callee_name(node.func) or "")
    if signature is None:
        return
    positional = [*signature.posonlyargs, *signature.args]
    for index, argument in enumerate(node.args):
        if index >= len(positional):
            break
        tables = _iterated_candidate_tables(argument, candidates)
        if not tables and _is_locale_key_row_table_literal(argument):
            # Written INLINE at the call site. One screen builds its column
            # table in the argument list rather than binding it first, so
            # there is no name to be a candidate under -- and a table with
            # no name was invisible to every rule here, though it is the
            # same table doing the same job as its named siblings.
            #
            # It is admitted on the same terms as a named one: registered
            # under a synthetic name so the parameter alias and the key
            # column discipline both apply unchanged, and confirmed only if
            # that parameter's rows actually reach a translator.
            synthetic = f"{_ANONYMOUS_TABLE}{len(candidates)}"
            candidates[synthetic] = argument
            tables = frozenset({synthetic})
        if tables:
            seen.setdefault(positional[index].arg, set()).update(tables)
