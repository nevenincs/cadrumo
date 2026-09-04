"""One account's balances and movements for an ejercicio, and the set of them.

This is the *sumas y saldos* (trial balance) shape: for each PGC account, what
it carried at the opening, what moved through the debe and the haber during the
period, and what it carries at the close. It is the level at which company
accounting enters this product — not the libro diario — because the Modelo 200
estados contables are transcribed from account balances, and the sanctioned
automated channel into Sociedades WEB carries balance, PyG and ECPN rather than
journal movements.

Every amount here is a **non-negative magnitude**; which side it falls on is
carried by :class:`~cadrumo.domain.contabilidad.direccion.ContabilidadDireccion`.
Accounting software commonly asks the operator to *type* a credit balance as a
negative number, but that is a data-entry convention at the boundary, not a
storage shape: a sign in the number would encode direction twice.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core.decimal.constants import ZERO
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .cuenta import CuentaPgc
from .direccion import ContabilidadDireccion
from .errors import SaldoCuentaBalanceError, SumasYSaldosPreCloseError

#: Cuenta 129 is *Resultado del ejercicio*. It is written by the asiento de
#: cierre, so a trial balance captured for Modelo 200 purposes — which must be
#: taken *before* the close — carries no closing balance on it. A populated 129
#: means the operator exported after closing, and the estados contables derived
#: from it would double-count the result.
_RESULTADO_DEL_EJERCICIO_PREFIX = "129"


class SaldoCuenta(BaseModel):
    """One account's opening balance, period movements, and closing balance.

    The closing balance is not stored as an independent fact: it is checked
    against the opening balance and the movements, so an internally
    inconsistent line is refused rather than silently preferred one way.
    """

    model_config = _STRICT_FROZEN

    cuenta: CuentaPgc
    opening_amount: Decimal = Field(ge=ZERO)
    opening_direccion: ContabilidadDireccion
    debe_amount: Decimal = Field(ge=ZERO)
    haber_amount: Decimal = Field(ge=ZERO)
    closing_amount: Decimal = Field(ge=ZERO)
    closing_direccion: ContabilidadDireccion

    @property
    def signed_opening(self) -> Decimal:
        """The opening balance as a signed quantity, debe positive."""
        return self.opening_amount * self.opening_direccion.sign

    @property
    def signed_closing(self) -> Decimal:
        """The closing balance as a signed quantity, debe positive."""
        return self.closing_amount * self.closing_direccion.sign

    @model_validator(mode="after")
    def _closing_follows_from_opening_and_movements(self) -> SaldoCuenta:
        expected = self.signed_opening + self.debe_amount - self.haber_amount
        if expected != self.signed_closing:
            raise SaldoCuentaBalanceError(
                f"closing balance of {self.cuenta} does not follow from its opening balance and movements"
            )
        return self

    @model_validator(mode="after")
    def _zero_is_not_directional(self) -> SaldoCuenta:
        """A zero balance must not claim a side.

        Zero is neither debe nor haber. Allowing either would make two records
        of the same fact unequal, and would let a caller read a direction that
        carries no information.
        """
        for amount, direccion, label in (
            (self.opening_amount, self.opening_direccion, "opening"),
            (self.closing_amount, self.closing_direccion, "closing"),
        ):
            if amount == ZERO and direccion is not ContabilidadDireccion.DEBE:
                raise SaldoCuentaBalanceError(
                    f"a zero {label} balance must use DEBE as its canonical direction, not {direccion.value}"
                )
        return self


class SumasYSaldos(BaseModel):
    """A whole trial balance for one ejercicio, taken before the close.

    Accounts are unique on their code. The set refuses a populated *resultado
    del ejercicio* closing balance, because a trial balance carrying one was
    taken after the asiento de cierre and cannot be used to derive the estados
    contables.
    """

    model_config = _STRICT_FROZEN

    ejercicio: int
    lineas: tuple[SaldoCuenta, ...]

    @model_validator(mode="after")
    def _accounts_are_unique(self) -> SumasYSaldos:
        codes = [linea.cuenta for linea in self.lineas]
        if len(set(codes)) != len(codes):
            raise SaldoCuentaBalanceError("cuentas must be unique in a trial balance")
        return self

    @model_validator(mode="after")
    def _taken_before_the_close(self) -> SumasYSaldos:
        for linea in self.lineas:
            if linea.cuenta.is_within(_RESULTADO_DEL_EJERCICIO_PREFIX) and linea.closing_amount != ZERO:
                raise SumasYSaldosPreCloseError(
                    f"cuenta {linea.cuenta} carries a closing balance, so this "
                    f"trial balance was taken after the asiento de cierre"
                )
        return self

    @property
    def total_debe(self) -> Decimal:
        """The sum of debe movements, which must equal :attr:`total_haber`."""
        return sum((linea.debe_amount for linea in self.lineas), ZERO)

    @property
    def total_haber(self) -> Decimal:
        """The sum of haber movements, which must equal :attr:`total_debe`."""
        return sum((linea.haber_amount for linea in self.lineas), ZERO)

    @property
    def is_cuadrado(self) -> bool:
        """Whether the trial balance squares — debe totals equal haber totals.

        Reported rather than enforced: an operator importing a partial or
        in-progress balance has an uncuadrado one, and refusing construction
        would leave them unable to see what is wrong. The consumer that needs a
        squared balance asks for it.
        """
        return self.total_debe == self.total_haber
