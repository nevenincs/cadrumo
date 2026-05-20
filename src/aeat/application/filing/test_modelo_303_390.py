"""Registry-boundary tests for Modelo 303 and Modelo 390 filing paths."""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import ModeloBuilderError, build_draft, build_runtime_schema_provider
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
def test_modelo_build_draft_requires_registry_definition(
    modelo: str,
    period: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(ModeloBuilderError, match="not present in the calculation registry"):
        build_draft(
            modelo=modelo,
            period=period,
            profile=_profile(),
            inputs=inputs,
            schema_provider=build_runtime_schema_provider(),
        )
