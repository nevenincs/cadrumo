"""Imports carried as text to a child Python interpreter.

``python -c "import package.module"`` and ``python -m package.module`` load the
named module exactly as an import statement in the launching source would; a
string spelling does not change the dependency.  This module finds those
payloads in an interpreter argument sequence and returns the imports they name,
so the ordinary boundary, private-owner and target-existence rules apply.
"""

from __future__ import annotations

import ast
import itertools
import textwrap
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Final

from .import_module_syntax import qualified_name
from .import_target_evaluation import TargetEvaluationContext
from .import_target_value_sets import bounded, combine

_CODE_FLAG: Final[str] = "-c"
_MODULE_FLAG: Final[str] = "-m"
#: Stands in for an interpolated value whose text the evaluator cannot close.
#: A target spelled through it is not a resolvable module and is never reported.
_PLACEHOLDER: Final[str] = "_import_gate_unresolved_value_"
_STRIP_METHODS: Final[frozenset[str]] = frozenset({"strip", "lstrip", "rstrip"})
_DEDENT_FUNCTIONS: Final[frozenset[str]] = frozenset({"textwrap.dedent", "dedent"})
_PAYLOAD_LOADERS: Final[frozenset[str]] = frozenset(
    {"__import__", "builtins.__import__", "importlib.import_module", "import_module", "runpy.run_module", "run_module"}
)


@dataclass(frozen=True)
class StringImport:
    """One module import named by an interpreter payload.

    ``symbols`` holds the names a ``from module import name`` statement binds;
    the consumer decides, as for a source statement, whether a name is a
    submodule or a symbol of ``target``.
    """

    target: str
    symbols: tuple[str, ...]
    lineno: int


def carries_interpreter_payload(node: ast.AST) -> bool:
    """Cheaply recognise a sequence that passes ``-c`` or ``-m`` to an interpreter."""
    elements = _sequence_elements(node)
    return elements is not None and any(
        isinstance(element, ast.Constant) and element.value in {_CODE_FLAG, _MODULE_FLAG} for element in elements[:-1]
    )


def string_payload_imports(node: ast.AST, context: TargetEvaluationContext) -> tuple[StringImport, ...]:
    """Return the imports an interpreter argument sequence at *node* carries.

    *node* is a list or tuple display, or a call whose positional arguments
    form the sequence.  A ``-c`` element followed by Python source contributes
    that source's imports; a ``-m`` element followed by a dotted module name
    contributes that module.  Text that does not parse as Python is not a
    Python payload and contributes nothing.
    """
    elements = _sequence_elements(node)
    if elements is None:
        return ()
    found: list[StringImport] = []
    for flag_node, payload in itertools.pairwise(elements):
        if not (isinstance(flag_node, ast.Constant) and flag_node.value in {_CODE_FLAG, _MODULE_FLAG}):
            continue
        if isinstance(payload, ast.Starred):
            continue
        for text in sorted(_payload_texts(payload, context)):
            if flag_node.value == _CODE_FLAG:
                found.extend(_code_imports(text, payload.lineno))
            else:
                found.extend(_reportable(text, (), payload.lineno))
    return tuple(found)


def _sequence_elements(node: ast.AST) -> Sequence[ast.expr] | None:
    """Return the ordered elements of an interpreter argument sequence."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return node.elts
    if isinstance(node, ast.Call):
        return node.args
    return None


def _payload_texts(node: ast.expr, context: TargetEvaluationContext) -> frozenset[str]:
    """Return every text the payload expression can take, or nothing when it is open."""
    texts = _texts(node, context, node.lineno, set())
    return texts if texts is not None else frozenset[str]()


def _texts(
    node: ast.AST, context: TargetEvaluationContext, lineno: int, resolving: set[tuple[int, str]]
) -> frozenset[str] | None:
    """Evaluate payload text, closing the shapes the target evaluator leaves open.

    The evaluator owns finite string evaluation.  Payload source adds two
    shapes it has no reason to model: whitespace normalisation of a source
    block, and interpolation of an argument (a path, a literal) whose own text
    cannot name a module.  The first is undone; the second is replaced by an
    inert identifier.
    """
    closed = context.values_for(node, lineno)
    if closed is not None:
        return closed
    if isinstance(node, ast.Call):
        return _transformed_texts(node, context, lineno, resolving)
    if isinstance(node, ast.JoinedStr):
        return _interpolated_texts(node, context, lineno, resolving)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return combine(
            _texts(node.left, context, lineno, resolving),
            _texts(node.right, context, lineno, resolving),
        )
    if isinstance(node, ast.Name):
        return _assigned_texts(node, context, lineno, resolving)
    return None


def _transformed_texts(
    node: ast.Call, context: TargetEvaluationContext, lineno: int, resolving: set[tuple[int, str]]
) -> frozenset[str] | None:
    """Undo ``textwrap.dedent(text)`` and argument-free ``text.strip()`` spellings."""
    if node.keywords:
        return None
    function = node.func
    if isinstance(function, ast.Attribute) and function.attr in _STRIP_METHODS and not node.args:
        return _texts(function.value, context, lineno, resolving)
    if qualified_name(function) in _DEDENT_FUNCTIONS and len(node.args) == 1:
        return _texts(node.args[0], context, lineno, resolving)
    return None


def _interpolated_texts(
    node: ast.JoinedStr, context: TargetEvaluationContext, lineno: int, resolving: set[tuple[int, str]]
) -> frozenset[str] | None:
    """Evaluate an f-string, standing an inert identifier in for open interpolations."""
    values: frozenset[str] | None = frozenset({""})
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            pieces: frozenset[str] | None = frozenset({part.value})
        elif isinstance(part, ast.FormattedValue):
            pieces = _texts(part.value, context, lineno, resolving)
            if pieces is None or part.conversion != -1 or part.format_spec is not None:
                pieces = frozenset({_PLACEHOLDER})
        else:
            return None
        values = combine(values, pieces)
        if values is None:
            return None
    return values


def _assigned_texts(
    node: ast.Name, context: TargetEvaluationContext, lineno: int, resolving: set[tuple[int, str]]
) -> frozenset[str] | None:
    """Follow a name to every visible assignment that can supply its text."""
    scope = context.nearest_function(node)
    key = (id(scope) if scope is not None else 0, node.id)
    if key in resolving:
        return None
    assignments = context.latest_values(node.id, lineno, scope)
    if assignments is None or not assignments:
        return None
    resolving.add(key)
    try:
        result: set[str] = set()
        for assignment in assignments:
            if assignment.projection or assignment.unpack:
                return None
            texts = _texts(assignment.value, context, assignment.lineno - 1, resolving)
            if texts is None:
                return None
            result.update(texts)
    finally:
        resolving.remove(key)
    return bounded(result)


def _is_dotted_name(text: str) -> bool:
    """Recognise a module name as ``-m`` accepts it."""
    return bool(text) and all(part.isidentifier() for part in text.split("."))


def _code_imports(source: str, lineno: int) -> Iterator[StringImport]:
    """Yield the absolute imports one ``-c`` program names."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except (SyntaxError, ValueError):
        return
    for statement in ast.walk(tree):
        yield from _statement_imports(statement, lineno)


def _statement_imports(node: ast.AST, lineno: int) -> Iterator[StringImport]:
    """Yield the imports one payload node names."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield from _reportable(alias.name, (), lineno)
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
        for alias in node.names:
            yield from _reportable(node.module, (alias.name,), lineno)
    elif isinstance(node, ast.Call):
        yield from _payload_loader_imports(node, lineno)


def _payload_loader_imports(node: ast.Call, lineno: int) -> Iterator[StringImport]:
    """Yield a supported dynamic loader's literal target within an interpreter payload."""
    if (
        qualified_name(node.func) in _PAYLOAD_LOADERS
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        yield from _reportable(node.args[0].value, (), lineno)


def _reportable(target: str, symbols: tuple[str, ...], lineno: int) -> Iterator[StringImport]:
    """Drop targets spelled through an unresolved interpolation."""
    if _PLACEHOLDER not in target and _is_dotted_name(target):
        yield StringImport(target, symbols, lineno)
