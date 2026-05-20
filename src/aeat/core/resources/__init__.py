"""Single resource-access boundary for the aeat package.

Exposes:

* The bundled-data boundary (``packaged_data``, ``bundled_path``,
  ``as_path``) inherited from the corpus-registry-packaging
  feature.
* The typed repository surface (``ResourceCacheRepository``,
  ``ResourceRepository``) for read-only bundled resources.
* The :func:`resources` factory and :class:`ResourceRegistry`
  aggregate that holds every repository.
* The typed error hierarchy (``ResourceLoadError`` and its three
  top-level subclasses).

Per the resource-management-api ADR this is the project's only
resource-access surface. Consumer code that wants a bundled
resource imports :func:`resources` and goes through the
appropriate Repository attribute; tests that verify the data-
tree shape may use ``bundled_path`` / ``packaged_data`` directly.
"""

from __future__ import annotations

from ._boundary import as_path, bundled_path, packaged_data
from ._errors import (
    ResourceBackendError,
    ResourceLoadError,
    ResourceNotFoundError,
    ResourceValidationError,
)
from ._keys import TypedResourceKey
from ._registry import ResourceRegistry, resources
from ._repository import ResourceCacheRepository, ResourceRepository

__all__ = [
    "ResourceBackendError",
    "ResourceCacheRepository",
    "ResourceLoadError",
    "ResourceNotFoundError",
    "ResourceRegistry",
    "ResourceRepository",
    "ResourceValidationError",
    "TypedResourceKey",
    "as_path",
    "bundled_path",
    "packaged_data",
    "resources",
]
