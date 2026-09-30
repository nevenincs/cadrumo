"""Name the box that settles a declaration, and which way it settles.

The settlement box and its direction are filing-grade claims, so each comes
from a declaration and never from a label, a box number or a bare sign:

* A modelo whose official design declares its "tipo de declaración" code set
  has its result boxes and its sign-to-code rule codified once, in
  :mod:`cadrumo.core.result_disposition`. The direction is read from the code
  that rule derives (``I`` pays, ``D`` refunds, ``C`` and ``B`` carry the
  credit forward, ``N`` is a nil return), before any payment or refund
  election the filer makes when filing.
* Otherwise the registry's declared final-result ``semantic_role`` names the
  settlement box (Modelo 100 today), and, with no sign rule declared, the
  direction is unknown rather than guessed from the sign.
* A modelo that declares neither, such as an informative return, has no
  settlement box.

A result box that holds no value yet has no direction either.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core.casilla_id import CasillaId
from ...core.result_disposition import (
    ResultDisposition,
    derive_result_disposition,
    result_disposition_casilla_ids,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.filing.schema import ModeloValueKind
from .settlement_casilla import declaration_result_casilla_id
from .work_form_models import ModeloFormResult, ModeloFormResultDirection
from .work_review import ModeloWorkReviewCasilla

_DIRECTION_BY_DISPOSITION: Final[Mapping[ResultDisposition, ModeloFormResultDirection]] = {
    ResultDisposition.INGRESO: ModeloFormResultDirection.TO_PAY,
    ResultDisposition.DOMICILIACION: ModeloFormResultDirection.TO_PAY,
    ResultDisposition.CUENTA_CORRIENTE_INGRESO: ModeloFormResultDirection.TO_PAY,
    ResultDisposition.DEVOLUCION: ModeloFormResultDirection.TO_REFUND,
    ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION: ModeloFormResultDirection.TO_REFUND,
    ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO: ModeloFormResultDirection.TO_REFUND,
    ResultDisposition.COMPENSACION: ModeloFormResultDirection.TO_CARRY_FORWARD,
    ResultDisposition.RESULTADO_A_DEDUCIR: ModeloFormResultDirection.TO_CARRY_FORWARD,
    ResultDisposition.NEGATIVA: ModeloFormResultDirection.NIL,
    # A renounced refund is an election, never derived from the result.
    ResultDisposition.RENUNCIA_DEVOLUCION: ModeloFormResultDirection.UNKNOWN,
}
"""The direction each official "tipo de declaración" code states; total over the codes."""

_ELECTABLE_DISPOSITIONS: Final[frozenset[ResultDisposition]] = frozenset({ResultDisposition.COMPENSACION})
"""The codes a refund election at filing can still change: a carried IVA credit may be requested as a refund."""


def _amount(row: ModeloWorkReviewCasilla) -> Decimal | None:
    """The result box's value, or ``None`` while it holds none."""
    if row.realised_kind is ModeloValueKind.EMPTY or isinstance(row.value, bool):
        return None
    if isinstance(row.value, Decimal | int):
        return Decimal(row.value)
    return None


def _declared_type_result(
    modelo: str, result_ids: tuple[CasillaId, ...], rows: Mapping[str, ModeloWorkReviewCasilla]
) -> ModeloFormResult | None:
    """The result by the modelo's declared "tipo de declaración" rule, over the result boxes this revision has."""
    present = tuple(casilla_id for casilla_id in result_ids if str(casilla_id) in rows)
    if not present:
        return None
    amounts = {casilla_id: _amount(rows[str(casilla_id)]) for casilla_id in present}
    known = {casilla_id: amount for casilla_id, amount in amounts.items() if amount is not None}
    nonzero = [casilla_id for casilla_id, amount in known.items() if amount != 0]
    settling = nonzero[0] if len(nonzero) == 1 else present[0]
    if len(known) != len(present):
        return ModeloFormResult(casilla_id=settling, box=None, value=None, direction=ModeloFormResultDirection.UNKNOWN)
    disposition = derive_result_disposition(modelo, known)
    return ModeloFormResult(
        casilla_id=settling,
        box=None,
        value=sum(known.values(), Decimal("0")),
        direction=ModeloFormResultDirection.UNKNOWN if disposition is None else _DIRECTION_BY_DISPOSITION[disposition],
        disposition=disposition,
        election_may_change=disposition in _ELECTABLE_DISPOSITIONS,
    )


def settlement_result(
    modelo: str, revision: ModeloRevision, rows: Mapping[str, ModeloWorkReviewCasilla]
) -> ModeloFormResult | None:
    """Return the settlement box of ``revision`` with its value and direction, or ``None``.

    ``rows`` are the work review's rows by casilla id. The returned ``box`` is
    left for the caller, which knows where the form prints the casilla.

    Raises:
        AmbiguousDeclarationResultError: The registry declares two final-result
            casillas for the revision, so it has none.
    """
    result_ids = result_disposition_casilla_ids(modelo)
    if result_ids is not None:
        declared = _declared_type_result(modelo, result_ids, rows)
        if declared is not None:
            return declared
    role_casilla = declaration_result_casilla_id(revision)
    if role_casilla is None or str(role_casilla) not in rows:
        return None
    return ModeloFormResult(
        casilla_id=role_casilla,
        box=None,
        value=_amount(rows[str(role_casilla)]),
        direction=ModeloFormResultDirection.UNKNOWN,
    )


__all__ = ["settlement_result"]
