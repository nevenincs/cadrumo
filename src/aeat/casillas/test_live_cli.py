"""Opt-in live tests for future issue-21-backed casillas draft workflows."""

from __future__ import annotations

import pytest

from ..cli._live import requires_live_enabled


@pytest.mark.live
@pytest.mark.parametrize(
    ("modelo", "period"),
    [
        ("MODELO_130", "2025Q4"),
        ("MODELO_303", "2025Q4"),
        ("MODELO_390", "2025"),
    ],
)
def test_real_llm_workflow_is_blocked_until_issue21_lands(modelo: str, period: str) -> None:
    """Skip until the real issue-21 client surface is available."""
    requires_live_enabled()
    pytest.skip(f"Real provider-backed extract/translate is deferred until issue #21 lands ({modelo}/{period}).")
