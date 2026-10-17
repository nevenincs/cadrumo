"""Public field-save failure understood by the authentication editor."""

from __future__ import annotations

from ....core.errors.hierarchy import CadrumoError


class AeatAuthFieldSaveError(CadrumoError):
    """Identify the attempted field without retaining its rejected input."""

    def __init__(self, path: str) -> None:
        """Retain only the canonical public profile path."""
        super().__init__(path)
        self.path = path
