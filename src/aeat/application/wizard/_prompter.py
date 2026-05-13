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

from collections import deque
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import questionary

from ...core.errors import AeatError
from ...core.i18n import tr
from ._errors import WizardScriptOverflowError, WizardScriptUnderflowError
from ._models import WizardChoice, WizardQuestion, WizardWidget


class WizardUnsupportedConsoleError(AeatError):
    """Raised when the host terminal cannot host an interactive wizard.

    Surfaces when ``prompt_toolkit`` rejects the active TTY (typically
    ``prompt_toolkit.output.win32.NoConsoleScreenBufferError`` under
    git-bash on Windows). The runtime catches this at the
    :class:`QuestionaryPrompter` boundary and surfaces a translated
    operator-facing message rather than a Python traceback.
    """


def _resolve_no_console_error_types() -> tuple[type[BaseException], ...]:
    """Return the prompt_toolkit error classes that signal an
    unsupported console host. Windows-only error is included when
    importable; the OSError fallback covers POSIX TTY misconfiguration.
    """

    error_types: list[type[BaseException]] = [OSError]
    try:
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError as _Win32NoConsole

        error_types.insert(0, _Win32NoConsole)
    except ImportError:
        pass
    return tuple(error_types)


_NO_CONSOLE_ERRORS: tuple[type[BaseException], ...] = _resolve_no_console_error_types()

if TYPE_CHECKING:
    from prompt_toolkit.input import Input
    from prompt_toolkit.output import Output


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
    unconsumed, surfacing test-fixture drift loudly.
    """

    def __init__(self, answers: deque[str] | list[str] | tuple[str, ...]) -> None:
        self._answers: deque[str] = deque(answers)
        self._asked: list[str] = []

    @property
    def asked(self) -> tuple[str, ...]:
        """Return the ids of the questions asked so far, in call order."""
        return tuple(self._asked)

    def ask(self, question: WizardQuestion, *, default: str | None) -> str:
        del default
        if not self._answers:
            context = {"question_id": question.id, "prompt_key": str(question.prompt)}
            raise WizardScriptUnderflowError(
                "scripted prompter exhausted",
                context=context,
            )
        self._asked.append(question.id)
        return self._answers.popleft()

    def close(self) -> None:
        """Assert every scripted answer was consumed.

        Raises:
            WizardScriptOverflowError: When the deque holds unconsumed
                canonical tokens at flow end.
        """

        if self._answers:
            context = {"remaining": tuple(self._answers)}
            raise WizardScriptOverflowError(
                "scripted prompter closed with unconsumed answers",
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

    def ask(self, question: WizardQuestion, *, default: str | None) -> str:
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
            raise WizardUnsupportedConsoleError(tr("wizard.errors.unsupported_console")) from exc

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
