"""A row belonging to one instance of a repeated fact must say which.

A taxpayer with three socios gets three rows whose labels are the same
translated schema label three times over. The path that tells them apart
is shown only once a row is opened, so without the instance on the row the
page lists nine indistinguishable cells and asks the operator to guess.

Asserted through the one authority both render paths read, because the
full rebuild and the in-place cell update must write identical strings —
the incremental path compares exactly these tuples to decide which cells
moved, so a second spelling would leave edited rows drifting from their
unedited siblings.
"""

from __future__ import annotations

import pytest

from .....application.user_profile import ProfileFieldView
from .. import ProfileManagerApp

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]


def _row(**overrides: object) -> ProfileFieldView:
    return ProfileFieldView.model_validate(
        {
            "path": "attribution_entity_socios.0.nif",
            "label": "NIF",
            "value": "B12345678",
            "masked": False,
            "required": False,
            **overrides,
        },
    )


def test_an_instance_row_is_named_by_its_instance() -> None:
    _state, label, value = ProfileManagerApp._rendered_row(_row(row_index="0"))

    assert label.startswith("0")
    assert label.endswith("NIF")
    assert value == "B12345678"


def test_two_instances_of_one_field_render_distinguishable_labels() -> None:
    """The point of the whole exercise, asserted as inequality."""

    first = ProfileManagerApp._rendered_row(_row(row_index="0"))[1]
    second = ProfileManagerApp._rendered_row(_row(row_index="1"))[1]

    assert first != second


def test_an_ordinary_row_is_labelled_exactly_as_before() -> None:
    """No instance, no decoration: every unrepeated field must read unchanged."""

    _state, label, _value = ProfileManagerApp._rendered_row(
        _row(path="identity.tax_id", label="NIF"),
    )

    assert label == "NIF"


def test_a_required_instance_row_keeps_its_required_mark() -> None:
    """Both decorations are additive; neither may displace the other."""

    _state, label, _value = ProfileManagerApp._rendered_row(
        _row(row_index="2", required=True),
    )

    assert label.startswith("2")
    assert label.endswith("*")
