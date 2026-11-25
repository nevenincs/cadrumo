"""A declaration recorded as filed offers a correction, prepared on served words and recorded locally.

Driven through the real workbench, the real correction dialog and the real
operation modal, over a correction door that answers with a served correction
context and records what it was asked to submit. The modal observes a
controller that settles as the test says: done, refused with the backend's own
detail and ways out, or with an outcome that may have committed. The figures
are read by the application's own correction parser against an admitted
baseline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import lru_cache

import pytest
from pydantic import BaseModel
from textual.widgets import Input, Select, Static

from .....application.modelo.action_errors import (
    AmendmentEvidenceMissingError,
    amendment_evidence_missing_precondition,
)
from .....application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from .....application.modelo.edit_models import (
    ModeloEditBaselineV1,
    ModeloEditCorrectionAddressV1,
    ModeloEditSchemaIdentityV1,
)
from .....application.modelo.edit_value_grammar import (
    ModeloEditValueChannel,
    ModeloEditValueFamily,
    ModeloEditValueGrammarV1,
)
from .....application.modelo.operation_shared import MODELO_WORK_AMEND_OPERATION_DEFINITION_ID
from .....application.modelo.work_amend_correction import (
    ModeloAmendmentCorrectionContextV1,
    ModeloAmendmentCorrectionRowV1,
    ModeloAmendmentFiledRecordV1,
    ModeloAmendmentKindOptionV1,
    ModeloAmendmentMotiveOptionV1,
)
from .....application.modelo.work_form_models import ModeloWorkForm
from .....application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from .....application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationReviewProjectionResultV1,
)
from .....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
)
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationPublicDefinitionContractV1
from .....application.operations.schema_identity import OperationSchemaIdentityV1
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .....domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from .....domain.modelos.filing_record import FilingDeclarationKind
from ....tests.production_operation_registry import production_operation_registry
from ...components.host import ScreenHostApp
from ...operations.controller_port import OperationControllerPort, OperationResponseControlPort
from ...refusal.panel import RefusalSlot
from ...tests.settling import settle
from ..amendment import (
    ModeloAmendmentAnswerV1,
    ModeloAmendmentScreen,
    ModeloWorkbenchAmendmentV1,
    parse_correction_entry,
)
from ..lifecycle import ModeloLifecycleActionUnavailableError
from ..workbench.ports import WorkbenchParseOutcome
from ..workbench.screen import ModeloWorkbenchScreen
from ..workbench.tests.declaration_states import recorded_as_filed
from ..workbench.tests.workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_FILING_RECORD_ID = "f" * 64
_DIGEST = "d" * 64
_NOW = datetime(2026, 11, 12, tzinfo=UTC)
_REASON = "A figure was left out."
_EVIDENCE_CODE = "REFUSED_MODELO_AMENDMENT_EVIDENCE_MISSING"


def _grammar() -> ModeloEditValueGrammarV1:
    return ModeloEditValueGrammarV1(
        data_type="money",
        family=ModeloEditValueFamily.DECIMAL,
        channel=ModeloEditValueChannel.DECIMAL,
        max_fraction_digits=6,
        minimum="-999999999999999.999999",
        maximum="999999999999999.999999",
    )


def _row(casilla_id: str, label: str, filed: str) -> ModeloAmendmentCorrectionRowV1:
    return ModeloAmendmentCorrectionRowV1(
        casilla_id=casilla_id,
        box=casilla_id,
        label=label,
        help=None,
        data_type="money",
        filed_value=filed,
        filed_value_text=f"{filed} EUR",
        edit_address=ModeloEditCorrectionAddressV1(casilla_id=casilla_id),
        grammar=_grammar(),
        legal_refs=(),
    )


def _context(*, motive_applies: bool = False) -> ModeloAmendmentCorrectionContextV1:
    """A served correction context, its words synthetic as the application would serve them."""
    kinds = (
        ModeloAmendmentKindOptionV1(
            kind=FilingDeclarationKind.COMPLEMENTARIA, words="Supplementary", help="Adds what was left out."
        ),
        ModeloAmendmentKindOptionV1(
            kind=FilingDeclarationKind.RECTIFICATIVA, words="Rectification", help="Corrects in either direction."
        ),
    )
    return ModeloAmendmentCorrectionContextV1(
        language=OutputLanguage.EN,
        filed=ModeloAmendmentFiledRecordV1(
            filing_record_id=_FILING_RECORD_ID,
            modelo_title="Served title",
            period_words="Served period",
            declaration_kind=FilingDeclarationKind.ORIGINAL,
            declaration_kind_words="Original",
            filed_at=_NOW,
            filed_on="12 November",
        ),
        kinds=kinds,
        motive_applies=motive_applies,
        motive_kind=FilingDeclarationKind.RECTIFICATIVA if motive_applies else None,
        motive_help="Choose one." if motive_applies else None,
        motives=(
            tuple(
                ModeloAmendmentMotiveOptionV1(motive=motive, words=motive.value) for motive in M303RectificativaMotive
            )
            if motive_applies
            else ()
        ),
        reason_prompt="Why are you correcting it?",
        rows=(_row("07", "Served base", "1000.00"), _row("09", "Served quota", "210.00")),
    )


def _baseline(form: ModeloWorkForm) -> ModeloEditBaselineV1:
    """An admitted edit baseline for the fixture declaration; a correction's figure is read against it."""
    identity = OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)
    return ModeloEditBaselineV1(
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.edit.apply",
            definition_contract_digest=_DIGEST,
            request_schema=identity,
            result_schema=identity,
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=identity,
            financial_operand_schema=identity,
        ),
        bucket_id="amendment-bucket",
        modelo=form.modelo,
        filing_year=form.filing_year,
        period=form.period,
        work_unit_id=form.work_unit_id,
        work_unit_record_digest=_DIGEST,
        calculation_head_digest=_DIGEST,
        current_calculation_revision_id=None,
        law_selected_revision_id=str(form.registry_revision_id),
        schema_identity=ModeloEditSchemaIdentityV1(
            schema_id="amendment-schema", schema_fingerprint=_DIGEST, completeness_manifest_digest=_DIGEST
        ),
        schema_version=1,
        permitted_surface=(),
        permitted_surface_digest=_DIGEST,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        issued_at=_NOW,
        expires_at=_NOW + timedelta(minutes=5),
        baseline_id="e" * 64,
    )


@lru_cache(maxsize=1)
def _amend_contract() -> tuple[OperationPublicDefinitionContractV1, str]:
    contracts = production_operation_registry().public_contract_set
    contract = next(
        row for row in contracts.definitions if row.definition_id == MODELO_WORK_AMEND_OPERATION_DEFINITION_ID
    )
    return contract, contracts.contract_set_digest


def _terminal(condition: OperationTerminalCondition, effect: OperationEffect) -> OperationObservationSuccessV1:
    contract, digest = _amend_contract()
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
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
        result_ref="c" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref=_EVIDENCE_CODE if condition is OperationTerminalCondition.REFUSED else None,
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


def _evidence_refusal() -> OperationErrorDetailV1:
    """The detail the amendment authority records when the filing has no imported official evidence."""
    error = AmendmentEvidenceMissingError(
        translated_message="errors.refused.refused_modelo_amendment_evidence_missing",
        context={"work_unit_id": "b" * 64, "filing_record_id": _FILING_RECORD_ID, "external_evidence_present": False},
        precondition_failure=amendment_evidence_missing_precondition(
            subject_leaf_key="modelo.work.amend", work_unit_id="b" * 64, filing_record_id=_FILING_RECORD_ID
        ),
    )
    detail = build_operation_error_detail(error)
    assert detail is not None
    return detail


class _SettlingController:
    """One submitted correction that the modal observes settling as the test said."""

    def __init__(
        self,
        observation: OperationObservationSuccessV1,
        detail: OperationErrorDetailV1 | None = None,
    ) -> None:
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
        raise AssertionError("a correction presents no review")

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        raise AssertionError("a correction presents no review")

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError("the settled correction is never cancelled")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise AssertionError("the settled correction is never detached")


@dataclass
class _AmendActions(FakeActions):
    """The workbench's actions with a correction door over a served context."""

    context: ModeloAmendmentCorrectionContextV1 = field(default_factory=_context)
    baseline: ModeloEditBaselineV1 | None = None
    controller: Callable[[], OperationControllerPort] | None = None
    submit_error: Exception | None = None
    context_error: Exception | None = None
    contexts_read: int = 0
    amended: list[tuple[str, ModeloAmendmentAnswerV1]] = field(default_factory=list)

    async def amendment_context(self, language: OutputLanguage) -> ModeloAmendmentCorrectionContextV1:
        self.contexts_read += 1
        if self.context_error is not None:
            raise self.context_error
        return self.context

    def parse_correction(
        self, row: ModeloAmendmentCorrectionRowV1, lexeme: str, language: OutputLanguage
    ) -> WorkbenchParseOutcome:
        return parse_correction_entry(row, lexeme, language, baseline=self.baseline, tax_id_format=None)

    async def amend(self, filing_record_id: str, answer: ModeloAmendmentAnswerV1) -> OperationControllerPort:
        self.amended.append((filing_record_id, answer))
        if self.submit_error is not None:
            raise self.submit_error
        assert self.controller is not None
        return self.controller()


def _recorded() -> ModeloWorkForm:
    return recorded_as_filed(synthetic_form())


def _actions(
    form: ModeloWorkForm,
    *,
    context: ModeloAmendmentCorrectionContextV1 | None = None,
    controller: Callable[[], OperationControllerPort] | None = None,
    submit_error: Exception | None = None,
    context_error: Exception | None = None,
) -> _AmendActions:
    return _AmendActions(
        context=context or _context(),
        baseline=_baseline(form),
        controller=controller,
        submit_error=submit_error,
        context_error=context_error,
    )


def _notice(screen: ModeloWorkbenchScreen) -> str:
    return str(screen.query_one("#wb-notice", Static).render())


async def _fill(app: ScreenHostApp[None], *, reason: str = _REASON, value: str = "1250.5") -> ModeloAmendmentScreen:
    dialog = app.screen
    assert isinstance(dialog, ModeloAmendmentScreen)
    dialog.query_one("#amend-reason", Input).value = reason
    dialog.query_one("#amend-value-0", Input).value = value
    return dialog


def test_the_correction_door_is_the_protocol_the_workbench_reads() -> None:
    assert isinstance(_AmendActions(), ModeloWorkbenchAmendmentV1)
    assert not isinstance(FakeActions(), ModeloWorkbenchAmendmentV1)


@pytest.mark.asyncio
async def test_a_recorded_declaration_offers_the_correction_in_served_words() -> None:
    form = _recorded()
    actions = _actions(form)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            footer_key = screen.active_bindings["m"].binding.description
            await pilot.press("m")
            await settle(pilot)
            dialog = app.screen
            assert isinstance(dialog, ModeloAmendmentScreen)
            texts = [str(widget.render()) for widget in dialog.query(Static)]
            kinds = dialog.query_one("#amend-kind", Select)
            kind_help = str(dialog.query_one("#amend-kind-help", Static).render())
            motive_shown = bool(dialog.query("#amend-motive"))

    assert footer_key == tr("tui.modelo.amendment.key", locale="en")
    assert actions.contexts_read == 1
    assert "Served title · Served period · Original · 12 November" in texts
    assert "Why are you correcting it?" in texts
    assert "[07] Served base · 1000.00 EUR" in texts
    assert kinds.value == FilingDeclarationKind.COMPLEMENTARIA.value
    assert kind_help == "Adds what was left out."
    assert not motive_shown


@pytest.mark.asyncio
async def test_a_declaration_not_recorded_as_filed_offers_no_correction() -> None:
    actions = _actions(synthetic_form())
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            still_workbench = app.screen is screen
            footer_hidden = "m" not in screen._footer_keys(140)

    assert still_workbench
    assert footer_hidden
    assert actions.contexts_read == 0


@pytest.mark.asyncio
async def test_a_recorded_declaration_without_a_correction_door_offers_none() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_recorded(), verified=True, filed=True), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            still_workbench = app.screen is screen

    assert still_workbench


@pytest.mark.asyncio
async def test_the_motive_is_asked_only_for_the_kind_that_states_one() -> None:
    form = _recorded()
    actions = _actions(form, context=_context(motive_applies=True))
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            dialog = await _fill(app)
            block = dialog.query_one("#amend-motive-block")
            shown_for_supplementary = block.display
            dialog.query_one("#amend-kind", Select).value = FilingDeclarationKind.RECTIFICATIVA.value
            await settle(pilot)
            shown_for_rectification = block.display
            help_text = str(dialog.query_one("#amend-kind-help", Static).render())
            await pilot.click("#amend-submit")
            await settle(pilot)
            unanswered = str(dialog.query_one("#amend-notice", Static).render())
            dialog.query_one("#amend-motive", Select).value = M303RectificativaMotive.RECTIFICACIONES.value
            await settle(pilot)
            await pilot.click("#amend-submit")
            await settle(pilot)

    assert not shown_for_supplementary
    assert shown_for_rectification
    assert help_text == "Corrects in either direction."
    assert unanswered == tr("tui.modelo.amendment.incomplete", locale="en")
    ((_, answer),) = actions.amended
    assert answer.kind is FilingDeclarationKind.RECTIFICATIVA
    assert answer.motive is M303RectificativaMotive.RECTIFICACIONES


@pytest.mark.asyncio
async def test_a_figure_the_parser_refuses_is_named_and_nothing_is_submitted() -> None:
    form = _recorded()
    actions = _actions(form)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            dialog = await _fill(app, value="12abc")
            await pilot.click("#amend-submit")
            await settle(pilot)
            still_open = app.screen is dialog
            refusal = str(dialog.query_one("#amend-error-0", Static).render())

    assert still_open
    assert refusal
    assert "12abc" not in refusal
    assert actions.amended == []


@pytest.mark.asyncio
async def test_a_confirmed_correction_is_recorded_locally_and_the_declaration_read_again() -> None:
    form = _recorded()
    reader = FakeReader(form=form, verified=True, filed=True)
    actions = _actions(
        form,
        controller=lambda: _SettlingController(
            _terminal(OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED)
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            loads_before = reader.loads
            await pilot.press("m")
            await settle(pilot)
            await _fill(app)
            await pilot.click("#amend-submit")
            await settle(pilot)
            back = app.screen is screen
            notice = _notice(screen)
            loads_after = reader.loads

    assert back
    ((filing_record_id, answer),) = actions.amended
    assert filing_record_id == _FILING_RECORD_ID
    assert answer.kind is FilingDeclarationKind.COMPLEMENTARIA
    assert answer.motive is None
    assert answer.reason == _REASON
    assert [(item.casilla_id, Decimal(item.value)) for item in answer.overrides] == [("07", Decimal("1250.5"))]
    assert notice == tr("tui.modelo.amendment.done", locale="en")
    assert loads_after > loads_before
    assert actions.refreshed == 1


@pytest.mark.asyncio
async def test_a_refused_correction_shows_the_served_refusal_and_its_ways_out() -> None:
    form = _recorded()
    with override_settings(cadrumo_output_language="en"):
        detail = _evidence_refusal()
        actions = _actions(
            form,
            controller=lambda: _SettlingController(
                _terminal(OperationTerminalCondition.REFUSED, OperationEffect.NONE), detail
            ),
        )
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            await _fill(app)
            await pilot.click("#amend-submit")
            await settle(pilot)
            notice = _notice(screen)
            slot = screen.query_one("#wb-operation-refusal", RefusalSlot)
            refusal = slot.refusal

    assert notice == tr("workspace.modelo.outcome.refused", locale="en")
    assert refusal is not None
    assert detail.refusal_words_language is OutputLanguage.EN
    assert refusal.sentence == detail.refusal_words
    assert refusal.verdict is not None
    assert refusal.verdict.action_id is not None
    assert actions.refreshed == 0


@pytest.mark.asyncio
async def test_an_outcome_that_may_have_committed_holds_further_corrections() -> None:
    form = _recorded()
    actions = _actions(
        form,
        controller=lambda: _SettlingController(
            _terminal(OperationTerminalCondition.INTERRUPTED, OperationEffect.UNKNOWN)
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            await _fill(app)
            await pilot.click("#amend-submit")
            await settle(pilot)
            first = _notice(screen)
            await pilot.press("m")
            await settle(pilot)
            second = (app.screen is screen, _notice(screen))

    unknown = tr("tui.modelo.amendment.unknown", locale="en")
    assert first == unknown
    assert second == (True, unknown)
    assert actions.contexts_read == 1
    assert len(actions.amended) == 1
    assert actions.refreshed == 0


@pytest.mark.asyncio
async def test_a_lost_start_acknowledgement_is_unknown_not_a_refusal() -> None:
    form = _recorded()
    actions = _actions(
        form,
        submit_error=ModeloLifecycleActionUnavailableError(
            "connection_closed", context={"operation_id": _OPERATION_ID, "effect": OperationEffect.UNKNOWN.value}
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            await _fill(app)
            await pilot.click("#amend-submit")
            await settle(pilot)
            notice = _notice(screen)

    assert notice == tr("tui.modelo.amendment.unknown", locale="en")


@pytest.mark.asyncio
async def test_an_unreadable_correction_says_it_is_unavailable() -> None:
    form = _recorded()
    actions = _actions(
        form,
        context_error=ModeloLifecycleActionUnavailableError(
            translated_message="workspace.modelo.correction.unavailable"
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot)
            await pilot.press("m")
            await settle(pilot)
            still_workbench = app.screen is screen
            notice = _notice(screen)

    assert still_workbench
    assert notice == tr("workspace.modelo.correction.unavailable", locale="en")
    assert actions.amended == []
