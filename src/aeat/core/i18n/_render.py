"""Translation rendering primitives shared across the codebase.

The application and adapter layers import :func:`tr` from here so they
can render translatable keys without reaching into the CLI entrypoints.
``python-i18n`` is initialised lazily on first call.
"""

from __future__ import annotations

import importlib.resources
import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import i18n
import yaml

from ..config import load_settings
from ..logging import get_logger

_log = get_logger(__name__)
_INITIALISED = False
SUPPORTED_OUTPUT_LANGUAGES: tuple[str, ...] = ("es", "en", "ca", "hu")
_PLACEHOLDER_RE = re.compile(r"%\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


def _ensure_initialised() -> None:
    """Lazy-initialise the ``python-i18n`` backend on first call."""
    global _INITIALISED
    if _INITIALISED:
        return
    i18n.load_path.append(str(importlib.resources.files("aeat").joinpath("locales")))
    i18n.set("filename_format", "{locale}.{format}")
    i18n.set("file_format", "yml")
    i18n.set("skip_locale_root_data", True)
    _INITIALISED = True


def _normalise_supported_language(value: object) -> str | None:
    raw = str(value).lower().strip()
    if raw in SUPPORTED_OUTPUT_LANGUAGES:
        return raw
    return None


def output_language() -> str:
    """Resolve the operator-facing output language.

    An explicit ``aeat_output_language`` value on the active Settings
    (env var, ``override_settings`` block, or ``.env`` file) wins for
    one-off sessions and automation. Otherwise the active profile's
    ``output.language`` key is used. The settings default remains the
    final fallback and defaults to Spanish for a clean install.

    Returns:
        The resolved ISO 639-1 language code.
    """
    try:
        settings = load_settings()
    except (KeyError, ValueError, AttributeError):
        return "es"
    if "aeat_output_language" in settings.model_fields_set:
        explicit = _normalise_supported_language(settings.aeat_output_language)
        if explicit is not None:
            return explicit
    profile_language = _active_profile_output_language()
    if profile_language is not None:
        return profile_language
    return _normalise_supported_language(settings.aeat_output_language) or "es"


def _active_profile_output_language() -> str | None:
    """Return active profile language without mutating workflow state."""

    try:
        from ...application.workflow._persistence import workflow_state_repository

        record = workflow_state_repository().load().active_profile_record()
        if record is None:
            return None
        raw = _normalise_supported_language(record.values.get("output.language", ""))
    except Exception as exc:
        _log.debug(
            "i18n: unable to resolve active-profile output language; falling back to settings (%s)",
            exc,
        )
        return None
    return raw


def tr(translation_key: str, /, **kwargs: object) -> str:
    """Render an abstract translation key in the configured output language.

    Args:
        translation_key: The abstract namespace key to render
            (e.g., ``"cli.auth.purpose"``). Positional-only so callers
            can pass interpolation kwargs named ``key`` without
            collision.
        **kwargs: Interpolation arguments for ``python-i18n``.

    Returns:
        The translated string.
    """
    if "locale" not in kwargs or kwargs["locale"] is None:
        kwargs["locale"] = output_language()
    locale = _normalise_supported_language(kwargs["locale"]) or "en"
    rendered = _lookup_translation(locale, translation_key)
    interpolation = {key: value for key, value in kwargs.items() if key != "locale"}
    if interpolation:
        rendered = _interpolate(rendered, interpolation)
    return rendered


@lru_cache(maxsize=len(SUPPORTED_OUTPUT_LANGUAGES))
def _locale_map(locale: str) -> dict[str, str]:
    resource = importlib.resources.files("aeat").joinpath("locales", f"{locale}.yml")
    with resource.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return _flatten_translations(loaded)


def _flatten_translations(value: object, prefix: str = "") -> dict[str, str]:
    if isinstance(value, Mapping):
        flattened: dict[str, str] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_translations(child, child_prefix))
        return flattened
    return {prefix: str(value)}


def _lookup_translation(locale: str, translation_key: str) -> str:
    try:
        return _locale_map(locale).get(translation_key, translation_key)
    except (OSError, yaml.YAMLError) as exc:
        _log.debug("i18n: unable to load locale %s; falling back to python-i18n (%s)", locale, exc)
        _ensure_initialised()
        return i18n.t(translation_key, locale=locale)


def _interpolate(rendered: str, values: Mapping[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in values:
            return match.group(0)
        return str(values[name])

    rendered = _PLACEHOLDER_RE.sub(_replace, rendered)
    try:
        return rendered.format(**values)
    except (KeyError, IndexError, ValueError):
        return rendered


__all__ = ["SUPPORTED_OUTPUT_LANGUAGES", "output_language", "tr"]
