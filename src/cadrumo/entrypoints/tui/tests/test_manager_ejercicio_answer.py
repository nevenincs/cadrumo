"""The profile page answers a field stated per ejercicio through the wizard's own questions."""

from __future__ import annotations

import pytest
from textual.widgets import Input, OptionList

from ....adapters.persistence.storage.tests.profile_capsule_runtime import load_test_profile_record
from ....application.aggregation.renta_imputation import ActivityImputationCriterion, declared_imputation_criteria
from ....application.user_profile.field_help import ProfileFieldEjercicioAnswer
from ....application.user_profile.overview import ProfileFieldView, ProfileOverview, build_profile_overview
from ....application.wizard.catalogue import build_setup_flow
from ....application.wizard.imputation_election import CRITERION_PROFILE_PATH, YEAR_QUESTION_ID
from ....application.wizard.patch_edit import apply_profile_patch
from ....core.bucket_pointer import require_active_bucket_id
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ..components.host import ScreenHostApp
from ..profile.edit_screens import FieldEditScreen
from ..profile.overview import ProfileManagerScreen
from .manager_pilot import wait_until_settled
from .manager_subject_profile import publish_manager_subject_session, registered_manager_subject
from .settling import settle

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (160, 60)
_LABEL = "Ejercicio Subject"
_CREDENTIAL_INPUT = "manager-ejercicio-operator-secret"
_FIRST = 2000
_SECOND = 2001


def _overview() -> ProfileOverview:
    with bundled_indexed_authority().operation() as operation:
        publish_manager_subject_session(label=_LABEL, passphrase=_CREDENTIAL_INPUT)
        return build_profile_overview(
            load_test_profile_record(require_active_bucket_id()),
            label=_LABEL,
            schema=operation.profile_schema(),
            flow=build_setup_flow(operation),
        )


def _persist_through_the_patch_owner(
    answer: ProfileFieldEjercicioAnswer, value: str, ejercicio: str, revision: int, digest: str
) -> ProfileOverview:
    with bundled_indexed_authority().operation() as operation:
        publish_manager_subject_session(label=_LABEL, passphrase=_CREDENTIAL_INPUT)
        apply_profile_patch(
            flow=build_setup_flow(operation),
            profile_id=require_active_bucket_id(),
            expected_revision=revision,
            expected_content_digest=digest,
            supplied={answer.question_id: value, answer.year_question_id: ejercicio},
            colegio_concertado=None,
            operation=operation,
        )
    return _overview()


def _refuse_the_one_field_door(*_args: object) -> ProfileOverview:
    raise AssertionError("a field stated per ejercicio must not use the one-field door")


def _criterion_field(overview: ProfileOverview) -> ProfileFieldView:
    return next(
        field for section in overview.sections for field in section.fields if field.path == CRITERION_PROFILE_PATH
    )


async def _answer(criterion: ActivityImputationCriterion, ejercicio: str | None) -> None:
    """Answer the criterion through the page's real dialogs; no ejercicio cancels the second one."""
    overview = _overview()
    field = _criterion_field(overview)
    page = ProfileManagerScreen(
        overview, persist=_refuse_the_one_field_door, persist_ejercicio=_persist_through_the_patch_owner
    )
    async with ScreenHostApp(page).run_test(size=_TERMINAL_SIZE) as pilot:
        await settle(pilot)
        page.app.push_screen(FieldEditScreen(field), page._apply_edit_for(field))
        await settle(pilot)
        options = page.app.screen.query_one("#edit-options", OptionList)
        options.highlighted = [choice.value for choice in field.choices].index(criterion.value)
        await pilot.click("#btn-edit-save")
        await settle(pilot)
        asked = page.app.screen
        assert isinstance(asked, FieldEditScreen)
        if ejercicio is None:
            asked.action_cancel()
        else:
            asked.query_one("#edit-input", Input).value = ejercicio
            await pilot.click("#btn-edit-save")
        await wait_until_settled(page, pilot)
        pilot.app.exit(None)


@pytest.mark.asyncio
async def test_an_answer_for_a_later_ejercicio_keeps_the_earlier_one(tmp_path) -> None:
    with registered_manager_subject(tmp_path, label=_LABEL, passphrase=_CREDENTIAL_INPUT):
        answer = _criterion_field(_overview()).ejercicio_answer
        assert answer is not None
        assert answer.year_question_id == YEAR_QUESTION_ID
        assert answer.statements == ()

        await _answer(ActivityImputationCriterion.COBROS_Y_PAGOS, str(_FIRST))
        await _answer(ActivityImputationCriterion.DEVENGO, str(_SECOND))

        publish_manager_subject_session(label=_LABEL, passphrase=_CREDENTIAL_INPUT)
        criteria = declared_imputation_criteria(load_test_profile_record(require_active_bucket_id()))
        assert criteria.declared(_FIRST) is ActivityImputationCriterion.COBROS_Y_PAGOS
        assert criteria.declared(_SECOND) is ActivityImputationCriterion.DEVENGO
        answer = _criterion_field(_overview()).ejercicio_answer
        assert answer is not None
        assert [(item.ejercicio, item.value) for item in answer.statements] == [
            (_FIRST, ActivityImputationCriterion.COBROS_Y_PAGOS.value),
            (_SECOND, ActivityImputationCriterion.DEVENGO.value),
        ]


@pytest.mark.asyncio
async def test_a_cancelled_ejercicio_writes_nothing(tmp_path) -> None:
    with registered_manager_subject(tmp_path, label=_LABEL, passphrase=_CREDENTIAL_INPUT):
        publish_manager_subject_session(label=_LABEL, passphrase=_CREDENTIAL_INPUT)
        before = load_test_profile_record(require_active_bucket_id()).content_digest

        await _answer(ActivityImputationCriterion.DEVENGO, None)

        publish_manager_subject_session(label=_LABEL, passphrase=_CREDENTIAL_INPUT)
        assert load_test_profile_record(require_active_bucket_id()).content_digest == before
