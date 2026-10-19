"""Profile question reads preserve unknown answers and the canonical wording."""

from __future__ import annotations

import pytest

from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ...wizard.catalogue import build_setup_flow
from ...wizard.models import iter_conditions
from ..question_view import profile_question_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_missing_answers_never_inherit_setup_defaults_and_saved_false_is_preserved() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        empty = profile_question_items(flow, {})
        assert empty and all(item.saved_value is None for item in empty)
        question = next(item for item in empty if item.question_id == "has-employees")
        assert question.widget.value == "confirm"
        assert [choice.value for choice in question.choices] == ["true", "false"]
        assert all(choice.label and not choice.label.startswith("flows.") for choice in question.choices)
        saved = profile_question_items(flow, {question.path: "false"})
        assert next(item for item in saved if item.question_id == question.question_id).saved_value == "false"
        source = {question.id: question for section in flow.sections for question in section.questions}
        for item in empty:
            original = source[item.question_id]
            assert item.prompt == tr(original.prompt)
            assert item.help == (None if original.help is None else tr(original.help))
            assert item.visibility == ("unknown" if iter_conditions(original.visible_when) else "visible")


def test_question_relevance_uses_saved_parent_answer_not_an_assumed_default() -> None:
    with bundled_indexed_authority().operation() as authority:
        flow = build_setup_flow(authority)
        questions = {question.id: question for section in flow.sections for question in section.questions}
        child = next(
            question
            for question in questions.values()
            if question.profile_key is not None
            and len(iter_conditions(question.visible_when)) == 1
            and questions[iter_conditions(question.visible_when)[0].question_id].profile_key is not None
        )
        condition = iter_conditions(child.visible_when)[0]
        parent = questions[condition.question_id]
        assert parent.profile_key is not None
        for answer, expected in [(condition.equals or condition.contains, "visible"), ("not-a-match", "hidden")]:
            assert answer is not None
            rows = profile_question_items(flow, {parent.profile_key: answer})
            assert next(item for item in rows if item.question_id == child.id).visibility == expected
