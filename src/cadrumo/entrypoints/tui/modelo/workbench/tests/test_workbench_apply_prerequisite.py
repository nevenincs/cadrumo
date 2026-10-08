"""A refused Apply leads to its source while staged values keep their own meaning."""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.widgets import Input, Static

from ......application.modelo.source_policy import SourceFamily
from ......application.modelo.value_presentation import format_casilla_value
from ......application.modelo.work_form_models import (
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormValueSource,
    address_key,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.period import Period
from ......domain.modelos.verification_report import VerificationCompletenessStatus
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..casilla_list_models import CasillaListEntry
from ..casilla_list_values import row_value_text
from ..issue_scale import verdict_text
from ..issues import WorkbenchIssuesScreen
from ..ports import WorkbenchApplyPrerequisite
from ..progress import NextAction
from ..screen import ModeloWorkbenchScreen
from ..session import WorkbenchEditSession
from .editor_panel import open_panel
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, fed_by, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("width", [80, 120])
async def test_the_named_recovery_key_leads_to_the_source_box_and_keeps_the_staged_answer(
    language: OutputLanguage,
    width: int,
) -> None:
    form = replace_fields(
        synthetic_form(),
        {
            "01": {
                "origin": ModeloFormOrigin.IMPORTED,
                "value": Decimal(0),
                "editability": ModeloFormEditability.OVERRIDABLE_SOURCE,
                "bindings": (fed_by("prior-general-loss", BindingSourceKind.PREVIOUS_FILING),),
                "source": ModeloFormValueSource(
                    family=SourceFamily.EARLIER_FILINGS,
                    earlier_filings=(
                        ModeloFormEarlierFiling(modelo="100", period=Period.from_year_and_code(2024, "0A")),
                    ),
                ),
            }
        },
    ).model_copy(update={"operator_entries_known": False})
    source = next(field for field in form.fields() if field.box == "01")
    answer = next(field for field in form.fields() if field.box == "06")
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 24)) as pilot:
            await pilot.pause()
            assert screen._session.stage_value(answer, Decimal(42), "42") is None
            screen._refresh_after_staging()
            screen._apply_prerequisite = WorkbenchApplyPrerequisite(
                address=source.address,
                calculation_revision_id=form.calculation_revision_id,
                source_boxes=("1391",),
            )
            assert screen._state_apply_prerequisite()
            await pilot.pause()
            assert str(screen.query_one("#wb-next", Static).render()).endswith("[i]")
            assert screen.active_bindings["i"].binding.show
            assert "[01]" in str(screen.query_one("#wb-notice", Static).render())
            await pilot.press("i")
            await pilot.pause()
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            diagnostic = issues._lines[0]
            assert diagnostic.key == address_key(source.address)
            assert diagnostic.technical == "" and "prior-general-loss" not in diagnostic.message
            assert "[1391]" in diagnostic.message and "2024" in diagnostic.message
            assert diagnostic.action == tr("tui.modelo.workbench.apply_prerequisite.action")
            assert diagnostic.action_targets_box
            await pilot.press("enter")
            await pilot.pause()
            listing = screen.query_one(CasillaList)
            assert listing.highlighted is not None and listing.highlighted.field.address == source.address
            painted = "\n".join(listing.render_line(y).text for y in range(listing.scrollable_content_region.height))
            assert "[01]" in painted
            await pilot.press("enter")
            await pilot.pause()
            panel = open_panel(app.screen)
            assert panel is not None and not panel.read_only
            assert panel.field.value == Decimal(0) and panel.field.origin is ModeloFormOrigin.IMPORTED
            assert len(screen.staged_changes) == 1 and screen.staged_changes[0].value == Decimal(42)
            await pilot.press("escape")
            await pilot.pause()
            screen._session.discard()
            screen._refresh_after_staging()
            assert screen._active_apply_prerequisite() is None
            assert screen._load is not None
            assert screen._progress(screen._load).next_action is not NextAction.APPLY
            app.exit(None)


@pytest.mark.parametrize("origin", [ModeloFormOrigin.OPTIONAL_EMPTY, ModeloFormOrigin.NEEDS_INPUT])
@pytest.mark.parametrize("value", [False, Decimal(0), Decimal(42)])
def test_a_concrete_typed_set_replaces_only_the_saved_absence_qualifier(
    origin: ModeloFormOrigin, value: ModeloFormScalar
) -> None:
    field = form_field("06", "Answer", origin)
    session = WorkbenchEditSession(OutputLanguage.EN)
    assert session.stage_value(field, value, str(value)) is None
    display = session.display()[address_key(field.address)]
    entry = CasillaListEntry(
        field,
        staged_text=display.text,
        previous_text=display.previous_text,
        staged_concrete_value=display.concrete_value,
    )
    assert entry.origin_words == "" and entry.origin_mark.strip() == ""
    assert entry.attention is not None and row_value_text(entry, OutputLanguage.EN) == str(value)
    assert field.value is None and field.origin is origin and entry.previous_text is not None


def test_a_staged_clear_or_restore_keeps_its_own_semantics_instead_of_becoming_a_concrete_set() -> None:
    session = WorkbenchEditSession(OutputLanguage.EN)
    with override_settings(cadrumo_output_language="en"):
        declared = form_field("06", "Answer", ModeloFormOrigin.ENTERED, Decimal(42))
        assert session.stage_clear(declared) is None
        clear = session.display()[address_key(declared.address)]
        assert not clear.concrete_value and clear.text == tr("tui.modelo.workbench.staged.clear")
        overridden = declared.model_copy(
            update={"origin": ModeloFormOrigin.OVERRIDES_SOURCE, "editability": ModeloFormEditability.EDITABLE_OVERRIDE}
        )
        assert session.stage_restore(overridden) is None
        restore = session.display()[address_key(overridden.address)]
        assert not restore.concrete_value and restore.text == tr("tui.modelo.workbench.staged.restore")
        empty = form_field("07", "Empty", ModeloFormOrigin.OPTIONAL_EMPTY)
        assert session.stage_value(empty, None, "") is None
        absent = session.display()[address_key(empty.address)]
        entry = CasillaListEntry(empty, staged_text=absent.text, staged_concrete_value=absent.concrete_value)
        assert not absent.concrete_value and entry.origin_words


@pytest.mark.asyncio
@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("height", [24, 40])
@pytest.mark.parametrize("value", [True, False, Decimal(0)])
async def test_reentering_a_staged_value_shows_and_prefills_the_draft_in_both_editor_hosts(
    language: OutputLanguage, height: int, value: ModeloFormScalar
) -> None:
    form = replace_fields(synthetic_form(), {"06": {"origin": ModeloFormOrigin.OPTIONAL_EMPTY, "value": None}})
    answer = next(field for field in form.fields() if field.box == "06")
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, height)) as pilot:
            await pilot.pause()
            assert value is not None
            display = format_casilla_value(value, data_type=answer.data_type, language=language)
            assert screen._session.stage_value(answer, value, display) is None
            screen._refresh_after_staging()
            screen._go_to(address_key(answer.address))
            await pilot.pause()
            listing = screen.query_one(CasillaList)
            assert listing.highlighted is not None
            assert tr("tui.modelo.workbench.attention.staged") in screen._state_line(listing.highlighted)
            assert "○" not in screen._state_line(listing.highlighted)
            await pilot.press("enter")
            await pilot.pause()
            panel = open_panel(app.screen)
            assert panel is not None and not panel.read_only
            now = str(panel.query_one("#editor-now-text", Static).render())
            assert display in now and tr("tui.modelo.workbench.attention.staged") in now
            assert "○" not in now
            saved = str(panel.query_one("#editor-saved-text", Static).render())
            assert "○" in saved
            typed = panel.query_one("#editor-input", Input).value
            assert typed == (display if isinstance(value, bool) else "0")
            assert panel.field.value is None and panel.field.origin is ModeloFormOrigin.OPTIONAL_EMPTY
            assert screen.staged_changes[0].value == value
            app.exit(None)


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("verdict", [None, *VerificationCompletenessStatus])
def test_only_a_saved_complete_check_gets_the_unapplied_changes_qualifier(
    language: OutputLanguage, verdict: VerificationCompletenessStatus | None
) -> None:
    form = synthetic_form().model_copy(update={"verification": verdict})
    with override_settings(cadrumo_output_language=language.value):
        original = verdict_text(form)
        changed = verdict_text(form, changes_unapplied=True)
        if verdict is VerificationCompletenessStatus.COMPLETE:
            assert changed == tr("tui.modelo.workbench.issues.verdict.saved_with_changes")
            assert original != changed
        else:
            assert changed == original


@pytest.mark.asyncio
@pytest.mark.parametrize("height", [24, 40])
@pytest.mark.parametrize("intent", ["clear", "restore"])
async def test_reentering_clear_and_restore_displays_the_intent_separately_from_saved_value(
    height: int, intent: str
) -> None:
    form = synthetic_form(needs_input=False)
    if intent == "restore":
        form = replace_fields(
            form,
            {
                "06": {
                    "origin": ModeloFormOrigin.OVERRIDES_SOURCE,
                    "editability": ModeloFormEditability.EDITABLE_OVERRIDE,
                }
            },
        )
    answer = next(field for field in form.fields() if field.box == "06")
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, height)) as pilot:
            await pilot.pause()
            method = screen._session.stage_clear if intent == "clear" else screen._session.stage_restore
            assert method(answer) is None
            staged = screen.staged_changes[0]
            screen._refresh_after_staging()
            screen._go_to(address_key(answer.address))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            panel = open_panel(app.screen)
            assert panel is not None
            assert staged.text in str(panel.query_one("#editor-now-text", Static).render())
            assert tr("tui.modelo.workbench.attention.staged") in str(
                panel.query_one("#editor-now-text", Static).render()
            )
            assert panel.query_one("#editor-input", Input).value == ""
            assert panel.field.value == Decimal("300.00") and screen.staged_changes[0] == staged
            assert panel.query_one("#editor-saved-text", Static).render()
            app.exit(None)
