"""Registry-boundary tests for Modelo 303 and Modelo 390 filing paths.

Modelo 303 (IVA autoliquidación) and Modelo 390 (IVA resumen anual)
are registry-backed: ``303.toml`` and ``390.toml`` carry full casilla
and revision definitions. ``build_draft`` must therefore project a
``ModeloDraft`` for both, sourcing its schema from the calculation
registry rather than refusing at the registry boundary. The
genuinely-unsupported-modelo refusal path is covered separately by
``test_testing_registry.test_unsupported_modelo_fails_at_registry_boundary``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import build_draft, build_runtime_schema_provider
from .testing import ModeloTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> ModeloTestProfile:
    return ModeloTestProfile(
        tax_id="12345678Z",
        display_name="Registry boundary IVA test",
    )


@pytest.mark.parametrize(
    ("modelo", "period", "inputs"),
    [
        ("303", "2025Q1", {"07": Decimal("10000.00"), "29": Decimal("200.00")}),
        ("390", "2025A", {"01": 2025}),
    ],
)
def test_modelo_build_draft_projects_registry_backed_draft(
    modelo: str,
    period: str,
    inputs: dict[str, object],
) -> None:
    """``build_draft`` projects a registry-backed draft for 303 / 390."""
    draft = build_draft(
        modelo=modelo,
        period=period,
        profile=_profile(),
        inputs=inputs,
        schema_provider=build_runtime_schema_provider(),
    )

    assert draft.modelo == modelo
    assert draft.period == period
    assert draft.profile_tax_id == "12345678Z"
