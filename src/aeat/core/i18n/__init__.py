"""Modern i18n primitives for the AEAT domain layer."""

from __future__ import annotations

from ..external_constants import OutputLanguage
from ._render import (
    OUTPUT_LANGUAGE_ENV_VAR,
    SUPPORTED_OUTPUT_LANGUAGES,
    output_language,
    register_profile_language_resolver,
    tr,
)
from ._translatable import Translatable

__all__ = [
    "OUTPUT_LANGUAGE_ENV_VAR",
    "SUPPORTED_OUTPUT_LANGUAGES",
    "OutputLanguage",
    "Translatable",
    "output_language",
    "register_profile_language_resolver",
    "tr",
]
