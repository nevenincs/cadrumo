"""Each Modelo 303 recargo cuota lands in the rung whose Tipo % AEAT publishes.

Modelo 303 states each recargo rung's rate as a design CONSTANT in the Tipo %
field beside it, so a cuota in the wrong rung is not merely a bad breakdown: it
is a figure the filed record contradicts arithmetically, checkable by AEAT from
the fichero alone without reference to the ledger behind it.

THE DEFECT THIS PINS. The 0,5 % super-reducido cuota (LIVA art. 161.3) was bound
to casilla 158, the rung whose Tipo [157] is the constant "00175" -- the art.
161.4 TABACO recargo -- while casilla 170, whose Tipo [169] admits "00050", sat
unbound. The declared total was unaffected in the 2023 revision, because both
158 and 170 are already summed by ``modelo-303-iva-cuota-devengada-total``. So
this was a MIS-ALLOCATION across official rungs, not an under-declaration, and
the repair moves a binding without touching a formula.

WHY 170 AND NOT A RE-POINTING OF 158. The design supports it: [169] admits
"00050", and the RDL 4/2024 transitional 0,26 % companion lands in that SAME
rung, so the transitional rates -- which the app does not yet model -- do not
change this destination and are not a precondition for this fix. Casilla 158 is
left operator-input awaiting the tabaco population, which is unmodelled in the
same way Modelo 390's [41]/[42] rung is.

SCOPE, DELIBERATE. Only the late-2024 epoch revision is asserted here. The
2009-2022 revision carries the same wrong binding AND excludes casilla
158 from its own total, which is a different and graver defect -- but that
revision declares casillas 158 and 170 at all, and the bundled 2022 design (the
last year it serves) has only three recargo rungs, [16]/[19]/[22], with neither
158 nor 170 among them. Its boxes are therefore anachronistic and its total is
consistent with its own design, so adding operands there would create an
over-declaration on a return that is currently correct. That half is a
revision-content question, not a binding one, and is tracked separately.

Real-behaviour: the committed revision through the real registry authority. No
mocks, stubs, skips or xfail.

Non-tautology: the expected rung is read from the bundled Diseño de Registros
description text, where the box appears as ``[NN]`` and its rate as a Constante,
never from the registry under test. The mapping is asserted in both directions --
the right casilla carries the binding AND the wrong one does not -- so a change
that bound both would fail.
"""

from __future__ import annotations

import pytest

from .....core.resources import resources
from .. import CasillaDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = "2024-desde-09-y-3t"

# Rung cuota box -> the binding AEAT's published Tipo % constant requires there.
# Read from the bundled 2024-late design: [157] "00175", [20] "00140",
# [23] "00520", [169] "00026"/"00050".
_EXPECTED_BINDING_BY_BOX = {
    "24": "modelo-303-recargo-equivalencia-general-cuota",
    "21": "modelo-303-recargo-equivalencia-reducido-cuota",
    "170": "modelo-303-recargo-equivalencia-super-reducido-cuota",
}

# The rung AEAT reserves for the art. 161.4 tabaco recargo. Its population is not
# modelled, so it must carry no binding at all rather than someone else's.
_TABACO_CUOTA_BOX = "158"


def _revision() -> ModeloRevision:
    return resources().modelos.authority.modelo("303").revisions[_REVISION]


def _casillas_by_number() -> dict[str, CasillaDefinition]:
    return {casilla.number: casilla for casilla in _revision().casillas}


@pytest.mark.parametrize(("box", "binding_id"), sorted(_EXPECTED_BINDING_BY_BOX.items()))
def test_each_recargo_cuota_box_carries_the_binding_its_published_rate_requires(
    box: str,
    binding_id: str,
) -> None:
    """The forward direction: the right rung carries the right cuota."""
    casilla = _casillas_by_number()[box]
    assert str(casilla.binding) == binding_id, (
        f"casilla {box} carries {casilla.binding!r}; AEAT's published Tipo % for that rung requires {binding_id!r}"
    )


def test_the_tabaco_rung_carries_no_binding_at_all() -> None:
    """The reverse direction, and the specific defect this module exists for.

    Asserting only that 170 is bound would still pass if 158 were bound too, and
    the cuota would then be declared twice under two contradictory rates. The
    tabaco population is unmodelled, so its rung must stay operator-input.
    """
    casilla = _casillas_by_number()[_TABACO_CUOTA_BOX]
    assert casilla.binding is None, (
        f"casilla {_TABACO_CUOTA_BOX} is the art. 161.4 tabaco rung (Tipo constant "
        f'"00175") and carries {casilla.binding!r}. A cuota declared there asserts a '
        f"1,75 % rate the filed record contradicts arithmetically."
    )
    assert casilla.input_kind == "manual", (
        f"casilla {_TABACO_CUOTA_BOX} is {casilla.input_kind!r}; an unmodelled "
        f"population must remain operator-input, not a computed or bound blank"
    )


def test_no_recargo_binding_is_declared_on_two_rungs() -> None:
    """One cuota, one rung: a binding on two boxes double-declares the same money.

    Derived from the revision rather than from the table above, so it also covers
    a recargo binding this module does not enumerate.
    """
    seen: dict[str, list[str]] = {}
    for casilla in _revision().casillas:
        if casilla.binding is None or "recargo-equivalencia" not in str(casilla.binding):
            continue
        seen.setdefault(str(casilla.binding), []).append(casilla.number)
    assert seen, "no recargo binding was found on any casilla; the check would be vacuous"
    for binding_id, boxes in seen.items():
        assert len(boxes) == 1, f"{binding_id} is declared on rungs {sorted(boxes)}"


def test_the_super_reducido_cuota_still_reaches_the_declared_total() -> None:
    """The property that makes this a mis-allocation rather than a lost figure.

    Both the old rung and the new one are summed by the annual devengada total,
    which is why the repair needed no formula change. If a later edit removed 170
    from that total, this fix would silently turn into an under-declaration.
    """
    from .. import expression_casilla_refs

    revision = _revision()
    total = next(f for f in revision.formulas if f.id == "modelo-303-iva-cuota-devengada-total")
    operands = {str(ref) for ref in expression_casilla_refs(total.expression)}
    assert operands, "the total formula yielded no operands; the assertion would be vacuous"
    assert "170" in operands, (
        "casilla 170 now carries the super-reducido recargo cuota but is not summed by "
        "modelo-303-iva-cuota-devengada-total, so that money leaves the declared total"
    )
