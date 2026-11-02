"""The RIRPF art. 7 election the setup flow states for one ejercicio.

The election binds a taxpayer for three years and is stated in each return, so
it is a fact about an ejercicio, not about the profile. The setup flow
therefore asks for the ejercicio next to the answer, and writes the criterion
and the Codigo de Comercio accounting fact dated to that whole ejercicio. An
undated fact states no year and the imputation resolver ignores it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...domain.user_profile.values import UserProfileFact
from .errors import WizardMissingFlagError, WizardPreconditionCondition, wizard_no_action_verdict
from .models import WizardFlow, WizardQuestion

if TYPE_CHECKING:
    from pydantic import BaseModel

CRITERION_QUESTION_ID: Final[str] = "irpf-activity-income-imputation-criterion"
YEAR_QUESTION_ID: Final[str] = "irpf-activity-income-imputation-year"
ACCOUNTING_QUESTION_ID: Final[str] = "irpf-codigo-comercio-accounting"

ELECTION_QUESTION_IDS: Final[frozenset[str]] = frozenset(
    {CRITERION_QUESTION_ID, YEAR_QUESTION_ID, ACCOUNTING_QUESTION_ID}
)
"""Questions whose answers are written by :func:`election_changes`, never as an undated fact."""

CRITERION_PROFILE_PATH: Final[str] = "irpf.activity_income_imputation_criterion"
ACCOUNTING_PROFILE_PATH: Final[str] = "irpf.codigo_comercio_accounting"

_STATED_QUESTION_IDS: Final[tuple[str, ...]] = (CRITERION_QUESTION_ID, ACCOUNTING_QUESTION_ID)
_QUESTION_PATHS: Final[Mapping[str, str]] = {
    CRITERION_QUESTION_ID: CRITERION_PROFILE_PATH,
    ACCOUNTING_QUESTION_ID: ACCOUNTING_PROFILE_PATH,
}


def election_changes(flow: WizardFlow, supplied: Mapping[str, str]) -> tuple[UserProfileFact, ...]:
    """Return the dated fact changes the election answers in ``supplied`` state.

    An answer becomes a fact dated 1 January to 31 December of the stated
    ejercicio; a blank answer becomes a dated fact with no value, which the fact
    writer reads as clearing that ejercicio only. A question absent from
    ``supplied`` is left as stored.

    Raises:
        WizardMissingFlagError: A criterion or accounting answer arrived without
            the ejercicio it is stated for.
        WizardValidationError: The ejercicio, criterion or accounting answer is
            outside what its question accepts.
    """
    from .widgets import validate_widget_answer

    questions = _election_questions(flow)
    year_raw = supplied.get(YEAR_QUESTION_ID, "")
    year = validate_widget_answer(questions[YEAR_QUESTION_ID], year_raw)
    stated = tuple(question_id for question_id in _STATED_QUESTION_IDS if question_id in supplied)
    if not stated:
        return ()
    if not year:
        raise _year_required(flow)
    window = {"valid_from": date(int(year), 1, 1), "valid_to": date(int(year), 12, 31)}
    changes: list[UserProfileFact] = []
    for question_id in stated:
        question = questions[question_id]
        answer = validate_widget_answer(question, supplied[question_id])
        if question.profile_key is None:
            raise ValueError(f"election question {question_id!r} must be bound to a profile path")
        stated_fact = {"path": question.profile_key, "value": answer or None, **window}
        changes.append(UserProfileFact.model_validate(stated_fact))
    return tuple(changes)


def election_answers(answers: BaseModel, *, stored: Mapping[str, str]) -> dict[str, str]:
    """Return the election answers a completed answers model states, as canonical tokens.

    A blank answer is unanswered here, not a clear: a full setup run leaves what
    it did not ask about as stored. So is an answer with no ejercicio that repeats
    the value ``stored`` holds at its path, which is what a run seeded from the
    profile carries for a question nobody changed.
    """
    stated: dict[str, str] = {}
    for question_id in sorted(ELECTION_QUESTION_IDS):
        value = getattr(answers, question_id.replace("-", "_"), "")
        if value == "":
            continue
        stated[question_id] = ("true" if value else "false") if isinstance(value, bool) else str(value)
    if YEAR_QUESTION_ID not in stated:
        for question_id, path in _QUESTION_PATHS.items():
            if question_id in stated and stored.get(path) == stated[question_id]:
                del stated[question_id]
    return stated


def _election_questions(flow: WizardFlow) -> dict[str, WizardQuestion]:
    questions = {
        question.id: question
        for section in flow.sections
        for question in section.questions
        if question.id in ELECTION_QUESTION_IDS
    }
    if questions.keys() != ELECTION_QUESTION_IDS:
        raise ValueError(f"wizard flow {flow.id!r} does not declare the imputation election questions")
    return questions


def _year_required(flow: WizardFlow) -> WizardMissingFlagError:
    return WizardMissingFlagError(
        translated_message="application.wizard.errors.imputation_year_required",
        context={
            "flow_id": flow.id,
            "missing": (YEAR_QUESTION_ID,),
            "missing_flags": f"--{YEAR_QUESTION_ID}",
        },
        precondition_verdict=wizard_no_action_verdict(
            condition=WizardPreconditionCondition.REQUIRED_FLAGS_SUPPLIED,
            facts={"required_flags_supplied": False, "missing_flag_count": 1},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


__all__ = [
    "ACCOUNTING_PROFILE_PATH",
    "ACCOUNTING_QUESTION_ID",
    "CRITERION_PROFILE_PATH",
    "CRITERION_QUESTION_ID",
    "ELECTION_QUESTION_IDS",
    "YEAR_QUESTION_ID",
    "election_answers",
    "election_changes",
]
