"""Shared refusal metadata for the private supervisor protocol line."""

from __future__ import annotations

from enum import StrEnum

from cadrumo.core.errors.hierarchy import CadrumoError


class ProtocolLineRefusal(StrEnum):
    """Why one supervisor protocol line was refused; the line is never echoed."""

    MALFORMED = "malformed"
    OVERSIZED = "oversized"


class ProtocolLineError(CadrumoError):
    """A supervisor protocol line outside the closed grammar."""

    def __init__(self, code: ProtocolLineRefusal) -> None:
        """Keep only the bounded refusal code."""
        super().__init__(code.value)
        self.reason = code
