"""Typed refusal raised inside Modelo edit-value validation."""

from __future__ import annotations

from typing import Final

from ...core.errors.hierarchy import CadrumoError
from .edit_models import ModeloEditParseReason

_PARSE_REFUSED_KEY: Final[str] = "errors.refused.refused_modelo_edit_parse"


class ModeloEditParseRefusedError(CadrumoError):
    """One entry the grammar refuses, with its reason and message arguments.

    Raised inside the parser and turned into a typed refusal at its boundary,
    so a caller receives a refusal value, never this error.
    """

    def __init__(self, reason: ModeloEditParseReason, *arguments: str) -> None:
        """Carry the refusal's reason and its message arguments, never the refused text."""
        super().__init__(translated_message=_PARSE_REFUSED_KEY, context={"reason": reason.value})
        self.reason = reason
        self.arguments = arguments


__all__ = ["ModeloEditParseRefusedError"]
