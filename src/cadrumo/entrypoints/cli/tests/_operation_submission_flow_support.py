"""Read, from source, which registered operations a function can submit.

Every submission to the runtime constructs one request record that names the
operation by its definition id and carries the encoded payload. This reading
starts at those constructions and follows both values back through the
functions that pass them along, so a command handler ends up with the
operations its reachable code can submit without anyone listing them.

The reading is static and deliberately modest. It follows a value through
parameters, plain local assignments, conditional expressions and module-level
constants; it follows a call through the name the caller imported, and a method
through the class its receiver is annotated with.

Two things narrow what a caller is read as reaching, and each needs the source
to say so outright. A conditional expression that tests one parameter against a
constant is kept as a choice, and settled where a caller passes that constant.
A parameter annotated with one concrete class is kept as a guard, and a caller
that constructs an object of an unrelated class is not read as reaching what
lies behind it. No other condition is evaluated, so a handler with several
modes is read as submitting every operation any mode reaches.

Where the definition id cannot be reduced to constants the reading says so and
keeps what it could learn instead: the collection the id was selected from, and
the classes the payload was built from. It never guesses.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Final, TypeGuard

from ...tests.source_tree_support import NameOrigin, SourceTree, module_level_bindings

type Symbol = NameOrigin
"""A file and the qualified name of a function, method, class or binding it defines at module level."""

type ConstantToken = tuple[str, ...]
"""A constant an argument can be compared with: a literal, or one member of one class."""

type _Function = ast.FunctionDef | ast.AsyncFunctionDef
type _Trail = frozenset[tuple[Symbol, str]]

_RECEIVER_NAMES: Final[frozenset[str]] = frozenset({"self", "cls"})
_NO_TRAIL: Final[_Trail] = frozenset[tuple[Symbol, str]]()


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


_NOTHING: Final[FlowValue] = FlowValue()
_OPAQUE: Final[FlowValue] = FlowValue(opaque=True)


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
class _ModuleIndex:
    """The functions, methods, classes and bindings one file defines at module level."""

    functions: Mapping[str, _Function]
    classes: Mapping[str, ast.ClassDef]
    bindings: Mapping[str, ast.expr]

    def defines(self, name: str) -> bool:
        return name in self.functions or name in self.classes or name in self.bindings


@dataclass(frozen=True, slots=True)
class _Scope:
    """The names one function or module-level binding can see as its own.

    ``assigned`` holds the values of names bound by a plain assignment and
    ``contexts`` the expressions a ``with`` statement bound a name from.
    ``rebound`` holds every name bound some other way -- unpacking, a loop, an
    inner function's parameter -- whose value this reading does not follow.
    """

    symbol: Symbol
    owner: Symbol | None
    function: _Function | None
    parameters: Mapping[str, ast.arg] = field(default_factory=dict[str, ast.arg])
    assigned: Mapping[str, tuple[ast.expr, ...]] = field(default_factory=dict[str, tuple[ast.expr, ...]])
    contexts: Mapping[str, tuple[ast.expr, ...]] = field(default_factory=dict[str, tuple[ast.expr, ...]])
    rebound: frozenset[str] = frozenset()

    @property
    def path(self) -> str:
        return self.symbol[0]

    def binds(self, name: str) -> bool:
        return name in self.parameters or name in self.assigned or name in self.contexts or name in self.rebound

    def is_plain_parameter(self, name: str) -> bool:
        """Whether the name is a parameter the function never binds again."""
        return name in self.parameters and name not in self.assigned and name not in self.rebound


@dataclass(frozen=True, slots=True)
class _Call:
    """One call to a scanned function, with whether its first positional parameter is already bound."""

    callee: Symbol
    node: ast.Call
    bound: bool


@dataclass(frozen=True, slots=True)
class _Resolution:
    """The symbols a name or attribute can refer to.

    ``bound`` records that a call through it already binds the callee's first
    positional parameter. ``traced`` is false when the reading could not tell
    what the expression refers to at all, as distinct from referring to
    nothing it walks.
    """

    targets: tuple[Symbol, ...] = ()
    bound: bool = False
    traced: bool = True


_UNRELATED: Final[_Resolution] = _Resolution()
_UNTRACED: Final[_Resolution] = _Resolution(traced=False)


@dataclass(frozen=True, slots=True)
class _Facts:
    """What one symbol's own source says, before any callee is consulted."""

    roots: tuple[Submission, ...] = ()
    calls: tuple[_Call, ...] = ()
    references: frozenset[Symbol] = frozenset()
    untyped_calls: tuple[tuple[str, int], ...] = ()


class SubmissionFlow:
    """Follow the definition id and payload of every submission back to the functions that supply them."""

    def __init__(
        self,
        tree: SourceTree,
        *,
        scanned: tuple[str, ...],
        submission: Symbol,
        identity_argument: str = "definition_id",
        payload_argument: str = "payload_json",
    ) -> None:
        """Bind the reading to its source tree and to the record every submission constructs.

        Args:
            tree: The source tree to read.
            scanned: Path prefixes of the packages whose functions are walked.
                A function elsewhere is never entered; a constant or a class
                elsewhere is still read when a walked function names it.
            submission: The class whose construction is a submission.
            identity_argument: The keyword that names the operation.
            payload_argument: The keyword that carries the encoded payload.
        """
        self._tree = tree
        self._scanned = scanned
        self._submission = submission
        self._identity_argument = identity_argument
        self._payload_argument = payload_argument
        self._indexes: dict[str, _ModuleIndex] = {}
        self._scopes: dict[Symbol, _Scope] = {}
        self._facts: dict[Symbol, _Facts] = {}
        self._receiver_classes: dict[tuple[Symbol, str], frozenset[Symbol]] = {}
        self._member_classes: dict[tuple[Symbol, str], frozenset[Symbol]] = {}
        self._required_classes: dict[Symbol, Mapping[str, Symbol]] = {}
        self._identities: dict[tuple[Symbol, int], FlowValue] = {}
        self._payloads: dict[tuple[Symbol, int], FlowValue] = {}

    def read(self, entries: Iterable[Symbol]) -> SubmissionReading:
        """Read the submissions of each entry and of everything it can reach."""
        reached = self.reach(entries)
        summaries = self._settle(reached)
        return SubmissionReading(
            submissions=summaries,
            untyped_receivers=self._untyped_receivers(reached, summaries),
        )

    def defines(self, symbol: Symbol) -> bool:
        """Whether the symbol is one this reading can enter."""
        return self._is_scanned(symbol[0]) and self._index(symbol[0]).defines(symbol[1])

    def symbols(self, path: str) -> tuple[Symbol, ...]:
        """Name every function, method and binding one scanned file defines at module level."""
        if not self._is_scanned(path):
            return ()
        index = self._index(path)
        return tuple((path, name) for name in (*index.functions, *index.bindings))

    def reach(self, entries: Iterable[Symbol]) -> tuple[Symbol, ...]:
        """Name every scanned symbol the entries can reach by call or by reference, entries included."""
        pending = list(entries)
        reached: dict[Symbol, None] = {}
        while pending:
            symbol = pending.pop()
            if symbol in reached or not self.defines(symbol):
                continue
            reached[symbol] = None
            facts = self._facts_of(symbol)
            pending.extend(call.callee for call in facts.calls)
            pending.extend(sorted(facts.references))
        return tuple(reached)

    def named_by(self, symbol: Symbol) -> frozenset[Symbol]:
        """Name every scanned symbol one symbol's own code calls or refers to."""
        if not self.defines(symbol):
            return frozenset[Symbol]()
        facts = self._facts_of(symbol)
        return frozenset({call.callee for call in facts.calls} | facts.references)

    # -- the fixed point ----------------------------------------------------

    def _settle(self, reached: tuple[Symbol, ...]) -> dict[Symbol, frozenset[Submission]]:
        summaries = {symbol: frozenset(self._facts_of(symbol).roots) for symbol in reached}
        changed = True
        while changed:
            changed = False
            for symbol in reached:
                facts = self._facts_of(symbol)
                current = summaries[symbol]
                grown = set(current)
                for call in facts.calls:
                    bound = (self._bound(symbol, call, submission) for submission in summaries.get(call.callee, ()))
                    grown.update(submission for submission in bound if submission is not None)
                for reference in facts.references:
                    grown.update(submission.unsupplied() for submission in summaries.get(reference, ()))
                if len(grown) != len(current):
                    summaries[symbol] = frozenset(grown)
                    changed = True
        return summaries

    def _bound(self, caller: Symbol, call: _Call, submission: Submission) -> Submission | None:
        """Rewrite a callee's submission in terms of the caller's own values.

        Returns nothing when the call cannot reach the submission: the caller
        passes an object of a class the submission's path does not accept.
        """
        function = self._index(call.callee[0]).functions.get(call.callee[1])
        if function is None:
            return submission.unsupplied()
        scope = self._scope(caller)
        guards: set[tuple[str, Symbol]] = set()
        for parameter, required in sorted({*self._required(call.callee).items(), *submission.guards}):
            supplied = _supplied_argument(call, function, parameter)
            if supplied is None:
                continue
            constructed = self._constructed_classes(scope, supplied, _NO_TRAIL)
            if constructed is not None and not any(self._inherits(cls, required) for cls in constructed):
                return None
            if isinstance(supplied, ast.Name) and scope.is_plain_parameter(supplied.id):
                guards.add((supplied.id, required))
        return Submission(
            site=submission.site,
            identity=self._bound_value(scope, call, function, submission.identity, identity=True),
            payload=self._bound_value(scope, call, function, submission.payload, identity=False),
            guards=frozenset(guards),
        )

    def _required(self, callee: Symbol) -> Mapping[str, Symbol]:
        """Name each parameter a function annotates with exactly one concrete class of the tree."""
        required = self._required_classes.get(callee)
        if required is None:
            arguments = self._index(callee[0]).functions[callee[1]].args
            module = self._module_scope(callee[0])
            found: dict[str, Symbol] = {}
            for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
                annotation = argument.annotation
                if isinstance(annotation, ast.Name):
                    cls = self._class_named(module, annotation.id)
                    if cls is not None and not self._is_structural(cls):
                        found[argument.arg] = cls
            required = found
            self._required_classes[callee] = required
        return required

    def _is_structural(self, cls: Symbol) -> bool:
        """Whether a class is a protocol, which an instance satisfies without inheriting from it."""
        return any(
            isinstance(node, ast.Name) and node.id == "Protocol"
            for base in self._index(cls[0]).classes[cls[1]].bases
            for node in ast.walk(base)
        )

    def _inherits(self, cls: Symbol, ancestor: Symbol) -> bool:
        pending = [cls]
        seen: set[Symbol] = set()
        while pending:
            current = pending.pop()
            if current == ancestor:
                return True
            if current not in seen:
                seen.add(current)
                pending.extend(self._bases(current))
        return False

    def _constructed_classes(self, scope: _Scope, expression: ast.expr, trail: _Trail) -> frozenset[Symbol] | None:
        """Name the exact classes an expression constructs, or nothing when the source does not show them.

        Only a construction counts. A declared return type says what an object
        is at least, not what it is, so it cannot rule a call out.
        """
        if isinstance(expression, ast.IfExp):
            first = self._constructed_classes(scope, expression.body, trail)
            second = self._constructed_classes(scope, expression.orelse, trail)
            return None if first is None or second is None else first | second
        if isinstance(expression, ast.Call):
            targets = self._resolve(scope, expression.func).targets
            classes = frozenset(target for target in targets if target[1] in self._index(target[0]).classes)
            return classes if classes and len(classes) == len(targets) else None
        if not isinstance(expression, ast.Name) or (scope.symbol, expression.id) in trail:
            return None
        name = expression.id
        assigned = scope.assigned.get(name, ())
        if not assigned or name in scope.parameters or name in scope.rebound or name in scope.contexts:
            return None
        constructed: set[Symbol] = set()
        for value in assigned:
            classes = self._constructed_classes(scope, value, trail | {(scope.symbol, name)})
            if classes is None:
                return None
            constructed |= classes
        return frozenset(constructed)

    def _bound_value(
        self, scope: _Scope, call: _Call, function: _Function, value: FlowValue, *, identity: bool
    ) -> FlowValue:
        bound = FlowValue(constants=value.constants, members=value.members, types=value.types, opaque=value.opaque)
        for parameter in sorted(value.parameters):
            bound |= self._argument(scope, call, function, parameter, identity=identity)
        for choice in value.choices:
            matching = self._bound_value(scope, call, function, choice.matching, identity=identity)
            otherwise = self._bound_value(scope, call, function, choice.otherwise, identity=identity)
            bound |= self._chosen(scope, call, function, choice, matching, otherwise)
        return bound

    def _chosen(
        self, scope: _Scope, call: _Call, function: _Function, choice: Choice, matching: FlowValue, otherwise: FlowValue
    ) -> FlowValue:
        """Settle a choice where the caller passes a constant, and pass it on where it passes a parameter."""
        supplied = _supplied_argument(call, function, choice.parameter)
        argument_scope = scope
        if supplied is None and not _spreads_arguments(call.node):
            supplied = _parameter_default(function, choice.parameter)
            argument_scope = self._module_scope(call.callee[0])
        if supplied is None:
            return matching | otherwise
        token = self._constant_token(argument_scope, supplied)
        if token is not None:
            return matching if token == choice.constant else otherwise
        if isinstance(supplied, ast.Name) and argument_scope.is_plain_parameter(supplied.id):
            return FlowValue(choices=frozenset({Choice(supplied.id, choice.constant, matching, otherwise)}))
        return matching | otherwise

    def _argument(
        self, scope: _Scope, call: _Call, function: _Function, parameter: str, *, identity: bool
    ) -> FlowValue:
        """Return the value the caller supplies for one of the callee's parameters."""
        supplied = _supplied_argument(call, function, parameter)
        if supplied is not None:
            return self._identity(scope, supplied) if identity else self._payload(scope, supplied)
        default = None if _spreads_arguments(call.node) else _parameter_default(function, parameter)
        if default is None:
            return _OPAQUE
        callee_module = self._module_scope(call.callee[0])
        return self._identity(callee_module, default) if identity else self._payload(callee_module, default)

    def _untyped_receivers(
        self, reached: tuple[Symbol, ...], summaries: Mapping[Symbol, frozenset[Submission]]
    ) -> tuple[str, ...]:
        submitting = {
            symbol[1].rpartition(".")[2]: symbol
            for symbol in reached
            if "." in symbol[1] and bool(summaries.get(symbol))
        }
        return tuple(
            f"{symbol[0]}:{line} calls .{name}() on a receiver of unknown class, "
            f"while {submitting[name][0]}:{submitting[name][1]} submits"
            for symbol in reached
            for name, line in self._facts_of(symbol).untyped_calls
            if name in submitting
        )

    # -- the module index and scopes --------------------------------------

    def _is_scanned(self, path: str) -> bool:
        return path.startswith(self._scanned)

    def _index(self, path: str) -> _ModuleIndex:
        index = self._indexes.get(path)
        if index is None:
            module = self._tree.parsed(path)
            functions: dict[str, _Function] = {}
            classes: dict[str, ast.ClassDef] = {}
            for node in module.body:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    functions[node.name] = node
                elif isinstance(node, ast.ClassDef):
                    classes[node.name] = node
                    for member in node.body:
                        if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                            functions[f"{node.name}.{member.name}"] = member
            index = _ModuleIndex(functions=functions, classes=classes, bindings=dict(module_level_bindings(module)))
            self._indexes[path] = index
        return index

    def _origin(self, path: str, name: str) -> Symbol | None:
        """Resolve a name used in a file to the module-level symbol that defines it.

        A scanned file is checked to define the name, and an import it merely
        passes along is followed. A file outside the scanned packages is taken
        at its word, so naming one of its symbols never costs a parse; whoever
        needs to know what kind of symbol it is reads the file then.
        """
        origin = self._tree.name_origins(path).get(name)
        seen: set[Symbol] = set()
        while origin is not None and origin not in seen:
            seen.add(origin)
            if not self._is_scanned(origin[0]) or self._index(origin[0]).defines(origin[1]):
                return origin
            origin = self._tree.name_origins(origin[0]).get(origin[1])
        return None

    def _class_named(self, scope: _Scope, name: str) -> Symbol | None:
        """Resolve a name to a class of the tree, unless the scope binds the name itself."""
        if scope.binds(name):
            return None
        origin = self._origin(scope.path, name)
        if origin is None or origin[1] not in self._index(origin[0]).classes:
            return None
        return origin

    def _module_scope(self, path: str) -> _Scope:
        return _Scope(symbol=(path, ""), owner=None, function=None)

    def _scope(self, symbol: Symbol) -> _Scope:
        scope = self._scopes.get(symbol)
        if scope is None:
            path, name = symbol
            function = self._index(path).functions.get(name)
            owner = (path, name.rpartition(".")[0]) if "." in name else None
            scope = (
                _Scope(symbol=symbol, owner=owner, function=None)
                if function is None
                else _function_scope(symbol, owner, function)
            )
            self._scopes[symbol] = scope
        return scope

    # -- what a symbol's own source says ----------------------------------

    def _facts_of(self, symbol: Symbol) -> _Facts:
        facts = self._facts.get(symbol)
        if facts is None:
            facts = self._read_facts(symbol)
            self._facts[symbol] = facts
        return facts

    def _read_facts(self, symbol: Symbol) -> _Facts:
        path, name = symbol
        index = self._index(path)
        if name in index.classes:
            return _Facts(references=self._class_references(symbol))
        scope = self._scope(symbol)
        body: ast.AST | None = scope.function if scope.function is not None else index.bindings.get(name)
        if body is None:
            return _Facts()
        roots: list[Submission] = []
        calls: list[_Call] = []
        references: set[Symbol] = set()
        untyped: list[tuple[str, int]] = []
        nodes = _nodes_outside_annotations(body)
        called = {id(node.func): node for node in nodes if isinstance(node, ast.Call)}
        for node in nodes:
            if isinstance(node, ast.Call) and self._is_submission(scope, node.func):
                roots.append(self._root(scope, node))
                continue
            if not isinstance(node, ast.Name | ast.Attribute):
                continue
            resolution = self._resolve(scope, node)
            call = called.get(id(node))
            if call is not None and not resolution.traced and isinstance(node, ast.Attribute):
                untyped.append((node.attr, node.lineno))
            for target in resolution.targets:
                if not self.defines(target):
                    continue
                if call is not None and target[1] in self._index(target[0]).functions:
                    calls.append(_Call(callee=target, node=call, bound=resolution.bound))
                else:
                    references.add(target)
        return _Facts(
            roots=tuple(roots), calls=tuple(calls), references=frozenset(references), untyped_calls=tuple(untyped)
        )

    def _class_references(self, symbol: Symbol) -> frozenset[Symbol]:
        """A class constructed or entered runs its special methods, and those of its bases."""
        path, name = symbol
        index = self._index(path)
        references: set[Symbol] = {
            (path, qualified)
            for qualified in index.functions
            if qualified.startswith(f"{name}.__") and qualified.endswith("__")
        }
        references.update(self._bases(symbol))
        return frozenset(references)

    def _bases(self, symbol: Symbol) -> Iterator[Symbol]:
        definition = self._index(symbol[0]).classes.get(symbol[1])
        if definition is None:
            return
        for base in definition.bases:
            if isinstance(base, ast.Name):
                origin = self._origin(symbol[0], base.id)
                if origin is not None:
                    yield origin

    def _is_submission(self, scope: _Scope, callee: ast.expr) -> bool:
        return self._submission in self._resolve(scope, callee).targets

    def _root(self, scope: _Scope, call: ast.Call) -> Submission:
        keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}
        identity = keywords.get(self._identity_argument)
        payload = keywords.get(self._payload_argument)
        return Submission(
            site=f"{scope.path}:{call.lineno}",
            identity=_OPAQUE if identity is None else self._identity(scope, identity),
            payload=_OPAQUE if payload is None else self._payload(scope, payload),
        )

    def _resolve(self, scope: _Scope, node: ast.AST) -> _Resolution:
        """Resolve a name or attribute to the symbols it can refer to."""
        if isinstance(node, ast.Name):
            if not isinstance(node.ctx, ast.Load) or scope.binds(node.id):
                return _UNRELATED
            origin = self._origin(scope.path, node.id)
            return _UNRELATED if origin is None else _Resolution(targets=(origin,))
        if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Load):
            return _UNRELATED
        receiver = node.value
        if isinstance(receiver, ast.Attribute):
            return self._resolve_member_method(scope, receiver, node.attr)
        if not isinstance(receiver, ast.Name):
            return _UNTRACED
        if receiver.id in _RECEIVER_NAMES and scope.owner is not None:
            return self._methods((scope.owner,), node.attr)
        if scope.binds(receiver.id):
            classes = self._classes_of_name(scope, receiver.id)
            return self._methods(tuple(sorted(classes)), node.attr) if classes else _UNTRACED
        module = self._tree.module_aliases(scope.path).get(receiver.id)
        if module is not None:
            return _Resolution(targets=((module, node.attr),)) if self._index(module).defines(node.attr) else _UNRELATED
        origin = self._class_named(scope, receiver.id)
        method = None if origin is None else self._method(origin, node.attr)
        if method is None:
            return _UNRELATED
        return _Resolution(targets=(method,), bound=self._is_class_method(method))

    def _resolve_member_method(self, scope: _Scope, receiver: ast.Attribute, name: str) -> _Resolution:
        """Resolve ``self.member.name`` through the class the member is declared or assigned as."""
        holder = receiver.value
        if not isinstance(holder, ast.Name) or holder.id not in _RECEIVER_NAMES or scope.owner is None:
            return _UNTRACED
        classes = self._classes_of_member(scope.owner, receiver.attr)
        return self._methods(tuple(sorted(classes)), name) if classes else _UNTRACED

    def _methods(self, classes: tuple[Symbol, ...], name: str) -> _Resolution:
        methods = (self._method(cls, name) for cls in classes)
        return _Resolution(targets=tuple(method for method in methods if method is not None), bound=True)

    def _method(self, cls: Symbol, name: str) -> Symbol | None:
        """Find a method on a class or the nearest base that defines it."""
        pending = [cls]
        seen: set[Symbol] = set()
        while pending:
            current = pending.pop(0)
            if current in seen:
                continue
            seen.add(current)
            if f"{current[1]}.{name}" in self._index(current[0]).functions:
                return (current[0], f"{current[1]}.{name}")
            pending.extend(self._bases(current))
        return None

    def _is_class_method(self, method: Symbol) -> bool:
        function = self._index(method[0]).functions[method[1]]
        return any(isinstance(item, ast.Name) and item.id == "classmethod" for item in function.decorator_list)

    # -- the class of a receiver ------------------------------------------

    def _classes_of_name(self, scope: _Scope, name: str) -> frozenset[Symbol]:
        key = (scope.symbol, name)
        known = self._receiver_classes.get(key)
        if known is None:
            # A name assigned from a call on itself would otherwise ask for its own class forever.
            self._receiver_classes[key] = frozenset()
            known = self._read_classes_of_name(scope, name)
            self._receiver_classes[key] = known
        return known

    def _read_classes_of_name(self, scope: _Scope, name: str) -> frozenset[Symbol]:
        classes: set[Symbol] = set()
        parameter = scope.parameters.get(name)
        if parameter is not None and parameter.annotation is not None:
            classes.update(self._annotated_classes(scope.path, parameter.annotation))
        for source in (*scope.assigned.get(name, ()), *scope.contexts.get(name, ())):
            classes.update(self._classes_of_expression(scope, source))
        return frozenset(classes)

    def _classes_of_member(self, owner: Symbol, member: str) -> frozenset[Symbol]:
        """Name the classes an instance attribute holds, from its declaration and from what is assigned to it."""
        key = (owner, member)
        known = self._member_classes.get(key)
        if known is not None:
            return known
        self._member_classes[key] = frozenset()
        path, name = owner
        index = self._index(path)
        classes: set[Symbol] = set()
        definition = index.classes.get(name)
        for node in () if definition is None else definition.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == member:
                classes.update(self._annotated_classes(path, node.annotation))
        for qualified, function in index.functions.items():
            if qualified.rpartition(".")[0] != name:
                continue
            method_scope = self._scope((path, qualified))
            for node in ast.walk(function):
                if isinstance(node, ast.AnnAssign) and _is_member(node.target, member):
                    classes.update(self._annotated_classes(path, node.annotation))
                elif isinstance(node, ast.Assign) and any(_is_member(target, member) for target in node.targets):
                    classes.update(self._classes_of_expression(method_scope, node.value))
        known = frozenset(classes)
        self._member_classes[key] = known
        return known

    def _classes_of_expression(self, scope: _Scope, expression: ast.expr) -> frozenset[Symbol]:
        if isinstance(expression, ast.Await):
            expression = expression.value
        elif _runs_a_coroutine(expression):
            # ``asyncio.run`` returns what the coroutine it is handed returns, as ``await`` does.
            expression = expression.args[0]
        if isinstance(expression, ast.Name) and scope.binds(expression.id):
            return self._classes_of_name(scope, expression.id)
        if not isinstance(expression, ast.Call):
            return frozenset[Symbol]()
        classes: set[Symbol] = set()
        for target in self._resolve(scope, expression.func).targets:
            index = self._index(target[0])
            if target[1] in index.classes:
                classes.add(target)
                continue
            function = index.functions.get(target[1])
            if function is not None and function.returns is not None:
                classes.update(self._annotated_classes(target[0], function.returns))
        return frozenset(classes)

    def _annotated_classes(self, path: str, annotation: ast.expr) -> frozenset[Symbol]:
        """Every class of the tree an annotation names, however it wraps them."""
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode="eval").body
            except SyntaxError:
                return frozenset[Symbol]()
        classes: set[Symbol] = set()
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name):
                origin = self._origin(path, node.id)
                if origin is not None and origin[1] in self._index(origin[0]).classes:
                    classes.add(origin)
        return frozenset(classes)

    # -- constants a choice can turn on -----------------------------------

    def _constant_token(self, scope: _Scope, expression: ast.expr) -> ConstantToken | None:
        """Reduce an expression to the constant it names, or to nothing when it names none."""
        if isinstance(expression, ast.Constant):
            return ("literal", repr(expression.value))
        if isinstance(expression, ast.Name) and not scope.binds(expression.id):
            origin = self._origin(scope.path, expression.id)
            binding = None if origin is None else self._index(origin[0]).bindings.get(origin[1])
            return ("literal", repr(binding.value)) if isinstance(binding, ast.Constant) else None
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            owner = self._class_named(scope, expression.value.id)
            if owner is None:
                return None
            return (*owner, self._member_spelling(owner, expression.attr))
        return None

    def _member_spelling(self, owner: Symbol, member: str) -> str:
        """Spell a class member by its value, so two names for one value read as the same constant."""
        definition = self._index(owner[0]).classes[owner[1]]
        for name, value in module_level_bindings(ast.Module(body=definition.body, type_ignores=[])):
            if name == member:
                return ast.dump(value)
        return member

    def _choice(self, scope: _Scope, expression: ast.IfExp, trail: _Trail) -> FlowValue | None:
        """Read ``a if parameter == CONSTANT else b`` as a choice on that parameter."""
        test = expression.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1:
            return None
        operator = test.ops[0]
        if not isinstance(operator, ast.Eq | ast.Is | ast.NotEq | ast.IsNot):
            return None
        for subject, constant in ((test.left, test.comparators[0]), (test.comparators[0], test.left)):
            if not isinstance(subject, ast.Name) or not scope.is_plain_parameter(subject.id):
                continue
            token = self._constant_token(scope, constant)
            if token is None:
                continue
            matching = self._read_identity(scope, expression.body, trail)
            otherwise = self._read_identity(scope, expression.orelse, trail)
            if isinstance(operator, ast.NotEq | ast.IsNot):
                matching, otherwise = otherwise, matching
            return FlowValue(choices=frozenset({Choice(subject.id, token, matching, otherwise)}))
        return None

    # -- the value of a definition id -------------------------------------

    def _identity(self, scope: _Scope, expression: ast.expr) -> FlowValue:
        key = (scope.symbol, id(expression))
        value = self._identities.get(key)
        if value is None:
            value = self._read_identity(scope, expression, _NO_TRAIL)
            self._identities[key] = value
        return value

    def _read_identity(self, scope: _Scope, expression: ast.expr, trail: _Trail) -> FlowValue:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return FlowValue(constants=frozenset({expression.value}))
        if isinstance(expression, ast.IfExp):
            choice = self._choice(scope, expression, trail)
            if choice is not None:
                return choice
            return self._read_identity(scope, expression.body, trail) | self._read_identity(
                scope, expression.orelse, trail
            )
        if isinstance(expression, ast.Name):
            return self._identity_of_name(scope, expression.id, trail)
        if isinstance(expression, ast.Subscript):
            selected = self._members(scope, expression.value, trail).settled()
            return FlowValue(members=selected.constants | selected.members, opaque=True)
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            module = self._tree.module_aliases(scope.path).get(expression.value.id)
            if module is not None and not scope.binds(expression.value.id):
                return self._identity_of_binding((module, expression.attr), trail)
        return _OPAQUE

    def _members(self, scope: _Scope, container: ast.expr, trail: _Trail) -> FlowValue:
        """Read the values a subscripted collection can yield, when its literal is in the source."""
        if isinstance(container, ast.Dict):
            values = list(container.values)
        elif isinstance(container, ast.Tuple | ast.List):
            values = list(container.elts)
        elif isinstance(container, ast.Name) and not scope.binds(container.id):
            origin = self._origin(scope.path, container.id)
            binding = None if origin is None else self._index(origin[0]).bindings.get(origin[1])
            if origin is None or binding is None or (origin, container.id) in trail:
                return _NOTHING
            return self._members(self._module_scope(origin[0]), binding, trail | {(origin, container.id)})
        else:
            return _NOTHING
        found = _NOTHING
        for value in values:
            found |= self._read_identity(scope, value, trail)
        return found

    def _identity_of_name(self, scope: _Scope, name: str, trail: _Trail) -> FlowValue:
        if (scope.symbol, name) in trail:
            return _NOTHING
        if not scope.binds(name):
            origin = self._origin(scope.path, name)
            return _OPAQUE if origin is None else self._identity_of_binding(origin, trail)
        value = FlowValue(opaque=name in scope.rebound or name in scope.contexts)
        if name in scope.parameters:
            value |= FlowValue(parameters=frozenset({name}))
        for assigned in scope.assigned.get(name, ()):
            value |= self._read_identity(scope, assigned, trail | {(scope.symbol, name)})
        return value

    def _identity_of_binding(self, origin: Symbol, trail: _Trail) -> FlowValue:
        binding = self._index(origin[0]).bindings.get(origin[1])
        if binding is None or (origin, origin[1]) in trail:
            return _OPAQUE
        return self._read_identity(self._module_scope(origin[0]), binding, trail | {(origin, origin[1])})

    # -- the classes a payload is built from ------------------------------

    def _payload(self, scope: _Scope, expression: ast.expr) -> FlowValue:
        key = (scope.symbol, id(expression))
        value = self._payloads.get(key)
        if value is None:
            value = self._read_payload(scope, expression, _NO_TRAIL)
            self._payloads[key] = value
        return value

    def _read_payload(self, scope: _Scope, expression: ast.expr, trail: _Trail) -> FlowValue:
        """Name the classes an expression's object is built from.

        A constructed class is named and its arguments are left alone: they
        are its fields, not the object. A call that returns something else
        passes on what it was given, so encoding a request still reads as that
        request. Anything the reading cannot place makes the value opaque.
        """
        if isinstance(expression, ast.Await):
            return self._read_payload(scope, expression.value, trail)
        if isinstance(expression, ast.IfExp):
            return self._read_payload(scope, expression.body, trail) | self._read_payload(
                scope, expression.orelse, trail
            )
        if isinstance(expression, ast.Name):
            return self._payload_of_name(scope, expression.id, trail)
        if isinstance(expression, ast.Call):
            return self._payload_of_call(scope, expression, trail)
        return _OPAQUE

    def _payload_of_name(self, scope: _Scope, name: str, trail: _Trail) -> FlowValue:
        if (scope.symbol, name) in trail:
            return _NOTHING
        if not scope.binds(name):
            return _OPAQUE
        value = FlowValue(opaque=name in scope.rebound or name in scope.contexts)
        if name in scope.parameters:
            value |= FlowValue(parameters=frozenset({name}))
        for assigned in scope.assigned.get(name, ()):
            value |= self._read_payload(scope, assigned, trail | {(scope.symbol, name)})
        return value

    def _payload_of_call(self, scope: _Scope, call: ast.Call, trail: _Trail) -> FlowValue:
        callee = call.func
        if isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name):
            owner = self._class_named(scope, callee.value.id)
            if owner is not None:
                return FlowValue(types=frozenset({owner}))
        returned: set[Symbol] = set()
        for target in self._resolve(scope, callee).targets:
            index = self._index(target[0])
            if target[1] in index.classes:
                returned.add(target)
                continue
            function = index.functions.get(target[1])
            if function is not None and function.returns is not None:
                returned.update(self._annotated_classes(target[0], function.returns))
        if returned:
            return FlowValue(types=frozenset(returned))
        passed: list[ast.expr] = [*call.args, *(keyword.value for keyword in call.keywords)]
        if isinstance(callee, ast.Attribute):
            passed = [callee.value]
        if not passed or any(isinstance(argument, ast.Starred) for argument in passed):
            return _OPAQUE
        value = _NOTHING
        for argument in passed:
            value |= self._read_payload(scope, argument, trail)
        return value


def _runs_a_coroutine(expression: ast.expr) -> TypeGuard[ast.Call]:
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


def _is_member(target: ast.expr, member: str) -> bool:
    """Whether an assignment target is ``self.member``."""
    return (
        isinstance(target, ast.Attribute)
        and target.attr == member
        and isinstance(target.value, ast.Name)
        and target.value.id in _RECEIVER_NAMES
    )


def _function_scope(symbol: Symbol, owner: Symbol | None, function: _Function) -> _Scope:
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
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.setdefault(target.id, []).append(node.value)
                    plain.add(id(target))
        elif isinstance(node, ast.AnnAssign | ast.NamedExpr) and isinstance(node.target, ast.Name):
            plain.add(id(node.target))
            if node.value is not None:
                assigned.setdefault(node.target.id, []).append(node.value)
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
    rebound.update(
        node.id
        for node in nodes
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and id(node) not in plain
    )
    return _Scope(
        symbol=symbol,
        owner=owner,
        function=function,
        parameters=parameters,
        assigned={name: tuple(values) for name, values in assigned.items()},
        contexts={name: tuple(values) for name, values in contexts.items()},
        rebound=frozenset(rebound),
    )


def _nodes_outside_annotations(body: ast.AST) -> tuple[ast.AST, ...]:
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


def _supplied_argument(call: _Call, function: _Function, parameter: str) -> ast.expr | None:
    """Return the expression a call passes for one parameter, by keyword or by position."""
    for keyword in call.node.keywords:
        if keyword.arg == parameter:
            return keyword.value
    positional = [argument.arg for argument in (*function.args.posonlyargs, *function.args.args)]
    if call.bound and positional and not _is_static_method(function):
        positional = positional[1:]
    if parameter not in positional:
        return None
    position = positional.index(parameter)
    leading = call.node.args[: position + 1]
    if len(leading) <= position or any(isinstance(argument, ast.Starred) for argument in leading):
        return None
    return leading[position]


def _spreads_arguments(call: ast.Call) -> bool:
    return any(keyword.arg is None for keyword in call.keywords) or any(
        isinstance(argument, ast.Starred) for argument in call.args
    )


def _parameter_default(function: _Function, parameter: str) -> ast.expr | None:
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


def _is_static_method(function: _Function) -> bool:
    return any(isinstance(item, ast.Name) and item.id == "staticmethod" for item in function.decorator_list)
