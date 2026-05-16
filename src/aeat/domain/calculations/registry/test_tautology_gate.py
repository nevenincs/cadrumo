"""Regression gate against tautological calculation tests.

Two CI checks live here. The first replays every chain-behaviour
scenario's declared expected value against the registry's own formula:
if the registry mechanically reproduces the test author's literal from
the test's own synthetic inputs, the assertion is tautological. The
second walks every test file in ``src/aeat/`` and flags any assertion
whose hardcoded Decimal target equals the sum of two-or-more earlier
``Decimal(...)`` literals declared in the same function — the
hand-summed pattern that an aggregator under test mechanically
reproduces.

Both checks are conservative: expressions that reference unresolved
bindings or parameters are skipped, and additive identities
(``x == x + 0``) are filtered out before flagging. The strict half is
that pure-arithmetic compositions over literal casilla values and
hand-summed aggregations cannot land green.

Replacements available for the assertion patterns the gates reject:
workbook parity against AEAT's published ``dr.xls``, live oracle
replay against the Renta WEB Open simulator, AEAT-published worked
examples, identity round-trips for ``op = "copy"`` formulas,
structural / graph-wiring assertions, and Python primitive contracts.
"""

from __future__ import annotations

import ast
import contextlib
import tomllib
from decimal import Decimal
from itertools import combinations
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT
from aeat.core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _load_modelo_100_formulas_2025() -> dict[str, dict]:
    data = tomllib.loads(
        (bundled_path("registry", "aeat", "modelos", "100", "revisions", "2025.toml")).read_text(encoding="utf-8")
    )
    return {f["target"]: f for f in data["revisions"]["2025"].get("formulas", [])}


def _evaluate_expression(expr: dict | None, casilla_values: dict[str, Decimal]) -> Decimal | None:
    """Best-effort replay of a registry formula expression against test inputs.

    Returns None whenever the expression depends on a binding or
    parameter we can't resolve without runtime context — the gate then
    skips that target rather than emit a false-positive tautology
    flag.
    """

    if not isinstance(expr, dict):
        return None
    if "literal" in expr:
        return Decimal(str(expr["literal"]))
    if "casilla" in expr:
        return casilla_values.get(expr["casilla"])
    if "relation" in expr:
        return casilla_values.get(expr["relation"])
    if "binding" in expr or "parameter" in expr or "dispatch_table" in expr:
        return None
    op = expr.get("op")
    args = expr.get("args") or []
    raw_values = [_evaluate_expression(a, casilla_values) for a in args]
    if any(v is None for v in raw_values):
        return None
    arg_values: list[Decimal] = [v for v in raw_values if v is not None]
    try:
        if op == "sum":
            return sum(arg_values, Decimal("0"))
        if op == "add" and len(arg_values) == 2:
            return arg_values[0] + arg_values[1]
        if op == "subtract" and len(arg_values) == 2:
            return arg_values[0] - arg_values[1]
        if op == "negate" and len(arg_values) == 1:
            return -arg_values[0]
        if op == "min":
            return min(arg_values)
        if op == "max":
            return max(arg_values)
        if op == "percent" and len(arg_values) == 2:
            return arg_values[0] * arg_values[1] / Decimal("100")
    except (ValueError, ArithmeticError):
        return None
    return None


def _extract_scenarios(text: str) -> list[tuple[dict[str, Decimal], list[tuple[str, Decimal]]]]:
    """Extract (overrides, expected_outputs) pairs from a test file's AST."""

    findings: list[tuple[dict[str, Decimal], list[tuple[str, Decimal]]]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_scenario_2025":
            continue
        overrides: dict[str, Decimal] = {}
        expected: list[tuple[str, Decimal]] = []
        for kw in node.keywords:
            if kw.arg == "overrides" and isinstance(kw.value, ast.Dict):
                for k, v in zip(kw.value.keys, kw.value.values, strict=False):
                    if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                        continue
                    if not (isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "Decimal"):
                        continue
                    if v.args and isinstance(v.args[0], ast.Constant):
                        raw = v.args[0].value
                        if isinstance(raw, str):
                            overrides[k.value] = Decimal(raw)
            if kw.arg == "expected" and isinstance(kw.value, ast.Tuple):
                for elt in kw.value.elts:
                    if not (isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name)):
                        continue
                    if elt.func.id != "RegistryScenarioExpectedOutput":
                        continue
                    tgt: str | None = None
                    val: Decimal | None = None
                    for kkw in elt.keywords:
                        if (
                            kkw.arg == "target"
                            and isinstance(kkw.value, ast.Constant)
                            and isinstance(kkw.value.value, str)
                        ):
                            tgt = kkw.value.value
                        if kkw.arg == "value" and isinstance(kkw.value, ast.Call):
                            inner = kkw.value
                            if (
                                isinstance(inner.func, ast.Name)
                                and inner.func.id == "Decimal"
                                and inner.args
                                and isinstance(inner.args[0], ast.Constant)
                                and isinstance(inner.args[0].value, str)
                            ):
                                val = Decimal(inner.args[0].value)
                    if tgt and val is not None:
                        expected.append((tgt, val))
        if expected:
            findings.append((overrides, expected))
    return findings


_TAUTOLOGY_WAIVERS: frozenset[str] = frozenset()
"""Targets that have a documented non-tautological grounding.

Each waiver MUST name an external authority — a workbook-parity
record, an AEAT worked-example reference, or a live-oracle payload id.
Empty by default; entries decay under review.
"""


def test_chain_behaviour_scenarios_are_not_tautological() -> None:
    """Every chain-behaviour assertion must NOT be reproducible from its own inputs."""

    formulas = _load_modelo_100_formulas_2025()
    test_path = PROJECT_ROOT / "src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py"
    if not test_path.exists():
        pytest.skip("chain-behaviour test file not present")
    text = test_path.read_text(encoding="utf-8")
    scenarios = _extract_scenarios(text)
    tautologies: list[str] = []
    for overrides, expected in scenarios:
        for target, expected_value in expected:
            if target in _TAUTOLOGY_WAIVERS:
                continue
            formula = formulas.get(target)
            if formula is None:
                continue
            computed = _evaluate_expression(formula.get("expression"), overrides)
            if computed is None:
                continue
            if abs(computed - expected_value) < Decimal("0.01"):
                tautologies.append(f"target {target!r}: registry yields {computed} from test inputs — tautological")
    assert not tautologies, (
        "Tautological chain-behaviour assertions detected — assertions reproduce the\n"
        "registry's own formula arithmetic against synthetic inputs, producing false-\n"
        "positive coverage.\n\n" + "\n".join(f"  - {t}" for t in tautologies)
    )


def _scan_hand_summed_aggregations(test_dir: Path) -> list[str]:
    """Look for the rule's second-worst pattern across ALL test files.

    Forbidden: a test that constructs N observations / inputs with literal
    Decimal values, calls an aggregation resolver / runtime, then asserts
    a hardcoded Decimal that equals the sum of >=2 of those literals. The
    author's mental arithmetic matches the resolver's arithmetic because
    they encode the same operation, not because the resolver is correct
    against AEAT.

    The scanner walks each test function, extracts every literal
    ``Decimal("<n>")`` constructor and every hardcoded Decimal assertion
    target, and flags any assertion whose target equals the sum of >=2
    earlier literals. Additive identities (``target = target + 0``,
    ``x = x + 0 + ... ``) are filtered out before flagging.
    """

    flagged: list[str] = []
    for path in sorted(test_dir.rglob("test_*.py")):
        if path.name == "test_tautology_gate.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            literals: list[Decimal] = []
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                if not (isinstance(inner.func, ast.Name) and inner.func.id == "Decimal"):
                    continue
                if not inner.args or not isinstance(inner.args[0], ast.Constant):
                    continue
                raw = inner.args[0].value
                if not isinstance(raw, str):
                    continue
                with contextlib.suppress(Exception):
                    literals.append(Decimal(raw))
            if len(literals) < 3:
                continue
            for assertion in (n for n in ast.walk(node) if isinstance(n, ast.Assert)):
                if not isinstance(assertion.test, ast.Compare):
                    continue
                if not assertion.test.ops or not isinstance(assertion.test.ops[0], ast.Eq):
                    continue
                rhs = assertion.test.comparators[0] if assertion.test.comparators else None
                if not (
                    isinstance(rhs, ast.Call)
                    and isinstance(rhs.func, ast.Name)
                    and rhs.func.id == "Decimal"
                    and rhs.args
                    and isinstance(rhs.args[0], ast.Constant)
                    and isinstance(rhs.args[0].value, str)
                ):
                    continue
                try:
                    target = Decimal(rhs.args[0].value)
                except (ValueError, ArithmeticError):
                    continue
                if target == Decimal("0"):
                    continue
                # Drop additive identities so the scanner does not flag
                # cases like ``x = x + 0`` or ``0 + 0 + x = x`` where the
                # "sum" is trivially the target itself.
                useful = [lit for lit in literals if lit != Decimal("0") and lit != target]
                if len(useful) < 2:
                    continue
                hit_combo: tuple[Decimal, ...] | None = None
                for size in (2, 3, 4):
                    if len(useful) < size:
                        continue
                    for combo in combinations(useful, size):
                        if sum(combo, Decimal("0")) == target:
                            hit_combo = combo
                            break
                    if hit_combo is not None:
                        break
                if hit_combo is not None:
                    waiver_key = f"{path.relative_to(PROJECT_ROOT).as_posix()}::{node.name}"
                    if waiver_key in _HAND_SUMMED_WAIVERS:
                        continue
                    flagged.append(
                        f"{waiver_key} "
                        f"line {assertion.lineno}: target {target} equals sum of "
                        f"{len(hit_combo)} earlier literals {hit_combo} — hand-summed pattern"
                    )
    return flagged


_HAND_SUMMED_WAIVERS: frozenset[str] = frozenset(
    {
        # ``sum_deductible_amounts`` is a Decimal-sum helper whose only
        # job is to thread a sum through Decimal addition; the
        # accompanying test verifies the Python primitive contract,
        # not a registry formula.
        "src/aeat/domain/vat/test_prorrata.py::test_sum_deductible_amounts_threads_through_decimal_addition",
    }
)
"""Functions whose hand-summed pattern is documented as legitimate.

Each waiver MUST map to an explicit allowance — workbook parity, AEAT
worked example, live-oracle payload, Python primitive contract,
identity round-trip on op=copy, or structural / graph-wiring assertion.
Entries decay under review.
"""


def test_no_hand_summed_aggregation_tests_across_codebase() -> None:
    """No test in the codebase may hand-sum Decimal literals into a hardcoded aggregate."""

    test_dir = PROJECT_ROOT / "src" / "aeat"
    flagged = _scan_hand_summed_aggregations(test_dir)
    if flagged:
        message = (
            "Hand-summed aggregation assertions detected — the test author summed\n"
            "Decimal literals and asserts a hardcoded aggregate that the resolver\n"
            "mechanically reproduces.\n\n" + "\n".join(f"  - {f}" for f in flagged)
        )
        pytest.fail(message)
