"""Typed submission-flow facts and static source scope helpers."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, TypeGuard

from cadrumo.entrypoints.tests.source_tree_support import NameOrigin

type Symbol = NameOrigin
"""A file and the qualified name of a function, method, class or binding it defines at module level."""

type ConstantToken = tuple[str, ...]
"""A constant an argument can be compared with: a literal, or one member of one class."""

type Function = ast.FunctionDef | ast.AsyncFunctionDef
type Trail = frozenset[tuple[Symbol, str]]

RECEIVER_NAMES: Final[frozenset[str]] = frozenset({"self", "cls"})
NO_TRAIL: Final[Trail] = frozenset[tuple[Symbol, str]]()


@dataclass(frozen=True, slots=True)
class Choice:
    """A value that depends on whether one parameter of the enclosing function equals a constant."""

    parameter: str
    constant: ConstantToken
    matching: FlowValue
    otherwise: FlowValue


@dataclass(frozen=True, slots=True)
class FlowValue:
    """What the source says an expression can evaluate to.

    ``constants`` are the string literals it can be; ``members`` are the
    literals of a collection it is selected from at run time; ``types`` are the
    classes its object is built from; ``parameters`` are the parameters of the
    enclosing function it may carry; ``choices`` are the values it takes
    depending on one such parameter. ``opaque`` records that some part of it
    reduces to none of these.
    """

    constants: frozenset[str] = frozenset()
    members: frozenset[str] = frozenset()
    types: frozenset[Symbol] = frozenset()
    parameters: frozenset[str] = frozenset()
    choices: frozenset[Choice] = frozenset()
    opaque: bool = False

    def __or__(self, other: FlowValue) -> FlowValue:
        """Return what either expression can evaluate to."""
        return FlowValue(
            constants=self.constants | other.constants,
            members=self.members | other.members,
            types=self.types | other.types,
            parameters=self.parameters | other.parameters,
            choices=self.choices | other.choices,
            opaque=self.opaque or other.opaque,
        )

    @property
    def depends_on_caller(self) -> bool:
        """Whether a caller's arguments still decide part of the value."""
        return bool(self.parameters or self.choices)

    def settled(self) -> FlowValue:
        """Return the value with every choice read as either branch."""
        value = FlowValue(
            constants=self.constants,
            members=self.members,
            types=self.types,
            parameters=self.parameters,
            opaque=self.opaque,
        )
        for choice in self.choices:
            value |= choice.matching.settled() | choice.otherwise.settled()
        return value

    def unsupplied(self) -> FlowValue:
        """Return the value as it stands when no caller supplies its parameters."""
        settled = self.settled()
        return FlowValue(
            constants=settled.constants,
            members=settled.members,
            types=settled.types,
            opaque=settled.opaque or bool(settled.parameters),
        )


NOTHING: Final[FlowValue] = FlowValue()
OPAQUE: Final[FlowValue] = FlowValue(opaque=True)


@dataclass(frozen=True, slots=True)
class Submission:
    """One submission a function can make, as far as its own parameters allow.

    ``site`` names the construction of the request record. ``identity`` is the
    value of its definition id and ``payload`` the value its payload was
    encoded from. ``guards`` name the class a parameter of the enclosing
    function must be an instance of for the submission to be reached at all.
    """

    site: str
    identity: FlowValue
    payload: FlowValue
    guards: frozenset[tuple[str, Symbol]] = frozenset()

    @property
    def depends_on_caller(self) -> bool:
        """Whether a caller's arguments still decide part of the submission."""
        return self.identity.depends_on_caller or self.payload.depends_on_caller or bool(self.guards)

    def unsupplied(self) -> Submission:
        """Read the submission as reached without a call: nothing supplies its parameters."""
        if not self.depends_on_caller:
            return self
        return Submission(site=self.site, identity=self.identity.unsupplied(), payload=self.payload.unsupplied())


@dataclass(frozen=True, slots=True)
class SubmissionReading:
    """The submissions of every symbol the reading walked from its entries.

    ``untyped_receivers`` names each method call whose receiver the source
    gives no class for, while a method of that name is known to submit: the
    reading cannot tell whether that call submits, so it reports the site
    rather than assume either answer.
    """

    submissions: Mapping[Symbol, frozenset[Submission]]
    untyped_receivers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModuleIndex:
    """The functions, methods, classes and bindings one file defines at module level."""

    functions: Mapping[str, Function]
    classes: Mapping[str, ast.ClassDef]
    bindings: Mapping[str, ast.expr]

    def defines(self, name: str) -> bool:
        """Check whether the module declares a name."""
        return name in self.functions or name in self.classes or name in self.bindings


@dataclass(frozen=True, slots=True)
class Scope:
    """The names one function or module-level binding can see as its own.

    ``assigned`` holds the values of names bound by a plain assignment and
    ``contexts`` the expressions a ``with`` statement bound a name from.
    ``rebound`` holds every name bound some other way -- unpacking, a loop, an
    inner function's parameter -- whose value this reading does not follow.
    """

    symbol: Symbol
    owner: Symbol | None
    function: Function | None
    parameters: Mapping[str, ast.arg] = field(default_factory=dict[str, ast.arg])
    assigned: Mapping[str, tuple[ast.expr, ...]] = field(default_factory=dict[str, tuple[ast.expr, ...]])
    contexts: Mapping[str, tuple[ast.expr, ...]] = field(default_factory=dict[str, tuple[ast.expr, ...]])
    rebound: frozenset[str] = frozenset()

    @property
    def path(self) -> str:
        """Return the source file for this scope."""
        return self.symbol[0]

    def binds(self, name: str) -> bool:
        """Check whether this scope binds a name."""
        return name in self.parameters or name in self.assigned or name in self.contexts or name in self.rebound

    def is_plain_parameter(self, name: str) -> bool:
        """Whether the name is a parameter the function never binds again."""
        return name in self.parameters and name not in self.assigned and name not in self.rebound


@dataclass(frozen=True, slots=True)
class Call:
    """One call to a scanned function, with whether its first positional parameter is already bound."""

    callee: Symbol
    node: ast.Call
    bound: bool


@dataclass(frozen=True, slots=True)
class Resolution:
    """The symbols a name or attribute can refer to.

    ``bound`` records that a call through it already binds the callee's first
    positional parameter. ``traced`` is false when the reading could not tell
    what the expression refers to at all, as distinct from referring to
    nothing it walks.
    """

    targets: tuple[Symbol, ...] = ()
    bound: bool = False
    traced: bool = True


UNRELATED: Final[Resolution] = Resolution()
UNTRACED: Final[Resolution] = Resolution(traced=False)


@dataclass(frozen=True, slots=True)
class Facts:
    """What one symbol's own source says, before any callee is consulted."""

    roots: tuple[Submission, ...] = ()
    calls: tuple[Call, ...] = ()
    references: frozenset[Symbol] = frozenset()
    untyped_calls: tuple[tuple[str, int], ...] = ()


def runs_a_coroutine(expression: ast.expr) -> TypeGuard[ast.Call]:
    """Whether an expression is ``asyncio.run(...)`` over exactly one coroutine."""
    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Attribute)
        and expression.func.attr == "run"
        and isinstance(expression.func.value, ast.Name)
        and expression.func.value.id == "asyncio"
        and len(expression.args) == 1
        and not expression.keywords
    )


def is_member(target: ast.expr, member: str) -> bool:
    """Whether an assignment target is ``self.member``."""
    return (
        isinstance(target, ast.Attribute)
        and target.attr == member
        and isinstance(target.value, ast.Name)
        and target.value.id in RECEIVER_NAMES
    )


def _record_assignment(
    node: ast.Assign | ast.AnnAssign | ast.NamedExpr, assigned: dict[str, list[ast.expr]], plain: set[int]
) -> None:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                assigned.setdefault(target.id, []).append(node.value)
                plain.add(id(target))
    elif isinstance(node, ast.AnnAssign | ast.NamedExpr) and isinstance(node.target, ast.Name):
        plain.add(id(node.target))
        if node.value is not None:
            assigned.setdefault(node.target.id, []).append(node.value)


def _record_scope_node(
    node: ast.AST,
    function: Function,
    assigned: dict[str, list[ast.expr]],
    contexts: dict[str, list[ast.expr]],
    plain: set[int],
    rebound: set[str],
) -> None:
    if isinstance(node, ast.Assign | ast.AnnAssign | ast.NamedExpr):
        _record_assignment(node, assigned, plain)
    elif isinstance(node, ast.withitem) and isinstance(node.optional_vars, ast.Name):
        contexts.setdefault(node.optional_vars.id, []).append(node.context_expr)
        plain.add(id(node.optional_vars))
    elif node is not function and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        inner = node.args
        rebound.update(
            argument.arg
            for argument in (*inner.posonlyargs, *inner.args, *inner.kwonlyargs, inner.vararg, inner.kwarg)
            if argument is not None
        )


def _rebound_names(nodes: tuple[ast.AST, ...], plain: set[int], rebound: set[str]) -> None:
    rebound.update(
        node.id
        for node in nodes
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and id(node) not in plain
    )


def function_scope(symbol: Symbol, owner: Symbol | None, function: Function) -> Scope:
    """Collect local bindings and rebinding evidence for a function."""
    arguments = function.args
    parameters = {
        argument.arg: argument for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
    }
    assigned: dict[str, list[ast.expr]] = {}
    contexts: dict[str, list[ast.expr]] = {}
    plain: set[int] = set()
    rebound: set[str] = {extra.arg for extra in (arguments.vararg, arguments.kwarg) if extra is not None}
    nodes = tuple(ast.walk(function))
    for node in nodes:
        _record_scope_node(node, function, assigned, contexts, plain, rebound)
    _rebound_names(nodes, plain, rebound)
    return Scope(
        symbol=symbol,
        owner=owner,
        function=function,
        parameters=parameters,
        assigned={name: tuple(values) for name, values in assigned.items()},
        contexts={name: tuple(values) for name, values in contexts.items()},
        rebound=frozenset(rebound),
    )


def nodes_outside_annotations(body: ast.AST) -> tuple[ast.AST, ...]:
    """List a body's nodes without its annotations: naming a class as a type neither calls nor constructs it."""
    nodes = tuple(ast.walk(body))
    skipped: set[int] = set()
    for node in nodes:
        annotation: ast.expr | None = None
        if isinstance(node, ast.arg | ast.AnnAssign):
            annotation = node.annotation
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            annotation = node.returns
        if annotation is not None:
            skipped.update(id(inner) for inner in ast.walk(annotation))
    return tuple(node for node in nodes if id(node) not in skipped)


def _positional_argument(call: Call, function: Function, parameter: str) -> ast.expr | None:
    positional = [argument.arg for argument in (*function.args.posonlyargs, *function.args.args)]
    if call.bound and positional and not is_static_method(function):
        positional = positional[1:]
    if parameter not in positional:
        return None
    position = positional.index(parameter)
    leading = call.node.args[: position + 1]
    if len(leading) <= position or any(isinstance(argument, ast.Starred) for argument in leading):
        return None
    return leading[position]


def supplied_argument(call: Call, function: Function, parameter: str) -> ast.expr | None:
    """Return the expression a call passes for one parameter, by keyword or by position."""
    for keyword in call.node.keywords:
        if keyword.arg == parameter:
            return keyword.value
    return _positional_argument(call, function, parameter)


def spreads_arguments(call: ast.Call) -> bool:
    """Check whether a call spreads arguments."""
    return any(keyword.arg is None for keyword in call.keywords) or any(
        isinstance(argument, ast.Starred) for argument in call.args
    )


def parameter_default(function: Function, parameter: str) -> ast.expr | None:
    """Find the default expression for a parameter."""
    arguments = function.args
    positional = [*arguments.posonlyargs, *arguments.args]
    defaults: dict[str, ast.expr] = {
        argument.arg: default
        for argument, default in zip(reversed(positional), reversed(arguments.defaults), strict=False)
    }
    defaults.update(
        {
            argument.arg: default
            for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
            if default is not None
        }
    )
    return defaults.get(parameter)


def is_static_method(function: Function) -> bool:
    """Check the function decorator for static method semantics."""
    return any(isinstance(item, ast.Name) and item.id == "staticmethod" for item in function.decorator_list)
