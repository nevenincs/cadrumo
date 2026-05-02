"""Brackets-threshold mutation harness.

The currently landed rulesets expose **zero** in-formula
:class:`BracketsFormula` nodes — the only real-world bracket table is
the Modelo 130 minoración (RIRPF art. 110.3.c), and that lives as the
:func:`aeat.domain.formulas._rulesets.modelo_130_2024.compute_casilla_13_minoracion`
Python helper, not as a
:class:`aeat.domain.formulas._formula.FormulaDefinition` body. The
brackets-threshold mutator is therefore tested against a **synthetic
ruleset** that mirrors the Modelo 130 minoración step function. When a
future ruleset adopts :class:`BracketsFormula` inside a
:class:`FormulaDefinition` body, the mutator inherits the proven
behaviour and the ``test_mutator_exhaustiveness`` defence ensures the
harness extends without silent gaps.

For each non-terminal bracket, a fixture whose probe input lands
within ±5 € of the boundary is supplied. Shifting the boundary by
±1 € must move the input into the neighbouring bracket and so produce
a bracket-value discrepancy on the dependent casilla.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...modelos import LegalCitationSource, ModeloCode
from .._engine import Engine
from .._formula import Bracket, BracketsFormula
from .._ruleset import Ruleset
from ._common import (
    brackets,
    casilla,
    formula,
    make_citation,
    ref,
)
from ._mutators import (
    iter_brackets_nodes,
    mutate_brackets_threshold,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


# -- Synthetic ruleset --------------------------------------------------


_BRACKETS: tuple[Bracket, ...] = (
    Bracket(upper_inclusive=Decimal("9000.00"), value=Decimal("100")),
    Bracket(upper_inclusive=Decimal("10000.00"), value=Decimal("75")),
    Bracket(upper_inclusive=Decimal("11000.00"), value=Decimal("50")),
    Bracket(upper_inclusive=Decimal("12000.00"), value=Decimal("25")),
    Bracket(upper_inclusive=None, value=Decimal("0")),
)


_CITATIONS = (
    make_citation(
        LegalCitationSource.REGLAMENTO,
        "110.3.c",
        "Artículo 110.3.c RD 439/2007 (Reglamento del IRPF) — escala "
        "de minoración del pago fraccionado autónomos. Reproducido "
        "aquí como ruleset sintético del harness de mutación; los "
        "tramos coinciden con la tabla real (umbrales 9 000, 10 000, "
        "11 000, 12 000 €).",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820",
    ),
)


_CASILLAS = (
    casilla(
        casilla_id="01",
        label={
            "es": "Probe (rendimiento neto previo)",
            "en": "Probe (previous-year net income)",
            "hu": "Próbabevallás (előző évi nettó)",
        },
        computed=False,
    ),
    casilla(
        casilla_id="02",
        label={
            "es": "Minoración aplicable",
            "en": "Applicable reduction",
            "hu": "Alkalmazható csökkentés",
        },
        computed=True,
        legal_basis=_CITATIONS,
    ),
)


_FORMULAS = (
    formula(
        casilla_id="02",
        formula_id="synthetic_brackets_338.minoracion",
        body=brackets(ref("01"), steps=_BRACKETS),
    ),
)


SYNTHETIC_BRACKETS_RULESET: Ruleset = Ruleset(
    ruleset_id="synthetic_brackets.338.2025",
    modelo=ModeloCode.MODELO_130,
    effective_from=date(2025, 1, 1),
    effective_to=date(2025, 12, 31),
    casillas=_CASILLAS,
    formulas=_FORMULAS,
    legal_citations=_CITATIONS,
)
"""Synthetic Modelo-130-shaped ruleset wrapping :data:`_BRACKETS` for the harness."""


# -- Test cases ---------------------------------------------------------


def _baseline_minoration(probe: Decimal) -> Decimal:
    """Return the minoration the synthetic ruleset would compute for ``probe``."""
    for bracket in _BRACKETS:
        if bracket.upper_inclusive is None or probe <= bracket.upper_inclusive:
            return bracket.value
    raise RuntimeError("brackets exhausted")


# Each test case shifts a non-terminal bracket by ±1 € and uses a
# probe that straddles that boundary by ≤ 5 €. The probe lands inside
# the lower bracket pre-mutation; the +1 € shift extends the lower
# bracket and so does NOT cross the probe (no discrepancy) — but the
# -1 € shift contracts the lower bracket so the probe slides into the
# upper bracket (discrepancy ≥ 25 € — the smallest tier delta).
#
# Symmetrically for a probe just above the boundary: -1 € does
# nothing, +1 € extends the lower bracket past the probe (discrepancy
# ≥ 25 €).
#
# To keep the contract simple — every mutation MUST produce a
# discrepancy — we mirror the test pairs: each non-terminal bracket
# gets one straddle-from-below probe (paired with -1 € shift) and one
# straddle-from-above probe (paired with +1 € shift).


_BRACKET_CASES = [
    # (bracket_index, probe, delta, expected_discrepancy_value)
    pytest.param(0, Decimal("8999.50"), Decimal("-1"), id="b0_lower_probe_minus_1"),
    pytest.param(0, Decimal("9000.50"), Decimal("1"), id="b0_upper_probe_plus_1"),
    pytest.param(1, Decimal("9999.50"), Decimal("-1"), id="b1_lower_probe_minus_1"),
    pytest.param(1, Decimal("10000.50"), Decimal("1"), id="b1_upper_probe_plus_1"),
    pytest.param(2, Decimal("10999.50"), Decimal("-1"), id="b2_lower_probe_minus_1"),
    pytest.param(2, Decimal("11000.50"), Decimal("1"), id="b2_upper_probe_plus_1"),
    pytest.param(3, Decimal("11999.50"), Decimal("-1"), id="b3_lower_probe_minus_1"),
    pytest.param(3, Decimal("12000.50"), Decimal("1"), id="b3_upper_probe_plus_1"),
]


@pytest.mark.parametrize(("bracket_index", "probe", "delta"), _BRACKET_CASES)
def test_brackets_threshold_shift_is_detected(bracket_index: int, probe: Decimal, delta: Decimal) -> None:
    """A ±1 € shift on a straddled boundary surfaces a per-tier discrepancy."""
    engine = Engine()
    fixture: dict[str, Decimal] = {"01": probe}

    # Compute the baseline value the engine derives for casilla 02
    # under the unmutated ruleset, then fold it into the audit input
    # so the audit-against contract checks 02 on the mutated run.
    expected = _baseline_minoration(probe)
    full_baseline = {**fixture, "02": expected}
    baseline = engine.audit_against(
        ruleset=SYNTHETIC_BRACKETS_RULESET,
        provided=full_baseline,
        tolerance=Decimal("0.01"),
    )
    assert baseline.is_clean(), (
        f"baseline must be clean before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )

    # Locate the BracketsFormula node path for the synthetic ruleset's
    # only formula (RoundFormula → BracketsFormula → path == (0,)).
    fd = SYNTHETIC_BRACKETS_RULESET.formula_for("02")
    assert fd is not None
    paths = list(iter_brackets_nodes(fd.formula))
    assert len(paths) == 1
    brackets_path, _node = paths[0]

    mutated = mutate_brackets_threshold(
        SYNTHETIC_BRACKETS_RULESET,
        "02",
        brackets_path,
        bracket_index,
        delta=delta,
    )
    report = engine.audit_against(
        ruleset=mutated,
        provided=full_baseline,
        tolerance=Decimal("0.01"),
    )
    affected = {d.casilla_id for d in report.discrepancies}
    assert "02" in affected, (
        f"brackets-threshold shift on bracket {bracket_index} (probe={probe}, delta={delta}) was NOT detected"
    )
    target = next(d for d in report.discrepancies if d.casilla_id == "02")
    assert abs(target.delta) >= Decimal("0.02"), (
        f"brackets-threshold shift on bracket {bracket_index} produced "
        f"|delta|={abs(target.delta)}, below the 0.02 € detection floor"
    )
    # The smallest legitimate delta is 25 € (the gap between adjacent
    # tier values in the synthetic ruleset).
    assert abs(target.delta) >= Decimal("25"), (
        f"brackets-threshold shift on bracket {bracket_index} produced "
        f"|delta|={abs(target.delta)}, below the smallest tier-step (25 €)"
    )


def test_mutate_brackets_threshold_rejects_terminal_bracket() -> None:
    """Harness integrity: shifting the terminal sentinel bracket raises."""
    fd = SYNTHETIC_BRACKETS_RULESET.formula_for("02")
    assert fd is not None
    paths = list(iter_brackets_nodes(fd.formula))
    brackets_path, node = paths[0]
    terminal_index = len(node.brackets) - 1
    with pytest.raises(IndexError):
        mutate_brackets_threshold(
            SYNTHETIC_BRACKETS_RULESET,
            "02",
            brackets_path,
            terminal_index,
            delta=Decimal("1"),
        )


def test_mutate_brackets_threshold_returns_a_valid_brackets_formula() -> None:
    """The mutated BracketsFormula passes its own ``_validate_brackets``.

    A ±1 € shift on a 1 000 €-spaced bracket sequence cannot produce a
    non-strictly-ascending tuple, so the validator must accept the
    mutated node — confirming the mutator constructs nodes via the
    public constructor (not ``model_copy``) so validators run.
    """
    fd = SYNTHETIC_BRACKETS_RULESET.formula_for("02")
    assert fd is not None
    paths = list(iter_brackets_nodes(fd.formula))
    brackets_path, _node = paths[0]
    mutated = mutate_brackets_threshold(
        SYNTHETIC_BRACKETS_RULESET,
        "02",
        brackets_path,
        bracket_index=0,
        delta=Decimal("1"),
    )
    new_fd = mutated.formula_for("02")
    assert new_fd is not None
    new_paths = list(iter_brackets_nodes(new_fd.formula))
    new_brackets = new_paths[0][1]
    assert isinstance(new_brackets, BracketsFormula)
    # First bracket boundary should now be 9 001 €.
    assert new_brackets.brackets[0].upper_inclusive == Decimal("9001.00")
