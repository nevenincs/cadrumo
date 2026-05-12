"""Structural assertions for the descriptor → ``PROFILE_KEYS`` projection.

These tests feed a tiny synthetic catalogue (NOT ``WIZARD_FLOWS``) to
``compile_profile_keys`` and verify the projection rules: distinct
profile keys produce one row each, requirement derives from
``required`` + ``visible_when``, conditional-requirement pairs flow
through when the parent question is profile-bound, transient parents
leave the conditional pair empty, duplicates raise, and the function
is pure (no env / file I/O).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from aeat.application.wizard._compiler import compile_profile_keys
from aeat.application.wizard._errors import WizardCompileError
from aeat.application.wizard._models import (
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardSection,
    WizardWidget,
)
from aeat.core.i18n import Translatable
from aeat.domain.profile._keys import ProfileKeyRequirement

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class _DummyAnswers(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


def _question(
    qid: str,
    *,
    profile_key: str | None,
    required: bool = True,
    visible_when: WizardCondition | None = None,
) -> WizardQuestion:
    return WizardQuestion(
        id=qid,
        profile_key=profile_key,
        widget=WizardWidget.TEXT,
        prompt=Translatable(f"wizard.demo.section.{qid}.prompt"),
        required=required,
        visible_when=visible_when,
        answer_type=str,
    )


def _flow(questions: tuple[WizardQuestion, ...]) -> WizardFlow:
    return WizardFlow(
        id="demo",
        title=Translatable("wizard.demo.title"),
        description=Translatable("wizard.demo.description"),
        sections=(
            WizardSection(
                id="section",
                title=Translatable("wizard.demo.section.title"),
                questions=questions,
            ),
        ),
        answers_model=_DummyAnswers,
    )


def test_one_profile_key_per_distinct_question() -> None:
    flow = _flow(
        (
            _question("tax-id", profile_key="tax.id"),
            _question("activity", profile_key="activity"),
        )
    )
    keys = compile_profile_keys((flow,))
    assert {entry.key for entry in keys} == {"tax.id", "activity"}


def test_none_bound_questions_are_skipped() -> None:
    flow = _flow(
        (
            _question("declaration-type", profile_key=None),
            _question("tax-id", profile_key="tax.id"),
        )
    )
    keys = compile_profile_keys((flow,))
    assert {entry.key for entry in keys} == {"tax.id"}


def test_required_without_condition_is_required() -> None:
    flow = _flow((_question("tax-id", profile_key="tax.id", required=True),))
    (entry,) = compile_profile_keys((flow,))
    assert entry.requirement is ProfileKeyRequirement.REQUIRED


def test_optional_when_flagged_optional() -> None:
    flow = _flow((_question("notes", profile_key="notes", required=False),))
    (entry,) = compile_profile_keys((flow,))
    assert entry.requirement is ProfileKeyRequirement.OPTIONAL


def test_conditional_question_is_optional() -> None:
    condition = WizardCondition(question_id="declaration-type", equals="2")
    flow = _flow(
        (
            _question("declaration-type", profile_key="declaration.type"),
            _question("spouse-name", profile_key="spouse.name", visible_when=condition),
        )
    )
    keys = {entry.key: entry for entry in compile_profile_keys((flow,))}
    spouse = keys["spouse.name"]
    assert spouse.requirement is ProfileKeyRequirement.OPTIONAL
    assert spouse.required_when_key == "declaration.type"
    assert spouse.required_when_value == "2"


def test_conditional_with_transient_parent_leaves_pair_empty() -> None:
    condition = WizardCondition(question_id="toggle", equals="true")
    flow = _flow(
        (
            _question("toggle", profile_key=None),
            _question("spouse-name", profile_key="spouse.name", visible_when=condition),
        )
    )
    (entry,) = compile_profile_keys((flow,))
    assert entry.required_when_key is None
    assert entry.required_when_value is None


def test_duplicate_profile_key_raises() -> None:
    flow_a = _flow((_question("tax-id-a", profile_key="tax.id"),))
    flow_b = WizardFlow(
        id="other",
        title=Translatable("wizard.other.title"),
        description=Translatable("wizard.other.description"),
        sections=(
            WizardSection(
                id="section",
                title=Translatable("wizard.other.section.title"),
                questions=(
                    WizardQuestion(
                        id="tax-id-b",
                        profile_key="tax.id",
                        widget=WizardWidget.TEXT,
                        prompt=Translatable("wizard.other.section.tax-id-b.prompt"),
                        answer_type=str,
                    ),
                ),
            ),
        ),
        answers_model=_DummyAnswers,
    )
    with pytest.raises(WizardCompileError):
        compile_profile_keys((flow_a, flow_b))


def test_description_uses_profile_key_prefix() -> None:
    flow = _flow((_question("tax-id", profile_key="tax.id"),))
    (entry,) = compile_profile_keys((flow,))
    assert str(entry.description) == "profile.keys.tax.id"


def test_compile_is_pure_no_env_or_file_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compiling must not touch the environment or the filesystem."""

    flow = _flow((_question("tax-id", profile_key="tax.id"),))

    def _explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("file I/O attempted during compile_profile_keys")

    for env_var in list(os.environ):
        monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setattr(Path, "read_text", _explode)
    keys = compile_profile_keys((flow,))
    assert keys[0].key == "tax.id"
