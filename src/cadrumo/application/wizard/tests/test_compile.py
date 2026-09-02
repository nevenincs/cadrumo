"""Structural assertions for the descriptor → ``PROFILE_KEYS`` projection.

These tests feed a tiny synthetic catalogue (NOT ``WIZARD_FLOWS``) to
``compile_profile_keys`` and verify the projection rules: distinct
profile keys produce one row each, requirement derives from
``required`` + ``visible_when``, conditional-requirement pairs flow
through when the parent question is profile-bound, transient parents
leave the conditional pair empty, duplicates raise, and the catalogue
itself carries only frozen literals (no env / file I/O).
"""

from __future__ import annotations

import pytest

from ....core.i18n import Translatable as tr
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....core.requirement import Requirement
from ..catalogue import WIZARD_FLOWS
from ..compiler import compile_profile_keys
from ..errors import WizardCompileError
from ..models import (
    WizardChoice,
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardSection,
    WizardVisibility,
    WizardWidget,
)
from ._support import EmptyAnswersBase

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
        prompt=tr(f"wizard.demo.section.{qid}.prompt"),
        required=required,
        visible_when=visible_when,
        answer_type=str,
    )


def _flow(questions: tuple[WizardQuestion, ...]) -> WizardFlow:
    return WizardFlow(
        id="demo",
        title=tr("wizard.demo.title"),
        description=tr("wizard.demo.description"),
        sections=(
            WizardSection(
                id="section",
                title=tr("wizard.demo.section.title"),
                questions=questions,
            ),
        ),
        answers_model=EmptyAnswersBase,
    )


def test_one_profile_key_per_distinct_question() -> None:
    flow = _flow(
        (
            _question("tax-id", profile_key="tax.id"),
            _question("activity", profile_key="activity"),
        ),
    )
    keys = compile_profile_keys((flow,))
    assert {entry.key for entry in keys} == {"tax.id", "activity"}


def test_none_bound_questions_are_skipped() -> None:
    flow = _flow(
        (
            _question("taxation-type", profile_key=None),
            _question("tax-id", profile_key="tax.id"),
        ),
    )
    keys = compile_profile_keys((flow,))
    assert {entry.key for entry in keys} == {"tax.id"}


def test_required_without_condition_is_required() -> None:
    flow = _flow((_question("tax-id", profile_key="tax.id", required=True),))
    (entry,) = compile_profile_keys((flow,))
    assert entry.requirement is Requirement.REQUIRED


def test_optional_when_flagged_optional() -> None:
    flow = _flow((_question("notes", profile_key="notes", required=False),))
    (entry,) = compile_profile_keys((flow,))
    assert entry.requirement is Requirement.OPTIONAL


def test_conditional_question_is_optional() -> None:
    condition = WizardCondition(question_id="taxation-type", equals="2")
    flow = _flow(
        (
            _question("taxation-type", profile_key="declaration.type"),
            _question("spouse-name", profile_key="spouse.name", visible_when=condition),
        ),
    )
    keys = {entry.key: entry for entry in compile_profile_keys((flow,))}
    spouse = keys["spouse.name"]
    assert spouse.requirement is Requirement.OPTIONAL
    assert spouse.required_when_key == "declaration.type"
    assert spouse.required_when_value == "2"


def test_conditional_with_transient_parent_leaves_pair_empty() -> None:
    condition = WizardCondition(question_id="toggle", equals="true")
    flow = _flow(
        (
            _question("toggle", profile_key=None),
            _question("spouse-name", profile_key="spouse.name", visible_when=condition),
        ),
    )
    (entry,) = compile_profile_keys((flow,))
    assert entry.required_when_key is None
    assert entry.required_when_value is None


def test_duplicate_profile_key_raises() -> None:
    flow_a = _flow((_question("tax-id-a", profile_key="tax.id"),))
    flow_b = WizardFlow(
        id="other",
        title=tr("wizard.other.title"),
        description=tr("wizard.other.description"),
        sections=(
            WizardSection(
                id="section",
                title=tr("wizard.other.section.title"),
                questions=(
                    WizardQuestion(
                        id="tax-id-b",
                        profile_key="tax.id",
                        widget=WizardWidget.TEXT,
                        prompt=tr("wizard.other.section.tax-id-b.prompt"),
                        answer_type=str,
                    ),
                ),
            ),
        ),
        answers_model=EmptyAnswersBase,
    )
    with pytest.raises(WizardCompileError, match=r"wizard|compile"):
        compile_profile_keys((flow_a, flow_b))


def test_description_uses_profile_key_prefix() -> None:
    flow = _flow((_question("tax-id", profile_key="tax.id"),))
    (entry,) = compile_profile_keys((flow,))
    assert str(entry.description) == "profile.keys.tax.id"


def test_wizard_flows_carry_only_frozen_literals() -> None:
    """The catalogue must hold only frozen pydantic records, Translatables, and primitives.

    The compiler is import-time pure by construction: ``compile_profile_keys``
    walks ``WIZARD_FLOWS`` and reads attributes off frozen records. The test
    asserts that every nested attribute of every ``WizardFlow`` is one of:

    * a frozen pydantic record (``model_config["frozen"]`` is true);
    * a ``Translatable`` marker;
    * an immutable primitive (``str``, ``bool``, ``int``, ``Path``, ``type``,
      ``WizardWidget``, ``tuple``, ``NoneType``).

    No callable, no mutable container, no module reference. A descriptor
    construction that hides a filesystem read behind a callable default
    would fail this assertion.
    """

    permitted_primitives: tuple[type, ...] = (str, bool, int, type(None), WizardWidget, type)

    def _assert_literal(value: object, path: str) -> None:
        if isinstance(value, permitted_primitives):
            return
        if isinstance(value, tr):
            return
        if isinstance(value, tuple):
            for index, item in enumerate(value):
                _assert_literal(item, f"{path}[{index}]")
            return
        if isinstance(
            value,
            WizardFlow | WizardSection | WizardQuestion | WizardChoice | WizardCondition | WizardVisibility,
        ):
            frozen = bool(value.model_config.get("frozen"))
            assert frozen, f"{path}: pydantic record is not frozen"
            for field_name in value.__class__.model_fields:
                _assert_literal(getattr(value, field_name), f"{path}.{field_name}")
            return
        raise AssertionError(f"{path}: unexpected non-literal value of type {type(value).__name__}")

    for index, flow in enumerate(WIZARD_FLOWS):
        _assert_literal(flow, f"WIZARD_FLOWS[{index}]")


def test_compile_is_pure_on_the_real_catalogue() -> None:
    """``compile_profile_keys(WIZARD_FLOWS)`` runs with no side effects.

    The catalogue carries only frozen literals (asserted above) so this
    invocation cannot perform file I/O or environment lookups. The test
    asserts the projection produces a non-empty tuple of ``ProfileKey``s
    keyed by the descriptor's declared ``profile_key`` values.
    """

    keys = compile_profile_keys(WIZARD_FLOWS)
    assert keys, "compile_profile_keys returned an empty tuple"
    declared = {
        question.profile_key
        for flow in WIZARD_FLOWS
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None
    }
    assert {entry.key for entry in keys} == declared


def test_real_catalogue_exposes_profile_owned_output_language_key() -> None:
    keys = {entry.key for entry in compile_profile_keys(WIZARD_FLOWS)}

    assert PROFILE_OUTPUT_LANGUAGE_PATH in keys
