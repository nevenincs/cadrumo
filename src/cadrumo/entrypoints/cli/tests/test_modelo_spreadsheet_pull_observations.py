"""Google calculation-pull row-observation ingress tests."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal

import pytest

from ....adapters.outbound.google.calc_sheets_pull_records import RowSetCellEdit, RowSetEdit
from ....application.storage.calc_sheets.engine import collect_row_sets
from ....application.storage.calc_sheets.row_set_assembly import assemble_row_sets_for_snapshot
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from .._modelo_spreadsheet_cli import _assemble_pull_observations
from ..errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _snapshot():
    return bundled_authority().snapshot(
        "190",
        filing_year=2025,
        period="0A",
    )


def _perceptor_row_set(*, row_index: int = 1, nif: str = "11111111A") -> RowSetEdit:
    return RowSetEdit(
        grouping="per_perceptor_clave",
        cells=(
            RowSetCellEdit(binding="modelo-190-perceptor-row-nif", row_index=row_index, value=nif),
            RowSetCellEdit(binding="modelo-190-perceptor-row-clave", row_index=row_index, value="A"),
            RowSetCellEdit(
                binding="modelo-190-perceptor-row-percibido-dinerario",
                row_index=row_index,
                value=Decimal("100.00"),
            ),
        ),
    )


def test_pull_row_assembly_routes_the_whole_pull_through_the_worksheet_ingress_guard() -> None:
    """A per-block call or a dispatcher bypass is structurally refused."""
    function = ast.parse(inspect.getsource(_assemble_pull_observations))
    imports = [node for node in ast.walk(function) if isinstance(node, ast.ImportFrom)]
    assert any(
        node.level == 3
        and node.module == "application.storage.calc_sheets.row_set_assembly"
        and [alias.name for alias in node.names] == ["assemble_row_sets_for_snapshot"]
        for node in imports
    )

    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    guard_calls = [
        node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "assemble_row_sets_for_snapshot"
    ]
    assert len(guard_calls) == 1
    guard_call = guard_calls[0]
    assert len(guard_call.args) == 2
    assert isinstance(guard_call.args[0], ast.Name)
    assert guard_call.args[0].id == "populated_row_sets"
    assert isinstance(guard_call.args[1], ast.Name)
    assert guard_call.args[1].id == "snapshot"

    assert all(
        not (
            isinstance(node.func, ast.Name)
            and node.func.id in {"assemble_observations_for_grouping", "assemble_observations_for_snapshot"}
        )
        for node in calls
    )
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.For)):
        assert not any(
            isinstance(inner.func, ast.Name) and inner.func.id == "assemble_row_sets_for_snapshot"
            for inner in ast.walk(loop)
            if isinstance(inner, ast.Call)
        )


def test_pull_refuses_a_binding_substituted_from_another_grouping() -> None:
    """An operator-repurposed cell reaches the CLI as a translated refusal."""
    snapshot = bundled_authority().snapshot("349", filing_year=2025, period="1T")
    first_grouping, second_grouping = collect_row_sets(snapshot.revision)
    substituted = RowSetEdit(
        grouping=first_grouping.grouping,
        cells=(RowSetCellEdit(binding=str(second_grouping.columns[0].binding), row_index=1, value="DE"),),
    )

    with pytest.raises(CliRefusedBoundaryError) as exc_info:
        _assemble_pull_observations(populated_row_sets=[substituted], snapshot=snapshot, enabled=True)

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    context = exc_info.value.context or {}
    assert context["validation_error_type"] == "row_set_ingress"
    assert context["validation_error_detail"] == "caller_binding_substitution"
    assert context["declared_grouping"] == second_grouping.grouping


def test_pull_refuses_two_blocks_claiming_the_same_row_coordinate() -> None:
    """The cross-block row-ownership collision only a whole-pull guard can see."""
    snapshot = _snapshot()
    first = _perceptor_row_set()
    second = _perceptor_row_set(nif="22222222J")

    with pytest.raises(CliRefusedBoundaryError) as exc_info:
        _assemble_pull_observations(populated_row_sets=[first, second], snapshot=snapshot, enabled=True)

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    context = exc_info.value.context or {}
    assert context["validation_error_detail"] == "row_ownership_collision"
    assert context["first_row_set_index"] == 0
    assert context["second_row_set_index"] == 1


def test_pull_accepts_two_blocks_on_distinct_row_coordinates() -> None:
    """Detector teeth: the healthy multi-block pull still assembles."""
    snapshot = _snapshot()

    groupings, observation_count = _assemble_pull_observations(
        populated_row_sets=[_perceptor_row_set(row_index=1), _perceptor_row_set(row_index=2, nif="22222222J")],
        snapshot=snapshot,
        enabled=True,
    )

    assert observation_count == 2
    assert [entry["grouping"] for entry in groupings] == ["per_perceptor_clave", "per_perceptor_clave"]


def test_worksheet_ingress_guard_raises_a_registry_refusal_the_cli_maps() -> None:
    """The guard's own error type is what the CLI refusal path translates."""
    snapshot = _snapshot()
    with pytest.raises(RegistryValidationError):
        assemble_row_sets_for_snapshot([_perceptor_row_set(), _perceptor_row_set()], snapshot)


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
