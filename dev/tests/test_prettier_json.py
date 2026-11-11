"""The Prettier layout keeps a short value on one line and breaks what Prettier breaks."""

from __future__ import annotations

import json

import pytest

from dev.prettier_json import dump_json

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_short_scalar_list_stays_on_one_line() -> None:
    assert dump_json({"a": [1, 2, 3]}) == '{\n  "a": [1, 2, 3]\n}\n'


def test_empty_containers_print_flat() -> None:
    assert dump_json({"a": [], "b": {}}) == '{\n  "a": [],\n  "b": {}\n}\n'


def test_a_matrix_of_several_rows_breaks_even_when_it_would_fit() -> None:
    assert dump_json([[1, 2], [3, 4]]) == "[\n  [1, 2],\n  [3, 4]\n]\n"


def test_a_single_row_matrix_stays_flat() -> None:
    assert dump_json([[1, 2]]) == "[[1, 2]]\n"


def test_a_list_holding_a_non_empty_object_breaks() -> None:
    assert dump_json([{"k": 1}]) == '[\n  {\n    "k": 1\n  }\n]\n'


def test_a_list_wider_than_the_line_breaks_one_item_per_row() -> None:
    items = ["x" * 30, "y" * 30, "z" * 30]
    text = dump_json(items)
    assert text.splitlines()[0] == "["
    assert json.loads(text) == items
    assert max(len(line) for line in text.splitlines()) <= 80


def test_non_ascii_text_is_kept_literally() -> None:
    assert dump_json(["é"]) == '["é"]\n'
