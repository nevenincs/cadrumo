"""A structural error in the declared work-form layout."""

from __future__ import annotations

from ...core.errors.hierarchy import InternalInvariantError


class ModeloWorkFormLayoutError(InternalInvariantError):
    """A declared layout does not account for every casilla exactly once."""
