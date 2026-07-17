"""Behaviour tests for the wizard ``Prompter`` protocol and its scripted
implementation.
"""

from __future__ import annotations

import errno
import os
from collections import deque
from io import StringIO

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from ....core.i18n import Translatable as tr
from .._errors import (
    WizardAnswerQueueOverflowError,
    WizardAnswerQueueUnderflowError,
)
from .._models import WizardQuestion, WizardWidget
from .._prompter import CanonicalAnswerPrompter, Prompter

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
    prompter = CanonicalAnswerPrompter(deque(["12345678Z", "Acme"]))
    assert prompter.ask(_question("tax-id", _PROMPT_TAX), default=None) == "12345678Z"
    assert prompter.ask(_question("name", _PROMPT_NAME), default=None) == "Acme"


def test_scripted_prompter_records_asked_questions() -> None:
    prompter = CanonicalAnswerPrompter(["12345678Z", "Acme"])
    prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    prompter.ask(_question("name", _PROMPT_NAME), default=None)
    assert prompter.asked == ("tax-id", "name")


def test_canonical_answer_prompter_raises_on_underflow() -> None:
    prompter = CanonicalAnswerPrompter([])
    with pytest.raises(WizardAnswerQueueUnderflowError) as excinfo:
        prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    assert excinfo.value.translated_message == "errors.internal.internal_wizard_answer_queue_underflow"
    assert excinfo.value.context == {
        "question_id": "tax-id",
        "prompt_key": "wizard.setup.profile.tax-id.prompt",
    }


def test_canonical_answer_prompter_close_raises_on_overflow() -> None:
    unused_answer = "unconsumed-answer-value"
    prompter = CanonicalAnswerPrompter([unused_answer])
    with pytest.raises(WizardAnswerQueueOverflowError) as excinfo:
        prompter.close()
    assert excinfo.value.translated_message == "errors.internal.internal_wizard_answer_queue_overflow"
    assert excinfo.value.context == {"remaining_count": 1, "asked_count": 0}
    assert unused_answer not in str(excinfo.value.context)


def test_scripted_prompter_close_succeeds_when_drained() -> None:
    prompter = CanonicalAnswerPrompter(["12345678Z"])
    answer = prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    assert answer == "12345678Z"
    result = prompter.close()
    assert result is None


def test_scripted_prompter_satisfies_prompter_protocol() -> None:
    prompter = CanonicalAnswerPrompter(["12345678Z"])
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

    from ....core.errors import resolve_error_message
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


# ── contract: emit_progress renders on the prompter's own output device ───


def test_emit_progress_renders_on_the_injected_output_device(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Progress must reach the device the prompts render on, and never stdout.

    An operator reads the flow's section headers and question counters off the
    same surface the prompts appear on, so a route the operator cannot see (a
    logger under a WARNING console handler) is not a render.
    """
    from .._prompter import QuestionaryPrompter

    buffer = StringIO()
    prompter = QuestionaryPrompter(output=PlainTextOutput(buffer))

    prompter.emit_progress("Sección 1 de 3")

    assert "Sección 1 de 3" in buffer.getvalue(), "emit_progress must render on the prompter's output device"

    captured = capsys.readouterr()
    assert captured.out == "", "emit_progress must not write to stdout"
    assert captured.err == "", "emit_progress must not write to stderr"


def test_emit_progress_renders_on_the_ambient_app_session_device(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A prompter built the production way renders progress on the session's device.

    ``from_ambient_app_session`` is the constructor the CLI uses, and outside an
    app session it leaves the IO un-injected so the prompts bind to the real
    terminal. Driving it inside a session with declared IO proves the un-injected
    prompter resolves the *same* device its prompts do rather than falling back to
    stdout.
    """
    from prompt_toolkit.application.current import create_app_session

    from .._prompter import QuestionaryPrompter

    buffer = StringIO()
    with create_pipe_input() as pipe_input, create_app_session(input=pipe_input, output=PlainTextOutput(buffer)):
        prompter = QuestionaryPrompter.from_ambient_app_session()
        prompter.emit_progress("(pregunta 2/5)")

    assert "(pregunta 2/5)" in buffer.getvalue(), "progress must reach the ambient session's output device"

    captured = capsys.readouterr()
    assert captured.out == "", "emit_progress must not write to stdout"
    assert captured.err == "", "emit_progress must not write to stderr"


def test_emit_progress_also_records_a_structured_log_line(caplog: pytest.LogCaptureFixture) -> None:
    """The secondary machine-facing trace still carries the progress text."""
    import logging

    from .._prompter import QuestionaryPrompter

    prompter = QuestionaryPrompter(output=PlainTextOutput(StringIO()))

    with caplog.at_level(logging.INFO, logger="cadrumo.application.wizard._prompter"):
        prompter.emit_progress("Hello wizard progress")

    records = [r for r in caplog.records if "wizard.progress" in r.message]
    assert records, "expected at least one wizard.progress log record"
    assert any("Hello wizard progress" in r.getMessage() for r in records)
