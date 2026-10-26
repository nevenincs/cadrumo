"""Resolve the output locale from the selected runtime profile."""

from __future__ import annotations

from cadrumo.core.config import load_settings
from cadrumo.core.config_support import coerce_output_language_setting
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import normalise_supported_language
from cadrumo_client.transport.frontend_client import FrontendClient


def resolve_runtime_profile_output_language(
    client: FrontendClient, *, requested: OutputLanguage | None
) -> OutputLanguage:
    """Honor an explicit setting, then the profile's language hint, then Spanish."""
    settings = load_settings()
    if requested is not None:
        return requested
    if "cadrumo_output_language" in settings.model_fields_set and settings.cadrumo_output_language is not None:
        return settings.cadrumo_output_language
    from cadrumo.application.user_profile.language_resolver import resolve_profile_output_language_hint

    profile_hint = resolve_profile_output_language_hint(str(client.profile_id))
    normalized = normalise_supported_language(profile_hint)
    if normalized is not None:
        return OutputLanguage(normalized)
    configured_language = settings.cadrumo_output_language
    selected = coerce_output_language_setting(configured_language.value if configured_language is not None else "")
    return selected or OutputLanguage.ES


__all__ = ["resolve_runtime_profile_output_language"]
