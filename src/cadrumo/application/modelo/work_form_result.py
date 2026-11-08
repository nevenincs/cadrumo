"""Name the box that settles a declaration, and which way it settles.

The settlement box and its direction are filing-grade claims, so each comes
from a declaration and never from a label, a box number or a bare sign:

* A modelo whose official design declares its "tipo de declaración" code set
  has its result boxes and its sign-to-code rule codified once, in
  :mod:`cadrumo.core.result_disposition`. The direction is read from the code
  that rule derives (``I`` pays, ``D`` refunds, ``C`` carries the credit
  forward, ``B`` is deducted from later instalments of the year, ``N`` is a
  nil or negative return, told apart by the sign), before any payment or
  refund election the filer makes when filing.
* Otherwise the registry's declared final-result ``semantic_role`` names the
  settlement box (Modelo 100 today), and, with no sign rule declared, the
  direction is unknown rather than guessed from the sign.
* A modelo that declares neither, such as an informative return, has no
  settlement box.

A result box that holds no value yet has no direction either.

See Also:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, formulas, bindings and layout metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core.casilla_id import CasillaId
from ...core.period import Period
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.result_casillas import derive_result_disposition
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.filing.schema import ModeloValueKind
from ...domain.iva.refund_eligibility import (
    RedemeEnrolmentState,
    RefundEligibility,
    refund_eligibility_for_period,
)
from .settlement_casilla import declaration_result_casillas
from .work_form_declaration_facts import ModeloFormResult, ModeloFormResultDirection
from .work_review import ModeloWorkReviewCasilla

_DIRECTION_BY_DISPOSITION: Final[Mapping[ResultDisposition, ModeloFormResultDirection]] = {
    ResultDisposition.INGRESO: ModeloFormResultDirection.TO_PAY,
    ResultDisposition.DOMICILIACION: ModeloFormResultDirection.TO_PAY,
    ResultDisposition.CUENTA_CORRIENTE_INGRESO: ModeloFormResultDirection.TO_PAY,
    ResultDisposition.DEVOLUCION: ModeloFormResultDirection.TO_REFUND,
    ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION: ModeloFormResultDirection.TO_REFUND,
    ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO: ModeloFormResultDirection.TO_REFUND,
    ResultDisposition.COMPENSACION: ModeloFormResultDirection.TO_CARRY_FORWARD,
    ResultDisposition.RESULTADO_A_DEDUCIR: ModeloFormResultDirection.TO_DEDUCT_LATER,
    ResultDisposition.NEGATIVA: ModeloFormResultDirection.NIL,
    # A renounced refund is an election, never derived from the result.
    ResultDisposition.RENUNCIA_DEVOLUCION: ModeloFormResultDirection.UNKNOWN,
}
"""The direction each official "tipo de declaración" code states; total over the codes."""

_ELECTABLE_DISPOSITIONS: Final[frozenset[ResultDisposition]] = frozenset({ResultDisposition.COMPENSACION})
"""The codes a refund election at filing can still change: a carried IVA credit may be requested as a refund.

Only the periodic IVA declaration derives ``C`` (every other modelo's closed
code set in :mod:`cadrumo.core.result_disposition` settles a negative result as
``B`` or ``N``), so this is exactly the LIVA art. 115 refund election and the
eligibility gate below is the right one to ask about it.
"""


def _amount(row: ModeloWorkReviewCasilla) -> Decimal | None:
    """The result box's value, or ``None`` while it holds none."""
    if row.realised_kind is ModeloValueKind.EMPTY or isinstance(row.value, bool):
        return None
    if isinstance(row.value, Decimal | int):
        return Decimal(row.value)
    return None


def _declared_type_result(
    modelo: str,
    result_ids: tuple[CasillaId, ...],
    values: Mapping[str, Decimal | None],
    period: Period,
    redeme: RedemeEnrolmentState,
) -> ModeloFormResult | None:
    """The result by the modelo's declared "tipo de declaración" rule, over the result boxes this revision has."""
    if not _has_declared_result_value(result_ids, values):
        return None
    present = result_ids
    known = _known_result_values(present, values)
    settling = _settling_result_casilla(present, known)
    if len(known) != len(present):
        return _unknown_declared_result(settling)
    disposition = derive_result_disposition(modelo, known, period=period)
    value = sum(known.values(), Decimal("0"))
    direction = _declared_result_direction(disposition, value)
    eligibility = _refund_eligibility(disposition, period, redeme)
    return ModeloFormResult(
        casilla_id=settling,
        box=None,
        value=value,
        direction=direction,
        disposition=disposition,
        election_may_change=eligibility is not None and eligibility.refund_allowed,
        refund_eligibility=eligibility,
    )


def _refund_eligibility(
    disposition: ResultDisposition | None, period: Period, redeme: RedemeEnrolmentState
) -> RefundEligibility | None:
    """Whether this result's carried credit may be elected as a refund, or ``None`` when none can be.

    The question only arises for a carried IVA credit; every other code settles
    with no election to make. The answer comes from the shared resolver, so the
    words the form serves and the code the export writes cannot disagree.
    """
    if disposition not in _ELECTABLE_DISPOSITIONS:
        return None
    return refund_eligibility_for_period(period=period, redeme=redeme)


def _has_declared_result_value(result_ids: tuple[CasillaId, ...], values: Mapping[str, Decimal | None]) -> bool:
    return any(casilla_id in values for casilla_id in result_ids)


def _known_result_values(
    result_ids: tuple[CasillaId, ...], values: Mapping[str, Decimal | None]
) -> dict[CasillaId, Decimal]:
    return {casilla_id: amount for casilla_id in result_ids if (amount := values.get(casilla_id)) is not None}


def _settling_result_casilla(result_ids: tuple[CasillaId, ...], known: Mapping[CasillaId, Decimal]) -> CasillaId:
    nonzero = [casilla_id for casilla_id, amount in known.items() if amount != 0]
    return nonzero[0] if len(nonzero) == 1 else result_ids[0]


def _unknown_declared_result(casilla_id: CasillaId) -> ModeloFormResult:
    return ModeloFormResult(casilla_id=casilla_id, box=None, value=None, direction=ModeloFormResultDirection.UNKNOWN)


def _declared_result_direction(disposition: ResultDisposition | None, value: Decimal) -> ModeloFormResultDirection:
    direction = ModeloFormResultDirection.UNKNOWN if disposition is None else _DIRECTION_BY_DISPOSITION[disposition]
    if direction is ModeloFormResultDirection.NIL and value < 0:
        # "Negativa" covers a zero result and a negative one nothing carries; only the sign tells them apart.
        return ModeloFormResultDirection.NEGATIVE
    return direction


def settlement_result(
    modelo: str,
    revision: ModeloRevision,
    rows: Mapping[str, ModeloWorkReviewCasilla],
    period: Period,
    *,
    redeme: RedemeEnrolmentState = RedemeEnrolmentState.UNSTATED,
) -> ModeloFormResult | None:
    """Return the settlement box of ``revision`` with its value and direction in ``period``, or ``None``.

    ``rows`` are the work review's rows by casilla id. The returned ``box`` is
    left for the caller, which knows where the form prints the casilla.

    ``redeme`` is the filer's stated inscription in the Registro de devolución
    mensual, which decides whether a carried IVA credit may be elected as a
    refund outside the year's last period. It defaults to
    :attr:`~cadrumo.domain.iva.refund_eligibility.RedemeEnrolmentState.UNSTATED`
    so a caller that has not read the profile offers only what is certain
    instead of assuming an answer.

    Raises:
        AmbiguousDeclarationResultError: The registry declares two final-result
            casillas for the revision, so it has none.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
    """
    return settlement_result_values(
        modelo, revision, {key: _amount(row) for key, row in rows.items()}, period, redeme=redeme
    )


def settlement_result_values(
    modelo: str,
    revision: ModeloRevision,
    values: Mapping[str, Decimal | None],
    period: Period,
    *,
    redeme: RedemeEnrolmentState = RedemeEnrolmentState.UNSTATED,
) -> ModeloFormResult | None:
    """Read the same settlement contract from already-loaded calculation values.

    Portfolio summaries use this path without building a review or a full form.
    Missing settlement operands remain unknown, including a partially computed
    result split across several declared boxes.

    ``redeme`` carries the same meaning and the same default as in
    :func:`settlement_result`.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
    """
    selected = declaration_result_casillas(modelo, revision)
    if selected is None:
        return None
    if selected.by_declared_type:
        return _declared_type_result(modelo, selected.casilla_ids, values, period, redeme)
    role_casilla = selected.casilla_ids[0]
    if role_casilla not in values:
        return None
    return ModeloFormResult(
        casilla_id=role_casilla,
        box=None,
        value=values[role_casilla],
        direction=ModeloFormResultDirection.UNKNOWN,
    )


__all__ = ["settlement_result", "settlement_result_values"]
