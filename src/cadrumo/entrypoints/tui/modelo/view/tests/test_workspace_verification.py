"""Real Textual-pilot proof for the modelo.workspace.verification destination.

The properties under test are the two the row turns on: that no second
readiness verdict is derived, and that unmeasured axes are DISCLOSED
distinctly from measured-and-empty ones.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ....components.widgets import ContentDataTable
from ..controller import ModeloWorkspaceReadSession, admit_workspace_session
from ..verification import ModeloWorkspaceVerificationScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES))
    assert refusal is None, f"expected an admitted projection, got: {refusal}"
    assert session is not None
    return session


@pytest.mark.asyncio
async def test_unmeasured_findings_are_distinguished_from_measured_and_empty(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """ "Nobody looked" and "looked and found nothing" get different text.

    Both would otherwise render as an empty findings table, which collapses
    a claim about the ADMISSION into a claim about the FILING.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert session.projection.work_review.review is None

    app = ScreenHostApp(ModeloWorkspaceVerificationScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        disposition = app.screen.query_one("#workspace-verification-findings-disposition", Static)
        assert str(disposition.content) == tr("flows.modelo_workspace_verification.findings_unmeasured")
        assert str(disposition.content) != tr("flows.modelo_workspace_verification.findings_none")


@pytest.mark.asyncio
async def test_unmeasured_readiness_is_stated_and_no_axes_table_is_mounted(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """An absent readiness produces a statement, never a table of blank axes."""
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert session.projection.readiness is None

    app = ScreenHostApp(ModeloWorkspaceVerificationScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        disposition = app.screen.query_one("#workspace-verification-readiness-disposition", Static)
        assert str(disposition.content) == tr("flows.modelo_workspace_verification.readiness_unmeasured")
        assert not app.screen.query("#workspace-verification-readiness-table")


@pytest.mark.asyncio
async def test_absent_evidence_and_recovery_actions_are_stated_not_shown_empty(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Canary: asserts the producers really carry none before checking the text.

    If a producer ever begins populating evidence or recovery actions, this
    test fails rather than the screen quietly continuing to claim none are
    supplied.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert all(capability.evidence == () for capability in session.projection.capabilities)
    assert all(capability.facts == () for capability in session.projection.capabilities)
    assert all(capability.recovery_action is None for capability in session.projection.capabilities)

    app = ScreenHostApp(ModeloWorkspaceVerificationScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-verification-evidence-not-carried", Static)
        assert str(notice.content) == tr("flows.modelo_workspace_verification.evidence_not_carried")


@pytest.mark.asyncio
async def test_the_screen_shows_only_its_own_capability_not_the_whole_denominator(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The complete denominator belongs to overview; repeating it duplicates a closed set.

    One capability line, and no table of all five. The line must actually
    name this screen's own capability rather than merely existing, so the
    producer attribution is asserted too -- an empty or generic line would
    otherwise satisfy a presence-only check.
    """
    from ......application.modelo.workspace_models import ModeloWorkspaceCapabilityName

    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    verification = next(
        capability
        for capability in session.projection.capabilities
        if capability.capability is ModeloWorkspaceCapabilityName.VERIFICATION_READINESS
    )

    app = ScreenHostApp(ModeloWorkspaceVerificationScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = str(app.screen.query_one("#workspace-verification-capability", Static).content)
        assert verification.disposition.value in rendered
        assert verification.producer in rendered
        assert len(app.screen.query(ContentDataTable)) == 0


@pytest.mark.asyncio
async def test_the_destination_offers_no_editing_affordance(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Verification is a read destination like every other C2 screen."""
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceVerificationScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for editing_widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(editing_widget), (
                f"the read destination mounted an editing widget: {editing_widget.__name__}"
            )
