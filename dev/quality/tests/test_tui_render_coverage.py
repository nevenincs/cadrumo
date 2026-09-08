"""Detector teeth for the live zero-target TUI render-coverage signal."""

from __future__ import annotations

import pytest

from ..tui_render_coverage import render

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_zero_unrendered_interfaces_is_clean() -> None:
    assert "every concrete interface" in render(())


def test_each_live_gap_is_named_without_a_disposition() -> None:
    rendered = render(("pkg.FirstScreen", "pkg.SecondScreen"))

    assert "2 concrete TUI interface(s)" in rendered
    assert "pkg.FirstScreen" in rendered
    assert "pkg.SecondScreen" in rendered
    assert "pending" not in rendered.casefold()
    assert "deferred" not in rendered.casefold()
