"""Whether the operations a taxpayer states for an ejercicio make Modelo 232 owed.

Orden HFP/816/2017 art. 2 names five grounds, and this module applies them to
the operations, the "none" statement and the turnover stated for one ejercicio.
The amounts, the turnover share and the types that are always specific come in
as :class:`Modelo232Thresholds`, read from the pinned registry by the caller;
nothing here restates them.

The grounds, as the order words them:

* art. 2.1.a, "operaciones realizadas con la misma persona o entidad vinculada
  siempre que el importe de la contraprestación del conjunto de operaciones en
  el período impositivo supere" the threshold. The order excludes no operation
  from this total, so the specific ones count here and again by type under
  art. 2.1.b. The AEAT instructions print the row as "(no operaciones
  específicas)"; that table is guidance, and the order governs where it is
  narrower.
* art. 2.1.b, "operaciones específicas, siempre que el importe conjunto de cada
  una de este tipo de operaciones en el período impositivo supere" the
  threshold: the total of one type over every counterparty.
* art. 2.3, "operaciones del mismo tipo que a su vez utilicen el mismo método de
  valoración, siempre que el importe del conjunto de dichas operaciones en el
  período impositivo sea superior al 50% de la cifra de negocios de la entidad",
  whatever the amount per person. It needs a stated turnover; without one this
  ground is undecided, never not met.
* art. 2.4, the LIS art. 23 intangibles reduction on income from related
  persons, whatever the amount.
* art. 2.5, "operaciones o tenga valores en países o territorios calificados como
  paraísos fiscales independientemente de su importe".

Art. 2.2 removes operations from the related-party information. An operation
that states an exclusion is left out of every total and counted apart.

Income and payment operations add up in one total. The order tests "el conjunto
de operaciones" and the instructions forbid netting income against payments
("sin que puedan efectuarse compensaciones entre ellas"). The instructions do not
say whether the thresholds are also tested per direction; this module does not
test them that way.

The finding carries counts and amounts only. It never carries a tax identifier
or a name.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .m232_related_party import (
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
)

__all__ = [
    "Modelo232Basis",
    "Modelo232Ground",
    "Modelo232GroundFinding",
    "Modelo232GroundState",
    "Modelo232Obligation",
    "Modelo232ObligationFinding",
    "Modelo232Thresholds",
    "assess_modelo_232_obligation",
]


class Modelo232Ground(StrEnum):
    """One ground of Orden HFP/816/2017 art. 2."""

    SAME_RELATED_PARTY = "same_related_party"
    """Art. 2.1.a: the operations with one related person or entity."""
    SPECIFIC_OPERATION_TYPE = "specific_operation_type"
    """Art. 2.1.b: the specific operations of one type."""
    TURNOVER_SHARE = "turnover_share"
    """Art. 2.3: operations of one type and valuation method against the turnover."""
    INTANGIBLES_REDUCTION = "intangibles_reduction"
    """Art. 2.4: the LIS art. 23 reduction on income from related persons."""
    TAX_HAVEN = "tax_haven"
    """Art. 2.5: operations or securities in a tax haven."""


class Modelo232GroundState(StrEnum):
    """What the stated facts show about one ground."""

    MET = "met"
    NOT_MET = "not_met"
    UNDECIDED = "undecided"


class Modelo232Basis(StrEnum):
    """What the taxpayer stated for the ejercicio."""

    NOTHING_STATED = "nothing_stated"
    NONE_STATED = "none_stated"
    OPERATIONS_STATED = "operations_stated"
    CONTRADICTION = "contradiction"
    """A "none" statement and an operation both stand, which the write path forbids."""


class Modelo232Obligation(StrEnum):
    """Whether Modelo 232 is owed for the ejercicio."""

    OWED = "owed"
    NOT_OWED = "not_owed"
    UNDECIDED = "undecided"


@dataclass(frozen=True, slots=True)
class Modelo232Thresholds:
    """The registry values the grounds are applied with, for one ejercicio."""

    same_related_party_eur: Decimal
    specific_operations_eur: Decimal
    turnover_share: Decimal
    always_specific_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class Modelo232GroundFinding:
    """What one ground shows: its state, the largest total tested and the limit it is tested against."""

    ground: Modelo232Ground
    state: Modelo232GroundState
    largest_total_eur: Decimal | None = None
    limit_eur: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Modelo232ObligationFinding:
    """The outcome for one ejercicio and the counts and amounts behind it."""

    ejercicio: int
    basis: Modelo232Basis
    grounds: tuple[Modelo232GroundFinding, ...]
    counted_operations: int
    excluded_operations: int
    excluded_total_eur: Decimal
    turnover_eur: Decimal | None
    turnover_source: Modelo232TurnoverSource | None

    @property
    def obligation(self) -> Modelo232Obligation:
        """Return owed when a ground is met, not owed when stated facts meet none, else undecided."""
        if any(ground.state is Modelo232GroundState.MET for ground in self.grounds):
            return Modelo232Obligation.OWED
        if self.basis is Modelo232Basis.NONE_STATED:
            return Modelo232Obligation.NOT_OWED
        if self.basis is Modelo232Basis.OPERATIONS_STATED and all(
            ground.state is Modelo232GroundState.NOT_MET for ground in self.grounds
        ):
            return Modelo232Obligation.NOT_OWED
        return Modelo232Obligation.UNDECIDED


def _largest(totals: dict[object, Decimal]) -> Decimal:
    return max(totals.values(), default=Decimal(0))


def _same_party_ground(counted: list[Modelo232Operation], thresholds: Modelo232Thresholds) -> Modelo232GroundFinding:
    totals: dict[object, Decimal] = defaultdict(Decimal)
    for operation in counted:
        totals[operation.counterparty_tax_id] += operation.amount_eur
    largest = _largest(totals)
    state = Modelo232GroundState.MET if largest > thresholds.same_related_party_eur else Modelo232GroundState.NOT_MET
    return Modelo232GroundFinding(Modelo232Ground.SAME_RELATED_PARTY, state, largest, thresholds.same_related_party_eur)


def _specific_type_ground(counted: list[Modelo232Operation], thresholds: Modelo232Thresholds) -> Modelo232GroundFinding:
    totals: dict[object, Decimal] = defaultdict(Decimal)
    for operation in counted:
        if _specific(operation, thresholds):
            totals[operation.tipo_operacion] += operation.amount_eur
    largest = _largest(totals)
    state = Modelo232GroundState.MET if largest > thresholds.specific_operations_eur else Modelo232GroundState.NOT_MET
    return Modelo232GroundFinding(
        Modelo232Ground.SPECIFIC_OPERATION_TYPE, state, largest, thresholds.specific_operations_eur
    )


def _turnover_ground(
    counted: list[Modelo232Operation],
    thresholds: Modelo232Thresholds,
    turnover: Modelo232TurnoverStatement | None,
) -> Modelo232GroundFinding:
    totals: dict[object, Decimal] = defaultdict(Decimal)
    for operation in counted:
        totals[(operation.tipo_operacion, operation.valuation_method)] += operation.amount_eur
    largest = _largest(totals)
    if turnover is None:
        # A positive total could exceed the share of a small enough turnover, so the ground is
        # undecided; with nothing above zero to compare it cannot be met whatever the turnover.
        state = Modelo232GroundState.UNDECIDED if largest > 0 else Modelo232GroundState.NOT_MET
        return Modelo232GroundFinding(Modelo232Ground.TURNOVER_SHARE, state, largest, None)
    limit = thresholds.turnover_share * turnover.turnover_eur
    state = Modelo232GroundState.MET if largest > limit else Modelo232GroundState.NOT_MET
    return Modelo232GroundFinding(Modelo232Ground.TURNOVER_SHARE, state, largest, limit)


def _specific(operation: Modelo232Operation, thresholds: Modelo232Thresholds) -> bool:
    return operation.specific_operation or operation.tipo_operacion in thresholds.always_specific_types


def _kind_ground(
    ground: Modelo232Ground, operations: list[Modelo232Operation], kinds: frozenset[Modelo232OperationKind]
) -> Modelo232GroundFinding:
    held = [operation for operation in operations if operation.operation_kind in kinds]
    state = Modelo232GroundState.MET if held else Modelo232GroundState.NOT_MET
    return Modelo232GroundFinding(ground, state, sum((o.amount_eur for o in held), Decimal(0)) if held else None)


def assess_modelo_232_obligation(
    ejercicio: int,
    *,
    operations: tuple[Modelo232Operation, ...],
    nones: tuple[Modelo232NoneStatement, ...],
    turnovers: tuple[Modelo232TurnoverStatement, ...],
    thresholds: Modelo232Thresholds,
) -> Modelo232ObligationFinding:
    """Apply the art. 2 grounds to what the taxpayer stated for ``ejercicio``.

    Withdrawn payloads and payloads of another ejercicio are ignored. A "none"
    statement beside an active operation is reported as a contradiction and
    decides nothing.
    """
    active = [operation for operation in operations if operation.active and operation.ejercicio == ejercicio]
    none_stated = any(statement.active and statement.ejercicio == ejercicio for statement in nones)
    active_turnovers = [item for item in turnovers if item.active and item.ejercicio == ejercicio]
    # The write path allows one standing turnover; more than one would make the share ambiguous.
    turnover = active_turnovers[0] if len(active_turnovers) == 1 else None
    counted = [operation for operation in active if not operation.excluded]
    excluded = [operation for operation in active if operation.excluded]
    if none_stated and active:
        basis = Modelo232Basis.CONTRADICTION
    elif none_stated:
        basis = Modelo232Basis.NONE_STATED
    elif active:
        basis = Modelo232Basis.OPERATIONS_STATED
    else:
        basis = Modelo232Basis.NOTHING_STATED
    grounds: tuple[Modelo232GroundFinding, ...] = ()
    if basis is Modelo232Basis.OPERATIONS_STATED:
        related = [o for o in counted if o.operation_kind is Modelo232OperationKind.RELATED_PARTY]
        grounds = (
            _same_party_ground(related, thresholds),
            _specific_type_ground(related, thresholds),
            _turnover_ground(related, thresholds, turnover),
            _kind_ground(
                Modelo232Ground.INTANGIBLES_REDUCTION,
                counted,
                frozenset({Modelo232OperationKind.INTANGIBLES_REDUCTION}),
            ),
            _kind_ground(
                Modelo232Ground.TAX_HAVEN,
                counted,
                frozenset({Modelo232OperationKind.TAX_HAVEN_OPERATION, Modelo232OperationKind.TAX_HAVEN_HOLDING}),
            ),
        )
    return Modelo232ObligationFinding(
        ejercicio=ejercicio,
        basis=basis,
        grounds=grounds,
        counted_operations=len(counted),
        excluded_operations=len(excluded),
        excluded_total_eur=sum((o.amount_eur for o in excluded), Decimal(0)),
        turnover_eur=None if turnover is None else turnover.turnover_eur,
        turnover_source=None if turnover is None else turnover.source,
    )
