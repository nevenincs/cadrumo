"""Exception hierarchy for :mod:`aeat.adapters.outbound.aeat.sede`.

Defines the base :exc:`SedeError` plus the narrowly-scoped subclasses
raised by the sede navigation, parsing, and fetch helpers. Every
subclass extends :exc:`aeat.core.errors.AeatError` so callers can
trap the whole AEAT integration surface with a single
``except AeatError``.
"""

from __future__ import annotations

from .....core.errors import AeatError


class SedeError(AeatError):
    """Base class for post-auth AEAT sede errors.

    Extends :exc:`aeat.core.errors.AeatError` so callers tracking
    cross-package errors can catch the whole AEAT surface uniformly.
    """


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
