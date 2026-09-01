"""Mounted-surface proofs for the C3 editor screen.

Split from ``test_c3_editor_accessibility`` because these run a real Textual
app and carry the integration/entrypoint markers, while that module's proofs
are headless unit tests. A file-level ``pytestmark`` cannot say both, and
tagging one test with two contradictory lane markers would leave it selected
by neither lane in the way its author expected.

The geometry, language and theme axes are taken from the SAME shared
denominators the C2 cohort uses -- ``SUPPORTED_TERMINAL_SIZES``,
``OutputLanguage``, and the two shipped theme names -- never restated here.
Two accessibility matrices asserting different definitions of "supported"
would let a surface pass one and fail the other with nothing to say which is
authoritative.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.edit.screen`
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from textual.widgets import Input, Static

from .....application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from .....application.modelo.work_addressing import ModeloExactWorkUnitTarget
from .....application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
from .....application.operations.registry import OperationSchemaIdentityV1
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import SUPPORTED_OUTPUT_LANGUAGES, tr
from .....core.period import Period
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.temporal import select_revision
from .....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from .....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZE_IDS, SUPPORTED_TERMINAL_SIZES
from ...components.host import ScreenHostApp
from ...components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..edit.controller import ModeloEditController
from ..edit.screen import EditorLocaleMismatchError, ModeloEditScreen, casilla_input_id

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_MODELO = "130"
_FILING_YEAR = 2026
_DIGEST = "a" * 64
_SENTINEL = "ZZQX-SENTINEL-9182736455-QXZZ"
"""A lexeme that cannot parse, so a refusal is unambiguous."""


def _identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    modelo = ModeloCode(_MODELO)
    revision_id = select_revision(
        bundled_authority().validate_modelo(modelo), filing_year=_FILING_YEAR, period="1T"
    ).id
    now = datetime(2026, 1, 10, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=modelo, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-1T",
        created_at=now,
        updated_at=now,
    )


def _hosted(locale: OutputLanguage = OutputLanguage.ES) -> tuple[ScreenHostApp[None], ModeloEditController]:
    """Admit a route and host its editor exactly as production would.

    Composes the shared :class:`ScreenHostApp` rather than a local host, so
    the matrix proves what an operator will actually see: a test-only host
    would omit the tokenised base CSS and the awaited push the shared one
    carries.
    """
    from .....application.modelo.edit_services import (
        modelo_edit_request_schema_identity,
        modelo_edit_result_schema_identity,
    )

    work_unit = _work_unit()
    catalogues = (WorkUnitCatalogue.from_work_units((work_unit,)), CalculationRevisionCatalogue())
    controller = ModeloEditController.for_locale(locale)
    admitted = controller.admit(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
        ),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        bucket_id=work_unit.bucket_id,
        work_catalogue=catalogues[0],
        calculation_catalogue=catalogues[1],
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.calculate",
            definition_contract_digest=_DIGEST,
            request_schema=modelo_edit_request_schema_identity(),
            result_schema=modelo_edit_result_schema_identity(),
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=_identity(),
            financial_operand_schema=_identity(),
        ),
    )
    assert admitted, f"admission refused: {controller.refusal_message_key}"
    return ScreenHostApp(ModeloEditScreen(controller, catalogues=lambda: catalogues)), controller


@pytest.mark.asyncio
async def test_the_editor_mounts_one_control_per_permitted_casilla_and_no_more() -> None:
    """The permitted surface is the whole denominator of what can be typed into.

    Checked by widget on the RUNNING screen rather than by reading the mount
    code: a screen could acquire an input through a composed widget without
    the mount path creating one, so what the module writes is not the
    property that matters.
    """
    app, controller = _hosted()

    async with app.run_test() as pilot:
        await pilot.pause()
        permitted = controller.fields().casilla_ids()
        assert permitted, "the real M130 admission permits no scalar; this proof would be vacuous"
        mounted = {widget.id for widget in app.screen.query(Input)}
        assert mounted == {casilla_input_id(casilla_id) for casilla_id in permitted}


@pytest.mark.asyncio
async def test_a_refused_lexeme_returns_focus_to_the_field_that_carried_it() -> None:
    """Focus is the error channel, so the operator never hunts for the bad field.

    Two fields are in play, and focus is moved AWAY before the refusal, so
    passing requires the screen to actively return it -- not merely to leave
    focus where it already was.
    """
    app, controller = _hosted()

    async with app.run_test() as pilot:
        await pilot.pause()
        casilla_ids = controller.fields().casilla_ids()
        assert len(casilla_ids) >= 2, (
            "this test stages a focus move BETWEEN two fields, so an admission permitting fewer "
            "than two scalars makes it meaningless. Asserted rather than skipped: the condition is "
            "constant for a fixed fixture address, so a skip here never fires and would begin "
            "firing silently the day the fixture changed -- turning a real proof into a green that "
            "measures nothing, with no announcement."
        )
        target = app.screen.query_one(f"#{casilla_input_id(casilla_ids[0])}", Input)
        other = app.screen.query_one(f"#{casilla_input_id(casilla_ids[1])}", Input)
        other.focus()
        await pilot.pause()
        assert app.screen.focused is other

        target.value = _SENTINEL
        await target.action_submit()
        await pilot.pause()

        assert controller.fields().state(casilla_ids[0]).is_unresolved
        assert app.screen.focused is target, "a refused lexeme must return focus to its own field"


@pytest.mark.asyncio
async def test_an_accepted_lexeme_leaves_focus_alone() -> None:
    """The counterpart: focus is only seized to report a problem.

    Without this, the focus test above would pass equally well against a
    screen that grabbed focus on every keystroke, which would fight the
    operator moving through the form.
    """
    app, controller = _hosted()

    async with app.run_test() as pilot:
        await pilot.pause()
        casilla_ids = controller.fields().casilla_ids()
        assert len(casilla_ids) >= 2, (
            "this test stages a focus move BETWEEN two fields, so an admission permitting fewer "
            "than two scalars makes it meaningless. Asserted rather than skipped: the condition is "
            "constant for a fixed fixture address, so a skip here never fires and would begin "
            "firing silently the day the fixture changed -- turning a real proof into a green that "
            "measures nothing, with no announcement."
        )
        target = app.screen.query_one(f"#{casilla_input_id(casilla_ids[0])}", Input)
        other = app.screen.query_one(f"#{casilla_input_id(casilla_ids[1])}", Input)
        other.focus()
        await pilot.pause()

        target.value = "100.00"
        await target.action_submit()
        await pilot.pause()

        assert controller.fields().state(casilla_ids[0]).is_unresolved is False
        assert app.screen.focused is other, "an accepted value must not steal focus"


@pytest.mark.asyncio
@pytest.mark.parametrize("size", SUPPORTED_TERMINAL_SIZES, ids=SUPPORTED_TERMINAL_SIZE_IDS)
async def test_the_editor_renders_at_every_supported_geometry(size: tuple[int, int]) -> None:
    """A narrow terminal must not drop the controls or crash the mount.

    The floor matters most: it is where an overflowing layout starts hiding
    controls rather than merely looking cramped, and a hidden input is an
    edit the operator cannot make.
    """
    app, controller = _hosted()

    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert app.screen.query(Static), f"the editor rendered nothing at {size}"
        assert len(app.screen.query(Input)) == len(controller.fields().casilla_ids()), (
            f"a control was dropped at {size}"
        )


@pytest.mark.asyncio
async def test_the_editor_renders_in_every_shipped_language() -> None:
    """Every shipped catalogue must carry this surface, not just the two authored first.

    Driven through ``override_settings`` because ``tr`` resolves the ambient
    output language, while the controller parses lexemes in the language it
    was admitted for. Both are moved together here, which is the only
    combination the screen permits -- see the mismatch proof below.

    Mounting without raising is necessary but NOT sufficient, so this also
    compares the rendered titles. A missing key raises at render, but a
    catalogue that silently served the Spanish string for every language
    would mount cleanly four times and still be wrong; requiring distinct
    renderings is what catches that.
    """
    titles: dict[str, str] = {}
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            app, _ = _hosted(OutputLanguage(language))
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                header = app.screen.query_one("#edit-header", Static)
                rendered = str(header.content)
                assert rendered, f"the editor header rendered nothing under {language}"
                assert "flows.modelo_edit" not in rendered, (
                    f"the header rendered its own key under {language}, so that catalogue has no entry"
                )
                titles[language] = rendered

    assert len(set(titles.values())) > 1, (
        f"every language rendered the same title {titles}, so the catalogue is not being consulted"
    )


@pytest.mark.asyncio
async def test_the_editor_toggles_between_both_shipped_themes() -> None:
    """The shared appearance toggle reaches the editor, rather than a local palette."""
    app, _ = _hosted()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        first = app.theme
        await pilot.press("f3")
        await pilot.pause()
        assert app.theme != first
        assert {first, app.theme} == {CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME}


@pytest.mark.asyncio
async def test_leaving_with_staged_work_reports_rather_than_discarding_it() -> None:
    """Escape must not silently throw away an edit the operator never abandoned."""
    app, controller = _hosted()

    async with app.run_test() as pilot:
        await pilot.pause()
        casilla_id = controller.fields().casilla_ids()[0]
        target = app.screen.query_one(f"#{casilla_input_id(casilla_id)}", Input)
        target.value = "42.00"
        await target.action_submit()
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert app.screen is not None, "escape discarded the screen while work was staged"
        assert controller.fields().state(casilla_id).touched, "the staged edit must survive the refused exit"


@pytest.mark.asyncio
async def test_the_editor_refuses_to_display_one_language_and_parse_another() -> None:
    """A form that reads numbers in a language it is not showing must not render.

    This is the failure the locale axis exists to catch, and it is invisible
    by construction: "1.234,56" is a valid spelling in more than one
    language, so a form displaying Hungarian while parsing Spanish accepts
    the operator's typing and records a different amount than the one they
    believe they entered. There is no error for the operator to notice.

    Refused at mount rather than reported, because a divergence means the
    route was built with the wrong locale -- a programming error the operator
    cannot act on.
    """
    app, _ = _hosted(OutputLanguage.ES)

    with (
        override_settings(cadrumo_output_language=OutputLanguage.HU.value),
        pytest.raises(EditorLocaleMismatchError, match="amounts would be read"),
    ):
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()


@pytest.mark.asyncio
async def test_a_stale_conflict_reaches_the_operator_as_a_visible_notice() -> None:
    """Drift the operator cannot see is drift they will submit over.

    The controller's stale-conflict state is already proven where it is
    decided, but that proof stops at a BOOLEAN. Between the flag and the
    operator sits the notice, which can say only one thing at a time and
    returns early on unresolved fields -- so the flag can be correct while
    the screen says nothing, and every other editor gate here (geometry,
    locale, theme, control count) passes either way because none of them
    read this widget.

    Driven entirely through the operator's own path: the drift is introduced
    behind the screen, then a value is typed into a real input and submitted,
    which is what refreshes the notice in production. Calling the refresh
    directly would have proven the renderer while leaving the question of
    whether anything ever CALLS it unanswered.

    The typed value is deliberately one that RESOLVES. An unresolved field
    wins the notice and would mask the conflict, which is the actual ordering
    hazard, and it is why this asserts the conflict text specifically rather
    than settling for a non-empty notice.
    """
    app, controller = _hosted()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        casilla_id = controller.fields().casilla_ids()[0]

        drifted = controller.refresh(
            work_catalogue=WorkUnitCatalogue(),
            calculation_catalogue=CalculationRevisionCatalogue(),
        )
        assert drifted, "an emptied work catalogue must be reported as drift"
        assert controller.in_stale_conflict is True

        field = app.screen.query_one(f"#{casilla_input_id(casilla_id)}", Input)
        field.focus()
        await pilot.pause()
        field.value = "77.00"
        await pilot.press("enter")
        await pilot.pause()

        painted = str(app.screen.query_one("#edit-notice", Static).content)
        assert painted.strip(), "a stale conflict must not leave the notice blank"
        assert painted == tr("flows.modelo_edit.stale_conflict"), (
            f"the operator was shown {painted!r} instead of the stale-conflict notice"
        )
        app.exit(None)
