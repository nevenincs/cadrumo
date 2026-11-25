"""Parsers that admit or refuse one command-line value at the parse boundary.

Typer converts each option and argument through a Pydantic adapter and wraps a
declared ``parser`` callable in it. A parser refuses through
:func:`refuse_cli_value`, whose sentence Typer reports verbatim as the
parameter's ``BadParameter``; a plain ``ValueError`` would reach the operator
behind Pydantic's ``Value error,`` prefix.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import NoReturn

from pydantic_core import PydanticCustomError


def refuse_cli_value(detail: str) -> NoReturn:
    """Refuse the value being parsed with ``detail`` as the operator's sentence."""
    raise PydanticCustomError("cli_value", "{detail}", {"detail": detail})


class CliChoice:
    """Admit one token of a choice set, read when the value is parsed.

    The set is read at parse time, so a set an operation fills after the
    command is declared, or one the published authority serves, is the one
    checked. A refusal names the value and the accepted set in Click's own
    wording, which the CLI error contract reads back as typed facts.
    """

    def __init__(self, read: Callable[[], Sequence[str]], *, case_sensitive: bool = True) -> None:
        """Admit the tokens ``read`` returns, called afresh at each parse."""
        self._read = read
        self._case_sensitive = case_sensitive

    @classmethod
    def of(cls, tokens: Sequence[str], *, case_sensitive: bool = True) -> CliChoice:
        """Admit ``tokens``, re-read at each parse so a list filled later is the one checked."""
        return cls(lambda: tokens, case_sensitive=case_sensitive)

    @property
    def choices(self) -> tuple[str, ...]:
        """The accepted tokens, in their declared order."""
        return tuple(self._read())

    def __call__(self, value: object) -> str:
        """Return the declared token ``value`` names, or refuse it with the accepted set."""
        token = str(value)
        choices = self.choices
        for choice in choices:
            if choice == token or (not self._case_sensitive and choice.casefold() == token.casefold()):
                return choice
        accepted = ", ".join(map(repr, choices))
        if len(choices) == 1:
            refuse_cli_value(f"{token!r} is not {accepted}.")
        refuse_cli_value(f"{token!r} is not one of {accepted}.")
