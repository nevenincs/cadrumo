"""Single resource-access boundary for the Cadrumo package.

Exposes:

* The bundled-data boundary (:func:`packaged_data`, :func:`bundled_path`,
  :func:`as_path`) for locating packaged corpus/registry data.
* The typed repository surface (:class:`ResourceCacheRepository`,
  :class:`ResourceRepository`) for read-only bundled resources.
* The ``resources`` factory and :class:`ResourceRegistry`
  aggregate that holds every repository.
* The typed error hierarchy (:class:`ResourceLoadError` and its three
  top-level subclasses).

This is the project's only resource-access surface. Consumer code that
wants a bundled
resource imports ``resources`` and goes through the
appropriate Repository attribute; tests that verify the data-
tree shape may use :func:`bundled_path` / :func:`packaged_data` directly.
"""

from __future__ import annotations

from ._boundary import (
    as_path,
    bundled_path,
    packaged_data,
    resolve_companion_binary,
    resolve_corpus_binary,
)
from .errors import (
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
    "resolve_companion_binary",
    "resolve_corpus_binary",
    "resources",
]
