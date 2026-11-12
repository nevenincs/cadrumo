"""The workbench draws a disclosed limitation as its own level and the figures a filer stated for earlier returns.

Driven through the standalone host with a synthetic form and the fake ports:

* a finding the backend marks as a disclosed limitation has its own chip, in the words the form serves, its own
  mark and its own level in the findings list;
* ``a`` lists the figures stated for earlier returns by family, in the served words, and one tick withdraws the
  whole family across every carry of it;
* a family the form does not admit a figure for shows the served refusal words and its served way out.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.widgets import Button, Checkbox, OptionList, Static

from ......application.modelo.work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormOrigin,
)
from ......application.modelo.work_form_findings import ModeloFormAttention, ModeloFormIssue
from ......application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormSection,
    ModeloFormStatedPriorValue,
    ModeloWorkForm,
)
from ......application.modelo.work_form_prior_value_models import (
    ModeloFormPriorValueAttestation,
    ModeloFormPriorValueRefusal,
    ModeloFormPriorValueWithdrawal,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....components.host import ScreenHostApp
from ....refusal.panel import RefusalPanel
from ....refusal.tests.refusal_fixtures import CREATE_WORK, primary_verdict
from ....tests.settling import settle
from ..header import attention_chips
from ..issue_projection import issue_lines
from ..issue_scale import IssueLevel, level_counts, title_text
from ..issues import WorkbenchIssuesScreen
from ..ports import WorkbenchChangeKind
from ..screen import ModeloWorkbenchScreen
from ..session import WorkbenchEditSession
from ..statements import StatementsScreen
from ..vocabulary import LIMITATION_MARK
from .workbench_fixture import FakeActions, FakeReader, form_counts, form_text, synthetic_form, with_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (160, 48)
_FAMILY = "130-2026-1T"
_OTHER_FAMILY = "130-2026-2T"
_LIMITATION_KEY = "application.modelo.findings.trabajo_deduction_not_computed"


def _limitation_form() -> ModeloWorkForm:
    """The synthetic form with one disclosed limitation, which is a warning that never blocks."""
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key=_LIMITATION_KEY,
        legal_refs=("ley-35-2006:art-19",),
        disclosed_limitation=True,
    )
    issue = ModeloFormIssue(finding=finding)
    assert issue.attention is ModeloFormAttention.LIMITATION
    return synthetic_form().model_copy(update={"issues": (issue,)})


def test_a_disclosed_limitation_has_its_own_chip_mark_and_level() -> None:
    form = _limitation_form()
    with override_settings(cadrumo_output_language="en"):
        chips = attention_chips(form, recorded=False)
        lines = issue_lines(form)
        title = title_text(level_counts(lines))

    (chip,) = [chip for chip in chips if chip.level is ModeloFormAttention.LIMITATION]
    assert chip.mark is LIMITATION_MARK
    assert chip.text == f"{LIMITATION_MARK.glyph} {chip.tally.words}"
    assert [line.level for line in lines] == [IssueLevel.LIMITATION]
    assert title.endswith(f"{LIMITATION_MARK.glyph} 1")
    assert LIMITATION_MARK.glyph not in "◆◐▲!i"


@pytest.mark.asyncio
async def test_the_header_chip_and_the_findings_list_show_the_limitation_in_served_and_catalogue_words() -> None:
    form = _limitation_form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            chips = str(screen.query_one("#wb-chips", Static).render())
            (served,) = [
                chip.tally.words
                for chip in attention_chips(form, recorded=False)
                if chip.level is ModeloFormAttention.LIMITATION
            ]
            await pilot.press("i")
            await settle(pilot)
            issues = app.screen
            assert isinstance(issues, WorkbenchIssuesScreen)
            options = issues.query_one("#issues-list", OptionList)
            listed = "\n".join(options.render_line(y).text for y in range(options.size.height))

    assert f"{LIMITATION_MARK.glyph} {served}" in chips
    assert f"{LIMITATION_MARK.glyph} Limit stated (1)" in listed


def _carry(binding_id: str, label: str, *, family: str | None, editable: bool = True) -> ModeloFormField:
    """A carry no casilla owns, holding a figure the filer stated for the family's earlier returns."""
    stated = (
        None
        if family is None
        else ModeloFormStatedPriorValue(
            source_words=f"Synthetic returns {family}", origin_words="Stated by you", family_id=family
        )
    )
    return ModeloFormField(
        address=ModeloFormBindingAddressV1(binding_id=binding_id),
        box=None,
        label=form_text(label),
        help=None,
        data_type="money",
        value=Decimal("5") if family is not None else None,
        origin=ModeloFormOrigin.ENTERED if family is not None else ModeloFormOrigin.OPTIONAL_EMPTY,
        editability=ModeloFormEditability.EDITABLE_VALUE if editable else ModeloFormEditability.LOCKED_SOURCE,
        required=False,
        stated_prior_value=stated,
    )


def _attestation(
    binding_id: str,
    family: str,
    *,
    stated: bool,
    admitted: bool = True,
    members: tuple[str, ...] = (),
) -> ModeloFormPriorValueAttestation:
    """One served entry; a stated one carries the family's whole withdrawal, a refused one its refusal."""
    refusal = None if admitted else primary_verdict(CREATE_WORK)
    return ModeloFormPriorValueAttestation(
        binding_id=binding_id,
        edit_address=ModeloFormBindingAddressV1(binding_id=binding_id),
        family_id=family,
        earlier_filings=(ModeloFormEarlierFiling(modelo="130", period=Period.from_year_and_code(2026, "1T")),),
        source_words=f"Synthetic returns {family}",
        action_words=f"Synthetic state {family}",
        statement_words=f"Synthetic statement {family}",
        effect_words=f"Synthetic effect {family}",
        stated=stated,
        admitted=admitted,
        refusal_reason=None if admitted else ModeloFormPriorValueRefusal.SOURCE_HELD,
        refusal_words=None if admitted else f"Synthetic refusal {family}",
        refusal=refusal,
        withdrawal=(
            ModeloFormPriorValueWithdrawal(
                family_id=family,
                binding_ids=tuple(sorted(members)),
                action_words=f"Synthetic withdraw {family}",
                effect_words=f"Synthetic withdrawal effect {family}",
            )
            if stated
            else None
        ),
    )


def _form(carries: list[ModeloFormField], attestations: tuple[ModeloFormPriorValueAttestation, ...]) -> ModeloWorkForm:
    base = synthetic_form()
    section = ModeloFormSection(
        id="p3.s1",
        heading=form_text("Carries"),
        official_heading=None,
        blocks=tuple(ModeloFormFieldBlock(id=f"carry{index}", field=item) for index, item in enumerate(carries)),
        counts=form_counts(carries),
        applies=True,
    )
    page = base.pages[0].model_copy(
        update={"id": "p3", "heading": form_text("Carries"), "sections": (section,), "counts": form_counts(carries)}
    )
    return with_pages(base, (*base.pages, page), prior_value_attestations=attestations)


_FIRST, _SECOND, _THIRD = "carry.prior.a", "carry.prior.b", "carry.prior.c"


def _stated_form(*, locked: bool = False) -> ModeloWorkForm:
    """Two carries stated under one family and one under another."""
    members = (_FIRST, _SECOND)
    carries = [
        _carry(_FIRST, "Carry a", family=_FAMILY),
        _carry(_SECOND, "Carry b", family=_FAMILY, editable=not locked),
        _carry(_THIRD, "Carry c", family=_OTHER_FAMILY),
    ]
    attestations = (
        _attestation(_FIRST, _FAMILY, stated=True, members=members),
        _attestation(_SECOND, _FAMILY, stated=True, members=members),
        _attestation(_THIRD, _OTHER_FAMILY, stated=True, members=(_THIRD,)),
    )
    return _form(carries, attestations)


def _staged_bindings(session: WorkbenchEditSession) -> set[str]:
    return {
        change.field.address.binding_id
        for change in session.changes
        if isinstance(change.field.address, ModeloFormBindingAddressV1)
    }


@pytest.mark.asyncio
async def test_a_stated_family_is_listed_in_served_words_and_one_tick_withdraws_it_whole() -> None:
    form = _stated_form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            dialog = app.screen
            assert isinstance(dialog, StatementsScreen)
            assert [family.family_id for family in dialog.families] == [_FAMILY, _OTHER_FAMILY]
            sources = [str(dialog.query_one(f"#prior-source-{i}", Static).render()) for i in range(2)]
            ticks = [str(box.label) for box in dialog.query(Checkbox)]
            stage = dialog.query_one("#statements-stage", Button)
            assert stage.disabled
            dialog.query_one("#prior-0", Checkbox).value = True
            await settle(pilot)
            assert not stage.disabled
            stage.press()
            await settle(pilot)
            staged = _staged_bindings(screen._session)
            kinds = {change.kind for change in screen._session.changes}

    assert sources == [f"Synthetic returns {_FAMILY}", f"Synthetic returns {_OTHER_FAMILY}"]
    assert ticks == [f"Synthetic withdraw {_FAMILY}", f"Synthetic withdraw {_OTHER_FAMILY}"]
    assert staged == {_FIRST, _SECOND}, "the whole family is staged, and no other"
    assert kinds <= {WorkbenchChangeKind.CLEAR, WorkbenchChangeKind.RESTORE}


@pytest.mark.asyncio
async def test_a_staged_family_withdrawal_opens_ticked_and_unticking_it_unstages_the_family() -> None:
    form = _stated_form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            first = form.prior_value_attestations[0]
            assert screen._session.stage_prior_withdrawal(form, first) is None
            assert screen._session.stages_prior_withdrawal(first)
            await pilot.press("a")
            await settle(pilot)
            dialog = app.screen
            assert isinstance(dialog, StatementsScreen)
            assert dialog.query_one("#prior-0", Checkbox).value
            assert not dialog.query_one("#prior-1", Checkbox).value
            dialog.query_one("#prior-0", Checkbox).value = False
            await settle(pilot)
            dialog.query_one("#statements-stage", Button).press()
            await settle(pilot)
            remaining = screen._session.changes

    assert remaining == ()


def test_withdrawing_one_stated_box_withdraws_its_family_and_a_locked_member_stages_nothing() -> None:
    form = _stated_form()
    session = WorkbenchEditSession(OutputLanguage.EN)
    first = next(item for item in form.fields() if item.stated_prior_value is not None)

    assert session.withdraw_stated(form, first) is None
    assert _staged_bindings(session) == {_FIRST, _SECOND}

    locked = _stated_form(locked=True)
    fresh = WorkbenchEditSession(OutputLanguage.EN)
    refused = fresh.withdraw_stated(locked, next(item for item in locked.fields() if item.stated_prior_value))
    assert refused is not None
    assert not fresh.changes, "a family is withdrawn whole or not at all"


def test_a_family_the_form_serves_no_withdrawal_for_is_not_withdrawn_box_by_box() -> None:
    form = _stated_form()
    bare = form.model_copy(
        update={
            "prior_value_attestations": tuple(
                item.model_copy(update={"withdrawal": None}) for item in form.prior_value_attestations
            )
        }
    )
    session = WorkbenchEditSession(OutputLanguage.EN)

    refused = session.withdraw_stated(bare, next(item for item in bare.fields() if item.stated_prior_value))

    assert refused is not None
    assert not session.changes


@pytest.mark.asyncio
async def test_a_refused_family_shows_the_served_refusal_words_and_the_served_way_out() -> None:
    carries = [_carry(_FIRST, "Carry a", family=None)]
    refused = _attestation(_FIRST, _FAMILY, stated=False, admitted=False)
    form = _form(carries, (refused,))
    assert refused.refusal is not None
    door = refused.refusal.action_words
    assert door is not None and door
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            await pilot.press("a")
            await settle(pilot)
            dialog = app.screen
            assert isinstance(dialog, StatementsScreen)
            panel = dialog.query_one(RefusalPanel)
            words = str(panel.query_one("#refusal-words", Static).render())
            labels = [str(button.label) for button in panel.query(Button)]
            ticks = list(dialog.query(Checkbox))

    assert words == f"Synthetic refusal {_FAMILY}"
    assert labels == [door], "the way out is the served one, worded by the backend"
    assert ticks == [], "a family that admits no figure offers nothing to tick"


@pytest.mark.asyncio
async def test_a_form_serving_no_figure_for_earlier_returns_offers_no_statements_key() -> None:
    form = _form([_carry(_FIRST, "Carry a", family=None)], ())
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            offered = screen.offers_statements()

    assert not offered
