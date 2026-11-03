"""Stored disagreement facts validate row containers before rendering their values."""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ..disagreement_words import value_facts_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    "facts",
    ["null", "{}", "17", '["rows",[42]]', '["rows",[{}]]', '["rows",{}]'],
)
def test_wrong_typed_kept_values_are_refused(facts: str) -> None:
    with pytest.raises(ValueError, match=r"a (kept value|row set)"):
        value_facts_words(facts, OutputLanguage.EN)


def test_kept_rows_render_in_their_original_order() -> None:
    assert value_facts_words('["rows",[["text","first"],["text","second"]]]', OutputLanguage.EN) == "first, second"
