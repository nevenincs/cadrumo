"""The declared value contract a binding promises its consumers.

A binding's value contract answers two questions that the authored declaration
previously left implicit and a consumer had to re-derive: what the value *means*
(:class:`BindingDataType`) and which typed channel carries it
(:class:`BindingValueChannel`). The two axes are kept separate rather than
collapsed to one token because they are not the same statement -- ``money`` and
``integer`` are distinct legal quantities that a formula rounds and signs
differently, while the channel is the transport a resolver and an export share.
They are, however, not independently choosable: :data:`CHANNEL_FOR_BINDING_DATA_TYPE`
pins exactly one channel per data type, so a declaration that pairs them wrongly
is a contradiction the schema refuses rather than a preference it honours.

Row-shaped values carry a third axis: the row-assembly grouping. It reuses
:class:`~cadrumo.core.aggregation.RowSetGroupingKind`, the same canonical
cross-layer enum the detail-record source tokens map onto, so the grouping a
binding declares and the grouping the assembly layer consumes cannot drift.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final

from pydantic import BeforeValidator, model_validator

from ....core.aggregation import BindingTypedEnumKind, RowSetGroupingKind
from .errors import RegistryValidationError
from .schema_base import RegistryModel, coerce_enum_member

__all__ = [
    "CHANNEL_FOR_BINDING_DATA_TYPE",
    "BindingDataType",
    "BindingValueChannel",
    "BindingValueContract",
]


class BindingDataType(StrEnum):
    """The legal quantity a binding value represents."""

    MONEY = "money"
    """A monetary amount, signed and rounded by its owning casilla contract."""

    DECIMAL = "decimal"
    """A non-monetary decimal quantity.

    Distinct from ``money``: it carries no currency and is not rounded or
    signed by a monetary casilla contract, and distinct from ``integer``:
    it is genuinely fractional. A prorrata-weighted count is the canonical
    shape — truncating it to ``integer`` would discard the prorrata, and
    calling it ``money`` would label a quantity as currency.
    """

    INTEGER = "integer"
    """A whole count with no monetary rounding or currency."""

    BOOLEAN = "boolean"
    """A declared yes/no fact, distinct from a zero amount."""

    TEXT = "text"
    """Free or catalogued text carried verbatim to an export."""

    DATE = "date"
    """A calendar date, never a period token."""

    ENUM = "enum"
    """A member of a closed substrate enum named by ``typed_enum``."""


class BindingValueChannel(StrEnum):
    """The typed transport a resolver produces and a consumer narrows on."""

    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    TEXT = "text"
    DATE = "date"
    ENUM = "enum"
    ROW_SET = "row_set"


CHANNEL_FOR_BINDING_DATA_TYPE: Final[Mapping[BindingDataType, BindingValueChannel]] = MappingProxyType(
    {
        BindingDataType.MONEY: BindingValueChannel.DECIMAL,
        BindingDataType.DECIMAL: BindingValueChannel.DECIMAL,
        BindingDataType.INTEGER: BindingValueChannel.INTEGER,
        BindingDataType.BOOLEAN: BindingValueChannel.BOOLEAN,
        BindingDataType.TEXT: BindingValueChannel.TEXT,
        BindingDataType.DATE: BindingValueChannel.DATE,
        BindingDataType.ENUM: BindingValueChannel.ENUM,
    },
)
"""The one permitted channel per data type.

``money`` is the only pairing whose two tokens differ in spelling: a monetary
quantity travels the ``decimal`` channel, because the channel names the carrier
type and not the legal quantity. Every other data type names its channel
identically, which makes the pairing look redundant -- it is not, because the
two axes are declared independently and the map is what refuses a contradiction.

``money`` and ``decimal`` are the one pair of data types that share a channel:
both travel as a :class:`~decimal.Decimal`, and what separates them is the legal
quantity, not the carrier. The map stays a function from data type to channel,
so the pairing check remains exact in the direction it is asked.
"""


class BindingValueContract(RegistryModel):
    """The typed value shape one binding declaration promises.

    ``typed_enum`` names the closed substrate enum an ``enum``-channel value
    bridges; ``row_grouping`` names the row-assembly axis a ``row_set`` value
    is grouped by. The row-set channel carries the same scalar ``data_type``
    vocabulary as a scalar value; cardinality is stated by ``channel`` alone.
    """

    data_type: Annotated[BindingDataType, BeforeValidator(coerce_enum_member(BindingDataType))]
    channel: Annotated[BindingValueChannel, BeforeValidator(coerce_enum_member(BindingValueChannel))]
    typed_enum: Annotated[BindingTypedEnumKind | None, BeforeValidator(coerce_enum_member(BindingTypedEnumKind))] = None
    row_grouping: Annotated[RowSetGroupingKind | None, BeforeValidator(coerce_enum_member(RowSetGroupingKind))] = None

    @model_validator(mode="after")
    def _validate_channel_pairing(self) -> BindingValueContract:
        # A row-set value carries one scalar element type. Its cardinality is
        # expressed by the channel, so it deliberately bypasses the scalar
        # one-to-one channel map below. The provider registration owns whether
        # the row family is grouped or provider-native.
        if self.channel is BindingValueChannel.ROW_SET:
            return self
        expected = CHANNEL_FOR_BINDING_DATA_TYPE[self.data_type]
        if self.channel is not expected:
            raise RegistryValidationError(
                f"binding value data_type {self.data_type.value!r} requires channel "
                f"{expected.value!r}, not {self.channel.value!r}",
                context={
                    "data_type": self.data_type.value,
                    "channel": self.channel.value,
                    "expected_channel": expected.value,
                },
            )
        return self

    @model_validator(mode="after")
    def _validate_row_grouping(self) -> BindingValueContract:
        is_row_set = self.channel is BindingValueChannel.ROW_SET
        if not is_row_set and self.row_grouping is not None:
            raise RegistryValidationError(
                f"binding value row_grouping is permitted only for the row_set channel, not {self.channel.value!r}",
                context={"channel": self.channel.value, "row_grouping": self.row_grouping.value},
            )
        return self
