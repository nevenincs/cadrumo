"""Modern i18n primitives for the AEAT domain layer."""

from __future__ import annotations

from ._render import SUPPORTED_OUTPUT_LANGUAGES, output_language, tr
from ._translatable import Translatable

__all__ = ["SUPPORTED_OUTPUT_LANGUAGES", "Translatable", "output_language", "tr"]
