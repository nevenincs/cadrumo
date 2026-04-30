"""Protocol stubs for wizard-facing dependencies.

The :class:`Prompter` Protocol decouples the wizard's state machine
from Typer's ``typer.prompt`` / ``typer.confirm`` so tests can drive
the wizard with a real in-process prompter (no mocks, no patches).

The :class:`FirstRunRunner` Protocol lets the wizard hand off to a
read-only workflow check (issue #59) without hard-importing
``aeat.workflow``. When no runner is supplied the ``FIRST_RUN`` step
is skipped cleanly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Prompter(Protocol):
    """Typed prompter protocol used by :class:`SetupWizard`.

    Every method returns a plain Python value (``str``, ``bool``,
    :class:`pathlib.Path``) already coerced to the wizard's expected
    shape. Implementations are free to source the answers from a
    terminal, a queue, a JSON file, or anywhere else.
    """

    def prompt_text(self, *, key: str, prompt: str, default: str | None = None) -> str:
        """Return a free-form text answer for ``key``."""
        ...

    def prompt_bool(self, *, key: str, prompt: str, default: bool) -> bool:
        """Return a yes/no answer for ``key``."""
        ...

    def prompt_path(self, *, key: str, prompt: str, default: Path | None = None) -> Path:
        """Return a filesystem path answer for ``key``."""
        ...

    def prompt_choice(
        self,
        *,
        key: str,
        prompt: str,
        choices: tuple[str, ...],
        default: str,
    ) -> str:
        """Return one of ``choices`` for ``key``."""
        ...

    def announce(self, *, key: str, message: str) -> None:
        """Display an informational message for ``key``. Never blocks."""
        ...


@runtime_checkable
class FirstRunRunner(Protocol):
    """Protocol for the optional first-run read-only workflow check (#59).

    The wizard calls :meth:`run_read_only` at the ``FIRST_RUN`` step when a
    runner is supplied. The runner must not mutate any AEAT-side state.
    """

    def run_read_only(self) -> str:
        """Return a short human-readable summary of the read-only output."""
        ...
