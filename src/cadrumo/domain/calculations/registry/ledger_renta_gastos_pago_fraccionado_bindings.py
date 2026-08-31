"""Canonical M130 pago-fraccionado ledger-gastos binding family."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal
from typing import Literal, NamedTuple, Protocol

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

_RENTA_130_GASTO_CASILLAS: frozenset[CasillaId] = casilla_id_set("_RENTA_130_GASTO_CASILLAS", "02")


class RentaGastosPagoFraccionadoObservationProtocol(Protocol):
    """Structural protocol for M130 pago-fraccionado gastos observations.

    The registry only needs these two attributes to resolve
    ``ledger_renta_gastos_pago_fraccionado_aggregation`` bindings; the full
    :class:`~cadrumo.application.aggregation._renta_gasto_ledger.RentaGastoObservation`
    satisfies this protocol without any explicit declaration. Mirrors
    :class:`RentaIncomeObservationProtocol` for the gastos dimension.
    """

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the declaration casilla receiving the deductible amount."""
        ...

    @property
    def deductible_amount(self) -> Decimal:
        """Return the deductible amount carried by the observation."""
        ...


class _RentaLedgerGastosPagoFraccionadoSelector(BaseModel):
    """Validated form of a ledger_renta_gastos_pago_fraccionado_aggregation binding selector.

    ``modelo`` is fixed to the M130 series (the only model sourcing gastos via
    this cumulative path). ``target_casilla_id`` is casilla 02 ("Gastos"). No
    period axis: the cumulative year-to-date window is applied by the
    application aggregator, exactly as for the income sibling.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: Literal[Modelo.M130] = Modelo.M130
    target_casilla_id: CasillaId
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_gastos_pago_fraccionado_selector(
    binding: DataBindingDefinition,
) -> _RentaLedgerGastosPagoFraccionadoSelector:
    try:
        return _RentaLedgerGastosPagoFraccionadoSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_gastos_pago_fraccionado_aggregation selector: {exc}",
        ) from exc


class _ReachabilityProbeObservation(NamedTuple):
    """Minimal structural instance of :class:`RentaGastosPagoFraccionadoObservationProtocol`.

    Not a test double: this is production code, called at registry-build
    time, constructing the smallest object that satisfies the registry's
    own declared Protocol. It exists so the reachability probe below never
    needs to import the concrete
    :class:`~cadrumo.application.aggregation._renta_gasto_ledger.RentaGastoObservation`
    -- doing so would have domain code depend on the application layer,
    the wrong hexagonal direction (`aeat-architecture-boundaries`). The
    Protocol is exactly the seam that makes this substitution legitimate:
    the resolver's matcher only ever reads the two declared attributes.
    """

    target_casilla_id: CasillaId
    deductible_amount: Decimal


def _renta_gastos_pago_fraccionado_reachability_probe(
    selector: _RentaLedgerGastosPagoFraccionadoSelector,
) -> None:
    """Assert the selector matches at least one constructible observation shape.

    Constructs a synthetic minimal observation from the selector's own
    declared ``target_casilla_id`` and runs it through the real matcher this
    family's resolver builds
    (:func:`_renta_gastos_pago_fraccionado_build_matcher`) -- not a
    reimplementation of the match rule, the same one production calculate
    and this probe both call. A selector whose matcher accepts no
    constructible shape is a defect no runtime ledger data can ever
    surface: the binding would aggregate to zero forever, indistinguishable
    from a taxpayer with no gasto deducible that period.

    This is a REACHABILITY probe only, and deliberately narrow. It proves
    the selector CAN match a shape built from its own declared fields; it
    never touches real ledger data and so cannot prove real data DOES
    match, and it cannot catch a matcher that accepts the wrong rows or a
    resolver that aggregates matched rows incorrectly -- both are outside
    what a build-time, data-free check can observe.

    **It also cannot fail as this family is currently matched, and saying so
    is the point.** The matcher tests
    ``observation.target_casilla_id == selector.target_casilla_id`` while the
    probe builds the observation from that same field, so the comparison is
    ``x == x`` for every selector, including a nonsense casilla id. Read
    without this paragraph the probe looks like coverage of a defect class it
    cannot reach, which is worse than no probe at all.

    It is kept rather than deleted because it costs nothing and becomes live
    the moment this family's matcher tests anything the selector declares as a
    SET -- the shape that makes the sibling
    :func:`_iva_reachability_probe` genuinely bite. The tautology is pinned by
    ``test_a_casilla_keyed_selector_probe_is_structurally_unable_to_fail``,
    which reddens if the match rule changes, forcing this paragraph to be
    rewritten instead of quietly outliving its truth.

    The reachability guarantee this family actually has is elsewhere and is
    real: ``target_casilla_id`` is validated against
    :data:`_RENTA_130_GASTO_CASILLAS` by the caller below, and the revision's
    own casilla set is cross-checked at snapshot build.
    """
    matcher = _renta_gastos_pago_fraccionado_build_matcher(selector)
    probe = _ReachabilityProbeObservation(
        target_casilla_id=selector.target_casilla_id,
        deductible_amount=Decimal("1.00"),
    )
    if not matcher(probe):
        raise RegistryValidationError(
            f"ledger_renta_gastos_pago_fraccionado_aggregation binding target_casilla_id "
            f"{selector.target_casilla_id!r} matches no constructible observation shape -- "
            "the binding can never resolve a value from any ledger data",
        )


def validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION:
        raise RegistryValidationError(
            f"binding {binding.id!r} is not a ledger_renta_gastos_pago_fraccionado_aggregation source"
        )
    selector = _renta_ledger_gastos_pago_fraccionado_selector(binding)
    if selector.target_casilla_id not in _RENTA_130_GASTO_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            "is outside the supported Modelo 130 gasto casillas",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_pago_fraccionado_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact != "deductible_amount_sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_pago_fraccionado_aggregation supports only "
            f"fact 'deductible_amount_sum', got {selector.fact!r}",
        )
    try:
        _renta_gastos_pago_fraccionado_reachability_probe(selector)
    except RegistryValidationError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} {exc}") from exc


def _renta_gastos_pago_fraccionado_build_matcher(
    selector: _RentaLedgerGastosPagoFraccionadoSelector,
) -> Callable[[RentaGastosPagoFraccionadoObservationProtocol], bool]:
    target_casilla_id = selector.target_casilla_id

    def matcher(observation: RentaGastosPagoFraccionadoObservationProtocol) -> bool:
        return observation.target_casilla_id == target_casilla_id

    return matcher


def _renta_gastos_pago_fraccionado_aggregate(
    matched: Sequence[RentaGastosPagoFraccionadoObservationProtocol],
    selector: _RentaLedgerGastosPagoFraccionadoSelector,
) -> Decimal:
    del selector  # single declared fact (deductible_amount_sum); nothing to dispatch on
    return sum((observation.deductible_amount for observation in matched), Decimal("0"))


def resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosPagoFraccionadoObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding on ``revision``.

    Matches observations by ``target_casilla_id`` and sums their
    ``deductible_amount``, mirroring the income resolver's casilla-keyed fold.
    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` whose gasto bindings are resolved.
        observations: M130 deductible gastos observations to aggregate over.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
        parse_selector=_renta_ledger_gastos_pago_fraccionado_selector,
        build_matcher=_renta_gastos_pago_fraccionado_build_matcher,
        aggregate=_renta_gastos_pago_fraccionado_aggregate,
    )


def unsupported_ledger_renta_gastos_pago_fraccionado_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosPagoFraccionadoObservationProtocol],
) -> tuple[RentaGastosPagoFraccionadoObservationProtocol, ...]:
    """Return the gasto observations no ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding can consume.

    ``revision`` is the :class:`ModeloRevision` whose declared bindings define
    what is consumable.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the ``target_casilla_id`` match predicate
    (reused from the resolver's ``_renta_gastos_pago_fraccionado_build_matcher``)
    and a zero-``deductible_amount`` false-fire guard — a gasto that
    contributes nothing declarable is excluded whether or not it is routed.
    No ``extra_exclusion``; unlike the IVA family this family has no
    category-level carve-out.

    Returns:
        Unsupported :class:`RentaGastosPagoFraccionadoObservationProtocol` observations.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
        parse_selector=_renta_ledger_gastos_pago_fraccionado_selector,
        build_matcher=_renta_gastos_pago_fraccionado_build_matcher,
        is_declarable=lambda observation: observation.deductible_amount != Decimal("0"),
    )


def validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerGastosPagoFraccionadoSelector`;
    runs the casilla / fact / aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerGastosPagoFraccionadoSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_gastos_pago_fraccionado_aggregation",
        validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition,
    )


RentaLedgerGastosPagoFraccionadoSelector = _RentaLedgerGastosPagoFraccionadoSelector
