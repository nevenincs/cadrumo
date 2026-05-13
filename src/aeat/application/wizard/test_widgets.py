"""Per-widget validator behaviour tests.

The tests feed valid and invalid canonical-token answers through
``validate_widget_answer`` and assert the validation outcome. They do
not re-implement the validator's decision rules; for closed-set
widgets the tests construct a ``WizardQuestion`` with the closed
choice set and verify both in-set and out-of-set tokens against the
dispatch entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.application.wizard._errors import WizardValidationError
from aeat.application.wizard._models import (
    WizardChoice,
    WizardCondition,
    WizardQuestion,
    WizardWidget,
)
from aeat.application.wizard._widgets import validate_widget_answer
from aeat.core.i18n import Translatable

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_TEXT_PROMPT = Translatable("wizard.setup.profile.tax-id.prompt")
_SELECT_PROMPT = Translatable("wizard.setup.profile.iva-regime.prompt")
_PATH_PROMPT = Translatable("wizard.setup.certificate.path.prompt")
_INTEGER_PROMPT = Translatable("wizard.setup.profile.employee-count.prompt")
_CHECKBOX_PROMPT = Translatable("wizard.setup.profile.regimes.prompt")
_CONDITION = WizardCondition(question_id="declaration-type", equals="2")


def _question(
    widget: WizardWidget,
    *,
    choices: tuple[WizardChoice, ...] = (),
    required: bool = True,
    visible_when: WizardCondition | None = None,
    prompt: Translatable = _TEXT_PROMPT,
    answer_type: type[str] | type[bool] | type[int] | type[Path] = str,
) -> WizardQuestion:
    return WizardQuestion(
        id="probe",
        profile_key=None,
        widget=widget,
        prompt=prompt,
        choices=choices,
        required=required,
        visible_when=visible_when,
        answer_type=answer_type,
    )


def test_text_strips_whitespace() -> None:
    question = _question(WizardWidget.TEXT)
    assert validate_widget_answer(question, "  12345678Z  ") == "12345678Z"


def test_text_rejects_blank_required() -> None:
    question = _question(WizardWidget.TEXT)
    with pytest.raises(WizardValidationError, match=r"blank_text"):
        validate_widget_answer(question, "  ")


def test_text_allows_blank_when_conditional() -> None:
    question = _question(WizardWidget.TEXT, visible_when=_CONDITION)
    assert validate_widget_answer(question, "") == ""


def test_secret_passthrough() -> None:
    question = _question(WizardWidget.SECRET)
    assert validate_widget_answer(question, "AEAT_CERTIFICATE_PASSWORD") == "AEAT_CERTIFICATE_PASSWORD"


def test_secret_rejects_blank_required() -> None:
    question = _question(WizardWidget.SECRET)
    with pytest.raises(WizardValidationError, match=r"blank_secret"):
        validate_widget_answer(question, "")


def test_confirm_accepts_true_tokens() -> None:
    question = _question(WizardWidget.CONFIRM, answer_type=bool)
    for token in ("true", "yes", "1", "Y"):
        assert validate_widget_answer(question, token) == "true"


def test_confirm_accepts_false_tokens() -> None:
    question = _question(WizardWidget.CONFIRM, answer_type=bool)
    for token in ("false", "no", "0", "N"):
        assert validate_widget_answer(question, token) == "false"


def test_confirm_rejects_unknown_token() -> None:
    question = _question(WizardWidget.CONFIRM, answer_type=bool)
    with pytest.raises(WizardValidationError, match=r"invalid_confirm"):
        validate_widget_answer(question, "maybe")


def test_select_accepts_declared_choice() -> None:
    choices = (
        WizardChoice(value="general", label=Translatable("wizard.choices.general")),
        WizardChoice(value="simplificado", label=Translatable("wizard.choices.simplificado")),
    )
    question = _question(WizardWidget.SELECT, choices=choices, prompt=_SELECT_PROMPT)
    assert validate_widget_answer(question, "general") == "general"


def test_select_rejects_out_of_set_choice() -> None:
    choices = (
        WizardChoice(value="general", label=Translatable("wizard.choices.general")),
        WizardChoice(value="simplificado", label=Translatable("wizard.choices.simplificado")),
    )
    question = _question(WizardWidget.SELECT, choices=choices, prompt=_SELECT_PROMPT)
    with pytest.raises(WizardValidationError, match=r"select_unknown"):
        validate_widget_answer(question, "xyz")


def test_select_rejects_when_no_choices_declared() -> None:
    question = _question(WizardWidget.SELECT, prompt=_SELECT_PROMPT)
    with pytest.raises(WizardValidationError, match=r"select_without_choices"):
        validate_widget_answer(question, "anything")


def test_checkbox_accepts_multi_token_membership() -> None:
    choices = (
        WizardChoice(value="iva", label=Translatable("wizard.choices.iva")),
        WizardChoice(value="irpf", label=Translatable("wizard.choices.irpf")),
    )
    question = _question(WizardWidget.CHECKBOX, choices=choices, prompt=_CHECKBOX_PROMPT)
    assert validate_widget_answer(question, "iva, irpf") == "iva,irpf"


def test_checkbox_rejects_unknown_token() -> None:
    choices = (
        WizardChoice(value="iva", label=Translatable("wizard.choices.iva")),
        WizardChoice(value="irpf", label=Translatable("wizard.choices.irpf")),
    )
    question = _question(WizardWidget.CHECKBOX, choices=choices, prompt=_CHECKBOX_PROMPT)
    with pytest.raises(WizardValidationError, match=r"checkbox_unknown"):
        validate_widget_answer(question, "iva, nope")


def test_checkbox_rejects_empty_required() -> None:
    choices = (WizardChoice(value="iva", label=Translatable("wizard.choices.iva")),)
    question = _question(WizardWidget.CHECKBOX, choices=choices, prompt=_CHECKBOX_PROMPT)
    with pytest.raises(WizardValidationError, match=r"checkbox_required"):
        validate_widget_answer(question, "")


def test_path_returns_expanded_string() -> None:
    question = _question(WizardWidget.PATH, prompt=_PATH_PROMPT, answer_type=Path)
    answer = validate_widget_answer(question, str(Path("certs/client.p12")))
    assert answer.endswith("client.p12")


def test_path_rejects_blank_required() -> None:
    question = _question(WizardWidget.PATH, prompt=_PATH_PROMPT, answer_type=Path)
    with pytest.raises(WizardValidationError, match=r"blank_path"):
        validate_widget_answer(question, "")


def test_integer_canonicalises_decimal() -> None:
    question = _question(WizardWidget.INTEGER, prompt=_INTEGER_PROMPT, answer_type=int)
    assert validate_widget_answer(question, " 42 ") == "42"


def test_integer_rejects_non_integer() -> None:
    question = _question(WizardWidget.INTEGER, prompt=_INTEGER_PROMPT, answer_type=int)
    with pytest.raises(WizardValidationError, match=r"invalid_integer|integer"):
        validate_widget_answer(question, "not-a-number")


def test_error_carries_prompt_key_context() -> None:
    question = _question(WizardWidget.CONFIRM, answer_type=bool)
    with pytest.raises(WizardValidationError) as excinfo:
        validate_widget_answer(question, "maybe")
    error = excinfo.value
    assert error.context is not None
    assert error.context["prompt_key"] == str(_TEXT_PROMPT)
    assert error.context["question_id"] == "probe"
