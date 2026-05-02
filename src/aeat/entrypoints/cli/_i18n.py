"""Multilingual i18n helpers for the CLI surface.

This module is the only place every CLI submodule resolves the
operator's output language and constructs in-place
:class:`aeat.core.i18n.Translatable` literals. Local copies of these
helpers (per-file ``_t`` / ``_lang`` / ``_msg`` helpers) are forbidden;
a regression test enforces the rule.

The helpers are intentionally tiny so call sites stay readable:

- :func:`output_language` returns the resolved
  :class:`aeat.core.i18n.Language`.
- :func:`t` constructs a multilingual
  :class:`aeat.core.i18n.Translatable` in the AEAT-canonical-first
  order matched by the configured fallback-chain default.
- :func:`tr` renders a :class:`aeat.core.i18n.Translatable` in the
  resolved output language.
"""

from __future__ import annotations

from ...core.config import load_settings
from ...core.i18n import Language, Translatable, get_translation


def output_language() -> Language:
    """Resolve the operator-facing output language from settings.

    Defaults to :attr:`aeat.core.i18n.Language.ES` on any failure
    (settings unreadable, value not a valid
    :class:`aeat.core.i18n.Language` member). The Spanish default
    matches the project mandate ``AEAT_OUTPUT_LANGUAGE=es``: the
    operator is a Spanish autónomo and the legal canonical lives in
    Spanish.

    Returns:
        The configured :class:`aeat.core.i18n.Language`, or
        :attr:`aeat.core.i18n.Language.ES` as a safe fallback.
    """

    try:
        return Language(load_settings().aeat_output_language)
    except (KeyError, ValueError):
        return Language.ES


def t(es: str, en: str, ca: str, hu: str) -> Translatable:
    """Build a multilingual :class:`aeat.core.i18n.Translatable` literal.

    Argument order matches the project's AEAT-canonical-first fallback
    chain: Spanish (legal canonical) -> English (project working
    language) -> Catalan (co-official UX) -> Hungarian (operator first
    language).

    Args:
        es: Spanish translation (the legal canonical).
        en: English translation (project working language).
        ca: Catalan translation (co-official UX).
        hu: Hungarian translation (operator first language).

    Returns:
        A :class:`aeat.core.i18n.Translatable` mapping ready for
        :func:`tr`.
    """

    return {"es": es, "en": en, "ca": ca, "hu": hu}


def tr(message: Translatable) -> str:
    """Render ``message`` in the configured CLI output language.

    Thin wrapper around :func:`aeat.core.i18n.get_translation` that
    pre-binds the language resolution to :func:`output_language`. Use at
    every user-facing emit site (``typer.echo``, ``Console.print``,
    ``typer.BadParameter``).

    Args:
        message: Multilingual literal to render, typically built via
            :func:`t`.

    Returns:
        The translated string in the resolved CLI output language.
    """

    return get_translation(message, output_language())
