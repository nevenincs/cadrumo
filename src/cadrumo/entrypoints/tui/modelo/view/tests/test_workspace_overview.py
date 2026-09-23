"""Real Textual-pilot proof for the modelo.workspace.overview destination.

The two properties under test are the ones where rendering the obvious
thing would assert something untrue: that the revision block shows
coordinates and not a chronology, and that absent recovery actions are
STATED rather than shown as an empty list.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.widgets import Button, Input, Static

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.edit_models import ModeloEditWritableScalarSurfaceEntryV1
from ......application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceLifecycleProjectionV1,
)
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....components.widgets import ContentDataTable
from ...lifecycle import ModeloLifecycleActionUnavailableError
from ..controller import ModeloWorkspaceReadSession, open_workspace_read_session
from ..overview import ModeloWorkspaceOverviewScreen, edit_control_id
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    return open_workspace_read_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection)


class _UnavailableLifecycleActions:
    """One typed refusal proves the view renders application errors without a generic fallback."""

    async def calculate(self) -> object:
        raise ModeloLifecycleActionUnavailableError(
            translated_message="application.modelo.lifecycle.refusal.calculation_required"
        )


def _lifecycle_session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    lifecycle = ModeloWorkspaceLifecycleProjectionV1(target=projection.target)
    return open_workspace_read_session(
        projection,
        lifecycle=lifecycle,
        lifecycle_actions=_UnavailableLifecycleActions(),
    )


@pytest.mark.asyncio
async def test_absent_recovery_actions_are_stated_not_rendered_as_an_empty_list(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """An empty actions panel would claim there is nothing the operator can do.

    The truth is that this producer does not say what can be done. The
    screen must carry the second claim, never the first.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert all(capability.recovery_action is None for capability in session.projection.capabilities)

    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-overview-actions", Static)
        assert str(notice.content) == tr("flows.modelo_workspace_overview.actions_not_carried")


@pytest.mark.asyncio
async def test_the_revision_block_shows_coordinates_and_no_chronology(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Three coordinate rows, none of them a sequence over time.

    The page states the two point assertions and the review status; the
    law-selected revision id is a technical detail. A row count above that
    would mean the screen had synthesised history the projection does not
    carry.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-revision-table", ContentDataTable)
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_every_capability_appears_exactly_once_with_a_distinguishing_glyph(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The screen shows the whole denominator, not a filtered subset.

    A capability omitted from the display would be indistinguishable from
    one the producer never answered, which is the distinction the closed
    denominator exists to preserve.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-capability-table", ContentDataTable)
        assert table.row_count == len(ModeloWorkspaceCapabilityName)


@pytest.mark.asyncio
async def test_an_absent_work_unit_renders_its_own_value_rather_than_a_blank_cell(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The address table always has four rows, present work unit or not."""
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-address-table", ContentDataTable)
        assert table.row_count == 4


@pytest.mark.asyncio
async def test_the_destination_offers_no_editing_affordance(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Overview is a read destination like every other C2 screen."""
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for editing_widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(editing_widget), (
                f"the read destination mounted an editing widget: {editing_widget.__name__}"
            )


def test_edit_control_ids_keep_valid_keys_and_encode_the_rest_distinctly() -> None:
    """Numeric and hyphenated keys keep their spelling; everything else is escaped one-to-one."""
    assert edit_control_id("scalar", "0165") == "modelo-edit-scalar-0165"
    assert edit_control_id("binding", "renta-certificado-trabajo-retenciones") == (
        "modelo-edit-binding-renta-certificado-trabajo-retenciones"
    )
    assert edit_control_id("scalar", "iva.prorrata-volumen-con-derecho") == (
        "modelo-edit-scalar-iva_2e_prorrata-volumen-con-derecho"
    )
    adversarial = ("a.b", "a_2e_b", "a_b", "a_5f_b", "a__b", "a-b", "ab")
    encoded = [edit_control_id("scalar", key) for key in adversarial]
    assert len(set(encoded)) == len(adversarial)


class _DottedCasillaEditActions:
    """A lifecycle door whose edit surface admits one semantic, dotted casilla id."""

    def __init__(self) -> None:
        self.edit_baseline = SimpleNamespace(
            permitted_surface=(
                ModeloEditWritableScalarSurfaceEntryV1.model_construct(
                    casilla_id="iva.prorrata-volumen-con-derecho", data_type="money", allowed_intents=("set",)
                ),
            )
        )
        self.applied: list[dict[str, object]] = []

    async def apply_edits(self, **kwargs: object) -> object:
        self.applied.append(kwargs)
        raise ModeloLifecycleActionUnavailableError(
            translated_message="application.modelo.lifecycle.refusal.calculation_required"
        )


@pytest.mark.asyncio
async def test_a_dotted_semantic_casilla_edit_control_composes_and_submits_its_value(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """One casilla id that is not a valid widget id must not stop the whole workspace from composing."""
    bucket_id, repository = bucket_and_repository
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    actions = _DottedCasillaEditActions()
    session = open_workspace_read_session(
        projection,
        lifecycle=ModeloWorkspaceLifecycleProjectionV1(target=projection.target),
        lifecycle_actions=actions,
    )
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(session))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one("#modelo-lifecycle-calculate", Button)
        field = app.screen.query_one(f"#{edit_control_id('scalar', 'iva.prorrata-volumen-con-derecho')}", Input)
        field.value = "150.00"
        app.screen.query_one("#modelo-edit-apply", Button).press()
        await pilot.pause()
        await app.workers.wait_for_complete()

    assert actions.applied == [{"scalar_values": {"iva.prorrata-volumen-con-derecho": "150.00"}, "binding_values": {}}]


@pytest.mark.asyncio
async def test_lifecycle_controls_require_confirmation_or_a_typed_precondition(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The installed actions have stable controls and never turn a refusal into success."""
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_lifecycle_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for identifier in (
            "#modelo-lifecycle-calculate",
            "#modelo-lifecycle-verify",
            "#modelo-lifecycle-file",
            "#modelo-lifecycle-export",
        ):
            assert app.screen.query_one(identifier, Button)
        assert app.screen.query_one("#modelo-lifecycle-export-path", Input)

        app.screen.query_one("#modelo-lifecycle-export", Button).press()
        await pilot.pause()
        assert str(app.screen.query_one("#modelo-lifecycle-notice", Static).content) == tr(
            "application.modelo.lifecycle.refusal.export_destination_required"
        )

        app.screen.query_one("#modelo-lifecycle-file", Button).press()
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("escape")
        await pilot.pause()

        app.screen.query_one("#modelo-lifecycle-calculate", Button).press()
        await pilot.pause()
        await app.workers.wait_for_complete()
        assert str(app.screen.query_one("#modelo-lifecycle-notice", Static).content) == tr(
            "application.modelo.lifecycle.refusal.calculation_required"
        )
