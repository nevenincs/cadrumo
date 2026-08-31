"""Parity checks for flow and wizard validation diagnostic redaction."""

from __future__ import annotations

import pytest

from ....core.redaction.rules import redact_validation_context
from ...wizard.widgets import _redact_validation_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        ({}, {}),
        ({"raw": "operator answer"}, {"raw_redacted": True, "raw_length": 15}),
        ({"detail": "validator trace"}, {"detail_redacted": True}),
        (
            {"raw": 42, "detail": True, "field": "income"},
            {"field": "income", "raw_redacted": True, "raw_length": 2, "detail_redacted": True},
        ),
    ],
)
def test_flow_and_wizard_share_validation_context_redaction(
    context: dict[str, object],
    expected: dict[str, object],
) -> None:
    """Both caller surfaces remove raw/detail values with identical safe markers."""
    assert redact_validation_context(context) == expected
    assert _redact_validation_context(context) == expected
