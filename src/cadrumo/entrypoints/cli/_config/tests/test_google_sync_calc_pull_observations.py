"""Google calculation-pull row-observation ingress tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....adapters.outbound.google import RowSetCellEdit, RowSetEdit
from .....application import calculations
from .....core.resources import resources
from .._google_sync_calc import _assemble_pull_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _snapshot():
    return resources().modelos.authority.snapshot(
        "190",
        filing_year=2025,
        period="0A",
    )


def test_pull_row_assembly_delegates_each_row_set_to_the_snapshot_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lower-level dispatcher bypass cannot substitute a different revision."""
    snapshot = _snapshot()
    row_set = RowSetEdit(
        grouping="not-a-live-grouping",
        cells=(RowSetCellEdit(binding="modelo-190-perceptor-row-nif", row_index=1, value="11111111A"),),
    )
    calls: list[tuple[object, object, object]] = []

    def assemble_for_snapshot(
        grouping: object,
        cells: object,
        supplied_snapshot: object,
    ) -> tuple[str, tuple[object, ...]]:
        calls.append((grouping, cells, supplied_snapshot))
        return "withholding", ()

    monkeypatch.setattr(calculations, "assemble_observations_for_snapshot", assemble_for_snapshot)

    groupings, observation_count = _assemble_pull_observations(
        populated_row_sets=[row_set],
        snapshot=snapshot,
        enabled=True,
    )

    assert calls == [(row_set.grouping, row_set.cells, snapshot)]
    assert observation_count == 0
    assert groupings == [
        {
            "grouping": row_set.grouping,
            "source_kind": "withholding",
            "observation_count": 0,
            "observations": [],
        },
    ]


def test_pull_row_assembly_returns_live_snapshot_assembled_observations() -> None:
    """A pulled row reaches S87's typed observation boundary under the live snapshot."""
    snapshot = _snapshot()
    row_set = RowSetEdit(
        grouping="per_perceptor_clave",
        cells=(
            RowSetCellEdit(binding="modelo-190-perceptor-row-nif", row_index=1, value="11111111A"),
            RowSetCellEdit(binding="modelo-190-perceptor-row-clave", row_index=1, value="A"),
            RowSetCellEdit(
                binding="modelo-190-perceptor-row-percibido-dinerario",
                row_index=1,
                value=Decimal("100.00"),
            ),
        ),
    )

    groupings, observation_count = _assemble_pull_observations(
        populated_row_sets=[row_set],
        snapshot=snapshot,
        enabled=True,
    )

    assert observation_count == 1
    assert groupings[0]["grouping"] == "per_perceptor_clave"
    assert groupings[0]["source_kind"] == "withholding"
    assert groupings[0]["observation_count"] == 1
    observations = groupings[0]["observations"]
    assert isinstance(observations, list)
    assert len(observations) == 1
    observation = observations[0]
    assert isinstance(observation, dict)
    assert observation["source_id"] == "detalle:per_perceptor_clave:row-1"
    assert observation["perceptor_tax_id"] == "11111111A"
    assert observation["clave"] == "A"
    assert observation["percibido_dinerario"] == "100.00"
    assert observation["country_code"] is None
    assert observation["transaction_date"] == "2025-12-31"
