"""Saved setup answers paired with the canonical CLI/TUI questions, without defaults."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel

from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ..wizard.models import WizardFlow, WizardQuestion, WizardWidget, iter_conditions


class ProfileQuestionChoice(BaseModel):
    """Accepted answer and its wording from the setup catalogue."""

    model_config = STRICT_FROZEN_CONFIG
    value: str
    label: str
    description: str | None = None


class ProfileQuestionCondition(BaseModel):
    """An earlier answer that controls whether this question is relevant."""

    model_config = STRICT_FROZEN_CONFIG
    question_id: str
    saved_value: str | None
    equals: str | None
    contains: str | None


class ProfileViewQuestionItem(BaseModel):
    """Question wording and actual saved answer; missing is never a default or false.

    Visibility is setup-flow relevance, not a determination of tax obligations.
    Required means required by that question when visible, not by every filing.
    """

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["question"] = "question"
    question_id: str
    path: str
    widget: WizardWidget
    prompt: str
    help: str | None
    saved_value: str | None
    required_when_visible: bool
    visibility: Literal["visible", "hidden", "unknown"]
    visible_when_any: tuple[ProfileQuestionCondition, ...]
    choices: tuple[ProfileQuestionChoice, ...]


def profile_question_items(flow: WizardFlow, values: Mapping[str, str]) -> tuple[ProfileViewQuestionItem, ...]:
    """Project only persisted non-secret setup questions using the same flow as profile patch.

    Unlike interactive setup, this read never inserts defaults. An unanswered
    parent leaves relevance unknown, so the agent can ask that parent first.
    Repeatable records and facts outside setup remain in the full profile view.
    """
    questions = {question.id: question for section in flow.sections for question in section.questions}
    answers = {
        key: values.get(question.profile_key) or None
        for key, question in questions.items()
        if question.profile_key is not None and question.widget is not WizardWidget.SECRET
    }
    return tuple(
        _question_item(question, question.profile_key, answers)
        for question in questions.values()
        if question.profile_key is not None and question.widget is not WizardWidget.SECRET
    )


def _question_item(
    question: WizardQuestion, profile_path: str, answers: Mapping[str, str | None]
) -> ProfileViewQuestionItem:
    conditions = tuple(
        ProfileQuestionCondition(
            question_id=condition.question_id,
            saved_value=answers.get(condition.question_id),
            equals=condition.equals,
            contains=condition.contains,
        )
        for condition in iter_conditions(question.visible_when)
    )
    matches = tuple(
        None
        if condition.saved_value is None
        else (
            condition.saved_value == condition.equals
            if condition.equals is not None
            else condition.contains in condition.saved_value.split(",")
        )
        for condition in conditions
    )
    visibility = "visible" if not matches or True in matches else "unknown" if None in matches else "hidden"
    return ProfileViewQuestionItem(
        question_id=question.id,
        path=profile_path,
        widget=question.widget,
        prompt=tr(question.prompt),
        help=None if question.help is None else tr(question.help),
        saved_value=answers.get(question.id),
        required_when_visible=question.required,
        visibility=visibility,
        visible_when_any=conditions,
        choices=_choices(question),
    )


def _choices(question: WizardQuestion) -> tuple[ProfileQuestionChoice, ...]:
    if question.widget is WizardWidget.CONFIRM:
        return (
            ProfileQuestionChoice(value="true", label=tr("flows.confirm.yes")),
            ProfileQuestionChoice(value="false", label=tr("flows.confirm.no")),
        )
    return tuple(
        ProfileQuestionChoice(
            value=choice.value,
            label=tr(choice.label),
            description=None if choice.description is None else tr(choice.description),
        )
        for choice in question.choices
    )
