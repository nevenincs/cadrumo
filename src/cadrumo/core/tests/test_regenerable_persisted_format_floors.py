"""Regenerable persisted formats never acquire durable compatibility floors."""

import pytest

from ..compatibility_lifecycle import PERSISTED_FORMATS, RELEASED_FORMAT_FLOORS
from ..compatibility_lifecycle import misclassified_floor_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_regenerable_formats_never_carry_a_frozen_floor() -> None:
    misclassified = misclassified_floor_keys(RELEASED_FORMAT_FLOORS, PERSISTED_FORMATS)
    assert misclassified == (), (
        "RELEASED_FORMAT_FLOORS freezes a durability floor for regenerable "
        f"format(s) {misclassified}; a regenerable format is discarded and rebuilt "
        "on a version mismatch, so freezing its floor promises to read bytes nothing needs"
    )
