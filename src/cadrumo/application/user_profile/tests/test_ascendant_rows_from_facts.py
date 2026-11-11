"""The stored ascendant facts read back into the rows a replacement takes."""

from __future__ import annotations

import pytest

from ..ascendant_rows import ProfileAscendantFact, ProfileAscendantRow, ascendant_rows_from_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_OBJECT = "renta_family.ascendiente"


def _leaves(row: ProfileAscendantRow) -> dict[str, str]:
    return {fact.field_key: fact.value for fact in row.facts}


def test_rows_come_back_in_stored_order_with_only_the_leaves_they_state() -> None:
    rows = ascendant_rows_from_facts(
        {
            f"{_OBJECT}.1.birth_date": "1951-11-30",
            f"{_OBJECT}.1.fallecimiento": "2025-02-01",
            f"{_OBJECT}.0.birth_date": "1948-03-04",
            f"{_OBJECT}.0.nif": "12345678Z",
            f"{_OBJECT}.0.convivientes": "2",
            "renta_family.ascendientes_count": "2",
        }
    )

    assert [_leaves(row) for row in rows] == [
        {"nif": "12345678Z", "birth_date": "1948-03-04", "convivientes": "2"},
        {"birth_date": "1951-11-30", "fallecimiento": "2025-02-01"},
    ]


def test_ten_rows_sort_numerically_not_lexically() -> None:
    facts = {f"{_OBJECT}.{index}.birth_date": f"19{40 + index}-01-01" for index in range(11)}

    rows = ascendant_rows_from_facts(facts)

    assert [_leaves(row)["birth_date"] for row in rows] == [f"19{40 + index}-01-01" for index in range(11)]


def test_a_blank_value_a_foreign_leaf_and_a_foreign_object_are_not_a_row() -> None:
    rows = ascendant_rows_from_facts(
        {
            f"{_OBJECT}.0.birth_date": "   ",
            f"{_OBJECT}.0.nombre": "not a leaf an ascendant row states",
            f"{_OBJECT}.x.birth_date": "1948-03-04",
            "renta_family.descendiente.0.birth_date": "2015-04-01",
            "renta_family.ascendientes_count": "0",
        }
    )

    assert rows == ()


def test_the_replacement_reads_the_same_rows_back() -> None:
    row = ProfileAscendantRow(facts=(ProfileAscendantFact(field_key="birth_date", value="1948-03-04"),))

    assert ascendant_rows_from_facts({f"{_OBJECT}.0.birth_date": "1948-03-04"}) == (row,)
