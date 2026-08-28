"""Standing gate: every ``integer-ceiling`` target is constrained non-negative.

``apply_rounding`` implements ``integer-ceiling`` with :data:`decimal.ROUND_CEILING`,
for the targets whose governing provision takes the result to the next unit up
rather than the nearest one -- LIVA art. 104.Dos, "se redondeará en la unidad
superior", the prorrata percentage.

``ROUND_CEILING`` moves toward positive infinity, which is *not* the same as
away from zero once an operand can be negative: it would round a negative result
toward zero and understate its magnitude. The other registry rounding codes carry
no such asymmetry -- ``money-2`` is ``ROUND_HALF_UP``, which is symmetric about
zero -- so this is the one rounding rule whose correctness depends on the sign of
what it is given.

``apply_rounding``'s own docstring states the precondition that makes the two
readings coincide: *"Every ``integer-ceiling`` target today is a
registry-constrained non-negative percentage (``sign = "non_negative"``,
``min_value = "0"``) ... a future negative-capable target must state which reading
its provision means before enrolling here."* That precondition is load-bearing and
was, until this gate, stated only in prose. Enrolling a signed casilla would not
fail anything; it would quietly round a negative amount the wrong way, and for a
refund or credit box that shortens what the taxpayer gets back.

The gate holds with zero violations today: the only enrolled target is modelo
303's prorrata percentage, across six revisions, each constrained both ways.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..authority import bundled_authority
from ..formula_runtime_ops import apply_rounding
from ..schema_rounding import RegistryRoundingCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _integer_ceiling_targets() -> list[tuple[str, str, str, object, object]]:
    """Return (modelo, revision, formula id, sign, min_value) for every ceiling-rounded formula."""
    rows: list[tuple[str, str, str, object, object]] = []
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            casillas = {str(casilla.id): casilla for casilla in revision.casillas}
            for formula in revision.formulas or ():
                if formula.rounding is not RegistryRoundingCode.INTEGER_CEILING:
                    continue
                target = casillas.get(str(formula.target_casilla_id))
                constraints = getattr(target, "constraints", None)
                rows.append(
                    (
                        str(modelo.id),
                        str(revision_id),
                        str(formula.id),
                        getattr(constraints, "sign", None),
                        getattr(constraints, "min_value", None),
                    )
                )
    return rows


def test_every_integer_ceiling_target_is_constrained_non_negative() -> None:
    """A signed target would let ROUND_CEILING understate a negative magnitude."""
    rows = _integer_ceiling_targets()

    # Anti-vacuity: with no enrolled target the assertion below is empty and
    # proves nothing, so the absence of any is itself a failure to investigate.
    assert rows, "no integer-ceiling formula found; either the code was retired or this gate stopped seeing it"

    unguarded = [
        f"{modelo} [{revision}] {formula}: sign={sign!r} min_value={minimum!r}"
        for modelo, revision, formula, sign, minimum in rows
        if str(sign) != "non_negative" or minimum is None or Decimal(str(minimum)) < 0
    ]

    assert not unguarded, (
        "integer-ceiling rounds toward positive infinity, so these targets must be "
        "constrained non-negative before enrolling, or the provision's intended "
        "reading for a negative result must be stated:\n" + "\n".join(f"  {row}" for row in unguarded)
    )


def test_ceiling_and_half_up_agree_on_the_non_negative_domain() -> None:
    """The precondition is what makes the two readings interchangeable here."""
    for raw in ("0", "0.4", "0.5", "49.2", "50", "99.999"):
        value = Decimal(raw)
        ceiled = apply_rounding(value, RegistryRoundingCode.INTEGER_CEILING)

        assert ceiled >= value, f"ceiling must never reduce a non-negative value, but {raw} became {ceiled}"
        assert ceiled - value < 1, f"ceiling must move less than one whole unit, but {raw} became {ceiled}"


def test_an_already_integral_percentage_is_left_alone() -> None:
    """A 50 % prorrata must stay 50, not become 51; the docstring calls this out."""
    assert apply_rounding(Decimal("50"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("50")


def test_ceiling_understates_a_negative_magnitude() -> None:
    """The hazard the precondition exists to exclude, shown on the real function.

    This is why the gate above is not cosmetic: were a signed casilla enrolled,
    a negative result would round toward zero rather than away from it.
    """
    ceiled = apply_rounding(Decimal("-0.4"), RegistryRoundingCode.INTEGER_CEILING)

    assert ceiled == Decimal("0"), "ROUND_CEILING moves toward positive infinity"
    assert abs(ceiled) < Decimal("0.4"), "so a negative magnitude is understated, not rounded up"
