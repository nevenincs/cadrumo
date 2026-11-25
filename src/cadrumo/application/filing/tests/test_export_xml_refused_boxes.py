"""Which boxes an XML value or required-content refusal names."""

from __future__ import annotations

import pytest

from ..export_xml_value_limits import refused_xml_boxes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _ContextCarryingError(Exception):
    def __init__(self, context: object) -> None:
        super().__init__("refusal")
        self.context = context


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        ({"box": "DP_APENOM_D"}, ("DP_APENOM_D",)),
        ({"refused_boxes": "A, B", "box": "A"}, ("A", "B")),
        ({}, ()),
        (["box"], ()),
        ("box", ()),
        (None, ()),
    ],
)
def test_refused_xml_boxes_reads_only_a_mapping_context(context: object, expected: tuple[str, ...]) -> None:
    assert refused_xml_boxes(_ContextCarryingError(context)) == expected
