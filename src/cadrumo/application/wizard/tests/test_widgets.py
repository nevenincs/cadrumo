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

from ....core.i18n import Translatable as tr
from ..errors import WizardValidationError
from ..models import (
    WizardChoice,
    WizardCondition,
    WizardQuestion,
    WizardWidget,
)
from ..widgets import validate_widget_answer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TEXT_PROMPT = tr("wizard.setup.profile.tax-id.prompt")
_SELECT_PROMPT = tr("wizard.setup.profile.iva-regime.prompt")
_PATH_PROMPT = tr("wizard.setup.certificate.path.prompt")
_INTEGER_PROMPT = tr("wizard.setup.profile.employee-count.prompt")
_CHECKBOX_PROMPT = tr("wizard.setup.profile.regimes.prompt")
_CONDITION = WizardCondition(question_id="declaration-type", equals="2")


def _question(
    widget: WizardWidget,
    *,
    choices: tuple[WizardChoice, ...] = (),
    required: bool = True,
    visible_when: WizardCondition | None = None,
    prompt: tr = _TEXT_PROMPT,
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


def test_confirm_rejects_blank_when_unconditionally_required() -> None:
    """A required CONFIRM with no visible_when gate must refuse blank.

    The default ``_question`` fixture marks the question required and
    leaves ``visible_when`` unset; blank must raise so the operator
    cannot silently leave a required boolean unanswered.
    """

    question = _question(WizardWidget.CONFIRM, answer_type=bool)
    with pytest.raises(WizardValidationError, match=r"invalid_confirm"):
        validate_widget_answer(question, "")


def test_confirm_accepts_blank_when_optional() -> None:
    """An optional CONFIRM must accept blank and project to the empty
    canonical, the undeclared three-state arm.

    The persistence-layer ``if value`` filter then drops the fact, so a
    profile that never positively declared the boolean reloads with the
    typed projection at ``None`` rather than collapsing onto a stored
    ``"false"`` token.
    """

    question = _question(WizardWidget.CONFIRM, required=False, answer_type=bool)
    assert validate_widget_answer(question, "") == ""
    assert validate_widget_answer(question, "   ") == ""


def test_confirm_accepts_blank_when_conditionally_gated() -> None:
    """A conditionally-gated CONFIRM accepts blank regardless of its
    ``required`` flag, matching the select-widget contract: a gated
    question represents an undeclared closed-set fact when its
    visibility predicate is false.
    """

    question = _question(
        WizardWidget.CONFIRM,
        required=True,
        visible_when=_CONDITION,
        answer_type=bool,
    )
    assert validate_widget_answer(question, "") == ""


def test_select_accepts_declared_choice() -> None:
    choices = (
        WizardChoice(value="general", label=tr("wizard.choices.general")),
        WizardChoice(value="simplificado", label=tr("wizard.choices.simplificado")),
    )
    question = _question(WizardWidget.SELECT, choices=choices, prompt=_SELECT_PROMPT)
    assert validate_widget_answer(question, "general") == "general"


def test_select_rejects_out_of_set_choice() -> None:
    choices = (
        WizardChoice(value="general", label=tr("wizard.choices.general")),
        WizardChoice(value="simplificado", label=tr("wizard.choices.simplificado")),
    )
    question = _question(WizardWidget.SELECT, choices=choices, prompt=_SELECT_PROMPT)
    with pytest.raises(WizardValidationError, match=r"select_unknown"):
        validate_widget_answer(question, "xyz")


def test_select_rejects_when_no_choices_declared() -> None:
    question = _question(WizardWidget.SELECT, prompt=_SELECT_PROMPT)
    with pytest.raises(WizardValidationError, match=r"select_without_choices"):
        validate_widget_answer(question, "anything")


def test_select_accepts_blank_for_optional_unconditional_question() -> None:
    """An optional SELECT with no default accepts a blank answer.

    An optional closed-set fact that the operator did not declare —
    the taxpayer entity-type axis, for example — must be representable
    as undeclared rather than forcing a default choice.
    """

    choices = (
        WizardChoice(value="general", label=tr("wizard.choices.general")),
        WizardChoice(value="simplificado", label=tr("wizard.choices.simplificado")),
    )
    question = _question(
        WizardWidget.SELECT,
        choices=choices,
        required=False,
        prompt=_SELECT_PROMPT,
    )
    assert validate_widget_answer(question, "") == ""


def test_select_rejects_blank_for_required_unconditional_question() -> None:
    """A required SELECT still rejects a blank answer."""

    choices = (
        WizardChoice(value="general", label=tr("wizard.choices.general")),
        WizardChoice(value="simplificado", label=tr("wizard.choices.simplificado")),
    )
    question = _question(
        WizardWidget.SELECT,
        choices=choices,
        required=True,
        prompt=_SELECT_PROMPT,
    )
    with pytest.raises(WizardValidationError, match=r"select_unknown"):
        validate_widget_answer(question, "")


def test_checkbox_accepts_multi_token_membership() -> None:
    """The checkbox canonical form is the sorted token set.

    The validated string feeds an order-independent ``frozenset`` set
    on ``TaxpayerProfile``; the validator sorts the tokens so the same
    selected set declared in any operator input order persists as one
    canonical string and never produces a spurious profile-changed
    diff or snapshot-hash mismatch.
    """

    choices = (
        WizardChoice(value="iva", label=tr("wizard.choices.iva")),
        WizardChoice(value="irpf", label=tr("wizard.choices.irpf")),
    )
    question = _question(WizardWidget.CHECKBOX, choices=choices, prompt=_CHECKBOX_PROMPT)
    assert validate_widget_answer(question, "iva, irpf") == "irpf,iva"
    # The same set in the reverse input order canonicalises identically.
    assert validate_widget_answer(question, "irpf, iva") == "irpf,iva"


def test_checkbox_rejects_unknown_token() -> None:
    choices = (
        WizardChoice(value="iva", label=tr("wizard.choices.iva")),
        WizardChoice(value="irpf", label=tr("wizard.choices.irpf")),
    )
    question = _question(WizardWidget.CHECKBOX, choices=choices, prompt=_CHECKBOX_PROMPT)
    with pytest.raises(WizardValidationError, match=r"checkbox_unknown"):
        validate_widget_answer(question, "iva, nope")


def test_checkbox_rejects_empty_required() -> None:
    choices = (WizardChoice(value="iva", label=tr("wizard.choices.iva")),)
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
    with pytest.raises(WizardValidationError, match=r"wizard|validation") as excinfo:
        validate_widget_answer(question, "maybe")
    error = excinfo.value
    assert error.context is not None
    # `prompt_key` is the resolved field label, never the raw
    # translation key path.
    from ....core.i18n import tr as _tr

    assert error.context["prompt_key"] == _tr(str(_TEXT_PROMPT))
    assert "prompt_key_path" not in error.context
    assert error.context["question_id"] == "probe"
    assert "raw" not in error.context
    assert error.context["raw_redacted"] is True
    assert error.context["raw_length"] == len("maybe")


def test_invalid_tax_id_error_does_not_leak_internal_key_path() -> None:
    """The NIF refusal message must not contain the internal key path.

    `question.prompt` carries a translation key
    (`wizard.setup.profile.tax-id.prompt`). The operator-facing
    refusal interpolates the prompt; the raw key path must be resolved
    to a human label before it reaches the message.
    """

    question = WizardQuestion(
        id="tax-id",
        profile_key=None,
        widget=WizardWidget.TEXT,
        prompt=tr("wizard.setup.profile.tax-id.prompt"),
        choices=(),
        required=True,
        visible_when=None,
        answer_type=str,
    )
    with pytest.raises(WizardValidationError) as excinfo:
        validate_widget_answer(question, "NOT-A-VALID-NIF")
    error = excinfo.value
    assert error.translated_message is not None
    assert "wizard.setup.profile.tax-id.prompt" not in error.translated_message
    assert error.context is not None
    assert error.context["prompt_key"] != "wizard.setup.profile.tax-id.prompt"
    assert "raw" not in error.context
    assert "detail" not in error.context
    assert error.context["raw_redacted"] is True
    assert error.context["detail_redacted"] is True


def test_invalid_tax_id_refusal_names_correct_check_letter() -> None:
    """The wizard refusal must surface the actionable checksum detail.

    A wrong NIF check letter is still refused, but the operator-facing
    message must name the correct check letter so the fix is a single
    keystroke. Previously the validator's diagnostic was dropped on the
    way to the message, leaving an opaque "no válido" refusal.
    """

    question = WizardQuestion(
        id="tax-id",
        profile_key=None,
        widget=WizardWidget.TEXT,
        prompt=tr("wizard.setup.profile.tax-id.prompt"),
        choices=(),
        required=True,
        visible_when=None,
        answer_type=str,
    )
    with pytest.raises(WizardValidationError) as excinfo:
        validate_widget_answer(question, "12345678A")
    message = excinfo.value.translated_message
    assert message is not None
    # The correct check letter for 12345678 is Z; the message must say so.
    assert "12345678" in message
    assert "Z" in message


def test_valid_tax_id_still_accepted() -> None:
    """A correct NIF is accepted unchanged — validation is not relaxed."""

    question = WizardQuestion(
        id="tax-id",
        profile_key=None,
        widget=WizardWidget.TEXT,
        prompt=tr("wizard.setup.profile.tax-id.prompt"),
        choices=(),
        required=True,
        visible_when=None,
        answer_type=str,
    )
    assert validate_widget_answer(question, "12345678Z") == "12345678Z"


def _postcode_question() -> WizardQuestion:
    return WizardQuestion(
        id="address-postcode",
        profile_key="contact.postcode",
        widget=WizardWidget.TEXT,
        prompt=tr("wizard.setup.profile.address-postcode.prompt"),
        choices=(),
        required=False,
        visible_when=None,
        answer_type=str,
    )


def test_postcode_accepts_valid_spanish_postcodes() -> None:
    """Valid Spanish postcodes pass and keep their leading zeros as strings."""

    question = _postcode_question()
    for postcode in ("28013", "01001", "08001", "52001"):
        assert validate_widget_answer(question, postcode) == postcode


def test_postcode_rejects_malformed_values() -> None:
    """Arbitrary text and out-of-range province codes are refused.

    Before fix: the postcode field accepted any text (``BADPOST``,
    ``99999``). After fix: only the 5-digit province-code 01-52 form
    passes.
    """

    question = _postcode_question()
    for postcode in ("BADPOST", "99999", "1234", "123456", "00999"):
        with pytest.raises(WizardValidationError, match=r"invalid_postcode"):
            validate_widget_answer(question, postcode)


def test_postcode_preserves_leading_zero_string() -> None:
    """The postcode answer is a string; a leading-zero value is not int-coerced."""

    question = _postcode_question()
    result = validate_widget_answer(question, "01001")
    assert isinstance(result, str)
    assert result == "01001"
