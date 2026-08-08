"""Error types shared by the locale-catalogue maintenance tooling.

:class:`LocaleError` is the single contributor-tool exception the developer CLI
catches around every verb. It lives here rather than in
:mod:`dev.locales.manager` so :mod:`dev.locales._write_guard` can raise it
without importing the manager it is imported by.
"""

from __future__ import annotations


class LocaleError(Exception):
    """Raised on locale management and parsing errors.

    A contributor-tool exception, never operator-facing: it carries no
    registered :class:`~cadrumo.core.errors.ErrorCode` and is not part of the
    translated-error-message machinery.
    """


class LocaleWriteConflictError(LocaleError):
    """Raised when a catalogue changed under an in-flight read-modify-write.

    A subclass of :class:`LocaleError` so the developer CLI's existing
    per-verb handler reports it without a second except-arm, while a caller
    that wants to distinguish "retry me" from "your input was wrong" can.
    """


__all__ = ["LocaleError", "LocaleWriteConflictError"]
