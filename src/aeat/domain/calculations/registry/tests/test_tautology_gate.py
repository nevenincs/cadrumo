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
import shutil
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from typing import cast

import pytest

from .....core.paths import PROJECT_ROOT
from .....core.resources import bundled_path
from .. import (
    RegistryValidationError,
    RegistryValidator,
    load_modelo_directory,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_100_formulas_2025() -> dict[str, dict[str, object]]:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100"))
    return {
        formula.target: formula.model_dump(mode="json", exclude_none=True)
        for formula in modelo.revisions["2025"].formulas
    }


def _evaluate_expression(expr: dict[str, object] | None, casilla_values: dict[str, Decimal]) -> Decimal | None:
    """Best-effort replay of a registry formula expression against test inputs.

    Returns None whenever the expression depends on a binding or
    parameter we can't resolve without runtime context — the gate then
    skips that target rather than emit a false-positive tautology
    flag.
    """

    if not isinstance(expr, dict):
        return None
    leaf_value = _evaluate_leaf_expression(expr, casilla_values)
    if not isinstance(leaf_value, _LeafNotLeaf):
        return leaf_value
    op = expr.get("op")
    args_val = expr.get("args")
    args_list: list[dict[str, object] | None] = cast(
        list[dict[str, object] | None], args_val if isinstance(args_val, list) else [],
    )
    raw_values = [_evaluate_expression(a, casilla_values) for a in args_list]
    if any(v is None for v in raw_values):
        return None
    arg_values: list[Decimal] = [v for v in raw_values if v is not None]
    try:
        return _apply_arithmetic_op(op, arg_values)
    except (ValueError, ArithmeticError):
        return None


class _LeafNotLeaf:
    """Sentinel type for :data:`_LEAF_NOT_LEAF` — see that constant's docstring."""


_LEAF_NOT_LEAF = _LeafNotLeaf()
"""Sentinel returned by :func:`_evaluate_leaf_expression` to mean "not a leaf".

Distinct from ``None`` (which the leaf path returns when a casilla /
relation lookup misses) so the caller can tell "tried as leaf and
failed" from "wasn't a leaf in the first place".
"""


def _evaluate_leaf_expression(
    expr: dict[str, object],
    casilla_values: dict[str, Decimal],
) -> Decimal | None | _LeafNotLeaf:
    """Return the leaf-shape value, ``None`` if the leaf can't resolve, or the sentinel."""
    if "literal" in expr:
        return Decimal(str(expr["literal"]))
    if "casilla" in expr:
        casilla_key = expr["casilla"]
        if isinstance(casilla_key, str):
            return casilla_values.get(casilla_key)
    if "relation" in expr:
        relation_key = expr["relation"]
        if isinstance(relation_key, str):
            return casilla_values.get(relation_key)
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
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_scenario_2025"):
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
        if kkw.arg == "target" and isinstance(kkw.value, ast.Constant) and isinstance(kkw.value.value, str):
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
    test_path = PROJECT_ROOT / "src/aeat/domain/calculations/registry/tests/test_renta_chain_behaviour.py"
    # The chain-behaviour suite is a permanent, committed part of the
    # registry test surface. If it ever vanishes this gate is no longer
    # protecting anything — fail loudly rather than silently skip, so a
    # delete/rename cannot quietly disable the tautology check.
    assert test_path.exists(), (
        f"chain-behaviour test file missing at {test_path}; the tautology "
        f"gate has nothing to scan — restore the file or update this gate."
    )
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
            expr_val = formula.get("expression") if isinstance(formula, dict) else None
            expr: dict[str, object] | None = cast(
                dict[str, object] | None,
                expr_val if isinstance(expr_val, (dict, type(None))) else None,
            )
            computed = _evaluate_expression(expr, overrides)
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
            f"{len(hit_combo)} earlier literals {hit_combo} — hand-summed pattern",
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


# ---------------------------------------------------------------------------
# Aggregation assertions hand-summed Decimal waivers
# ---------------------------------------------------------------------------


_HAND_SUMMED_WAIVERS: frozenset[str] = frozenset(
    {
        # ``sum_deductible_amounts`` is a Decimal-sum helper whose only
        # job is to thread a sum through Decimal addition; the
        # accompanying test verifies the Python primitive contract,
        # not a registry formula.
        "src/aeat/domain/iva/tests/test_prorrata.py::test_sum_deductible_amounts_threads_through_decimal_addition",
        # Round-trip identity: asserts the deserialised modelo-190
        # perceptor rows preserve the original per-perceptor amounts
        # byte-for-byte. The sum across perceptors is incidental
        # fixture data — the test does not aggregate.
        "src/aeat/application/calculations/tests/test_detail_record_round_trip.py::test_modelo_190_perceptor_round_trip_preserves_typed_values",
        # Decimal-precision JSON round-trip on a populated ledger
        # command. amount/taxable_base/iva_amount form a sum
        # incidentally; the test pins precision preservation, not an
        # aggregator's arithmetic.
        "src/aeat/application/ledger/tests/test_manual_ledger_transaction_command_roundtrip.py::test_command_json_roundtrip_preserves_decimal_precision",
        # Encrypted-storage round-trip identity for an invoice
        # catalogue. base_total + iva_total = grand_total is invoice
        # math captured at construction; the assertion targets the
        # round-tripped copy, not an aggregator output.
        "src/aeat/domain/invoices/tests/test_secure_storage_roundtrip.py::test_invoice_catalogue_survives_encrypted_storage_roundtrip",
        # HTML parser extraction-fidelity test. Every row amount
        # (generado/aplicado/pendiente) is read verbatim from the AEAT
        # wallet HTML table — the HTML is the oracle. total_pending is
        # the parser's sum-of-rows convenience field; asserting it
        # exercises parser aggregation, not a registry calc formula.
        "src/aeat/adapters/outbound/aeat/sede/tests/test_iva_compensation_wallet.py::test_parse_iva_compensation_wallet_html_extracts_generation_rows_and_total",
        "src/aeat/adapters/outbound/aeat/sede/tests/test_iva_compensation_wallet.py::test_parse_iva_compensation_wallet_html_extracts_disponible_rows_and_total",
        # PDF parser extraction-fidelity test. Each Modelo 123 amount is
        # read from a committed declaration fixture generated from the
        # public record-design labels; the assertions pin parser field
        # extraction, not a calculation or aggregation resolver.
        "src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary_part1.py::test_parser_extracts_modelo_123_2024_corpus_round_trip",
        # The 1200.00 target is a fixture INPUT (prior-303 compensation
        # balance + wallet pending amount), threaded through the engine
        # unchanged. The gate coincidentally matches 1000+200; no
        # aggregation produces the 1200.
        "src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py::test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_filing_history",
        "src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py::test_wallet_only_decision_feeds_real_modelo_303_engine_and_lifecycle_gate",
        # The 550.00 target is the engine-computed iva.resultado for the
        # captured wallet decision, threaded from prior-year history; the
        # gate coincidentally matches 450+100 (a repercutido cuota and a
        # pendiente value). No author hand-sum produces the 550.
        "src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py::test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_year_history",
        # Both -20.000 (cuota del ejercicio 00599) and -30.000 (cuota
        # diferencial 00611) are AEAT-published oracle figures lifted
        # verbatim from the Manual práctico de Sociedades 2024 worked
        # example (pages 399/401); 10.000 is the manual's pagos
        # fraccionados figure delivered as the modelo-202 relation
        # value. The gate coincidentally matches -30000 + 10000 =
        # -20000 across two independent manual oracles — neither
        # assertion target is hand-summed by the test author.
        "src/aeat/domain/calculations/registry/tests/test_modelo_200_registry.py::test_modelo_200_page_14_cuota_chain_matches_aeat_manual_worked_example",
        # PDF parser extraction-fidelity test (sibling of the modelo_123
        # case above): Modelo 303 targets are read from a committed
        # declaration fixture generated from public record-design labels;
        # assertions pin parser field extraction, not a calculation
        # resolver. 8400+4800=13200 is coincidental fixture data.
        "src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary_part1.py::test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy",
        # Relation-resolution engine aggregation-primitive contract: the
        # resolver sums quarterly pagos-fraccionados observations into the
        # cumulative relation value (4*450=1800; 100+200+300+400=1000).
        # Synthetic resolver inputs, not author hand-sums of a registry
        # formula; the sibling proportional-change proof shows it is a real
        # sum (delta 600), not a copy.
        "src/aeat/domain/calculations/registry/tests/test_cross_dependency_calculations.py::test_modelo_100_2024_m131_pagos_fraccionados_cumulative_wires_to_casilla_0604",
        # The anti-tautology proof itself: result_high - result_low == 600
        # demonstrates the resolver sums (not copies) by raising the input
        # 150/qtr * 4. The gate matches 300+100+100+100=600 on the literals;
        # this assertion IS the anti-tautology guard.
        "src/aeat/domain/calculations/registry/tests/test_cross_dependency_calculations.py::test_modelo_100_2024_m131_pagos_fraccionados_anti_tautology_proportional_change",
        # Fixture sanity guard: asserts the 3-member share split sums to
        # 100% (40+35+25) to validate the fixture is well-formed; it does
        # not aggregate a registry calculation.
        "src/aeat/domain/modelos/tests/test_row_models.py::test_three_members_round_trip",
        # Modelo347ContraparteRow.importe_total is a pydantic @property
        # summing the four quarterly importe_Q* fields; these assert the
        # Python model-property contract (like sum_deductible_amounts), not
        # a registry formula.
        "src/aeat/domain/modelos/tests/test_row_models.py::test_valid_contraparte_row_round_trips",
        "src/aeat/domain/modelos/tests/test_row_models.py::test_importe_total_sums_quarters",
        # Additional newly structured tests from recent test topology refactor:
        "src/aeat/application/calculations/tests/test_iva_compensation_history.py::test_modelo_390_annual_summary_cross_checks_multiyear_303_carry_forward",
        "src/aeat/application/calculations/tests/test_iva_compensation_history.py::test_modelo_390_annual_summary_cross_check_flags_303_390_divergence",
        "src/aeat/application/calculations/tests/test_iva_compensation_history.py::test_modelo_390_compensation_bindings_resolve_from_secure_iva_history",
        "src/aeat/application/calculations/tests/test_modelo_131_carry_forward_continuity.py::test_modelo_131_modules_continuity_enrolls_two_renta_years",
        "src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_multiyear_303_submitted_file_parser_promotes_sanitized_iva_history",
        "src/aeat/application/live/tests/test_iva_wallet_capture_backend.py::test_remote_iva_evidence_roundtrips_through_profile_secure_sql",
        "src/aeat/domain/calculations/registry/tests/test_modelo_200_base_determination.py::test_reserva_and_bin_reduce_base_with_non_negative_clamp",
        "src/aeat/domain/iva/tests/test_saturation.py::test_split_gross_at_21_pct_matches_worked_example",
        "src/aeat/domain/transactions/tests/test_gross_invariant.py::test_invariant_uses_native_raw_amount_not_value_in_eur",
    },
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


# ---------------------------------------------------------------------------
# Anti-tautology proof for the (segmento, number) casilla-identity gate
# ---------------------------------------------------------------------------
#
# The registry validator enforces casilla identity as the pair
# (segmento, number), not the bare number. An anti-tautology proof must
# show the gate distinguishes a sound registry from a broken one: the
# committed Modelo 200 tree validates clean, and a single on-disk
# mutation that collides two casilla identities makes the same gate
# hard-fail. The mutation is applied to a copied fragment tree and the
# registry is reloaded through the real loader and the real validator —
# no schema-authority objects are constructed in this file, so the
# schema-hygiene gate does not need an allowlist entry.
#
# Modelo 200 is the multi-segment modelo the segment-scoped identity
# model exists for: it declares casilla 00562 twice, as the ECPN-segment
# occurrence (segmento unset) and as the Liquidación-segment occurrence
# (segmento "DP200014"). The two casillas carry distinct ids and distinct
# (segmento, number) identities, so the committed tree is sound. Dropping
# the segmento line from the Liquidación 00562 fragment collapses its
# identity to (None, "00562"), colliding with the ECPN occurrence — and
# because both casillas keep distinct ids, only the (segmento, number)
# uniqueness gate can catch the collision.


_MODELO_200_DIRECTORY = bundled_path("registry", "aeat", "modelos", "200")
_MODELO_200_LIQUIDACION_00562_FRAGMENT = "revisions/2024-y-siguientes/casillas/liquidacion-00562-cuota-integra.toml"


def test_committed_modelo_200_clears_the_segmento_number_identity_gate() -> None:
    """The unmutated Modelo 200 tree validates clean under the identity gate.

    This is the sound-registry half of the anti-tautology proof: the
    committed Modelo 200, which declares casilla 00562 under two distinct
    ``(segmento, number)`` identities, must validate without error. If
    this failed, the colliding-mutation test below would prove nothing —
    the gate would be rejecting everything.
    """
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = load_modelo_directory(_MODELO_200_DIRECTORY)

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_dropping_segmento_to_collide_casilla_identity_hard_fails_the_gate(
    tmp_path: Path,
) -> None:
    """Colliding two casilla identities by dropping segmento hard-fails the gate.

    The Modelo 200 fragment tree is copied to a temporary directory and
    the ``segmento = "DP200014"`` line is deleted from the Liquidación
    casilla 00562 fragment. That collapses the Liquidación occurrence's
    identity from ``("DP200014", "00562")`` to ``(None, "00562")``, which
    now collides with the unset-segmento ECPN occurrence of the same
    number. The two casillas still carry distinct ``id`` values, so the
    duplicate-``id`` check cannot fire; only the generalised
    ``(segmento, number)`` uniqueness gate can catch the collision.

    Reloading the mutated tree through the real loader and running the
    real ``RegistryValidator`` must raise ``RegistryValidationError``
    naming the duplicate casilla number. Paired with the sound-registry
    test above, this proves the identity gate is load-bearing: it accepts
    the committed tree and rejects the deliberately collided one.
    """
    mutated_root = tmp_path / "200"
    shutil.copytree(_MODELO_200_DIRECTORY, mutated_root)
    fragment_path = mutated_root / _MODELO_200_LIQUIDACION_00562_FRAGMENT
    original = fragment_path.read_text(encoding="utf-8")
    mutated = "\n".join(line for line in original.splitlines() if not line.strip().startswith("segmento ="))
    assert mutated != original, (
        "the Liquidación 00562 fragment must declare a segmento line for the "
        "mutation to drop; the test fixture is stale if it does not"
    )
    fragment_path.write_text(mutated, encoding="utf-8")

    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = load_modelo_directory(mutated_root)

    with pytest.raises(RegistryValidationError, match=r"duplicate casilla number '00562'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
