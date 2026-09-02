"""Whether a live capture covered one subject or a batch of them.

Two CLI capture-result payloads declared this pair independently. It lives in the
application layer that performs the capture rather than in either payload module,
because neither CLI payload module may import the other.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

__all__ = ["LiveCaptureMode", "LiveCaptureModeValue"]


class LiveCaptureMode(StrEnum):
    """How many subjects one live capture run covered."""

    SINGLE = "single"
    """One named subject, requested explicitly."""

    BULK = "bulk"
    """Every subject the surface listed, captured in one run."""


LiveCaptureModeValue = Literal[LiveCaptureMode.SINGLE, LiveCaptureMode.BULK]
"""The same mode for a strict CLI payload field."""
