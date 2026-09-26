"""Real Textual-pilot proof for the modelo.workspace.verification destination.

The properties under test are the two the row turns on: that no second
readiness verdict is derived, and that unmeasured axes are DISCLOSED
distinctly from measured-and-empty ones.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceCapabilityName
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ....components.widgets import ContentDataTable
from ..controller import ModeloWorkspaceReadSession, open_workspace_read_session
from ..models import disposition_label, evidence_reference_label, recovery_action_label
from ..verification import ModeloWorkspaceVerificationScreen
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    return open_workspace_read_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection)


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
async def test_the_capability_evidence_line_says_what_the_producer_carries(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The line reports the capability's own payload, in both directions.

    Read the verification capability first and decide from it which sentence
    the screen owes, rather than pinning one outcome: a static inspection over
    a target with no work unit names no addressable step, while one over an
    existing work unit does, and the screen must be right either way. Asserting
    only the empty sentence would pass on a screen that had stopped reading the
    payload at all.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    capability = next(
        candidate
        for candidate in session.projection.capabilities
        if candidate.capability is ModeloWorkspaceCapabilityName.VERIFICATION_READINESS
    )
    expected_parts = [evidence_reference_label(reference) for reference in capability.evidence]
    if capability.recovery_action is not None:
        expected_parts.append(recovery_action_label(capability.recovery_action))
    expected = (
        tr("flows.modelo_workspace_verification.evidence_none")
        if not expected_parts
        else tr(
            "flows.modelo_workspace_verification.evidence_carried",
            entries="; ".join(expected_parts),
        )
    )

    app = ScreenHostApp(ModeloWorkspaceVerificationScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-verification-evidence", Static)
        assert str(notice.content) == expected


@pytest.mark.asyncio
async def test_the_capability_facts_name_the_registry_family_behind_the_answer(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The explanation is real registry data, not a decorative empty tuple.

    The verification capability rests on the revision's own
    ``verification_expectations`` family, and a static inspection does not
    carry that family -- so the source disposition is unmeasured rather than a
    fabricated empty one, and the fact naming the family is still present.
    """
    bucket_id, repository = bucket_and_repository
    capability = next(
        candidate
        for candidate in _session(bucket_id, repository).projection.capabilities
        if candidate.capability is ModeloWorkspaceCapabilityName.VERIFICATION_READINESS
    )

    facts = {fact.name: fact.value.value for fact in capability.facts}

    assert facts["source_family"] == "verification_expectations"
    assert "declared_members" not in facts
    assert capability.source_disposition is None


@pytest.mark.asyncio
async def test_the_screen_shows_only_its_own_capability_not_the_whole_denominator(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The complete denominator belongs to overview; repeating it duplicates a closed set.

    One capability line, and no table of the whole denominator. The line must
    say this capability's own disposition rather than merely exist, and the
    producer attribution must be kept -- in the collapsed technical details --
    so an empty or generic line cannot satisfy a presence-only check.
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
        assert disposition_label(verification.disposition) in rendered
        technical = app.screen.query_one("#workspace-verification-technical-table", ContentDataTable)
        producer = technical.get_row(f"producer.{verification.capability.value}")
        assert producer[1] == f"{verification.producer_owner}.{verification.producer}"
        assert [table.id for table in app.screen.query(ContentDataTable)] == ["workspace-verification-technical-table"]


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
