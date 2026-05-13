"""Translation rendering primitives shared across the codebase.

The application and adapter layers import :func:`tr` from here so they
can render translatable keys without reaching into the CLI entrypoints.
``python-i18n`` is initialised lazily on first call.
"""

from __future__ import annotations

import importlib.resources
import os

import i18n

from ..config import load_settings
from ..logging import get_logger

_log = get_logger(__name__)
_INITIALISED = False
SUPPORTED_OUTPUT_LANGUAGES: tuple[str, ...] = ("es", "en", "ca", "hu")


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

    Explicit ``AEAT_CLI_LANGUAGE`` and ``AEAT_OUTPUT_LANGUAGE`` win for
    one-off sessions and automation. Otherwise the active profile's
    ``output.language`` key is used. The settings default remains the
    final fallback and defaults to English for a clean install.

    Returns:
        The resolved ISO 639-1 language code.
    """
    for env_name in ("AEAT_CLI_LANGUAGE", "AEAT_OUTPUT_LANGUAGE"):
        override = os.environ.get(env_name)
        if override and override.strip():
            explicit = _normalise_supported_language(override)
            if explicit is not None:
                return explicit
    profile_language = _active_profile_output_language()
    if profile_language is not None:
        return profile_language
    try:
        lang = load_settings().aeat_output_language
        return _normalise_supported_language(lang) or "en"
    except (KeyError, ValueError, AttributeError):
        return "en"


def _active_profile_output_language() -> str | None:
    """Return active profile language without mutating workflow state."""

    try:
        from ...application.workflow._persistence import workflow_state_repository

        record = workflow_state_repository().load().active_profile_record()
        if record is None:
            return None
        raw = _normalise_supported_language(record.values.get("output.language", ""))
    except (OSError, ValueError, KeyError, AttributeError, ImportError) as exc:
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
    _ensure_initialised()
    kwargs.setdefault("locale", output_language())
    return i18n.t(translation_key, **kwargs)


__all__ = ["SUPPORTED_OUTPUT_LANGUAGES", "output_language", "tr"]
