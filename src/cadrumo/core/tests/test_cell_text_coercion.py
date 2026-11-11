"""Unit tests for the shared spreadsheet cell-to-text coercer.

Four readers previously carried their own copy of this step. Two wanted the
plain rendering, one normalises integral floats, and one renders temporals as
ISO-8601. The axes are now parameters, so these tests exist to keep the three
renderings observably distinct: collapsing either axis into the default would
silently change what a casilla value or a raw-field archive prints.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from ..tabular import coerce_cell_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_default_rendering_leaves_both_axes_off() -> None:
    """Neither axis applies unless asked for."""
    assert coerce_cell_text(None) == ""
    assert coerce_cell_text("  spaced  ") == "spaced"
    assert coerce_cell_text(3.0) == "3.0"
    assert coerce_cell_text(date(2026, 4, 17)) == "2026-04-17"
    assert coerce_cell_text(datetime(2026, 4, 17, 10, 30, 5, 123456)) == "2026-04-17 10:30:05.123456"


def test_the_integral_float_axis_drops_the_spurious_decimal() -> None:
    """A casilla value stored as ``3.0`` must print as ``3``, not ``3.0``."""
    assert coerce_cell_text(3.0, integral_floats_as_int=True) == "3"
    assert coerce_cell_text(-14.0, integral_floats_as_int=True) == "-14"
    # A fractional value keeps every digit; only the whole-number case changes.
    assert coerce_cell_text(3.5, integral_floats_as_int=True) == "3.5"


def test_the_integral_float_axis_is_off_by_default() -> None:
    """The axis must be opt-in, or the raw-field archive loses the source spelling."""
    assert coerce_cell_text(3.0) != coerce_cell_text(3.0, integral_floats_as_int=True)


def test_the_temporal_axis_pins_iso_8601_and_truncates_to_seconds() -> None:
    """A booking stamp is archived ISO-8601 at whole-second resolution."""
    assert coerce_cell_text(datetime(2026, 4, 17, 10, 30, 5, 123456), temporal_as_iso=True) == "2026-04-17 10:30:05"
    assert coerce_cell_text(date(2026, 4, 17), temporal_as_iso=True) == "2026-04-17"


def test_the_temporal_axis_is_off_by_default() -> None:
    """Sub-second precision survives unless the archiving rendering is requested."""
    stamp = datetime(2026, 4, 17, 10, 30, 5, 123456)
    assert coerce_cell_text(stamp) != coerce_cell_text(stamp, temporal_as_iso=True)


def test_the_two_axes_are_disjoint_by_type() -> None:
    """Enabling both changes nothing for a value only one of them governs."""
    stamp = datetime(2026, 4, 17, 10, 30, 5, 123456)
    assert coerce_cell_text(stamp, integral_floats_as_int=True, temporal_as_iso=True) == coerce_cell_text(
        stamp,
        temporal_as_iso=True,
    )
    assert coerce_cell_text(3.0, integral_floats_as_int=True, temporal_as_iso=True) == coerce_cell_text(
        3.0,
        integral_floats_as_int=True,
    )


def test_a_boolean_renders_as_its_python_text_under_every_setting() -> None:
    """``bool`` is an ``int`` subclass, not a float; no axis may capture it."""
    for kwargs in ({}, {"integral_floats_as_int": True}, {"temporal_as_iso": True}):
        assert coerce_cell_text(True, **kwargs) == "True"  # type: ignore[arg-type]
