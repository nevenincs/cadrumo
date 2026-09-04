"""Corrections to the resultado contable, and the shape each kind may carry.

A Modelo 200 filing does not tax the accounting result directly: it applies
*correcciones al resultado de la cuenta de pérdidas y ganancias* — ajustes
extracontables — to reach the base imponible. Each correction increases
(aumento) or decreases (disminución) the result, and is either **permanente**
or **temporaria**.

The distinction is not a label; it decides which fields exist. The AEAT Manual
práctico, on the página 20 bis desglose, states that for a permanent correction
*"No podrá cumplimentarse la columna que recoge los saldos pendientes a
principio y a fin de ejercicio ya que al tratarse de un ajuste extracontable
permanente no existe saldo pendiente pues el ajuste no podrá ser objeto de
reversión en ejercicios siguientes."* A permanent correction therefore has no
pending balance at all — not a zero one.

That is why the pending fields below are ``None`` rather than ``Decimal("0")``
on a permanent correction: absent-because-forbidden and present-and-zero are
different states, and collapsing them would let a reversal be recorded against
a correction that can never reverse.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .errors import AjusteExtracontableShapeError

_ZERO = Decimal("0")


class AjusteDireccion(StrEnum):
    """Whether a correction raises or lowers the resultado contable.

    Attributes:
        AUMENTO: Increases the result, and so the base imponible.
        DISMINUCION: Decreases the result, and so the base imponible.
    """

    AUMENTO = "aumento"
    DISMINUCION = "disminucion"


class AjusteClase(StrEnum):
    """Whether a correction can reverse in a later period.

    Attributes:
        PERMANENTE: Never reverses. Carries no pending balance.
        TEMPORARIA: Reverses in a later period, so it carries a pending
            balance at the opening and close of each ejercicio until it does.
    """

    PERMANENTE = "permanente"
    TEMPORARIA = "temporaria"


class AjusteExtracontable(BaseModel):
    """One correction to the resultado contable for one ejercicio.

    ``origen_ejercicio_amount`` is the part arising in this period and
    ``origen_anterior_amount`` the part arising from earlier ones; the cuadro
    keeps them apart because only the second can be a reversal.

    The pending balances are ``None`` on a permanent correction and required on
    a temporaria. Neither state is expressible for the other kind.
    """

    model_config = _STRICT_FROZEN

    clase: AjusteClase
    direccion: AjusteDireccion
    origen_ejercicio_amount: Decimal = Field(default=_ZERO, ge=_ZERO)
    origen_anterior_amount: Decimal = Field(default=_ZERO, ge=_ZERO)
    pendiente_inicio_amount: Decimal | None = Field(default=None, ge=_ZERO)
    pendiente_fin_amount: Decimal | None = Field(default=None, ge=_ZERO)

    @property
    def period_amount(self) -> Decimal:
        """The correction applied in this period, from either origin."""
        return self.origen_ejercicio_amount + self.origen_anterior_amount

    @property
    def carries_pending_balance(self) -> bool:
        """Whether this correction can reverse, and so tracks a balance."""
        return self.clase is AjusteClase.TEMPORARIA

    @model_validator(mode="after")
    def _pending_shape_follows_the_clase(self) -> AjusteExtracontable:
        has_pending = (
            self.pendiente_inicio_amount is not None
            or self.pendiente_fin_amount is not None
        )
        if self.clase is AjusteClase.PERMANENTE:
            if has_pending:
                raise AjusteExtracontableShapeError(
                    "a permanent correction cannot carry a pending balance: it "
                    "never reverses, so the balance does not exist rather than "
                    "being zero"
                )
            if self.origen_anterior_amount != _ZERO:
                raise AjusteExtracontableShapeError(
                    "a permanent correction cannot arise from an earlier "
                    "ejercicio: it has no balance to carry forward"
                )
            return self
        if (
            self.pendiente_inicio_amount is None
            or self.pendiente_fin_amount is None
        ):
            raise AjusteExtracontableShapeError(
                "a temporary correction must state both pending balances, "
                "using Decimal('0') where the balance is genuinely nil"
            )
        return self

    @model_validator(mode="after")
    def _reversal_does_not_exceed_the_opening_balance(self) -> AjusteExtracontable:
        if self.pendiente_inicio_amount is None:
            return self
        if self.origen_anterior_amount > self.pendiente_inicio_amount:
            raise AjusteExtracontableShapeError(
                "a correction arising from earlier ejercicios cannot exceed the "
                "pending balance it reverses"
            )
        return self
