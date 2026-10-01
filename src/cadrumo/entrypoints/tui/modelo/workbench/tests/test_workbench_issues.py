"""The issues list puts everything to look at on one scale, wraps every word and acts on every Enter.

The findings are real verification findings with real catalogue messages over
the synthetic form: one that blocks filing on a box, one worth checking about
the whole declaration, one about a box the form does not show, and the boxes
whose value was assumed. Driven through the workbench, the list is grouped by
level with a count per level, reads where, what is wrong and what to do for
each finding without cutting a word, keeps codes and facts behind ``t``, and
Enter goes to a box, opens a detail in place or says the box is not on the
form. A finding the form marks as an explanation sits at the information level
and asks nothing; a long run of assumed boxes is cut to two lines, and a very
long one is listed by section; a declaration recorded as filed asks for nothing.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from rich.cells import cell_len
from rich.console import Console
from textual.content import Content
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormIssue,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......domain.calculations.registry.schema_form_layouts import FormPageCondition
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..header import ChipLevel, attention_chips, status_line
from ..issues import (
    ASSUMED_BOXES_BEFORE_SECTIONS,
    IssueLevel,
    WorkbenchIssuesScreen,
    issue_lines,
    level_counts,
    levels_marked,
    title_text,
    unentered_boxes,
    unentered_levels,
    verdict_text,
)
from ..screen import ModeloWorkbenchScreen
from ..sources import BoxNumbers
from ..vocabulary import BLOCKS_MARK
from .declaration_states import recorded_as_filed
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, form_field, status_line_of, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MESSAGE_KEY = "application.modelo.findings.oss_evidence_missing"
_EXPLANATION_KEY = "application.modelo.findings.cross_period_modelo_not_applicable.message"
_LEGAL_REF = "ley-37-1992:art-99"


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _finding(
    casilla_id: str | None,
    severity: ModeloVerificationFindingSeverity,
    kind: ModeloVerificationFindingKind = ModeloVerificationFindingKind.BLOCKING_RULE,
) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=kind,
        severity=severity,
        casilla_id=casilla_id,
        message_locale_key=_MESSAGE_KEY,
        legal_refs=(_LEGAL_REF,),
    )


def _explanation() -> ModeloFormIssue:
    """An advisory the verification emits to explain a dependency it scoped out: for information only."""
    return ModeloFormIssue(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            message_locale_key=_EXPLANATION_KEY,
            message_facts={"source_modelo_count": 2},
            legal_refs=(_LEGAL_REF,),
        )
    )


def _checked(*, assumed: bool = True) -> ModeloWorkForm:
    """The fixture checked and blocked, with box 07 assumed rather than entered."""
    form = synthetic_form(needs_input=False)
    if assumed:
        form = replace_fields(form, {"07": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("0")}})
    return form.model_copy(
        update={
            "verification": VerificationCompletenessStatus.BLOCKED,
            "issues": (
                ModeloFormIssue(
                    finding=_finding(
                        None, ModeloVerificationFindingSeverity.WARNING, ModeloVerificationFindingKind.ADVISORY
                    )
                ),
                ModeloFormIssue(finding=_finding("06", ModeloVerificationFindingSeverity.BLOCKING), box="06"),
                ModeloFormIssue(
                    finding=_finding(
                        "71",
                        ModeloVerificationFindingSeverity.WARNING,
                        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
                    )
                ),
            ),
        }
    )


def _text(text: str) -> ModeloFormText:
    return ModeloFormText(text=text, disclosure=ModeloFormTextDisclosure.LOCALIZED)


def _counts(total: int) -> ModeloFormCounts:
    return ModeloFormCounts(
        total=total,
        needs_input=0,
        entered=0,
        imported=0,
        calculated=0,
        overridden=0,
        default_to_confirm=total,
        not_applicable=0,
        blocked=0,
    )


def _assumed_boxes(*section_sizes: int) -> ModeloWorkForm:
    """A declaration whose boxes nobody entered, numbered 1000 upward, in sections of the given sizes."""
    number = iter(range(1000, 10000))
    sections: list[ModeloFormSection] = []
    for index, size in enumerate(section_sizes, start=1):
        fields: list[ModeloFormField] = [
            form_field(str(next(number)), "Importe", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("5.00"))
            for _ in range(size)
        ]
        sections.append(
            ModeloFormSection(
                id=f"s{index}",
                heading=_text(f"Apartado {index}"),
                official_heading=None,
                blocks=tuple(ModeloFormFieldBlock(id=f"f{field.box}", field=field) for field in fields),
                counts=_counts(size),
            )
        )
    page = ModeloFormPage(
        id="p1",
        heading=_text("Liquidación"),
        official_ref=None,
        condition=FormPageCondition.ALWAYS,
        applies=True,
        sections=tuple(sections),
        counts=_counts(sum(section_sizes)),
    )
    return synthetic_form(needs_input=False).model_copy(
        update={"pages": (page,), "working_figures": (), "result_addresses": (), "counts": _counts(sum(section_sizes))}
    )


def _list_text(screen: WorkbenchIssuesScreen) -> str:
    options = screen.query_one("#issues-list", OptionList)
    return "\n".join(options.render_line(y).text.rstrip() for y in range(options.size.height))


def _words(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_findings_sit_on_one_scale_with_where_what_and_what_to_do() -> None:
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(_checked())
        assumed = unentered_boxes(_checked(), IssueLevel.CONFIRM)
        title = title_text(level_counts(lines, unentered_levels(_checked())))

    assert [(line.level, line.box, line.where) for line in lines] == [
        (IssueLevel.BLOCKS, "06", "[06] Retenciones e ingresos a cuenta"),
        (IssueLevel.CHECK, "·", "Whole declaration"),
        (IssueLevel.CHECK, "71", "[71]"),
    ]
    # The missing document is the finding's message, so the form names one step for it whatever its kind.
    assert [line.action for line in lines] == ["What to do: Attach the document to the entry in your records."] * 3
    assert all(line.message.startswith("This declaration includes one-stop-shop") for line in lines)
    assert lines[0].key == address_key(ModeloFormCasillaAddressV1(casilla_id="06"))
    assert lines[1].key is None
    assert lines[2].key is None
    assert lines[2].detail.startswith("Box [71] is not shown on this declaration's pages.")
    assert assumed is not None
    assert assumed.boxes == ("07",)
    assert not assumed.by_section
    assert title == "Issues to look at   ▲ 1   ◐ 1   ◆ 2"


def test_a_finding_the_form_marks_as_an_explanation_is_for_information_and_asks_nothing() -> None:
    form = _checked(assumed=False).model_copy(update={"issues": (_explanation(),)})
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(form)
        title = title_text(level_counts(lines))

    assert [line.level for line in lines] == [IssueLevel.INFO]
    assert lines[0].action == "What to do: Nothing to do. It explains what the calculation did."
    assert lines[0].message == "2 modelos were not used, because they do not apply to you."
    assert title == "Issues to look at   i 1"


def test_the_verdict_says_what_the_check_concluded_and_leaves_the_counting_to_the_title() -> None:
    with override_settings(cadrumo_output_language="en"):
        blocked = verdict_text(_checked())
        passed = verdict_text(_checked().model_copy(update={"verification": VerificationCompletenessStatus.COMPLETE}))

    assert blocked == "The check found something that blocks filing."
    assert passed == "The check passed."


@pytest.mark.asyncio
async def test_the_list_groups_by_level_wraps_every_word_and_keeps_codes_and_facts_behind_t() -> None:
    form = _checked().model_copy(update={"issues": (*_checked().issues, _explanation())})
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 100)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            title = str(issues.query_one("#issues-title", Static).render())
            verdict = str(issues.query_one("#issues-verdict", Static).render())
            before = _list_text(issues)
            await pilot.press("t")
            await _settle(pilot)
            technical = _list_text(issues)
            await pilot.press("t", "end", "t")
            await _settle(pilot)
            explained = _list_text(issues)
            app.exit(None)

    headings = [line.strip() for line in before.splitlines() if line.strip().startswith(("▲", "◐", "◆", "i "))]
    assert headings == [
        "▲ Blocks filing (1)",
        "◐ Assumed, please confirm (1)",
        "◆ Worth checking (2)",
        "i For your information (1)",
    ]
    assert title == "Issues to look at   ▲ 1   ◐ 1   ◆ 2   i 1"
    assert verdict == "The check found something that blocks filing."
    message = "This declaration includes one-stop-shop (OSS) activity, but no supporting documents for it are saved."
    assert _words(before).count(message) == 3
    assert "…" not in before
    assert _LEGAL_REF not in before
    assert "source_modelo_count" not in before
    assert _words(technical).count(_LEGAL_REF) == 1
    assert "source_modelo_count=2" in _words(explained)


@pytest.mark.asyncio
async def test_enter_goes_to_a_box_opens_a_detail_or_says_the_box_is_not_on_the_form() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_checked()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 100)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            await pilot.press("end", "up", "enter")
            await _settle(pilot)
            opened = _list_text(issues)
            still_open = app.screen is issues
            await pilot.press("down", "enter")
            await _settle(pilot)
            not_on_form = _list_text(issues)
            await pilot.press("home", "enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted
            app.exit(None)

    assert still_open
    assert "This is advice. You can file the declaration as it is." in _words(opened)
    assert "Box [71] is not shown on this declaration's pages." in _words(not_on_form)
    assert back
    assert landed_on is not None
    assert landed_on.field.box == "06"


@pytest.mark.asyncio
async def test_enter_on_the_assumed_values_goes_to_the_first_of_their_boxes() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_checked()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            await pilot.press("down", "enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted
            app.exit(None)

    assert back
    assert landed_on is not None
    assert landed_on.field.box == "07"


def test_a_list_of_box_numbers_takes_at_most_two_lines_and_counts_the_rest() -> None:
    boxes = tuple(str(number) for number in range(1000, 1018))
    console = Console(width=40)
    with override_settings(cadrumo_output_language="en"):
        with console.capture() as captured:
            console.print(BoxNumbers(boxes))
        wide = BoxNumbers(boxes).text(console, 200)

    lines = captured.get().splitlines()
    shown = re.findall(r"\[(\d+)\]", " ".join(lines))
    rest = re.search(r"and (\d+) more", lines[-1])
    assert len(lines) == 2
    assert rest is not None
    assert len(shown) + int(rest.group(1)) == len(boxes)
    assert shown == list(boxes[: len(shown)])
    assert wide == " ".join(f"[{box}]" for box in boxes)


@pytest.mark.asyncio
async def test_the_assumed_boxes_are_listed_in_two_lines_then_counted() -> None:
    form = _assumed_boxes(ASSUMED_BOXES_BEFORE_SECTIONS)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(60, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            listed = [
                line for line in _list_text(issues).splitlines() if re.search(r"\[\d+\]", line) or " more" in line
            ]
            app.exit(None)

    assert len(listed) == 2
    rest = re.search(r"and (\d+) more", listed[-1])
    assert rest is not None
    assert len(re.findall(r"\[\d+\]", " ".join(listed))) + int(rest.group(1)) == ASSUMED_BOXES_BEFORE_SECTIONS


@pytest.mark.asyncio
async def test_past_twenty_assumed_boxes_the_list_names_their_sections_and_enter_opens_one() -> None:
    form = _assumed_boxes(12, 15)
    with override_settings(cadrumo_output_language="en"):
        assumed = unentered_boxes(form, IssueLevel.CONFIRM)
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(100, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            listed = _list_text(issues)
            await pilot.press("down", "enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted
            app.exit(None)

    assert assumed is not None
    assert assumed.by_section
    assert [(section.title, len(section.keys)) for section in assumed.sections] == [
        ("Apartado 1", 12),
        ("Apartado 2", 15),
    ]
    assert "Apartado 1 (12)" in listed
    assert "Apartado 2 (15)" in listed
    assert "Open each section and confirm its values" in _words(listed)
    assert not re.search(r"\[\d{4}\]", listed)
    assert back
    assert landed_on is not None
    assert landed_on.field.box == "1012"


@pytest.mark.asyncio
async def test_a_declaration_recorded_as_filed_lists_no_assumed_values_and_counts_nothing_to_do() -> None:
    form = recorded_as_filed(_checked())
    with override_settings(cadrumo_output_language="en"):
        assumed = unentered_boxes(form, IssueLevel.CONFIRM)
        screen = WorkbenchIssuesScreen(form)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(100, 40)) as pilot:
            await _settle(pilot)
            title = str(screen.query_one("#issues-title", Static).render())
            listed = _list_text(screen)
            app.exit(None)

    assert assumed is None
    assert title == "Issues to look at   ◆ 2"
    assert "◐" not in listed
    assert "Assumed, please confirm" not in listed
    assert "▲ Blocks filing" in listed
    assert "▲ Blocks filing (" not in listed


def test_without_findings_or_assumed_values_the_list_says_there_is_nothing_to_look_at() -> None:
    form = _checked(assumed=False).model_copy(
        update={"issues": (), "verification": VerificationCompletenessStatus.COMPLETE}
    )
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(form)
        title = title_text(level_counts(lines, unentered_levels(form)))

    assert lines == ()
    assert unentered_levels(form) == ()
    assert title == "Issues to look at"


@pytest.mark.asyncio
async def test_the_declarations_status_line_leads_the_dialog_and_the_title_is_strong() -> None:
    status = "To pay 1,300.00 € · file by 20 Apr 2026"
    with override_settings(cadrumo_output_language="en"):
        screen = WorkbenchIssuesScreen(_checked(), status_line=status_line_of(status))
        app = ScreenHostApp(screen)
        async with app.run_test(size=(100, 40)) as pilot:
            await _settle(pilot)
            panel = screen.query_one("#issues-panel")
            first = panel.children[0]
            shown = str(first.render()) if isinstance(first, Static) else ""
            title = screen.query_one("#issues-title", Static)
            verdict = screen.query_one("#issues-verdict", Static)
            title_style, verdict_style = title.rich_style, verdict.rich_style
            app.exit(None)
        plain = WorkbenchIssuesScreen(_checked())
        plain_app = ScreenHostApp(plain)
        async with plain_app.run_test(size=(100, 40)) as pilot:
            await _settle(pilot)
            without = [child.id for child in plain.query_one("#issues-panel").children]
            plain_app.exit(None)

    assert first.id == "issues-status"
    assert shown == status
    assert without[0] == "issues-title"
    assert "issues-status" not in without
    assert title_style.bold
    assert title_style.color != verdict_style.color


def _recounted(form: ModeloWorkForm) -> ModeloWorkForm:
    """The form with every page's and the form's to-do counts taken again from its boxes, as the read model counts."""

    def counted(fields: tuple[ModeloFormField, ...], counts: ModeloFormCounts) -> ModeloFormCounts:
        return counts.model_copy(
            update={
                "needs_input": sum(1 for field in fields if field.origin is ModeloFormOrigin.NEEDS_INPUT),
                "default_to_confirm": sum(1 for field in fields if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM),
            }
        )

    pages = tuple(
        page.model_copy(
            update={
                "counts": counted(
                    tuple(field for section in page.sections for field in section_fields(section)), page.counts
                )
            }
        )
        for page in form.pages
    )
    recounted = form.model_copy(update={"pages": pages})
    return recounted.model_copy(update={"counts": counted(recounted.fields(), form.counts)})


def _chips(form: ModeloWorkForm) -> dict[ChipLevel, int]:
    return {chip.level: chip.count for chip in attention_chips(form, recorded=False)}


@pytest.mark.asyncio
async def test_the_missing_boxes_the_header_counts_are_listed_at_their_own_level() -> None:
    form = _recounted(synthetic_form(needs_input=True))
    with override_settings(cadrumo_output_language="en"):
        missing = unentered_boxes(form, IssueLevel.MISSING)
        title = title_text(level_counts(issue_lines(form), unentered_levels(form)))
        chips = _chips(form)
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(100, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            listed = _list_text(issues)
            await pilot.press("down", "enter")
            await _settle(pilot)
            landed_on = screen.query_one(CasillaList).highlighted
            app.exit(None)

    assert missing is not None
    assert missing.boxes == ("06",)
    assert chips == {ChipLevel.MISSING: 1}
    assert title == "Issues to look at   ! 1"
    assert "! Needs your input (1)" in listed
    assert "[06]" in listed
    assert "If the right value is zero, enter 0" in _words(listed)
    assert landed_on is not None and landed_on.field.box == "06"


def test_boxes_on_a_page_that_does_not_apply_are_neither_listed_nor_counted() -> None:
    both = _recounted(
        replace_fields(
            synthetic_form(needs_input=True),
            {"19": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("5.00")}},
        )
    )
    # Page 2 holds the missing box 06 and the assumed box 19; page 1 holds neither.
    set_aside = both.model_copy(
        update={
            "pages": tuple(
                page.model_copy(update={"applies": False}) if page.id == "p2" else page for page in both.pages
            )
        }
    )
    with override_settings(cadrumo_output_language="en"):
        applying = {boxes.level: boxes.boxes for boxes in unentered_levels(both)}
        not_applying = unentered_levels(set_aside)
        chips_applying, chips_not_applying = _chips(both), _chips(set_aside)

    # The instrument sees both boxes while their page applies, so their absence below is the page's doing.
    assert applying == {IssueLevel.MISSING: ("06",), IssueLevel.CONFIRM: ("19",)}
    assert chips_applying == {ChipLevel.MISSING: 1, ChipLevel.CONFIRM: 1}
    assert not_applying == ()
    assert chips_not_applying == {}


@pytest.mark.asyncio
async def test_on_the_smallest_terminal_the_status_keeps_one_line_the_list_opens_on_a_heading_and_the_footer_fits() -> (
    None
):
    form = _checked()
    with override_settings(cadrumo_output_language="en"):
        status = status_line(form, OutputLanguage.EN, staged=0, recorded=False)
        assert status is not None and len(status.chips) >= 2
        screen = WorkbenchIssuesScreen(form, status_line=status)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            bar = screen.query_one("#issues-status", Static)
            bar_height, bar_text = bar.region.height, str(bar.render())
            listed = screen.query_one("#issues-list", OptionList)
            scrolled = listed.scroll_offset.y
            first_option = listed.get_option_at_index(0)
            visible_rows = listed.scrollable_content_region.height
            footer_keys = [key for key in screen.query("FooterKey") if key.display]
            footer_edges = [key.region.right for key in footer_keys]
            clipped = [
                str(getattr(key, "description", ""))
                for key in footer_keys
                if key.region.width < cell_len(str(getattr(key, "description", "")))
            ]
            app.exit(None)

    assert bar_height == 1, "the repeated result line never wraps"
    assert cell_len(bar_text) <= 80
    assert BLOCKS_MARK.glyph in bar_text, "the most urgent chip stays"
    assert scrolled == 0 and first_option.disabled and (first_option.id or "").startswith("level-")
    assert visible_rows >= 6, "the list keeps room to show its entries"
    assert footer_edges and max(footer_edges) <= 80, "no footer key runs past the edge"
    assert clipped == [], "no footer key is cut short"


def _styled(content: Content, glyph: str) -> set[str]:
    """The styles drawn over each standing occurrence of ``glyph`` in ``content``."""
    plain = content.plain
    return {str(span.style) for span in content.spans if plain[span.start : span.end] == glyph}


def test_each_level_glyph_takes_its_one_colour_wherever_it_marks_a_level() -> None:
    title = levels_marked("Issues to look at   ▲ 1   ! 2   ◐ 1   ◆ 1   i 2")
    heading = levels_marked("◆ Worth checking (1)")
    prose = levels_marked("Revisa la retenció i torna a calcular.")

    assert _styled(title, "▲") == {"$error"} and _styled(title, "!") == {"$error"}
    assert _styled(title, "◐") == {"$warning"} and _styled(title, "◆") == {"$warning"}
    assert _styled(title, "i") == {"$secondary"}
    assert _styled(heading, "◆") == {"$warning"}
    assert prose.spans == [], "a word in prose is never taken for a mark"


@pytest.mark.asyncio
async def test_a_stale_calculation_names_c_beside_what_to_do_and_c_calculates_again() -> None:
    stale = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.ledger_snapshot_drift",
        legal_refs=("ley-58-2003:art-119",),
    )
    information = ModeloFormCalculationNote(reason="oss_no_live_source", attention=ModeloFormAttention.INFO)
    form = synthetic_form(calculated=True, needs_input=False).model_copy(
        update={
            "issues": (ModeloFormIssue(finding=stale),),
            "calculation_notes": (information,),
            "verification": VerificationCompletenessStatus.BLOCKED,
        }
    )
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        lines = issue_lines(form)
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            listed = _list_text(app.screen) if isinstance(app.screen, WorkbenchIssuesScreen) else ""
            await pilot.press("c")
            await _settle(pilot)
            app.exit(None)

    stale_line = next(line for line in lines if line.recalculates)
    info_line = next(line for line in lines if line.level is IssueLevel.INFO)
    assert f"{stale_line.action} [c]" in listed
    assert info_line.action not in listed, "nothing to do is not said for what is only for information"
    assert actions.requested == ["calculate"]
