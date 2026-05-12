"""Behaviour tests for the wizard ``Prompter`` protocol and its scripted
implementation.
"""

from __future__ import annotations

from collections import deque

import pytest

from aeat.application.wizard._errors import (
    WizardScriptOverflowError,
    WizardScriptUnderflowError,
)
from aeat.application.wizard._models import WizardQuestion, WizardWidget
from aeat.application.wizard._prompter import Prompter, ScriptedPrompter
from aeat.core.i18n import Translatable

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_PROMPT_TAX = Translatable("wizard.setup.profile.tax-id.prompt")
_PROMPT_NAME = Translatable("wizard.setup.profile.name.prompt")


def _question(qid: str, prompt: Translatable) -> WizardQuestion:
    return WizardQuestion(
        id=qid,
        profile_key=None,
        widget=WizardWidget.TEXT,
        prompt=prompt,
        answer_type=str,
    )


def test_scripted_prompter_pops_in_fifo_order() -> None:
    prompter = ScriptedPrompter(deque(["12345678Z", "Acme"]))
    assert prompter.ask(_question("tax-id", _PROMPT_TAX), default=None) == "12345678Z"
    assert prompter.ask(_question("name", _PROMPT_NAME), default=None) == "Acme"


def test_scripted_prompter_records_asked_questions() -> None:
    prompter = ScriptedPrompter(["12345678Z", "Acme"])
    prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    prompter.ask(_question("name", _PROMPT_NAME), default=None)
    assert prompter.asked == ("tax-id", "name")


def test_scripted_prompter_raises_on_underflow() -> None:
    prompter = ScriptedPrompter([])
    with pytest.raises(WizardScriptUnderflowError):
        prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)


def test_scripted_prompter_close_raises_on_overflow() -> None:
    prompter = ScriptedPrompter(["unused-token"])
    with pytest.raises(WizardScriptOverflowError):
        prompter.close()


def test_scripted_prompter_close_succeeds_when_drained() -> None:
    prompter = ScriptedPrompter(["12345678Z"])
    prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    prompter.close()


def test_scripted_prompter_satisfies_prompter_protocol() -> None:
    prompter = ScriptedPrompter(["12345678Z"])
    assert isinstance(prompter, Prompter)
