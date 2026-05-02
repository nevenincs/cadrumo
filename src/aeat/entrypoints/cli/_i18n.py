"""Quad-lingual i18n helpers for the CLI surface.

This module is the *only* place every CLI submodule resolves the
operator's output language and constructs in-place ``Translatable``
literals. Local copies of these helpers (the pre-restructure pattern
of redefining ``_t`` / ``_lang`` / ``_msg`` per file) are forbidden;
a regression test enforces the rule.

The helpers are intentionally tiny so that call sites stay readable:

- ``output_language()`` returns the resolved :class:`~aeat.core.i18n.Language`.
- ``t(es, en, ca, hu)`` constructs a quad-lingual ``Translatable``
  in the AEAT-canonical-first order matched by the configured
  fallback chain default.
- ``tr(message)`` renders a ``Translatable`` in the resolved
  output language.
"""

from __future__ import annotations

from ...core.config import load_settings
from ...core.i18n import Language, Translatable, get_translation


def output_language() -> Language:
    """Resolve the Kent-facing output language from settings.

    Defaults to :attr:`Language.ES` on any failure (settings
    unreadable, value not a valid :class:`Language` member). The
    Spanish-default matches the project mandate
    ``AEAT_OUTPUT_LANGUAGE=es``; Kent is a Spanish autónomo and the
    legal canonical lives in Spanish.
    """

    try:
        return Language(load_settings().aeat_output_language)
    except (KeyError, ValueError):
        return Language.ES


def t(es: str, en: str, ca: str, hu: str) -> Translatable:
    """Build a quad-lingual ``Translatable`` in one positional call.

    Argument order matches the project's AEAT-canonical-first
    fallback chain: Spanish (legal canonical) → English (project
    working language) → Catalan (co-official UX) → Hungarian
    (operator first language).
    """

    return {"es": es, "en": en, "ca": ca, "hu": hu}


def tr(message: Translatable) -> str:
    """Render *message* in the configured CLI output language.

    Thin wrapper around :func:`get_translation` that pre-binds the
    language resolution to :func:`output_language`. Use at every
    user-facing emit site (``typer.echo``, ``Console.print``,
    ``typer.BadParameter``).
    """

    return get_translation(message, output_language())
