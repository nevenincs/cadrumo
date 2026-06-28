"""Domain errors for the :mod:`aeat.domain.categories` subpackage."""

from __future__ import annotations

from ...core.errors import AeatError


class CategoryError(AeatError):
    """Base class for every error raised by :mod:`aeat.domain.categories`."""


class CategoryValidationError(CategoryError, ValueError):
    """Raised when category records or registries violate state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """
