"""Prompter abstraction for the wizard runtime.

The :class:`Prompter` protocol decouples "where does an answer come
from" from "what does the wizard ask for". The runtime calls
``prompter.ask(question, default=...)`` for every visible question
and receives a canonical-token string in return. Two implementations
ship: ``ScriptedPrompter`` for deterministic tests and structured
flag-driven CLI invocations, and ``QuestionaryPrompter`` for live
operator interaction. Both speak the same canonical-token contract.
"""

from __future__ import annotations

import sys
from collections import deque
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import questionary

from ...core.errors import AeatError
from ...core.i18n import tr
from ...core.logging import get_logger
from ._errors import WizardScriptOverflowError, WizardScriptUnderflowError
from ._models import WizardChoice, WizardQuestion, WizardWidget

_log = get_logger(__name__)


class WizardUnsupportedConsoleError(AeatError):
    """Raised when the host terminal cannot host an interactive wizard.

    Surfaces when ``prompt_toolkit`` rejects the active TTY (typically
    ``prompt_toolkit.output.win32.NoConsoleScreenBufferError`` under
    git-bash on Windows). The runtime catches this at the
    :class:`QuestionaryPrompter` boundary and surfaces a translated
    operator-facing message rather than a Python traceback.
    """


class WizardEditUnsupportedConsoleError(WizardUnsupportedConsoleError):
    """No-console refusal raised specifically from the ``profile edit`` flow.

    The base error's recovery suggestion names ``profile create``, which
    reads as a destructive replacement when an operator hit the
    no-console state via ``profile edit``. This subclass carries its own
    registered error code so the trailing recovery suggestion names the
    non-interactive ``profile edit`` patch form instead.
    """


def _resolve_no_console_error_types() -> tuple[type[BaseException], ...]:
    """Return the prompt_toolkit error classes that signal an unsupported console host.

    The Windows-only error is included when importable; the OSError fallback
    covers POSIX TTY misconfiguration.
    """
    error_types: list[type[BaseException]] = [OSError]
    try:
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError as _Win32NoConsole

        error_types.insert(0, _Win32NoConsole)
    except ImportError as exc:
        _log.debug(
            "wizard prompter: prompt_toolkit win32 console probe unavailable on this platform: %s",
            exc,
        )
    return tuple(error_types)


_NO_CONSOLE_ERRORS: tuple[type[BaseException], ...] = _resolve_no_console_error_types()

if TYPE_CHECKING:
    from prompt_toolkit.input import Input
    from prompt_toolkit.output import Output

    from ._models import WizardFlow


@runtime_checkable
class Prompter(Protocol):
    """Capability protocol for collecting one answer from one question."""

    def ask(self, question: WizardQuestion, *, default: str | None) -> str:
        """Render ``question`` and return the operator's canonical-token answer."""
        ...


class ScriptedPrompter:
    """Test-only prompter that pops canonical-token answers from a FIFO queue.

    Tests construct a ``ScriptedPrompter`` with a deque of canonical
    tokens whose order matches the runtime's expected question
    sequence. Each ``ask`` call pops the leftmost token; an empty
    deque raises :class:`WizardScriptUnderflowError`. Calling
    :meth:`close` after the runtime finishes raises
    :class:`WizardScriptOverflowError` if any scripted token went
    unconsumed, surfacing test-fixture drift loudly without exposing
    token values in diagnostics.
    """

    def __init__(self, answers: deque[str] | list[str] | tuple[str, ...]) -> None:
        self._answers: deque[str] = deque(answers)
        self._asked: list[str] = []

    @property
    def asked(self) -> tuple[str, ...]:
        """Return the ids of the questions asked so far, in call order."""
        return tuple(self._asked)

    def ask(self, question: WizardQuestion, *, default: str | None) -> str:
        """Pop and return the next scripted canonical-token answer.

        Args:
            question: The :class:`WizardQuestion` being asked (used only in
                the underflow error message).
            default: Ignored; the scripted queue always supplies an explicit
                answer.

        Raises:
            WizardScriptUnderflowError: When the answer queue is empty.
        """
        del default
        if not self._answers:
            context = {"question_id": question.id, "prompt_key": str(question.prompt)}
            raise WizardScriptUnderflowError(
                translated_message="errors.internal.internal_wizard_script_underflow",
                context=context,
            )
        self._asked.append(question.id)
        return self._answers.popleft()

    def close(self) -> None:
        """Assert every scripted answer was consumed.

        Raises:
            WizardScriptOverflowError: When the deque holds unconsumed
                canonical tokens at flow end. The exception context
                reports counts only because scripted tokens can contain
                secrets.
        """
        if self._answers:
            context = {
                "remaining_count": len(self._answers),
                "asked_count": len(self._asked),
            }
            raise WizardScriptOverflowError(
                translated_message="errors.internal.internal_wizard_script_overflow",
                context=context,
            )


def _render_choice(choice: WizardChoice) -> questionary.Choice:
    """Render a :class:`WizardChoice` into a ``questionary.Choice``."""
    return questionary.Choice(
        title=tr(str(choice.label)),
        value=choice.value,
        description=tr(str(choice.description)) if choice.description is not None else None,
    )


class QuestionaryPrompter:
    """Production prompter that dispatches each widget onto a questionary primitive.

    The mapping is one-to-one: ``TEXT`` → ``questionary.text``,
    ``SECRET`` → ``questionary.password``, ``CONFIRM`` →
    ``questionary.confirm``, ``SELECT`` → ``questionary.select``,
    ``CHECKBOX`` → ``questionary.checkbox``, ``PATH`` →
    ``questionary.path``, ``INTEGER`` → ``questionary.text`` with a
    numeric validator. The class accepts an optional
    ``input`` / ``output`` pair so tests can drive it through
    :func:`prompt_toolkit.input.create_pipe_input`.
    """

    def __init__(self, *, input: Input | None = None, output: Output | None = None) -> None:
        self._input = input
        self._output = output

    def prepare(self, flow: WizardFlow) -> None:
        """Verify prompt support and explain the setup flow before progress starts."""
        self._ensure_interactive_environment()
        question_total = sum(len(section.questions) for section in flow.sections)
        required_total = sum(1 for section in flow.sections for question in section.questions if question.required)
        self.emit_progress(
            tr(
                f"wizard.{flow.id}.intro",
                section_total=len(flow.sections),
                question_total=question_total,
                required_total=required_total,
            ),
        )

    def emit_progress(self, text: str) -> None:
        """Emit a progress line (section header or question prefix).

        Called by the runtime between question prompts so operators see
        their position in the flow. Routes through the structured logger
        so the message is handled by the configured logging pipeline and
        any registered secret-scrubbing filters.
        """
        _log.info("wizard.progress text=%r", text)

    def _ensure_interactive_environment(self) -> None:
        """Fail before progress when this process cannot host an interactive prompt."""
        if self._input is not None or self._output is not None:
            return
        if not sys.stdin.isatty():
            raise WizardUnsupportedConsoleError(
                translated_message="wizard.errors.unsupported_console",
            )
        try:
            from prompt_toolkit.output.defaults import create_output

            output = create_output(always_prefer_tty=True)
            output.flush()
        except _NO_CONSOLE_ERRORS as exc:
            raise WizardUnsupportedConsoleError(
                translated_message="wizard.errors.unsupported_console",
            ) from exc

    def ask(self, question: WizardQuestion, *, default: str | None) -> str:
        """Render ``question`` interactively and return the canonical-token answer.

        Dispatches to the appropriate ``questionary`` primitive based on
        ``question.widget`` and returns the operator's response as a
        canonical-token string (``"true"``/``"false"`` for CONFIRM,
        comma-separated tokens for CHECKBOX, raw text otherwise).

        Args:
            question: The :class:`WizardQuestion` to render.
            default: Pre-filled answer string shown to the operator.

        Raises:
            WizardUnsupportedConsoleError: When the host terminal cannot
                host an interactive prompt (Windows no-console, non-TTY).
        """
        prompt = tr(str(question.prompt))
        try:
            match question.widget:
                case WizardWidget.TEXT:
                    return self._ask_text(prompt, default)
                case WizardWidget.SECRET:
                    return self._ask_secret(prompt)
                case WizardWidget.CONFIRM:
                    return self._ask_confirm(prompt, default)
                case WizardWidget.SELECT:
                    return self._ask_select(prompt, question, default)
                case WizardWidget.CHECKBOX:
                    return self._ask_checkbox(prompt, question)
                case WizardWidget.PATH:
                    return self._ask_path(prompt, default)
                case WizardWidget.INTEGER:
                    return self._ask_integer(prompt, default)
        except _NO_CONSOLE_ERRORS as exc:
            raise WizardUnsupportedConsoleError(
                translated_message="wizard.errors.unsupported_console",
            ) from exc

    def _ask_text(self, prompt: str, default: str | None) -> str:
        result = questionary.text(
            prompt,
            default=default or "",
            input=self._input,
            output=self._output,
        ).ask()
        return _stringify(result)

    def _ask_secret(self, prompt: str) -> str:
        result = questionary.password(prompt, input=self._input, output=self._output).ask()
        return _stringify(result)

    def _ask_confirm(self, prompt: str, default: str | None) -> str:
        default_value = (default or "true").strip().lower() in {"true", "yes", "1", "y"}
        result = questionary.confirm(
            prompt,
            default=default_value,
            input=self._input,
            output=self._output,
        ).ask()
        if result is True:
            return "true"
        if result is False:
            return "false"
        return _stringify(result)

    def _ask_select(self, prompt: str, question: WizardQuestion, default: str | None) -> str:
        choices = [_render_choice(choice) for choice in question.choices]
        result = questionary.select(
            prompt,
            choices=choices,
            default=default,
            input=self._input,
            output=self._output,
        ).ask()
        return _stringify(result)

    def _ask_checkbox(self, prompt: str, question: WizardQuestion) -> str:
        choices = [_render_choice(choice) for choice in question.choices]
        result = questionary.checkbox(
            prompt,
            choices=choices,
            input=self._input,
            output=self._output,
        ).ask()
        if result is None:
            return ""
        tokens = [str(item) for item in result]
        return ",".join(tokens)

    def _ask_path(self, prompt: str, default: str | None) -> str:
        result = questionary.path(
            prompt,
            default=default or "",
            input=self._input,
            output=self._output,
        ).ask()
        return _stringify(result)

    def _ask_integer(self, prompt: str, default: str | None) -> str:
        def _is_integer(raw: str) -> bool:
            try:
                int(raw.strip())
            except ValueError:
                return False
            return True

        result = questionary.text(
            prompt,
            default=default or "",
            validate=_is_integer,
            input=self._input,
            output=self._output,
        ).ask()
        return _stringify(result).strip()


def _stringify(value: object) -> str:
    """Coerce questionary's return value into a canonical-token string."""
    if value is None:
        return ""
    return str(value)


__all__ = [
    "Prompter",
    "QuestionaryPrompter",
    "ScriptedPrompter",
]
