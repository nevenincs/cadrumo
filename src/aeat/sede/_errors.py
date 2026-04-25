"""Errors raised by :mod:`aeat.sede` navigation and fetch helpers."""

from __future__ import annotations

from ..errors import AeatError


class SedeError(AeatError):
    """Base class for post-auth AEAT sede errors."""


class SedeNavigationError(SedeError):
    """Raised when a navigation step fails (goto, click, wait)."""


class SedeParseError(SedeError):
    """Raised when the captured HTML cannot be parsed to a record."""


class ExpedienteNotFoundError(SedeError):
    """Raised when no expediente matches the requested filter."""


class JustificanteFetchError(SedeError):
    """Raised when the CSV-keyed PDF download fails or is malformed."""


__all__ = [
    "ExpedienteNotFoundError",
    "JustificanteFetchError",
    "SedeError",
    "SedeNavigationError",
    "SedeParseError",
]
