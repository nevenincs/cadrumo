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
from typing import Protocol, runtime_checkable

from ._errors import WizardScriptOverflowError, WizardScriptUnderflowError
from ._models import WizardQuestion


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


__all__ = [
    "Prompter",
    "ScriptedPrompter",
]
