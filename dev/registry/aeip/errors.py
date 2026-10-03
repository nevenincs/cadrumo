"""The AEIP authoring lane's existing registry load/refusal error type."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.errors import RegistryLoadError

__all__ = ("AeipError",)

# Preserve the established catch surface without introducing an unregistered
# exception subtype into the global error-code registry.
AeipError = RegistryLoadError
