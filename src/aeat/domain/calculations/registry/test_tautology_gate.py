"""Regression gate against tautological calculation tests.

This test enforces ``.claude/rules/no-tautological-calculation-tests.md``
mechanically. For every chain-behaviour scenario declared with
synthetic casilla input overrides + a hardcoded expected output, the
gate replays the registry's declared formula against the test's own
inputs. If the registry formula's output equals the test's expected
literal, the test is tautological — the assertion only verifies that
"the formula declared on disk computes what the formula declared on
disk says it computes."

The gate is intentionally conservative: when the formula references
bindings or parameters that the gate cannot resolve without runtime
context, the case is reported as DERIVED and skipped. The audit is
deliberately strict on the cases it CAN replay so that pure
arithmetic tautologies (sum/subtract/min/max/percent over literal
casilla values) cannot land.

Allowed patterns (per the rule):
- Workbook-parity assertions
- AEAT-published worked-example replays
- Live oracle replay (renta_web_open replay payloads)
- Identity round-trips for ``op = "copy"`` formulas
- Structural / graph-wiring assertions
- Python primitive contracts
"""

from __future__ import annotations

import ast
import tomllib
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _load_modelo_100_formulas_2025() -> dict[str, dict]:
    data = tomllib.loads(
        (PROJECT_ROOT / "registry" / "aeat" / "modelos" / "100" / "revisions" / "2025.toml").read_text(encoding="utf-8")
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
    except Exception:
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

Add a target to this set only with an inline reason that names an
external authority (workbook parity record, BOE worked-example
reference, or a live oracle payload id). The waiver entries decay
under the same review rule that landed them.
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
        "positive coverage. See .claude/rules/no-tautological-calculation-tests.md.\n\n"
        + "\n".join(f"  - {t}" for t in tautologies)
    )
