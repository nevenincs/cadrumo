"""Canonical typed error hierarchy for resource management.

Three top-level error classes give consumers a uniform catch
surface across all twelve :class:`ResourceRepository`
implementations without breaking the existing per-domain error
classes. Each per-domain error (``RegistryLoadError``,
``ManualParseError``, etc.) subclasses the appropriate top-level
error.
"""

from __future__ import annotations

from ..errors import CadrumoError, CoreNotFoundError


class ResourceLoadError(CadrumoError):
    """Base class for every failure to load a bundled resource."""


class ResourceNotFoundError(ResourceLoadError, CoreNotFoundError):
    """A resource key does not resolve to any bundled file.

    Raised when the underlying bundled-data path does not exist
    or when a queried identifier has no record in the loaded
    catalogue.

    Inherits from CoreNotFoundError to participate in the shared
    not-found catch surface across all layers.
    """


class ResourceValidationError(ResourceLoadError):
    """A bundled file exists but fails strict pydantic validation."""


class ResourceBackendError(ResourceLoadError):
    """An IO or backend-level failure while reading the bundled data."""
