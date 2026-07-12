"""Modelo 210 explicit-IRNR ledger binding contract.

The selected :class:`ModeloRevision` declares the bindings this module
validates and resolves.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from ....core import Modelo
from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import invariant_diagnostics, selector_against_model
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, validated_casilla_id
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "IrnrIncomeObservationProtocol",
    "_IrnrLedgerIncomeSelector",
    "resolve_ledger_irnr_income_aggregation_binding_values",
    "unsupported_ledger_irnr_income_observations",
    "validate_ledger_irnr_income_aggregation_binding",
    "validate_ledger_irnr_income_aggregation_binding_definition",
]


class _IrnrLedgerIncomeSelector(BaseModel):
    """Validated selector for a Modelo 210 gross-income ledger binding."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M210] = Modelo.M210
    target_casilla_id: CasillaId
    fact: Literal["gross_income_sum"] = "gross_income_sum"


_IRNR_GROSS_INCOME_CASILLAS: frozenset[CasillaId] = frozenset(
    (validated_casilla_id("rendimientos_integros", surface="_IRNR_GROSS_INCOME_CASILLAS"),),
)


def _irnr_ledger_income_selector(binding: DataBindingDefinition) -> _IrnrLedgerIncomeSelector:
    try:
        return _IrnrLedgerIncomeSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_irnr_income_aggregation selector: {exc}",
        ) from exc


def validate_ledger_irnr_income_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_irnr_income_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION:
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_irnr_income_aggregation source")
    selector = _irnr_ledger_income_selector(binding)
    if selector.target_casilla_id not in _IRNR_GROSS_INCOME_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            f"is outside the supported Modelo 210 gross-income casillas {sorted(_IRNR_GROSS_INCOME_CASILLAS)!r}",
        )
    if binding_aggregation_op(binding) is not BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_irnr_income_aggregation supports only aggregation op 'sum'",
        )


def validate_ledger_irnr_income_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_irnr_income_aggregation`` binding at registry-build time."""
    failures = selector_against_model(binding, _IrnrLedgerIncomeSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_irnr_income_aggregation",
        validate_ledger_irnr_income_aggregation_binding_definition,
    )


class IrnrIncomeObservationProtocol(Protocol):
    """Structural protocol for one selected M210 gross-income observation."""

    @property
    def target_casilla_id(self) -> CasillaId: ...

    @property
    def gross_income_amount(self) -> Decimal: ...


def resolve_ledger_irnr_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IrnrIncomeObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve Modelo 210 gross-income bindings from selected M210 observations.

    Args:
        revision: The :class:`ModeloRevision` that declares the bindings to resolve.
        observations: Selected M210 gross-income observations.

    Returns:
        Binding ids mapped to their selected gross-income totals.

    Raises:
        RegistryValidationError: If a declared binding has a malformed selector.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION:
            continue
        selector = _irnr_ledger_income_selector(binding)
        resolved[binding.id] = sum(
            (
                observation.gross_income_amount
                for observation in available
                if observation.target_casilla_id == selector.target_casilla_id
            ),
            Decimal("0"),
        )
    return resolved


def unsupported_ledger_irnr_income_observations(
    revision: ModeloRevision,
    observations: Iterable[IrnrIncomeObservationProtocol],
) -> tuple[IrnrIncomeObservationProtocol, ...]:
    """Return non-zero M210 observations no declared source binding consumes.

    Args:
        revision: The :class:`ModeloRevision` whose bindings determine support.
        observations: Selected M210 gross-income observations to inspect.

    Returns:
        Non-zero observations that no declared binding consumes.

    Raises:
        RegistryValidationError: If a declared binding has a malformed selector.
    """
    supported = frozenset(
        _irnr_ledger_income_selector(binding).target_casilla_id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION
    )
    return tuple(
        observation
        for observation in observations
        if observation.gross_income_amount != Decimal("0") and observation.target_casilla_id not in supported
    )
