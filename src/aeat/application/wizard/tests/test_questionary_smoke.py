"""Headless integration smoke for the ``QuestionaryPrompter``.

The parametrized test drives real ``QuestionaryPrompter.ask`` calls
through ``prompt_toolkit.input.create_pipe_input`` plus an in-memory
``PlainTextOutput``. The cases confirm the canonical-token contract
holds end-to-end and that the widget dispatch matches the questionary
primitive listed in the contract model.
"""

from __future__ import annotations

from io import StringIO

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from ....core.i18n import Translatable as tr
from .._models import (
    WizardChoice,
    WizardQuestion,
    WizardWidget,
)
from .._prompter import QuestionaryPrompter

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROMPT = tr("wizard.setup.profile.tax-id.prompt")


def _question(
    widget: WizardWidget,
    *,
    choices: tuple[WizardChoice, ...] = (),
    answer_type: type[str] | type[bool] | type[int] = str,
) -> WizardQuestion:
    return WizardQuestion(
        id="probe",
        profile_key=None,
        widget=widget,
        prompt=_PROMPT,
        choices=choices,
        answer_type=answer_type,
    )


def _memory_output() -> PlainTextOutput:
    return PlainTextOutput(StringIO())


@pytest.mark.parametrize(
    ("widget", "answer_type", "choices", "keystrokes", "expected"),
    [
        (WizardWidget.TEXT, str, (), "12345678Z\r", "12345678Z"),
        (WizardWidget.SECRET, str, (), "AEAT_CERTIFICATE_PASSWORD\r", "AEAT_CERTIFICATE_PASSWORD"),
        (WizardWidget.CONFIRM, bool, (), "y\r", "true"),
        (WizardWidget.CONFIRM, bool, (), "n\r", "false"),
        (
            WizardWidget.SELECT,
            str,
            (
                WizardChoice(value="general", label=tr("wizard.choices.general")),
                WizardChoice(value="simplificado", label=tr("wizard.choices.simplificado")),
            ),
            "\r",
            "general",
        ),
        (
            WizardWidget.CHECKBOX,
            str,
            (
                WizardChoice(value="iva", label=tr("wizard.choices.iva")),
                WizardChoice(value="irpf", label=tr("wizard.choices.irpf")),
            ),
            " \r",
            "iva",
        ),
        (WizardWidget.PATH, str, (), "certs/client.p12\r", "certs/client.p12"),
        (WizardWidget.INTEGER, int, (), "42\r", "42"),
    ],
    ids=[
        "text",
        "secret",
        "confirm-yes",
        "confirm-no",
        "select-first",
        "checkbox-first",
        "path",
        "integer",
    ],
)
def test_questionary_prompter_round_trip_via_pipe_input(
    widget: WizardWidget,
    answer_type: type[str] | type[bool] | type[int],
    choices: tuple[WizardChoice, ...],
    keystrokes: str,
    expected: str,
) -> None:
    question = _question(widget, choices=choices, answer_type=answer_type)
    with create_pipe_input() as pipe:
        pipe.send_text(keystrokes)
        prompter = QuestionaryPrompter(input=pipe, output=_memory_output())
        assert prompter.ask(question, default=None) == expected
