"""Internationalization primitives: the :func:`tr` translation surface.

Resolves operator-facing strings to the active output language (Spanish,
English, Catalan, or Hungarian) — the single runtime translation surface
the CLI renders through. User documentation is authored separately and
never reuses these translation keys.

Major declarations:

* :func:`tr` — translate a key to the active language.
* :func:`describe_auth_provider_operator_impact` — render the canonical
  localized impact of an :class:`core.AuthProviderDescription`.
* :func:`output_language` and
  :data:`OUTPUT_LANGUAGE_ENV_VAR` — resolve and override the active
  :class:`OutputLanguage`, drawn from
  :data:`SUPPORTED_OUTPUT_LANGUAGES`.
* :func:`register_profile_language_resolver` — wire the active profile's
  language preference into resolution.
* :class:`Translatable` — a value that carries its own translation key.
"""

from __future__ import annotations

from ..external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ._auth_provider import describe_auth_provider_operator_impact
from ._translatable import Translatable
from .render import (
    OUTPUT_LANGUAGE_ENV_VAR,
    SUPPORTED_OUTPUT_LANGUAGES,
    MissingTranslationError,
    UnmatchedPlaceholderError,
    clear_output_language_cache,
    clear_output_language_cache_for_settings_override,
    extract_placeholders,
    lookup_translation,
    lookup_translation_entry,
    output_language,
    register_profile_language_resolver,
    tr,
)
from .routing import route_key_to_shard

__all__ = [
    "DEFAULT_OUTPUT_LANGUAGE",
    "OUTPUT_LANGUAGE_ENV_VAR",
    "SUPPORTED_OUTPUT_LANGUAGES",
    "MissingTranslationError",
    "OutputLanguage",
    "Translatable",
    "UnmatchedPlaceholderError",
    "clear_output_language_cache",
    "clear_output_language_cache_for_settings_override",
    "describe_auth_provider_operator_impact",
    "extract_placeholders",
    "lookup_translation",
    "lookup_translation_entry",
    "output_language",
    "register_profile_language_resolver",
    "route_key_to_shard",
    "tr",
]
