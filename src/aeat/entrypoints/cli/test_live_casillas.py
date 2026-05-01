"""Opt-in live placeholders for the LLM-backed casillas draft workflow.

Holds the slot for the future provider-backed extract/translate flow
that will exercise real LLM calls against canonical
``MODELO_130``/``MODELO_303``/``MODELO_390`` corpora once the
production LLM client surface lands. Each test honours the
``AEAT_LIVE_TESTS_ENABLED`` gate and currently skips with an
explanatory message until the dependency lands.
"""

from __future__ import annotations

import pytest

from ._live import requires_live_enabled

pytestmark = [pytest.mark.live_read, pytest.mark.domain_application]


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
