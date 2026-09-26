"""A settled lifecycle operation always leaves its terminal notice on the workspace.

An operation that settles within its first observation makes the operation
modal dismiss itself almost as soon as it is pushed, and an operator can act
again at once. An installed run twice recorded a refusal in the operation
journal and then an empty workspace notice for minutes afterwards. This drives
the real overview, the real lifecycle door, the real composed operation
services and the real modal through that fast settlement and immediate
resubmission many times, and requires a terminal notice every time.
"""

from __future__ import annotations

import time

import pytest
from textual.widgets import Button, Input, Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceLifecycleProjectionV1
from ......core.external_constants import OutputLanguage
from ......domain.calculations.registry.authority import bundled_indexed_authority
from .....operation_composition import compose_operation_dependencies
from ....components.host import ScreenHostApp
from ....operations.modal import OperationModal
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..controller import open_workspace_read_session
from ..overview import ModeloWorkspaceOverviewScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Enough immediate resubmissions to land in the window between a settlement
#: becoming visible and its conflict lease being released; measured losing the
#: notice within the first thirty on a loaded host.
_REPETITIONS = 60
_SETTLE_SECONDS = 10.0
#: No such revision exists, so every export settles terminally within a second.
_UNKNOWN_REVISION = "f" * 64


@pytest.mark.timeout(600)
@pytest.mark.asyncio
async def test_an_immediate_resubmission_always_leaves_a_terminal_notice(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    bucket_id, repository = bucket_and_repository
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    work_unit_id = projection.target.work_unit_id
    assert work_unit_id is not None
    lost: str | None = None
    delivered = 0
    with bundled_indexed_authority().operation() as operation:
        services = compose_operation_dependencies(authority_operation=operation)
        try:
            overview = ModeloWorkspaceOverviewScreen(
                open_workspace_read_session(
                    projection,
                    lifecycle=ModeloWorkspaceLifecycleProjectionV1(target=projection.target),
                    lifecycle_actions=ModeloWorkspaceLifecycleDoor(
                        services=services,
                        work_unit_id=str(work_unit_id),
                        calculation_revision_id=_UNKNOWN_REVISION,
                    ),
                )
            )
            app = ScreenHostApp(overview)
            async with app.run_test() as pilot:
                await pilot.pause()
                for repetition in range(_REPETITIONS):
                    overview._notice("")
                    overview.query_one("#modelo-lifecycle-export-path", Input).value = f"export-{repetition}.boe"
                    overview.query_one("#modelo-lifecycle-export", Button).press()
                    deadline = time.monotonic() + _SETTLE_SECONDS
                    notice = ""
                    while time.monotonic() < deadline and not notice:
                        await pilot.pause(0.05)
                        if not isinstance(app.screen, OperationModal):
                            notice = str(overview.query_one("#modelo-lifecycle-notice", Static).content)
                    if not notice:
                        lost = (
                            f"repetition {repetition} (after {delivered} delivered): no notice within "
                            f"{_SETTLE_SECONDS:g} s, top screen {type(app.screen).__name__}, "
                            f"action in flight {overview._action_in_flight}"
                        )
                        break
                    delivered += 1
        finally:
            await services.shutdown()

    assert lost is None, lost
