"""The imputation election operations read and state one ejercicio through the setup wizard's questions.

These tests drive the operations' read and write functions against an
encrypted profile, and read the result back through the imputation resolver,
so the operations and the setup wizard are checked to share one writer.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.aggregation.renta_imputation import ActivityImputationCriterion, declared_imputation_criteria
from cadrumo.application.user_profile.capsule_record import ProfileRecordConflictError
from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from cadrumo.application.user_profile.imputation_election_contracts import (
    ProfileImputationElectionReadRequest,
    ProfileImputationElectionReadResult,
    ProfileImputationElectionSetRequest,
)
from cadrumo.application.user_profile.imputation_election_service import (
    apply_imputation_election,
    read_imputation_election,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.wizard.errors import WizardValidationError
from cadrumo.application.wizard.imputation_election import CRITERION_PROFILE_PATH
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.values import UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = 2024
_SECOND = 2025


class _World:
    """One registered, authenticated profile and the authority it is read under."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def read(self, year: int, language: OutputLanguage = OutputLanguage.EN) -> ProfileImputationElectionReadResult:
        request = ProfileImputationElectionReadRequest(
            profile_id=UUID(self.profile_id), tax_year=year, output_language=language
        )
        return read_imputation_election(request, authority_operation=self.operation)

    def state(self, year: int, *, criterion: str | None = None, accounting: str | None = None) -> UserProfileRecord:
        current = self.record()
        request = ProfileImputationElectionSetRequest(
            profile_id=UUID(self.profile_id),
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            tax_year=year,
            criterion=criterion,
            codigo_comercio_accounting=accounting,
        )
        return apply_imputation_election(request, authority_operation=self.operation)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"imputation-election-operation-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Imputation election operation",
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


def test_an_unstated_ejercicio_reads_undeclared_and_never_as_a_criterion(world: _World) -> None:
    read = world.read(_SECOND)

    assert read.criterion.state == "undeclared"
    assert read.criterion.value is None
    assert read.codigo_comercio_accounting.state == "undeclared"
    assert read.criterion_statements == ()
    assert read.record_revision == world.record().record_revision
    assert read.content_digest == world.record().content_digest


def test_the_read_serves_the_wizard_questions_choices_in_schema_order(world: _World) -> None:
    read = world.read(_SECOND)

    schema_tokens = world.operation.profile_schema().field(CRITERION_PROFILE_PATH).enum_values
    assert tuple(choice.value for choice in read.criterion_question.choices) == tuple(schema_tokens)
    assert read.criterion_question.path == CRITERION_PROFILE_PATH
    assert tuple(choice.value for choice in read.accounting_question.choices) == ("true", "false")
    assert read.accounting_asked_for_criteria == (ActivityImputationCriterion.COBROS_Y_PAGOS.value,)
    assert read.year_question.path is None


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_served_word_is_a_translation_and_not_a_catalogue_key(world: _World, language: OutputLanguage) -> None:
    read = world.read(_SECOND, language)

    assert read.words_language is language
    questions = (read.criterion_question, read.year_question, read.accounting_question)
    words = [question.prompt for question in questions]
    words += [question.help for question in questions if question.help is not None]
    words += [choice.label for question in questions for choice in question.choices]
    assert all(word.strip() for word in words)
    assert not any(word.startswith(("wizard.", "flows.")) for word in words)


def test_the_served_words_follow_the_requested_language(world: _World) -> None:
    prompts = {language: world.read(_SECOND, language).criterion_question.prompt for language in OutputLanguage}

    assert len(set(prompts.values())) == len(prompts)


def test_stating_a_criterion_writes_that_ejercicio_only(world: _World) -> None:
    before = world.record()
    after = world.state(_FIRST, criterion="devengo")

    assert after.record_revision == before.record_revision + 1
    criteria = declared_imputation_criteria(world.record())
    assert criteria.declared(_FIRST) is ActivityImputationCriterion.DEVENGO
    assert criteria.declared(_SECOND) is None
    assert [
        (fact.valid_from, fact.valid_to, fact.value)
        for fact in world.record().facts
        if fact.path == CRITERION_PROFILE_PATH
    ] == [(date(_FIRST, 1, 1), date(_FIRST, 12, 31), "devengo")]
    assert world.read(_FIRST).criterion.value == "devengo"
    assert world.read(_SECOND).criterion.state == "undeclared"


def test_a_cash_election_with_its_accounting_answer_reads_back_with_the_earlier_ejercicio(world: _World) -> None:
    world.state(_FIRST, criterion="devengo")
    world.state(_SECOND, criterion="cobros_y_pagos", accounting="false")

    read = world.read(_SECOND)
    assert read.criterion.value == "cobros_y_pagos"
    assert read.codigo_comercio_accounting.value == "false"
    assert [(statement.ejercicio, statement.value) for statement in read.criterion_statements] == [
        (_FIRST, "devengo"),
        (_SECOND, "cobros_y_pagos"),
    ]
    assert world.read(_FIRST).codigo_comercio_accounting.state == "undeclared"


def test_an_accounting_answer_alone_leaves_the_criterion_as_stored(world: _World) -> None:
    world.state(_SECOND, criterion="cobros_y_pagos")
    world.state(_SECOND, accounting="true")

    read = world.read(_SECOND)
    assert read.criterion.value == "cobros_y_pagos"
    assert read.codigo_comercio_accounting.value == "true"


def test_an_empty_answer_clears_that_ejercicio_and_keeps_the_others(world: _World) -> None:
    world.state(_FIRST, criterion="devengo")
    world.state(_SECOND, criterion="devengo")

    world.state(_FIRST, criterion="")

    assert world.read(_FIRST).criterion.state == "undeclared"
    assert world.read(_SECOND).criterion.value == "devengo"


def test_stating_the_stored_answer_again_publishes_nothing(world: _World) -> None:
    world.state(_FIRST, criterion="devengo")
    before = world.record()

    after = world.state(_FIRST, criterion="devengo")

    assert after.record_revision == before.record_revision
    assert after.content_digest == before.content_digest


def test_a_stale_revision_is_refused_and_writes_nothing(world: _World) -> None:
    current = world.record()
    world.state(_FIRST, criterion="devengo")
    stale = ProfileImputationElectionSetRequest(
        profile_id=UUID(world.profile_id),
        expected_revision=current.record_revision,
        expected_content_digest=current.content_digest,
        tax_year=_SECOND,
        criterion="cobros_y_pagos",
    )

    with pytest.raises(ProfileRecordConflictError):
        apply_imputation_election(stale, authority_operation=world.operation)
    assert world.read(_SECOND).criterion.state == "undeclared"


@pytest.mark.parametrize(
    ("year", "criterion", "accounting"),
    [
        (_FIRST, "accrual", None),
        (_FIRST, "devengo", "perhaps"),
        (25, "devengo", None),
    ],
)
def test_an_answer_the_wizard_question_does_not_accept_is_refused(
    world: _World, year: int, criterion: str, accounting: str | None
) -> None:
    before = world.record()

    with pytest.raises(WizardValidationError):
        world.state(year, criterion=criterion, accounting=accounting)
    assert world.record().content_digest == before.content_digest


def test_a_change_that_states_nothing_is_refused_at_the_contract() -> None:
    with pytest.raises(ValidationError):
        ProfileImputationElectionSetRequest(
            profile_id=UUID(int=1),
            expected_revision=1,
            expected_content_digest="0" * 64,
            tax_year=_FIRST,
        )


def test_two_statements_in_force_for_one_ejercicio_read_contradictory(world: _World) -> None:
    world.state(_SECOND, criterion="devengo")
    current = world.record()
    spanning = UserProfileFact(
        path=CRITERION_PROFILE_PATH,
        value="cobros_y_pagos",
        valid_from=date(_FIRST, 1, 1),
        valid_to=date(_SECOND, 12, 31),
    )
    apply_profile_fact_changes(
        profile_id=world.profile_id,
        changes=(spanning,),
        door=ProfileFactWriteDoor.PATCH,
        expected_record=current,
        profile_decode_context=world.operation.profile_decode_context(),
    )

    assert declared_imputation_criteria(world.record()).declared(_SECOND) is None
    read = world.read(_SECOND)
    assert read.criterion.state == "contradictory"
    assert read.criterion.value is None
    assert world.read(_FIRST).criterion.value == "cobros_y_pagos"
