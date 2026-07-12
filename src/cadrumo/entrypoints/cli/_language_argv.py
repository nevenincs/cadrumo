"""Console-entry argv pre-parse for the ``--language`` help-honesty contract.

The root ``--language`` / ``--lang`` flag must localise help text, not just
command output (operator-surface ADR decision D6,
``2026-06-10-cli-operator-surface-adr``). Help strings are rendered by
``tr(...)`` at module-import time and the profile-owned output-language resolver
(``2026-05-13-cli-workflow-redesign-profile-output-language-adr``) reads
``AEAT_OUTPUT_LANGUAGE`` *before* import. The root Typer callback's
``override_settings`` ran too late for help text — and was never reached at all
for a leaf ``SUB --help`` (click short-circuits the leaf ``--help`` before the
root group callback body runs).

The cheapest honest fix that keeps the import-time i18n model intact is to read
the flag from raw ``argv`` in the console entry point and promote it to
``AEAT_OUTPUT_LANGUAGE`` before the lazily imported subcommand modules render
their ``tr(...)``-bound help. This module owns that pure, dependency-free
pre-parse so it can be unit-tested in isolation and imported without dragging in
the full CLI command tree.
"""

from __future__ import annotations

import os

from ...core.external_constants import OUTPUT_LANGUAGE_ENV_VAR, SUPPORTED_OUTPUT_LANGUAGES


def _normalise_supported_language_for_argv(value: str) -> str | None:
    """Lower-case and trim ``value``; return it only if it is a shipped locale.

    Unsupported values return ``None`` so the canonical Typer ``Choice`` on the
    root callback remains the single authority that refuses an invalid value with
    the accepted-set hint — this pre-parse only forwards a value the catalogue
    already supports.
    """
    raw = value.strip().lower()
    if raw in SUPPORTED_OUTPUT_LANGUAGES:
        return raw
    return None


def _language_from_argv(argv: list[str]) -> str | None:
    """Extract a supported ``--language`` / ``--lang`` value from a raw argv slice.

    Reads the operator-typed ``--language LANG`` / ``--lang LANG`` and the
    ``--language=LANG`` / ``--lang=LANG`` spliced forms without constructing the
    Typer app. Returns the supported, normalised language code when one is
    supplied, otherwise ``None``.
    """
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ("--language", "--lang"):
            if index + 1 < len(argv):
                normalised = _normalise_supported_language_for_argv(argv[index + 1])
                if normalised is not None:
                    return normalised
            index += 2
            continue
        if token.startswith("--language=") or token.startswith("--lang="):
            normalised = _normalise_supported_language_for_argv(token.split("=", 1)[1])
            if normalised is not None:
                return normalised
        index += 1
    return None


def apply_language_argv_to_environment(argv: list[str]) -> None:
    """Promote an explicit ``--language`` flag to the help-rendering env var.

    Sets ``AEAT_OUTPUT_LANGUAGE`` from ``argv`` so help strings rendered by
    ``tr(...)`` at module-import time honour the flag, making ``--language``
    genuinely localise help text (the highest-honesty D6 outcome) by feeding the
    existing import-time resolver rather than intercepting help rendering.

    An explicit ``--language`` on the invocation is the most specific operator
    intent, so it wins over an ambient ``AEAT_OUTPUT_LANGUAGE`` for that run; the
    profile-owned precedence and the env override for sessions without
    ``--language`` are untouched.
    """
    language = _language_from_argv(argv)
    if language is not None:
        os.environ[OUTPUT_LANGUAGE_ENV_VAR] = language


__all__ = ["apply_language_argv_to_environment"]
