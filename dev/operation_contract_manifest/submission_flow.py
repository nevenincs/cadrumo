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
from collections.abc import Iterable, Mapping
from typing import override

from .submission_resolution import SubmissionResolutionFlow
from .submission_source import (
    NO_TRAIL,
    OPAQUE,
    Call,
    Choice,
    FlowValue,
    Function,
    Scope,
    Submission,
    SubmissionReading,
    Symbol,
    Trail,
    parameter_default,
    spreads_arguments,
    supplied_argument,
)


class SubmissionFlow(SubmissionResolutionFlow):
    """Follow the definition id and payload of every submission back to the functions that supply them."""

    def read(self, entries: Iterable[Symbol]) -> SubmissionReading:
        """Read the submissions of each entry and of everything it can reach."""
        reached = self.reach(entries)
        summaries = self._settle(reached)
        return SubmissionReading(
            submissions=summaries,
            untyped_receivers=self._untyped_receivers(reached, summaries),
        )

    @override
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

    def _grow_summary(self, symbol: Symbol, summaries: dict[Symbol, frozenset[Submission]]) -> set[Submission]:
        facts = self._facts_of(symbol)
        grown = set(summaries[symbol])
        for call in facts.calls:
            bound = (self._bound(symbol, call, submission) for submission in summaries.get(call.callee, ()))
            grown.update(submission for submission in bound if submission is not None)
        for reference in facts.references:
            grown.update(submission.unsupplied() for submission in summaries.get(reference, ()))
        return grown

    def _settle(self, reached: tuple[Symbol, ...]) -> dict[Symbol, frozenset[Submission]]:
        summaries = {symbol: frozenset(self._facts_of(symbol).roots) for symbol in reached}
        changed = True
        while changed:
            changed = False
            for symbol in reached:
                current = summaries[symbol]
                grown = self._grow_summary(symbol, summaries)
                if len(grown) != len(current):
                    summaries[symbol] = frozenset(grown)
                    changed = True
        return summaries

    def _bound(self, caller: Symbol, call: Call, submission: Submission) -> Submission | None:
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
            supplied = supplied_argument(call, function, parameter)
            if supplied is None:
                continue
            constructed = self._constructed_classes(scope, supplied, NO_TRAIL)
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

    def _constructed_name(self, scope: Scope, name: str, trail: Trail) -> frozenset[Symbol] | None:
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

    def _constructed_choice(self, scope: Scope, expression: ast.IfExp, trail: Trail) -> frozenset[Symbol] | None:
        first = self._constructed_classes(scope, expression.body, trail)
        second = self._constructed_classes(scope, expression.orelse, trail)
        return None if first is None or second is None else first | second

    def _constructed_classes(self, scope: Scope, expression: ast.expr, trail: Trail) -> frozenset[Symbol] | None:
        """Name the exact classes an expression constructs, or nothing when the source does not show them.

        Only a construction counts. A declared return type says what an object
        is at least, not what it is, so it cannot rule a call out.
        """
        if isinstance(expression, ast.IfExp):
            return self._constructed_choice(scope, expression, trail)
        if isinstance(expression, ast.Call):
            targets = self._resolve(scope, expression.func).targets
            classes = frozenset(target for target in targets if target[1] in self._index(target[0]).classes)
            return classes if classes and len(classes) == len(targets) else None
        if not isinstance(expression, ast.Name) or (scope.symbol, expression.id) in trail:
            return None
        return self._constructed_name(scope, expression.id, trail)

    def _bound_value(
        self, scope: Scope, call: Call, function: Function, value: FlowValue, *, identity: bool
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
        self, scope: Scope, call: Call, function: Function, choice: Choice, matching: FlowValue, otherwise: FlowValue
    ) -> FlowValue:
        """Settle a choice where the caller passes a constant, and pass it on where it passes a parameter."""
        supplied = supplied_argument(call, function, choice.parameter)
        argument_scope = scope
        if supplied is None and not spreads_arguments(call.node):
            supplied = parameter_default(function, choice.parameter)
            argument_scope = self._module_scope(call.callee[0])
        if supplied is None:
            return matching | otherwise
        token = self._constant_token(argument_scope, supplied)
        if token is not None:
            return matching if token == choice.constant else otherwise
        if isinstance(supplied, ast.Name) and argument_scope.is_plain_parameter(supplied.id):
            return FlowValue(choices=frozenset({Choice(supplied.id, choice.constant, matching, otherwise)}))
        return matching | otherwise

    def _argument(self, scope: Scope, call: Call, function: Function, parameter: str, *, identity: bool) -> FlowValue:
        """Return the value the caller supplies for one of the callee's parameters."""
        supplied = supplied_argument(call, function, parameter)
        if supplied is not None:
            return self._identity(scope, supplied) if identity else self._payload(scope, supplied)
        default = None if spreads_arguments(call.node) else parameter_default(function, parameter)
        if default is None:
            return OPAQUE
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
