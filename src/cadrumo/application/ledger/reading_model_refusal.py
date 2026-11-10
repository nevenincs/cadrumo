"""The refusal of a document read for want of a picked reading model, and what it serves.

The agent service refuses a run with ``no_selection`` when the person has
picked no model for the role. The refusal's verdict states that as a fact. A
refusal worded as "the automatic reader could not run" hides it, so a person
could not tell which condition to put right. This module reads the fact off the
verdict and gives the three things a frontend renders for it: the refusal's own
sentence, the step that leads to the choice, and the stable code.

The choice is made in the window beside the agent, so the step is the closed
``choose_reading_model`` kind. Whether a surface can offer it is the surface's
own knowledge; the backend serves the step and its words and nothing else.
"""

from __future__ import annotations

from typing import Final

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ..operations.error_detail import served_words_language
from ..operations.next_step import OperationChooseReadingModelStepV1, OperationNextStepV1, OperationNextStepWording
from ..operator_actions.models import PreconditionVerdict
from .evidence_errors import EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY

__all__ = [
    "NO_READING_MODEL_LOCALE_KEY",
    "model_run_refusal_code",
    "reader_refusal_locale_key",
    "reader_refusal_next_step",
    "reading_model_not_selected",
    "served_reading_model_refusal",
]

NO_READING_MODEL_LOCALE_KEY: Final = "errors.refused.refused_llm_no_model_selected"
"""The refusal sentence for a role with no picked model: it says to pick one and where."""

_CHOOSE_READING_MODEL_LOCALE_KEY: Final = "application.ledger.evidence.next_step.choose_reading_model"
_REFUSAL_FACT: Final = "model_run_refusal"


def model_run_refusal_code(verdict: PreconditionVerdict | None) -> str | None:
    """Return the agent service's refusal code a verdict states, or ``None`` when it states none."""
    if verdict is None:
        return None
    for evidence in verdict.evidence:
        code = evidence.values.get(_REFUSAL_FACT)
        if isinstance(code, str):
            return code
    return None


def reading_model_not_selected(refusal_code: str | None) -> bool:
    """Whether ``refusal_code`` is the agent service's refusal for a role with no picked model."""
    return refusal_code == ModelRunRefusalCode.NO_SELECTION.value


def reader_refusal_locale_key(refusal_code: str | None) -> str:
    """The sentence a refused document read serves for the agent service's ``refusal_code``.

    A role with no picked model is told to pick one; every other refusal keeps
    the reader-unavailable sentence.
    """
    if reading_model_not_selected(refusal_code):
        return NO_READING_MODEL_LOCALE_KEY
    return EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY


def reader_refusal_next_step(refusal_code: str | None) -> OperationNextStepWording | None:
    """The step that leads to choosing a reading model, for the refusal that needs one."""
    if not reading_model_not_selected(refusal_code):
        return None

    def worded(language: OutputLanguage) -> OperationChooseReadingModelStepV1:
        return OperationChooseReadingModelStepV1(words=tr(_CHOOSE_READING_MODEL_LOCALE_KEY, locale=language.value))

    return worded


def served_reading_model_refusal(refusal_code: str | None) -> tuple[str, OutputLanguage, OperationNextStepV1] | None:
    """The sentence, its language and the step a surface shows for a role with no picked model.

    ``None`` for any other refusal: those keep the surfaces' own treatment.
    """
    wording = reader_refusal_next_step(refusal_code)
    if wording is None:
        return None
    language = served_words_language()
    return tr(NO_READING_MODEL_LOCALE_KEY, locale=language.value), language, wording(language)
