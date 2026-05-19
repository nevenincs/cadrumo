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
    leaf_value = _evaluate_leaf_expression(expr, casilla_values)
    if leaf_value is not _LEAF_NOT_LEAF:
        return leaf_value
    op = expr.get("op")
    args = expr.get("args") or []
    raw_values = [_evaluate_expression(a, casilla_values) for a in args]
    if any(v is None for v in raw_values):
        return None
    arg_values: list[Decimal] = [v for v in raw_values if v is not None]
    try:
        return _apply_arithmetic_op(op, arg_values)
    except (ValueError, ArithmeticError):
        return None


_LEAF_NOT_LEAF: object = object()
"""Sentinel returned by :func:`_evaluate_leaf_expression` to mean "not a leaf".

Distinct from ``None`` (which the leaf path returns when a casilla /
relation lookup misses) so the caller can tell "tried as leaf and
failed" from "wasn't a leaf in the first place".
"""


def _evaluate_leaf_expression(
    expr: dict,
    casilla_values: dict[str, Decimal],
) -> Decimal | None | object:
    """Return the leaf-shape value, ``None`` if the leaf can't resolve, or the sentinel."""
    if "literal" in expr:
        return Decimal(str(expr["literal"]))
    if "casilla" in expr:
        return casilla_values.get(expr["casilla"])
    if "relation" in expr:
        return casilla_values.get(expr["relation"])
    if "binding" in expr or "parameter" in expr or "dispatch_table" in expr:
        return None  # runtime-only leaf; replay can't resolve without context
    return _LEAF_NOT_LEAF


def _apply_arithmetic_op(op: object, args: list[Decimal]) -> Decimal | None:
    """Best-effort scalar arithmetic for the seven ops the gate replays.

    Returns ``None`` for unsupported ops (the gate skips those targets
    rather than emit a false-positive). Raises through ValueError /
    ArithmeticError so the caller can return None on math failures.
    """
    if op == "sum":
        return sum(args, Decimal("0"))
    if op == "add" and len(args) == 2:
        return args[0] + args[1]
    if op == "subtract" and len(args) == 2:
        return args[0] - args[1]
    if op == "negate" and len(args) == 1:
        return -args[0]
    if op == "min":
        return min(args)
    if op == "max":
        return max(args)
    if op == "percent" and len(args) == 2:
        return args[0] * args[1] / Decimal("100")
    return None


def _extract_scenarios(text: str) -> list[tuple[dict[str, Decimal], list[tuple[str, Decimal]]]]:
    """Extract (overrides, expected_outputs) pairs from a test file's AST."""

    findings: list[tuple[dict[str, Decimal], list[tuple[str, Decimal]]]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_scenario_2025"
        ):
            continue
        overrides = _scenario_overrides(node)
        expected = _scenario_expected(node)
        if expected:
            findings.append((overrides, expected))
    return findings


def _decimal_literal_value(node: ast.expr | None) -> Decimal | None:
    """Return ``Decimal("<raw>")`` if ``node`` matches that exact AST shape."""
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Decimal"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return None
    try:
        return Decimal(node.args[0].value)
    except (ValueError, ArithmeticError):
        return None


def _scenario_overrides(node: ast.Call) -> dict[str, Decimal]:
    """Read the ``overrides=`` mapping kwarg into a plain {str: Decimal} dict."""
    overrides: dict[str, Decimal] = {}
    for kw in node.keywords:
        if kw.arg != "overrides" or not isinstance(kw.value, ast.Dict):
            continue
        for k, v in zip(kw.value.keys, kw.value.values, strict=False):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            decimal_value = _decimal_literal_value(v)
            if decimal_value is not None:
                overrides[k.value] = decimal_value
    return overrides


def _scenario_expected(node: ast.Call) -> list[tuple[str, Decimal]]:
    """Read the ``expected=`` tuple kwarg into [(target, value), …]."""
    expected: list[tuple[str, Decimal]] = []
    for kw in node.keywords:
        if kw.arg != "expected" or not isinstance(kw.value, ast.Tuple):
            continue
        for elt in kw.value.elts:
            target_value = _expected_target_value(elt)
            if target_value is not None:
                expected.append(target_value)
    return expected


def _expected_target_value(node: ast.expr) -> tuple[str, Decimal] | None:
    """Read one ``RegistryScenarioExpectedOutput(target=…, value=Decimal("…"))`` literal."""
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "RegistryScenarioExpectedOutput"
    ):
        return None
    target: str | None = None
    value: Decimal | None = None
    for kkw in node.keywords:
        if (
            kkw.arg == "target"
            and isinstance(kkw.value, ast.Constant)
            and isinstance(kkw.value.value, str)
        ):
            target = kkw.value.value
        elif kkw.arg == "value":
            value = _decimal_literal_value(kkw.value)
    if target and value is not None:
        return (target, value)
    return None


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
            flagged.extend(_scan_function_for_hand_sums(node, path))
    return flagged


def _collect_decimal_literals(node: ast.FunctionDef) -> list[Decimal]:
    """Return every ``Decimal("<raw>")`` literal value used anywhere in ``node``."""
    literals: list[Decimal] = []
    for inner in ast.walk(node):
        value = _decimal_literal_value(inner) if isinstance(inner, ast.expr) else None
        if value is not None:
            literals.append(value)
    return literals


def _find_hand_summed_combo(target: Decimal, literals: list[Decimal]) -> tuple[Decimal, ...] | None:
    """Return the first 2-to-4-literal subset that sums to target, or None."""
    # Drop additive identities so the scanner does not flag cases like
    # ``x = x + 0`` or ``0 + 0 + x = x`` where the "sum" is trivially the
    # target itself.
    useful = [lit for lit in literals if lit != Decimal("0") and lit != target]
    if len(useful) < 2:
        return None
    for size in (2, 3, 4):
        if len(useful) < size:
            continue
        for combo in combinations(useful, size):
            if sum(combo, Decimal("0")) == target:
                return combo
    return None


def _scan_function_for_hand_sums(node: ast.FunctionDef, path: Path) -> list[str]:
    """Apply the hand-summed-aggregation rule to one test function."""
    literals = _collect_decimal_literals(node)
    if len(literals) < 3:
        return []
    flagged: list[str] = []
    for assertion in (n for n in ast.walk(node) if isinstance(n, ast.Assert)):
        target = _assertion_decimal_target(assertion)
        if target is None or target == Decimal("0"):
            continue
        hit_combo = _find_hand_summed_combo(target, literals)
        if hit_combo is None:
            continue
        waiver_key = f"{path.relative_to(PROJECT_ROOT).as_posix()}::{node.name}"
        if waiver_key in _HAND_SUMMED_WAIVERS:
            continue
        flagged.append(
            f"{waiver_key} "
            f"line {assertion.lineno}: target {target} equals sum of "
            f"{len(hit_combo)} earlier literals {hit_combo} — hand-summed pattern"
        )
    return flagged


def _assertion_decimal_target(assertion: ast.Assert) -> Decimal | None:
    """Return the right-hand Decimal literal of an ``assert lhs == Decimal("…")`` shape, else None."""
    test = assertion.test
    if not isinstance(test, ast.Compare):
        return None
    if not test.ops or not isinstance(test.ops[0], ast.Eq):
        return None
    rhs = test.comparators[0] if test.comparators else None
    return _decimal_literal_value(rhs)


_HAND_SUMMED_WAIVERS: frozenset[str] = frozenset(
    {
        # ``sum_deductible_amounts`` is a Decimal-sum helper whose only
        # job is to thread a sum through Decimal addition; the
        # accompanying test verifies the Python primitive contract,
        # not a registry formula.
        "src/aeat/domain/vat/test_prorrata.py::test_sum_deductible_amounts_threads_through_decimal_addition",
        # Round-trip identity: asserts the deserialised modelo-190
        # perceptor rows preserve the original per-perceptor amounts
        # byte-for-byte. The sum across perceptors is incidental
        # fixture data — the test does not aggregate.
        "src/aeat/application/calculations/test_detail_record_round_trip.py::test_modelo_190_perceptor_round_trip_preserves_typed_values",
        # Decimal-precision JSON round-trip on a populated ledger
        # command. amount/taxable_base/iva_amount form a sum
        # incidentally; the test pins precision preservation, not an
        # aggregator's arithmetic.
        "src/aeat/application/ledger/test_manual_ledger_transaction_command_roundtrip.py::test_command_json_roundtrip_preserves_decimal_precision",
        # Encrypted-storage round-trip identity for an invoice
        # catalogue. base_total + iva_total = grand_total is invoice
        # math captured at construction; the assertion targets the
        # round-tripped copy, not an aggregator output.
        "src/aeat/domain/invoices/test_secure_storage_roundtrip.py::test_invoice_catalogue_survives_encrypted_storage_roundtrip",
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
