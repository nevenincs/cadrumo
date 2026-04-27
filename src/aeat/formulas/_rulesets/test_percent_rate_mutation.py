"""Percent-rate mutation harness for every landed ruleset (#338).

Issue #338 — Track 2 / EPIC #316. Extends the mutation harness with
a ``percent_rate`` mutator class. For every :class:`PercentFormula`
node in every landed ruleset variant whose rate operand is mutable
(a :class:`Literal` value or a :class:`ParamRef` resolving via the
:class:`ParameterTable`), the harness:

1. Confirms the unmutated ruleset audits clean against the case's
   fixture (baseline sentinel).
2. Constructs a mutated ruleset with the rate shifted by ±1 pp.
3. Asserts the audit surfaces a discrepancy on at least one casilla
   downstream of the mutated rate, and the ``|delta|`` on that
   casilla is ``≥ 0.02 €`` (the detection floor inherited from the
   wave-67e operand-swap harness).

Rates living in compound expressions (e.g. the
``percent_from_whole`` shape used by Modelo 200 casilla 00562 and
Modelo 202 casilla 18, where the rate is a :class:`DivFormula`
normalising a whole-percent input) are not in scope of this
mutator; the mul/div scalar mutator catches the
``Literal("100")`` denominator. Rates living in :class:`CasillaRef`
operands (e.g. Modelo 303 casilla 66) are not mutable via AST and
appear in the unflagged-nodes catalogue assembled by
``test_mutator_kill_rate``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from .._engine import Engine
from .._formula import PercentFormula
from .._ruleset import Ruleset
from . import (
    MODELO_111_2024,
    MODELO_111_2025,
    MODELO_115_2024,
    MODELO_115_2025,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_130_2026,
    MODELO_131_2024,
    MODELO_131_2025,
    MODELO_180_2024,
    MODELO_180_2025,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
)
from ._mutators import (
    classify_percent_rate,
    iter_percent_nodes,
    mutate_parameter_rate,
    mutate_percent_literal_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


@dataclass(frozen=True)
class _PercentCase:
    """One enumerated mutation case — ruleset, target casilla, fixture, direction."""

    ruleset: Ruleset
    casilla_id: str
    fixture: dict[str, Decimal]
    target_param_id: str | None
    direction_id: str
    rate_delta: Decimal


# -- Per-ruleset fixtures (real ruleset evaluations, no mocks) ----------
#
# Each fixture provides a base value on the casilla feeding the
# PercentFormula's base operand; the rate's ±1 pp shift then produces
# a discrepancy of at least 0.02 € on the casilla that the percent
# computes. Fixtures contain only the inputs needed; missing user
# casillas default to Decimal("0") per the engine's contract.


def _f111_premios_fixture() -> dict[str, Decimal]:
    """Modelo 111 — drives casilla 09 = 19 % * 08 = 19 € on base 100 €.

    A ±1 pp rate shift moves 09 by 1.00 €, well above the 0.02 €
    detection floor. Casilla 28 also shifts (it includes 09); 30
    shifts in turn (= 28 - 29).
    """
    return {
        "08": Decimal("100.00"),
        "11": Decimal("0.00"),
        "29": Decimal("0.00"),
    }


def _f111_arrendamiento_fixture() -> dict[str, Decimal]:
    """Modelo 111 — drives casilla 12 = 19 % * 11 = 19 € on base 100 €."""
    return {
        "08": Decimal("0.00"),
        "11": Decimal("100.00"),
        "29": Decimal("0.00"),
    }


def _f115_fixture() -> dict[str, Decimal]:
    """Modelo 115 — drives casilla 03 = 19 % * 02 = 19 € on base 100 €."""
    return {
        "02": Decimal("100.00"),
        "04": Decimal("0.00"),
        "05": Decimal("0.00"),
    }


def _f130_irpf_fixture() -> dict[str, Decimal]:
    """Modelo 130 — drives casilla 04 = 20 % * 03 = 20 € on net 100 €."""
    return {
        "01": Decimal("100.00"),
        "02": Decimal("0.00"),
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "08": Decimal("0.00"),
        "10": Decimal("0.00"),
        "13": Decimal("0.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "18": Decimal("0.00"),
    }


def _f130_agraria_fixture() -> dict[str, Decimal]:
    """Modelo 130 — drives casilla 09 = 2 % * 08 = 2 € on base 100 €.

    Note: the agraria rate is 2 % so a ±1 pp shift produces a 1.00 €
    delta on casilla 09; that propagates through 11 = 09 - 10 (not
    clamp_pos for casilla 11) to 12 = clamp_pos(07 + 11). Because
    07 = clamp_pos(20% * 0) - 0 - 0 = 0 here, 12 = max(0, 0 + 1.00 €
    after mutation) = 1.00 € (or 3.00 € on +1 pp shift). Either way
    the |delta| on casilla 09 alone is 1.00 €, well above floor.
    """
    return {
        "01": Decimal("0.00"),
        "02": Decimal("0.00"),
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "08": Decimal("100.00"),
        "10": Decimal("0.00"),
        "13": Decimal("0.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "18": Decimal("0.00"),
    }


def _f131_fixture_first() -> dict[str, Decimal]:
    """Modelo 131 — drives casilla 04 = 2 % * 03 = 2 € on base 100 €."""
    return {
        "01": Decimal("0.00"),
        "02": Decimal("0.00"),
        "03": Decimal("100.00"),
        "05": Decimal("0.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "11": Decimal("0.00"),
        "12": Decimal("0.00"),
        "14": Decimal("0.00"),
    }


def _f131_fixture_second() -> dict[str, Decimal]:
    """Modelo 131 — drives casilla 06 = 2 % * 05 = 2 € on base 100 €."""
    return {
        "01": Decimal("0.00"),
        "02": Decimal("0.00"),
        "03": Decimal("0.00"),
        "05": Decimal("100.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "11": Decimal("0.00"),
        "12": Decimal("0.00"),
        "14": Decimal("0.00"),
    }


def _f180_fixture() -> dict[str, Decimal]:
    """Modelo 180 — drives casilla 03 = 19 % * 02 = 19 € on base 100 €.

    Modelo 180's casilla set is {01, 02, 03, 04} — the resumen anual is
    a 4-casilla rollup of Modelo 115's quarterly retentions. Casilla
    01 (perceptores), 02 (base), 04 (ingresos en especie) are inputs;
    03 is computed.
    """
    return {
        "01": Decimal("0.00"),
        "02": Decimal("100.00"),
        "04": Decimal("0.00"),
    }


def _f303_super_fixture() -> dict[str, Decimal]:
    """Modelo 303 — drives casilla 03 = 4 % * 01 = 4 € on base 100 €."""
    return {
        "01": Decimal("100.00"),
        "04": Decimal("0.00"),
        "07": Decimal("0.00"),
        "65": Decimal("100"),
        "67": Decimal("0.00"),
    }


def _f303_reducido_fixture() -> dict[str, Decimal]:
    """Modelo 303 — drives casilla 06 = 10 % * 04 = 10 € on base 100 €."""
    return {
        "01": Decimal("0.00"),
        "04": Decimal("100.00"),
        "07": Decimal("0.00"),
        "65": Decimal("100"),
        "67": Decimal("0.00"),
    }


def _f303_general_fixture() -> dict[str, Decimal]:
    """Modelo 303 — drives casilla 09 = 21 % * 07 = 21 € on base 100 €."""
    return {
        "01": Decimal("0.00"),
        "04": Decimal("0.00"),
        "07": Decimal("100.00"),
        "65": Decimal("100"),
        "67": Decimal("0.00"),
    }


# -- Case-table generation ----------------------------------------------


def _ruleset_cases() -> tuple[tuple[Ruleset, str, dict[str, Decimal]], ...]:
    """Pair every PercentFormula casilla with a fixture exercising its rate.

    Returns ``(ruleset, casilla_id, fixture)`` triples — the harness
    fans out into ``+0.01`` / ``-0.01`` directions per pair, and
    classifies the rate to choose between the literal-rate path and
    the parameter-rate path.
    """
    return (
        # Modelo 111 — 2024 + 2025.
        (MODELO_111_2024, "09", _f111_premios_fixture()),
        (MODELO_111_2024, "12", _f111_arrendamiento_fixture()),
        (MODELO_111_2025, "09", _f111_premios_fixture()),
        (MODELO_111_2025, "12", _f111_arrendamiento_fixture()),
        # Modelo 115 — 2024 + 2025.
        (MODELO_115_2024, "03", _f115_fixture()),
        (MODELO_115_2025, "03", _f115_fixture()),
        # Modelo 130 — 2024 + 2025 + 2026 (issue #321).
        (MODELO_130_2024, "04", _f130_irpf_fixture()),
        (MODELO_130_2024, "09", _f130_agraria_fixture()),
        (MODELO_130_2025, "04", _f130_irpf_fixture()),
        (MODELO_130_2025, "09", _f130_agraria_fixture()),
        (MODELO_130_2026, "04", _f130_irpf_fixture()),
        (MODELO_130_2026, "09", _f130_agraria_fixture()),
        # Modelo 131 — 2024 + 2025.
        (MODELO_131_2024, "04", _f131_fixture_first()),
        (MODELO_131_2024, "06", _f131_fixture_second()),
        (MODELO_131_2025, "04", _f131_fixture_first()),
        (MODELO_131_2025, "06", _f131_fixture_second()),
        # Modelo 180 — 2024 + 2025.
        (MODELO_180_2024, "03", _f180_fixture()),
        (MODELO_180_2025, "03", _f180_fixture()),
        # Modelo 303 — 2024 + 2025 (three rate-bearing casillas each).
        (MODELO_303_2024, "03", _f303_super_fixture()),
        (MODELO_303_2024, "06", _f303_reducido_fixture()),
        (MODELO_303_2024, "09", _f303_general_fixture()),
        (MODELO_303_2025, "03", _f303_super_fixture()),
        (MODELO_303_2025, "06", _f303_reducido_fixture()),
        (MODELO_303_2025, "09", _f303_general_fixture()),
        (MODELO_303_2026, "03", _f303_super_fixture()),
        (MODELO_303_2026, "06", _f303_reducido_fixture()),
        (MODELO_303_2026, "09", _f303_general_fixture()),
    )


def _build_test_params() -> list:
    """Generate one pytest.param per (ruleset * casilla * direction)."""
    params: list = []
    for ruleset, casilla_id, fixture in _ruleset_cases():
        fd = ruleset.formula_for(casilla_id)
        assert fd is not None, f"ruleset {ruleset.ruleset_id} missing formula for casilla {casilla_id}"
        # Find the (single) outermost PercentFormula whose rate is mutable.
        # Per the ADR we mutate one node per casilla; if a casilla had
        # multiple percent rates, this enumeration would pick them all.
        for path, node in iter_percent_nodes(fd.formula):
            location = classify_percent_rate(fd, path, node)
            if location.mode not in ("literal", "param"):
                continue
            for direction_id, rate_delta in (("plus_1pp", Decimal("0.01")), ("minus_1pp", Decimal("-0.01"))):
                params.append(
                    pytest.param(
                        _PercentCase(
                            ruleset=ruleset,
                            casilla_id=casilla_id,
                            fixture=fixture,
                            target_param_id=location.param_id,
                            direction_id=direction_id,
                            rate_delta=rate_delta,
                        ),
                        id=f"{ruleset.ruleset_id}:casilla_{casilla_id}:{location.mode}:{direction_id}",
                    )
                )
    return params


# -- Harness ------------------------------------------------------------


@pytest.mark.parametrize("case", _build_test_params())
def test_percent_rate_mutation_is_detected(case: _PercentCase) -> None:
    """Mutated rate MUST surface a discrepancy on a downstream casilla.

    Baseline sentinel asserts the unmutated ruleset audits clean against
    the fixture; the mutation then either shifts a parameter-table
    rate (when ``target_param_id`` is set) or rewrites a literal-rate
    in place (otherwise).
    """
    engine = Engine()
    fd = case.ruleset.formula_for(case.casilla_id)
    assert fd is not None

    # Baseline derivation: compute the casilla's value WITHOUT a
    # user-side fixture key, so the audit only checks the
    # explicitly-provided inputs. This avoids depending on a
    # pre-computed expected value (the rate-mutator is contract-only).
    baseline_ledger = engine.derive(
        ruleset=case.ruleset,
        inputs={k: v for k, v in case.fixture.items() if not _is_computed(case.ruleset, k)},
    )
    baseline_values = {entry.casilla_id: entry.value for entry in baseline_ledger.entries}

    # Re-audit with the baseline-derived values folded in. This is the
    # baseline-sentinel: derived ledger ≡ user-supplied values ⇒ no
    # discrepancy.
    full_baseline = {**case.fixture, **baseline_values}
    baseline_report = engine.audit_against(
        ruleset=case.ruleset,
        provided=full_baseline,
        tolerance=Decimal("0.01"),
    )
    assert baseline_report.is_clean(), (
        f"baseline audit must be clean before mutation; saw {[d.casilla_id for d in baseline_report.discrepancies]}"
    )

    # Apply mutation.
    if case.target_param_id is not None:
        mutated = mutate_parameter_rate(
            case.ruleset,
            case.target_param_id,
            delta=case.rate_delta,
        )
    else:
        # Locate the percent node + its rate-leaf path in the casilla's
        # formula tree at runtime so the test parametrisation does not
        # have to encode the path explicitly.
        rate_path: tuple[int, ...] | None = None
        for path, node in iter_percent_nodes(fd.formula):
            location = classify_percent_rate(fd, path, node)
            if location.mode == "literal":
                rate_path = (*path, 0)
                break
        assert rate_path is not None, "literal-rate path must exist for literal-mode case"
        mutated = mutate_percent_literal_rate(
            case.ruleset,
            case.casilla_id,
            rate_path,
            delta=case.rate_delta,
        )

    # Audit the mutated ruleset against the same baseline
    # (computed-and-user-supplied) values; a discrepancy must surface.
    mutated_report = engine.audit_against(
        ruleset=mutated,
        provided=full_baseline,
        tolerance=Decimal("0.01"),
    )
    affected = {d.casilla_id for d in mutated_report.discrepancies}
    assert affected, (
        f"percent-rate mutation on {case.ruleset.ruleset_id} casilla "
        f"{case.casilla_id} ({case.direction_id}) was NOT detected — "
        f"audit produced no discrepancies"
    )
    max_delta = max(abs(d.delta) for d in mutated_report.discrepancies)
    assert max_delta >= Decimal("0.02"), (
        f"percent-rate mutation on {case.ruleset.ruleset_id} casilla "
        f"{case.casilla_id} produced max |delta|={max_delta}, below the "
        f"0.02 € detection floor (fixture base may be too small)"
    )


def _is_computed(ruleset: Ruleset, casilla_id: str) -> bool:
    """Return ``True`` if ``casilla_id`` is a computed casilla."""
    return ruleset.casilla(casilla_id).computed


def test_classify_percent_rate_distinguishes_literal_param_and_compound() -> None:
    """Sanity check: classifier returns the documented ``mode`` slugs."""
    # Modelo 111 casilla 09: rate is a ParamRef → ``param``.
    fd = MODELO_111_2025.formula_for("09")
    assert fd is not None
    paths = list(iter_percent_nodes(fd.formula))
    assert len(paths) == 1
    location = classify_percent_rate(fd, paths[0][0], paths[0][1])
    assert location.mode == "param"
    assert location.param_id == "irpf.premios_rate"


def test_iter_percent_nodes_walks_through_round_and_clamp_pos() -> None:
    """Walker reaches a PercentFormula nested under a clamp_pos under a Round."""
    # Modelo 130 casilla 04: ``clamp_pos(percent(param(...), ref(...)))``,
    # wrapped by the ``formula(...)`` helper into a terminal RoundFormula.
    fd = MODELO_130_2025.formula_for("04")
    assert fd is not None
    nodes = list(iter_percent_nodes(fd.formula))
    assert len(nodes) == 1
    path, node = nodes[0]
    assert isinstance(node, PercentFormula)
    # Path: RoundFormula.operands[0] → ClampPositiveFormula.operands[0] → PercentFormula.
    assert path == (0, 0)


def test_classify_percent_rate_handles_compound_rate() -> None:
    """percent_from_whole(ref, ref) → rate is a DivFormula → ``compound`` mode.

    Modelo 200 casilla 00562 uses the compound-rate shape; the
    classifier must surface it as ``compound`` so the harness skips
    it (the mul/div scalar mutator catches the inner ``Literal('100')``).
    """
    from . import MODELO_200_2024

    fd = MODELO_200_2024.formula_for("00562")
    assert fd is not None
    nodes = list(iter_percent_nodes(fd.formula))
    assert len(nodes) == 1
    path, node = nodes[0]
    location = classify_percent_rate(fd, path, node)
    assert location.mode == "compound"


def test_mutate_parameter_rate_rejects_unknown_param() -> None:
    """Harness integrity: mutating an unknown parameter raises LookupError."""
    with pytest.raises(LookupError):
        mutate_parameter_rate(
            MODELO_115_2025,
            "this.parameter.does.not.exist",
            delta=Decimal("0.01"),
        )


def test_mutate_percent_literal_rate_rejects_non_literal_path() -> None:
    """Harness integrity: targeting a non-literal-rate path raises TypeError."""
    fd = MODELO_111_2025.formula_for("09")
    assert fd is not None
    # Path (0, 0) inside the casilla-09 formula points at the ParamRef
    # (rate operand of the PercentFormula). The literal-rate mutator
    # must refuse that target rather than silently succeed.
    with pytest.raises(TypeError):
        mutate_percent_literal_rate(
            MODELO_111_2025,
            "09",
            (0, 0),
            delta=Decimal("0.01"),
        )
