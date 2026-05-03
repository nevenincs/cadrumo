"""Registry-boundary tests for Modelo 303 and Modelo 390 filing paths."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from ...domain.filing import CasillaSchemaProvider
from . import FilingBuilderError, build_draft
from .testing import SyntheticProfile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> SyntheticProfile:
    return SyntheticProfile(
        tax_id="12345678Z",
        display_name="Registry boundary IVA test",
        applicable_modelos=("303", "390"),
    )


def _schema_provider() -> CasillaSchemaProvider:
    return cast("CasillaSchemaProvider", object())


@pytest.mark.parametrize(
    ("modelo", "period", "inputs"),
    [
        ("303", "2025Q1", {"07": Decimal("10000.00"), "29": Decimal("200.00")}),
        ("390", "2025", {"01": 2025}),
    ],
)
def test_modelo_build_draft_requires_registry_snapshot(
    modelo: str,
    period: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(FilingBuilderError, match="validated registry snapshot"):
        build_draft(
            modelo=modelo,
            period=period,
            profile=_profile(),
            inputs=inputs,
            schema_provider=_schema_provider(),
        )
