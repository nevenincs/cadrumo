"""In-process prompter implementations.

Two concrete prompters are provided:

* :class:`QueuedPrompter` — a test-friendly prompter backed by a FIFO
  queue of typed answers. Every call pops the front of the queue and
  returns it, type-checked. Used by unit tests and by the
  non-interactive CLI path.
* :class:`TyperPrompter` — a thin wrapper over ``typer.prompt`` /
  ``typer.confirm`` for the real interactive CLI. Lives here so the
  wizard body has no direct Typer import.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ._errors import SetupError


class QueuedPrompter:
    """A deterministic in-process prompter backed by a typed FIFO queue.

    Every ``prompt_*`` call pops the front of the queue and returns it,
    raising :class:`SetupError` if the queue is empty or the popped
    value has the wrong type. ``announce`` is a silent no-op by default
    but records every call for assertions in tests.

    Args:
        answers: Iterable of typed answers in the order the wizard will
            ask for them.
    """

    def __init__(self, answers: Iterable[Any]) -> None:
        self._queue: deque[Any] = deque(answers)
        self.announcements: list[tuple[str, str]] = []

    def _pop(self, key: str, expected: type) -> Any:
        if not self._queue:
            msg = f"QueuedPrompter ran out of answers while resolving {key!r}"
            raise SetupError(msg)
        value = self._queue.popleft()
        if not isinstance(value, expected):
            msg = f"QueuedPrompter expected {expected.__name__} for {key!r}, got {type(value).__name__}"
            raise SetupError(msg)
        return value

    def prompt_text(self, *, key: str, prompt: str, default: str | None = None) -> str:
        del prompt, default
        return self._pop(key, str)  # type: ignore[no-any-return]

    def prompt_bool(self, *, key: str, prompt: str, default: bool) -> bool:
        del prompt, default
        return self._pop(key, bool)  # type: ignore[no-any-return]

    def prompt_path(self, *, key: str, prompt: str, default: Path | None = None) -> Path:
        del prompt, default
        return self._pop(key, Path)  # type: ignore[no-any-return]

    def prompt_choice(
        self,
        *,
        key: str,
        prompt: str,
        choices: tuple[str, ...],
        default: str,
    ) -> str:
        del prompt, default
        value = self._pop(key, str)
        if value not in choices:
            msg = f"QueuedPrompter returned {value!r} which is not in {choices!r} for {key!r}"
            raise SetupError(msg)
        return value  # type: ignore[no-any-return]

    def announce(self, *, key: str, message: str) -> None:
        self.announcements.append((key, message))

    @property
    def remaining(self) -> int:
        """Number of answers still queued. Useful for test assertions."""
        return len(self._queue)


class TyperPrompter:
    """Thin wrapper over ``typer.prompt`` / ``typer.confirm`` for interactive use.

    Kept in its own class so the wizard body never imports ``typer``
    directly. The CLI layer constructs a :class:`TyperPrompter` and
    hands it to :meth:`SetupWizard.run`.
    """

    def __init__(self) -> None:
        import typer  # local import to keep the wizard body Typer-free

        self._typer = typer

    def prompt_text(self, *, key: str, prompt: str, default: str | None = None) -> str:
        del key
        if default is None:
            return str(self._typer.prompt(prompt))
        return str(self._typer.prompt(prompt, default=default))

    def prompt_bool(self, *, key: str, prompt: str, default: bool) -> bool:
        del key
        return bool(self._typer.confirm(prompt, default=default))

    def prompt_path(self, *, key: str, prompt: str, default: Path | None = None) -> Path:
        del key
        raw = self._typer.prompt(prompt, default=str(default) if default is not None else None)
        return Path(str(raw)).expanduser()

    def prompt_choice(
        self,
        *,
        key: str,
        prompt: str,
        choices: tuple[str, ...],
        default: str,
    ) -> str:
        del key
        choice_text = ", ".join(choices)
        full = f"{prompt} [{choice_text}]"
        while True:
            raw = str(self._typer.prompt(full, default=default))
            if raw in choices:
                return raw
            self._typer.echo(f"Please enter one of: {choice_text}")

    def announce(self, *, key: str, message: str) -> None:
        del key
        self._typer.echo(message)
