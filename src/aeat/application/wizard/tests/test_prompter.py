"""Behaviour tests for the wizard ``Prompter`` protocol and its scripted
implementation.
"""

from __future__ import annotations

import errno
import os
from collections import deque

import pytest

from ....core.i18n import Translatable as tr
from .._errors import (
    WizardScriptOverflowError,
    WizardScriptUnderflowError,
)
from .._models import WizardQuestion, WizardWidget
from .._prompter import Prompter, ScriptedPrompter

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROMPT_TAX = tr("wizard.setup.profile.tax-id.prompt")
_PROMPT_NAME = tr("wizard.setup.profile.name.prompt")


def _question(qid: str, prompt: tr) -> WizardQuestion:
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
    with pytest.raises(WizardScriptUnderflowError) as excinfo:
        prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    assert excinfo.value.translated_message == "errors.internal.internal_wizard_script_underflow"
    assert excinfo.value.context == {
        "question_id": "tax-id",
        "prompt_key": "wizard.setup.profile.tax-id.prompt",
    }


def test_scripted_prompter_close_raises_on_overflow() -> None:
    unused_answer = "unconsumed-answer-value"
    prompter = ScriptedPrompter([unused_answer])
    with pytest.raises(WizardScriptOverflowError) as excinfo:
        prompter.close()
    assert excinfo.value.translated_message == "errors.internal.internal_wizard_script_overflow"
    assert excinfo.value.context == {"remaining_count": 1, "asked_count": 0}
    assert unused_answer not in str(excinfo.value.context)


def test_scripted_prompter_close_succeeds_when_drained() -> None:
    prompter = ScriptedPrompter(["12345678Z"])
    answer = prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    assert answer == "12345678Z"
    result = prompter.close()
    assert result is None


def test_scripted_prompter_satisfies_prompter_protocol() -> None:
    prompter = ScriptedPrompter(["12345678Z"])
    assert isinstance(prompter, Prompter)


def test_questionary_prompter_translates_no_console_error() -> None:
    """A questionary call that raises an unsupported-console error must surface
    a translated :class:`WizardUnsupportedConsoleError`, not the raw
    prompt_toolkit exception.

    The test drives the prompter with a real ``Output`` implementation
    backed by a closed OS pipe, producing the same ``OSError`` family
    accepted as a NoConsoleScreenBufferError fallback.
    """

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output.plain_text import PlainTextOutput

    from ....core.errors._registry import resolve_error_message
    from .._prompter import (
        QuestionaryPrompter,
        WizardUnsupportedConsoleError,
    )

    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    stream = os.fdopen(write_fd, "w", encoding="utf-8")
    try:
        with create_pipe_input() as pipe_input:
            prompter = QuestionaryPrompter(input=pipe_input, output=PlainTextOutput(stream))
            with pytest.raises(WizardUnsupportedConsoleError) as raised:
                prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    finally:
        try:
            stream.close()
        except OSError as exc:
            assert exc.errno in {errno.EINVAL, errno.EPIPE}

    cause = raised.value.__cause__
    assert isinstance(cause, OSError)
    message = resolve_error_message(raised.value)
    assert "aeat config profile create NAME" in message
    assert str(cause) not in message


# ── contract: QuestionaryPrompter.emit_progress routes through structured logger ───


def test_emit_progress_routes_through_logger_not_stdout(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """emit_progress must use the structured logger; nothing must reach stdout."""
    import logging

    from .._prompter import QuestionaryPrompter

    prompter = QuestionaryPrompter()

    with caplog.at_level(logging.INFO, logger="aeat.application.wizard._prompter"):
        prompter.emit_progress("Sección 1 de 3")

    captured = capsys.readouterr()
    assert captured.out == "", "emit_progress must not write to stdout"
    assert captured.err == "", "emit_progress must not write to stderr"

    assert any("wizard.progress" in r.message for r in caplog.records), (
        "expected a 'wizard.progress' log record from emit_progress"
    )


def test_emit_progress_log_record_carries_text(caplog: pytest.LogCaptureFixture) -> None:
    """The log record emitted by emit_progress must carry the progress text."""
    import logging

    from .._prompter import QuestionaryPrompter

    prompter = QuestionaryPrompter()

    with caplog.at_level(logging.INFO, logger="aeat.application.wizard._prompter"):
        prompter.emit_progress("Hello wizard progress")

    records = [r for r in caplog.records if "wizard.progress" in r.message]
    assert records, "expected at least one wizard.progress log record"
