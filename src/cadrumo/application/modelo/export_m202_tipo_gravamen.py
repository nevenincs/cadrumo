"""Derive the Modelo 202 "tipo de gravamen del ejercicio en curso" from the governed Impuesto sobre Sociedades rates.

Page 01 of every Modelo 202 record design consigns the rates the entity applies
in the período impositivo in progress (2025 design position 132, An15, Nota 10
lists "21/22", "20/25" and the like; 2019 and 2023 designs position 127, An5).
The rates are law, never an operator's choice: LIS art. 29 sets them and the
Modelo 200 edition for the período's ejercicio publishes them as parameters, the
same ones its ``modelo-200-tipo-gravamen-por-forma-juridica`` formula reads.

The régimen the stated profile marks describe selects the lane, in the order
LIS art. 29 gives precedence:

- Ley 49/2002 entities apply their own special rate.
- An entity in its first two profit-making períodos applies the new-entity rate
  (art. 29.1, second paragraph), unless a lower one applies.
- Otherwise a microempresa, whose INCN of the período impositivo inmediato
  anterior is below the governed threshold, applies the art. 29.1 scale (one
  rate, or one per tranche); a reducida dimensión entity applying its specific
  rate applies that one; any other entity the general rate.
- A cooperativa fiscalmente protegida applies its protected rate to its
  cooperative results and the lane above to the rest, so it consigns both.

A lane the ejercicio's edition does not publish did not exist in that law: before
Ley 31/2022 there was no microempresa scale and an art. 101 entity applied the
general rate, so the 2022 edition publishes neither lane. Such a lane is absent
for that edition, never projected from a later one, and the entity falls to the
lane that remains. Régimes whose rates the registry does not publish (SOCIMI,
tonnage regime), an ejercicio whose Modelo 200 edition publishes none of the
rates every edition carries, and a cooperativa on a multi-tranche scale (the
design lists no such combination) refuse terminally.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.authority_grade import RegistryAuthorityGrade
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.schema_formula import BracketEntry, DatedValue, ParameterDefinition
from ..filing.export_refusal_doors import ExportRefusalReason, export_design_terminal
from ..filing.producer_snapshot import FilingProducerSnapshotError

_RATES_MODELO: Final = "200"
_ANNUAL_PERIOD: Final = "0A"

GENERAL: Final = "is.modelo-200.tipo-gravamen-general"
NEW_ENTITY: Final = "is.modelo-200.tipo-gravamen-new-entity-first-2-years"
COOPERATIVE_PROTECTED: Final = "is.modelo-200.tipo-gravamen-cooperative-protected"
NON_PROFIT: Final = "is.modelo-200.tipo-gravamen-non-profit-special-regime"
ERD_ART_101: Final = "is.modelo-200.tipo-gravamen-erd-art101"
MICROEMPRESA_SCALE: Final = "is.modelo-200.tipo-gravamen-pyme"
MICROEMPRESA_THRESHOLD: Final = "is.modelo-200.incn-umbral-microempresa"

_REQUIRED_PARAMETERS: Final = (
    GENERAL,
    NEW_ENTITY,
    COOPERATIVE_PROTECTED,
    NON_PROFIT,
)

_HUNDRED: Final = Decimal(100)
_RATE_SEPARATOR: Final = "/"
_TIPO_GRAVAMEN_FACT: Final = "tipo_gravamen_impuesto_sociedades"
_PRODUCER_FACT_REQUIRED_MESSAGE: Final = "application.filing.export.errors.producer_fact_required"


@dataclass(frozen=True, slots=True)
class RegimenMarks:
    """The stated régimen marks that select the lane of LIS art. 29 an entity's rates come from."""

    ley_49_2002: bool
    socimi: bool
    navieras_tonelaje: bool
    new_entity_first_two_profit_periods: bool
    erd_tipo_especifico: bool
    cooperativa_protegida: bool


@dataclass(frozen=True, slots=True)
class GovernedRates:
    """The Impuesto sobre Sociedades rate parameters published for one período impositivo.

    ``on`` is the first day of the período: LIS rates are those of the período
    impositivo, and the registry dates them on the filing-period axis by the
    período's start.
    """

    on: date
    parameters: Mapping[str, ParameterDefinition]

    def microempresa_threshold(self) -> Decimal | None:
        """The INCN below which an entity is a microempresa (LIS art. 29.1); None when the edition has no lane."""
        if MICROEMPRESA_THRESHOLD not in self.parameters or MICROEMPRESA_SCALE not in self.parameters:
            return None
        return _nearest_value(self.parameters[MICROEMPRESA_THRESHOLD], self.on).value

    def publishes(self, parameter_id: str) -> bool:
        """Whether the edition publishes the lane at all."""
        return parameter_id in self.parameters

    def rate(self, parameter_id: str) -> Decimal:
        """One scalar rate, in percent."""
        return _nearest_value(self.parameters[parameter_id], self.on).value

    def microempresa_scale(self) -> tuple[Decimal, ...]:
        """The microempresa scale's rates, one per tranche from the lowest base, in percent."""
        rows = sorted(_nearest_brackets(self.parameters[MICROEMPRESA_SCALE], self.on), key=lambda row: row.lower_bound)
        return _distinct_in_order(row.marginal_rate * _HUNDRED for row in rows)


def governed_rates(*, periodo_start: date, operation: PinnedAuthorityOperation) -> GovernedRates:
    """Read the rate parameters the Modelo 200 edition for the período's ejercicio publishes.

    Raises:
        FilingProducerSnapshotError: The ejercicio has no Modelo 200 edition, or
            its edition publishes no rates; nothing the filer states repairs it.
    """
    try:
        snapshot = operation.snapshot(
            _RATES_MODELO,
            filing_year=periodo_start.year,
            period=_ANNUAL_PERIOD,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
    except RegistrySnapshotError as exc:
        raise _unsupported("the ejercicio of the período impositivo has no Modelo 200 edition") from exc
    published = {parameter.id: parameter for parameter in snapshot.revision.parameters}
    missing = [parameter_id for parameter_id in _REQUIRED_PARAMETERS if parameter_id not in published]
    if missing:
        raise _unsupported(f"the Modelo 200 edition publishes no {', '.join(missing)}")
    return GovernedRates(on=periodo_start, parameters=published)


def tipo_gravamen_rates(*, marks: RegimenMarks, microempresa: bool, rates: GovernedRates) -> tuple[Decimal, ...]:
    """Return the rates, in percent and consigning order, the entity applies in the período.

    Raises:
        FilingProducerSnapshotError: The régimen's rates are not published, or
            the combination is one the design gives no consignment for.
    """
    if marks.ley_49_2002:
        return (rates.rate(NON_PROFIT),)
    if marks.socimi or marks.navieras_tonelaje:
        raise _unsupported("the registry publishes no rate for the SOCIMI or tonnage régimen")
    if marks.new_entity_first_two_profit_periods:
        return (rates.rate(NEW_ENTITY),)
    base = _base_lane(marks=marks, microempresa=microempresa, rates=rates)
    if not marks.cooperativa_protegida:
        return base
    if len(base) > 1:
        raise _unsupported("a cooperativa fiscalmente protegida on a multi-tranche scale has no consignment")
    return _distinct_in_order((rates.rate(COOPERATIVE_PROTECTED), *base))


def several_rates_beyond_own_keys(*, rates: Sequence[Decimal], marks: RegimenMarks, microempresa: bool) -> bool:
    """Whether the entity is one of the "otras entidades con posibilidad de aplicar más de un tipo impositivo".

    The cooperativa and the microempresa each have their own key, so only more
    than one rate those keys do not already explain sets this mark.
    """
    return len(rates) > 1 and not marks.cooperativa_protegida and not microempresa


def consigned_rates(rates: Sequence[Decimal]) -> str:
    """The design's consignment: each rate as two digits, joined with "/" (Nota 10: "00", "21/22", "20/25").

    Raises:
        FilingProducerSnapshotError: A published rate is not a whole percentage
            the design can consign.
    """
    if any(rate != rate.to_integral_value() or not 0 <= rate < _HUNDRED for rate in rates):
        raise _unsupported("a published rate is not a whole percentage the design consigns")
    return _RATE_SEPARATOR.join(f"{int(rate):02d}" for rate in rates)


def _base_lane(*, marks: RegimenMarks, microempresa: bool, rates: GovernedRates) -> tuple[Decimal, ...]:
    if microempresa:
        return rates.microempresa_scale()
    if marks.erd_tipo_especifico and rates.publishes(ERD_ART_101):
        return (rates.rate(ERD_ART_101),)
    return (rates.rate(GENERAL),)


def _nearest_value(parameter: ParameterDefinition, on: date) -> DatedValue:
    """The dated value in force on ``on``, else the nearest published one (a rate always resolves)."""
    covering = [value for value in parameter.values if _covers(value.valid_from, value.valid_to, on)]
    if len(covering) == 1:
        return covering[0]
    if covering or not parameter.values:
        raise _unsupported(f"parameter {parameter.id} has no single value for the período")
    return min(parameter.values, key=lambda value: _distance(value.valid_from, value.valid_to, on))


def _nearest_brackets(parameter: ParameterDefinition, on: date) -> tuple[BracketEntry, ...]:
    """The bracket rows in force on ``on``, else those of the nearest published window."""
    covering = tuple(row for row in parameter.brackets if _covers(row.valid_from, row.valid_to, on))
    if covering:
        return covering
    if not parameter.brackets:
        raise _unsupported(f"parameter {parameter.id} has no scale for the período")
    nearest = min(parameter.brackets, key=lambda row: _distance(row.valid_from, row.valid_to, on))
    return tuple(row for row in parameter.brackets if row.valid_from == nearest.valid_from)


def _covers(valid_from: date, valid_to: date | None, on: date) -> bool:
    return valid_from <= on and (valid_to is None or on <= valid_to)


def _distance(valid_from: date, valid_to: date | None, on: date) -> int:
    if on < valid_from:
        return (valid_from - on).days
    return (on - valid_to).days if valid_to is not None else 0


def _distinct_in_order(rates: Iterable[Decimal]) -> tuple[Decimal, ...]:
    distinct: list[Decimal] = []
    for rate in rates:
        if rate not in distinct:
            distinct.append(rate)
    return tuple(distinct)


def _unsupported(detail: str) -> FilingProducerSnapshotError:
    return FilingProducerSnapshotError(
        f"the Modelo 202 tipo de gravamen cannot be derived: {detail}",
        translated_message=_PRODUCER_FACT_REQUIRED_MESSAGE,
        context={"fact": _TIPO_GRAVAMEN_FACT},
        precondition_verdict=export_design_terminal(ExportRefusalReason.PRODUCER_FACT_UNSUPPLIED),
    )


__all__ = [
    "GovernedRates",
    "RegimenMarks",
    "consigned_rates",
    "governed_rates",
    "several_rates_beyond_own_keys",
    "tipo_gravamen_rates",
]
