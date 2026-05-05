"""Translation rendering primitives shared across the codebase.

The application and adapter layers import :func:`tr` from here so they
can render translatable keys without reaching into the CLI entrypoints.
``python-i18n`` is initialised lazily on first call.
"""

from __future__ import annotations

import importlib.resources

import i18n

from ..config import load_settings

_INITIALISED = False


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


def output_language() -> str:
    """Resolve the operator-facing output language from settings.

    Defaults to ``"es"`` on any failure.

    Returns:
        The configured ISO 639-1 language code.
    """
    try:
        lang = load_settings().aeat_output_language
        return str(lang).lower().strip()
    except (KeyError, ValueError, AttributeError):
        return "es"


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


__all__ = ["output_language", "tr"]
