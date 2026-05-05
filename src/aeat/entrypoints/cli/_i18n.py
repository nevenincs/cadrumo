"""Centralized localization backend for the CLI surface.

This module initializes the `python-i18n` backend and provides a strict,
key-based translation function.

- :func:`output_language` returns the resolved ISO 639-1 language string.
- :func:`tr` renders an abstract key using the configured backend.
"""

from __future__ import annotations

import importlib.resources

import i18n

from ...core.config import load_settings

# Initialize python-i18n
i18n.load_path.append(str(importlib.resources.files("aeat").joinpath("locales")))
i18n.set("filename_format", "{locale}.{format}")
i18n.set("file_format", "yml")
i18n.set("skip_locale_root_data", True)


def output_language() -> str:
    """Resolve the operator-facing output language from settings.

    Defaults to "es" on any failure.

    Returns:
        The configured ISO 639-1 language code.
    """
    try:
        lang = load_settings().aeat_output_language
        return str(lang).lower().strip()
    except (KeyError, ValueError, AttributeError):
        return "es"


def tr(key: str, **kwargs) -> str:
    """Render an abstract key in the configured CLI output language.

    Args:
        key: The abstract namespace key to render (e.g., 'cli.auth.purpose').
        **kwargs: Interpolation arguments for python-i18n.

    Returns:
        The translated string.
    """
    kwargs.setdefault("locale", output_language())
    return i18n.t(key, **kwargs)
