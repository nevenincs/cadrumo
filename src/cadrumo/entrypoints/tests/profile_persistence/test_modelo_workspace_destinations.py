"""The installed Modelo workspace pages render a calculated declaration's values.

Driven through the production launcher reader over real encrypted storage and a
real calculation, then through the real destination screens: the proof that the
graded admission's work review reaches the operator, not a projection built for
the test. An uncalculated declaration in the same bucket is read beside it, so a
refusal for one unit is shown to stay with that unit.
"""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Static

from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceGradedSnapshotScopeV1,
    ModeloWorkspaceRefusalCode,
)
from cadrumo.application.workbench_generation import ModeloWorkspaceProjectedReadV1
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_NET_RESULT_CASILLA,
    Repos,
    calculation_ports_for_test,
    seed_work_unit,
)
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.launcher import _modelo_projection_reader
from cadrumo.entrypoints.tui.modelo.view.controller import open_workspace_read_session
from cadrumo.entrypoints.tui.modelo.view.inputs import ModeloWorkspaceInputsScreen
from cadrumo.entrypoints.tui.modelo.view.results import ModeloWorkspaceResultsScreen
from cadrumo.entrypoints.tui.modelo.view.verification import ModeloWorkspaceVerificationScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def _calculated_and_uncalculated(repos: Repos) -> tuple[WorkUnit, WorkUnit]:
    work_repo, calculation_repo, _, _, bucket_event_repo = repos
    calculated = seed_work_unit(work_repo)
    uncalculated = seed_work_unit(work_repo, period="2T")
    with calculation_ports_for_test(
        bucket_id=calculated.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    ) as ports:
        calculate_modelo_revision(
            calculated.work_unit_id,
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=ports,
        )
    units = work_repo.load().work_units
    return units[calculated.work_unit_id], units[uncalculated.work_unit_id]


def _reads(repos: Repos) -> tuple[ModeloWorkspaceProjectedReadV1, ModeloWorkspaceProjectedReadV1]:
    calculated, uncalculated = _calculated_and_uncalculated(repos)
    with bundled_indexed_authority().operation() as operation:
        project = _modelo_projection_reader(operation)
        return project(calculated), project(uncalculated)


def test_the_reader_admits_a_calculated_unit_with_its_review_and_keeps_the_neighbour_refusal_apart(
    repos: Repos,
) -> None:
    calculated, uncalculated = _reads(repos)

    assert calculated.graded_refusal is None
    assert isinstance(calculated.projection.admission, ModeloWorkspaceGradedSnapshotScopeV1)
    assert calculated.projection.work_review.disposition is ModeloWorkspaceCapabilityDisposition.AVAILABLE

    assert uncalculated.graded_refusal is not None
    assert uncalculated.graded_refusal.code is ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE
    assert uncalculated.projection.target.work_unit_id != calculated.projection.target.work_unit_id


@pytest.mark.asyncio
async def test_results_lists_the_calculated_boxes_with_their_values(repos: Repos) -> None:
    calculated, _ = _reads(repos)
    app = ScreenHostApp(ModeloWorkspaceResultsScreen(open_workspace_read_session(calculated.projection)))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query("#workspace-results-not-applicable")
        table = app.screen.query_one("#workspace-results-table", DataTable)
        rows = {str(table.get_row_at(index)[0]): str(table.get_row_at(index)[1]) for index in range(table.row_count)}

    assert str(M130_NET_RESULT_CASILLA) in rows
    assert rows[str(M130_NET_RESULT_CASILLA)]


@pytest.mark.asyncio
async def test_inputs_state_each_box_s_declared_kind_rather_than_unmeasured(repos: Repos) -> None:
    calculated, _ = _reads(repos)
    app = ScreenHostApp(ModeloWorkspaceInputsScreen(open_workspace_read_session(calculated.projection)))
    unmeasured = tr("flows.modelo_workspace_inputs.input_kind_unmeasured")

    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query("#workspace-inputs-values-disposition")
        kinds = [
            str(cell)
            for table in app.screen.query(DataTable)
            if str(table.id).startswith("workspace-inputs-table-")
            for index in range(table.row_count)
            for cell in table.get_row_at(index)[-1:]
        ]

    assert kinds
    assert unmeasured not in kinds


@pytest.mark.asyncio
async def test_verification_reports_the_review_s_findings_rather_than_unmeasured(repos: Repos) -> None:
    calculated, _ = _reads(repos)
    app = ScreenHostApp(ModeloWorkspaceVerificationScreen(open_workspace_read_session(calculated.projection)))

    async with app.run_test() as pilot:
        await pilot.pause()
        findings = app.screen.query("#workspace-verification-findings-disposition")
        disposition = str(findings.first(Static).content) if findings else ""

    assert disposition != tr("flows.modelo_workspace_verification.findings_unmeasured")
