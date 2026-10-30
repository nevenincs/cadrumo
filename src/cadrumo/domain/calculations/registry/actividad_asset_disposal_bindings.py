"""The binding family that carries a baja's figures to the boxes a Modelo 100 revision gives them.

A route names what a figure is; the revision's own bindings say which box receives
it, so no box number lives in code and each edition answers for itself.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import BaseModel, BeforeValidator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_selector_utils import provider_member
from .ids import BindingId
from .ledger_binding_validation import (
    ledger_binding_build_diagnostics,
    ledger_binding_selector,
    require_ledger_aggregation_op,
    require_ledger_fact,
)
from .schema_base import coerce_enum_member

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision


class ActivityAssetDisposalRoute(StrEnum):
    """What a baja's figure is, whichever box an edition gives it."""

    TRANSMISSION_GAIN_ELEMENT = "transmission_gain_element"
    TRANSMISSION_GAIN_PROPERTY = "transmission_gain_property"
    TRANSMISSION_LOSS_ELEMENT = "transmission_loss_element"
    TRANSMISSION_LOSS_PROPERTY = "transmission_loss_property"
    NO_TRANSMISSION_GAIN = "no_transmission_gain"
    NO_TRANSMISSION_LOSS = "no_transmission_loss"
    EXCESS_DIRECT_ESTIMATION = "excess_direct_estimation"
    EXCESS_OBJECTIVE_ESTIMATION = "excess_objective_estimation"


_AMOUNT_FACTS: frozenset[str] = frozenset({"amount_sum"})


class ActivityAssetDisposalProvider(BaseModel):
    """Validated form of an ``activity_asset_disposal`` binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.ACTIVITY_ASSET_DISPOSAL] = BindingSourceKind.ACTIVITY_ASSET_DISPOSAL
    modelo: Literal["100"] = "100"
    period: Literal["0A"] = "0A"
    route: Annotated[ActivityAssetDisposalRoute, BeforeValidator(coerce_enum_member(ActivityAssetDisposalRoute))]
    target_casilla_id: CasillaId
    fact: Literal["amount_sum"] = "amount_sum"


class ActivityAssetDisposalObservationProtocol(Protocol):
    """What the family reads from one figure of a baja."""

    @property
    def route(self) -> ActivityAssetDisposalRoute:
        """Name what the figure is."""
        ...

    @property
    def amount(self) -> Decimal:
        """Return the figure as a magnitude; its route carries the direction."""
        ...


def _validate_definition(binding: BindingDefinition) -> None:
    selector = ledger_binding_selector(
        binding,
        BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
        ActivityAssetDisposalProvider,
    )
    require_ledger_aggregation_op(binding)
    require_ledger_fact(binding, selector.fact, _AMOUNT_FACTS)


def validate_activity_asset_disposal_binding(binding: BindingDefinition) -> list[str]:
    """Validate an ``activity_asset_disposal`` binding at registry-build time.

    Returns:
        The failures found, empty when the binding is valid.
    """
    return ledger_binding_build_diagnostics(binding, ActivityAssetDisposalProvider, _validate_definition)


def _family_bindings(revision: ModeloRevision) -> tuple[tuple[BindingDefinition, ActivityAssetDisposalProvider], ...]:
    return tuple(
        (binding, provider_member(binding, ActivityAssetDisposalProvider))
        for binding in revision.bindings
        if binding.source == BindingSourceKind.ACTIVITY_ASSET_DISPOSAL
    )


def activity_asset_disposal_route_casillas(revision: ModeloRevision) -> Mapping[ActivityAssetDisposalRoute, CasillaId]:
    """Return the box this :class:`ModeloRevision` gives each route; an unbound route is absent.

    Returns:
        The destination of every route the revision binds.
    """
    return {provider.route: provider.target_casilla_id for _binding, provider in _family_bindings(revision)}


def resolve_activity_asset_disposal_binding_values(
    revision: ModeloRevision,
    observations: Iterable[ActivityAssetDisposalObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Add up each route's figures into each :class:`ModeloRevision` binding; no route is a proven zero.

    Returns:
        One value per ``activity_asset_disposal`` binding on the revision.
    """
    observed = tuple(observations)
    return {
        binding.id: sum((item.amount for item in observed if item.route is provider.route), Decimal("0"))
        for binding, provider in _family_bindings(revision)
    }


__all__ = [
    "ActivityAssetDisposalObservationProtocol",
    "ActivityAssetDisposalProvider",
    "ActivityAssetDisposalRoute",
    "activity_asset_disposal_route_casillas",
    "resolve_activity_asset_disposal_binding_values",
    "validate_activity_asset_disposal_binding",
]
