"""Focused contracts for the binding value contract."""

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingTypedEnumKind, RowSetGroupingKind
from ..binding_value_contract import (
    CHANNEL_FOR_BINDING_DATA_TYPE,
    BindingDataType,
    BindingValueChannel,
    BindingValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_money_contract_hydrates_onto_the_decimal_channel() -> None:
    contract = BindingValueContract.model_validate({"data_type": "money", "channel": "decimal"})

    assert contract.data_type is BindingDataType.MONEY
    assert contract.channel is BindingValueChannel.DECIMAL
    assert contract.typed_enum is None
    assert contract.row_grouping is None


def test_enum_contract_carries_the_named_substrate_enum() -> None:
    contract = BindingValueContract.model_validate(
        {"data_type": "enum", "channel": "enum", "typed_enum": "CCAA"},
    )

    assert contract.typed_enum is BindingTypedEnumKind.CCAA


def test_grouped_row_contract_round_trips_through_its_json_form() -> None:
    contract = BindingValueContract(
        data_type=BindingDataType.TEXT,
        channel=BindingValueChannel.ROW_SET,
        row_grouping=RowSetGroupingKind.WITHHOLDING,
    )

    assert BindingValueContract.model_validate(contract.model_dump(mode="json")) == contract


def test_provider_native_row_contract_round_trips_without_a_grouping() -> None:
    """A row family emitted by its own resolver names no grouping and is still a row family."""
    contract = BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.ROW_SET)

    assert contract.row_grouping is None
    assert BindingValueContract.model_validate(contract.model_dump(mode="json")) == contract


def test_the_row_set_channel_carries_the_per_row_element_type() -> None:
    """``data_type`` on a row_set value is the element type, not the collection."""
    contract = BindingValueContract.model_validate(
        {"data_type": "text", "channel": "row_set", "row_grouping": "withholding"},
    )

    assert contract.data_type is BindingDataType.TEXT
    assert contract.channel is BindingValueChannel.ROW_SET


def test_the_retired_rows_data_type_is_refused() -> None:
    """``rows`` conflated the element type with the transport and is no longer a data type."""
    assert "rows" not in {member.value for member in BindingDataType}
    with pytest.raises(ValidationError):
        BindingValueContract.model_validate({"data_type": "rows", "channel": "row_set"})


@pytest.mark.parametrize("data_type", list(BindingDataType))
def test_every_scalar_data_type_declares_exactly_one_permitted_channel(data_type: BindingDataType) -> None:
    channel = CHANNEL_FOR_BINDING_DATA_TYPE[data_type]

    contract = BindingValueContract(data_type=data_type, channel=channel)

    assert contract.channel is channel
    assert channel is not BindingValueChannel.ROW_SET


@pytest.mark.parametrize("data_type", list(BindingDataType))
def test_every_scalar_data_type_is_also_a_legal_row_element_type(data_type: BindingDataType) -> None:
    """Every scalar quantity can be the per-row element of a row family."""
    contract = BindingValueContract(
        data_type=data_type,
        channel=BindingValueChannel.ROW_SET,
        row_grouping=RowSetGroupingKind.FOREIGN_ASSET,
    )

    assert contract.channel is BindingValueChannel.ROW_SET


def test_contract_refuses_a_channel_its_data_type_does_not_carry() -> None:
    with pytest.raises(ValidationError, match="requires channel 'decimal'"):
        BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.TEXT)


def test_contract_refuses_a_grouping_on_a_scalar_channel() -> None:
    with pytest.raises(ValidationError, match="permitted only for the row_set channel"):
        BindingValueContract(
            data_type=BindingDataType.MONEY,
            channel=BindingValueChannel.DECIMAL,
            row_grouping=RowSetGroupingKind.WITHHOLDING,
        )


def test_decimal_contract_hydrates_onto_the_decimal_channel() -> None:
    """A non-monetary decimal quantity shares the carrier with money, not the data type."""
    contract = BindingValueContract.model_validate({"data_type": "decimal", "channel": "decimal"})

    assert contract.data_type is BindingDataType.DECIMAL
    assert contract.channel is BindingValueChannel.DECIMAL
    assert contract.data_type is not BindingDataType.MONEY


def test_decimal_and_money_share_one_channel_without_collapsing_the_data_types() -> None:
    decimal = BindingValueContract(data_type=BindingDataType.DECIMAL, channel=BindingValueChannel.DECIMAL)
    money = BindingValueContract(data_type=BindingDataType.MONEY, channel=BindingValueChannel.DECIMAL)

    assert decimal.channel is money.channel
    assert decimal != money


def test_decimal_contract_refuses_the_integer_channel() -> None:
    """A fractional quantity must not be declared onto the whole-count channel."""
    with pytest.raises(ValidationError, match="requires channel 'decimal'"):
        BindingValueContract(data_type=BindingDataType.DECIMAL, channel=BindingValueChannel.INTEGER)
