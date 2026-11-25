"""A machine-secret field that carries a JSON array splits into the JSON text of each element."""

from __future__ import annotations

import json

import pytest

from ..machine_secret_json_items import json_array_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_each_element_keeps_its_own_meaning() -> None:
    items = json_array_items('[{"key": "a", "quantity": "2"}, {"key": "b"}]')

    assert [json.loads(item) for item in items] == [{"key": "a", "quantity": "2"}, {"key": "b"}]


@pytest.mark.parametrize("blank", ["", "   \n"])
def test_blank_text_is_no_elements(blank: str) -> None:
    assert json_array_items(blank) == ()


@pytest.mark.parametrize("text", ['{"key": "private-value"}', "not json private-value", '"private-value"'])
def test_anything_but_one_array_is_refused_without_echoing_it(text: str) -> None:
    with pytest.raises(ValueError, match="one JSON array") as refusal:
        json_array_items(text)

    assert "private-value" not in str(refusal.value)
