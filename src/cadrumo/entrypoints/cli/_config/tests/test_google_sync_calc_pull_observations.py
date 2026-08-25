"""Google calculation-pull row-observation ingress tests."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal

import pytest

from .....adapters.outbound.google import RowSetCellEdit, RowSetEdit
from .....core.resources import resources
from .._google_sync_calc import _assemble_pull_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _snapshot():
    return resources().modelos.authority.snapshot(
        "190",
        filing_year=2025,
        period="0A",
    )


def test_pull_row_assembly_calls_the_public_snapshot_command_with_the_selected_snapshot() -> None:
    """A lower-level dispatcher bypass or substituted snapshot is structurally refused."""
    function = ast.parse(inspect.getsource(_assemble_pull_observations))
    imports = [node for node in ast.walk(function) if isinstance(node, ast.ImportFrom)]
    assert any(
        node.level == 4
        and node.module == "application.calculations"
        and [alias.name for alias in node.names] == ["assemble_observations_for_snapshot"]
        for node in imports
    )

    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert any(
        node.func.id == "assemble_observations_for_snapshot"
        and len(node.args) == 3
        and isinstance(node.args[2], ast.Name)
        and node.args[2].id == "snapshot"
        for node in calls
    )
    assert all(node.func.id != "assemble_observations_for_grouping" for node in calls)


def test_pull_row_assembly_returns_live_snapshot_assembled_observations() -> None:
    """A pulled row reaches the typed observation boundary under the live snapshot."""
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
