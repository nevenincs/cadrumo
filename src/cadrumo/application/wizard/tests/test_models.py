"""Structural assertions for the wizard descriptor models.

These tests verify the model layer's contract: strict frozen
extra-forbid configuration, the closed widget taxonomy, the
``answer_type`` constraint, and the section / flow non-empty tuple
invariants. They do not re-implement pydantic primitives.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.i18n import Translatable as tr
from ..models import (
    WizardChoice,
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardSection,
    WizardWidget,
)
from ._support import EmptyAnswersBase

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFAULT_PROMPT = tr("wizard.setup.profile.tax-id.prompt")
_SECTION_TITLE = tr("wizard.setup.profile.title")


def _question(
    *,
    qid: str = "tax-id",
    profile_key: str | None = "tax.id",
    widget: WizardWidget = WizardWidget.TEXT,
    prompt: tr = _DEFAULT_PROMPT,
    answer_type: type[str] | type[bool] | type[int] | type[Path] = str,
) -> WizardQuestion:
    return WizardQuestion(
        id=qid,
        profile_key=profile_key,
        widget=widget,
        prompt=prompt,
        answer_type=answer_type,
    )


def _section() -> WizardSection:
    return WizardSection(
        id="profile",
        title=_SECTION_TITLE,
        questions=(_question(),),
    )


def test_every_model_is_strict_frozen_extra_forbid() -> None:
    for cls in (
        WizardCondition,
        WizardChoice,
        WizardQuestion,
        WizardSection,
        WizardFlow,
    ):
        config = cls.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"


def test_flow_rejects_non_tuple_sections() -> None:
    """Passing a list (instead of a tuple) violates the strict schema."""

    with pytest.raises(ValidationError, match=r"sections|Tuple|tuple"):
        WizardFlow.model_validate(
            {
                "id": "setup",
                "title": "wizard.setup.title",
                "description": "wizard.setup.description",
                "sections": [_section().model_dump()],
                "answers_model": EmptyAnswersBase,
            },
        )


def test_flow_rejects_empty_sections_tuple() -> None:
    with pytest.raises(ValidationError, match=r"sections|at least 1"):
        WizardFlow(
            id="setup",
            title=tr("wizard.setup.title"),
            description=tr("wizard.setup.description"),
            sections=(),
            answers_model=EmptyAnswersBase,
        )


def test_section_rejects_empty_questions_tuple() -> None:
    with pytest.raises(ValidationError, match=r"questions|at least 1"):
        WizardSection(
            id="profile",
            title=tr("wizard.setup.profile.title"),
            questions=(),
        )


def test_condition_rejects_non_string_equals() -> None:
    """Strict mode rejects integer ``equals`` even when coercion would succeed."""

    with pytest.raises(ValidationError, match=r"equals|string|str"):
        WizardCondition.model_validate({"question_id": "declaration-type", "equals": 2})


def test_question_profile_key_accepts_none() -> None:
    question = _question(profile_key=None)
    assert question.profile_key is None


def test_question_answer_type_accepts_canonical_set() -> None:
    for canonical in (str, bool, int, Path):
        question = _question(answer_type=canonical)
        assert question.answer_type is canonical


def test_question_answer_type_rejects_non_canonical_type() -> None:
    with pytest.raises(ValidationError, match=r"answer_type|float"):
        WizardQuestion.model_validate(
            {
                "id": "tax-id",
                "profile_key": "tax.id",
                "widget": "text",
                "prompt": "wizard.setup.profile.tax-id.prompt",
                "answer_type": float,
            },
        )


def test_question_widget_must_be_member() -> None:
    with pytest.raises(ValidationError, match=r"widget|Input should be"):
        WizardQuestion.model_validate(
            {
                "id": "tax-id",
                "profile_key": "tax.id",
                "widget": "unsupported",
                "prompt": "wizard.setup.profile.tax-id.prompt",
                "answer_type": str,
            },
        )


def test_widget_enum_covers_seven_kinds() -> None:
    assert {member.value for member in WizardWidget} == {
        "text",
        "secret",
        "confirm",
        "select",
        "checkbox",
        "path",
        "integer",
    }
