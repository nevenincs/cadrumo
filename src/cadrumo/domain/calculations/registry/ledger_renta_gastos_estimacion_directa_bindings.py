"""Canonical Renta estimacion directa ledger-gastos binding family."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel

from ....core.aggregation import (
    BindingAggregationOp,
    BindingSourceKind,
)
from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from ._ledger_binding_resolution import (
    resolve_ledger_family_binding_values,
    unsupported_ledger_family_observations,
)
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .ids import BindingId
from .ledger_binding_selector_support import casilla_id_set
from .schema import DataBindingDefinition, ModeloRevision

# SpendingCategory routing table.
_RENTA_100_FIRST_SLICE_CASILLAS: frozenset[CasillaId] = casilla_id_set(
    "_RENTA_100_FIRST_SLICE_CASILLAS",
    "0183",
    "0186",
    "0191",
    "0192",
    "0193",
    "0194",
    "0195",
    "0199",
    "0200",
    "0202",
    "0203",
    "0206",
    "0208",
    "0217",
)


class RentaGastosEstimacionDirectaObservationProtocol(Protocol):
    """Structural protocol for first-slice Renta estimación directa gastos observations.

    The registry only needs these four attributes to resolve
    ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings; the full
    :class:`~cadrumo.domain.renta.RentaDeductibleExpenseObservation` satisfies
    this protocol without any explicit declaration.

    Properties are declared read-only so that Literal-typed concrete attributes
    (e.g. ``modelo: Literal[Modelo.M100]``) satisfy the protocol under strict
    covariant checking.
    """

    @property
    def modelo(self) -> str:
        """Return the Modelo series associated with the gasto observation."""
        ...

    @property
    def period(self) -> str:
        """Return the filing period associated with the gasto observation."""
        ...

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the declaration casilla receiving the deductible amount."""
        ...

    @property
    def deductible_amount(self) -> Decimal:
        """Return the deductible amount carried by the observation."""
        ...


class _RentaLedgerGastosEstimacionDirectaSelector(BaseModel):
    """Validated form of a ledger_renta_gastos_estimacion_directa_aggregation binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: Literal[Modelo.M100] = Modelo.M100
    period: Literal["0A"] = "0A"
    target_casilla_id: CasillaId
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_gastos_estimacion_directa_selector(
    binding: DataBindingDefinition,
) -> _RentaLedgerGastosEstimacionDirectaSelector:
    try:
        return _RentaLedgerGastosEstimacionDirectaSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_gastos_estimacion_directa_aggregation selector: {exc}",
        ) from exc


def validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_renta_gastos_estimacion_directa_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION:
        raise RegistryValidationError(
            f"binding {binding.id!r} is not a ledger_renta_gastos_estimacion_directa_aggregation source"
        )
    selector = _renta_ledger_gastos_estimacion_directa_selector(binding)
    if selector.target_casilla_id not in _RENTA_100_FIRST_SLICE_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            "is outside the first Modelo 100 Renta ledger gastos slice",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_estimacion_directa_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact != "deductible_amount_sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_estimacion_directa_aggregation supports only "
            f"fact 'deductible_amount_sum', got {selector.fact!r}",
        )


def _renta_gastos_estimacion_directa_build_matcher(
    selector: _RentaLedgerGastosEstimacionDirectaSelector,
) -> Callable[[RentaGastosEstimacionDirectaObservationProtocol], bool]:
    modelo, period, target_casilla_id = selector.modelo, selector.period, selector.target_casilla_id

    def matcher(observation: RentaGastosEstimacionDirectaObservationProtocol) -> bool:
        return (
            observation.modelo == modelo
            and observation.period == period
            and observation.target_casilla_id == target_casilla_id
        )

    return matcher


def _renta_gastos_estimacion_directa_aggregate(
    matched: Sequence[RentaGastosEstimacionDirectaObservationProtocol],
    selector: _RentaLedgerGastosEstimacionDirectaSelector,
) -> Decimal:
    del selector  # single declared fact (deductible_amount_sum); nothing to dispatch on
    return sum((observation.deductible_amount for observation in matched), Decimal("0"))


def resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosEstimacionDirectaObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_gastos_estimacion_directa_aggregation`` binding on ``revision``.

    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` whose gastos bindings to resolve.
        observations: Typed gastos observations the bindings aggregate
            via their declared ``selector.fact`` and ``aggregation.op``.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        parse_selector=_renta_ledger_gastos_estimacion_directa_selector,
        build_matcher=_renta_gastos_estimacion_directa_build_matcher,
        aggregate=_renta_gastos_estimacion_directa_aggregate,
    )


def unsupported_ledger_renta_gastos_estimacion_directa_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosEstimacionDirectaObservationProtocol],
) -> tuple[RentaGastosEstimacionDirectaObservationProtocol, ...]:
    """Return the :class:`RentaGastosEstimacionDirectaObservationProtocol` rows no binding on ``revision`` can consume.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the (modelo, period, target_casilla_id)
    match predicate (reused from the resolver's
    ``_renta_gastos_estimacion_directa_build_matcher``) and a
    zero-``deductible_amount`` false-fire guard. No ``extra_exclusion``.

    Args:
        revision: The :class:`ModeloRevision` whose gastos bindings define
            the supported (modelo, period, target_casilla_id) triples.
        observations: First-slice gastos observations to screen.

    Returns:
        Tuple of observations whose non-zero deductible amount is selected by no
        ``ledger_renta_gastos_estimacion_directa_aggregation`` binding.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        parse_selector=_renta_ledger_gastos_estimacion_directa_selector,
        build_matcher=_renta_gastos_estimacion_directa_build_matcher,
        is_declarable=lambda observation: observation.deductible_amount != Decimal("0"),
    )


def renta_first_slice_binding_target_casillas(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the ``target_casilla_id`` set this revision's own bindings route to.

    Unlike :data:`cadrumo.domain.renta._first_slice_routing.FIRST_SLICE_EXPENSE_CASILLAS`
    (the universal BOE-prescribed routing table spanning every filing year the
    application supports), this returns only the casillas a
    ``ledger_renta_gastos_estimacion_directa_aggregation`` binding on THIS revision actually
    targets. Older Modelo 100 revisions (2020-2023) declare no such bindings
    at all -- the first-slice ledger-aggregation mechanism did not yet exist
    for them -- so their required set is legitimately empty even though the
    universal routing table's codomain is wider. The snapshot-time
    referential-integrity gate
    (:mod:`cadrumo.domain.renta.first_slice_routing_integrity`) uses this
    per-revision set rather than the universal table so it only fails when a
    binding THIS revision actually declares points at a casilla absent from
    that same revision -- the real defect class the gate exists to catch,
    not "does every filing year's estimación directa casilla exist on every
    other filing year's revision" (it does not, by BOE design: casillas are
    added, split, and renumbered across years).

    Args:
        revision: The :class:`ModeloRevision` whose own
            ``ledger_renta_gastos_estimacion_directa_aggregation`` binding selectors are
            inspected.
    """
    return frozenset(
        _renta_ledger_gastos_estimacion_directa_selector(binding).target_casilla_id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION
    )


def validate_ledger_renta_gastos_estimacion_directa_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_gastos_estimacion_directa_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerGastosEstimacionDirectaSelector`;
    runs the fact/aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerGastosEstimacionDirectaSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_gastos_estimacion_directa_aggregation",
        validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition,
    )


RentaLedgerGastosEstimacionDirectaSelector = _RentaLedgerGastosEstimacionDirectaSelector
