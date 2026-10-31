"""Reject a tax value written into the activity-asset code instead of the registry.

Every limit, period and form code of the activity-asset register belongs to the
published authority. This gate reads the code's syntax, so what it admits is a
position a number can lawfully hold, never a list of permitted values: a new
literal is rejected unless where it stands already says why it is not a tax fact.
"""

from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parents[3] / "src" / "cadrumo"
_DIRECTORIES = (
    _SRC / "domain" / "renta" / "actividad_asset",
    _SRC / "application" / "actividad_asset",
)
_FILES = (
    _SRC / "application" / "aggregation" / "modelo_bindings_actividad_assets.py",
    _SRC / "application" / "aggregation" / "activity_asset_ledger_reconciliation.py",
)
_REGISTRY_GLOB = (_SRC / "domain" / "calculations" / "registry", "actividad_asset_*.py")

_ARITHMETIC_IDENTITIES = frozenset({0, 1})
_FIELD_BOUNDS = frozenset({"ge", "gt", "le", "lt", "min_length", "max_length", "default"})
_TECHNICAL_CONSTANT = re.compile(r"_(LIMIT|PER_DAY|PER_YEAR)$")
_CODE_SHAPED = re.compile(r"^(?!0+$)\d{1,4}[A-Z]?$")
_RECORD_ADDRESS_KEYWORDS = frozenset({"modelo", "period"})
_RECORD_ADDRESS_FUNCTIONS = frozenset({"revision_for_context"})
_BOX_SHAPE_PATTERN = re.compile(r"\\d\{")


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _called_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else ""


def _chain(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    found: list[ast.AST] = []
    while node in parents:
        node = parents[node]
        found.append(node)
    return found


def _is_decimal_argument(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return isinstance(parent, ast.Call) and _called_name(parent) == "Decimal"


def _numeric_position_is_lawful(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    """Say whether a number stands where only arithmetic, the calendar or a technical bound can."""
    outer = node
    parent = parents.get(outer)
    if isinstance(parent, ast.Call) and _called_name(parent) == "Decimal":
        outer, parent = parent, parents.get(parent)
    if isinstance(parent, ast.UnaryOp):
        outer, parent = parent, parents.get(parent)
    if isinstance(parent, ast.BinOp):
        if isinstance(parent.op, (ast.Div, ast.Mult)) and node.value in {"100", 100}:
            return True
        if isinstance(parent.op, ast.FloorDiv) and parent.right is outer:
            return True
    if isinstance(parent, ast.Compare) and any(
        isinstance(side, ast.Call) and _called_name(side) == "len" for side in (parent.left, *parent.comparators)
    ):
        return True
    if isinstance(parent, ast.Compare) and node.value in {"100", 100} and "percentage" in ast.dump(parent.left):
        return True
    if isinstance(parent, ast.keyword):
        return parent.arg in _FIELD_BOUNDS and not isinstance(outer, ast.Call)
    for ancestor in _chain(outer, parents):
        if isinstance(ancestor, ast.IfExp) and "isleap" in ast.dump(ancestor.test):
            return True
        if (
            isinstance(ancestor, ast.Subscript)
            and ancestor.slice in parents
            and _within(outer, ancestor.slice, parents)
        ):
            return True
        if isinstance(ancestor, (ast.Assign, ast.AnnAssign)):
            targets = ancestor.targets if isinstance(ancestor, ast.Assign) else [ancestor.target]
            return any(isinstance(item, ast.Name) and _TECHNICAL_CONSTANT.search(item.id) for item in targets)
    return False


def _within(node: ast.AST, ancestor: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    return node is ancestor or ancestor in _chain(node, parents)


def _year_end_date(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return (
        isinstance(parent, ast.Call)
        and _called_name(parent) == "date"
        and len(parent.args) == 3
        and [getattr(item, "value", None) for item in parent.args[1:]] in ([12, 31], [1, 1])
    )


def _code_position_is_lawful(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    """Say whether a code-shaped string only addresses a registry record, naming no box or clave."""
    parent = parents.get(node)
    if isinstance(parent, ast.keyword):
        return parent.arg in _RECORD_ADDRESS_KEYWORDS
    if isinstance(parent, ast.Call):
        return _called_name(parent) in _RECORD_ADDRESS_FUNCTIONS
    for ancestor in _chain(node, parents):
        if isinstance(ancestor, ast.AnnAssign) and isinstance(ancestor.target, ast.Name):
            return ancestor.target.id in _RECORD_ADDRESS_KEYWORDS
    return False


def _docstring_constants(tree: ast.AST) -> set[ast.AST]:
    found: set[ast.AST] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for statement in body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                found.add(statement.value)
    return found


def tax_literal_findings(source: str) -> list[str]:
    """Return every literal of ``source`` that stands where a tax fact could.

    Returns:
        One ``line: value`` entry per finding.
    """
    tree = ast.parse(source)
    parents = _parents(tree)
    docstrings = _docstring_constants(tree)
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or node in docstrings or isinstance(node.value, bool):
            continue
        value = node.value
        if isinstance(value, (int, float)):
            lawful = (
                value in _ARITHMETIC_IDENTITIES
                or _numeric_position_is_lawful(node, parents)
                or _year_end_date(node, parents)
            )
        elif isinstance(value, str) and _is_decimal_argument(node, parents):
            lawful = Decimal(value) in _ARITHMETIC_IDENTITIES or _numeric_position_is_lawful(node, parents)
        elif isinstance(value, str) and _CODE_SHAPED.match(value):
            lawful = _code_position_is_lawful(node, parents)
        elif isinstance(value, str):
            lawful = not _BOX_SHAPE_PATTERN.search(value)
        else:
            lawful = True
        if not lawful:
            findings.append(f"{node.lineno}: {value!r}")
    return findings


def _governed_files() -> tuple[Path, ...]:
    directory, pattern = _REGISTRY_GLOB
    return (
        *(path for root in _DIRECTORIES for path in sorted(root.glob("*.py"))),
        *_FILES,
        *sorted(directory.glob(pattern)),
    )


@pytest.mark.parametrize(
    ("line", "value"),
    [
        ("_PERIOD = 3\n", "3"),
        ("x = affected.year + 3\n", "3"),
        ("cap = amount * 2\n", "2"),
        ("cap = Decimal('300')\n", "'300'"),
        ("cap = Decimal('1000')\n", "'1000'"),
        ("cap = amount * Decimal('0.25')\n", "'0.25'"),
        ("BOX = '0208'\n", "'0208'"),
        ("CLAVE: Final[str] = '5'\n", "'5'"),
        ("box = validated_casilla_id('01')\n", "'01'"),
        ("target: Literal['02'] = '02'\n", "'02'"),
    ],
)
def test_the_gate_rejects_a_representative_new_literal(line: str, value: str) -> None:
    assert any(finding.endswith(value) for finding in tax_literal_findings(line))


def test_the_gate_rejects_a_box_shape_pattern() -> None:
    assert tax_literal_findings("box: str = Field(pattern=r'^0\\d{3}$')\n")


@pytest.mark.parametrize(
    "line",
    [
        "x = covered_until - timedelta(days=1)\n",
        "end = date(tax_year, 12, 31)\n",
        "days = 366 if calendar.isleap(year) else 365\n",
        "rate = value / Decimal('100')\n",
        "digits = period * (period + 1) // 2\n",
        "correction_number = original_revision_number + 1\n",
        "name: str = Field(max_length=128)\n",
        "ok = len(value) == 64\n",
        "_WALK_LIMIT = 100\n",
        "revision = operation.revision_for_context('100', filing_year=year, period='0A')\n",
        '"""A docstring may cite art. 28.3 and casilla 0208."""\n',
    ],
)
def test_the_gate_admits_what_stands_where_no_tax_fact_can(line: str) -> None:
    assert tax_literal_findings(line) == []


def test_the_activity_asset_code_states_no_tax_value() -> None:
    files = _governed_files()
    assert len(files) > 20, "the governed roots no longer hold the activity-asset code"
    findings = {
        str(path.relative_to(_SRC)): found
        for path in files
        if (found := tax_literal_findings(path.read_text(encoding="utf-8")))
    }
    assert not findings, findings
