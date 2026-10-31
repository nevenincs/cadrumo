"""Hold tax values written into the domain and application code to a shrinking recorded set.

The operator's rule is that a tax number, limit, threshold, period or form code lives in
the registry. Calendar facts, arithmetic, technical limits and registry ids may stay in code.
This gate reads syntax and judges a literal by the position it stands in:

- a ``Decimal`` other than an arithmetic identity or a power-of-ten rounding quantum;
- a ``Field`` numeric bound, which can hide a closed set of claves;
- a code-shaped string that does not stand where a modelo or period address stands, so a
  modelo id cannot pass for a box id or the reverse;
- two or more modelo ids held together, which is a routing rule;
- a one or two letter string compared with, or stored under, a name that means a clave.

The modelo ids come from the registry tree and the period codes from their enum, so neither
is listed here. Literals already present are recorded in
``dev/quality/metadata/tax_literal_sweep_baseline.json``, written only by running this file
with ``--write``: a new finding fails, and so does an entry the code no longer has, so the
record can only shrink. A recorded entry is an open finding, not an accepted exception.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT: Final = Path(__file__).resolve().parents[3]
_SRC: Final = _ROOT / "src" / "cadrumo"
_SCANNED: Final = ("domain", "application")
_BASELINE: Final = _ROOT / "dev" / "quality" / "metadata" / "tax_literal_sweep_baseline.json"

_NUMERIC_BOUNDS: Final = frozenset({"ge", "gt", "le", "lt"})
_ARITHMETIC_BOUNDS: Final = frozenset({0, 1})
_CODE_SHAPED: Final = re.compile(r"^\d{2,4}[A-Z]?$")
_LETTER_CLAVE: Final = re.compile(r"^[A-Z]{1,2}$")
_CLAVE_NAME: Final = re.compile(r"clave|subclave|tipo_|_code$|^code$|codigo", re.IGNORECASE)
_MODELO_NAME: Final = re.compile(r"modelo|model\b", re.IGNORECASE)
_PERIOD_NAME: Final = re.compile(r"period|token|quarter", re.IGNORECASE)
_MODELO_ADDRESS_CALLS: Final = frozenset(
    {"Modelo", "modelo_directory", "revision", "revision_for_context", "select_revision_metadata"},
)
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


def _lawful_decimal(text: str) -> bool:
    try:
        value = Decimal(text)
    except InvalidOperation:
        return True
    if value in {Decimal(0), Decimal(1), Decimal(100), Decimal(-1)}:
        return True
    return value.is_finite() and value > 0 and value.as_tuple().digits[0] == 1 and sum(value.as_tuple().digits) == 1


class _Sweep(ast.NodeVisitor):
    def __init__(self, tree: ast.AST, modelos: frozenset[str], periods: frozenset[str]) -> None:
        self._parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        self._docstrings = _docstrings(tree)
        self._modelos = modelos
        self._periods = periods
        self.findings: list[str] = []

    def _report(self, kind: str, value: object) -> None:
        self.findings.append(f"{kind}:{value!r}")

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
            ):
                self._report("decimal", argument.value)
        if name == "Field":
            for keyword in node.keywords:
                if (
                    keyword.arg in _NUMERIC_BOUNDS
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, (int, float))
                    and not isinstance(keyword.value.value, bool)
                    and keyword.value.value not in _ARITHMETIC_BOUNDS
                ):
                    self._report(f"field_{keyword.arg}", keyword.value.value)
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
            self._report("modelo_set", ",".join(sorted(ids)))
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
            if value in self._periods and self._stands_as_address(node):
                return
            if value in self._modelos and self._stands_as_address(node):
                return
            if value not in self._modelos and value not in self._periods and self._stands_as_address(node):
                return
            self._report("code", value)
        elif _LETTER_CLAVE.match(value) and _CLAVE_NAME.search(self._annotated_context(node)):
            self._report("letter_clave", value)


def sweep_source(source: str, *, modelos: frozenset[str], periods: frozenset[str]) -> list[str]:
    """Return one ``kind:value`` entry per literal of ``source`` standing where a tax fact could."""
    tree = ast.parse(source)
    sweep = _Sweep(tree, modelos, periods)
    sweep.visit(tree)
    return sweep.findings


def sweep_tree(root: Path, *, modelos: frozenset[str], periods: frozenset[str]) -> dict[str, dict[str, int]]:
    """Return the findings of every production module below ``root``, by relative path."""
    found: dict[str, dict[str, int]] = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if "tests" in relative.parts:
            continue
        counted = Counter(sweep_source(path.read_text(encoding="utf-8"), modelos=modelos, periods=periods))
        if counted:
            found[relative.as_posix()] = dict(sorted(counted.items()))
    return found


def _current() -> dict[str, dict[str, int]]:
    modelos, periods = _modelo_ids(), _period_codes()
    found: dict[str, dict[str, int]] = {}
    for top in _SCANNED:
        for path, entries in sweep_tree(_SRC / top, modelos=modelos, periods=periods).items():
            found[f"{top}/{path}"] = entries
    return found


def _differences(
    current: dict[str, dict[str, int]], recorded: dict[str, dict[str, int]]
) -> tuple[list[str], list[str]]:
    """Return the entries the code has beyond the record, and those the record holds beyond the code."""
    new: list[str] = []
    gone: list[str] = []
    for path in sorted(current.keys() | recorded.keys()):
        now = Counter(current.get(path, {}))
        before = Counter(recorded.get(path, {}))
        new += [f"{path} {entry} x{count}" for entry, count in (now - before).items()]
        gone += [f"{path} {entry} x{count}" for entry, count in (before - now).items()]
    return new, gone


_FAKE_MODELOS: Final = frozenset({"303", "111", "100"})
_FAKE_PERIODS: Final = frozenset({"0A", "1T", "01"})


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("cap = Decimal('300.51')\n", "decimal"),
        ("clave: int = Field(ge=1, le=7)\n", "field_le"),
        ("BOX = '0208'\n", "code"),
        ("box = '303'\n", "code"),
        ("ROUTED = frozenset({Modelo('111').value, Modelo('303').value})\n", "modelo_set"),
        ("ok = modelo in {'111', '303'}\n", "modelo_set"),
        ("if clave == 'A':\n    pass\n", "letter_clave"),
        ("subclave = 'B'\n", "letter_clave"),
        ("tipo_renta_code: str = 'XY'\n", "letter_clave"),
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
    ],
)
def test_the_sweep_admits_what_stands_where_no_tax_fact_can(line: str) -> None:
    assert sweep_source(line, modelos=_FAKE_MODELOS, periods=_FAKE_PERIODS) == []


def test_a_defect_added_to_a_copied_tree_fails_the_comparison(tmp_path: Path) -> None:
    source = _SRC / "domain" / "period.py"
    copy = tmp_path / "domain" / "period.py"
    copy.parent.mkdir(parents=True)
    copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    modelos, periods = _modelo_ids(), _period_codes()
    clean = sweep_tree(tmp_path, modelos=modelos, periods=periods)

    with copy.open("a", encoding="utf-8") as handle:
        handle.write("\n_INSTALMENT_CAP = Decimal('300.51')\n")

    new, gone = _differences(sweep_tree(tmp_path, modelos=modelos, periods=periods), clean)
    assert new == ["domain/period.py decimal:'300.51' x1"]
    assert gone == []


def test_the_domain_and_application_code_adds_no_tax_literal() -> None:
    recorded = json.loads(_BASELINE.read_text(encoding="utf-8"))
    new, gone = _differences(_current(), recorded)
    assert not new, f"a tax value belongs to the registry: {new}"
    assert not gone, f"these findings are gone, so rerun this file with --write to shrink the record: {gone}"


if __name__ == "__main__" and sys.argv[1:] == ["--write"]:
    _BASELINE.write_text(json.dumps(_current(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
