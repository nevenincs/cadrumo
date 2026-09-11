"""Canonical AEAT receipt presentation identifier."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

__all__ = ["AeatPresentationId"]


AeatPresentationId = Annotated[str, StringConstraints(max_length=64)]
"""AEAT's número de justificante printed on a receipt body."""
