"""The visitor that finds tax literals in a module, and the entry points that run it."""

from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path
from typing import override

from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_LAST

from .tax_literal_sweep_kinds import (
    BoundReader,
)
from .tax_literal_sweep_vocabulary import (
    ADDRESS_KEYWORDS,
    ARITHMETIC_BOUNDS,
    ARITHMETIC_COMPARE,
    ARITHMETIC_OPERANDS,
    ARITHMETIC_PERCENT,
    CALENDAR_RANGES,
    CALENDAR_UNITS,
    CALENDAR_VALUES,
    CHECKBOX_MARK,
    CLAVE_NAME,
    CLOCK_CALLS,
    CODE_LETTERS,
    CODE_LIST,
    CODE_SHAPED,
    COLLECTION_CALLS,
    COMMAND_ROOTS,
    COUNTRY_NAME,
    DATE_CALLS,
    DATE_TEXTS,
    DAY_NAME,
    DAYS_OF_A_YEAR,
    DECIMAL_MODULE_NAMES,
    EDITION_TAIL,
    EPOCHS,
    FACT_WORDS,
    FILE_PERMISSION_NAME,
    FILE_PERMISSIONS,
    FIRST_YEAR,
    FORM_HANDING_MODULE,
    FORM_HANDING_OWNERS,
    FORM_NAMED_MODULE,
    FORM_SHAPE_WORDS,
    HEX_CLASSES,
    IDENTITY_NUMBERS,
    ISO_DATE,
    KEYWORD_MECHANICS,
    LAST_YEAR,
    LEAP_DAY_SHIFT,
    LENGTH_BOUNDS,
    LETTER_CLAVE,
    MACHINE_OWNERS,
    MECHANICS_OWNERS,
    MODELO_ADDRESS_CALLS,
    MODELO_ID_DECLARATION,
    MODELO_TAIL,
    MONTH_NAME,
    MONTH_TUPLE_LENGTH,
    MONTHS_OF_A_YEAR,
    NUMBER_CALLS,
    PATTERN_CALLS,
    PERIOD_ENUM,
    PERIOD_TAIL,
    POSITIONAL_MECHANICS,
    RECORD_DESIGN_LETTERS,
    RECORD_DESIGN_OWNERS,
    RECORD_DESIGN_READERS,
    REGEX_CALLS,
    SCANNED,
    SHA256_HEX,
    SHEET_GEOMETRY_OWNERS,
    SHEET_GEOMETRY_WORDS,
    SHEET_MEASURES,
    SMALL_COUNT,
    SPELLED_BOX,
    SPELLED_FORM,
    STANDARD_SHAPE_FUNCTION,
    STANDARD_SHAPE_WIDTHS,
    TEXT_NUMBER,
    TEXT_WIDTH_CALLS,
    THOUSAND,
    UNIT_CONVERSIONS,
    VALUE_KEYWORDS,
    WIDTH_QUANTIFIER,
    YEAR_ARITHMETIC_CALLS,
    YEAR_ENDPOINTS,
    YEAR_NAME,
    YEAR_WIDTH,
    YES_NO_LETTERS,
    annotation_kind,
    bare_limit,
    called_name,
    cent_or_finer_text,
    constant_number,
    docstrings,
    expression_names,
    fixed_pattern_members,
    folded_number,
    is_hundred,
    lawful_decimal,
    lawful_length,
    lawful_range,
    machine_capacity,
    machine_unit_name,
    mechanic_name,
    modelo_ids,
    name_words,
    period_codes,
    reader_name,
    rounding_quantum,
    single_code_letter,
    tax_name,
    terminal_name,
    wire_capacity,
)


class _Sweep(BoundReader, ast.NodeVisitor):
    def __init__(
        self,
        tree: ast.Module,
        modelos: frozenset[str],
        periods: frozenset[str],
        own_form: str | None,
        *,
        machine: bool = False,
        owner: str = "",
        form_handing: bool = False,
    ) -> None:
        self._form_handing = form_handing
        self._tree = tree
        self._owner = owner
        self._module = owner.removesuffix(".py").replace("/", ".")
        if owner and not owner.startswith("cadrumo_client/"):
            self._module = "cadrumo." + self._module
        self._own_form = own_form
        self._machine = machine
        self._parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        self._docstrings = docstrings(tree)
        self._modelos = modelos
        self._periods = periods
        self._modelo_names = self._names_holding_a_form()
        self._decimal_names = DECIMAL_MODULE_NAMES | {
            alias.asname
            for statement in ast.walk(tree)
            if isinstance(statement, ast.ImportFrom) and statement.module == "decimal"
            for alias in statement.names
            if alias.name == "Decimal" and alias.asname is not None
        }
        self.findings: list[str] = []

    def _names_holding_a_form(self) -> frozenset[str]:
        return frozenset(
            target.id
            for statement in ast.walk(self._tree)
            if isinstance(statement, ast.Assign) and self._form_code_of(statement.value) is not None
            for target in statement.targets
            if isinstance(target, ast.Name)
        )

    def _form_code_of(self, node: ast.AST | None) -> str | None:
        """Return the form code spelled by ``node``: a literal, ``Modelo('303')`` or its ``.value``."""
        if isinstance(node, ast.Attribute) and node.attr == "value":
            node = node.value
        if isinstance(node, ast.Call) and called_name(node) == "Modelo" and node.args:
            node = node.args[0]
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in self._modelos:
            return node.value
        return None

    def _reads_name(self, name: str) -> bool:
        """A tax word in a name is read even in an owner that only lays values out."""
        return self._holds_facts() or (not self._machine and tax_name(name))

    def _measures_the_sheet(self, node: ast.AST) -> bool:
        """Return whether a name around ``node`` says it measures a worksheet."""
        current = node
        while current is not None:
            names: list[str] = []
            if isinstance(current, ast.keyword):
                names.append(current.arg or "")
            elif isinstance(current, ast.Assign):
                names += [expression_names(target) for target in current.targets]
            elif isinstance(current, (ast.AnnAssign, ast.For)):
                names.append(expression_names(current.target))
            elif isinstance(current, ast.Compare):
                names.append(expression_names(current))
            elif isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(current.name)
            joined = "_".join(names).replace(" ", "_")
            if name_words(joined) & SHEET_GEOMETRY_WORDS and not tax_name(joined):
                return True
            current = self._parents.get(current)
        return False

    def _report(self, kind: str, value: object, node: ast.AST) -> None:
        if kind in SHEET_MEASURES and self._owner.startswith(SHEET_GEOMETRY_OWNERS) and self._measures_the_sheet(node):
            return
        self.findings.append(f"{kind}:{value!r}@{getattr(node, 'lineno', 0)}")

    @override
    def visit_Module(self, node: ast.Module) -> None:
        """Read each module-level number through what its name and its reads say it is."""
        for statement in node.body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target, value = statement.targets[0], statement.value
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                target, value = statement.target, statement.value
            else:
                continue
            number = folded_number(value)
            if (
                number is not None
                and isinstance(target, ast.Name)
                and not self._named_value_admitted(target.id, number)
            ):
                self._report("module_value", f"{target.id}={number}", statement)
            form = self._form_code_of(value)
            if form is not None and form != self._own_form and isinstance(target, ast.Name):
                self._report("named_form", f"{target.id}={form}", statement)
        self.generic_visit(node)

    def _spells_another_form(self, value: str) -> bool:
        spelled = SPELLED_FORM.match(value)
        if spelled is None:
            return False
        form = str(spelled[1])
        return form in self._modelos and form != self._own_form

    def _named_value_admitted(self, name: str, number: float) -> bool:
        if self._machine:
            return True
        if tax_name(name):
            return number in IDENTITY_NUMBERS
        if self._owner.startswith(MECHANICS_OWNERS) or machine_unit_name(name) or mechanic_name(name):
            return True
        if FILE_PERMISSION_NAME.search(name) and number in FILE_PERMISSIONS:
            return True
        if number in ARITHMETIC_COMPARE:
            return True
        if self._names_its_calendar_unit(name, number) or (machine_capacity(number) and not bare_limit(name)):
            return True
        if number in {FIRST_YEAR, LAST_YEAR} and YEAR_NAME.search(name):
            return True
        return self._only_cuts_a_sequence_short(name) or self._only_bounds_a_wire_length(name, number)

    @staticmethod
    def _names_its_calendar_unit(name: str, number: float) -> bool:
        """A calendar number stands only under the unit it counts: twelve months, not twelve of anything."""
        units = CALENDAR_UNITS.get(number)
        return units is not None and bool(name_words(name) & units)

    def _only_bounds_a_wire_length(self, name: str, number: float) -> bool:
        """A round thousand is a capacity when every read of it is the ``max_length`` of a field."""
        if not wire_capacity(number):
            return False
        reads = [
            node
            for node in ast.walk(self._tree)
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
        ]
        return bool(reads) and all(self._is_max_length(read) for read in reads)

    def _is_max_length(self, read: ast.Name) -> bool:
        """A wire capacity bounds a text: the longest a value may be, not how many rows a form holds."""
        parent = self._parents.get(read)
        if not (isinstance(parent, ast.keyword) and parent.arg == "max_length"):
            return False
        _field, annotation = self._constraint_declaration(read)
        return annotation_kind(annotation, self._tree, self._module) != "collection"

    def _only_cuts_a_sequence_short(self, name: str) -> bool:
        """Return whether every read of ``name`` in this module is a slice's end, and it counts no part of a form."""
        if name_words(name) & FORM_SHAPE_WORDS:
            return False
        reads = [
            node
            for node in ast.walk(self._tree)
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
        ]
        return bool(reads) and all(self._is_slice_end(read) for read in reads)

    def _is_slice_end(self, read: ast.Name) -> bool:
        parent = self._parents.get(read)
        return isinstance(parent, ast.Slice) and parent.upper is read

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
        return isinstance(owner, ast.ClassDef) and owner.name == PERIOD_ENUM

    def _is_command_path_segment(self, node: ast.Constant) -> bool:
        """A segment of a tuple rooted at a command family spells a CLI path, not a fact."""
        path = self._parents.get(node)
        if not isinstance(path, ast.Tuple) or not path.elts:
            return False
        root = path.elts[0]
        return isinstance(root, ast.Constant) and root.value in COMMAND_ROOTS and root is not node

    def _annotated_context(self, node: ast.AST) -> str:
        """Return the names of the assignment target, comparison side or subscript around ``node``."""
        current = node
        while current in self._parents:
            parent = self._parents[current]
            if isinstance(parent, ast.Compare):
                return expression_names(parent)
            if isinstance(parent, ast.keyword):
                return parent.arg or ""
            if isinstance(parent, ast.Assign):
                return " ".join(expression_names(target) for target in parent.targets)
            if isinstance(parent, ast.AnnAssign):
                return expression_names(parent.target)
            if isinstance(parent, ast.Call) and called_name(parent) not in COLLECTION_CALLS:
                return called_name(parent)
            if isinstance(parent, (ast.stmt, ast.Lambda)):
                return ""
            current = parent
        return ""

    def _own_side_names(self, node: ast.AST) -> tuple[str, ...]:
        """Return the names the literal itself stands under, read from its own side of what holds it.

        ``period.casilla == '0208'`` stands under ``casilla``, not under ``period``. ``box_token = '0208'`` stands
        under the whole of its target, which is what a tail rule then reads.
        """
        current = node
        while current in self._parents:
            parent = self._parents[current]
            if isinstance(parent, ast.Compare):
                sides = (parent.left, *parent.comparators)
                return tuple(terminal_name(side) for side in sides if side is not current)
            if isinstance(parent, ast.keyword):
                return (parent.arg or "",)
            if isinstance(parent, ast.Assign):
                return tuple(terminal_name(target) for target in parent.targets)
            if isinstance(parent, ast.AnnAssign):
                return (terminal_name(parent.target),)
            if isinstance(parent, ast.Call) and called_name(parent) not in COLLECTION_CALLS:
                return (called_name(parent),)
            if isinstance(parent, (ast.stmt, ast.Lambda)):
                return ()
            current = parent
        return ()

    def _stands_as_address(self, node: ast.Constant, tail: re.Pattern[str]) -> bool:
        parent = self._parents.get(node)
        if isinstance(parent, ast.Call) and called_name(parent) in MODELO_ADDRESS_CALLS:
            return tail is MODELO_TAIL
        if isinstance(parent, ast.keyword) and parent.arg in ADDRESS_KEYWORDS:
            return True
        return any(tail.search(name) for name in self._own_side_names(node))

    @override
    def visit_Call(self, node: ast.Call) -> None:
        name = called_name(node)
        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        if name in self._decimal_names and (len(node.args) == 1 or "value" in keywords):
            self._visit_decimal_call(node, keywords)
        if name == "Fraction" and len(node.args) == 2 and is_hundred(node.args[1]):
            self._report("percent", constant_number(node.args[0]), node)
        if name in NUMBER_CALLS and node.args and self._holds_facts():
            self._visit_number_call(node)
        if name == "startswith" and self._holds_facts() and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and single_code_letter(argument.value):
                self._report("letter_compare", argument.value, node)
        if name == "replace" and self._holds_facts():
            self._visit_date_replacement(node, keywords)
        if name in PATTERN_CALLS:
            self._visit_constraints(node, keywords)
        if self._form_handing:
            self._visit_form_width_call(node, name, keywords)
            if name in TEXT_WIDTH_CALLS:
                self._visit_text_width(node, name)
        if name in REGEX_CALLS and node.args:
            self._visit_regex(node.args[0], node)
        if name == "timedelta":
            self._visit_timedelta(node, keywords)
        if name in DATE_CALLS and (len(node.args) >= 3 or {"month", "day"} <= keywords.keys()):
            self._visit_date(node, keywords)
        if self._holds_facts():
            self._visit_number_arguments(node, name)
        self.generic_visit(node)

    def _visit_decimal_call(self, node: ast.Call, keywords: dict[str | None, ast.expr]) -> None:
        argument = node.args[0] if node.args else keywords["value"]
        literal = argument.value if isinstance(argument, ast.Constant) else None
        if isinstance(literal, (str, int, float)) and not self._quantizes_to(node, str(literal)):
            held_under_tax = cent_or_finer_text(str(literal)) and tax_name(
                self._annotated_context(node).replace(" ", "_")
            )
            if held_under_tax or not lawful_decimal(str(literal)):
                self._report("decimal", literal, node)

    def _visit_timedelta(self, node: ast.Call, keywords: dict[str | None, ast.expr]) -> None:
        for span in (keywords.get("days", node.args[0] if node.args else None), keywords.get("weeks")):
            number = constant_number(span)
            if number is not None and number not in ARITHMETIC_BOUNDS:
                self._report("timedelta", number, node)

    def _visit_number_call(self, node: ast.Call) -> None:
        """``int('12450')`` and ``float('300.51')`` hold what the text says; ``int(raw, 16)`` holds nothing."""
        argument = node.args[0]
        text = argument.value if isinstance(argument, ast.Constant) and isinstance(argument.value, str) else None
        number = constant_number(argument)
        if text is not None and TEXT_NUMBER.match(text):
            number = float(text.replace(",", "."))
        if number is not None and len(node.args) == 1 and self._may_be_fact(number, ""):
            self._report("call_value", f"{called_name(node)}({number})", node)

    def _visit_date_replacement(self, node: ast.Call, keywords: dict[str | None, ast.expr]) -> None:
        month, day = constant_number(keywords.get("month")), constant_number(keywords.get("day"))
        if (month is None and day is None) or (month, day) in YEAR_ENDPOINTS or (month, day) == LEAP_DAY_SHIFT:
            return
        if month not in {None, 1, 12} or day not in {None, 1, 31}:
            self._report("date_literal", (month, day), node)

    def _quantizes_to(self, node: ast.Call, literal: str) -> bool:
        """A power of ten handed straight to ``quantize`` is a precision, whatever its size."""
        parent = self._parents.get(node)
        return (
            isinstance(parent, ast.Call)
            and called_name(parent) == "quantize"
            and node in parent.args
            and rounding_quantum(Decimal(literal))
        )

    def _holds_facts(self) -> bool:
        return not self._machine and not self._owner.startswith(MECHANICS_OWNERS)

    def _visit_number_arguments(self, node: ast.Call, name: str) -> None:
        if name in {"min", "max"}:
            self._visit_clamp(node)
        if name in YEAR_ARITHMETIC_CALLS:
            self._visit_year_arithmetic(node, name)
        if name == "getattr" and len(node.args) == 3 and isinstance(node.args[1], ast.Constant):
            number = constant_number(node.args[2])
            if number is not None and self._may_be_fact(number, str(node.args[1].value)):
                self._report("call_value", f"getattr({node.args[1].value}, {number})", node)
        if name == "Field":
            self._visit_field_default(node)
        if name in PATTERN_CALLS or name in {"Decimal", "timedelta", *DATE_CALLS}:
            return
        self._visit_positional_numbers(node, name)
        keywords = {keyword.arg: constant_number(keyword.value) for keyword in node.keywords}
        if (keywords.get("minimum"), keywords.get("maximum")) in CALENDAR_RANGES:
            return
        for keyword, number in keywords.items():
            if number is not None and self._may_be_fact(number, keyword or ""):
                self._report("keyword_value", f"{keyword}={number}", node)

    def _visit_clamp(self, node: ast.Call) -> None:
        for argument in node.args:
            number = constant_number(argument)
            spoken_of_tax = tax_name(self._annotated_context(node).replace(" ", "_"))
            if (
                number is not None
                and number not in ARITHMETIC_OPERANDS
                and (spoken_of_tax or not machine_capacity(number))
            ):
                self._report("clamp", number, node)

    def _visit_year_arithmetic(self, node: ast.Call, name: str) -> None:
        for argument in node.args:
            number = constant_number(argument)
            if number is not None and FIRST_YEAR < number < LAST_YEAR:
                self._report("year_range", number, node)
            elif (
                number is not None
                and number >= SMALL_COUNT
                and number != MONTHS_OF_A_YEAR + 1
                and number not in ARITHMETIC_OPERANDS
                and not machine_capacity(number)
            ):
                self._report("call_value", f"{name}({number})", node)

    def _visit_positional_numbers(self, node: ast.Call, name: str) -> None:
        for argument in node.args:
            number = constant_number(argument)
            if (
                number is not None
                and name not in {"min", "max", *YEAR_ARITHMETIC_CALLS, *POSITIONAL_MECHANICS}
                and self._may_be_fact(number, "")
            ):
                self._report("call_value", f"{name}({number})", node)

    def _visit_field_default(self, node: ast.Call) -> None:
        """A field's default is judged under the field's own name, not under the word ``default``."""
        defaults = {keyword.arg: keyword.value for keyword in node.keywords}
        number = constant_number(defaults.get("default", node.args[0] if node.args else None))
        field, _annotation = self._constraint_declaration(node)
        if number is not None and self._may_be_fact(number, field):
            self._report("field_default", f"{field}={number}", node)

    def _may_be_fact(self, number: float, name: str) -> bool:
        """Return whether a bare number under ``name`` can be a tax value rather than a position or unit."""
        if tax_name(name):
            return number not in IDENTITY_NUMBERS
        if name in VALUE_KEYWORDS:
            return not (isinstance(number, int) and number < SMALL_COUNT) and not machine_capacity(number)
        if self._owner.startswith("core/config") and name.startswith("cadrumo_"):
            return False
        if number in ARITHMETIC_OPERANDS or name in KEYWORD_MECHANICS:
            return False
        if machine_capacity(number):
            return False
        if self._owner.startswith(SHEET_GEOMETRY_OWNERS) and name_words(name) & SHEET_GEOMETRY_WORDS:
            return False
        if machine_unit_name(name) or mechanic_name(name):
            return False
        if FILE_PERMISSION_NAME.search(name) and number in FILE_PERMISSIONS:
            return False
        if self._names_its_calendar_unit(name, number):
            return False
        return not isinstance(number, int) or number >= SMALL_COUNT or bool(name_words(name) & FACT_WORDS)

    @override
    def visit_BinOp(self, node: ast.BinOp) -> None:
        if self._holds_facts() and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)):
            scale = self._percent_scale(node)
            if scale is not None:
                self._report("percent", scale, node)
            elif folded_number(node) is None:
                for side, other in ((node.left, node.right), (node.right, node.left)):
                    number = constant_number(side)
                    if number is not None and not self._mechanical_operand(number, node.op, other, node):
                        self._report("arithmetic", number, node)
        self.generic_visit(node)

    @override
    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        number = constant_number(node.value)
        if (
            self._holds_facts()
            and number is not None
            and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod))
            and not self._mechanical_operand(number, node.op, node.target, node)
        ):
            self._report("arithmetic", number, node)
        self.generic_visit(node)

    @override
    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        for value in node.values:
            self._visit_bare_result(value, node)
        self.generic_visit(node)

    @override
    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._visit_inner_binding(node.target, node.value, node)
        self.generic_visit(node)

    @override
    def visit_Yield(self, node: ast.Yield) -> None:
        self._visit_bare_result(node.value, node)
        self.generic_visit(node)

    @override
    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_defaults(node)
        self._visit_bare_result(node.body, node)
        self.generic_visit(node)

    @override
    def visit_FormattedValue(self, node: ast.FormattedValue) -> None:
        self._visit_bare_result(node.value, node)
        self.generic_visit(node)

    def _mechanical_operand(self, number: float, op: ast.operator, other: ast.AST, node: ast.AST) -> bool:
        if number in ARITHMETIC_OPERANDS or machine_capacity(number):
            return True
        if number in UNIT_CONVERSIONS and isinstance(op, (ast.Mult, ast.Div, ast.FloorDiv)):
            return True
        if isinstance(other, ast.Call) and called_name(other) in CLOCK_CALLS:
            return True
        if number in CALENDAR_VALUES and name_words(expression_names(node).replace(" ", "_")) & CALENDAR_UNITS.get(
            number, frozenset()
        ):
            return True
        return isinstance(number, int) and number < SMALL_COUNT

    @staticmethod
    def _percent_scale(node: ast.BinOp) -> float | None:
        """A rate written with the per cent scale, whatever its size and whichever order it is written in.

        ``amount * 19 / 100``, ``amount / 100 * 19``, ``amount * (19 / 100)``, ``amount * 19 // 100``.
        """
        if isinstance(node.op, ast.Mult):
            for side, other in ((node.left, node.right), (node.right, node.left)):
                number = constant_number(other)
                if (
                    number is not None
                    and number not in ARITHMETIC_BOUNDS
                    and isinstance(side, ast.BinOp)
                    and isinstance(side.op, (ast.Div, ast.FloorDiv))
                    and is_hundred(side.right)
                ):
                    return number
            return None
        if not isinstance(node.op, (ast.Div, ast.FloorDiv)) or not is_hundred(node.right):
            return None
        direct = constant_number(node.left)
        if direct is not None and direct not in ARITHMETIC_BOUNDS and direct != ARITHMETIC_PERCENT:
            return direct
        product = node.left
        if not isinstance(product, ast.BinOp) or not isinstance(product.op, ast.Mult):
            return None
        for side in (product.left, product.right):
            number = constant_number(side)
            if number is not None and number not in ARITHMETIC_BOUNDS:
                return number
        return None

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_defaults(node)
        self.generic_visit(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_defaults(node)
        self.generic_visit(node)

    @override
    def visit_Return(self, node: ast.Return) -> None:
        self._visit_bare_result(node.value, node)
        self.generic_visit(node)

    @override
    def visit_IfExp(self, node: ast.IfExp) -> None:
        if not (isinstance(node.test, ast.Call) and called_name(node.test) == "isleap"):
            for branch in (node.body, node.orelse):
                self._visit_bare_result(branch, node)
        self.generic_visit(node)

    def _visit_bare_result(self, value: ast.AST | None, node: ast.AST) -> None:
        number = constant_number(value)
        if number is not None and self._holds_facts() and self._may_be_fact(number, self._annotated_context(node)):
            self._report("result_value", number, node)

    def _visit_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> None:
        arguments = [*node.args.posonlyargs, *node.args.args]
        positional = zip(reversed(arguments), reversed(node.args.defaults), strict=False)
        keyword_only = zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
        for argument, default in (*positional, *keyword_only):
            number = constant_number(default)
            if number is not None and self._reads_name(argument.arg) and self._may_be_fact(number, argument.arg):
                self._report("default_value", f"{argument.arg}={number}", node)

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1:
            self._visit_inner_binding(node.targets[0], node.value, node)
        self.generic_visit(node)

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._visit_inner_binding(node.target, node.value, node)
        self.generic_visit(node)

    def _visit_inner_binding(self, target: ast.AST, value: ast.AST, node: ast.AST) -> None:
        """A class attribute or a local holds a number as a module constant does."""
        if isinstance(self._parents.get(node), ast.Module):
            return
        number = folded_number(value)
        name = reader_name(target)
        if number is not None and name and self._reads_name(name) and self._may_be_fact(number, name):
            self._report("inner_value", f"{name}={number}", node)

    def _visit_form_width_call(self, node: ast.Call, name: str, keywords: dict[str | None, ast.expr]) -> None:
        plurality = self._plurality_bound(
            node, constant_number(keywords.get("min_length")), constant_number(keywords.get("max_length"))
        )
        for bound in () if plurality else LENGTH_BOUNDS:
            number = constant_number(keywords.get(bound))
            if number is not None and number not in ARITHMETIC_BOUNDS and not machine_capacity(number):
                self._report("form_width", f"{bound}={number}", node)
        if name not in PATTERN_CALLS and self._inside_annotated(node):
            for argument in node.args:
                number = constant_number(argument)
                if number is not None and number not in ARITHMETIC_BOUNDS and not machine_capacity(number):
                    self._report("form_width", f"{name}({number})", node)

    def _visit_text_width(self, node: ast.Call, name: str) -> None:
        for argument in node.args[:1]:
            number = constant_number(argument)
            if number is not None and number not in ARITHMETIC_BOUNDS and not machine_capacity(number):
                self._report("form_width", f"{name}({number})", node)

    def _inside_annotated(self, node: ast.AST) -> bool:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.Subscript) and reader_name(current.value) == "Annotated":
                return True
        return False

    def _visit_form_width_pattern(self, pattern: str, node: ast.AST) -> None:
        declared, _annotation = self._constraint_declaration(node)
        if MODELO_ID_DECLARATION.search(declared):
            return
        for group, low, high in WIDTH_QUANTIFIER.findall(pattern):
            if group in HEX_CLASSES or group == ")":
                continue
            if low == YEAR_WIDTH and not high and YEAR_NAME.search(declared):
                continue
            self._report("form_width", f"{group}{{{low},{high}}}", node)

    def _visit_constraints(self, node: ast.Call, keywords: dict[str | None, ast.expr]) -> None:
        pattern = keywords.get("pattern")
        text = pattern.value if isinstance(pattern, ast.Constant) and isinstance(pattern.value, str) else None
        if pattern is not None:
            self._visit_regex(pattern, node)
        low = constant_number(keywords.get("ge", keywords.get("gt")))
        high = constant_number(keywords.get("le", keywords.get("lt")))
        declared, _ = self._constraint_declaration(node)
        if not lawful_range(low, high, declared.replace(" ", "_")) and not self._technical_bound(node, low, high):
            self._report("field_bound", (low, high), node)
        lengths = {arg: constant_number(keywords.get(arg)) for arg in LENGTH_BOUNDS}
        _field, annotation = self._constraint_declaration(node)
        lexical = (
            called_name(node) == "StringConstraints" or annotation_kind(annotation, self._tree, self._module) == "text"
        )
        if (
            not lexical
            and not self._plurality_bound(node, lengths["min_length"], lengths["max_length"])
            and not lawful_length(lengths["min_length"], lengths["max_length"], text)
        ):
            self._report("field_length", (lengths["min_length"], lengths["max_length"]), node)

    def _visit_regex(self, pattern: ast.AST, node: ast.AST) -> None:
        if not isinstance(pattern, ast.Constant) or not isinstance(pattern.value, str):
            return
        if self._form_handing:
            self._visit_form_width_pattern(pattern.value, node)
        repeated_groups = [width for width in WIDTH_QUANTIFIER.findall(pattern.value) if width[0] == ")"]
        uuid_shape = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}" in pattern.value.lower()
        if repeated_groups and not uuid_shape:
            self._report("regex_width", pattern.value, node)
        for group in re.findall(r"\((?:\?:)?([0-9A-Z]+(?:\|[0-9A-Z]+)+)\)", pattern.value):
            alternatives = tuple(group.split("|"))
            if set(alternatives).issubset(self._modelos):
                self._report("modelo_set", ",".join(sorted(alternatives)), node)
        if re.search(r"(?<![0-9\\])(?:19|20)[0-9]{2}[-/]", pattern.value):
            self._report("regex_year", pattern.value, node)
        members = fixed_pattern_members(pattern.value)
        if members == (self._own_form,):
            return
        if len(members) > 1 and set(members).issubset(self._modelos):
            self._report("modelo_set", ",".join(sorted(members)), node)
        elif members and any(CODE_SHAPED.fullmatch(member) for member in members):
            self._report("regex_values", members, node)
        else:
            field, _annotation = self._constraint_declaration(node)
            if members and CLAVE_NAME.search(field) and not COUNTRY_NAME.search(field):
                self._report("letter_clave", members, node)

    def _visit_date(self, node: ast.Call, keywords: dict[str | None, ast.expr]) -> None:
        parts: list[ast.expr | None] = [*node.args[:3]]
        parts += [keywords.get(part) for part in ("year", "month", "day")[len(parts) :]]
        year, month, day = (constant_number(argument) for argument in parts)
        if year is not None:
            if (year, month, day) not in EPOCHS:
                self._report("date_literal", (year, month, day), node)
        elif month is not None and day is not None and (month, day) not in YEAR_ENDPOINTS:
            self._report("date_literal", (month, day), node)

    @override
    def visit_Compare(self, node: ast.Compare) -> None:
        length_calls = [
            side for side in (node.left, *node.comparators) if isinstance(side, ast.Call) and called_name(side) == "len"
        ]
        is_len = bool(length_calls)
        structural_len = is_len and all(self._structural_length(call, node) for call in length_calls)
        reads_code_point = any(
            isinstance(side, ast.Call) and called_name(side) == "ord" for side in (node.left, *node.comparators)
        )
        spoken_of_tax = tax_name(expression_names(node).replace(" ", "_"))
        for side in (node.left, *node.comparators):
            if self._modelo_literal(side) or (isinstance(side, ast.Name) and side.id in self._modelo_names):
                self._report("modelo_compare", ast.unparse(node), node)
            number = constant_number(side)
            if number is None or reads_code_point:
                continue
            if self._four_digit_year_shape(node):
                continue
            if FIRST_YEAR < number < LAST_YEAR and not is_len:
                self._report("year_branch", number, node)
            elif self._is_threshold(number, node, is_len=is_len, structural_len=structural_len, spoken=spoken_of_tax):
                self._report("len_compare" if is_len else "threshold", number, node)
        self._visit_compared_members(node)
        if self._form_handing and is_len and not self._standard_shape(node):
            self._visit_form_width_comparison(node, length_calls)
        if is_len and not self._machine and not structural_len:
            for side in node.comparators:
                if isinstance(side, (ast.Set, ast.Tuple, ast.List)):
                    self._report("len_in", ast.unparse(side), node)
        self.generic_visit(node)

    def _is_threshold(
        self, number: float, node: ast.Compare, *, is_len: bool, structural_len: bool, spoken: bool
    ) -> bool:
        return (
            number not in ARITHMETIC_COMPARE
            and (spoken or not machine_capacity(number))
            and not self._machine
            and not structural_len
            and (spoken or number != SHA256_HEX)
            and (is_len or spoken or not self._compares_its_calendar_unit(number, node))
            and not (is_len and self._standard_shape(node))
        )

    def _standard_shape(self, node: ast.Compare) -> bool:
        """A function named for a standard shape may compare a length with that shape's one width."""
        function = self._enclosing_function(node)
        if not STANDARD_SHAPE_FUNCTION.search(function) or name_words(function.replace(".", "_")) & FORM_SHAPE_WORDS:
            return False
        lowered = function.lower()
        widths = {width for shape, width in STANDARD_SHAPE_WIDTHS.items() if shape in lowered}
        numbers = {constant_number(side) for side in (node.left, *node.comparators)} - {None}
        return numbers <= widths

    @staticmethod
    def _four_digit_year_shape(node: ast.Compare) -> bool:
        """``1000 <= year <= 9999`` says a value has four digits; it selects no year."""
        numbers = [constant_number(side) for side in (node.left, *node.comparators)]
        return numbers[0] == THOUSAND and numbers[-1] == FOUR_DIGIT_YEAR_LAST

    def _visit_compared_members(self, node: ast.Compare) -> None:
        """A year tested against a set of years, or anything tested against one code letter, routes on a fact."""
        for side in (node.left, *node.comparators):
            if isinstance(side, (ast.Tuple, ast.List, ast.Set)):
                for member in side.elts:
                    number = constant_number(member)
                    if number is not None and FIRST_YEAR < number < LAST_YEAR:
                        self._report("year_branch", number, node)
                    if self._modelo_literal(member):
                        self._report("modelo_compare", ast.unparse(node), node)
                    if isinstance(member, ast.Constant) and self._letter_may_be_code(member.value, node):
                        self._report("letter_compare", member.value, node)
            elif isinstance(side, ast.Constant) and (
                self._letter_may_be_code(side.value, node) or self._letters_may_be_codes(side.value, node)
            ):
                self._report("letter_compare", side.value, node)

    def _letters_may_be_codes(self, value: object, node: ast.Compare) -> bool:
        """``kind in 'AE'`` lists code letters in one string; country codes under their own name are not those."""
        return (
            isinstance(value, str)
            and CODE_LETTERS.fullmatch(value) is not None
            and self._holds_facts()
            and any(isinstance(operator, (ast.In, ast.NotIn)) for operator in node.ops)
            and not COUNTRY_NAME.search(expression_names(node))
        )

    def _reads_a_design_letter(self, value: object) -> bool:
        return value in RECORD_DESIGN_LETTERS and self._owner.startswith(RECORD_DESIGN_OWNERS)

    def _letter_may_be_code(self, value: object, node: ast.Compare) -> bool:
        if not single_code_letter(value) or not self._holds_facts():
            return False
        if value == CHECKBOX_MARK or self._reads_a_design_letter(value):
            return False
        return not all(isinstance(operator, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for operator in node.ops)

    def _compares_its_calendar_unit(self, number: float, node: ast.Compare) -> bool:
        if number not in CALENDAR_VALUES:
            return False
        units = CALENDAR_UNITS.get(number)
        if units is None or not self._holds_facts():
            return True
        names = f"{expression_names(node)} {self._enclosing_function(node)}".replace(" ", "_").replace(".", "_")
        return bool(name_words(names) & units)

    def _visit_form_width_comparison(self, node: ast.Compare, length_calls: list[ast.Call]) -> None:
        """A text's length compared with a number restates a width; a split's part count is grammar."""
        if any(call.args and self._expression_kind(call.args[0]) == "grammar_sequence" for call in length_calls):
            return
        for side in (node.left, *node.comparators):
            number = constant_number(side)
            if number is not None and number not in ARITHMETIC_BOUNDS and not machine_capacity(number):
                self._report("form_width", f"len=={number}", node)

    def _modelo_literal(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Call):
            node = node.value
        if isinstance(node, ast.Call) and called_name(node) == "Modelo":
            return True
        return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in self._modelos

    @override
    def visit_Match(self, node: ast.Match) -> None:
        for case in node.cases:
            for pattern in ast.walk(case.pattern):
                if isinstance(pattern, ast.MatchValue) and isinstance(pattern.value, ast.Constant):
                    value = pattern.value.value
                    if (
                        isinstance(value, (int, float))
                        or (isinstance(value, str) and CODE_SHAPED.match(value))
                        or (single_code_letter(value) and self._holds_facts())
                    ):
                        self._report("match_case", value, pattern)
        self.generic_visit(node)

    @override
    def visit_Dict(self, node: ast.Dict) -> None:
        for key in node.keys:
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and CODE_SHAPED.match(key.value)
                and not self._month_keyed(key)
            ):
                self._report("dict_key", key.value, key)
            if isinstance(key, ast.Constant) and single_code_letter(key.value) and self._holds_facts():
                self._report("letter_key", key.value, key)
            key_number = constant_number(key)
            if key is not None and key_number is not None and self._holds_facts() and self._may_be_fact(key_number, ""):
                self._report("dict_key", key_number, key)
        for key, value in zip(node.keys, node.values, strict=True):
            number = constant_number(value)
            if (
                number is not None
                and isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and self._reads_name(key.value)
                and self._may_be_fact(number, key.value)
            ):
                self._report("dict_value", f"{key.value}={number}", value)
            self.visit(value)

    @override
    def visit_Subscript(self, node: ast.Subscript) -> None:
        target = node.value
        if (target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")) == "Literal":
            spelled = {member.value for member in ast.walk(node.slice) if isinstance(member, ast.Constant)}
            for member in ast.walk(node.slice):
                if (
                    isinstance(member, ast.Constant)
                    and isinstance(member.value, str)
                    and CODE_SHAPED.match(member.value)
                ) or (
                    isinstance(member, ast.Constant)
                    and single_code_letter(member.value)
                    and self._holds_facts()
                    and not self._reads_a_design_letter(member.value)
                    and spelled != YES_NO_LETTERS
                ):
                    self._report("literal_type", member.value, member)
                number = constant_number(member)
                if (
                    number is not None
                    and number not in IDENTITY_NUMBERS
                    and self._holds_facts()
                    and not self._literal_names_a_unit(node)
                ):
                    self._report("literal_type", number, member)
            return
        if self._form_handing and isinstance(node.slice, ast.Slice):
            for bound in (node.slice.lower, node.slice.upper):
                number = constant_number(bound)
                if number is not None and number not in ARITHMETIC_COMPARE and not machine_capacity(number):
                    self._report("form_width", f"slice({number})", node)
        self._visit_position(node)
        self.generic_visit(node)

    def _visit_position(self, node: ast.Subscript) -> None:
        """A position past the small counts can only be a count of rows some form holds."""
        if not self._holds_facts():
            return
        for bound in (node.slice.lower, node.slice.upper) if isinstance(node.slice, ast.Slice) else (node.slice,):
            number = constant_number(bound)
            if number is not None and number >= SMALL_COUNT and not machine_capacity(number):
                self._report("position", number, node)

    def _literal_names_a_unit(self, node: ast.AST) -> bool:
        field, _annotation = self._constraint_declaration(node)
        return machine_unit_name(field.replace(" ", "_"))

    def _visit_collection(self, node: ast.Set | ast.Tuple | ast.List) -> None:
        months = [constant_number(element) for element in node.elts]
        if (
            len(months) >= MONTH_TUPLE_LENGTH
            and all(month is not None and 1 <= month <= MONTHS_OF_A_YEAR for month in months)
            and (isinstance(node, ast.Set) or months == sorted({month for month in months if month is not None}))
        ):
            self._report("month_tuple", tuple(months), node)
        if self._holds_facts() and len(node.elts) >= MONTH_TUPLE_LENGTH - 1:
            for month in months:
                if month is not None and self._may_be_fact(month, self._annotated_context(node).replace(" ", "_")):
                    self._report("number_set", month, node)
        ids: list[str] = []
        for element in node.elts:
            literal = element
            if isinstance(element, ast.Attribute) and isinstance(element.value, ast.Call):
                literal = element.value
            if isinstance(literal, ast.Call) and called_name(literal) == "Modelo" and literal.args:
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
        if isinstance(parent, ast.Call) and called_name(parent) == "Decimal":
            return
        if ISO_DATE.match(value) or any(pattern.match(value) for pattern in DATE_TEXTS):
            self._report("date_text", value, node)
        elif SPELLED_BOX.match(value) or CODE_LIST.match(value) or self._spells_another_form(value):
            self._report("code", value, node)
        elif (
            TEXT_NUMBER.match(value)
            and not CODE_SHAPED.match(value)
            and float(value.replace(",", ".")) not in IDENTITY_NUMBERS
            and self._holds_facts()
            and bool(name_words(self._annotated_context(node).replace(" ", "_")) & FACT_WORDS)
        ):
            self._report("number_text", value, node)
        elif CODE_SHAPED.match(value):
            if not self._code_is_admitted(node, value):
                self._report("code", value, node)
        elif (
            LETTER_CLAVE.match(value)
            and CLAVE_NAME.search(context := self._annotated_context(node))
            and not COUNTRY_NAME.search(context)
        ):
            self._report("letter_clave", value, node)

    def _code_is_admitted(self, node: ast.Constant, value: str) -> bool:
        """Return whether a code-shaped string stands where no tax fact can."""
        if value == self._own_form or self._month_keyed(node):
            return True
        if self._defines_period_code(node) or self._is_command_path_segment(node):
            return True
        if any(EDITION_TAIL.search(name) for name in self._own_side_names(node)) and not isinstance(
            self._parents.get(node), ast.Compare
        ):
            return True
        if value.isdigit() and int(value) <= MONTHS_OF_A_YEAR and MONTH_NAME.search(self._annotated_context(node)):
            return True
        if value.isdigit() and int(value) in DAYS_OF_A_YEAR and DAY_NAME.search(self._annotated_context(node)):
            return True
        if value in self._periods and self._stands_as_address(node, PERIOD_TAIL):
            return True
        return value in self._modelos and self._stands_as_address(node, MODELO_TAIL)


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
    form_named = FORM_NAMED_MODULE.search(module)
    sweep = _Sweep(
        tree,
        modelos,
        periods,
        form_named[1] if form_named else None,
        machine=machine,
        owner=owner,
        form_handing=(FORM_HANDING_MODULE.search(module) is not None or owner.startswith(FORM_HANDING_OWNERS))
        and not owner.startswith(RECORD_DESIGN_READERS),
    )
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
            machine=owner.startswith(MACHINE_OWNERS),
            owner=owner,
        )
        if findings:
            found[relative.as_posix()] = findings
    return found


def current() -> dict[str, list[str]]:
    modelos, periods = modelo_ids(), period_codes()
    found: dict[str, list[str]] = {}
    for top in SCANNED:
        for path, entries in sweep_tree(top, modelos=modelos, periods=periods).items():
            found[f"{top.name}/{path}"] = entries
    return found
