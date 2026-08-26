"""Calculate-time advisory when an operator casilla input replaces a computed one.

The bucket aggregation merge lets an operator-supplied casilla value win over a
value the source resolvers computed for the same casilla. That precedence is
intended: the operator holds facts the engine does not -- the provisional
prorrata percentage of LIVA art. 105.Uno lives in the profile register, not in
the ledger -- so the computed figure is a default, not an authority.

What was missing is the disclosure. The override happened in silence, and every
casilla it can reach is written into a filed return, so an operator could file a
figure differing from the one the engine derived without either value ever being
shown beside the other.

The condition is exact rather than heuristic, because both maps are in hand at
the merge: signal only where the casilla appears in BOTH and the two values
differ. A casilla the engine never computed is not an override, and an operator
value equal to the computed one is not a divergence; neither raises anything.

Deliberately direction-agnostic. On a regularizacion neither a higher nor a
lower operator figure is presumptively the error, and this codebase's screens
already watch the under-declaration direction far more closely than the over-
declaration one -- so a screen that fired in only one direction would inherit
that blind spot rather than close it.

See Also:
    :mod:`application.modelo._rate_box_advisory`
        The sibling advisory this one mirrors in shape and wiring.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import CasillaId
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.schema import ModeloRevision
from ..aggregation import CalculationSourceDiagnostic

__all__ = ["collect_operator_override_divergence_diagnostics"]

#: Not a :class:`BindingSourceKind`. The override arrives on the operator's own
#: input channel rather than from any registry binding source, so the token is
#: deliberately non-canonical and ``binding_source`` stays ``None``.
_OPERATOR_INPUT_SOURCE_KIND = "operator_casilla_input"


def collect_operator_override_divergence_diagnostics(
    revision: ModeloRevision,
    *,
    casilla_inputs: Mapping[CasillaId, Decimal],
    bound_inputs: Mapping[CasillaId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one advisory per casilla where an operator value replaced a computed one.

    Args:
        revision: The :class:`ModeloRevision` being calculated, read only to
            name the casilla's official box number in the message.
        casilla_inputs: The operator-supplied casilla values, as passed to the
            calculation.
        bound_inputs: The values the source resolvers computed for bound
            casillas, before the operator merge.

    Returns:
        Tuple of non-blocking
        :class:`~application.aggregation.CalculationSourceDiagnostic` rows, each
        naming the casilla and BOTH values, sorted by casilla id. Empty when no
        operator value diverges from a computed one.
    """
    casillas = casillas_by_id(revision)
    diagnostics: list[CalculationSourceDiagnostic] = []
    for casilla_id in sorted(casilla_inputs.keys() & bound_inputs.keys()):
        computed = bound_inputs[casilla_id]
        supplied = casilla_inputs[casilla_id]
        if computed == supplied:
            continue
        casilla = casillas.get(casilla_id)
        box = f" (box {casilla.number})" if casilla is not None and casilla.number != casilla_id else ""
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="operator_override_diverges_from_computed",
                source_kind=_OPERATOR_INPUT_SOURCE_KIND,
                message=(
                    f"Casilla {casilla_id!r}{box} was filed with the value you supplied "
                    f"({supplied}), not the {computed} this calculation derived. Your value "
                    f"wins by design, because you may hold facts the calculation cannot see. "
                    f"The derived figure was discarded"
                ),
                remedy=(
                    "Confirm the supplied value is the one you intend to file; to file the "
                    "derived figure instead, recalculate without setting this casilla."
                ),
                casilla_id=casilla_id,
            ),
        )
    return tuple(diagnostics)
