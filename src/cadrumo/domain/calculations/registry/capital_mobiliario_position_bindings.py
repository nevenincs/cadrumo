"""The binding family that carries a saver's interest and dividends to the boxes a Modelo 100 revision gives them.

A binding names an official detail record and the quantity it draws from that
record's occurrences: the gross, the withholding or the expenses. It never names
a concept token or a casilla number in code; the registry concept vocabulary says
which detail record a linked ledger row feeds, and the revision's casilla
declarations say which box each binding fills. A binding that names no detail
record draws its quantity from every occurrence, which is how a box that totals
one quantity across records is declared.

A row column names, besides its record and quantity, the dictionary field of the
official design that states the quantity once per occurrence. Each occurrence
then gives the column one row, and the scalar binding of the same record and
quantity is the total those rows must add up to.
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
    "capital_mobiliario_row_totals",
    "resolve_capital_mobiliario_position_binding_values",
    "resolve_capital_mobiliario_row_values",
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
    dictionary_field: str | None = Field(default=None, min_length=1, max_length=64)
    """The official dictionary field a row column fills once per occurrence; a scalar names none."""


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


def _validate_row_column(binding: BindingDefinition, selector: CapitalMobiliarioPositionProvider) -> None:
    if binding.value.data_type is not BindingDataType.MONEY or binding.value.channel is not BindingValueChannel.ROW_SET:
        raise RegistryValidationError(f"row column {binding.id!r} carries money on the row-set channel")
    if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS:
        raise RegistryValidationError(
            f"row column {binding.id!r} gives each occurrence a row, so its operation is rows"
        )
    if selector.detail_record is None:
        raise RegistryValidationError(f"row column {binding.id!r} fills one detail record; name the record")


def _validate_definition(binding: BindingDefinition) -> None:
    selector = ledger_binding_selector(
        binding, BindingSourceKind.CAPITAL_MOBILIARIO_POSITION, CapitalMobiliarioPositionProvider
    )
    if selector.dictionary_field is not None:
        _validate_row_column(binding, selector)
        return
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


def _scalar_bindings(
    revision: ModeloRevision,
) -> tuple[tuple[BindingDefinition, CapitalMobiliarioPositionProvider], ...]:
    return tuple(item for item in capital_mobiliario_position_bindings(revision) if item[1].dictionary_field is None)


def _row_columns(
    revision: ModeloRevision,
) -> tuple[tuple[BindingDefinition, CapitalMobiliarioPositionProvider], ...]:
    return tuple(
        item for item in capital_mobiliario_position_bindings(revision) if item[1].dictionary_field is not None
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
        One value per scalar family binding of the :class:`ModeloRevision` outside ``excluded``.
    """
    observed = tuple(occurrences)
    return {
        binding.id: sum(
            (_quantity(item, provider.quantity) for item in observed if _draws(provider, item)),
            Decimal("0"),
        )
        for binding, provider in _scalar_bindings(revision)
        if binding.id not in excluded
    }


def _draws(provider: CapitalMobiliarioPositionProvider, item: CapitalMobiliarioOccurrenceFigures) -> bool:
    return provider.detail_record is None or item.detail_record == provider.detail_record


def resolve_capital_mobiliario_row_values(
    revision: ModeloRevision,
    occurrences: Iterable[CapitalMobiliarioOccurrenceFigures],
    *,
    excluded: frozenset[BindingId] = frozenset(),
) -> dict[tuple[BindingId, int], Decimal]:
    """Give each occurrence one row on every row column of its record, numbered within that record from one.

    ``excluded`` names the columns the caller leaves without rows.

    Returns:
        The quantity of each occurrence by row column and row of the :class:`ModeloRevision`.
    """
    observed = tuple(occurrences)
    values: dict[tuple[BindingId, int], Decimal] = {}
    for binding, provider in _row_columns(revision):
        if binding.id in excluded:
            continue
        drawn = (item for item in observed if _draws(provider, item))
        for index, item in enumerate(drawn, start=1):
            values[(binding.id, index)] = _quantity(item, provider.quantity)
    return values


def capital_mobiliario_row_totals(revision: ModeloRevision) -> tuple[tuple[BindingId, tuple[BindingId, ...]], ...]:
    """Pair each scalar binding of a :class:`ModeloRevision` with the row columns whose rows add up to it.

    A column belongs to a scalar when it draws the same quantity from a record the
    scalar draws. A scalar no column states is left out.
    """
    columns = _row_columns(revision)
    totals: list[tuple[BindingId, tuple[BindingId, ...]]] = []
    for binding, provider in _scalar_bindings(revision):
        stated = tuple(
            column.id
            for column, selector in columns
            if selector.quantity is provider.quantity
            and (provider.detail_record is None or selector.detail_record == provider.detail_record)
        )
        if stated:
            totals.append((binding.id, stated))
    return tuple(totals)
