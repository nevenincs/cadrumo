"""The binding family that carries a baja's figures to the boxes a Modelo 100 revision gives them.

A route names what a figure is; the revision's own bindings say which box receives
it, so no box number lives in code and each edition answers for itself.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, Literal, Protocol

from pydantic import BaseModel, BeforeValidator, Field

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member
from .errors import RegistryValidationError
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
    TRANSMISSION_ELEMENT_TYPE = "transmission_element_type"
    EXCESS_DIRECT_ESTIMATION = "excess_direct_estimation"
    EXCESS_OBJECTIVE_ESTIMATION = "excess_objective_estimation"


class ActivityAssetDisposalRowField(StrEnum):
    """What one column of a sale's row of other elements states."""

    ELEMENT_TYPE = "element_type"
    TRANSMISSION_DATE = "transmission_date"
    TRANSMISSION_VALUE = "transmission_value"
    ACQUISITION_VALUE = "acquisition_value"
    LOSS = "loss"
    GAIN = "gain"


_AMOUNT_FACTS: frozenset[str] = frozenset({"amount_sum"})
ELEMENT_ROW_ROUTES: Final[frozenset[ActivityAssetDisposalRoute]] = frozenset(
    {ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT, ActivityAssetDisposalRoute.TRANSMISSION_LOSS_ELEMENT},
)
"""The figures that fill a row of other elements, whose type the row states as a clave."""


class ActivityAssetDisposalProvider(BaseModel):
    """Validated form of an ``activity_asset_disposal`` binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.ACTIVITY_ASSET_DISPOSAL] = BindingSourceKind.ACTIVITY_ASSET_DISPOSAL
    modelo: Literal["100"] = "100"
    period: Literal["0A"] = "0A"
    route: (
        Annotated[ActivityAssetDisposalRoute, BeforeValidator(coerce_enum_member(ActivityAssetDisposalRoute))] | None
    ) = None
    """What a scalar figure is; a row column names its ``row_field`` instead."""
    target_casilla_id: CasillaId
    fact: Literal["amount_sum", "element_type_clave", "row_field"] = "amount_sum"
    clave: str | None = Field(default=None, min_length=1, max_length=8)
    """The clave the revision gives an element affected to an activity, on its element-type binding."""
    record: Literal["elemento_patrimonial"] | None = None
    grouping: Literal["per_disposal"] | None = None
    row_field: (
        Annotated[ActivityAssetDisposalRowField, BeforeValidator(coerce_enum_member(ActivityAssetDisposalRowField))]
        | None
    ) = None


class ActivityAssetDisposalRowProtocol(Protocol):
    """What one sale states on a row of its own, a missing column left off the row."""

    @property
    def source_identity(self) -> str:
        """Identify the sale the row comes from."""
        ...

    def column(self, row_field: ActivityAssetDisposalRowField) -> Decimal | str | None:
        """Return this sale's value for a column; the clave column is the revision's own."""
        ...


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


def _validate_row_definition(binding: BindingDefinition, selector: ActivityAssetDisposalProvider) -> None:
    if selector.route is not None or selector.row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} names a row column and no route")
    if selector.record is None or selector.grouping is None:
        raise RegistryValidationError(f"binding {binding.id!r} names the record and the grouping of its rows")
    if (selector.row_field is ActivityAssetDisposalRowField.ELEMENT_TYPE) != (selector.clave is not None):
        raise RegistryValidationError(f"binding {binding.id!r} states a clave only on the element-type column")
    if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS:
        raise RegistryValidationError(f"binding {binding.id!r} requires aggregation op 'rows'")


def _validate_definition(binding: BindingDefinition) -> None:
    selector = ledger_binding_selector(
        binding,
        BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
        ActivityAssetDisposalProvider,
    )
    if selector.fact == "row_field":
        _validate_row_definition(binding, selector)
        return
    if selector.route is None or selector.row_field is not None:
        raise RegistryValidationError(f"binding {binding.id!r} names a route and no row column")
    if selector.route is ActivityAssetDisposalRoute.TRANSMISSION_ELEMENT_TYPE:
        if selector.fact != "element_type_clave" or selector.clave is None:
            raise RegistryValidationError(f"binding {binding.id!r} states the clave of the element type")
        if binding_aggregation_op(binding) is not BindingAggregationOp.COPY:
            raise RegistryValidationError(f"binding {binding.id!r} copies its clave; it is not a sum")
        return
    if selector.clave is not None:
        raise RegistryValidationError(f"binding {binding.id!r} carries a figure, not a clave")
    require_ledger_aggregation_op(binding)
    require_ledger_fact(binding, selector.fact, _AMOUNT_FACTS)


def validate_activity_asset_disposal_binding(binding: BindingDefinition) -> list[str]:
    """Validate an ``activity_asset_disposal`` binding at registry-build time.

    Returns:
        The failures found, empty when the binding is valid.
    """
    return ledger_binding_build_diagnostics(binding, ActivityAssetDisposalProvider, _validate_definition)


def _all_bindings(revision: ModeloRevision) -> tuple[tuple[BindingDefinition, ActivityAssetDisposalProvider], ...]:
    return tuple(
        (binding, provider_member(binding, ActivityAssetDisposalProvider))
        for binding in revision.bindings
        if binding.source == BindingSourceKind.ACTIVITY_ASSET_DISPOSAL
    )


def _family_bindings(revision: ModeloRevision) -> tuple[tuple[BindingDefinition, ActivityAssetDisposalProvider], ...]:
    return tuple(item for item in _all_bindings(revision) if item[1].fact != "row_field")


def activity_asset_disposal_route_casillas(revision: ModeloRevision) -> Mapping[ActivityAssetDisposalRoute, CasillaId]:
    """Return the box this :class:`ModeloRevision` gives each route; an unbound route is absent.

    Returns:
        The destination of every route the revision binds.
    """
    return {
        provider.route: provider.target_casilla_id
        for _binding, provider in _family_bindings(revision)
        if provider.route is not None
    }


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
        if provider.clave is None
    }


def resolve_activity_asset_disposal_element_type_values(
    revision: ModeloRevision,
    observations: Iterable[ActivityAssetDisposalObservationProtocol],
) -> tuple[dict[BindingId, str], tuple[BindingId, ...]]:
    """State the clave of a row of other elements on each :class:`ModeloRevision` binding that carries one.

    Returns:
        The clave by binding where a baja fills such a row, and the bindings that do
        not apply because none does.
    """
    filled = any(item.route in ELEMENT_ROW_ROUTES for item in observations)
    claves = tuple(
        (binding.id, provider.clave) for binding, provider in _family_bindings(revision) if provider.clave is not None
    )
    if filled:
        return dict(claves), ()
    return {}, tuple(binding_id for binding_id, _clave in claves)


def activity_asset_disposal_row_binding_ids(revision: ModeloRevision) -> tuple[BindingId, ...]:
    """Return the row columns this :class:`ModeloRevision` declares for a sale of an element."""
    return tuple(binding.id for binding, provider in _all_bindings(revision) if provider.fact == "row_field")


def resolve_activity_asset_disposal_row_values(
    revision: ModeloRevision,
    rows: Iterable[ActivityAssetDisposalRowProtocol],
) -> tuple[dict[tuple[BindingId, int], Decimal | str], dict[tuple[BindingId, int], str]]:
    """Give each sale its own row on every column this :class:`ModeloRevision` declares.

    The scalar bindings keep the totals the form's own sums read; these columns say what
    each sale states. A column a sale has no value for stays absent from its row.

    Returns:
        The values by binding and row, and the sale each coordinate comes from.
    """
    values: dict[tuple[BindingId, int], Decimal | str] = {}
    identities: dict[tuple[BindingId, int], str] = {}
    columns = tuple(item for item in _all_bindings(revision) if item[1].fact == "row_field")
    for index, row in enumerate(rows):
        for binding, provider in columns:
            field = provider.row_field
            if field is None:  # defensive: a row column names its field at build time
                continue
            value = provider.clave if field is ActivityAssetDisposalRowField.ELEMENT_TYPE else row.column(field)
            if value is not None:
                values[(binding.id, index)] = value
                identities[(binding.id, index)] = row.source_identity
    return values, identities


__all__ = [
    "ELEMENT_ROW_ROUTES",
    "ActivityAssetDisposalObservationProtocol",
    "ActivityAssetDisposalProvider",
    "ActivityAssetDisposalRoute",
    "ActivityAssetDisposalRowField",
    "ActivityAssetDisposalRowProtocol",
    "activity_asset_disposal_route_casillas",
    "activity_asset_disposal_row_binding_ids",
    "resolve_activity_asset_disposal_binding_values",
    "resolve_activity_asset_disposal_element_type_values",
    "resolve_activity_asset_disposal_row_values",
    "validate_activity_asset_disposal_binding",
]
