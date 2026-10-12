"""Find request validators whose refusal wording can quote the value they refused.

A request that fails its model is refused with the model's own wording, and
that wording travels to wires, logs and transcripts the request never reaches.
``cadrumo.core.request_faults`` replaces a message that repeats the refused
input verbatim, which misses a value the validator reformatted, a value too
short to match as a word, and another field's value quoted by a field-level
validator. This module closes that gap at the source: it reads the code of every
validator reachable from a request model and reports each message that is built
from a value.

A message is built from a value when an f-string, a ``%`` format, a
``str.format`` call or a concatenation puts into it an expression derived from
what the validator was given. A constant, a field name (``info.field_name``), a
class name and anything not derived from the validator's input are not values.
The scan follows a call into a helper only where the call passes a value, since
that helper's own wording is what the model then reports. A call made inside a
``try`` whose handler catches the failure is not followed: the handler raises
the wording the model reports, and the scan reads that.
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import inspect
import textwrap
import typing
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from types import FunctionType, MethodType
from typing import override

from pydantic import BaseModel
from pydantic.functional_validators import AfterValidator, BeforeValidator, PlainValidator, WrapValidator
from pydantic_core import PydanticCustomError

from cadrumo.core.errors.hierarchy import CadrumoError

_FOLLOW_DEPTH = 4
"""How many helper calls deep a value is followed from a validator."""

_NAME_ATTRIBUTES = frozenset({"field_name", "__name__", "__qualname__"})
_UNTAINTED_PARAMETERS = frozenset({"cls", "info"})
_MESSAGE_ERRORS = (ValueError, TypeError, AssertionError, ArithmeticError)
_CATCHING_ERRORS = (ValueError, TypeError, Exception, BaseException, CadrumoError)
_VALIDATOR_WRAPPERS = (AfterValidator, BeforeValidator, PlainValidator, WrapValidator)
_PACKAGES = ("cadrumo", "cadrumo_harness")


@dataclass(frozen=True, slots=True)
class MessageLeak:
    """One refusal message built from a value, and where it is built."""

    model: str
    function: str
    line: int
    message: str
    value: str

    def describe(self) -> str:
        """Name the message, the value it quotes and where, for a failure report."""
        return f"{self.function} line {self.line} quotes {self.value} in {self.message}  (on {self.model})"


def request_validators(models: Iterable[type]) -> list[tuple[type, Callable[..., object]]]:
    """Return every validator function of these models and of the models and dataclasses they hold."""
    validators: list[tuple[type, Callable[..., object]]] = []
    for model in _reachable_types(models):
        if issubclass(model, BaseModel):
            decorators = model.__pydantic_decorators__
            for group in (
                decorators.field_validators,
                decorators.model_validators,
                decorators.validators,
                decorators.root_validators,
            ):
                validators.extend((model, decorator.func) for decorator in group.values())
            validators.extend((model, function) for function in _annotated_validators(model))
        post_init = getattr(model, "__post_init__", None)
        if post_init is not None and dataclasses.is_dataclass(model):
            validators.append((model, post_init))
    return validators


def message_leaks(validators: Iterable[tuple[type, Callable[..., object]]]) -> tuple[MessageLeak, ...]:
    """Report every message the validators build from a value, each once."""
    found: dict[tuple[str, int, str], MessageLeak] = {}
    for model, function in validators:
        for leak in _function_leaks(function, model, _FOLLOW_DEPTH, set(), tainted=None):
            found.setdefault((leak.function, leak.line, leak.message), leak)
    return tuple(sorted(found.values(), key=lambda leak: (leak.function, leak.line)))


def _in_scope(owner: type) -> bool:
    return isinstance(owner, type) and owner.__module__.split(".")[0] in _PACKAGES


def _annotation_types(annotation: object, found: list[type]) -> None:
    origin = typing.get_origin(annotation)
    if origin is not None:
        for part in typing.get_args(annotation):
            _annotation_types(part, found)
    elif isinstance(annotation, type):
        found.append(annotation)
    elif isinstance(annotation, typing.TypeAliasType):
        _annotation_types(annotation.__value__, found)


def _reachable_types(roots: Iterable[type]) -> list[type]:
    """Walk the models and dataclasses that the roots hold in their fields, in a stable order."""
    seen: dict[type, None] = {}
    pending = list(roots)
    while pending:
        candidate = pending.pop()
        if candidate in seen or not _in_scope(candidate):
            continue
        parts: list[type] = []
        if issubclass(candidate, BaseModel):
            seen[candidate] = None
            for field in candidate.model_fields.values():
                _annotation_types(field.annotation, parts)
        elif dataclasses.is_dataclass(candidate):
            seen[candidate] = None
            try:
                hints = typing.get_type_hints(candidate)
            except (NameError, TypeError):
                hints = {}
            for hint in hints.values():
                _annotation_types(hint, parts)
        pending.extend(parts)
    return sorted(seen, key=lambda model: (model.__module__, model.__qualname__))


def _annotated_validators(model: type[BaseModel]) -> list[Callable[..., object]]:
    """Return the functions that ``Annotated`` validators carry on the fields of ``model``."""
    functions: list[Callable[..., object]] = []

    def collect(annotation: object) -> None:
        origin = typing.get_origin(annotation)
        if origin is typing.Annotated:
            base, *metadata = typing.get_args(annotation)
            collect(base)
            functions.extend(item.func for item in metadata if isinstance(item, _VALIDATOR_WRAPPERS))
        elif origin is not None:
            for part in typing.get_args(annotation):
                collect(part)
        elif isinstance(annotation, typing.TypeAliasType):
            collect(annotation.__value__)

    for field in model.model_fields.values():
        collect(field.annotation)
        functions.extend(item.func for item in field.metadata if isinstance(item, _VALIDATOR_WRAPPERS))
    return functions


def _plain_function(candidate: object) -> FunctionType | None:
    """Return the Python function behind a validator or a callee, or ``None`` for anything else."""
    inner = getattr(candidate, "__func__", candidate)
    if not callable(inner):
        return None
    try:
        unwrapped: object = inspect.unwrap(inner)
    except ValueError:
        return None
    if not isinstance(unwrapped, FunctionType):
        return None
    return unwrapped if unwrapped.__module__.split(".")[0] in _PACKAGES else None


def _parsed(function: FunctionType) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, int] | None:
    """Parse a function's source; the second member is the file line its first line sits on."""
    try:
        source = textwrap.dedent(inspect.getsource(function))
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return node, function.__code__.co_firstlineno - 1
    return None


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    arguments = node.args
    return [item.arg for item in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]


def _names_used(node: ast.AST) -> set[str]:
    """Collect the names an expression reads, leaving out what it only uses to name a field or a class."""
    names: set[str] = set()

    def visit(current: ast.AST) -> None:
        if isinstance(current, ast.Attribute) and current.attr in _NAME_ATTRIBUTES:
            return
        if (
            isinstance(current, ast.Call)
            and isinstance(current.func, ast.Name)
            and current.func.id == "getattr"
            and len(current.args) >= 2
            and isinstance(current.args[1], ast.Constant)
            and current.args[1].value in _NAME_ATTRIBUTES
        ):
            return
        if isinstance(current, ast.Name):
            names.add(current.id)
        for child in ast.iter_child_nodes(current):
            visit(child)

    visit(node)
    return names


def _propagate_taint(node: ast.FunctionDef | ast.AsyncFunctionDef, tainted: set[str]) -> None:
    """Mark every local that is assigned from a tainted expression, until no more are."""
    changed = True
    while changed:
        changed = False
        for statement in ast.walk(node):
            targets: Sequence[ast.AST] = ()
            source: ast.AST | None = None
            if isinstance(statement, ast.Assign):
                targets = statement.targets
                source = statement.value
            elif isinstance(statement, ast.AnnAssign | ast.AugAssign) and statement.value is not None:
                targets = (statement.target,)
                source = statement.value
            elif isinstance(statement, ast.For | ast.comprehension):
                targets = (statement.target,)
                source = statement.iter
            elif isinstance(statement, ast.NamedExpr):
                targets = (statement.target,)
                source = statement.value
            elif isinstance(statement, ast.ExceptHandler) and statement.name is not None:
                # The handler's exception carries what the guarded code reported.
                tainted_body = any(_names_used(item) & tainted for item in statement.body)
                if tainted_body and statement.name not in tainted:
                    tainted.add(statement.name)
                    changed = True
                continue
            if source is None or not _names_used(source) & tainted:
                continue
            for target in targets:
                for name in (item.id for item in ast.walk(target) if isinstance(item, ast.Name)):
                    if name not in tainted:
                        tainted.add(name)
                        changed = True


def _resolve(expression: ast.expr, function: FunctionType, owner: type | None) -> object | None:
    """Resolve a called name or attribute chain to the object it names, or ``None``."""
    if isinstance(expression, ast.Name):
        return function.__globals__.get(expression.id, getattr(builtins, expression.id, None))
    if isinstance(expression, ast.Attribute):
        base = expression.value
        if isinstance(base, ast.Name) and base.id in {"self", "cls"} and owner is not None:
            return getattr(owner, expression.attr, None)
        resolved = _resolve(base, function, owner)
        return None if resolved is None else getattr(resolved, expression.attr, None)
    return None


def _carries_message(error: object) -> bool:
    """Say whether an exception class puts the first argument it is built with into its own text."""
    if not isinstance(error, type) or not issubclass(error, BaseException):
        return error is None
    if issubclass(error, PydanticCustomError):
        return True
    for base in error.__mro__:
        if "__init__" in vars(base):
            return base in {CadrumoError, BaseException, Exception} or issubclass(base, _MESSAGE_ERRORS)
    return False


def _message_pieces(call: ast.Call, error: object) -> list[ast.expr]:
    if isinstance(error, type) and issubclass(error, PydanticCustomError):
        pieces = list(call.args[1:2])
        if len(call.args) > 2 and isinstance(call.args[2], ast.Dict):
            pieces.extend(call.args[2].values)
        return pieces
    positional = list(call.args)
    named = [keyword.value for keyword in call.keywords if keyword.arg == "message"]
    if error is None or (isinstance(error, type) and issubclass(error, _MESSAGE_ERRORS)):
        return positional + named
    # A registered error puts its first argument, or its ``message``, in its text.
    return positional[:1] + named


def _catches(handler: ast.ExceptHandler, function: FunctionType, owner: type | None) -> bool:
    """Say whether an ``except`` clause takes the failures a guarded helper raises."""
    if any(
        isinstance(item, ast.Raise) and item.exc is None for statement in handler.body for item in ast.walk(statement)
    ):
        # A handler that re-raises passes the helper's wording on as it was.
        return False
    if handler.type is None:
        return True
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    for name in names:
        caught = _resolve(name, function, owner)
        if isinstance(caught, type) and (
            caught in _CATCHING_ERRORS or issubclass(caught, (CadrumoError, *_MESSAGE_ERRORS))
        ):
            return True
    return False


class _Reader(ast.NodeVisitor):
    """Read one function: the messages it builds from tainted values, and the helpers it hands them to."""

    def __init__(self, function: FunctionType, owner: type | None, tainted: set[str], first_line: int) -> None:
        self._function = function
        self._owner = owner
        self._tainted = tainted
        self._first_line = first_line
        self._assigned: dict[str, list[ast.expr]] = {}
        self._guarded = 0
        self.constructs: list[tuple[int, ast.expr, ast.expr]] = []
        self.calls: list[ast.Call] = []

    def note_assignments(self, node: ast.AST) -> None:
        for statement in ast.walk(node):
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        self._assigned.setdefault(target.id, []).append(statement.value)

    def _value_in(self, expression: ast.expr) -> bool:
        return bool(_names_used(expression) & self._tainted)

    def _scan_message(self, expression: ast.expr, depth: int = 0) -> None:
        if isinstance(expression, ast.Name) and depth < 3:
            for assigned in self._assigned.get(expression.id, []):
                self._scan_message(assigned, depth + 1)
            return
        for node in ast.walk(expression):
            if isinstance(node, ast.JoinedStr):
                for part in node.values:
                    if isinstance(part, ast.FormattedValue) and self._value_in(part.value):
                        self.constructs.append((node.lineno, node, part.value))
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod | ast.Add):
                if self._is_text(node.left) or self._is_text(node.right):
                    operands = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
                    for operand in (node.left, *operands):
                        if self._value_in(operand) and not self._is_text(operand):
                            self.constructs.append((node.lineno, node, operand))
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "format"
                and self._is_text(node.func.value)
            ):
                for argument in (*node.args, *(keyword.value for keyword in node.keywords)):
                    if self._value_in(argument):
                        self.constructs.append((node.lineno, node, argument))

    def _is_text(self, node: ast.expr) -> bool:
        """Say whether an expression is text a message can be built on: a literal, or a name that holds one."""
        if isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            return True
        if not isinstance(node, ast.Name):
            return False
        assigned = self._assigned.get(node.id)
        if assigned:
            return all(self._is_text(value) for value in assigned)
        return isinstance(self._function.__globals__.get(node.id), str)

    @override
    def visit_Raise(self, node: ast.Raise) -> None:
        call = node.exc
        if isinstance(call, ast.Call):
            error = _resolve(call.func, self._function, self._owner)
            if _carries_message(error):
                for piece in _message_pieces(call, error):
                    self._scan_message(piece)
        self.generic_visit(node)

    @override
    def visit_Assert(self, node: ast.Assert) -> None:
        if node.msg is not None:
            self._scan_message(node.msg)
        self.generic_visit(node)

    @override
    def visit_Try(self, node: ast.Try) -> None:
        guarded = any(_catches(handler, self._function, self._owner) for handler in node.handlers)
        if guarded:
            self._guarded += 1
        for statement in node.body:
            self.visit(statement)
        if guarded:
            self._guarded -= 1
        for statement in (*node.handlers, *node.orelse, *node.finalbody):
            self.visit(statement)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        if not self._guarded:
            self.calls.append(node)
        self.generic_visit(node)


def _receives_its_owner(callee: object, call: ast.Call, owner: type) -> bool:
    """Say whether the call's first parameter is bound by the call itself, as ``self.helper(value)`` binds it."""
    if isinstance(callee, MethodType):
        return True
    function = call.func
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id == "self"
        and not isinstance(inspect.getattr_static(owner, function.attr, None), staticmethod)
    )


def _function_leaks(
    candidate: object, owner: type, depth: int, visited: set[tuple[int, frozenset[str]]], *, tainted: set[str] | None
) -> list[MessageLeak]:
    function = _plain_function(candidate)
    if function is None:
        return []
    parsed = _parsed(function)
    if parsed is None:
        return []
    node, first_line = parsed
    parameters = _parameters(node)
    start = {name for name in parameters if name not in _UNTAINTED_PARAMETERS} if tainted is None else set(tainted)
    key = (id(function.__code__), frozenset(start))
    if key in visited:
        return []
    visited.add(key)
    _propagate_taint(node, start)
    reader = _Reader(function, owner, start, first_line)
    reader.note_assignments(node)
    for statement in node.body:
        reader.visit(statement)
    leaks = [
        MessageLeak(
            model=f"{owner.__module__}.{owner.__qualname__}",
            function=f"{function.__module__}.{function.__qualname__}",
            line=first_line + line,
            message=ast.unparse(construct),
            value=ast.unparse(value),
        )
        for line, construct, value in reader.constructs
    ]
    if depth > 0:
        for call in reader.calls:
            callee = _resolve(call.func, function, owner)
            target = _plain_function(callee)
            if target is None:
                continue
            parsed_callee = _parsed(target)
            if parsed_callee is None:
                continue
            names = _parameters(parsed_callee[0])
            positional = names[1:] if _receives_its_owner(callee, call, owner) else names
            passed: set[str] = set()
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id in start
                and names
            ):
                passed.add(names[0])
            passed.update(
                name
                for name, argument in zip(positional, call.args, strict=False)
                if _names_used(argument) & start and not isinstance(argument, ast.Starred)
            )
            passed.update(
                keyword.arg
                for keyword in call.keywords
                if keyword.arg is not None and _names_used(keyword.value) & start
            )
            if passed:
                leaks.extend(_function_leaks(target, owner, depth - 1, visited, tainted=passed))
    return leaks
