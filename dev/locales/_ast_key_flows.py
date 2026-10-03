"""Confirm scalar, class, factory, and declared constant values reach translation."""

from __future__ import annotations

import ast

from ._ast_key_calls import _call_site_key_argument_exprs, _translation_call_names
from ._ast_key_dicts import _flow_confirmed_locale_key_dicts
from ._ast_key_policy import _ANONYMOUS_TABLE
from ._ast_key_rows import _collect_row_table_key_column_literals, _flow_confirmed_locale_key_row_tables
from ._ast_key_syntax import (
    _callee_name,
    _collect_declared_locale_keys,
    _collect_dotted_literals,
    _declares_locale_key_constant,
    _is_dotted_literal,
    _walk_nodes,
)


def _flow_confirmed_class_attribute_keys(tree: ast.AST, wrappers: frozenset[str] = frozenset()) -> set[str]:
    """Return dotted literals a class declares as an attribute and reads into a translator.

    A screen family names its own banner on the subclass and lets the base
    render it::

        class AeatSyncCensusScreen(AeatSyncWorkspaceScreen):
            heading = "tui.aeat_sync.census.title"
        ...
            yield Static(aeat_sync_copy(self.heading), ...)

    Nothing about that declaration is a call, a registry constant, or a
    collection, so every rule here looked past it and each subclass banner read
    as an orphan.

    Shape alone is again insufficient, and here the counter-example is one this
    scanner has already been bitten by: a class attribute holding a dotted
    literal is just as likely to be a route or an action id as a key. The
    attribute NAME must be read into a translator somewhere for its literals to
    count, which is the same bargain the dict and row-table shapes strike.
    """
    candidates: dict[str, set[str]] = {}
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            collect_class_attribute_candidate(statement, candidates)
    if not candidates:
        return set()

    tr_names = _translation_call_names(tree) | wrappers
    findings: set[str] = set()
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        for argument in _call_site_key_argument_exprs(node, tr_names):
            if isinstance(argument, ast.Attribute) and argument.attr in candidates:
                findings |= candidates[argument.attr]
    return findings


def _flow_confirmed_local_key_names(tree: ast.AST, wrappers: frozenset[str] = frozenset()) -> set[str]:
    """Return dotted literals held in a local that is then translated.

    A surface that picks between two labels names the choice before rendering
    it::

        status_key = "tui.ledger.evidence.pending" if row.pending_review else "tui.ledger.evidence.reviewed"
        table.add_row(..., ledger_copy(status_key))

    The call site passes a NAME, so the literal resolver saw no key there, and
    the value is a bare scalar rather than a registry, so the constant and
    collection rules had nothing to match either. Both branches were invisible.

    The candidate value is deliberately narrow -- a string constant, a
    conditional between them, or the literal fallback of ``mapping.get``.
    Other calls and subscripts are already the business of registry and
    row-table rules, and widening this to any expression would let it claim
    their shapes without their confirmation.

    Shape alone still does not collect: a dotted literal in a local is as
    likely to be a route or a lookup token as copy, so the NAME must reach a
    translator, which is the same bargain every other shape here strikes.
    """
    candidates: dict[str, set[str]] = {}
    for node in _walk_nodes(tree):
        collect_local_key_candidate(node, candidates)
    if not candidates:
        return set()

    tr_names = _translation_call_names(tree) | wrappers
    findings: set[str] = set()
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        for argument in _call_site_key_argument_exprs(node, tr_names):
            if isinstance(argument, ast.Name) and argument.id in candidates:
                findings |= candidates[argument.id]
    return findings


def _key_factory_returns(tree: ast.AST) -> dict[str, set[str]]:
    """Return ``function name -> the dotted keys every one of its returns yields``.

    A refusal that must name its own reason writes the choice as a function
    rather than at the call site::

        def session_refusal_translation_key(refusal):
            return (
                "cli.config.errors.profile_session_absent"
                if refusal in _LOGGED_OUT_REFUSALS
                else "cli.config.errors.profile_session_expired"
            )

    and the caller does ``key = session_refusal_translation_key(refusal)`` before
    passing ``key`` on. The local rule declines that deliberately -- its
    candidate value must be a key EXPRESSION, and a call is not one -- so both
    literals were invisible.

    A function qualifies only when EVERY return it makes is a key expression: a
    string constant, or a conditional between them. One return of anything else
    -- a computed name, a lookup, a formatted string -- and the function is not
    a key factory and none of its literals count. That is what keeps this from
    becoming "any function that mentions a dotted string".
    """
    factories: dict[str, set[str]] = {}
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        returns = [child for child in ast.walk(node) if isinstance(child, ast.Return)]
        if not returns:
            continue
        literals: set[str] = set()
        for statement in returns:
            if not isinstance(statement.value, ast.Constant | ast.IfExp):
                literals.clear()
                break
            found: set[str] = set()
            _collect_dotted_literals(statement.value, found)
            if not found:
                literals.clear()
                break
            literals |= found
        if literals:
            factories[node.name] = literals
    return factories


def _flow_confirmed_key_factory_keys(tree: ast.AST, wrappers: frozenset[str] = frozenset()) -> set[str]:
    """Return key-factory literals whose call result reaches a translator."""
    factories = _key_factory_returns(tree)
    if not factories:
        return set()
    bound: dict[str, set[str]] = {}
    for node in _walk_nodes(tree):
        collect_key_factory_binding(node, factories, bound)

    tr_names = _translation_call_names(tree) | wrappers
    findings: set[str] = set()
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        for argument in _call_site_key_argument_exprs(node, tr_names):
            if isinstance(argument, ast.Name) and argument.id in bound:
                findings |= bound[argument.id]
    return findings


def _extract_locale_constant_keys(tree: ast.AST, wrappers: frozenset[str] = frozenset()) -> set[str]:
    """Find dotted locale keys declared in explicit locale-key constants.

    Recognizes two independent declaration shapes: a constant NAMED as a
    locale-key registry (:func:`_declares_locale_key_constant`, suffix-based,
    which then trusts every dotted literal nested under its value), and a
    dict literal SHAPED as one AND actually read into a translator sink
    (:func:`_flow_confirmed_locale_key_dicts`) regardless of what its target
    is named. The second shape is what let a status-token-to-key mapping
    orphan invisibly when it carried neither a suffixed name nor a literal
    ``tr()`` call site — see :func:`dict_constant_naming_violations_in_tree`
    for the companion naming HAZARD this shape also earns. Flow confirmation
    (not shape alone) keeps a same-shaped unrelated lookup table — mapping
    one dotted identifier to another without ever reaching the translator —
    from being misread as a locale-key declaration.
    """
    findings: set[str] = _flow_confirmed_class_attribute_keys(tree, wrappers)
    findings |= _flow_confirmed_local_key_names(tree, wrappers)
    findings |= _flow_confirmed_key_factory_keys(tree, wrappers)
    flow_confirmed = _flow_confirmed_locale_key_dicts(tree, wrappers) | _flow_confirmed_locale_key_row_tables(
        tree, wrappers
    )
    for name, value in flow_confirmed.items():
        # A table written inline has no assignment for the walk below to match
        # against, so its keys are taken from the confirmed expression itself.
        if name.startswith(_ANONYMOUS_TABLE):
            _collect_row_table_key_column_literals(tree, value, findings, wrappers)
    for node in _walk_nodes(tree):
        collect_locale_constant_declaration(node, flow_confirmed, findings)
    return findings


def collect_class_attribute_candidate(statement: ast.stmt, candidates: dict[str, set[str]]) -> None:
    """Collect class attribute candidate."""
    target: ast.expr | None = None
    value: ast.expr | None = None
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target, value = statement.targets[0], statement.value
    elif isinstance(statement, ast.AnnAssign):
        target, value = statement.target, statement.value
    if not isinstance(target, ast.Name) or not isinstance(value, ast.Constant):
        return
    if isinstance(value.value, str) and _is_dotted_literal(value.value):
        candidates.setdefault(target.id, set()).add(value.value)


def collect_local_key_candidate(node: ast.AST, candidates: dict[str, set[str]]) -> None:
    """Collect local key candidate."""
    target: ast.expr | None = None
    value: ast.expr | None = None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    if not isinstance(target, ast.Name) or value is None:
        return
    literals = local_key_candidate_literals(value)
    if literals:
        candidates.setdefault(target.id, set()).update(literals)


def collect_key_factory_binding(node: ast.AST, factories: dict[str, set[str]], bound: dict[str, set[str]]) -> None:
    """Collect key factory binding."""
    target: ast.expr | None = None
    value: ast.expr | None = None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
        return
    name = _callee_name(value.func)
    if name in factories:
        bound.setdefault(target.id, set()).update(factories[name])


def collect_locale_constant_declaration(node: ast.AST, flow_confirmed: dict[str, ast.expr], findings: set[str]) -> None:
    """Collect locale constant declaration."""
    if isinstance(node, ast.Assign):
        collect_assigned_locale_constant(node, flow_confirmed, findings)
    elif isinstance(node, ast.AnnAssign):
        collect_annotated_locale_constant(node, flow_confirmed, findings)


def collect_assigned_locale_constant(node: ast.Assign, flow_confirmed: dict[str, ast.expr], findings: set[str]) -> None:
    """Collect assigned locale constant."""
    named = any(_declares_locale_key_constant(target) for target in node.targets)
    shaped = any(
        isinstance(target, ast.Name) and flow_confirmed.get(target.id) is node.value for target in node.targets
    )
    if named or shaped:
        _collect_declared_locale_keys(node.value, findings)


def collect_annotated_locale_constant(
    node: ast.AnnAssign, flow_confirmed: dict[str, ast.expr], findings: set[str]
) -> None:
    """Collect annotated locale constant."""
    named = _declares_locale_key_constant(node.target)
    shaped = isinstance(node.target, ast.Name) and flow_confirmed.get(node.target.id) is node.value
    if (named or shaped) and node.value is not None:
        _collect_declared_locale_keys(node.value, findings)


def local_key_candidate_literals(value: ast.expr) -> set[str] | None:
    """Local key candidate literals."""
    literals: set[str] = set()
    if isinstance(value, ast.Constant | ast.IfExp):
        _collect_dotted_literals(value, literals)
    elif (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "get"
        and len(value.args) >= 2
    ):
        _collect_dotted_literals(value.args[1], literals)
    else:
        return
    return literals
