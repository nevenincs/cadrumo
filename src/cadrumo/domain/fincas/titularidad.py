"""Per-property titularidad: who declares the property's income, and in what proportion.

The rental engine computes whole-property figures — gross rent, LIRPF
art. 23.1 deductible gastos, the art. 23.1.f amortización, the art. 23.2
reducción and the art. 85 imputación. None of those are what a
contribuyente declares unless the contribuyente holds the whole property
in pleno dominio. This module carries the facts that turn a
whole-property figure into the share attributable to one contribuyente.

Authority
---------
*Manual práctico de Renta 2025*, Parte 1:

* Capítulo 4, "Individualización de los rendimientos del capital
  inmobiliario" (págs. 292-293), citing Art. 11.3 Ley IRPF. Rendimientos
  belong to "las personas que sean titulares de los bienes inmuebles, o
  de los derechos reales sobre los mismos". Where a usufruct exists,
  "el rendimiento íntegro debe declararlo el usufructuario y no el nudo
  propietario". Where titularidad is shared, each cotitular declares
  "la cantidad que resulte de aplicar al rendimiento total producido por
  el inmueble o derecho el porcentaje que represente su participación en
  la titularidad del mismo".
* Capítulo 10, "Individualización de las rentas inmobiliarias" (pág. 805).
  The same proportional rule governs the art. 85 imputación, and the
  usufruct rule is stated with its consequence spelled out: the renta is
  imputed to the titular del derecho "en la misma cuantía que la que
  correspondería al propietario, sin que este último deba incluir
  cantidad alguna en su declaración en concepto de imputación de rentas
  inmobiliarias".
* Capítulo 4, "Declaración bienes inmuebles — Datos particulares de cada
  inmueble" (pág. 295). The declaration carries three per-property facts:
  the contribuyente titular in casilla [0062], the porcentaje de
  propiedad in casilla [0063] and the porcentaje de usufructo in casilla
  [0064], the two percentages "expresad[o]s en números enteros con dos
  decimales".

Both regimes therefore attribute to the holder of the *derecho de
disfrute*, not to the holder of bare title, and both do so in proportion
to that holder's participation. A nudo propietario declares neither the
rendimiento nor the imputación, however large the porcentaje de
propiedad recorded in casilla [0063]. That asymmetry is the reason this
module models a regime alongside the two percentages: the percentages
alone cannot distinguish full ownership from bare ownership, and the
difference between them is the whole figure.

What is deliberately not supported
----------------------------------
A contribuyente may hold pleno dominio over part of a property and the
usufructo over the rest — Capítulo 4, "Gastos deducibles" (pág. 281),
"Plena propiedad y usufructo sobre un inmueble". The manual states that
in that case "el gasto por amortización se calculará de forma diferente
para la parte del inmueble del que es pleno propietario y la parte del
que es usufructuario", the usufructo part amortising over the cost and
duration of the usufruct rather than at the art. 23.1.f 3 % rate. The
rental register carries no acquisition cost or duration for a usufruct,
so that split cannot be computed here. The combination is representable
as :attr:`TitularidadRegime.PLENO_DOMINIO_Y_USUFRUCTO` and refused at
the aggregation boundary rather than approximated.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.text_bounds import PositiveCount
from .enums import TitularContribuyente, TitularidadRegime
from .errors import FincaValidationError

#: Upper bound for casilla [0063] and casilla [0064], and for their sum.
_FULL_PERCENTAGE = Decimal("100")

#: Casillas [0063] and [0064] are declared "en números enteros con dos
#: decimales", so a share carrying more precision than that is not a
#: declarable value and is refused rather than rounded into one.
_DECLARED_PERCENTAGE_EXPONENT = -2

#: Regimes whose attribution derives from the porcentaje de propiedad
#: (casilla [0063]) and therefore require it to be positive.
_PROPIEDAD_REGIMES = frozenset({TitularidadRegime.PLENO_DOMINIO, TitularidadRegime.NUDA_PROPIEDAD})


class Titularidad(BaseModel):
    """One contribuyente's title over one finca, for one ejercicio.

    The record is a per-property fact, matching the manual's
    "Datos particulares de cada inmueble" block: casilla [0062] carries
    the member of the unidad familiar who holds the title, and casillas
    [0063] and [0064] carry that holder's two percentages. No taxpayer
    identity is modelled — casilla [0062] is a closed role vocabulary
    ("Común", "Primer declarante", "Cónyuge", "Hijo 1º" …), not a name
    or a NIF.

    Attributes:
        regime: Which right the contribuyente holds, and therefore
            which percentage governs attribution. See
            :class:`TitularidadRegime`.
        contribuyente: Casilla [0062] — the member of the unidad
            familiar holding the title. ``None`` only when the regime is
            :attr:`TitularidadRegime.NO_DECLARADA`.
        hijo_ordinal: The ordinal in "Hijo 1º", "Hijo 2º" … Required
            when :attr:`contribuyente` is
            :attr:`TitularContribuyente.HIJO`, forbidden otherwise.
        porcentaje_propiedad: Casilla [0063], as a percentage in
            ``[0, 100]`` with at most two decimals.
        porcentaje_usufructo: Casilla [0064], on the same scale.
    """

    model_config = _STRICT_FROZEN

    regime: TitularidadRegime
    contribuyente: TitularContribuyente | None = None
    hijo_ordinal: PositiveCount | None = None
    porcentaje_propiedad: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), le=_FULL_PERCENTAGE)
    porcentaje_usufructo: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), le=_FULL_PERCENTAGE)

    @model_validator(mode="after")
    def _validate_declared_shares(self) -> Titularidad:
        self._reject_undeclarable_precision()
        self._reject_incoherent_total()
        self._reject_regime_mismatch()
        self._reject_contribuyente_mismatch()
        return self

    def _reject_undeclarable_precision(self) -> None:
        for casilla, value in (
            ("[0063]", self.porcentaje_propiedad),
            ("[0064]", self.porcentaje_usufructo),
        ):
            if value.as_tuple().exponent < _DECLARED_PERCENTAGE_EXPONENT:
                raise FincaValidationError(
                    f"casilla {casilla} is declared with at most two decimals; "
                    f"{value} carries more precision than the declaration accepts",
                )

    def _reject_incoherent_total(self) -> None:
        total = self.porcentaje_propiedad + self.porcentaje_usufructo
        if total > _FULL_PERCENTAGE:
            raise FincaValidationError(
                "porcentaje de propiedad [0063] plus porcentaje de usufructo [0064] "
                f"must not exceed 100; declared {self.porcentaje_propiedad} + "
                f"{self.porcentaje_usufructo} = {total}",
            )

    def _reject_regime_mismatch(self) -> None:
        has_propiedad = self.porcentaje_propiedad > Decimal("0")
        has_usufructo = self.porcentaje_usufructo > Decimal("0")
        if self.regime is TitularidadRegime.NO_DECLARADA:
            if has_propiedad or has_usufructo:
                raise FincaValidationError(
                    "regime NO_DECLARADA declares no title, so casillas [0063] and [0064] must both be zero",
                )
            return
        if self.regime in _PROPIEDAD_REGIMES and not (has_propiedad and not has_usufructo):
            raise FincaValidationError(
                f"regime {self.regime.value} attributes through casilla [0063], which must be "
                "positive, while casilla [0064] must be zero",
            )
        if self.regime is TitularidadRegime.USUFRUCTO and not (has_usufructo and not has_propiedad):
            raise FincaValidationError(
                "regime USUFRUCTO attributes through casilla [0064], which must be "
                "positive, while casilla [0063] must be zero",
            )
        if self.regime is TitularidadRegime.PLENO_DOMINIO_Y_USUFRUCTO and not (has_propiedad and has_usufructo):
            raise FincaValidationError(
                "regime PLENO_DOMINIO_Y_USUFRUCTO records both rights, so casillas "
                "[0063] and [0064] must both be positive",
            )

    def _reject_contribuyente_mismatch(self) -> None:
        declared = self.regime is not TitularidadRegime.NO_DECLARADA
        if declared and self.contribuyente is None:
            raise FincaValidationError(
                f"regime {self.regime.value} requires the titular in casilla [0062]",
            )
        if not declared and self.contribuyente is not None:
            raise FincaValidationError(
                "regime NO_DECLARADA declares no title, so casilla [0062] must be empty",
            )
        is_hijo = self.contribuyente is TitularContribuyente.HIJO
        if is_hijo and self.hijo_ordinal is None:
            raise FincaValidationError(
                'casilla [0062] "Hijo" requires the ordinal that distinguishes "Hijo 1º" from "Hijo 2º"',
            )
        if not is_hijo and self.hijo_ordinal is not None:
            raise FincaValidationError(
                'hijo_ordinal applies only to casilla [0062] "Hijo"',
            )

    @property
    def is_filing_grade(self) -> bool:
        """Return whether this titularidad can attribute a filing-grade share.

        ``False`` for :attr:`TitularidadRegime.NO_DECLARADA` (the facts
        were never declared) and for
        :attr:`TitularidadRegime.PLENO_DOMINIO_Y_USUFRUCTO` (the facts
        are declared but the amortización rule the manual prescribes for
        the usufructo part is not modelled here). The two are distinct
        states and :attr:`refusal_reason` reports which one applies.
        """
        return self.refusal_reason is None

    @property
    def refusal_reason(self) -> str | None:
        """Return why this titularidad cannot attribute, or ``None`` when it can."""
        if self.regime is TitularidadRegime.NO_DECLARADA:
            return (
                "titularidad was never declared: casilla [0062] (titular), casilla [0063] "
                "(porcentaje de propiedad) and casilla [0064] (porcentaje de usufructo) are all absent, "
                "and an absent share is not a declaration of sole full ownership"
            )
        if self.regime is TitularidadRegime.PLENO_DOMINIO_Y_USUFRUCTO:
            return (
                "titularidad combines pleno dominio over part of the finca with usufructo over the "
                "rest; the amortización for the usufructo part derives from the cost and duration of "
                "the usufruct rather than from the art. 23.1.f rate, and the rental register carries "
                "neither, so no attributed total is produced"
            )
        return None

    def attribution_share(self) -> Decimal:
        """Return the fraction of the whole-property figures this contribuyente declares.

        Returns:
            A :class:`~decimal.Decimal` in ``[0, 1]``: the porcentaje de
            propiedad for pleno dominio, the porcentaje de usufructo for
            a usufructo, and exactly zero for nuda propiedad, because
            the nudo propietario declares neither the rendimiento nor
            the art. 85 imputación.

        Raises:
            FincaValidationError: When the titularidad is not
                filing-grade. The message names which of the two
                non-filing-grade states applies.
        """
        reason = self.refusal_reason
        if reason is not None:
            raise FincaValidationError(reason)
        if self.regime is TitularidadRegime.NUDA_PROPIEDAD:
            return Decimal("0")
        percentage = (
            self.porcentaje_usufructo if self.regime is TitularidadRegime.USUFRUCTO else self.porcentaje_propiedad
        )
        return percentage / _FULL_PERCENTAGE


def not_declared() -> Titularidad:
    """Return the explicit "titularidad not declared" state.

    Named rather than defaulted: a :class:`~domain.fincas.models.Finca`
    must state its titularidad, and stating that it is unknown is a
    different act from forgetting to state it at all.
    """
    return Titularidad(regime=TitularidadRegime.NO_DECLARADA)


__all__ = [
    "Titularidad",
    "not_declared",
]
