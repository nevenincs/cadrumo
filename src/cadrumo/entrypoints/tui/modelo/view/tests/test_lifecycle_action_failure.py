"""An unregistered failure while opening a lifecycle action leaves the workspace usable.

A registered refusal already becomes a workspace notice. Any other exception
used to escape the action worker, which failed the worker and left the
overview believing an action was still in flight, so every later press was
silently ignored. The overview runs here in a real Textual pilot over a real
projection; only the lifecycle door is a stand-in, because the failure under
test is one the real door has no reason to raise on demand.
"""

from __future__ import annotations

import logging

import pytest
from textual.widgets import Button, Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceLifecycleProjectionV1
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ...lifecycle import ModeloLifecycleActionUnavailableError
from ..controller import open_workspace_read_session
from ..overview import ModeloWorkspaceOverviewScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Text an unregistered failure carries; it must never reach the operator's notice.
_FAILURE_DETAIL = "unregistered failure detail that is not operator copy"


class _FailsOnceThenRefusesActions:
    """A lifecycle door whose first calculation fails outside the registered error family."""

    def __init__(self) -> None:
        self.calls = 0

    async def calculate(self) -> object:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError(_FAILURE_DETAIL)
        raise ModeloLifecycleActionUnavailableError(
            translated_message="application.modelo.lifecycle.refusal.calculation_required"
        )


@pytest.mark.asyncio
async def test_an_unregistered_failure_is_noticed_logged_and_the_next_action_still_runs(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
    caplog: pytest.LogCaptureFixture,
) -> None:
    bucket_id, repository = bucket_and_repository
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    actions = _FailsOnceThenRefusesActions()
    overview = ModeloWorkspaceOverviewScreen(
        open_workspace_read_session(
            projection,
            lifecycle=ModeloWorkspaceLifecycleProjectionV1(target=projection.target),
            lifecycle_actions=actions,
        )
    )
    app = ScreenHostApp(overview)

    with caplog.at_level(logging.ERROR, logger="cadrumo.entrypoints.tui.modelo.view.overview"):
        async with app.run_test() as pilot:
            await pilot.pause()
            overview.query_one("#modelo-lifecycle-calculate", Button).press()
            await pilot.pause()
            await app.workers.wait_for_complete()

            failed_notice = str(overview.query_one("#modelo-lifecycle-notice", Static).content)
            assert failed_notice == tr("operation.modal.terminal.failed")
            assert _FAILURE_DETAIL not in failed_notice
            assert overview._action_in_flight is False

            overview.query_one("#modelo-lifecycle-calculate", Button).press()
            await pilot.pause()
            await app.workers.wait_for_complete()

            assert actions.calls == 2
            assert str(overview.query_one("#modelo-lifecycle-notice", Static).content) == tr(
                "application.modelo.lifecycle.refusal.calculation_required"
            )
            assert overview._action_in_flight is False
            assert app.is_running

    failures = [record for record in caplog.records if record.name == "cadrumo.entrypoints.tui.modelo.view.overview"]
    assert len(failures) == 1
    assert failures[0].levelno == logging.ERROR
    assert failures[0].exc_info is not None and failures[0].exc_info[0] is RuntimeError
    assert "RuntimeError" in failures[0].getMessage()
    assert _FAILURE_DETAIL not in failures[0].getMessage()
