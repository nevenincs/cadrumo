"""Canonical domain errors for the :mod:`cadrumo.domain.categories` subpackage."""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class CategoryError(CadrumoError):
    """Base class for every error raised by :mod:`cadrumo.domain.categories`."""


class CategoryValidationError(CategoryError):
    """Raised when category records or registries violate state or shape invariants.

    Its canonical registered ancestry is :class:`CategoryError`. Pydantic
    validators translate this registered failure to ``ValueError`` at their
    narrow boundary.
    """
