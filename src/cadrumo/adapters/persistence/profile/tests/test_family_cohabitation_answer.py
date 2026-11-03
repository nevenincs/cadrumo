"""A single parent states whether they live with the child's other parent, and the profile view serves the answer.

Art. 84.2.4º LIRPF denies the joint-taxation reduction of the single-parent unit
while they do. These tests drive the real wizard patch writer and the desktop's
one-field writer against an encrypted profile, then read the household
questions back through the ``family_rows`` stream of the profile view. Nothing
stated is not "no": it is served as nothing stated, and the question is served
only while the family situation makes it relevant.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.capsule_record import ProfileRecordConflictError
from cadrumo.application.user_profile.fact_write import apply_manager_profile_field_mutation
from cadrumo.application.user_profile.family_question import (
    CONVIVE_CON_OTRO_PROGENITOR_QUESTION_ID,
    ProfileViewFamilyQuestionItem,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_MAX_RESULT_BYTES,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.application.user_profile.view_reader import read_profile_view_page
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.commands import run_wizard_persistence_path
from cadrumo.application.wizard.patch_edit import apply_profile_patch
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.values import UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PATH = "renta_family.convive_con_otro_progenitor"
_SITUATION_ID = "situacion-familiar"
_QUESTION_ID = CONVIVE_CON_OTRO_PROGENITOR_QUESTION_ID


class _World:
    """One registered, authenticated profile and the wizard flow pinned to its authority."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation
        self.flow = build_setup_flow(operation)

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def patch(self, supplied: dict[str, str]) -> UserProfileRecord:
        current = self.record()
        return apply_profile_patch(
            flow=self.flow,
            profile_id=self.profile_id,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            supplied=supplied,
            colegio_concertado=None,
            operation=self.operation,
        )

    def stored(self) -> str | None:
        return record_to_path_values(self.record()).get(_PATH)

    def questions(self, language: str = "en") -> list[ProfileViewFamilyQuestionItem]:
        """The ``family_rows`` stream as the profile view serves it, read to its last page."""
        items: list[object] = []
        cursor = 0
        revision: int | None = None
        digest: ContentDigest | None = None
        while True:
            page = read_profile_view_page(
                ProfileViewOperationRequest(
                    profile_id=UUID(self.profile_id),
                    page_kind=ProfileViewPageKind.FAMILY_ROWS,
                    cursor=cursor,
                    output_language=OutputLanguage(language),
                    expected_revision=revision,
                    expected_content_digest=digest,
                ),
                authority_operation=self.operation,
            )
            assert page.outcome == "page"
            assert len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES
            items.extend(page.items)
            if page.next_cursor is None:
                return [item for item in items if isinstance(item, ProfileViewFamilyQuestionItem)]
            cursor = page.next_cursor
            revision, digest = page.record_revision, page.content_digest


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"family-cohabitation-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Family cohabitation",
            passphrase=secret,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=outcome.label,
            passphrase_callback=secret.__str__,
            profile_decode_context=operation.profile_decode_context(),
        )
        register_minimal_profile(profile_id=outcome.profile_id)
        yield _World(outcome.profile_id, operation)


def test_nothing_is_served_until_the_family_situation_makes_the_question_relevant(world: _World) -> None:
    assert world.questions() == []
    world.patch({_SITUATION_ID: "casado"})
    assert world.questions() == []


@pytest.mark.parametrize("situation", ["soltero", "separado_divorciado", "pareja_hecho_registrada"])
def test_a_single_parent_is_served_the_question_with_nothing_stated(world: _World, situation: str) -> None:
    world.patch({_SITUATION_ID: situation})

    (question,) = world.questions()

    assert question.question_id == _QUESTION_ID
    assert question.path == _PATH
    assert question.saved_value is None
    assert [choice.value for choice in question.choices] == ["true", "false"]
    assert world.stored() is None


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_question_is_served_in_the_words_setup_asks_it(world: _World, language: str) -> None:
    world.patch({_SITUATION_ID: "soltero"})

    (question,) = world.questions(language)

    assert question.prompt == tr(f"wizard.setup.family.{_QUESTION_ID}.prompt", locale=language)
    assert question.help == tr(f"wizard.setup.family.{_QUESTION_ID}.help", locale=language)
    assert [choice.label for choice in question.choices] == [
        tr("flows.confirm.yes", locale=language),
        tr("flows.confirm.no", locale=language),
    ]


@pytest.mark.parametrize(("answer", "stated"), [("true", True), ("false", False)])
def test_the_wizard_patch_states_the_answer_and_the_view_serves_it(world: _World, answer: str, stated: bool) -> None:
    world.patch({_SITUATION_ID: "soltero"})

    world.patch({_QUESTION_ID: answer})

    assert next(fact.value for fact in world.record().facts if fact.path == _PATH) is stated
    assert world.stored() == answer
    (question,) = world.questions()
    assert question.saved_value == answer


def test_an_edit_that_omits_the_answer_keeps_it_and_one_that_clears_it_takes_it_back(world: _World) -> None:
    world.patch({_SITUATION_ID: "soltero", _QUESTION_ID: "false"})

    world.patch({"taxpayer-sex": "H"})
    assert world.stored() == "false"

    world.patch({_QUESTION_ID: ""})
    assert world.stored() is None
    (question,) = world.questions()
    assert question.saved_value is None


def test_an_answer_to_another_situation_stays_stored_but_is_not_asked(world: _World) -> None:
    world.patch({_SITUATION_ID: "soltero", _QUESTION_ID: "true"})

    world.patch({_SITUATION_ID: "casado"})

    assert world.stored() == "true"
    assert world.questions() == []


def test_the_patch_is_bound_to_the_revision_it_was_read_at(world: _World) -> None:
    world.patch({_SITUATION_ID: "soltero"})
    stale = world.record()
    world.patch({_QUESTION_ID: "false"})

    with pytest.raises(ProfileRecordConflictError, match="baseline is stale"):
        apply_profile_patch(
            flow=world.flow,
            profile_id=world.profile_id,
            expected_revision=stale.record_revision,
            expected_content_digest=stale.content_digest,
            supplied={_QUESTION_ID: "true"},
            colegio_concertado=None,
            operation=world.operation,
        )

    assert world.stored() == "false"


def test_a_quiet_edit_that_never_names_the_question_leaves_the_fact_absent(world: _World) -> None:
    world.patch({_SITUATION_ID: "soltero"})
    before = world.record()

    values, _changed = run_wizard_persistence_path(
        world.flow,
        "edit",
        {},
        {},
        scalar_profile_values={},
        quiet=False,
        accept_defaults=True,
        profile_name="Family cohabitation",
        profile_id=world.profile_id,
        operation=world.operation,
    )

    assert _PATH not in values
    assert world.stored() is None
    assert world.record().content_digest == before.content_digest


def test_the_desktop_writes_the_answer_through_the_one_field_writer_against_its_baseline(world: _World) -> None:
    world.patch({_SITUATION_ID: "soltero"})
    read = world.record()

    apply_manager_profile_field_mutation(
        profile_id=world.profile_id,
        path=_PATH,
        value="true",
        expected_revision=read.record_revision,
        expected_content_digest=read.content_digest,
        profile_decode_context=world.operation.profile_decode_context(),
    )

    (question,) = world.questions()
    assert question.saved_value == "true"

    # A write against the baseline it already moved past is refused and writes nothing.
    with pytest.raises(ProfileRecordConflictError, match="baseline is stale"):
        apply_manager_profile_field_mutation(
            profile_id=world.profile_id,
            path=_PATH,
            value="false",
            expected_revision=read.record_revision,
            expected_content_digest=read.content_digest,
            profile_decode_context=world.operation.profile_decode_context(),
        )
    assert world.stored() == "true"

    # The empty value takes the statement back: nothing stated again, which is not "false".
    moved = world.record()
    apply_manager_profile_field_mutation(
        profile_id=world.profile_id,
        path=_PATH,
        value="",
        expected_revision=moved.record_revision,
        expected_content_digest=moved.content_digest,
        profile_decode_context=world.operation.profile_decode_context(),
    )
    assert world.stored() is None
    (question,) = world.questions()
    assert question.saved_value is None


def test_a_value_that_is_neither_yes_nor_no_is_refused_and_writes_nothing(world: _World) -> None:
    world.patch({_SITUATION_ID: "soltero"})
    read = world.record()

    with pytest.raises(Exception, match="convive_con_otro_progenitor"):
        apply_manager_profile_field_mutation(
            profile_id=world.profile_id,
            path=_PATH,
            value="maybe",
            expected_revision=read.record_revision,
            expected_content_digest=read.content_digest,
            profile_decode_context=world.operation.profile_decode_context(),
        )

    assert world.stored() is None
    assert world.record().content_digest == read.content_digest
