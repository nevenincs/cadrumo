"""Canonical domain errors for the :mod:`cadrumo.domain.categories` subpackage."""

from __future__ import annotations

from ...core.errors import CadrumoError


class CategoryError(CadrumoError):
    """Base class for every error raised by :mod:`cadrumo.domain.categories`."""


class CategoryValidationError(CategoryError, ValueError):
    """Raised when category records or registries violate state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """
