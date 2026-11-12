"""The binding family that carries a saver's interest and dividends to the boxes a Modelo 100 revision gives them.

A binding names an official detail record and the quantity it draws from that
record's occurrences: the gross, the withholding or the expenses. It never names
a concept token or a casilla number in code; the registry concept vocabulary says
which detail record a linked ledger row feeds, and the revision's casilla
declarations say which box each binding fills. A binding that names no detail
record draws its quantity from every occurrence, which is how a box that totals
one quantity across records is declared.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member
from .binding_value_contract import BindingDataType, BindingValueChannel
from .errors import RegistryValidationError
from .form_codes import form_role_validator
from .ledger_binding_validation import ledger_binding_build_diagnostics, ledger_binding_selector
from .schema_base import coerce_enum_member

if TYPE_CHECKING:
    from .ids import BindingId
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "CapitalMobiliarioOccurrenceFigures",
    "CapitalMobiliarioPositionProvider",
    "CapitalMobiliarioQuantity",
    "capital_mobiliario_position_bindings",
    "resolve_capital_mobiliario_position_binding_values",
    "revision_declares_capital_mobiliario_position",
    "validate_capital_mobiliario_position_binding",
]


class CapitalMobiliarioQuantity(StrEnum):
    """Which amount of a detail-record occurrence a binding draws."""

    GROSS = "gross"
    WITHHOLDING = "withholding"
    EXPENSES = "expenses"


class CapitalMobiliarioPositionProvider(BaseModel):
    """Validated form of a ``capital_mobiliario_position`` binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.CAPITAL_MOBILIARIO_POSITION] = BindingSourceKind.CAPITAL_MOBILIARIO_POSITION
    modelo: Annotated[str, AfterValidator(form_role_validator("renta.annual"))]
    period: Literal["0A"] = "0A"
    detail_record: str | None = Field(default=None, min_length=1, max_length=32)
    """The official detail record whose occurrences the binding draws; none draws every record's."""
    quantity: Annotated[CapitalMobiliarioQuantity, BeforeValidator(coerce_enum_member(CapitalMobiliarioQuantity))]


class CapitalMobiliarioOccurrenceFigures(Protocol):
    """What the family reads from one computed occurrence."""

    @property
    def detail_record(self) -> str:
        """Name the official detail record the occurrence fills."""
        ...

    @property
    def gross(self) -> Decimal:
        """Return the occurrence's gross income."""
        ...

    @property
    def withholding(self) -> Decimal:
        """Return the occurrence's withholding."""
        ...

    @property
    def expenses(self) -> Decimal:
        """Return the occurrence's deductible expenses."""
        ...


def _validate_definition(binding: BindingDefinition) -> None:
    selector = ledger_binding_selector(
        binding, BindingSourceKind.CAPITAL_MOBILIARIO_POSITION, CapitalMobiliarioPositionProvider
    )
    if binding.value.data_type is not BindingDataType.MONEY or binding.value.channel is not BindingValueChannel.DECIMAL:
        raise RegistryValidationError(f"binding {binding.id!r} carries money on the decimal channel")
    if binding_aggregation_op(binding) is not BindingAggregationOp.SUM:
        raise RegistryValidationError(f"binding {binding.id!r} sums its occurrences, so its operation is sum")
    if selector.quantity is CapitalMobiliarioQuantity.GROSS and selector.detail_record is None:
        raise RegistryValidationError(
            f"binding {binding.id!r} draws a gross, which belongs to one detail record; name the record"
        )


def validate_capital_mobiliario_position_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``capital_mobiliario_position`` binding at registry-build time.

    Returns:
        The failures found, empty when the binding is valid.
    """
    return ledger_binding_build_diagnostics(binding, CapitalMobiliarioPositionProvider, _validate_definition)


def capital_mobiliario_position_bindings(
    revision: ModeloRevision,
) -> tuple[tuple[BindingDefinition, CapitalMobiliarioPositionProvider], ...]:
    """Return every family binding of a :class:`ModeloRevision` beside its typed provider, in declaration order."""
    return tuple(
        (binding, provider_member(binding, CapitalMobiliarioPositionProvider))
        for binding in revision.bindings
        if binding.source is BindingSourceKind.CAPITAL_MOBILIARIO_POSITION
    )


def revision_declares_capital_mobiliario_position(revision: ModeloRevision) -> bool:
    """Return whether a :class:`ModeloRevision` declares any member of the family."""
    return any(binding.source is BindingSourceKind.CAPITAL_MOBILIARIO_POSITION for binding in revision.bindings)


def _quantity(item: CapitalMobiliarioOccurrenceFigures, quantity: CapitalMobiliarioQuantity) -> Decimal:
    match quantity:
        case CapitalMobiliarioQuantity.GROSS:
            return item.gross
        case CapitalMobiliarioQuantity.WITHHOLDING:
            return item.withholding
        case CapitalMobiliarioQuantity.EXPENSES:
            return item.expenses


def resolve_capital_mobiliario_position_binding_values(
    revision: ModeloRevision,
    occurrences: Iterable[CapitalMobiliarioOccurrenceFigures],
    *,
    excluded: frozenset[BindingId] = frozenset(),
) -> dict[BindingId, Decimal]:
    """Add up each binding's quantity over the occurrences of its record; no occurrence is a proven zero.

    ``excluded`` names the bindings the caller leaves unresolved, which receive no value.

    Returns:
        One value per family binding of the :class:`ModeloRevision` outside ``excluded``.
    """
    observed = tuple(occurrences)
    return {
        binding.id: sum(
            (
                _quantity(item, provider.quantity)
                for item in observed
                if provider.detail_record is None or item.detail_record == provider.detail_record
            ),
            Decimal("0"),
        )
        for binding, provider in capital_mobiliario_position_bindings(revision)
        if binding.id not in excluded
    }
