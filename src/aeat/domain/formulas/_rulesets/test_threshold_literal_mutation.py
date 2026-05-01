"""Threshold-literal mutation harness (issue #457 Wave 5 strict-audit closure).

Closes the gap surfaced by the Wave-5 strict-review audit: ~120
:class:`Literal` nodes across the landed rulesets are operands of
:class:`SubFormula`, :class:`MinFormula`, :class:`MaxFormula`,
:class:`AddFormula`, :class:`RoundFormula`, or
:class:`ClampPositiveFormula` — bracket boundaries (e.g. M100 0540's
12450 / 20200 / 35200 / 60000 / 300000), LIRPF art. 20 piecewise
thresholds (14852 / 17673.52 / 7302 / 2364.34), IVA rate constants
(M303 02/05/08 = 4 / 10 / 21), additive-padding zeros, etc. A typo in
any of these silently miscalculates tax for taxpayers near the
boundary.

The mutator shifts the literal by ±1 € and asserts the audit surfaces
a discrepancy on the casilla. Architectural identities — ``Max(0, X)``
or ``Min(0, X)`` with ``X > 0`` — are filtered by
:func:`is_additive_identity_literal` (any small mutation has no
observable effect because the identity literal is dominated).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal

import pytest

from .._engine import Engine
from .._ruleset import Ruleset
from . import (
    MODELO_100_2024,
    MODELO_100_2025,
    MODELO_100_2026,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_130_2026,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
    MODELO_390_2024,
    MODELO_390_2025,
    MODELO_390_2026,
)
from ._mutators import (
    is_additive_identity_literal,
    iter_threshold_literal_paths,
    mutate_threshold_literal,
)
from .test_operand_swap_mutation import (
    _modelo_100_art20_piece_a_fixture,
    _modelo_100_art20_piece_b_fixture,
    _modelo_100_full_fixture_2024,
    _modelo_100_full_fixture_post_2025,
    _modelo_130_rich_fixture,
    _modelo_303_fixture,
    _modelo_390_fixture,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


@dataclass(frozen=True)
class _ThresholdCase:
    """One enumerated mutation case for the threshold-literal mutator."""

    ruleset: Ruleset
    casilla_id: str
    leaf_path: tuple[int, ...]
    parent_op: str
    offset: Decimal
    fixture: dict[str, Decimal]
    direction_id: str


_DEFAULT_OFFSETS: tuple[tuple[str, Decimal], ...] = (
    ("plus_1eur", Decimal("1")),
    ("minus_1eur", Decimal("-1")),
)


def _modelo_100_d_simplificada_cap_binding_fixture() -> dict[str, Decimal]:
    """M100 fixture driving the D simplificada 5 % cap into BINDING state.

    The comprehensive M100 fixture sets 0220 = 30 000 € so
    ``min(0.05 * 0220, 2000) = min(1500, 2000) = 1500`` — the 2000
    cap is NOT binding, and mutating its literal is invisible. To
    detect typos in the cap value, we drive 0220 = 50 000 € so
    ``min(2500, 2000) = 2000`` — cap IS binding, mutating 2000 →
    2001 produces ``min(2500, 2001) = 2001``, delta 1 €.

    This fixture is **minimal**: only the D simplificada chain
    inputs + the casilla 0225 baseline. The audit only checks
    casillas present in the fixture, so the broader M100 cascade
    (which would shift because 0240 changes when 0220 changes) is
    intentionally absent — ``audit_against`` skips computed casillas
    that aren't supplied.
    """
    return {
        "0210": Decimal("55000.00"),
        "0215": Decimal("5000.00"),
        "0235": Decimal("1000.00"),
        # Computed baselines for the D simplificada chain only.
        "0220": Decimal("50000.00"),
        "0225": Decimal("2000.00"),  # cap binding (2500 > 2000)
        "0230": Decimal("48000.00"),
        "0240": Decimal("47000.00"),
    }


def _modelo_390_devolver_fixture() -> dict[str, Decimal]:
    """M390 fixture driving casilla 191 NEGATIVE so 193's Literal(0) is observable.

    Casilla 193 = ``clamp_pos(sub_op(Literal(0), ref('191')))``. With
    191 > 0 (the default ``_modelo_390_fixture`` scenario), the inner
    ``Sub(0, 191)`` is negative and ``clamp_pos`` absorbs any
    epsilon-shift on the literal — pre-Wave-6 this was catalogued as a
    clamp-mask deferral. Driving 191 NEGATIVE (the legitimate
    "devolver" scenario where annual VAT due is negative because
    refunds exceeded charges) flips the inner ``Sub`` positive, so
    ``clamp_pos(0 - (-4200)) = 4200`` and a +1 EUR shift on the
    literal produces 4201 — delta 1 EUR, detectable.

    Inputs: 100 = 10 000, 101 = 5 000 → 104 = 15 000;
    96 = 30 000 → 105 = 15 000; 108 = 500, 109 = 300 → 190 = 15 800;
    662 = 20 000 → 191 = -4 200; 192 = clamp_pos(-4200) = 0;
    193 = clamp_pos(0 - (-4200)) = 4 200.
    """
    return {
        "95": Decimal("100000.00"),
        "96": Decimal("30000.00"),
        "100": Decimal("10000.00"),
        "101": Decimal("5000.00"),
        "104": Decimal("15000.00"),
        "105": Decimal("15000.00"),
        "108": Decimal("500.00"),
        "109": Decimal("300.00"),
        "190": Decimal("15800.00"),
        "191": Decimal("-4200.00"),
        "192": Decimal("0.00"),
        "193": Decimal("4200.00"),
        "662": Decimal("20000.00"),
    }


def _modelo_303_fixture_with_iva_rate_baselines() -> dict[str, Decimal]:
    """M303 fixture including printed-IVA-rate baseline values for 02/05/08.

    The base ``_modelo_303_fixture`` from the operand-swap harness omits
    casillas 02 / 05 / 08 (the printed IVA rates as standalone
    ``Round(Literal(rate))`` formulas) because they don't participate
    in the sub_op chain. The threshold-literal harness mutates those
    rate literals and needs the audit to compare derived vs provided,
    so the fixture is enriched with 02 = 4, 05 = 10, 08 = 21
    (LIVA arts. 90/91 nominal rates).
    """
    return {
        **_modelo_303_fixture(),
        "02": Decimal("4"),
        "05": Decimal("10"),
        "08": Decimal("21"),
    }


_FIXTURE_FOR_RULESET: tuple[
    tuple[Ruleset, Callable[[], dict[str, Decimal]]],
    ...,
] = (
    (MODELO_100_2024, _modelo_100_full_fixture_2024),
    (MODELO_100_2025, _modelo_100_full_fixture_post_2025),
    (MODELO_100_2026, _modelo_100_full_fixture_post_2025),
    (MODELO_130_2024, _modelo_130_rich_fixture),
    (MODELO_130_2025, _modelo_130_rich_fixture),
    (MODELO_130_2026, _modelo_130_rich_fixture),
    (MODELO_303_2024, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_303_2025, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_303_2026, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_390_2024, _modelo_390_fixture),
    (MODELO_390_2025, _modelo_390_fixture),
    (MODELO_390_2026, _modelo_390_fixture),
)


# Per-path fixture overrides for threshold literals whose detection
# requires a different operand range than the default comprehensive
# fixture. Two pattern families:
#
# 1. **LIRPF art. 20 piecewise constants** (M100 casilla 0021 paths
#    starting (0, 1, 0, ...) for piece_a and (0, 1, 1, ...) for
#    piece_b). With the default comprehensive fixture's high
#    rendimiento (0001 = 200 000), 0020 > 19 747.50 and both pieces
#    clamp to 0 — mutation invisible. Use the targeted piece_a /
#    piece_b fixtures from the sub_op module.
#
# 2. **D simplificada 5 % cap** (M100 casilla 0225 path (0, 1) — the
#    Min upper bound 2000). Default fixture leaves 0220 = 30 000 so
#    0.05 * 30 000 = 1 500 < 2 000; cap NOT binding; mutation
#    invisible. Use the cap-binding variant.
_THRESHOLD_PATH_OVERRIDES: dict[
    tuple[str, str, tuple[int, ...]],
    Callable[[], dict[str, Decimal]],
] = {
    # M100 art. 20 piece_a outer + threshold (paths (0,1,0,0,*) and
    # (0,1,0,0,1,1,0,*)).
    ("modelo_100.2024", "0021", (0, 1, 0, 0, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2024", "0021", (0, 1, 0, 0, 1, 1, 0, 1)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2025", "0021", (0, 1, 0, 0, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2025", "0021", (0, 1, 0, 0, 1, 1, 0, 1)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2026", "0021", (0, 1, 0, 0, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2026", "0021", (0, 1, 0, 0, 1, 1, 0, 1)): _modelo_100_art20_piece_a_fixture,
    # M100 art. 20 piece_b outer + threshold (paths (0,1,1,0,*) and
    # (0,1,1,0,1,1,0,*)).
    ("modelo_100.2024", "0021", (0, 1, 1, 0, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2024", "0021", (0, 1, 1, 0, 1, 1, 0, 1)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2025", "0021", (0, 1, 1, 0, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2025", "0021", (0, 1, 1, 0, 1, 1, 0, 1)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2026", "0021", (0, 1, 1, 0, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2026", "0021", (0, 1, 1, 0, 1, 1, 0, 1)): _modelo_100_art20_piece_b_fixture,
    # M100 casilla 0225 cap upper bound (Min RHS).
    ("modelo_100.2024", "0225", (0, 1)): _modelo_100_d_simplificada_cap_binding_fixture,
    ("modelo_100.2025", "0225", (0, 1)): _modelo_100_d_simplificada_cap_binding_fixture,
    ("modelo_100.2026", "0225", (0, 1)): _modelo_100_d_simplificada_cap_binding_fixture,
    # M390 casilla 193 Literal(0) — needs 191 < 0 to be observable.
    # The default _modelo_390_fixture has 191 > 0 (positive cuota
    # resultante, the "ingresar" scenario); use a "devolver"
    # variant where 190 < 662 so 191 is negative and clamp_pos
    # surfaces the literal.
    ("modelo_390.2024", "193", (0, 0, 0)): _modelo_390_devolver_fixture,
    ("modelo_390.2025", "193", (0, 0, 0)): _modelo_390_devolver_fixture,
    ("modelo_390.2026", "193", (0, 0, 0)): _modelo_390_devolver_fixture,
}


# Catalogue of clamp-mask-dominated literal positions whose mutation
# produces no observable discrepancy because a downstream
# ``clamp_pos`` absorbs the change AND no fixture redesign can flip
# the inner sign. Empty post-Wave-6 closure: the M390 193
# ``Literal(0)`` previously catalogued here was found to be
# observable when 191 < 0 (the legitimate "devolver" scenario); the
# per-path override ``_modelo_390_devolver_fixture`` in
# :data:`_THRESHOLD_PATH_OVERRIDES` covers it.
#
# Sentinel preserved for any future structural-clamp-mask cases that
# genuinely cannot be flipped by fixture redesign. Each entry must
# carry a defensible rationale; a future contributor extending this
# set should justify why a typo of that literal would not corrupt
# any taxpayer's filing under ANY reasonable fixture.
_CLAMP_MASKED_IDENTITY_POSITIONS: dict[tuple[str, str, tuple[int, ...]], str] = {}


def _iter_covered_threshold_targets() -> Iterator[tuple[Ruleset, str, tuple[int, ...], str, Decimal]]:
    """Yield every (ruleset, casilla, leaf_path, parent_op, literal_value) the harness covers.

    Walks each registered ruleset's formulas and yields every
    threshold-literal position EXCEPT:

    - **Additive-identity literals** (``Max(0, X)`` / ``Min(0, X)``)
      — :func:`is_additive_identity_literal` filters these.
    - **Clamp-mask-dominated literals** (catalogued in
      :data:`_CLAMP_MASKED_IDENTITY_POSITIONS`) — a downstream
      ``clamp_pos`` absorbs any ε-shift; the literal is in the AST
      but its value is architecturally invariant.

    Both exclusions are catalogued separately for the aggregator's
    parity columns.
    """
    for ruleset, _fixture_factory in _FIXTURE_FOR_RULESET:
        for fd in ruleset.formulas:
            for leaf_path, literal, parent_op in iter_threshold_literal_paths(fd.formula):
                if is_additive_identity_literal(parent_op, literal.value):
                    continue
                if (ruleset.ruleset_id, fd.casilla_id, leaf_path) in _CLAMP_MASKED_IDENTITY_POSITIONS:
                    continue
                yield ruleset, fd.casilla_id, leaf_path, parent_op, literal.value


def _iter_excluded_identity_targets() -> Iterator[tuple[Ruleset, str, tuple[int, ...], str, Decimal, str]]:
    """Yield every architectural-identity literal — informational catalogue only.

    These positions are deliberately not exercised by the harness.
    The function exists so the kill-rate aggregator can count them
    in a separate ``threshold_literal_identity_excluded`` column for
    catalogue parity, and so a per-position rationale is available
    for review.
    """
    for ruleset, _fixture_factory in _FIXTURE_FOR_RULESET:
        for fd in ruleset.formulas:
            for leaf_path, literal, parent_op in iter_threshold_literal_paths(fd.formula):
                if is_additive_identity_literal(parent_op, literal.value):
                    yield (
                        ruleset,
                        fd.casilla_id,
                        leaf_path,
                        parent_op,
                        literal.value,
                        f"{parent_op}({literal.value}, X) — additive/multiplicative identity",
                    )
                elif (ruleset.ruleset_id, fd.casilla_id, leaf_path) in _CLAMP_MASKED_IDENTITY_POSITIONS:
                    yield (
                        ruleset,
                        fd.casilla_id,
                        leaf_path,
                        parent_op,
                        literal.value,
                        _CLAMP_MASKED_IDENTITY_POSITIONS[(ruleset.ruleset_id, fd.casilla_id, leaf_path)],
                    )


def _build_test_params() -> list:
    """Generate one pytest.param per (ruleset, casilla, leaf_path, direction)."""
    fixture_for_ruleset_id: dict[str, Callable[[], dict[str, Decimal]]] = {
        ruleset.ruleset_id: factory for ruleset, factory in _FIXTURE_FOR_RULESET
    }
    params: list = []
    for ruleset, casilla_id, leaf_path, parent_op, _value in _iter_covered_threshold_targets():
        override = _THRESHOLD_PATH_OVERRIDES.get((ruleset.ruleset_id, casilla_id, leaf_path))
        fixture_factory = override if override is not None else fixture_for_ruleset_id[ruleset.ruleset_id]
        fixture = fixture_factory()
        for direction_id, offset in _DEFAULT_OFFSETS:
            path_id = "_".join(str(p) for p in leaf_path) if leaf_path else "root"
            params.append(
                pytest.param(
                    _ThresholdCase(
                        ruleset=ruleset,
                        casilla_id=casilla_id,
                        leaf_path=leaf_path,
                        parent_op=parent_op,
                        offset=offset,
                        fixture=fixture,
                        direction_id=direction_id,
                    ),
                    id=(f"{ruleset.ruleset_id}:casilla_{casilla_id}:{parent_op}_at_{path_id}:{direction_id}"),
                )
            )
    return params


@pytest.mark.parametrize("case", _build_test_params())
def test_threshold_literal_mutation_is_detected(case: _ThresholdCase) -> None:
    """A ±1 € shift on any threshold literal MUST surface a discrepancy.

    Baseline-clean sentinel first; then the mutated ruleset audits and
    MUST surface a discrepancy on at least one casilla with
    ``|delta| >= 0.02 €``. A failing case points directly at the
    offending ``(ruleset, casilla, leaf_path, parent_op, direction)``
    tuple via the parametrize id.
    """
    engine = Engine()
    baseline = engine.audit_against(ruleset=case.ruleset, provided=case.fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean(), (
        f"baseline must be clean before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )
    mutated = mutate_threshold_literal(
        case.ruleset,
        case.casilla_id,
        case.leaf_path,
        offset=case.offset,
    )
    report = engine.audit_against(ruleset=mutated, provided=case.fixture, tolerance=Decimal("0.01"))
    assert report.discrepancies, (
        f"threshold-literal {case.parent_op} mutation on {case.ruleset.ruleset_id} "
        f"casilla {case.casilla_id} at path {case.leaf_path} ({case.direction_id}) "
        f"was NOT detected"
    )
    max_delta = max(abs(d.delta) for d in report.discrepancies)
    assert max_delta >= Decimal("0.02"), (
        f"threshold-literal {case.parent_op} mutation on {case.ruleset.ruleset_id} "
        f"casilla {case.casilla_id} produced max |delta|={max_delta}, below the "
        f"0.02 € detection floor."
    )


def test_iter_threshold_literal_paths_skips_mul_div_leaves() -> None:
    """Walker MUST NOT yield Mul/Div leaves — those are owned by the scalar harness.

    Modelo 303 casilla 66's body is ``Round(Div(Percent(...), Literal('100')))``.
    The Literal('100') is a direct Div operand and therefore owned by
    :func:`mutate_scalar_leaf` — it must NOT appear in the threshold-
    literal walker's output.
    """
    fd = MODELO_303_2025.formula_for("66")
    assert fd is not None
    threshold_paths = list(iter_threshold_literal_paths(fd.formula))
    # Casilla 66 has zero non-Mul/Div literals — only the Div leaf,
    # which is excluded.
    assert threshold_paths == [], f"expected no threshold literals in M303 casilla 66; got {threshold_paths}"


def test_iter_threshold_literal_paths_skips_percent_rate_position() -> None:
    """Walker MUST NOT yield the rate operand of a PercentFormula.

    The rate is owned by :func:`mutate_percent_literal_rate` (or
    :func:`mutate_parameter_rate` for ParamRef rates). M111 casilla 09
    body is ``Round(ClampPos(Percent(ParamRef('irpf.premios_rate'),
    Ref('08'))))``  — no inline literal rate, so the walker yields
    nothing for that casilla. M303 02/05/08 (printed IVA rates as
    standalone literals under RoundFormula) are NOT in PercentFormula
    rate position; they MUST be yielded.
    """
    fd_303_02 = MODELO_303_2025.formula_for("02")
    assert fd_303_02 is not None
    paths_303_02 = list(iter_threshold_literal_paths(fd_303_02.formula))
    assert len(paths_303_02) == 1, (
        f"expected M303 casilla 02 to expose 1 threshold literal (printed IVA rate 4); got {paths_303_02}"
    )
    _path, literal, parent_op = paths_303_02[0]
    assert literal.value == Decimal("4")
    assert parent_op == "round"


def test_additive_identity_filter_skips_max_zero() -> None:
    """``is_additive_identity_literal`` returns True for ``Max(0, X)`` / ``Min(0, X)`` literals.

    M130 casilla 12's body has a ``Max(Literal(0), inner)`` shape; the
    literal 0 is a clamp_pos-equivalent identity. The filter must
    exclude it from the harness while yielding it for the catalogue.
    """
    assert is_additive_identity_literal("max", Decimal("0"))
    assert is_additive_identity_literal("min", Decimal("0"))
    # Non-zero literals are NOT identities even in max/min positions.
    assert not is_additive_identity_literal("max", Decimal("1"))
    # Non-max/min positions are NOT identities even at zero.
    assert not is_additive_identity_literal("sub", Decimal("0"))
    assert not is_additive_identity_literal("add", Decimal("0"))


def test_mutate_threshold_literal_rejects_non_literal_path() -> None:
    """Targeting a non-Literal path raises ``TypeError``."""
    fd = MODELO_303_2025.formula_for("45")
    assert fd is not None
    # Path () is the RoundFormula root, not a Literal.
    with pytest.raises(TypeError):
        mutate_threshold_literal(
            MODELO_303_2025,
            "45",
            (),
            offset=Decimal("1"),
        )


def test_threshold_literal_coverage_is_non_trivial() -> None:
    """Sanity: the harness covers a non-trivial number of literal positions.

    A regression that drops coverage to zero (e.g. by accidentally
    excluding all parent op slugs) would silently de-arm this
    harness. Asserts the parameter table has > 200 cases (currently
    ~225 = ~115 covered nodes x 2 directions).
    """
    params = _build_test_params()
    assert len(params) >= 200, (
        f"threshold-literal harness coverage suspiciously low: {len(params)} cases. "
        f"A walker regression may have silently disarmed the harness."
    )
