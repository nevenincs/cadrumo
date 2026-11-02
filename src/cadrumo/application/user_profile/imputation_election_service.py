"""Read and state the RIRPF art. 7 election for one ejercicio through the setup wizard's questions.

The setup wizard owns the election's questions, their words and the dated
facts an answer becomes (:func:`~cadrumo.application.wizard.imputation_election.election_changes`).
This module only reads those facts for one ejercicio and routes a change for one
ejercicio through the same questions, so the election has one validator and one
writer whichever surface collects it.

Core types: :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ...core.config import override_settings
from ...core.i18n.render import tr
from ..aggregation.renta_imputation import declared_imputation_criteria
from ..wizard.catalogue import build_setup_flow
from ..wizard.imputation_election import (
    ACCOUNTING_PROFILE_PATH,
    ACCOUNTING_QUESTION_ID,
    CRITERION_PROFILE_PATH,
    CRITERION_QUESTION_ID,
    YEAR_QUESTION_ID,
    election_changes,
)
from ..wizard.models import WizardFlow, WizardQuestion, iter_conditions
from .edit_baseline import require_profile_edit_baseline
from .fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from .field_help import profile_field_ejercicio_answers
from .imputation_election_contracts import (
    ProfileImputationElectionAnswer,
    ProfileImputationElectionQuestion,
    ProfileImputationElectionReadRequest,
    ProfileImputationElectionReadResult,
    ProfileImputationElectionSetRequest,
)
from .profile_record_repository import ProfileRecordRepository
from .question_view import profile_question_choices

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.user_profile.values import UserProfileFact, UserProfileRecord


def _stated_in(fact: UserProfileFact, year: int) -> bool:
    """Whether ``fact`` is a dated statement in force during ``year``; an undated fact states no year."""
    return (
        fact.valid_from is not None
        and fact.value is not None
        and fact.valid_from <= date(year, 12, 31)
        and (fact.valid_to is None or fact.valid_to >= date(year, 1, 1))
    )


def _token(value: object) -> str:
    return ("true" if value else "false") if isinstance(value, bool) else str(value)


def _answer(facts: Iterable[UserProfileFact], path: str, year: int) -> ProfileImputationElectionAnswer:
    values = {_token(fact.value) for fact in facts if fact.path == path and _stated_in(fact, year)}
    if not values:
        return ProfileImputationElectionAnswer(state="undeclared")
    if len(values) > 1:
        return ProfileImputationElectionAnswer(state="contradictory")
    return ProfileImputationElectionAnswer(state="declared", value=next(iter(values)))


def _criterion_answer(record: UserProfileRecord, year: int) -> ProfileImputationElectionAnswer:
    """Serve the criterion the imputation resolver reads for ``year``, never a default."""
    declared = declared_imputation_criteria(record).declared(year)
    if declared is not None:
        return ProfileImputationElectionAnswer(state="declared", value=declared.value)
    answer = _answer(record.facts, CRITERION_PROFILE_PATH, year)
    return answer if answer.state != "declared" else ProfileImputationElectionAnswer(state="contradictory")


def _questions(flow: WizardFlow) -> dict[str, WizardQuestion]:
    wanted = {CRITERION_QUESTION_ID, YEAR_QUESTION_ID, ACCOUNTING_QUESTION_ID}
    questions = {
        question.id: question for section in flow.sections for question in section.questions if question.id in wanted
    }
    if questions.keys() != wanted:
        raise ValueError(f"wizard flow {flow.id!r} does not declare the imputation election questions")
    return questions


def _question_words(question: WizardQuestion) -> ProfileImputationElectionQuestion:
    return ProfileImputationElectionQuestion(
        question_id=question.id,
        path=question.profile_key,
        prompt=tr(question.prompt),
        help=None if question.help is None else tr(question.help),
        choices=profile_question_choices(question),
    )


def read_imputation_election(
    request: ProfileImputationElectionReadRequest,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> ProfileImputationElectionReadResult:
    """Read one ejercicio's election from the exact current encrypted record, in the requested words."""
    profile_id = str(request.profile_id)
    decode = authority_operation.profile_decode_context()
    record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
    flow = build_setup_flow(authority_operation)
    questions = _questions(flow)
    accounting = questions[ACCOUNTING_QUESTION_ID]
    with override_settings(cadrumo_output_language=request.output_language.value):
        return ProfileImputationElectionReadResult(
            profile_id=request.profile_id,
            record_revision=record.record_revision,
            content_digest=record.content_digest,
            tax_year=request.tax_year,
            criterion=_criterion_answer(record, request.tax_year),
            codigo_comercio_accounting=_answer(record.facts, ACCOUNTING_PROFILE_PATH, request.tax_year),
            criterion_statements=profile_field_ejercicio_answers(flow, record.facts)[CRITERION_PROFILE_PATH].statements,
            criterion_question=_question_words(questions[CRITERION_QUESTION_ID]),
            year_question=_question_words(questions[YEAR_QUESTION_ID]),
            accounting_question=_question_words(accounting),
            accounting_asked_for_criteria=tuple(
                condition.equals
                for condition in iter_conditions(accounting.visible_when)
                if condition.question_id == CRITERION_QUESTION_ID and condition.equals is not None
            ),
            words_language=request.output_language,
        )


def apply_imputation_election(
    request: ProfileImputationElectionSetRequest,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> UserProfileRecord:
    """Validate one ejercicio's answers as the setup wizard does and CAS-publish the dated facts.

    Raises:
        ProfileRecordConflictError: The profile moved past the expected revision or digest.
        WizardValidationError: An answer or the ejercicio is outside what its question accepts.
    """
    profile_id = str(request.profile_id)
    decode = authority_operation.profile_decode_context()
    current = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
    supplied = {YEAR_QUESTION_ID: str(request.tax_year)}
    if request.criterion is not None:
        supplied[CRITERION_QUESTION_ID] = request.criterion
    if request.codigo_comercio_accounting is not None:
        supplied[ACCOUNTING_QUESTION_ID] = request.codigo_comercio_accounting
    require_profile_edit_baseline(
        current,
        expected_revision=request.expected_revision,
        expected_content_digest=request.expected_content_digest,
        field_paths=tuple(
            path
            for question_id, path in (
                (CRITERION_QUESTION_ID, CRITERION_PROFILE_PATH),
                (ACCOUNTING_QUESTION_ID, ACCOUNTING_PROFILE_PATH),
            )
            if question_id in supplied
        ),
    )
    changes = election_changes(build_setup_flow(authority_operation), supplied)
    return apply_profile_fact_changes(
        profile_id=profile_id,
        changes=changes,
        door=ProfileFactWriteDoor.MANAGER_IMPUTATION_ELECTION,
        expected_record=current,
        profile_decode_context=decode,
    )


__all__ = ["apply_imputation_election", "read_imputation_election"]
