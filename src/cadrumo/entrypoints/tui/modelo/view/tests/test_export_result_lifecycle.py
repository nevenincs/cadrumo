"""A finished export states its facts on the workspace before the workspace moves on.

This drives the real overview, the real lifecycle door, the real composed
operation services and the real operation modal over one verified Modelo 303
revision in an isolated synthetic store. The operator fills the visible export
controls and presses Export; the statement that follows must carry the facts
the export result states -- evidence status, completeness and software identity
grade among them -- and the workspace refreshes only once the operator has
closed it.

Every expected value is independent of the code under test: the revision comes
from the fixture, the size and digest are measured on the file that landed, and
the grade and completeness follow from Modelo 303's registry, which renders an
envelope header and declares a completeness manifest.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select, Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......adapters.persistence.profile.tests.modelo_export_support import isolated_backend_context
from ......application.modelo.work_addressing import ModeloVisibleFilingTarget
from ......application.modelo.workspace import resolve_static_inspection_result
from ......application.modelo.workspace_models import (
    ModeloWorkspaceLifecycleProjectionV1,
    ModeloWorkspaceVisibleFilingTargetV1,
)
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.modelo_export_artefact import ModeloExportArtefact
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ......domain.modelos.calculation_revision import CalculationRevision
from .....operation_composition import compose_operation_dependencies
from .....tests.profile_persistence.modelo_303_export_support import build_verified_modelo_303_revision
from ....components.host import ScreenHostApp
from ....components.widgets import ContentDataTable
from ...export_result import ModeloExportResultScreen
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..controller import open_workspace_read_session
from ..overview import ModeloWorkspaceOverviewScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SETTLE_SECONDS = 120.0
_PERIOD = Period.from_year_and_code(2026, "2T")


@dataclass(frozen=True, slots=True)
class _VerifiedModelo303:
    bucket_id: str
    revision: CalculationRevision
    work_repository: WorkUnitCatalogueRepository
    operation: PinnedAuthorityOperation


@pytest.fixture
def verified_303(tmp_path: Path) -> Iterator[_VerifiedModelo303]:
    """Yield one verified Modelo 303 revision in an isolated synthetic store.

    Built before the test's event loop runs, because verification drives its
    own event loop and cannot start inside a running one.
    """
    with isolated_backend_context(tmp_path), bundled_indexed_authority().operation() as operation:
        _taxpayer_nif, bucket_id, revision, work_repository, *_repositories = build_verified_modelo_303_revision(
            operation=operation
        )
        yield _VerifiedModelo303(
            bucket_id=bucket_id, revision=revision, work_repository=work_repository, operation=operation
        )


def _overview(verified: _VerifiedModelo303, door: ModeloWorkspaceLifecycleDoor) -> ModeloWorkspaceOverviewScreen:
    projection = resolve_static_inspection_result(
        ModeloWorkspaceVisibleFilingTargetV1(
            target=ModeloVisibleFilingTarget(modelo="303", filing_year=2026, period=_PERIOD)
        ),
        bucket_id=verified.bucket_id,
        catalogue_repository=verified.work_repository,
        authority=verified.operation,
        output_language=OutputLanguage.ES,
    ).projection
    return ModeloWorkspaceOverviewScreen(
        open_workspace_read_session(
            projection,
            lifecycle=ModeloWorkspaceLifecycleProjectionV1(target=projection.target),
            lifecycle_actions=door,
        )
    )


async def _await_statement(app: App[object], pilot: Pilot[object]) -> ModeloExportResultScreen:
    """Wait for the export statement the settled operation opens, fully mounted.

    The statement focuses its close control as the last step of mounting, after
    its facts are in place, so focus there is the signal that it is readable.
    """
    deadline = time.monotonic() + _SETTLE_SECONDS
    while time.monotonic() < deadline:
        await pilot.pause(0.1)
        screen = app.screen
        if (
            isinstance(screen, ModeloExportResultScreen)
            and screen.focused is not None
            and screen.focused.id == "modelo-export-result-close"
        ):
            return screen
    raise AssertionError(f"no export statement within {_SETTLE_SECONDS:g} s; top screen {type(app.screen).__name__}")


def _facts(statement: ModeloExportResultScreen) -> dict[str, str]:
    table = statement.query_one("#modelo-export-result-table", ContentDataTable)
    return {str(row_key.value): str(table.get_row(row_key)[1]) for row_key in table.rows}


def _warnings(statement: ModeloExportResultScreen) -> str:
    return "\n".join(str(item.content) for item in statement.query_one("#modelo-export-result-warnings").query(Static))


@pytest.mark.timeout(600)
@pytest.mark.asyncio
async def test_a_complete_filing_file_export_states_its_facts_before_the_workspace_refreshes(
    verified_303: _VerifiedModelo303, tmp_path: Path
) -> None:
    """Revision, format, identity grade, evidence, completeness, path, size and digest are all shown."""
    output = tmp_path / "modelo-303-2T.txt"
    refreshed: list[bool] = []
    services = compose_operation_dependencies(authority_operation=verified_303.operation)
    try:
        door = ModeloWorkspaceLifecycleDoor(
            services=services,
            work_unit_id=verified_303.revision.work_unit_id,
            calculation_revision_id=verified_303.revision.calculation_revision_id,
            refresh_after_success=lambda: refreshed.append(True),
        )
        app = ScreenHostApp(_overview(verified_303, door))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.screen.query_one("#modelo-lifecycle-export-path", Input).value = str(output)
            app.screen.query_one("#modelo-lifecycle-export", Button).press()
            statement = await _await_statement(app, pilot)

            landed = output.read_bytes()
            assert _facts(statement) == {
                "calculation_revision_id": verified_303.revision.calculation_revision_id,
                "export_format": "fichero-boe",
                "software_identity_grade": tr("tui.modelo.export.result.software_identity_grade.development_mock"),
                "evidence_status": tr(
                    "tui.modelo.export.result.evidence_status.local_export_not_official_aeat_filing_evidence"
                ),
                "completeness": tr("tui.modelo.export.result.completeness.not_flagged"),
                "output_path": str(output),
                "byte_size": str(len(landed)),
                "file_sha256": hashlib.sha256(landed).hexdigest(),
            }
            warnings = _warnings(statement)
            assert tr("tui.modelo.export.result.warning.not_official") in warnings
            assert tr("tui.modelo.export.result.warning.development_software_identity") in warnings
            assert tr("tui.modelo.export.result.warning.completeness_unverified") not in warnings
            # The statement stands until the operator closes it; the refresh
            # that closes the workspace waits for that.
            assert refreshed == []

            statement.query_one("#modelo-export-result-close", Button).press()
            deadline = time.monotonic() + _SETTLE_SECONDS
            while not refreshed and time.monotonic() < deadline:
                await pilot.pause(0.1)
    finally:
        await services.shutdown()

    assert refreshed == [True]


@pytest.mark.timeout(600)
@pytest.mark.asyncio
async def test_a_calculation_report_export_states_that_its_completeness_is_not_assessed(
    verified_303: _VerifiedModelo303, tmp_path: Path
) -> None:
    """Choosing the report on the artefact control yields a report statement, not a filing-file one."""
    output = tmp_path / "modelo-303-2T-report.csv"
    services = compose_operation_dependencies(authority_operation=verified_303.operation)
    try:
        door = ModeloWorkspaceLifecycleDoor(
            services=services,
            work_unit_id=verified_303.revision.work_unit_id,
            calculation_revision_id=verified_303.revision.calculation_revision_id,
        )
        app = ScreenHostApp(_overview(verified_303, door))
        async with app.run_test() as pilot:
            await pilot.pause()
            artefact = app.screen.query_one("#modelo-lifecycle-export-artefact", Select)
            artefact.value = ModeloExportArtefact.CALCULATION_REPORT_CSV.value
            app.screen.query_one("#modelo-lifecycle-export-path", Input).value = str(output)
            app.screen.query_one("#modelo-lifecycle-export", Button).press()
            statement = await _await_statement(app, pilot)

            landed = output.read_bytes()
            facts = _facts(statement)
            assert facts["calculation_revision_id"] == verified_303.revision.calculation_revision_id
            assert facts["export_format"] == "csv"
            assert facts["evidence_status"] == tr(
                "tui.modelo.export.result.evidence_status.local_calculation_report_not_official_aeat_filing_evidence"
            )
            assert facts["completeness"] == tr("tui.modelo.export.result.completeness.not_assessed")
            assert facts["software_identity_grade"] == tr(
                "tui.modelo.export.result.software_identity_grade.development_mock"
            )
            assert facts["output_path"] == str(output)
            assert facts["byte_size"] == str(len(landed))
            assert facts["file_sha256"] == hashlib.sha256(landed).hexdigest()
            warnings = _warnings(statement)
            assert tr("tui.modelo.export.result.warning.not_official") in warnings
            assert tr("tui.modelo.export.result.warning.development_software_identity_of_filing_file") in warnings

            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, ModeloWorkspaceOverviewScreen)
    finally:
        await services.shutdown()
