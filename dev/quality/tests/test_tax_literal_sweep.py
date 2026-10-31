"""Refuse a tax value written into the code that handles tax.

The operator's rule is that a tax number, limit, threshold, period or form code lives in
the registry. Calendar facts, arithmetic, technical limits and registry ids may stay in code.
The sweep follows scalar types, lexical producers and canonical technical owners.
Unknown collection bounds remain findings; a lexical width does not select a fiscal value:

- a ``Decimal`` other than an arithmetic identity or a rounding quantum;
- a numeric bound or comparison other than arithmetic, a calendar range or a machine capacity;
- a collection bound or repeated-record count, which can hide a form's row limit;
- complete fixed code alternatives in a regex, rather than its character widths;
- a year in a branch, a ``date`` with a fixed year or day, a ``timedelta`` of days, a month tuple;
- a code-shaped string, ``Literal`` member, ``match`` case or dict key outside a modelo or period address;
- a comparison with a modelo id, or two or more modelo ids held together, which is a routing rule;
- a one or two letter string compared with, or stored under, a name that means a clave.

A literal leaves the findings only through a rule below. There is no record of accepted
literals: what the rules do not cover fails and stays listed until it moves or a rule states
why it may stay. The modelo ids come from the registry tree and the period codes from their
enum, so neither is listed.

The sweep reads literals where they are written. A value given a name at module scope and read
through that name leaves its reach, so whether such a name holds a tax value is a question for
review, not a finding of this gate.
"""

from __future__ import annotations

import ast
import re
import sys
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Final, override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT: Final = Path(__file__).resolve().parents[3]
_SRC: Final = _ROOT / "src" / "cadrumo"
_SCANNED: Final = (
    _SRC / "domain",
    _SRC / "application",
    _SRC / "core",
    _SRC / "adapters",
    _SRC / "entrypoints",
    _ROOT / "src" / "cadrumo_client",
)
_MACHINE_OWNERS: Final = ("cadrumo_client/", "adapters/persistence/storage/", "core/redaction/")
"""These read operating system answers, framing and byte sizes; no tax value reaches them."""

_NUMERIC_BOUNDS: Final = frozenset({"ge", "gt", "le", "lt"})
_ARITHMETIC_BOUNDS: Final = frozenset({0, 1})
_CODE_SHAPED: Final = re.compile(r"^\d{2,4}[A-Z]?$")
_LETTER_CLAVE: Final = re.compile(r"^[A-Z]{1,2}$")
_CLAVE_NAME: Final = re.compile(r"clave|subclave|tipo_|_code$|^code$|codigo", re.IGNORECASE)
_MODELO_NAME: Final = re.compile(r"modelo|model\b", re.IGNORECASE)
_PERIOD_NAME: Final = re.compile(r"period|token|quarter", re.IGNORECASE)
_EDITION_NAME: Final = re.compile(r"revision_id|design_epoch", re.IGNORECASE)
_MODELO_ADDRESS_CALLS: Final = frozenset(
    {"Modelo", "modelo_directory", "revision", "revision_for_context", "select_revision_metadata", "snapshot"},
)
_FORM_NAMED_MODULE: Final = re.compile(r"(?:^|_)m(\d{3})(?:_|$)")
_MONTH_NAME: Final = re.compile(r"month", re.IGNORECASE)
_DAY_NAME: Final = re.compile(r"days?(?:_|$)|dias", re.IGNORECASE)
_COUNTRY_NAME: Final = re.compile(r"country|iso", re.IGNORECASE)
_LENGTH_BOUNDS: Final = frozenset({"min_length", "max_length"})
_SHA256_HEX: Final = 64
_STANDARD_SHAPE_FUNCTION: Final = re.compile(
    r"(?:^|_|\.)(?:yyyymmdd|ddmmyyyy|territory_definition|jurisdictions|modelo_code|selector_address)(?:_|\.|s?$)",
    re.IGNORECASE,
)
_PATTERN_CALLS: Final = frozenset({"Field", "StringConstraints", "constr"})
_REGEX_CALLS: Final = frozenset(
    {"compile", "match", "fullmatch", "search", "sub", "subn", "findall", "finditer", "split"}
)
_WIDTH_QUANTIFIER: Final = re.compile(r"(\[[^\]]*\]|\\[A-Za-z]|\.|\))\{(\d+)(?:,(\d*))?\}")
_HEX_CLASSES: Final = frozenset({"[0-9a-f]", "[a-f0-9]", "[0-9A-Fa-f]", "[A-Fa-f0-9]", "[0-9a-fA-F]", "[a-fA-F0-9]"})
_CALENDAR_RANGES: Final = frozenset({(1, 12), (1, 31), (1, 53), (1, 366), (365, 366), (1, 7), (1900, 9999)})
_CALENDAR_VALUES: Final = frozenset({7, 12, 24, 28, 29, 30, 31, 52, 53, 60, 365, 366, 1900, 9999})
_ARITHMETIC_COMPARE: Final = frozenset({-1, 0, 1, 2, 100})
_FIRST_YEAR: Final = 1900
_LAST_YEAR: Final = 2100
_YEAR_ENDPOINTS: Final = frozenset({(1, 1), (12, 31)})
_EXCEL_EPOCH: Final = (1899, 12, 30)
_MONTH_TUPLE_LENGTH: Final = 3
_MONTHS_OF_A_YEAR: Final = 12
_DAYS_OF_A_YEAR: Final = frozenset({365, 366})
_ADDRESS_KEYWORDS: Final = frozenset({"modelo", "period", "modelo_id", "source_modelo", "registry_token"})
_PERIOD_ENUM: Final = "StandardPeriodCode"
_COMMAND_ROOTS: Final = frozenset({"app", "config"})


def _modelo_ids() -> frozenset[str]:
    return frozenset(
        path.name for path in (_SRC / "_data" / "registry" / "aeat" / "modelos").iterdir() if path.is_dir()
    )


def _period_codes() -> frozenset[str]:
    sys.path.insert(0, str(_ROOT / "src"))
    from cadrumo.core.period import StandardPeriodCode

    return frozenset(code.value for code in StandardPeriodCode)


def _called_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else ""


def _expression_names(node: ast.AST) -> str:
    return " ".join(
        item.id if isinstance(item, ast.Name) else item.attr
        for item in ast.walk(node)
        if isinstance(item, (ast.Name, ast.Attribute))
    )


def _docstrings(tree: ast.AST) -> set[ast.AST]:
    found: set[ast.AST] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list):
            for statement in body:
                if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                    found.add(statement.value)
    return found


def _machine_capacity(value: float) -> bool:
    """A power of two or of ten from a thousand up sizes a buffer or payload, not a tax rule."""
    if not isinstance(value, int) or value < 1:
        return False
    return (value >= 16 and value & (value - 1) == 0) or (
        value >= 1000 and str(value).strip("0") in {"1", "2", "4", "5"}
    )


def _lawful_range(low: float | None, high: float | None) -> bool:
    """Return whether a ``Field``'s numeric bounds state arithmetic, a calendar range or a capacity."""
    if (low, high) in _CALENDAR_RANGES:
        return True
    return all(bound is None or bound in _ARITHMETIC_BOUNDS or _machine_capacity(bound) for bound in (low, high))


def _lawful_length(low: float | None, high: float | None, pattern: str | None) -> bool:
    """Return whether ``Field`` lengths state a digest, a payload guard or nothing at all."""
    if (
        pattern is not None
        and all(group[0] in _HEX_CLASSES for group in _WIDTH_QUANTIFIER.findall(pattern))
        and (_WIDTH_QUANTIFIER.search(pattern))
    ):
        return True
    if low == high and low == _SHA256_HEX:
        return True
    if low is not None and low not in _ARITHMETIC_BOUNDS:
        return False
    return high is None or high in _ARITHMETIC_BOUNDS or _machine_capacity(high)


def _lawful_decimal(text: str) -> bool:
    try:
        value = Decimal(text)
    except InvalidOperation:
        return True
    if not value.is_finite():
        return True
    if value in {Decimal(0), Decimal(1), Decimal(100), Decimal(-1)}:
        return True
    return 0 < value < 1 and value.as_tuple().digits[0] == 1 and sum(value.as_tuple().digits) == 1


def _constant_number(node: ast.AST | None) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _constant_number(node.operand)
        return None if inner is None else -inner
    return None


@cache
def _module_tree(module: str) -> ast.Module | None:
    """Inspect canonical project scalar definitions without importing application code."""
    if not module.startswith(("cadrumo.", "cadrumo_client.")):
        return None
    path = _ROOT / "src" / Path(*module.split(".")).with_suffix(".py")
    return ast.parse(path.read_text(encoding="utf-8")) if path.is_file() else None


@cache
def _imports_for(tree: ast.AST, module: str) -> dict[str, tuple[str, str]]:
    imports = {}
    package = module.split(".")[:-1]
    for node in _scope_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            prefix = package[: len(package) - node.level + 1] if node.level else []
            target = ".".join([*prefix, *(node.module or "").split(".")]).strip(".")
            imports.update({alias.asname or alias.name: (target, alias.name) for alias in node.names})
    return imports


def _annotation_kind(
    node: ast.AST | None, tree: ast.AST, module: str, seen: frozenset[tuple[str, str]] = frozenset()
) -> str:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        kinds = {_annotation_kind(part, tree, module, seen) for part in (node.left, node.right)} - {"unknown"}
        return kinds.pop() if len(kinds) == 1 else "unknown"
    if isinstance(node, ast.Subscript):
        name = _reader_name(node.value)
        first = node.slice.elts[0] if isinstance(node.slice, ast.Tuple) else node.slice
        if name in {"Annotated", "Optional"}:
            return _annotation_kind(first, tree, module, seen)
        if (
            name in {"dict", "Mapping"}
            and isinstance(node.slice, ast.Tuple)
            and all(_annotation_kind(part, tree, module, seen) == "text" for part in node.slice.elts)
        ):
            return "text_mapping"
        if name in {"tuple", "list", "set", "frozenset", "dict", "Mapping", "Sequence"}:
            return "collection"
    if not isinstance(node, ast.Name):
        return "unknown"
    if node.id in {"str", "bytes", "StrEnum"}:
        return "text"
    key = (module, node.id)
    if key in seen:
        return "unknown"
    seen = seen | {key}
    imported = _imports_for(tree, module).get(node.id)
    if imported is not None:
        target, symbol = imported
        if (target, symbol) == ("cadrumo.domain.calculations.registry.schema_formula", "FormulaExpression"):
            return "expression"
        if (target, symbol) == ("urllib.parse", "SplitResult"):
            return "url"
        imported_tree = _module_tree(target)
        if imported_tree is not None:
            return _annotation_kind(ast.Name(id=symbol, ctx=ast.Load()), imported_tree, target, seen)
    for declaration in getattr(tree, "body", []):
        if isinstance(declaration, ast.ClassDef) and declaration.name == node.id:
            if any(_annotation_kind(base, tree, module, seen) == "text" for base in declaration.bases):
                return "text"
        elif isinstance(declaration, ast.TypeAlias):
            if declaration.name.id == node.id:
                return _annotation_kind(declaration.value, tree, module, seen)
        elif isinstance(declaration, (ast.Assign, ast.AnnAssign)):
            targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
            if any(isinstance(target, ast.Name) and target.id == node.id for target in targets):
                return _annotation_kind(declaration.value, tree, module, seen)
    return "unknown"


def _scope_nodes(scope: ast.AST) -> list[ast.AST]:
    nodes = [scope]
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        nodes.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return nodes


def _dom_cell_call(node: ast.Call) -> bool:
    if _called_name(node) != "find_all":
        return False
    if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value in {"td", "th"}:
        return True
    return any(
        keyword.arg == "class_"
        and isinstance(keyword.value, ast.Call)
        and keyword.value.args
        and isinstance(keyword.value.args[0], ast.Constant)
        and keyword.value.args[0].value == "z-listcell"
        for keyword in node.keywords
    )


def _fixed_pattern_members(pattern: str) -> tuple[str, ...]:
    """Recognize complete literal alternatives, leaving digit widths as lexical grammar."""
    text = pattern.removeprefix("^").removesuffix("$").removesuffix(r"\Z")
    if text.startswith("(?:") and text.endswith(")"):
        text = text[3:-1]
    elif text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    members = tuple(text.split("|"))
    return members if all(re.fullmatch(r"[0-9A-Z]+", member) for member in members) else ()


class _Sweep(ast.NodeVisitor):
    def __init__(
        self,
        tree: ast.Module,
        modelos: frozenset[str],
        periods: frozenset[str],
        own_form: str | None,
        *,
        machine: bool = False,
        owner: str = "",
    ) -> None:
        self._tree = tree
        self._owner = owner
        self._module = owner.removesuffix(".py").replace("/", ".")
        if owner and not owner.startswith("cadrumo_client/"):
            self._module = "cadrumo." + self._module
        self._own_form = own_form
        self._machine = machine
        self._parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        self._docstrings = _docstrings(tree)
        self._modelos = modelos
        self._periods = periods
        self.findings: list[str] = []

    def _report(self, kind: str, value: object, node: ast.AST) -> None:
        self.findings.append(f"{kind}:{value!r}@{getattr(node, 'lineno', 0)}")

    def _enclosing_function(self, node: ast.AST) -> str:
        """Return the enclosing function and class names, innermost first, in snake case."""
        names = []
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(re.sub(r"(?<=[a-z])(?=[A-Z])", "_", current.name))
        return ".".join(names)

    def _scope(self, node: ast.AST) -> ast.AST:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current
        return self._tree

    def _constraint_declaration(self, node: ast.AST) -> tuple[str, ast.AST | None]:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.AnnAssign):
                return _expression_names(current.target), current.annotation
            if isinstance(current, ast.TypeAlias):
                return _reader_name(current.name), current.value
            if isinstance(current, ast.Assign):
                return " ".join(_expression_names(t) for t in current.targets), current.value
            if isinstance(current, ast.stmt):
                break
        return "", None

    def _expression_kind(self, node: ast.AST, seen: frozenset[tuple[int, str]] = frozenset()) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return "text"
        if isinstance(node, ast.ListComp) and all(
            self._expression_kind(generator.iter, seen) == "grammar_sequence" for generator in node.generators
        ):
            return "grammar_sequence"
        if isinstance(node, ast.Attribute) and node.attr == "path" and self._expression_kind(node.value, seen) == "url":
            return "text"
        if isinstance(node, ast.Subscript):
            parent_kind = self._expression_kind(node.value, seen)
            if parent_kind in {"text", "match"}:
                return "text"
            if parent_kind == "grammar_sequence":
                return "grammar_sequence" if isinstance(node.slice, ast.Slice) else "text"
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "args"
            and self._expression_kind(node.value, seen) == "expression"
        ):
            return "grammar_sequence"
        if isinstance(node, ast.Call):
            name = _called_name(node)
            if name == "str":
                return "text"
            if isinstance(node.func, ast.Attribute):
                receiver = self._expression_kind(node.func.value, seen)
                if receiver == "text":
                    if name in {"split", "rsplit", "partition", "rpartition"}:
                        return "grammar_sequence"
                    if name in {"strip", "lstrip", "rstrip", "replace", "upper", "lower", "casefold", "join"}:
                        return "text"
                if name == "items" and receiver == "text_mapping":
                    return "text_items"
                if name == "compile" and _reader_name(node.func.value) == "re":
                    return "pattern"
                if name in {"match", "fullmatch", "search"} and receiver == "pattern":
                    return "match"
                if name == "group" and receiver == "match":
                    return "text"
                if self._owner.startswith("adapters/") and _dom_cell_call(node):
                    return "grammar_sequence"
            for function in ast.walk(self._tree):
                if isinstance(function, ast.FunctionDef) and function.name == name:
                    kind = _annotation_kind(function.returns, self._tree, self._module)
                    if kind != "unknown":
                        if (
                            kind == "collection"
                            and self._owner.startswith("adapters/")
                            and any(isinstance(call, ast.Call) and _dom_cell_call(call) for call in ast.walk(function))
                        ):
                            return "grammar_sequence"
                        return kind
        if isinstance(node, ast.Name):
            scope = self._scope(node)
            key = (id(scope), node.id)
            if key in seen:
                return "unknown"
            seen = seen | {key}
            assignments = [
                part.value
                for part in _scope_nodes(scope)
                if isinstance(part, ast.Assign) and any(_reader_name(target) == node.id for target in part.targets)
            ]
            if len(assignments) > 1:
                for assigned in assignments:
                    if (
                        isinstance(assigned, ast.Subscript)
                        and isinstance(assigned.slice, ast.Slice)
                        and ast.dump(assigned.value) == ast.dump(node)
                    ):
                        continue
                    if self._expression_kind(assigned, seen) not in {"text", "grammar_sequence", "pattern", "match"}:
                        return "unknown"
            local_binding = False
            for declaration in _scope_nodes(scope):
                value = None
                if isinstance(declaration, ast.arg) and declaration.arg == node.id:
                    local_binding = True
                    kind = _annotation_kind(declaration.annotation, self._tree, self._module)
                    if kind == "collection" and isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        arguments = [*scope.args.posonlyargs, *scope.args.args]
                        if declaration in arguments:
                            index = arguments.index(declaration)
                            callers = [
                                call
                                for call in ast.walk(self._tree)
                                if isinstance(call, ast.Call)
                                and _called_name(call) == scope.name
                                and len(call.args) > index
                            ]
                            if callers and all(
                                self._expression_kind(call.args[index], seen) == "grammar_sequence" for call in callers
                            ):
                                return "grammar_sequence"
                    if kind != "unknown":
                        return kind
                if isinstance(declaration, ast.AnnAssign) and _reader_name(declaration.target) == node.id:
                    kind = _annotation_kind(declaration.annotation, self._tree, self._module)
                    if kind != "unknown":
                        return kind
                    local_binding = True
                    value = declaration.value
                if isinstance(declaration, ast.Assign) and any(_reader_name(t) == node.id for t in declaration.targets):
                    local_binding = True
                    value = declaration.value
                if isinstance(declaration, ast.Assign) and any(
                    isinstance(target, (ast.Tuple, ast.List))
                    and any(_reader_name(part) == node.id for part in target.elts)
                    for target in declaration.targets
                ):
                    local_binding = True
                    if self._expression_kind(declaration.value, seen) == "grammar_sequence":
                        return "text"
                if (
                    isinstance(declaration, (ast.comprehension, ast.For))
                    and _reader_name(declaration.target) == node.id
                    and self._expression_kind(declaration.iter, seen) == "grammar_sequence"
                ):
                    return "text"
                if (
                    isinstance(declaration, ast.For)
                    and isinstance(declaration.target, (ast.Tuple, ast.List))
                    and any(_reader_name(part) == node.id for part in declaration.target.elts)
                ):
                    local_binding = True
                    if self._expression_kind(declaration.iter, seen) == "text_items":
                        return "text"
                if isinstance(declaration, ast.For) and _reader_name(declaration.target) == node.id:
                    local_binding = True
                    if isinstance(declaration.iter, ast.Name):
                        for argument in _scope_nodes(scope):
                            annotation = (
                                argument.annotation
                                if isinstance(argument, ast.arg) and argument.arg == declaration.iter.id
                                else None
                            )
                            if isinstance(annotation, ast.Subscript) and _reader_name(annotation.value) in {
                                "Mapping",
                                "dict",
                            }:
                                first = (
                                    annotation.slice.elts[0]
                                    if isinstance(annotation.slice, ast.Tuple)
                                    else annotation.slice
                                )
                                if _annotation_kind(first, self._tree, self._module) == "text":
                                    return "text"
                if value is not None:
                    kind = self._expression_kind(value, seen)
                    if kind != "unknown":
                        return kind
            if scope is not self._tree and not local_binding:
                for declaration in self._tree.body:
                    if isinstance(declaration, (ast.Assign, ast.AnnAssign)):
                        targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
                        if any(_reader_name(t) == node.id for t in targets) and declaration.value is not None:
                            return self._expression_kind(declaration.value, seen)
        return "unknown"

    def _structural_length(self, length: ast.Call, comparison: ast.Compare) -> bool:
        if not length.args:
            return False
        value = length.args[0]
        if self._expression_kind(value) in {"text", "grammar_sequence"}:
            return True
        # A character predicate establishes text grammar even when a library's
        # generic validator parameter is deliberately annotated as object.
        scope = self._scope(comparison)
        spelling = ast.dump(value)
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in {"isdigit", "isascii", "isdecimal"}
            and ast.dump(call.func.value) == spelling
            for call in _scope_nodes(scope)
        ):
            return True
        numbers = {_constant_number(side) for side in (comparison.left, *comparison.comparators)} - {None}
        # Fixed text record fields are checked against literal field labels.
        indices = [
            part.slice.value
            for part in _scope_nodes(scope)
            if isinstance(part, ast.Subscript)
            and ast.dump(part.value) == spelling
            and isinstance(part.slice, ast.Constant)
            and isinstance(part.slice.value, int)
        ]
        if (
            indices
            and max(indices) + 1 in numbers
            and any(
                isinstance(part, ast.Compare)
                and any(
                    isinstance(side, ast.Constant) and isinstance(side.value, str)
                    for side in (part.left, *part.comparators)
                )
                and any(
                    isinstance(side, ast.Subscript) and ast.dump(side.value) == spelling
                    for side in (part.left, *part.comparators)
                )
                for part in _scope_nodes(scope)
            )
        ):
            return True
        if self._owner == "adapters/outbound/aeat/sede/_declarations_listbox.py":
            return (
                isinstance(value, ast.Name)
                and value.id == "cell_texts"
                and bool(indices)
                and max(indices) + 1 in numbers
            )
        if self._owner == "domain/calculations/registry/export_components.py":
            return any(
                isinstance(part, ast.Compare)
                and any(
                    isinstance(side, ast.Tuple) and len(side.elts) in numbers for side in (part.left, *part.comparators)
                )
                and any(
                    isinstance(member, ast.Attribute)
                    and isinstance(member.value, ast.Name)
                    and member.value.id == "ExportValuePolicy"
                    for member in ast.walk(part)
                )
                for part in _scope_nodes(scope)
            )
        return False

    def _constraint_class(self, node: ast.AST) -> ast.ClassDef | None:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.ClassDef):
                return current
        return None

    def _technical_bound(self, node: ast.Call, low: float | None, high: float | None) -> bool:
        field, _annotation = self._constraint_declaration(node)
        owner = self._owner
        if field == "http_status" and (low, high) == (100, 599):
            return owner in {"application/connectivity_probe.py", "application/workflow/run_models.py"}
        if (low, high) == (0, 366) and field in {"dias_miembro", "dias_arrendamiento"}:
            # The calendar envelope belongs to this wire mirror's unchanged
            # transfer into the canonical domain row, not to an arbitrary cap.
            owner_class = self._constraint_class(node)
            row_type = _imports_for(self._tree, self._module).get("Modelo184MemberRow")
            return (
                owner == "application/modelo/edit_apply_row_contracts.py"
                and row_type == ("cadrumo.domain.modelos.row_models", "Modelo184MemberRow")
                and owner_class is not None
                and any(
                    isinstance(function, ast.FunctionDef)
                    and function.name == "to_row"
                    and any(
                        isinstance(call, ast.Call)
                        and _called_name(call) == "Modelo184MemberRow"
                        and any(
                            arg.arg == field
                            and isinstance(arg.value, ast.Attribute)
                            and isinstance(arg.value.value, ast.Name)
                            and arg.value.value.id == "self"
                            and arg.value.attr == field
                            for arg in call.keywords
                        )
                        for call in ast.walk(function)
                    )
                    for function in owner_class.body
                )
            )
        if field == "quarters_filed" and (low, high) == (1, 4):
            return owner in {"application/modelo/projection.py", "application/modelo/projection_operation.py"} and any(
                isinstance(part, ast.Attribute) and part.attr in {"is_quarterly", "quarters_available"}
                for part in ast.walk(self._tree)
            )
        if field == "lookback_years" and (low, high) == (1, 50):
            return (
                owner == "core/external_constants.py"
                and "aeat_notifications_query" in self._enclosing_function(node).lower()
            )
        if field == "cadrumo_bucket_default_session_absolute_minutes" and (low, high) == (60, 720):
            return owner == "core/config_runtime_fields.py"
        if high == 9999 and field.endswith("year"):
            return any(
                keyword.arg == "ge"
                and isinstance(keyword.value, ast.Name)
                and _imports_for(self._tree, self._module).get(keyword.value.id)
                == ("cadrumo.core.filing_year", "FILING_YEAR_MIN")
                for keyword in node.keywords
            )
        return False

    def _plurality_bound(self, node: ast.Call, low: float | None, high: float | None) -> bool:
        if (low, high) == (2, 2):
            field, _annotation = self._constraint_declaration(node)
            return self._owner == "application/modelo/projection_operation.py" and field == "years"
        if low != 2 or high is not None:
            return False
        field, annotation = self._constraint_declaration(node)
        names = _expression_names(annotation) if annotation is not None else ""
        if self._owner in {"application/ledger/merge_operation.py", "application/ledger/split_operation.py"}:
            return any(token in names for token in {"TransactionId", "_TransactionPrefix", "LedgerSplitChildRequest"})
        if self._owner == "application/workflow/resume_contracts.py":
            return field == "candidates" and "WorkflowResumeCandidateSnapshot" in names
        if self._owner == "application/inventory/registered_requests.py":
            return (
                field == "evidence"
                and "PhysicalClosingEvidence" in names
                and _imports_for(self._tree, self._module).get("PhysicalClosingEvidence")
                == ("cadrumo.domain.contribuyente.inventory.closing_foundations", "PhysicalClosingEvidence")
            )
        return False

    def _month_keyed(self, node: ast.Constant) -> bool:
        """A month number keying a text that names that same month is a calendar table."""
        parent = self._parents.get(node)
        if not isinstance(parent, ast.Dict) or node not in parent.keys:
            return False
        value = parent.values[parent.keys.index(node)]
        return isinstance(value, ast.Constant) and f"month_{node.value}" in str(value.value)

    def _defines_period_code(self, node: ast.Constant) -> bool:
        """A member of the enum the gate reads the period codes from is their definition."""
        assignment = self._parents.get(node)
        owner = self._parents.get(assignment) if isinstance(assignment, ast.Assign) else None
        return isinstance(owner, ast.ClassDef) and owner.name == _PERIOD_ENUM

    def _is_command_path_segment(self, node: ast.Constant) -> bool:
        """A segment of a tuple rooted at a command family spells a CLI path, not a fact."""
        path = self._parents.get(node)
        if not isinstance(path, ast.Tuple) or not path.elts:
            return False
        root = path.elts[0]
        return isinstance(root, ast.Constant) and root.value in _COMMAND_ROOTS and root is not node

    def _annotated_context(self, node: ast.AST) -> str:
        """Return the names of the assignment target, comparison side or subscript around ``node``."""
        current = node
        while current in self._parents:
            parent = self._parents[current]
            if isinstance(parent, ast.Compare):
                return _expression_names(parent)
            if isinstance(parent, ast.keyword):
                return parent.arg or ""
            if isinstance(parent, ast.Assign):
                return " ".join(_expression_names(target) for target in parent.targets)
            if isinstance(parent, ast.AnnAssign):
                return _expression_names(parent.target)
            if isinstance(parent, ast.Call):
                return _called_name(parent)
            if isinstance(parent, (ast.stmt, ast.Lambda)):
                return ""
            current = parent
        return ""

    def _stands_as_address(self, node: ast.Constant) -> bool:
        parent = self._parents.get(node)
        if isinstance(parent, ast.Call) and _called_name(parent) in _MODELO_ADDRESS_CALLS:
            return True
        if isinstance(parent, ast.keyword) and parent.arg in _ADDRESS_KEYWORDS:
            return True
        context = self._annotated_context(node)
        return bool(_MODELO_NAME.search(context) or _PERIOD_NAME.search(context))

    @override
    def visit_Call(self, node: ast.Call) -> None:
        name = _called_name(node)
        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        if name == "Decimal" and len(node.args) == 1:
            argument = node.args[0]
            literal = argument.value if isinstance(argument, ast.Constant) else None
            if isinstance(literal, (str, int, float)) and not _lawful_decimal(str(literal)):
                self._report("decimal", literal, node)
        if name in _PATTERN_CALLS:
            self._visit_constraints(node, keywords)
        if name in _REGEX_CALLS and node.args:
            self._visit_regex(node.args[0], node)
        if name == "timedelta":
            days = keywords.get("days", node.args[0] if node.args else None)
            number = _constant_number(days)
            if number is not None and number not in _ARITHMETIC_BOUNDS:
                self._report("timedelta", number, node)
        if name == "date" and len(node.args) == 3:
            self._visit_date(node)
        self.generic_visit(node)

    def _visit_constraints(self, node: ast.Call, keywords: dict[str | None, ast.expr]) -> None:
        pattern = keywords.get("pattern")
        text = pattern.value if isinstance(pattern, ast.Constant) and isinstance(pattern.value, str) else None
        if pattern is not None:
            self._visit_regex(pattern, node)
        low = _constant_number(keywords.get("ge", keywords.get("gt")))
        high = _constant_number(keywords.get("le", keywords.get("lt")))
        if not _lawful_range(low, high) and not self._technical_bound(node, low, high):
            self._report("field_bound", (low, high), node)
        lengths = {arg: _constant_number(keywords.get(arg)) for arg in _LENGTH_BOUNDS}
        _field, annotation = self._constraint_declaration(node)
        lexical = (
            _called_name(node) == "StringConstraints"
            or _annotation_kind(annotation, self._tree, self._module) == "text"
        )
        if (
            not lexical
            and not self._plurality_bound(node, lengths["min_length"], lengths["max_length"])
            and not _lawful_length(lengths["min_length"], lengths["max_length"], text)
        ):
            self._report("field_length", (lengths["min_length"], lengths["max_length"]), node)

    def _visit_regex(self, pattern: ast.AST, node: ast.AST) -> None:
        if not isinstance(pattern, ast.Constant) or not isinstance(pattern.value, str):
            return
        repeated_groups = [width for width in _WIDTH_QUANTIFIER.findall(pattern.value) if width[0] == ")"]
        uuid_shape = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}" in pattern.value.lower()
        if repeated_groups and not uuid_shape:
            self._report("regex_width", pattern.value, node)
        for group in re.findall(r"\((?:\?:)?([0-9A-Z]+(?:\|[0-9A-Z]+)+)\)", pattern.value):
            alternatives = tuple(group.split("|"))
            if set(alternatives).issubset(self._modelos):
                self._report("modelo_set", ",".join(sorted(alternatives)), node)
        if re.search(r"(?<![0-9\\])(?:19|20)[0-9]{2}[-/]", pattern.value):
            self._report("regex_year", pattern.value, node)
        members = _fixed_pattern_members(pattern.value)
        if members == (self._own_form,):
            return
        if len(members) > 1 and set(members).issubset(self._modelos):
            self._report("modelo_set", ",".join(sorted(members)), node)
        elif members and any(_CODE_SHAPED.fullmatch(member) for member in members):
            self._report("regex_values", members, node)
        else:
            field, _annotation = self._constraint_declaration(node)
            if members and _CLAVE_NAME.search(field) and not _COUNTRY_NAME.search(field):
                self._report("letter_clave", members, node)

    def _visit_date(self, node: ast.Call) -> None:
        year, month, day = (_constant_number(argument) for argument in node.args)
        if year is not None:
            if (year, month, day) != _EXCEL_EPOCH:
                self._report("date_literal", (year, month, day), node)
        elif month is not None and day is not None and (month, day) not in _YEAR_ENDPOINTS:
            self._report("date_literal", (month, day), node)

    @override
    def visit_Compare(self, node: ast.Compare) -> None:
        length_calls = [
            side
            for side in (node.left, *node.comparators)
            if isinstance(side, ast.Call) and _called_name(side) == "len"
        ]
        is_len = bool(length_calls)
        structural_len = is_len and all(self._structural_length(call, node) for call in length_calls)
        reads_code_point = any(
            isinstance(side, ast.Call) and _called_name(side) == "ord" for side in (node.left, *node.comparators)
        )
        for side in (node.left, *node.comparators):
            if self._modelo_literal(side):
                self._report("modelo_compare", ast.unparse(node), node)
            number = _constant_number(side)
            if number is None or reads_code_point:
                continue
            if _FIRST_YEAR < number < _LAST_YEAR and not is_len:
                self._report("year_branch", number, node)
            elif (
                number not in _ARITHMETIC_COMPARE
                and not _machine_capacity(number)
                and not self._machine
                and not structural_len
                and number != _SHA256_HEX
                and (is_len or number not in _CALENDAR_VALUES)
                and not (is_len and _STANDARD_SHAPE_FUNCTION.search(self._enclosing_function(node)))
            ):
                self._report("len_compare" if is_len else "threshold", number, node)
        if is_len and not self._machine and not structural_len:
            for side in node.comparators:
                if isinstance(side, (ast.Set, ast.Tuple, ast.List)):
                    self._report("len_in", ast.unparse(side), node)
        self.generic_visit(node)

    def _modelo_literal(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Call):
            node = node.value
        if isinstance(node, ast.Call) and _called_name(node) == "Modelo":
            return True
        return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in self._modelos

    @override
    def visit_Match(self, node: ast.Match) -> None:
        for case in node.cases:
            for pattern in ast.walk(case.pattern):
                if isinstance(pattern, ast.MatchValue) and isinstance(pattern.value, ast.Constant):
                    value = pattern.value.value
                    if isinstance(value, (int, float)) or (isinstance(value, str) and _CODE_SHAPED.match(value)):
                        self._report("match_case", value, pattern)
        self.generic_visit(node)

    @override
    def visit_Dict(self, node: ast.Dict) -> None:
        for key in node.keys:
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and _CODE_SHAPED.match(key.value)
                and not self._month_keyed(key)
            ):
                self._report("dict_key", key.value, key)
        for value in node.values:
            self.visit(value)

    @override
    def visit_Subscript(self, node: ast.Subscript) -> None:
        target = node.value
        if (target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")) == "Literal":
            for member in ast.walk(node.slice):
                if (
                    isinstance(member, ast.Constant)
                    and isinstance(member.value, str)
                    and _CODE_SHAPED.match(member.value)
                ):
                    self._report("literal_type", member.value, member)
            return
        self.generic_visit(node)

    def _visit_collection(self, node: ast.Set | ast.Tuple | ast.List) -> None:
        months = [_constant_number(element) for element in node.elts]
        if (
            len(months) >= _MONTH_TUPLE_LENGTH
            and all(month is not None and 1 <= month <= _MONTHS_OF_A_YEAR for month in months)
            and (isinstance(node, ast.Set) or months == sorted({month for month in months if month is not None}))
        ):
            self._report("month_tuple", tuple(months), node)
        ids: list[str] = []
        for element in node.elts:
            literal = element
            if isinstance(element, ast.Attribute) and isinstance(element.value, ast.Call):
                literal = element.value
            if isinstance(literal, ast.Call) and _called_name(literal) == "Modelo" and literal.args:
                literal = literal.args[0]
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str) and literal.value in self._modelos:
                ids.append(literal.value)
        if len(ids) >= 2 and len(ids) == len(node.elts):
            self._report("modelo_set", ",".join(sorted(ids)), node)
        self.generic_visit(node)

    @override
    def visit_Set(self, node: ast.Set) -> None:
        self._visit_collection(node)

    @override
    def visit_Tuple(self, node: ast.Tuple) -> None:
        self._visit_collection(node)

    @override
    def visit_List(self, node: ast.List) -> None:
        self._visit_collection(node)

    @override
    def visit_Constant(self, node: ast.Constant) -> None:
        value = node.value
        if not isinstance(value, str) or node in self._docstrings:
            return
        parent = self._parents.get(node)
        if isinstance(parent, ast.Call) and _called_name(parent) == "Decimal":
            return
        if _CODE_SHAPED.match(value):
            if value == self._own_form or self._month_keyed(node):
                return
            if self._defines_period_code(node) or self._is_command_path_segment(node):
                return
            if _EDITION_NAME.search(self._annotated_context(node)) and not isinstance(
                self._parents.get(node), ast.Compare
            ):
                return
            if (
                value.isdigit()
                and int(value) <= _MONTHS_OF_A_YEAR
                and _MONTH_NAME.search(self._annotated_context(node))
            ):
                return
            if value.isdigit() and int(value) in _DAYS_OF_A_YEAR and _DAY_NAME.search(self._annotated_context(node)):
                return
            if value in self._periods and self._stands_as_address(node):
                return
            if value in self._modelos and self._stands_as_address(node):
                return
            if value not in self._modelos and value not in self._periods and self._stands_as_address(node):
                return
            self._report("code", value, node)
        elif (
            _LETTER_CLAVE.match(value)
            and _CLAVE_NAME.search(context := self._annotated_context(node))
            and not _COUNTRY_NAME.search(context)
        ):
            self._report("letter_clave", value, node)


def sweep_source(
    source: str,
    *,
    modelos: frozenset[str],
    periods: frozenset[str],
    module: str = "",
    machine: bool = False,
    owner: str = "",
) -> list[str]:
    """Return one ``kind:value@line`` entry per literal of ``source`` standing where a tax fact could.

    ``module`` names the file: a module named for one form may name that form. ``machine``
    marks an owner whose comparisons read operating system answers and byte sizes.
    """
    tree = ast.parse(source)
    form_named = _FORM_NAMED_MODULE.search(module)
    sweep = _Sweep(tree, modelos, periods, form_named[1] if form_named else None, machine=machine, owner=owner)
    sweep.visit(tree)
    return sweep.findings


def sweep_tree(root: Path, *, modelos: frozenset[str], periods: frozenset[str]) -> dict[str, list[str]]:
    """Return the findings of every production module below ``root``, by relative path."""
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if "tests" in relative.parts:
            continue
        owner = f"{root.name}/{relative.as_posix()}"
        findings = sweep_source(
            path.read_text(encoding="utf-8"),
            modelos=modelos,
            periods=periods,
            module=path.stem,
            machine=owner.startswith(_MACHINE_OWNERS),
            owner=owner,
        )
        if findings:
            found[relative.as_posix()] = findings
    return found


def _current() -> dict[str, list[str]]:
    modelos, periods = _modelo_ids(), _period_codes()
    found: dict[str, list[str]] = {}
    for top in _SCANNED:
        for path, entries in sweep_tree(top, modelos=modelos, periods=periods).items():
            found[f"{top.name}/{path}"] = entries
    return found


_FAKE_MODELOS: Final = frozenset({"303", "111", "100"})
_FAKE_PERIODS: Final = frozenset({"0A", "1T", "01"})


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("cap = Decimal('300.51')\n", "decimal"),
        ("clave: int = Field(ge=1, le=6)\n", "field_bound"),
        ("rows: tuple[int, ...] = Field(min_length=18, max_length=18)\n", "field_length"),
        ("rows: tuple[int, ...] = Field(max_length=12)\n", "field_length"),
        ("ok = len(row) == 3\n", "len_compare"),
        ("BOX = '0208'\n", "code"),
        ("descendant_count: int = Field(ge=0, le=10)\n", "field_bound"),
        ("if revision_id == '2022':\n    pass\n", "code"),
        ("box = '303'\n", "code"),
        ("ROUTED = frozenset({Modelo('111').value, Modelo('303').value})\n", "modelo_set"),
        ("ok = modelo in {'111', '303'}\n", "modelo_set"),
        ("if clave == 'A':\n    pass\n", "letter_clave"),
        ("subclave = 'B'\n", "letter_clave"),
        ("tipo_renta_code: str = 'XY'\n", "letter_clave"),
        ("first_year: int = Field(ge=2012)\n", "field_bound"),
        ("month: int = Field(le=13)\n", "field_bound"),
        ("minimum_days: int = Field(le=180)\n", "field_bound"),
        ("slot: int = Field(ge=1, le=5)\n", "field_bound"),
        ("deduction_limit: int = Field(le=300)\n", "field_bound"),
        ("rate = Decimal('0.19')\n", "decimal"),
        ("cap = Decimal('1000')\n", "decimal"),
        ("MAX = Decimal('999999.99')\n", "decimal"),
        ("limit: int = Field(max_length=99)\n", "field_length"),
        ("if income > 12450:\n    pass\n", "threshold"),
        ("if width > 77:\n    pass\n", "threshold"),
        ("slot_width: int = Field(ge=2, le=9)\n", "field_bound"),
        ("if ejercicio == 2022:\n    pass\n", "year_branch"),
        ("QUARTERS = (1, 4, 7, 10)\n", "month_tuple"),
        ("QUARTERS = {10, 1, 7, 4}\n", "month_tuple"),
        ("if code == 127:\n    pass\n", "threshold"),
        ("start = date(2023, 1, 1)\n", "date_literal"),
        ("end = date(year, 7, 30)\n", "date_literal"),
        ("due = today + timedelta(days=20)\n", "timedelta"),
        ("modelo: Literal['100']\n", "literal_type"),
        ("if modelo == '303':\n    pass\n", "modelo_compare"),
        ("if context.modelo == Modelo('100').value:\n    pass\n", "modelo_compare"),
        ("match code:\n    case '0208':\n        pass\n", "match_case"),
        ("ROWS = {'0208': 1}\n", "dict_key"),
        ("ok = len(code) in {3, 4}\n", "len_in"),
        ("class OtherCodes(StrEnum):\n    JAN = '01'\n", "code"),
        ("class StandardPeriodCode(StrEnum):\n    def f(self):\n        box = '01'\n", "code"),
        ("PATH = ('ledger', '100', 'import')\n", "code"),
    ],
)
def test_the_sweep_rejects_a_representative_tax_literal(line: str, kind: str) -> None:
    findings = sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS)
    assert any(finding.startswith(f"{kind}:") for finding in findings), findings


@pytest.mark.parametrize(
    "line",
    [
        "code: Annotated[str, StringConstraints(min_length=2, max_length=2)]\n",
        "code: str = Field(pattern=r'^\\d{3}$')\n",
        "CODE = re.compile(r'^[A-Z]{2}\\d{3}$')\n",
        "code: str = Field(min_length=16, max_length=16)\n",
        "BOX = re.compile(r'^(?P<box>\\d{4})$')\n",
        "x = Decimal('0.01')\n",
        "rate = value / Decimal('100')\n",
        "name: str = Field(max_length=128)\n",
        "name: str = Field(max_length=4096)\n",
        "count: int = Field(ge=0)\n",
        "directory = operation.modelo_directory('303')\n",
        "selected = Modelo('303')\n",
        "work = load(modelo='303', period='1T')\n",
        '"""A docstring may cite casilla 0208 and clave A."""\n',
        "label = 'A'\n",
        "end = date(year, 12, 31)\n",
        "start = date(year, 1, 1)\n",
        "EPOCH = date(1899, 12, 30)\n",
        "later = now + timedelta(hours=18)\n",
        "next_day = day + timedelta(days=1)\n",
        "year: int = Field(ge=1900, le=9999)\n",
        "month: Annotated[int, Field(ge=1, le=12)]\n",
        "calendar_days: int = Field(ge=365, le=366)\n",
        "digest: str = Field(pattern=r'^[0-9a-f]{64}$', min_length=64, max_length=64)\n",
        "run: str = Field(pattern=r'^[0-9a-f]{16}$', min_length=16, max_length=16)\n",
        "ISO = re.compile(r'\\d{4}-\\d{2}-\\d{2}')\n",
        "GAP = re.compile(r'Ejercicio.{0,80}?x')\n",
        "_SPAIN_COUNTRY_CODE = 'ES'\n",
        "NAMES = {'01': 'finding.month_01'}\n",
        "REVISION_ID = '2022'\n",
        "def _validate_yyyymmdd(raw):\n    return len(raw) != 8\n",
        "def _territory_definition(code):\n    return len(code) != 5\n",
        "def _impatriado_jurisdictions_are_canonical(values):\n    return all(len(value) == 2 for value in values)\n",
        "class ModeloCode(str):\n    def __new__(cls, raw):\n        return len(raw) != 3\n",
        "def _require_selector_address(target):\n    return len(target) == 16\n",
        "ok = len(target_period) == 2\n",
        "class StandardPeriodCode(StrEnum):\n    JAN = '01'\n",
        "PATH = ('app', 'live', 'borrador', '100', 'import')\n",
        "DISPLAY = re.compile(r'^(?P<year>\\d{4})\\s+x$')\n",
        "ok = ord(character) == 127\n",
        "ok = 0xD800 <= ord(character) <= 0xDFFF\n",
        "unset = Decimal('NaN')\n",
        "widths = (3, 12, 12, 7)\n",
        "parts = {(4, 2, 2)}\n",
        "parts = {(1, 8, 2)}\n",
    ],
)
def test_the_sweep_admits_what_stands_where_no_tax_fact_can(line: str) -> None:
    assert sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("CODE = re.compile(r'^(?:0208|0209)$')", "regex_values"),
        ("MODELS = re.compile(r'^(?:111|303)$')", "modelo_set"),
        ("MODELS = re.compile(r'^(?:111|303)-\\d{4}$')", "modelo_set"),
        ("CUTOFF = re.compile(r'^2024-\\d{2}-\\d{2}$')", "regex_year"),
        ("clave: str = Field(pattern=r'^(?:A|B)$')", "letter_clave"),
        ("ROWS = re.compile(r'^(?:row;){18}$')", "regex_width"),
        ("rows: tuple[int, ...] = Field(min_length=2, max_length=2)", "field_length"),
        ("qualifying_children: tuple[int, ...] = Field(min_length=2)", "field_length"),
        ("clave: int = Field(ge=1, le=4)", "field_bound"),
        ("deduction: int = Field(ge=0, le=366)", "field_bound"),
        ("tax_years: int = Field(ge=1, le=50)", "field_bound"),
        ("rows = 'text'\ndef f(rows):\n    return len(rows) > 12", "len_compare"),
        ("def f(rows):\n    def nested():\n        rows = 'text'\n    return len(rows) > 12", "len_compare"),
        (
            "def f(raw: str, rows: list[int]):\n    value = rows\n"
            "    if rows:\n        value = raw\n    return len(value) > 12",
            "len_compare",
        ),
        ("def f(rows):\n    return 12 < len(rows)", "len_compare"),
        ("def f(rows):\n    a, b, c = rows\n    return len(rows) == 3", "len_compare"),
    ],
)
def test_grammar_classification_preserves_fiscal_members_and_unknown_collections(source: str, kind: str) -> None:
    assert any(
        item.startswith(kind + ":") for item in sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS)
    )


@pytest.mark.parametrize(
    "source",
    [
        "def parse(raw: str):\n    parts = raw.split('-')\n    return len(parts) == 3",
        "def parse(raw: str):\n    whole, fraction = raw.rsplit(',', 1)\n    return len(fraction) in {1, 2}",
        "from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression\n"
        "def evaluate(expression: FormulaExpression):\n    return len(expression.args) == 12",
        "from urllib.parse import SplitResult\n"
        "def parse(value: SplitResult):\n    return len(value.path.split('/')) == 4",
        "COUNTRY = re.compile(r'^(?:ES|FR)$')",
    ],
)
def test_scalar_and_record_grammar_is_proven_by_its_producer(source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


@pytest.mark.parametrize(
    ("owner", "source"),
    [
        ("application/connectivity_probe.py", "http_status: int = Field(ge=100, le=599)"),
        ("core/external_constants.py", "class AeatNotificationsQuery:\n    lookback_years: int = Field(ge=1, le=50)"),
        (
            "core/config_runtime_fields.py",
            "cadrumo_bucket_default_session_absolute_minutes: int = Field(ge=60, le=720)",
        ),
        (
            "application/workflow/resume_contracts.py",
            "candidates: tuple[WorkflowResumeCandidateSnapshot, ...] = Field(min_length=2)",
        ),
    ],
)
def test_canonical_technical_roles_admit_only_their_own_constraints(owner: str, source: str) -> None:
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []
    defects = "\ncap = Decimal('300.51')\nclave: int = Field(ge=1, le=4)\nrows: tuple[int, ...] = Field(max_length=12)"
    findings = sweep_source(source + defects, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
    assert {finding.split(":", 1)[0] for finding in findings} >= {"decimal", "field_bound", "field_length"}


def test_collection_names_cannot_borrow_a_technical_owner_exemption() -> None:
    source = "qualifying_children: tuple[Child, ...] = Field(min_length=2)"
    for owner in (
        "application/ledger/merge_operation.py",
        "application/inventory/registered_requests.py",
        "application/workflow/resume_contracts.py",
    ):
        assert any(
            f.startswith("field_length:")
            for f in sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
        )


def test_inventory_plurality_requires_its_canonical_evidence_type() -> None:
    field = "evidence: tuple[PhysicalClosingEvidence, ...] = Field(min_length=2)"
    owner = "application/inventory/registered_requests.py"
    canonical = "from cadrumo.domain.contribuyente.inventory.closing_foundations import PhysicalClosingEvidence\n"
    assert sweep_source(canonical + field, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []
    counterfeit = "from unrelated import PhysicalClosingEvidence\n"
    assert any(
        f.startswith("field_length:")
        for f in sweep_source(counterfeit + field, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner)
    )


def test_nested_import_cannot_authorize_a_module_field_annotation() -> None:
    canonical = "from cadrumo.core.i18n.translatable import Translatable as Token\n"
    field = "value: Token = Field(max_length=12)\n"
    assert sweep_source(canonical + field, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []
    source = f"from unrelated import Token\ndef nested():\n    {canonical}{field}"
    assert any(
        f.startswith("field_length:")
        for f in sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner="application/example.py")
    )


def test_calendar_day_wire_bound_requires_unchanged_domain_transfer() -> None:
    source = (
        "from cadrumo.domain.modelos.row_models import Modelo184MemberRow\n"
        "class Wire:\n    dias_miembro: int = Field(ge=0, le=366)\n"
        "    def to_row(self):\n        return Modelo184MemberRow(dias_miembro=self.dias_miembro)"
    )
    owner = "application/modelo/edit_apply_row_contracts.py"
    assert sweep_source(source, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, owner=owner) == []
    assert any(
        f.startswith("field_bound:")
        for f in sweep_source(
            source.replace("dias_miembro=self.dias_miembro", "dias_miembro=0"),
            modelos=_FAKE_MODELOS,
            periods=_FAKE_PERIODS,
            owner=owner,
        )
    )


def test_a_module_named_for_one_form_may_name_that_form_and_no_other() -> None:
    line = "box = '303'\nother = '111'\n"
    findings = sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, module="m303_arrivals")
    assert findings == ["code:'111'@2"]


def test_a_machine_owner_may_compare_sizes_but_not_hold_a_tax_value() -> None:
    assert sweep_source("ok = status == 404\n", modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, machine=True) == []
    findings = sweep_source("cap = Decimal('300.51')\n", modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, machine=True)
    assert findings == ["decimal:'300.51'@1"]


def test_a_defect_added_to_a_copied_tree_is_found(tmp_path: Path) -> None:
    source = _SRC / "domain" / "period.py"
    copy = tmp_path / "domain" / "period.py"
    copy.parent.mkdir(parents=True)
    copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    modelos, periods = _modelo_ids(), _period_codes()
    clean = sweep_tree(tmp_path, modelos=modelos, periods=periods)

    with copy.open("a", encoding="utf-8") as handle:
        handle.write("\n_INSTALMENT_CAP = Decimal('300.51')\n")

    found = sweep_tree(tmp_path, modelos=modelos, periods=periods)["domain/period.py"]
    assert set(found) - set(clean.get("domain/period.py", ())) == {
        f"decimal:'300.51'@{len(copy.read_text(encoding='utf-8').splitlines())}"
    }


_STRICT_FORM_READERS = frozenset(
    {
        "resolve_form_codes",
        "form_for_role",
        "forms_for_role",
        "periodic_withholding_modelos",
        "invoice_evidence_modelos",
        "ledger_payment_modelos",
    }
)
_VALIDATOR_DECORATORS = frozenset({"field_validator", "model_validator"})


def _reader_name(node: ast.AST) -> str:
    return str(getattr(node, "id", getattr(node, "attr", "")))


def _strict_reads_in_validators(tree: ast.AST) -> list[tuple[int, str]]:
    """Return strict form-fact reads inside Pydantic validators, which a scope-free client also runs."""
    found: list[tuple[int, str]] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        decorators = {_reader_name(n) for d in function.decorator_list for n in ast.walk(d)}
        if decorators & _VALIDATOR_DECORATORS:
            found += [
                (call.lineno, function.name)
                for call in ast.walk(function)
                if isinstance(call, ast.Call) and _reader_name(call.func) in _STRICT_FORM_READERS
            ]
    return found


def test_the_validator_rule_finds_a_strict_read() -> None:
    source = """
class M(BaseModel):
    @model_validator(mode="after")
    def _v(self):
        resolve_form_codes("x")
        return self
"""
    assert _strict_reads_in_validators(ast.parse(source)) == [(5, "_v")]
    assert _strict_reads_in_validators(ast.parse("def f():\n    resolve_form_codes('x')\n")) == []


def test_no_validator_turns_a_valid_client_result_into_an_error() -> None:
    src = Path(__file__).resolve().parents[3] / "src"
    findings = [
        f"{path}:{line} {name}"
        for path in src.rglob("*.py")
        if "tests" not in path.parts
        for line, name in _strict_reads_in_validators(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert not findings, "\n".join(findings)


def test_the_tax_code_holds_no_tax_literal() -> None:
    found = _current()
    listing = "\n".join(f"{path}: {entry}" for path, entries in sorted(found.items()) for entry in entries)
    assert not found, f"a tax value belongs to the registry:\n{listing}"
