"""Internationalization primitives: the :func:`tr` translation surface.

Resolves operator-facing strings to the active output language (Spanish,
English, Catalan, or Hungarian) — the single runtime translation surface
the CLI renders through. User documentation is authored separately and
never reuses these translation keys.

Major declarations:

* :func:`tr` — translate a key to the active language.
* :func:`~aeat.core.i18n.output_language` and
  :data:`OUTPUT_LANGUAGE_ENV_VAR` — resolve and override the active
  :class:`OutputLanguage`, drawn from
  :data:`SUPPORTED_OUTPUT_LANGUAGES`.
* :func:`register_profile_language_resolver` — wire the active profile's
  language preference into resolution.
* :class:`Translatable` — a value that carries its own translation key.
"""

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
