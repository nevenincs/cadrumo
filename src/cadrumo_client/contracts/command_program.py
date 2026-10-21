"""Shared executable-root identities for operator command targets."""

from __future__ import annotations

from enum import StrEnum


class CommandProgram(StrEnum):
    """Executable that owns a canonical operator command path."""

    AEAT = "aeat"
    AUTHENTICATION = "cadrumo-runtime"

    @property
    def executable_name(self) -> str:
        """Return the executable token used to invoke this command program."""
        return self.value


__all__ = ["CommandProgram"]
