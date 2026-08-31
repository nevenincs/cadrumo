"""Single resource-access boundary for the Cadrumo package.

The defining modules are:

* :mod:`cadrumo.core.resources.bundled_data` for locating packaged
  corpus/registry data (:func:`packaged_data`, :func:`bundled_path`,
  :func:`as_path`, :func:`resolve_corpus_binary`,
  :func:`resolve_companion_binary`).
* :mod:`cadrumo.core.resources.registry` for the ``resources`` factory and
  the :class:`ResourceRegistry` aggregate that holds every repository.
* :mod:`cadrumo.core.resources.errors` for the typed error hierarchy
  (:class:`ResourceLoadError` and its three top-level subclasses).

The typed repository surface (:class:`ResourceCacheRepository`,
:class:`ResourceRepository`) and the typed key base
(:class:`TypedResourceKey`) keep their package-private defining modules,
because only the repository implementations under ``_repos/`` build on them.

This is the project's only resource-access surface. Consumer code that wants
a bundled resource imports ``resources`` from
:mod:`cadrumo.core.resources.registry` and goes through the appropriate
Repository attribute; tests that verify the data-tree shape may use
:func:`bundled_path` / :func:`packaged_data` from
:mod:`cadrumo.core.resources.bundled_data` directly.
"""

from __future__ import annotations

from ._keys import TypedResourceKey
from ._repository import ResourceCacheRepository, ResourceRepository
from .bundled_data import (
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
from .registry import ResourceRegistry, resources

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
