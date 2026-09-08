"""Detect gate consumers that weaken a declared structured verdict grammar.

A verdict token can be recognised only after the producer's output shape has
been parsed.  Direct containment, prefix, or suffix predicates against a token
are blind when the declared grammar permits surrounding text.  The declarations
below identify producers and their verdict tokens; they are scope, not
exceptions, and adding another producer expands the sweep.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import override

__all__ = [
    "GateVerdictConsumer",
    "WeakGateVerdictPredicate",
    "gate_verdict_consumers",
    "scan_gate_verdict_grammar",
    "scan_paths_for_gate_verdict_grammar",
]


@dataclass(frozen=True, slots=True)
class _GateOutputGrammar:
    producer: str
    markers: frozenset[str]
    verdicts: frozenset[str]


@dataclass(frozen=True, slots=True)
class _SubprocessRunAliases:
    modules: frozenset[str]
    direct: frozenset[str]


_GATE_OUTPUT_GRAMMARS = (
    _GateOutputGrammar(
        producer="import-linter",
        markers=frozenset({"lint-imports"}),
        verdicts=frozenset({"BROKEN", "KEPT"}),
    ),
)


@dataclass(frozen=True, slots=True)
class GateVerdictConsumer:
    """One module that names a declared producer and one of its verdicts."""

    path: Path
    producer: str


@dataclass(frozen=True, slots=True)
class WeakGateVerdictPredicate:
    """One predicate that reads a structured gate verdict as an unparsed token."""

    path: Path
    lineno: int
    producer: str
    predicate: str
    verdict: str

    @override
    def __str__(self) -> str:
        """Render an openable locator and the weakened grammar claim."""
        return (
            f"{self.path}:{self.lineno} {self.predicate}({self.verdict!r}) "
            f"cannot parse {self.producer}'s structured verdict"
        )


def _literal_strings(tree: ast.AST) -> frozenset[str]:
    docstrings = {
        id(statement.value)
        for parent in ast.walk(tree)
        if isinstance(parent, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and parent.body
        for statement in parent.body[:1]
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    }
    return frozenset(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    )


def _grammars_for(tree: ast.Module) -> tuple[_GateOutputGrammar, ...]:
    literals = _literal_strings(tree)
    return tuple(
        grammar
        for grammar in _GATE_OUTPUT_GRAMMARS
        if any(marker in literal for marker in grammar.markers for literal in literals)
        and grammar.verdicts.intersection(literals)
    )


def gate_verdict_consumers(paths: tuple[Path, ...]) -> tuple[GateVerdictConsumer, ...]:
    """Return modules enrolled by a declared producer grammar."""
    consumers: list[GateVerdictConsumer] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        consumers.extend(GateVerdictConsumer(path, grammar.producer) for grammar in _grammars_for(tree))
    return tuple(consumers)


def _literal_verdicts(node: ast.expr, verdicts: frozenset[str]) -> tuple[str, ...]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,) if node.value in verdicts else ()
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return tuple(
            element.value
            for element in node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str) and element.value in verdicts
        )
    return ()


def _block_terminates(statements: list[ast.stmt]) -> bool:
    return bool(statements) and isinstance(statements[-1], (ast.Return, ast.Raise))


def _assigned_value(target: ast.expr, value: ast.expr | None, name: str) -> ast.expr | None:
    """Return the value paired with one binding in a simple assignment target."""
    if isinstance(target, ast.Name):
        return value if target.id == name else None
    if (
        isinstance(target, (ast.Tuple, ast.List))
        and isinstance(value, (ast.Tuple, ast.List))
        and len(target.elts) == len(value.elts)
    ):
        for child_target, child_value in zip(target.elts, value.elts, strict=True):
            assigned = _assigned_value(child_target, child_value, name)
            if assigned is not None:
                return assigned
    return None


def _writes_for_name(nodes: tuple[ast.AST, ...], name: str) -> list[tuple[ast.AST, ast.expr | None]]:
    writes: list[tuple[ast.AST, ast.expr | None]] = []
    for node in nodes:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if name in _target_names(target):
                    writes.append((node, _assigned_value(target, node.value, name)))
                    break
        elif isinstance(node, ast.AnnAssign):
            if name in _target_names(node.target):
                writes.append((node, _assigned_value(node.target, node.value, name)))
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name) and node.target.id == name:
            writes.append((node, node.value))
        elif isinstance(node, (ast.For, ast.AsyncFor)) and name in _target_names(node.target):
            writes.append((node, None))
    return writes


def _last_direct_write(
    statements: list[ast.stmt], name: str
) -> tuple[ast.Assign | ast.AnnAssign, ast.AST | None] | None:
    for statement in reversed(statements):
        if isinstance(statement, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in statement.targets):
                return statement, statement.value
            continue
        if isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.target.id == name:
                return statement, statement.value
            continue
        if any(
            isinstance(candidate, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in (candidate.targets if isinstance(candidate, ast.Assign) else (candidate.target,))
            )
            for candidate in ast.walk(statement)
        ):
            return None
    return None


def _write_may_not_reach_use(node: ast.AST, use_node: ast.AST, nodes: tuple[ast.AST, ...]) -> bool:
    """Return whether control flow can bypass a write before the named use."""
    for container in nodes:
        if container is node or not _contains_node(container, node) or _contains_node(container, use_node):
            continue
        if isinstance(container, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Match)):
            return True
        if isinstance(container, (ast.Try, ast.TryStar)):
            write_is_on_normal_path = any(
                _contains_node(statement, node) for statement in (*container.body, *container.orelse)
            )
            handlers_terminate = bool(container.handlers) and all(
                _block_terminates(handler.body) for handler in container.handlers
            )
            if not write_is_on_normal_path or not handlers_terminate:
                return True
    return False


def _verdicts_at_use(
    name: str,
    use_node: ast.AST,
    nodes: tuple[ast.AST, ...],
    verdicts: frozenset[str],
) -> tuple[str, ...]:
    """Resolve a verdict name from its reaching write at one use site."""
    assignments = [
        (node, value)
        for node, value in _writes_for_name(nodes, name)
        if not (
            isinstance(node, (ast.For, ast.AsyncFor))
            and any(_contains_node(statement, use_node) for statement in node.body)
        )
    ]
    preceding = [(node, value) for node, value in assignments if _position(node) < _position(use_node)]
    if preceding:
        assignment, value = max(preceding, key=lambda item: _position(item[0]))
        if isinstance(assignment, (ast.For, ast.AsyncFor)):
            return ()
        if value is None or _write_may_not_reach_use(assignment, use_node, nodes):
            return ()
        return _literal_verdicts(value, verdicts)
    if assignments:
        return ()
    for node in nodes:
        if (
            isinstance(node, (ast.For, ast.AsyncFor))
            and name in _target_names(node.target)
            and any(_contains_node(statement, use_node) for statement in node.body)
        ):
            return _literal_verdicts(node.iter, verdicts)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)) and _contains_node(
            node, use_node
        ):
            for generator in node.generators:
                if name in _target_names(generator.target) and not _contains_node(generator.iter, use_node):
                    return _literal_verdicts(generator.iter, verdicts)
    return ()


def _loaded_names(node: ast.AST) -> frozenset[str]:
    return frozenset(
        candidate.id
        for candidate in ast.walk(node)
        if isinstance(candidate, ast.Name) and isinstance(candidate.ctx, ast.Load)
    )


def _target_names(node: ast.expr) -> frozenset[str]:
    """Return names actually bound by an assignment target, not its receivers."""
    if isinstance(node, ast.Name):
        return frozenset({node.id})
    if isinstance(node, (ast.Tuple, ast.List)):
        return frozenset(name for element in node.elts for name in _target_names(element))
    if isinstance(node, ast.Starred):
        return _target_names(node.value)
    return frozenset[str]()


def _scopes(tree: ast.Module) -> tuple[ast.Module | ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    return (tree, *(node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))))


def _scope_index(
    tree: ast.Module,
) -> tuple[
    dict[int, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef],
    dict[int, tuple[ast.AST, ...]],
]:
    """Index every node under its closest function scope in one traversal."""
    mutable_nodes: dict[int, list[ast.AST]] = {id(scope): [] for scope in _scopes(tree)}
    scope_by_node: dict[int, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def visit(node: ast.AST, scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        scope_by_node[id(node)] = scope
        mutable_nodes[id(scope)].append(node)
        child_scope = node if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
        for child in ast.iter_child_nodes(node):
            visit(child, child_scope)

    visit(tree, tree)
    return scope_by_node, {scope_id: tuple(nodes) for scope_id, nodes in mutable_nodes.items()}


def _position(node: ast.AST) -> tuple[int, int]:
    return (int(getattr(node, "lineno", -1)), int(getattr(node, "col_offset", -1)))


def _subprocess_run_aliases(nodes: tuple[ast.AST, ...]) -> _SubprocessRunAliases:
    modules: set[str] = set()
    direct: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names if alias.name == "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            direct.update(alias.asname or alias.name for alias in node.names if alias.name == "run")
    return _SubprocessRunAliases(frozenset(modules), frozenset(direct))


def _subprocess_alias_reaches_use(
    name: str,
    *,
    direct: bool,
    use_node: ast.AST,
    nodes: tuple[ast.AST, ...],
    module_nodes: tuple[ast.AST, ...],
) -> bool:
    """Return whether the reaching binding is the requested subprocess import."""
    for candidate_nodes in (nodes, module_nodes):
        events: list[tuple[ast.AST, bool]] = []
        events.extend((write, False) for write, _ in _writes_for_name(candidate_nodes, name))
        for candidate in candidate_nodes:
            if isinstance(candidate, ast.Import):
                for alias in candidate.names:
                    bound = alias.asname or alias.name.partition(".")[0]
                    if bound == name:
                        events.append((candidate, not direct and alias.name == "subprocess"))
            elif isinstance(candidate, ast.ImportFrom):
                for alias in candidate.names:
                    bound = alias.asname or alias.name
                    if bound == name:
                        events.append((candidate, direct and candidate.module == "subprocess" and alias.name == "run"))
            else:
                shadows_name = (
                    (isinstance(candidate, ast.arg) and candidate.arg == name)
                    or (
                        isinstance(candidate, (ast.For, ast.AsyncFor, ast.comprehension))
                        and name in _target_names(candidate.target)
                    )
                    or (
                        isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        and candidate.name == name
                    )
                )
                if shadows_name:
                    events.append((candidate, False))
        if events:
            preceding = [
                (event, is_subprocess) for event, is_subprocess in events if _position(event) < _position(use_node)
            ]
            if not preceding:
                return False
            _, is_subprocess = max(preceding, key=lambda item: _position(item[0]))
            return is_subprocess
        if candidate_nodes is module_nodes:
            break
    return False


def _expression_mentions_marker(
    expression: ast.AST,
    use_node: ast.AST,
    nodes: tuple[ast.AST, ...],
    markers: frozenset[str],
    module_nodes: tuple[ast.AST, ...],
    resolving: frozenset[str] = frozenset(),
) -> bool:
    if any(marker in literal for marker in markers for literal in _literal_strings(expression)):
        return True
    for name in _loaded_names(expression):
        if name in resolving:
            continue
        for candidate_nodes in (nodes, module_nodes):
            writes = _writes_for_name(candidate_nodes, name)
            if candidate_nodes is module_nodes and len(writes) != 1:
                break
            preceding = [(write, value) for write, value in writes if _position(write) < _position(use_node)]
            if preceding:
                write, value = max(preceding, key=lambda item: _position(item[0]))
                if isinstance(write, (ast.For, ast.AsyncFor)):
                    if any(_contains_node(statement, use_node) for statement in write.body):
                        return _expression_mentions_marker(
                            write.iter,
                            write,
                            candidate_nodes,
                            markers,
                            module_nodes,
                            resolving | {name},
                        )
                    break
                if (
                    value is not None
                    and not _write_may_not_reach_use(write, use_node, candidate_nodes)
                    and _expression_mentions_marker(
                        value,
                        write,
                        candidate_nodes,
                        markers,
                        module_nodes,
                        resolving | {name},
                    )
                ):
                    return True
                break
            if writes:
                break
    return False


def _is_subprocess_output(
    node: ast.AST,
    aliases: _SubprocessRunAliases,
    markers: frozenset[str],
    module_nodes: tuple[ast.AST, ...],
    nodes: tuple[ast.AST, ...],
) -> bool:
    local_aliases = _subprocess_run_aliases(nodes)
    visible_aliases = _SubprocessRunAliases(
        modules=aliases.modules | local_aliases.modules,
        direct=aliases.direct | local_aliases.direct,
    )

    def is_declared_run(call: ast.Call) -> bool:
        callable_is_run = (
            isinstance(call.func, ast.Name)
            and call.func.id in visible_aliases.direct
            and _subprocess_alias_reaches_use(
                call.func.id,
                direct=True,
                use_node=call,
                nodes=nodes,
                module_nodes=module_nodes,
            )
        ) or (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in visible_aliases.modules
            and call.func.attr == "run"
            and _subprocess_alias_reaches_use(
                call.func.value.id,
                direct=False,
                use_node=call,
                nodes=nodes,
                module_nodes=module_nodes,
            )
        )
        if not callable_is_run:
            return False
        command = (
            call.args[0]
            if call.args
            else next(
                (keyword.value for keyword in call.keywords if keyword.arg == "args"),
                None,
            )
        )
        if command is None:
            return False
        executable = command.elts[0] if isinstance(command, (ast.List, ast.Tuple)) and command.elts else command
        return _expression_mentions_marker(executable, call, nodes, markers, module_nodes)

    if isinstance(node, ast.Call):
        if is_declared_run(node):
            return True
        return isinstance(node.func, ast.Attribute) and _is_subprocess_output(
            node.func.value, aliases, markers, module_nodes, nodes
        )
    if isinstance(node, ast.Subscript) and isinstance(node.value, (ast.Tuple, ast.List)):
        index: int | None = None
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
            index = node.slice.value
        elif (
            isinstance(node.slice, ast.UnaryOp)
            and isinstance(node.slice.op, ast.USub)
            and isinstance(node.slice.operand, ast.Constant)
            and isinstance(node.slice.operand.value, int)
        ):
            index = -node.slice.operand.value
        if index is not None and -len(node.value.elts) <= index < len(node.value.elts):
            return _is_subprocess_output(node.value.elts[index], aliases, markers, module_nodes, nodes)
        return False
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        return _is_subprocess_output(node.value, aliases, markers, module_nodes, nodes)
    if isinstance(node, ast.BinOp):
        return _is_subprocess_output(node.left, aliases, markers, module_nodes, nodes) or _is_subprocess_output(
            node.right, aliases, markers, module_nodes, nodes
        )
    if isinstance(node, ast.IfExp):
        return _is_subprocess_output(node.body, aliases, markers, module_nodes, nodes) and _is_subprocess_output(
            node.orelse, aliases, markers, module_nodes, nodes
        )
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(_is_subprocess_output(element, aliases, markers, module_nodes, nodes) for element in node.elts)
    return False


def _contains_node(container: ast.AST, candidate: ast.AST) -> bool:
    return any(node is candidate for node in ast.walk(container))


def _expression_is_gate_output(
    expression: ast.AST,
    use_node: ast.AST,
    scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    nodes: tuple[ast.AST, ...],
    parameters: dict[int, frozenset[str]],
    aliases: _SubprocessRunAliases,
    markers: frozenset[str],
    module_nodes: tuple[ast.AST, ...],
) -> bool:
    if _is_subprocess_output(expression, aliases, markers, module_nodes, nodes):
        return True
    return any(
        _name_is_gate_output(name, use_node, scope, nodes, parameters, aliases, markers, module_nodes)
        for name in _loaded_names(expression)
    )


def _name_is_gate_output(
    name: str,
    use_node: ast.AST,
    scope: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    nodes: tuple[ast.AST, ...],
    parameters: dict[int, frozenset[str]],
    aliases: _SubprocessRunAliases,
    markers: frozenset[str],
    module_nodes: tuple[ast.AST, ...],
) -> bool:
    assignments = [
        (node, value)
        for node, value in _writes_for_name(nodes, name)
        if not (
            isinstance(node, (ast.For, ast.AsyncFor))
            and any(_contains_node(statement, use_node) for statement in node.body)
        )
    ]
    preceding = [(node, value) for node, value in assignments if _position(node) < _position(use_node)]
    if preceding:
        assignment, value = max(preceding, key=lambda item: _position(item[0]))
        if isinstance(assignment, (ast.For, ast.AsyncFor)):
            return False
        for container in nodes:
            if (
                isinstance(container, ast.If)
                and not _contains_node(container, use_node)
                and _contains_node(container, assignment)
            ):
                body_write = _last_direct_write(container.body, name)
                else_write = _last_direct_write(container.orelse, name)
                if body_write is None or else_write is None:
                    return False
                return all(
                    branch_value is not None
                    and _expression_is_gate_output(
                        branch_value,
                        branch_write,
                        scope,
                        nodes,
                        parameters,
                        aliases,
                        markers,
                        module_nodes,
                    )
                    for branch_write, branch_value in (body_write, else_write)
                )
        if _write_may_not_reach_use(assignment, use_node, nodes):
            return False
        return value is not None and _expression_is_gate_output(
            value, assignment, scope, nodes, parameters, aliases, markers, module_nodes
        )
    if assignments:
        return False
    for node in nodes:
        if isinstance(node, (ast.For, ast.AsyncFor)) and name in _target_names(node.target):
            if any(_contains_node(statement, use_node) for statement in node.body):
                return _expression_is_gate_output(
                    node.iter, node, scope, nodes, parameters, aliases, markers, module_nodes
                )
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)) and _contains_node(
            node, use_node
        ):
            for generator in node.generators:
                if (
                    name in _target_names(generator.target)
                    and use_node is not generator
                    and not _contains_node(generator.iter, use_node)
                ):
                    return _expression_is_gate_output(
                        generator.iter,
                        generator.iter,
                        scope,
                        nodes,
                        parameters,
                        aliases,
                        markers,
                        module_nodes,
                    )
    return name in parameters[id(scope)]


def _derived_gate_output_parameters(
    tree: ast.Module,
    scope_by_node: dict[int, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef],
    nodes_by_scope: dict[int, tuple[ast.AST, ...]],
    aliases: _SubprocessRunAliases,
    markers: frozenset[str],
    module_nodes: tuple[ast.AST, ...],
) -> dict[int, frozenset[str]]:
    """Propagate source-order-aware gate output arguments into local helpers."""
    scopes = _scopes(tree)
    functions = {scope.name: scope for scope in scopes if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))}
    mutable: dict[int, set[str]] = {id(scope): set() for scope in scopes}
    while True:
        parameters = {scope_id: frozenset(names) for scope_id, names in mutable.items()}
        additions: set[tuple[int, str]] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id not in functions:
                continue
            caller = scope_by_node[id(node)]
            callee = functions[node.func.id]
            positional = tuple(callee.args.posonlyargs) + tuple(callee.args.args)
            for argument, parameter in zip(node.args, positional, strict=False):
                if _expression_is_gate_output(
                    argument,
                    node,
                    caller,
                    nodes_by_scope[id(caller)],
                    parameters,
                    aliases,
                    markers,
                    module_nodes,
                ):
                    additions.add((id(callee), parameter.arg))
        pending = {(scope_id, name) for scope_id, name in additions if name not in mutable[scope_id]}
        if not pending:
            return parameters
        for scope_id, name in pending:
            mutable[scope_id].add(name)


def scan_gate_verdict_grammar(path: Path, source: str) -> tuple[WeakGateVerdictPredicate, ...]:
    """Return weak predicates against every gate grammar named by one module."""
    tree = ast.parse(source, filename=str(path))
    findings: list[WeakGateVerdictPredicate] = []
    scope_by_node, nodes_by_scope = _scope_index(tree)
    aliases = _subprocess_run_aliases(nodes_by_scope[id(tree)])
    for grammar in _grammars_for(tree):
        module_nodes = nodes_by_scope[id(tree)]
        derived_parameters = _derived_gate_output_parameters(
            tree, scope_by_node, nodes_by_scope, aliases, grammar.markers, module_nodes
        )
        for node in ast.walk(tree):
            scope = scope_by_node[id(node)]
            receiver_is_gate_output = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and _expression_is_gate_output(
                    node.func.value,
                    node,
                    scope,
                    nodes_by_scope[id(scope)],
                    derived_parameters,
                    aliases,
                    grammar.markers,
                    module_nodes,
                )
            )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"startswith", "endswith"}
                and node.args
                and not node.keywords
                and receiver_is_gate_output
            ):
                literal_verdicts = _literal_verdicts(node.args[0], grammar.verdicts)
                if isinstance(node.args[0], ast.Name):
                    literal_verdicts = _verdicts_at_use(
                        node.args[0].id,
                        node,
                        nodes_by_scope[id(scope)],
                        grammar.verdicts,
                    )
                findings.extend(
                    WeakGateVerdictPredicate(
                        path=path,
                        lineno=node.lineno,
                        producer=grammar.producer,
                        predicate=node.func.attr,
                        verdict=verdict,
                    )
                    for verdict in literal_verdicts
                )
            if not (
                isinstance(node, ast.Compare)
                and len(node.ops) == 1
                and isinstance(node.ops[0], (ast.In, ast.NotIn))
                and len(node.comparators) == 1
            ):
                continue
            findings.extend(
                WeakGateVerdictPredicate(
                    path=path,
                    lineno=node.lineno,
                    producer=grammar.producer,
                    predicate="not in" if isinstance(node.ops[0], ast.NotIn) else "in",
                    verdict=verdict,
                )
                for verdict in _literal_verdicts(node.left, grammar.verdicts)
                if _expression_is_gate_output(
                    node.comparators[0],
                    node,
                    scope,
                    nodes_by_scope[id(scope)],
                    derived_parameters,
                    aliases,
                    grammar.markers,
                    module_nodes,
                )
            )
    return tuple(findings)


def scan_paths_for_gate_verdict_grammar(paths: tuple[Path, ...]) -> tuple[WeakGateVerdictPredicate, ...]:
    """Return weak gate-verdict predicates across the supplied modules."""
    findings: list[WeakGateVerdictPredicate] = []
    for path in paths:
        findings.extend(scan_gate_verdict_grammar(path, path.read_text(encoding="utf-8")))
    return tuple(findings)
