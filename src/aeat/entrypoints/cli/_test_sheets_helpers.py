"""Unit tests for :mod:`aeat.cli._sheets_helpers`."""

from __future__ import annotations

import pytest

from ._sheets_helpers import coerce_value_input_option, parse_values_json

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class TestParseValuesJson:
    """Behaviour of ``parse_values_json``."""

    def test_two_d_array_passes_through(self) -> None:
        assert parse_values_json("[[1, 2], [3, 4]]") == [[1, 2], [3, 4]]

    def test_one_d_array_wrapped_into_row(self) -> None:
        assert parse_values_json("[1, 2, 3]") == [[1, 2, 3]]

    def test_scalar_wrapped_into_one_by_one(self) -> None:
        assert parse_values_json("42") == [[42]]

    def test_string_scalar(self) -> None:
        assert parse_values_json('"hello"') == [["hello"]]

    def test_empty_array(self) -> None:
        assert parse_values_json("[]") == [[]]

    def test_object_payload_raises(self) -> None:
        with pytest.raises(ValueError, match="must be a list or scalar"):
            parse_values_json('{"a": 1}')

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_values_json("not json")


class TestCoerceValueInputOption:
    """Behaviour of ``coerce_value_input_option``."""

    def test_raw_true(self) -> None:
        assert coerce_value_input_option(True) == "RAW"

    def test_raw_false(self) -> None:
        assert coerce_value_input_option(False) == "USER_ENTERED"
