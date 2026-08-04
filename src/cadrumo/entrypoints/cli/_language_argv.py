"""Console-entry argv pre-parse for the ``--language`` help-honesty contract.

The root ``--language`` / ``--lang`` flag must localise help text, not just
command output. Help strings are rendered by
``tr(...)`` at module-import time and the profile-owned output-language resolver
reads ``CADRUMO_OUTPUT_LANGUAGE`` *before* import. The root Typer callback's
``override_settings`` ran too late for help text — and was never reached at all
for a leaf ``SUB --help`` (click short-circuits the leaf ``--help`` before the
root group callback body runs).

The cheapest honest fix that keeps the import-time i18n model intact is to read
the flag from raw ``argv`` in the console entry point and promote it to
``CADRUMO_OUTPUT_LANGUAGE`` before the lazily imported subcommand modules render
their ``tr(...)``-bound help. This module owns that pure, dependency-free
pre-parse so it can be unit-tested in isolation and imported without dragging in
the full CLI command tree.
"""

from __future__ import annotations

import os

from ...core.config import coerce_output_language_setting
from ...core.external_constants import OUTPUT_LANGUAGE_ENV_VAR, OutputLanguage

_LANGUAGE_FLAGS: tuple[str, ...] = ("--language", "--lang", "--output-language")
_LANGUAGE_FLAG_PREFIXES: tuple[str, ...] = ("--language=", "--lang=", "--output-language=")


def _language_from_argv(argv: list[str]) -> OutputLanguage | None:
    """Extract a supported language value from a raw argv slice.

    Reads the operator-typed ``--language LANG`` / ``--lang LANG`` /
    ``--output-language LANG`` and their ``--flag=LANG`` spliced forms without
    constructing the Typer app. ``--output-language`` is not a registered Typer
    option, but a parse-time refusal naming it must still render in the language
    the operator asked for, so the raw pre-parse recognises the spelling.
    Returns the supported language as its :class:`OutputLanguage` member
    when one is supplied, otherwise ``None``.
    """
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in _LANGUAGE_FLAGS:
            if index + 1 < len(argv):
                normalised = coerce_output_language_setting(argv[index + 1])
                if normalised is not None:
                    return normalised
            index += 2
            continue
        if token.startswith(_LANGUAGE_FLAG_PREFIXES):
            normalised = coerce_output_language_setting(token.split("=", 1)[1])
            if normalised is not None:
                return normalised
        index += 1
    return None


def language_from_argv(argv: list[str]) -> OutputLanguage | None:
    """Public accessor for the raw-argv language pre-parse.

    Terminal error handling resolves the parse-time output language from the
    invocation argv before any command context exists; it reads that resolution
    through this facade rather than the private helper.
    """
    return _language_from_argv(argv)


def apply_language_argv_to_environment(argv: list[str]) -> OutputLanguage | None:
    """Promote an explicit ``--language`` flag to the help-rendering env var.

    Sets ``CADRUMO_OUTPUT_LANGUAGE`` from ``argv`` so help strings rendered by
    ``tr(...)`` at module-import time honour the flag, making ``--language``
    genuinely localise help text (the highest-honesty D6 outcome) by feeding the
    existing import-time resolver rather than intercepting help rendering.

    An explicit ``--language`` on the invocation is the most specific operator
    intent, so it wins over an ambient ``CADRUMO_OUTPUT_LANGUAGE`` for that run; the
    profile-owned precedence and the env override for sessions without
    ``--language`` are untouched.

    Returns:
        The promoted language, or ``None`` when ``argv`` carried no supported
        ``--language``/``--lang``/``--output-language`` flag. The caller uses
        this to decide whether a process-environment change actually happened
        and needs the settings cache invalidated -- this module stays
        dependency-free (see the module docstring) and does not invalidate
        anything itself.
    """
    language = _language_from_argv(argv)
    if language is not None:
        os.environ[OUTPUT_LANGUAGE_ENV_VAR] = language.value
    return language


__all__ = ["apply_language_argv_to_environment", "language_from_argv"]
