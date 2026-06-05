"""Headless integration smoke for the ``QuestionaryPrompter``.

One test per widget kind drives a real ``QuestionaryPrompter.ask`` call
through ``prompt_toolkit.input.create_pipe_input`` plus a
``DummyOutput``. The tests confirm the canonical-token contract holds
end-to-end and that the widget dispatch matches the questionary
primitive listed in the contract model.
"""

from __future__ import annotations

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

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


def test_text_round_trip_via_pipe_input() -> None:
    question = _question(WizardWidget.TEXT)
    with create_pipe_input() as pipe:
        pipe.send_text("12345678Z\r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "12345678Z"


def test_secret_round_trip_via_pipe_input() -> None:
    question = _question(WizardWidget.SECRET)
    with create_pipe_input() as pipe:
        pipe.send_text("AEAT_CERTIFICATE_PASSWORD\r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "AEAT_CERTIFICATE_PASSWORD"


def test_confirm_yes_round_trip_via_pipe_input() -> None:
    question = _question(WizardWidget.CONFIRM, answer_type=bool)
    with create_pipe_input() as pipe:
        pipe.send_text("y\r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "true"


def test_confirm_no_round_trip_via_pipe_input() -> None:
    question = _question(WizardWidget.CONFIRM, answer_type=bool)
    with create_pipe_input() as pipe:
        pipe.send_text("n\r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "false"


def test_select_round_trip_via_pipe_input() -> None:
    choices = (
        WizardChoice(value="general", label=tr("wizard.choices.general")),
        WizardChoice(value="simplificado", label=tr("wizard.choices.simplificado")),
    )
    question = _question(WizardWidget.SELECT, choices=choices)
    with create_pipe_input() as pipe:
        # First choice is selected by pressing enter immediately.
        pipe.send_text("\r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "general"


def test_checkbox_round_trip_via_pipe_input() -> None:
    choices = (
        WizardChoice(value="iva", label=tr("wizard.choices.iva")),
        WizardChoice(value="irpf", label=tr("wizard.choices.irpf")),
    )
    question = _question(WizardWidget.CHECKBOX, choices=choices)
    with create_pipe_input() as pipe:
        # Press space to select the first option, then enter to confirm.
        pipe.send_text(" \r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "iva"


def test_path_round_trip_via_pipe_input() -> None:
    question = _question(WizardWidget.PATH)
    with create_pipe_input() as pipe:
        pipe.send_text("certs/client.p12\r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "certs/client.p12"


def test_integer_round_trip_via_pipe_input() -> None:
    question = _question(WizardWidget.INTEGER, answer_type=int)
    with create_pipe_input() as pipe:
        pipe.send_text("42\r")
        prompter = QuestionaryPrompter(input=pipe, output=DummyOutput())
        assert prompter.ask(question, default=None) == "42"
