"""Modern i18n primitives for the AEAT domain layer."""

from __future__ import annotations

from ._render import output_language, tr
from ._translatable import Translatable

__all__ = ["Translatable", "output_language", "tr"]
