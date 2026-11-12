"""The workbench states a figure for earlier returns the application does not hold, whole or not at all.

Driven through the standalone host with a synthetic form, the fake ports and the real statements dialog,
staged session, review and operation modal:

* a family the form admits a figure for offers one entry per carry, labelled with the carry's own words;
  every entry filled and read stages the whole family, which the review words and the edit apply carries as
  ``attest_prior_value`` figures;
* a partly filled family, or one with an entry the application does not read, stages nothing;
* a family the form refuses a figure for offers no entry, only its served refusal;
* the apply's served refusal is shown beneath the notice, and an outcome that may have committed is not
  reported as undone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from typing import override

import pytest
from pydantic import BaseModel
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, Input, Static

from ......application.modelo.action_errors import (
    AmendmentEvidenceMissingError,
    amendment_evidence_missing_precondition,
)
from ......application.modelo.edit_admission import MODELO_EDIT_APPLY_DEFINITION_ID
from ......application.modelo.edit_models import ModeloEditBindingIntentKind
from ......application.modelo.work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormOrigin,
)
from ......application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormSection,
    ModeloWorkForm,
)
from ......application.modelo.work_form_prior_value_models import (
    ModeloFormPriorValueAttestation,
    ModeloFormPriorValueRefusal,
)
from ......application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from ......application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationReviewProjectionResultV1,
)
from ......application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from ......application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from ......application.operations.persistence.replay import OperationReplayStatus
from ......application.operations.registry import OperationPublicDefinitionContractV1
from ......core.config import override_settings
from ......core.decimal.coercion import coerce_finite_european_decimal
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ......core.period import Period
from .....tests.production_operation_registry import production_operation_registry
from ....components.host import ScreenHostApp
from ....operations.controller_port import OperationControllerPort, OperationResponseControlPort
from ....refusal.panel import RefusalPanel, RefusalSlot
from ....refusal.tests.refusal_fixtures import CREATE_WORK, primary_verdict
from ....tests.settling import settle
from ..factory import _intents
from ..ports import (
    WorkbenchChange,
    WorkbenchChangeKind,
    WorkbenchParsed,
    WorkbenchParseOutcome,
    WorkbenchRefused,
)
from ..screen import ModeloWorkbenchScreen
from ..session import StagedChange, StageRefusal, WorkbenchEditSession
from ..statements import StatementsScreen
from .workbench_fixture import FakeActions, FakeReader, form_counts, form_text, synthetic_form, with_pages

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SIZE = (160, 48)
_FAMILY = "130-2026-1T"
_OTHER_FAMILY = "130-2026-2T"
_FIRST, _SECOND, _THIRD = "carry.prior.a", "carry.prior.b", "carry.prior.c"
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 11, 12, tzinfo=UTC)
_AMBIGUOUS = "Synthetic: this number could be read two ways"


def _carry(binding_id: str, label: str) -> ModeloFormField:
    """A carry no casilla owns, holding no figure yet."""
    return ModeloFormField(
        address=ModeloFormBindingAddressV1(binding_id=binding_id),
        box=None,
        label=form_text(label),
        help=None,
        data_type="money",
        value=None,
        origin=ModeloFormOrigin.OPTIONAL_EMPTY,
        editability=ModeloFormEditability.EDITABLE_VALUE,
        required=False,
    )


def _attestation(
    binding_id: str, family: str, *, admitted: bool = True, stated: bool = False
) -> ModeloFormPriorValueAttestation:
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
    )


def _form(
    attestations: tuple[ModeloFormPriorValueAttestation, ...], carries: tuple[str, ...] = (_FIRST, _SECOND, _THIRD)
) -> ModeloWorkForm:
    fields = [_carry(binding_id, f"Carry {binding_id[-1]}") for binding_id in carries]
    base = synthetic_form()
    section = ModeloFormSection(
        id="p3.s1",
        heading=form_text("Carries"),
        official_heading=None,
        blocks=tuple(ModeloFormFieldBlock(id=f"carry{index}", field=item) for index, item in enumerate(fields)),
        counts=form_counts(fields),
        applies=True,
    )
    page = base.pages[0].model_copy(
        update={"id": "p3", "heading": form_text("Carries"), "sections": (section,), "counts": form_counts(fields)}
    )
    return with_pages(base, (*base.pages, page), prior_value_attestations=attestations)


def _admitted_form() -> ModeloWorkForm:
    """Two carries of one family and one of another, each admitted and unstated."""
    return _form(
        (
            _attestation(_FIRST, _FAMILY),
            _attestation(_SECOND, _FAMILY),
            _attestation(_THIRD, _OTHER_FAMILY),
        )
    )


@dataclass
class _Actions(FakeActions):
    """The fake actions reading a figure through the project's European decimal coercion."""

    @override
    def parse(self, field: ModeloFormField, lexeme: str, language: OutputLanguage) -> WorkbenchParseOutcome:
        value = coerce_finite_european_decimal(lexeme)
        if value is None:
            return WorkbenchRefused(message=_AMBIGUOUS)
        return WorkbenchParsed(value=value, display=f"{value:.2f}")


async def _open(app: ScreenHostApp[None], pilot: Pilot[None]) -> StatementsScreen:
    await settle(pilot)
    await pilot.press("a")
    await settle(pilot)
    dialog = app.screen
    assert isinstance(dialog, StatementsScreen)
    return dialog


def _binding(change: StagedChange) -> str:
    address = change.field.address
    assert isinstance(address, ModeloFormBindingAddressV1)
    return address.binding_id


def _error(dialog: StatementsScreen, index: int) -> str:
    return str(dialog.query_one(f"#figure-error-{index}", Static).render())


@pytest.mark.asyncio
async def test_a_family_is_stated_whole_staged_reviewed_and_applied_as_prior_value_figures() -> None:
    form = _admitted_form()
    actions = _Actions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            dialog = await _open(app, pilot)
            labels = [str(item.render()) for item in dialog.query(".figure-label").results(Static)]
            entries = [item.id for item in dialog.query(Input)]
            stage = dialog.query_one("#statements-stage", Button)
            disabled_before = stage.disabled
            dialog.query_one("#figure-0-0", Input).value = "1.234,56"
            dialog.query_one("#figure-0-1", Input).value = "10"
            await settle(pilot)
            disabled_after = stage.disabled
            await pilot.click("#statements-stage")
            await settle(pilot)
            staged = screen._session.changes
            await pilot.press("R")
            await settle(pilot)
            lines = "\n".join(str(item.render()) for item in app.screen.query(".review-change").results(Static))
            await pilot.press("a")
            await settle(pilot)

    assert labels == ["Carry a", "Carry b", "Carry c"]
    assert entries == ["figure-0-0", "figure-0-1", "figure-1-0"]
    assert disabled_before
    assert not disabled_after
    assert {change.kind for change in staged} == {WorkbenchChangeKind.STATE_PRIOR_VALUE}
    assert [(_binding(change), change.value) for change in staged] == [
        (_FIRST, Decimal("1234.56")),
        (_SECOND, Decimal("10")),
    ]
    assert f"Synthetic effect {_FAMILY}" in lines
    expected = tuple(
        WorkbenchChange(
            address=ModeloFormBindingAddressV1(binding_id=binding_id),
            kind=WorkbenchChangeKind.STATE_PRIOR_VALUE,
            value=value,
        )
        for binding_id, value in ((_FIRST, Decimal("1234.56")), (_SECOND, Decimal("10")))
    )
    assert actions.applied == [expected]


def test_a_staged_figure_reaches_the_edit_contract_as_attest_prior_value_with_its_figure() -> None:
    change = WorkbenchChange(
        address=ModeloFormBindingAddressV1(binding_id=_FIRST),
        kind=WorkbenchChangeKind.STATE_PRIOR_VALUE,
        value=Decimal("12.5"),
    )

    scalar, binding = _intents((change,))

    assert scalar == ()
    ((intent,),) = (binding,)
    assert intent.kind is ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE
    assert intent.value == Decimal("12.5")
    assert intent.address.binding_id == _FIRST


@pytest.mark.asyncio
async def test_a_partly_filled_family_is_refused_whole_and_nothing_is_staged() -> None:
    form = _admitted_form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=_Actions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            dialog = await _open(app, pilot)
            dialog.query_one("#figure-0-0", Input).value = "100"
            await settle(pilot)
            await pilot.click("#statements-stage")
            await settle(pilot)
            still_open = app.screen is dialog
            refusal = _error(dialog, 0)
            other = _error(dialog, 1)
            staged = screen._session.changes

    assert still_open
    assert refusal
    assert other == ""
    assert staged == ()


@pytest.mark.asyncio
async def test_a_number_the_application_does_not_read_is_refused_with_its_words_and_nothing_is_staged() -> None:
    form = _admitted_form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=_Actions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            dialog = await _open(app, pilot)
            dialog.query_one("#figure-0-0", Input).value = "1.234"
            dialog.query_one("#figure-0-1", Input).value = "10"
            dialog.query_one("#figure-1-0", Input).value = "7"
            await settle(pilot)
            await pilot.click("#statements-stage")
            await settle(pilot)
            still_open = app.screen is dialog
            refusal = _error(dialog, 0)
            staged = screen._session.changes

    assert still_open
    assert refusal == f"Carry a: {_AMBIGUOUS}"
    assert staged == (), "the readable family is not staged while another is refused"


@pytest.mark.asyncio
async def test_staged_figures_open_filled_and_emptying_them_takes_the_family_out() -> None:
    form = _admitted_form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=_Actions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            dialog = await _open(app, pilot)
            dialog.query_one("#figure-1-0", Input).value = "7"
            await pilot.click("#statements-stage")
            await settle(pilot)
            staged_first = [change.kind for change in screen._session.changes]
            await pilot.press("a")
            await settle(pilot)
            reopened = app.screen
            assert isinstance(reopened, StatementsScreen)
            shown = reopened.query_one("#figure-1-0", Input).value
            unchanged_disabled = reopened.query_one("#statements-stage", Button).disabled
            reopened.query_one("#figure-1-0", Input).value = ""
            await settle(pilot)
            await pilot.click("#statements-stage")
            await settle(pilot)
            remaining = screen._session.changes

    assert staged_first == [WorkbenchChangeKind.STATE_PRIOR_VALUE]
    assert shown == "7.00"
    assert unchanged_disabled
    assert remaining == ()


@pytest.mark.asyncio
async def test_a_family_the_form_refuses_a_figure_for_offers_no_entry_only_its_refusal() -> None:
    form = _form(
        (
            _attestation(_FIRST, _FAMILY),
            _attestation(_SECOND, _FAMILY, admitted=False),
        ),
        carries=(_FIRST, _SECOND),
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=_Actions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            dialog = await _open(app, pilot)
            entries = list(dialog.query(Input))
            words = str(dialog.query_one(RefusalPanel).query_one("#refusal-words", Static).render())
            ticks = list(dialog.query(Checkbox))

    assert entries == []
    assert ticks == []
    assert words == f"Synthetic refusal {_FAMILY}"


@pytest.mark.asyncio
async def test_no_entry_is_offered_where_nothing_can_read_a_figure() -> None:
    form = _admitted_form()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=None)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            offered = screen.offers_statements()

    assert not offered


def test_the_session_states_a_family_whole_and_refuses_a_part_a_held_family_or_a_missing_box() -> None:
    form = _admitted_form()
    session = WorkbenchEditSession(OutputLanguage.EN)
    both = {_FIRST: (Decimal("1"), "1.00"), _SECOND: (Decimal("2"), "2.00")}

    assert session.stage_prior_figures(form, _FAMILY, {_FIRST: both[_FIRST]}) is StageRefusal.NOT_EDITABLE
    assert session.stage_prior_figures(form, _FAMILY, {**both, _THIRD: both[_FIRST]}) is StageRefusal.NOT_EDITABLE
    assert session.stage_prior_figures(form, "130-2099-1T", both) is StageRefusal.NOT_EDITABLE
    assert session.changes == ()

    assert session.stage_prior_figures(form, _FAMILY, both) is None
    assert session.stages_prior_figures(_FAMILY)
    assert not session.stages_prior_figures(_OTHER_FAMILY)
    assert session.prior_figures(_FAMILY) == both

    held = _form(
        (_attestation(_FIRST, _FAMILY, stated=True), _attestation(_SECOND, _FAMILY)), carries=(_FIRST, _SECOND)
    )
    fresh = WorkbenchEditSession(OutputLanguage.EN)
    assert fresh.stage_prior_figures(held, _FAMILY, both) is StageRefusal.NOT_EDITABLE
    refused = _form(
        (_attestation(_FIRST, _FAMILY), _attestation(_SECOND, _FAMILY, admitted=False)), carries=(_FIRST, _SECOND)
    )
    assert fresh.stage_prior_figures(refused, _FAMILY, both) is StageRefusal.NOT_EDITABLE
    unplaced = _form((_attestation(_FIRST, _FAMILY), _attestation(_SECOND, _FAMILY)), carries=(_FIRST,))
    assert fresh.stage_prior_figures(unplaced, _FAMILY, both) is StageRefusal.NOT_EDITABLE
    assert fresh.changes == ()


def test_reading_the_declaration_again_drops_the_whole_family_when_one_carry_no_longer_admits_it() -> None:
    form = _admitted_form()
    session = WorkbenchEditSession(OutputLanguage.EN)
    both = {_FIRST: (Decimal("1"), "1.00"), _SECOND: (Decimal("2"), "2.00")}
    assert session.stage_prior_figures(form, _FAMILY, both) is None
    assert session.stage_prior_figures(form, _OTHER_FAMILY, {_THIRD: (Decimal("3"), "3.00")}) is None

    unchanged = session.rebase(form)
    assert unchanged.dropped == ()
    assert len(session.changes) == 3

    moved = _form(
        (
            _attestation(_FIRST, _FAMILY),
            _attestation(_SECOND, _FAMILY, admitted=False),
            _attestation(_THIRD, _OTHER_FAMILY),
        )
    )
    outcome = session.rebase(moved)

    assert {_binding(change) for change in outcome.dropped} == {_FIRST, _SECOND}
    assert [change.prior_value.family_id for change in session.changes if change.prior_value] == [_OTHER_FAMILY]


# -- the apply's outcome ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _apply_contract() -> tuple[OperationPublicDefinitionContractV1, str]:
    contracts = production_operation_registry().public_contract_set
    contract = next(row for row in contracts.definitions if row.definition_id == MODELO_EDIT_APPLY_DEFINITION_ID)
    return contract, contracts.contract_set_digest


def _terminal(condition: OperationTerminalCondition, effect: OperationEffect) -> OperationObservationSuccessV1:
    contract, digest = _apply_contract()
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=MODELO_EDIT_APPLY_DEFINITION_ID,
        subject_ref="b" * 64,
        revision=3,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=effect,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref="REFUSED_MODELO_AMENDMENT_EVIDENCE_MISSING"
        if condition is OperationTerminalCondition.REFUSED
        else None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=0,
        requested_cursor=0,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=0,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=page)


def _refusal_detail() -> OperationErrorDetailV1:
    error = AmendmentEvidenceMissingError(
        translated_message="errors.refused.refused_modelo_amendment_evidence_missing",
        context={"work_unit_id": "b" * 64, "filing_record_id": "f" * 64, "external_evidence_present": False},
        precondition_failure=amendment_evidence_missing_precondition(
            subject_leaf_key="modelo.work.amend", work_unit_id="b" * 64, filing_record_id="f" * 64
        ),
    )
    detail = build_operation_error_detail(error)
    assert detail is not None
    return detail


class _SettlingController:
    """One submitted apply that the modal observes settling as the test said."""

    def __init__(self, observation: OperationObservationSuccessV1, detail: OperationErrorDetailV1 | None) -> None:
        self._observation = observation
        self._detail = detail

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return "operator:tui-modelo"

    async def start(self) -> str:
        return _OPERATION_ID

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        del after_cursor, page_limit
        return self._observation

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        del projection
        return self._detail

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        raise AssertionError("an apply presents no review")

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        raise AssertionError("an apply presents no review")

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError("the settled apply is never cancelled")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise AssertionError("the settled apply is never detached")


@dataclass
class _SettlingActions(_Actions):
    """Actions whose apply settles as the test says."""

    settles: OperationObservationSuccessV1 | None = None
    detail: OperationErrorDetailV1 | None = None

    @override
    async def apply(self, changes: tuple[WorkbenchChange, ...]) -> OperationControllerPort:
        self.applied.append(changes)
        assert self.settles is not None
        return _SettlingController(self.settles, self.detail)


async def _apply_stated(
    actions: _SettlingActions, form: ModeloWorkForm
) -> tuple[ModeloWorkbenchScreen, str, RefusalSlot | None, int]:
    screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=actions)
    app = ScreenHostApp(screen)
    async with app.run_test(size=_SIZE) as pilot:
        dialog = await _open(app, pilot)
        dialog.query_one("#figure-1-0", Input).value = "7"
        await pilot.click("#statements-stage")
        await settle(pilot)
        await pilot.press("R")
        await settle(pilot)
        await pilot.press("a")
        await settle(pilot)
        await settle(pilot)
        notice = str(screen.query_one("#wb-notice", Static).render())
        slot = next(iter(screen.query("#wb-operation-refusal").results(RefusalSlot)), None)
        return screen, notice, slot, len(screen._session.changes)


@pytest.mark.asyncio
async def test_a_refused_apply_shows_the_served_refusal_and_keeps_the_figures_staged() -> None:
    form = _admitted_form()
    with override_settings(cadrumo_output_language="en"):
        detail = _refusal_detail()
        actions = _SettlingActions(
            settles=_terminal(OperationTerminalCondition.REFUSED, OperationEffect.NONE), detail=detail
        )
        _, _, slot, staged = await _apply_stated(actions, form)

    assert slot is not None
    assert slot.refusal is not None
    assert slot.refusal.sentence == detail.refusal_words
    assert staged == 1, "a refused apply leaves the figure staged"
    assert [change.kind for change in actions.applied[0]] == [WorkbenchChangeKind.STATE_PRIOR_VALUE]


@pytest.mark.asyncio
async def test_an_outcome_that_may_have_committed_stays_unknown_and_is_not_reported_undone() -> None:
    form = _admitted_form()
    with override_settings(cadrumo_output_language="en"):
        actions = _SettlingActions(settles=_terminal(OperationTerminalCondition.INTERRUPTED, OperationEffect.UNKNOWN))
        _, notice, _, staged = await _apply_stated(actions, form)
        not_done = tr("workspace.modelo.operation.not_done", locale="en")

    assert notice == tr("workspace.modelo.operation.unknown", locale="en")
    assert notice != not_done
    assert "changes are still here" not in notice
    assert staged == 1
    assert len(actions.applied) == 1
