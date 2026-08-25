"""Registry period-token boundaries use the canonical core union."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema import PeriodSelector, RegistrySnapshotRef
from ..bindings_previous_filing import PreviousModeloSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_period_boundaries_normalize_administrative_tokens() -> None:
    """Modelo 036 event coordinates remain valid alongside filing-period codes."""
    snapshot = RegistrySnapshotRef(
        modelo="036",
        revision_id="2025-02-03-y-siguientes",
        modelo_year=2025,
        period="alta",
    )
    selector = PeriodSelector(
        year_from=2025,
        periods=("alta", "modificacion", "baja", "comunicacion", "variacion"),
    )
    previous_filing = PreviousModeloSelector(source_modelo="036", period="modificacion")

    assert snapshot.period == "ALTA"
    assert selector.periods == ("alta", "modificacion", "baja", "comunicacion", "variacion")
    assert previous_filing.required_periods == ("modificacion",)


@pytest.mark.parametrize("invalid_period", ("BOGUS", "2025 1T"))
def test_registry_period_boundaries_refuse_unknown_or_display_tokens(invalid_period: str) -> None:
    """All audited boundaries reject non-canonical raw and combined period forms."""
    with pytest.raises(ValidationError):
        RegistrySnapshotRef(
            modelo="303",
            revision_id="2025-y-siguientes",
            modelo_year=2025,
            period=invalid_period,
        )
    with pytest.raises(ValidationError):
        PeriodSelector(years=(2025,), periods=(invalid_period,))
    with pytest.raises(ValidationError):
        PreviousModeloSelector(source_modelo="303", period=invalid_period)
