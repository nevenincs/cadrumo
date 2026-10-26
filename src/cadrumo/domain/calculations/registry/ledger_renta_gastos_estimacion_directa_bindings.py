"""Canonical Renta estimacion directa ledger-gastos binding family."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, field_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from ._ledger_binding_resolution import (
    deductible_amount_aggregate,
    resolve_ledger_family_binding_values,
    unsupported_ledger_family_observations,
)
from .binding_selector_utils import provider_member
from .ids import BindingId
from .ledger_binding_selector_support import casilla_id_set
from .ledger_binding_validation import (
    ledger_binding_build_diagnostics,
    ledger_binding_selector,
    require_ledger_aggregation_op,
    require_ledger_fact,
    require_ledger_target_casilla,
)

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

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


_DEDUCTIBLE_AMOUNT_FACTS: frozenset[str] = frozenset({"deductible_amount_sum"})


class RentaGastosEstimacionDirectaObservationProtocol(Protocol):
    """Structural protocol for first-slice Renta estimación directa gastos observations.

    The registry only needs these four attributes to resolve
    ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings; the full
    :class:`~cadrumo.domain.renta.ledger_expenses.RentaDeductibleExpenseObservation` satisfies
    this protocol without any explicit declaration.

    Properties are declared read-only so that concrete attributes satisfy the
    protocol under strict covariant checking.
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


class LedgerRentaGastosEstimacionDirectaProvider(BaseModel):
    """Validated form of a ledger_renta_gastos_estimacion_directa_aggregation binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION
    )

    modelo: Modelo = Modelo("100")
    period: Literal["0A"] = "0A"
    target_casilla_id: CasillaId
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"

    @field_validator("modelo")
    @classmethod
    @pydantic_validation_boundary
    def _require_modelo_100(cls, value: Modelo) -> Modelo:
        if value != Modelo("100"):
            raise ValueError("ledger_renta_gastos_estimacion_directa_aggregation modelo must be '100'")
        return value


def validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition(
    binding: BindingDefinition,
) -> None:
    """Validate a ``ledger_renta_gastos_estimacion_directa_aggregation`` binding definition."""
    selector = ledger_binding_selector(
        binding,
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        LedgerRentaGastosEstimacionDirectaProvider,
    )
    require_ledger_target_casilla(
        binding,
        selector.target_casilla_id,
        _RENTA_100_FIRST_SLICE_CASILLAS,
        scope="first Modelo 100 Renta ledger gastos slice",
    )
    require_ledger_aggregation_op(binding)
    require_ledger_fact(binding, selector.fact, _DEDUCTIBLE_AMOUNT_FACTS)


def _renta_gastos_estimacion_directa_build_matcher(
    selector: LedgerRentaGastosEstimacionDirectaProvider,
) -> Callable[[RentaGastosEstimacionDirectaObservationProtocol], bool]:
    modelo, period, target_casilla_id = selector.modelo, selector.period, selector.target_casilla_id

    def matcher(observation: RentaGastosEstimacionDirectaObservationProtocol) -> bool:
        return (
            observation.modelo == modelo
            and observation.period == period
            and observation.target_casilla_id == target_casilla_id
        )

    return matcher


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
        provider_model=LedgerRentaGastosEstimacionDirectaProvider,
        build_matcher=_renta_gastos_estimacion_directa_build_matcher,
        aggregate=deductible_amount_aggregate,
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
        provider_model=LedgerRentaGastosEstimacionDirectaProvider,
        build_matcher=_renta_gastos_estimacion_directa_build_matcher,
        is_declarable=lambda observation: observation.deductible_amount != Decimal("0"),
    )


def renta_first_slice_binding_target_casillas(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the ``target_casilla_id`` set this revision's own bindings route to.

    Unlike the universal BOE-prescribed first-slice routing projection spanning
    every filing year the
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
        provider_member(binding, LedgerRentaGastosEstimacionDirectaProvider).target_casilla_id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION
    )


def validate_ledger_renta_gastos_estimacion_directa_aggregation_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_gastos_estimacion_directa_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`LedgerRentaGastosEstimacionDirectaProvider`;
    runs the fact/aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition`.
    """
    return ledger_binding_build_diagnostics(
        binding,
        LedgerRentaGastosEstimacionDirectaProvider,
        validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition,
    )


LedgerRentaGastosEstimacionDirectaProvider = LedgerRentaGastosEstimacionDirectaProvider
