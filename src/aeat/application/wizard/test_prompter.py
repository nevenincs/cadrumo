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
from aeat.core.i18n import Translatable as tr

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

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
    with pytest.raises(WizardScriptUnderflowError, match=r"wizard|script|underflow"):
        prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)


def test_scripted_prompter_close_raises_on_overflow() -> None:
    prompter = ScriptedPrompter(["unused-token"])
    with pytest.raises(WizardScriptOverflowError, match=r"overflow|unused|script|drained"):
        prompter.close()


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
    that raises a stand-in ``OSError`` from its ``write`` method on
    first use; that is the same exception shape the catch handler
    accepts as a NoConsoleScreenBufferError stand-in.
    """

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from aeat.application.wizard._prompter import (
        QuestionaryPrompter,
        WizardUnsupportedConsoleError,
    )

    class _RaisingOutput(DummyOutput):
        """Real ``Output`` whose first write raises an
        unsupported-console OSError. Stand-in for
        ``prompt_toolkit.output.win32.NoConsoleScreenBufferError``.
        """

        def write(self, data: str) -> None:  # pragma: no cover - first call raises
            raise OSError("No console screen buffer attached")

        def write_raw(self, data: str) -> None:  # pragma: no cover - first call raises
            raise OSError("No console screen buffer attached")

    with create_pipe_input() as pipe_input:
        prompter = QuestionaryPrompter(input=pipe_input, output=_RaisingOutput())
        with pytest.raises(WizardUnsupportedConsoleError) as raised:
            prompter.ask(_question("tax-id", _PROMPT_TAX), default=None)
    message = str(raised.value)
    assert "aeat config profile create NAME" in message
    assert "No console screen buffer attached" not in message


# ── S68: QuestionaryPrompter.emit_progress routes through structured logger ───


def test_emit_progress_routes_through_logger_not_stdout(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """emit_progress must use the structured logger; nothing must reach stdout."""
    import logging

    from aeat.application.wizard._prompter import QuestionaryPrompter

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

    from aeat.application.wizard._prompter import QuestionaryPrompter

    prompter = QuestionaryPrompter()

    with caplog.at_level(logging.INFO, logger="aeat.application.wizard._prompter"):
        prompter.emit_progress("Hello wizard progress")

    records = [r for r in caplog.records if "wizard.progress" in r.message]
    assert records, "expected at least one wizard.progress log record"
