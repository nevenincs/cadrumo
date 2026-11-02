"""Match source filings and fold their values for canonical relation requirements.

The registry-declared source casillas, periods and aggregation determine the
values supplied to relation prefill and previous-filing binding resolution.

See Also:
    :mod:`domain.calculations.registry.relations`
        Registry requirements describing the source-filing folds.
    :mod:`domain.calculations.registry.bindings_previous_filing`
        Previous-filing binding resolver that reuses :func:`fold_sum_or_copy`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final, NamedTuple

from ....core.aggregation import RelationAggregationOp
from ....core.casilla_id import CasillaId
from ....core.period import Period
from ...modelos.filing_kind_evidence import (
    UNKNOWN_FILING_KIND,
    ComplementariaOnlySourceOutcome,
    ObservedFilingKind,
    complementaria_only_source_outcome,
)
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .bindings import RegistryModeloObservation
    from .relations import RegistryFoldRequirement
    from .schema import ModeloRevision


@dataclass(frozen=True, slots=True)
class SourceFilingKindEvidence:
    """What the fold may know about one matched source filing beyond its casillas.

    ``filing_kind`` is the observed declaration's kind with its evidence basis;
    ``complementaria_only_casilla_ids`` are the casillas the source filing's own
    registry revision declares only a complementaria fills. Both come from
    outside the calculation-only observation, so the caller supplies them.
    """

    filing_kind: ObservedFilingKind
    complementaria_only_casilla_ids: frozenset[CasillaId]


UNKNOWN_SOURCE_FILING_KIND: Final[SourceFilingKindEvidence] = SourceFilingKindEvidence(
    filing_kind=UNKNOWN_FILING_KIND,
    complementaria_only_casilla_ids=frozenset(),
)
"""The evidence assumed for a matched filing the caller supplied none for."""

type SourceFilingKindIndex = Mapping[tuple[str, int, str], SourceFilingKindEvidence]
"""Source filing-kind evidence keyed by ``(modelo, filing_year, period)``."""


class GatheredRequirementValues(NamedTuple):
    """The per-period source values of one requirement and the casillas proven zero.

    ``proven_zero`` names each ``(period, casilla)`` that was absent from its
    filing and folded as zero because the filing is an admitted original and the
    casilla is declared complementaria-only.
    """

    values: tuple[tuple[Decimal, ...], ...]
    proven_zero: tuple[tuple[str, CasillaId], ...]


def complementaria_only_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the casillas ``revision`` declares only a complementaria fills."""
    return frozenset(casilla.id for casilla in revision.casillas if casilla.complementaria_only is not None)


def _gather_period_values(
    requirement: RegistryFoldRequirement,
    source_period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    evidence: SourceFilingKindEvidence,
    proven_zero: list[tuple[str, CasillaId]],
) -> list[Decimal]:
    """Return one matched filing's source-casilla values, recording casillas proven zero."""
    period_values: list[Decimal] = []
    for source_casilla_id in requirement.source_casilla_ids:
        value = casilla_values.get(source_casilla_id)
        outcome = complementaria_only_source_outcome(
            source_casilla_id,
            observed_value=value,
            filing_kind=evidence.filing_kind,
            complementaria_only_casilla_ids=evidence.complementaria_only_casilla_ids,
        )
        if outcome is ComplementariaOnlySourceOutcome.CONTRADICTED:
            raise RegistryValidationError(
                f"relation requirement {_requirement_ids(requirement)!r} reads complementaria-only casilla "
                f"{source_casilla_id!r} = {value} from "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}, whose filing kind "
                f"is original on basis {evidence.filing_kind.basis.value!r}",
            )
        if outcome is ComplementariaOnlySourceOutcome.PROVEN_ZERO:
            proven_zero.append((source_period, source_casilla_id))
            value = Decimal("0")
        if value is None:
            raise RegistryValidationError(
                f"relation requirement {_requirement_ids(requirement)!r} requires observed source casilla id "
                f"{source_casilla_id!r} from "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}",
            )
        period_values.append(value)
    return period_values


def gather_observed_requirement_values(
    requirement: RegistryFoldRequirement,
    observations: tuple[RegistryModeloObservation, ...],
    *,
    source_filing_kinds: SourceFilingKindIndex | None = None,
) -> GatheredRequirementValues:
    """Return the source-casilla values matched for one fold requirement, per period.

    Matches exactly one
    :class:`~domain.calculations.registry.bindings.RegistryModeloObservation` per
    declared source period and extracts every one of the requirement's source
    :class:`~core.casilla_id.CasillaId` values from it. The returned values carry
    one entry per ``requirement.periods`` entry, in declaration order; each entry
    holds the period's values in ``requirement.source_casilla_ids`` order, ready
    for :func:`fold_observed_requirement_values`.

    A matched filing that lacks a declared source casilla is refused, so the
    requirement stays unresolved rather than reading the missing value as zero,
    unless :func:`~domain.modelos.filing_kind_evidence.complementaria_only_source_outcome`
    proves it zero from ``source_filing_kinds``. A filing with no entry there has
    an unknown kind. An admitted original carrying a nonzero complementaria-only
    value is refused as contradictory.
    """
    no_kinds: dict[tuple[str, int, str], SourceFilingKindEvidence] = {}
    kinds: SourceFilingKindIndex = no_kinds if source_filing_kinds is None else source_filing_kinds
    per_period: list[tuple[Decimal, ...]] = []
    proven_zero: list[tuple[str, CasillaId]] = []
    for source_period in _filed_cadence_periods(requirement, observations):
        matches = tuple(
            observation
            for observation in observations
            if observation.modelo == requirement.source_modelo
            and observation.filing_year == requirement.filing_year
            and observation.period == source_period
        )
        if len(matches) != 1:
            raise RegistryValidationError(
                f"relation requirement {_requirement_ids(requirement)!r} expected one observed filing "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}, found {len(matches)}",
            )
        casilla_values = matches[0].casilla_values
        evidence = kinds.get(
            (requirement.source_modelo, requirement.filing_year, source_period),
            UNKNOWN_SOURCE_FILING_KIND,
        )
        period_values = _gather_period_values(
            requirement,
            source_period,
            casilla_values,
            evidence,
            proven_zero,
        )
        per_period.append(tuple(period_values))
    return GatheredRequirementValues(values=tuple(per_period), proven_zero=tuple(proven_zero))


def _filed_cadence_periods(
    requirement: RegistryFoldRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> tuple[str, ...]:
    """Return the declared periods of the one cadence the source was filed under.

    A source modelo may be declared over alternative cadences -- Modelo 111 is
    filed quarterly or, by a large company, monthly (RIRPF art. 108) -- and a
    filer files one of them for the year, never both. When the declared periods
    span more than one cadence, exactly one cadence must be completely observed;
    none or several leave the requirement unresolved rather than folding a mix.
    A single-cadence declaration is returned unchanged.
    """
    groups: dict[str, list[str]] = {}
    for source_period in requirement.periods:
        kind = Period.from_year_and_code(requirement.filing_year, source_period).kind
        groups.setdefault(str(kind), []).append(source_period)
    if len(groups) < 2:
        return requirement.periods

    def observed(source_period: str) -> bool:
        return any(
            observation.modelo == requirement.source_modelo
            and observation.filing_year == requirement.filing_year
            and observation.period == source_period
            for observation in observations
        )

    filed = [tuple(periods) for periods in groups.values() if all(observed(period) for period in periods)]
    if len(filed) != 1:
        raise RegistryValidationError(
            f"relation requirement {_requirement_ids(requirement)!r} needs exactly one completely filed cadence of "
            f"{requirement.source_modelo!r}/{requirement.filing_year}; found {len(filed)}",
        )
    return filed[0]


def fold_sum_or_copy(
    op: str,
    values: tuple[Decimal, ...] | list[Decimal],
    *,
    subject: str,
    copy_unit: str,
) -> Decimal:
    """Fold a value sequence through the shared ``sum`` / ``copy`` arithmetic.

    The one place ``sum`` (add every value) and ``copy`` (require exactly one
    value and return it) are implemented. ``subject`` and ``copy_unit`` carry the
    caller's diagnostic vocabulary so a refused copy names the right entity
    (a relation requirement's observation, or a binding's source casilla). An op
    that is neither ``sum`` nor ``copy`` is rejected; callers handle any other op
    (e.g. the Modelo 130 ``prior_pagos_fraccionados`` identity) before delegating.

    Used by both :func:`fold_observed_requirement_values` and
    :func:`domain.calculations.registry.bindings_previous_filing.resolve_previous_filing_binding_values`.
    """
    if op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(f"{subject} copy aggregation requires one {copy_unit}")
        return values[0]
    if op == "sum":
        return sum(values, Decimal("0"))
    raise RegistryValidationError(f"{subject} uses unsupported aggregation op {op!r}")


def fold_observed_requirement_values(
    requirement: RegistryFoldRequirement,
    values: tuple[tuple[Decimal, ...], ...],
) -> Decimal:
    """Fold per-period source values through a requirement's declared op.

    ``copy`` requires exactly one gathered period and returns its value; ``sum``
    adds the gathered values; ``pagos_fraccionados_ingresados`` applies
    :func:`fold_pagos_fraccionados_ingresados`. This is the one fold both
    relation paths apply to a
    :class:`~domain.calculations.registry.relations.RegistryFoldRequirement`; the
    period match is :func:`gather_observed_requirement_values`.
    """
    aggregation_op = requirement.aggregation_op
    # Every relation-derived requirement declares its aggregation op; only the
    # unrelated same-modelo previous_filing producer leaves it unset, and this
    # fold is the one both RELATION paths apply, per the docstring above.
    if aggregation_op is None:
        raise RegistryValidationError(
            f"relation requirement {_requirement_ids(requirement)!r} declares no aggregation op to fold with",
        )
    subject = f"relation requirement {_requirement_ids(requirement)!r}"
    if aggregation_op is RelationAggregationOp.PAGOS_FRACCIONADOS_INGRESADOS:
        return fold_pagos_fraccionados_ingresados(values, subject=subject)
    return fold_sum_or_copy(
        aggregation_op.value,
        tuple(_single_value(period_values, subject=subject) for period_values in values),
        subject=subject,
        copy_unit="observation",
    )


def fold_pagos_fraccionados_ingresados(
    values: tuple[tuple[Decimal, ...], ...],
    *,
    subject: str,
) -> Decimal:
    """Sum what pago-fraccionado autoliquidaciones actually paid over their periods.

    Each entry is one period's effective (latest) autoliquidación as the pair
    ``(resultado, resultado a ingresar de las anteriores)``. The AEAT Modelo 130
    and 131 instructions set the period's result as its liquidación minus what
    earlier autoliquidaciones of the same period already resulted a ingresar (zero
    when none did); a positive result is paid, while a negative one is not paid
    and may instead be deducted in a later period of the same ejercicio. So the
    amount paid for a period is the earlier paid result plus the positive part of
    the current one, and those amounts add across periods. A negative result
    contributes nothing here; its later deduction already lowers the result of
    the period that applies it.
    """
    zero = Decimal("0")
    total = zero
    for period_values in values:
        if len(period_values) != 2:
            raise RegistryValidationError(
                f"{subject} pagos_fraccionados_ingresados aggregation requires the result casilla and the "
                f"previously paid result casilla per period; got {len(period_values)} values",
            )
        resultado, resultado_anteriores = period_values
        total += resultado_anteriores + max(resultado, zero)
    return total


def _single_value(period_values: tuple[Decimal, ...], *, subject: str) -> Decimal:
    if len(period_values) != 1:
        raise RegistryValidationError(f"{subject} folds one source casilla per period; got {len(period_values)}")
    return period_values[0]


def _requirement_ids(requirement: RegistryFoldRequirement) -> tuple[str, ...]:
    """Return the binding ids carried by either kind of fold requirement."""
    return requirement.target_bindings or requirement.binding_ids
