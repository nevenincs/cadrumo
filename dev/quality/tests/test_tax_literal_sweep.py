"""Refuse a tax value written into the domain and application code.

The operator's rule is that a tax number, limit, threshold, period or form code lives in
the registry. Calendar facts, arithmetic, technical limits and registry ids may stay in code.
This gate reads syntax and judges a literal by the position it stands in:

- a ``Decimal`` other than an arithmetic identity or a power-of-ten rounding quantum;
- a ``Field`` numeric bound, which can hide a closed set of claves;
- a ``Field`` length or a ``len()`` comparison, which can hide a form's row count or code shape;
- a code-shaped string that does not stand where a modelo or period address stands, so a
  modelo id cannot pass for a box id or the reverse;
- two or more modelo ids held together, which is a routing rule;
- a one or two letter string compared with, or stored under, a name that means a clave.

A literal leaves the findings only through a rule below, read from its own position: a
calendar bound, a technical limit, a standard's code, or a registry id. There is no record
of accepted literals, so a value the rules do not cover fails until it moves or a rule that
states why it may stay is added here. The modelo ids come from the registry tree and the
period codes from their enum, so neither is listed.
"""

from __future__ import annotations

import ast
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT: Final = Path(__file__).resolve().parents[3]
_SRC: Final = _ROOT / "src" / "cadrumo"
_SCANNED: Final = ("domain", "application")

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
_YEAR_NAME: Final = re.compile(r"year|ejercicio", re.IGNORECASE)
_MONTH_NAME: Final = re.compile(r"month", re.IGNORECASE)
_DAY_NAME: Final = re.compile(r"days?(?:_|$)|dias", re.IGNORECASE)
_QUARTER_NAME: Final = re.compile(r"quarter", re.IGNORECASE)
_TECHNICAL_BOUND_NAME: Final = re.compile(
    r"http_status|seconds|pixels|width|height|rounding_scale|_count$|generation$|(?:^|_)row$|(?:inventory|replay)_?limit",
    re.IGNORECASE,
)
_NON_TAX_DECIMAL_NAME: Final = re.compile(r"confidence|score|hours_per_day", re.IGNORECASE)
_COUNTRY_NAME: Final = re.compile(r"country|iso", re.IGNORECASE)
_LENGTH_BOUNDS: Final = frozenset({"min_length", "max_length"})
_PAYLOAD_GUARD: Final = 16
_ORDERED_PAYLOAD_GUARD: Final = 64
_SHA256_HEX: Final = 64
_STANDARD_SHAPE_NAME: Final = re.compile(
    r"(?:^|_)(?:hash|digest|sha256|nonce|ciphertext|id|country|pais|iso|currency|nif|tax_id|year|ejercicio|period|"
    r"modelo|path|state|periodo|years|update_fields|classify_fields|emisor|selector|separator|ref|locale|language|date|on|attachment|generation|public_key|member_?state|"
    r"isin|intents|normalisations|fields?|filters|parties|reversed|coordinates|components)(?:_|$|\b)",
    re.IGNORECASE,
)
_STRUCTURE_LEN_NAME: Final = re.compile(
    r"args$|parts?$|parts\[|segments|split|groups?$|groups\[|fraction$|tokens?$|head$|pieces|pair|anchors|spans|children|candidates|"
    r"keys$|ids$|boundaries|endpoints|arguments|suffix|outcomes|years$|actions|agenda|digits|"
    r"grant|dek|operator_id|work_unit|_id$|stripped|\\bcase_id",
    re.IGNORECASE,
)
_STANDARD_SHAPE_FUNCTION: Final = re.compile(
    r"(?:^|_)(?:date|year|month|day|calendar|country|currency|iso|member|ccaa|alpha|amount|number|decimal|modelo_id)(?:_|s?$)",
    re.IGNORECASE,
)
_ORDERING_OPERATORS: Final = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_DAYS_OF_A_YEAR: Final = frozenset({365, 366})
_MONTHS_OF_A_YEAR: Final = 12
_QUARTERS_OF_A_YEAR: Final = 4
_ADDRESS_KEYWORDS: Final = frozenset({"modelo", "period", "modelo_id", "source_modelo", "registry_token"})


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


def _all_nines(value: object) -> bool:
    """A bound of nines states a field width, whatever the field holds."""
    return set(str(value).replace(".", "")) == {"9"}


def _lawful_bound(owner: str, value: float) -> bool:
    """Return whether a numeric bound on ``owner`` is a calendar range or a technical limit."""
    if _all_nines(value) or _TECHNICAL_BOUND_NAME.search(owner):
        return True
    if _YEAR_NAME.search(owner):
        return value % 100 in {0, 1, 99}
    if _DAY_NAME.search(owner):
        return value in _DAYS_OF_A_YEAR
    if _MONTH_NAME.search(owner):
        return value <= _MONTHS_OF_A_YEAR
    return bool(_QUARTER_NAME.search(owner)) and value <= _QUARTERS_OF_A_YEAR


def _lawful_length(owner: str, value: int, other: int | None) -> bool:
    """Return whether a ``Field`` length states a structure, a size guard or a standard's shape."""
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", owner)
    if value in _ARITHMETIC_BOUNDS or _STANDARD_SHAPE_NAME.search(words):
        return True
    exact = other == value
    if exact:
        return False
    return value >= _PAYLOAD_GUARD or (other is not None and other >= _PAYLOAD_GUARD) or (other is None and value == 2)


def _lawful_len_comparison(subject: str, operator: ast.cmpop, value: int) -> bool:
    """Return whether ``len(subject)`` against ``value`` states arithmetic, structure or a size guard."""
    if value in _ARITHMETIC_BOUNDS or value == _SHA256_HEX or _STRUCTURE_LEN_NAME.search(subject):
        return True
    if isinstance(operator, _ORDERING_OPERATORS):
        return value == 2 or value >= _ORDERED_PAYLOAD_GUARD
    return False


def _lawful_decimal(text: str) -> bool:
    try:
        value = Decimal(text)
    except InvalidOperation:
        return True
    if value in {Decimal(0), Decimal(1), Decimal(100), Decimal(-1)} or _all_nines(text):
        return True
    return value.is_finite() and value > 0 and value.as_tuple().digits[0] == 1 and sum(value.as_tuple().digits) == 1


class _Sweep(ast.NodeVisitor):
    def __init__(self, tree: ast.AST, modelos: frozenset[str], periods: frozenset[str], own_form: str | None) -> None:
        self._own_form = own_form
        self._parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        self._docstrings = _docstrings(tree)
        self._modelos = modelos
        self._periods = periods
        self.findings: list[str] = []

    def _report(self, kind: str, value: object, node: ast.AST) -> None:
        self.findings.append(f"{kind}:{value!r}@{getattr(node, 'lineno', 0)}")

    def _owner(self, node: ast.AST) -> str:
        """Return the name the statement around ``node`` declares, whatever annotation holds it."""
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.AnnAssign):
                return _expression_names(current.target)
            if isinstance(current, ast.Assign):
                return " ".join(_expression_names(target) for target in current.targets)
            if isinstance(current, ast.AugAssign):
                return _expression_names(current.target)
            if isinstance(current, ast.TypeAlias):
                return _expression_names(current.name)
            if isinstance(current, ast.stmt):
                return ""
        return ""

    def _annotation_of(self, node: ast.AST) -> str:
        """Return the annotated type around a ``Field``: a row per month states the calendar."""
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.AnnAssign):
                return ast.unparse(current.annotation)
            if isinstance(current, ast.stmt):
                return ""
        return ""

    def _enclosing_function(self, node: ast.AST) -> str:
        current = node
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current.name
        return ""

    def _month_keyed(self, node: ast.Constant) -> bool:
        """A month number keying a text that names that same month is a calendar table."""
        parent = self._parents.get(node)
        if not isinstance(parent, ast.Dict) or node not in parent.keys:
            return False
        value = parent.values[parent.keys.index(node)]
        return isinstance(value, ast.Constant) and f"month_{node.value}" in str(value.value)

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
        if name == "Decimal" and len(node.args) == 1:
            argument = node.args[0]
            if (
                isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
                and not _lawful_decimal(argument.value)
                and not _NON_TAX_DECIMAL_NAME.search(self._owner(node))
            ):
                self._report("decimal", argument.value, node)
        if name == "Field":
            for keyword in node.keywords:
                if (
                    keyword.arg in _NUMERIC_BOUNDS
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, (int, float))
                    and not isinstance(keyword.value.value, bool)
                    and keyword.value.value not in _ARITHMETIC_BOUNDS
                    and not _lawful_bound(self._owner(node), keyword.value.value)
                ):
                    self._report(f"field_{keyword.arg}", keyword.value.value, keyword.value)
            lengths = {
                keyword.arg: keyword.value.value
                for keyword in node.keywords
                if keyword.arg in _LENGTH_BOUNDS
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, int)
            }
            for bound, value in lengths.items():
                other = lengths.get("max_length" if bound == "min_length" else "min_length")
                if value == _MONTHS_OF_A_YEAR and "Monthly" in self._annotation_of(node):
                    continue
                if not _lawful_length(self._owner(node), value, other):
                    self._report(f"field_{bound}", value, node)
        self.generic_visit(node)

    @override
    def visit_Compare(self, node: ast.Compare) -> None:
        left = node.left
        if (
            len(node.comparators) == 1
            and isinstance(left, ast.Call)
            and _called_name(left) == "len"
            and left.args
            and isinstance(limit := node.comparators[0], ast.Constant)
            and isinstance(limit.value, int)
            and not _lawful_len_comparison(ast.unparse(left.args[0]), node.ops[0], limit.value)
            and not _STANDARD_SHAPE_FUNCTION.search(self._enclosing_function(node))
        ):
            self._report("len_compare", limit.value, node)
        self.generic_visit(node)

    def _visit_collection(self, node: ast.Set | ast.Tuple | ast.List) -> None:
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
            if _EDITION_NAME.search(self._annotated_context(node)):
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


def sweep_source(source: str, *, modelos: frozenset[str], periods: frozenset[str], module: str = "") -> list[str]:
    """Return one ``kind:value@line`` entry per literal of ``source`` standing where a tax fact could.

    ``module`` names the file: a module named for one form may name that form.
    """
    tree = ast.parse(source)
    form_named = _FORM_NAMED_MODULE.search(module)
    sweep = _Sweep(tree, modelos, periods, form_named[1] if form_named else None)
    sweep.visit(tree)
    return sweep.findings


def sweep_tree(root: Path, *, modelos: frozenset[str], periods: frozenset[str]) -> dict[str, list[str]]:
    """Return the findings of every production module below ``root``, by relative path."""
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if "tests" in relative.parts:
            continue
        findings = sweep_source(path.read_text(encoding="utf-8"), modelos=modelos, periods=periods, module=path.stem)
        if findings:
            found[relative.as_posix()] = findings
    return found


def _current() -> dict[str, list[str]]:
    modelos, periods = _modelo_ids(), _period_codes()
    found: dict[str, list[str]] = {}
    for top in _SCANNED:
        for path, entries in sweep_tree(_SRC / top, modelos=modelos, periods=periods).items():
            found[f"{top}/{path}"] = entries
    return found


_FAKE_MODELOS: Final = frozenset({"303", "111", "100"})
_FAKE_PERIODS: Final = frozenset({"0A", "1T", "01"})


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("cap = Decimal('300.51')\n", "decimal"),
        ("clave: int = Field(ge=1, le=7)\n", "field_le"),
        ("rows: tuple[int, ...] = Field(min_length=18, max_length=18)\n", "field_min_length"),
        ("rows: tuple[int, ...] = Field(max_length=12)\n", "field_max_length"),
        ("ok = len(row) == 3\n", "len_compare"),
        ("BOX = '0208'\n", "code"),
        ("box = '303'\n", "code"),
        ("ROUTED = frozenset({Modelo('111').value, Modelo('303').value})\n", "modelo_set"),
        ("ok = modelo in {'111', '303'}\n", "modelo_set"),
        ("if clave == 'A':\n    pass\n", "letter_clave"),
        ("subclave = 'B'\n", "letter_clave"),
        ("tipo_renta_code: str = 'XY'\n", "letter_clave"),
        ("first_year: int = Field(ge=2012)\n", "field_ge"),
        ("month: int = Field(le=13)\n", "field_le"),
        ("minimum_days: int = Field(le=180)\n", "field_le"),
        ("slot: int = Field(ge=1, le=5)\n", "field_le"),
        ("deduction_limit: int = Field(le=300)\n", "field_le"),
    ],
)
def test_the_sweep_rejects_a_representative_tax_literal(line: str, kind: str) -> None:
    findings = sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS)
    assert any(finding.startswith(f"{kind}:") for finding in findings), findings


@pytest.mark.parametrize(
    "line",
    [
        "x = Decimal('0.01')\n",
        "rate = value / Decimal('100')\n",
        "name: str = Field(max_length=128)\n",
        "count: int = Field(ge=0)\n",
        "directory = operation.modelo_directory('303')\n",
        "selected = Modelo('303')\n",
        "if context.modelo == Modelo('100').value:\n    pass\n",
        "work = load(modelo='303', period='1T')\n",
        '"""A docstring may cite casilla 0208 and clave A."""\n',
        "label = 'A'\n",
        "end = date(year, 12, 31)\n",
        "year: int = Field(ge=1900, le=9999)\n",
        "type Year = Annotated[int, Field(ge=2000, le=2099)]\n",
        "month: Annotated[int, Field(ge=1, le=12)]\n",
        "calendar_days: int = Field(ge=365, le=366)\n",
        "quarters_filed: int = Field(ge=1, le=4)\n",
        "http_status: int = Field(ge=100, le=599)\n",
        "lifetime_seconds: float = Field(gt=0, le=1800)\n",
        "numero_orden: int = Field(ge=1, le=9999999)\n",
        "MAXIMUM = Decimal('999999999999.99')\n",
        "_LOW_CONFIDENCE = Decimal('0.5')\n",
        "_SPAIN_COUNTRY_CODE = 'ES'\n",
        "NAMES = {'01': 'finding.month_01'}\n",
        "if revision_id == '2022':\n    pass\n",
    ],
)
def test_the_sweep_admits_what_stands_where_no_tax_fact_can(line: str) -> None:
    assert sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


def test_a_module_named_for_one_form_may_name_that_form_and_no_other() -> None:
    line = "box = '303'\nother = '111'\n"
    findings = sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS, module="m303_arrivals")
    assert findings == ["code:'111'@2"]


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


def test_the_domain_and_application_code_holds_no_tax_literal() -> None:
    found = _current()
    assert not found, f"a tax value belongs to the registry: {found}"
