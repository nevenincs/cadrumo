"""Canonical Modelo 303 filed-casilla carry-forward derivation policy.

The value this derives, ``iva.compensacion-disponible-fin-periodo``, is what the
``modelo-303-compensacion-pendiente-anteriores`` binding selects from period
``N-1`` to fill casilla 110 of period ``N``. It is therefore a figure-bearing
cross-period carry: a wrong answer here does not fail, it reappears as a wrong
balance one quarter later with every period looking internally coherent.

Whether the period's negative result was CARRIED (compensación, fichero tipo
``C``) or REFUNDED (devolución, tipo ``D``) changes that value, because a
refunded credit is not carried (RD 1624/1992 art. 30 / Ley 37/1992 art. 116).
That disposition is **not a casilla** -- the Modelo 303 registry models no
devolución box, and the election lives only in the fichero header -- so it
cannot be recovered from ``casilla_values`` and MUST be supplied by the caller.

``refunded`` is deliberately a required argument with no default. A default
would be silently wrong for exactly one population (taxpayers who requested a
refund) in the direction that over-states an available credit, and the two
callers that read AEAT-fetched filings genuinely cannot observe the
disposition -- so the assumption they make must be written down at the call
site rather than inherited from a signature.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ...core.casilla_id import CasillaId, validated_casilla_id
from .carry_forward import derive_303_compensation_available

_ZERO = Decimal("0")


def _casilla_id(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="Modelo 303 compensation derivation casilla constant")


M303_COMPENSATION_AVAILABLE_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")
M303_COMPENSATION_POSTERIOR_CASILLA: CasillaId = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
M303_COMPENSATION_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
M303_COMPENSATION_GENERADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")
M303_COMPENSATION_APLICADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-aplicada-periodo")
"""The applied-in-period casilla of the same chain.

Declared here rather than one layer up because the registry's own binding
validator names it, and the registry cannot reach an application-layer
declaration. A second literal there would drift from this one exactly as the
others did.
"""


@dataclass(frozen=True, slots=True)
class M303CompensationAvailableDerivation:
    """One policy-authoritative available-compensation result from filed casillas.

    ``available`` is the carry the period leaves behind, and ``generated`` is the
    credit the period itself created and carries — the two components of the same
    decomposition, so ``available == posterior + generated`` holds on every
    branch, including a refunded one (where ``generated`` is zero).

    ``generated`` is carried here rather than recomputed by the caller because
    the disposition governs BOTH numbers. A consumer that reads ``available``
    from this derivation and derives the generated credit itself gets the
    refunded case right in one field and wrong in the other, and the two land in
    one :class:`IvaCompensationPeriodState` written by one constructor — so
    nothing downstream can tell which of the pair to believe.
    """

    available: Decimal
    generated: Decimal
    basis: Literal["generated", "resultado", "refunded"]
    operand_refs: tuple[CasillaId, ...]
    operand_values: tuple[Decimal, ...]


def derive_m303_compensation_available_from_casillas(
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    refunded: bool,
) -> M303CompensationAvailableDerivation | None:
    """Derive Modelo 303 available compensation from canonical filed casillas.

    A directly filed generated-credit casilla takes precedence. When it is
    unavailable, the statutory result casilla is converted through the pure
    carry-forward policy. Absence of both inputs leaves the observation unchanged.

    Args:
        casilla_values: The period's filed casilla values.
        refunded: Whether the period's negative result was requested as
            devolución rather than carried forward. Required, never defaulted:
            it is not derivable from ``casilla_values`` (see the module
            docstring), and guessing it over-states the carry for every
            refund-requesting taxpayer. When ``True`` the generated credit is
            excluded from the carry on BOTH bases, leaving the
            posterior-only balance that survives a refund.

    Returns:
        The derivation — the available carry and the generated component that
        produced it — or ``None`` when the inputs are absent.
    """
    posterior = casilla_values.get(M303_COMPENSATION_POSTERIOR_CASILLA)
    if posterior is None:
        return None
    generated = casilla_values.get(M303_COMPENSATION_GENERADA_CASILLA)
    if generated is not None:
        if refunded:
            # A refunded period carries no generated credit, so the directly
            # filed generated casilla is not an operand of the carry at all --
            # and the refs must say so, because they are checked against the
            # registry formula's projection by the callers.
            return M303CompensationAvailableDerivation(
                available=posterior,
                generated=_ZERO,
                # This is not a resultado-derived carry.  The disposition has
                # excluded the period's generated credit, so recording the
                # ordinary fallback basis would make later evidence claim the
                # wrong policy path.
                basis="refunded",
                operand_refs=(),
                operand_values=(),
            )
        return M303CompensationAvailableDerivation(
            available=posterior + generated,
            generated=generated,
            basis="generated",
            operand_refs=(M303_COMPENSATION_POSTERIOR_CASILLA, M303_COMPENSATION_GENERADA_CASILLA),
            operand_values=(posterior, generated),
        )
    resultado = casilla_values.get(M303_COMPENSATION_RESULTADO_CASILLA)
    if resultado is None:
        return None
    available = derive_303_compensation_available(
        posterior=posterior,
        resultado=resultado,
        refunded=refunded,
    )
    return M303CompensationAvailableDerivation(
        available=available,
        # The generated component is read back OUT of the pure policy's answer
        # rather than recomputed from ``resultado`` here. ``max(0, -resultado)``
        # and its refunded zeroing are that policy's rule, and a second copy of
        # it in this module is how the two would drift apart on the next
        # regulatory change to the conversion.
        generated=available - posterior,
        basis="refunded" if refunded else "resultado",
        operand_refs=(),
        operand_values=(),
    )


__all__ = [
    "M303_COMPENSATION_APLICADA_CASILLA",
    "M303_COMPENSATION_AVAILABLE_CASILLA",
    "M303_COMPENSATION_GENERADA_CASILLA",
    "M303_COMPENSATION_POSTERIOR_CASILLA",
    "M303_COMPENSATION_RESULTADO_CASILLA",
    "M303CompensationAvailableDerivation",
    "derive_m303_compensation_available_from_casillas",
]
