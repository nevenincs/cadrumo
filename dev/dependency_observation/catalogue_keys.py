"""Observe the locale catalogue by the keys a process looks up, not by the shard files that hold them.

Every product module reads its sentences through one catalogue, and a shard
such as ``common.yml`` holds the sentences of every surface. Keyed on the
shard's bytes, a run that read three of its keys would be stale after any edit
to any other key. An observation that opts in (see
:func:`~dev.dependency_observation.observation.prepare_inherited_journals`)
records instead each key a process looked up, with the digest of what the
catalogue answered for it: whether the key is there, and its value.

The catalogue's own reads of a shard are then not file reads: they are
suspended while a key is resolved. Everything else stays a file read: a process
that iterates the catalogue, or reads a shard's bytes itself, depends on the
whole shard, and the iteration records every shard file and directory. The
digest is taken again by :func:`current_entry_digest`, through the same
catalogue, so a key moved to another shard with its value unchanged is unchanged.

This module uses the standard library only; the catalogue class is patched
once its module has been imported, whoever imports it.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.abc
import importlib.machinery
import json
import os
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Final, cast, override

if TYPE_CHECKING:
    from .observation import Observation

#: The module that defines the catalogue, and the class whose lookups are keyed.
CATALOGUE_MODULE: Final[str] = "cadrumo.core.i18n.lazy_catalogue"
CATALOGUE_CLASS: Final[str] = "LazyLocaleCatalogue"
#: Separates a catalogue's shard directory from a key in a keyed read's identity.
KEY_SEPARATOR: Final[str] = "\x1f"
_PATCHED: Final[str] = "__cadrumo_keyed_observation__"
_SHARD_SUFFIX: Final[str] = ".yml"


def entry_digest(entry: tuple[bool, str | None]) -> str:
    """The digest of what a catalogue answers for one key: whether it holds it, and its value."""
    return hashlib.sha256(json.dumps(list(entry), ensure_ascii=False).encode("utf-8")).hexdigest()


def key_identity(shard_directory: str, key: str) -> str:
    """One keyed read's identity: the catalogue's shard directory and the key looked up in it."""
    return f"{shard_directory}{KEY_SEPARATOR}{key}"


def split_identity(identity: str) -> tuple[str, str]:
    """The shard directory and the key a keyed read's identity names."""
    directory, _, key = identity.partition(KEY_SEPARATOR)
    return directory, key


def _entry(catalogue: Any, key: str) -> tuple[bool, str | None]:
    """What ``catalogue`` holds for ``key`` once the key has been resolved."""
    cache = cast("dict[str, str | None]", catalogue.key_cache)
    return key in cache, cache.get(key)


def _patch(observation: Observation, module: ModuleType) -> None:
    """Route the catalogue's key lookups through ``observation`` as keyed reads."""
    catalogue_class = getattr(module, CATALOGUE_CLASS, None)
    if catalogue_class is None or getattr(catalogue_class, _PATCHED, False):
        return
    lookup: Callable[[Any, str], str | None] = catalogue_class.__getitem__
    holds: Callable[[Any, object], bool] = catalogue_class.__contains__
    iterate: Callable[[Any], Iterator[str]] = catalogue_class.__iter__
    count: Callable[[Any], int] = catalogue_class.__len__

    def note(catalogue: Any, key: str) -> None:
        directory = catalogue.shard_dir
        if directory is not None:
            observation.note_key(str(directory), key, entry_digest(_entry(catalogue, key)))

    @functools.wraps(lookup)
    def keyed_lookup(self: Any, key: str) -> str | None:
        try:
            with observation.suspended():
                return lookup(self, key)
        finally:
            note(self, key)

    @functools.wraps(holds)
    def keyed_holds(self: Any, key: object) -> bool:
        with observation.suspended():
            held = holds(self, key)
        if isinstance(key, str):
            note(self, key)
        return held

    def note_whole(catalogue: Any) -> None:
        directory = catalogue.shard_dir
        if directory is None:
            return
        for folder, _, files in os.walk(directory):
            observation.note_listing(folder)
            for name in sorted(files):
                if name.endswith(_SHARD_SUFFIX):
                    observation.note_file(os.path.join(folder, name))

    @functools.wraps(iterate)
    def whole_iteration(self: Any) -> Iterator[str]:
        keys = iterate(self)
        note_whole(self)
        return keys

    @functools.wraps(count)
    def whole_count(self: Any) -> int:
        size = count(self)
        note_whole(self)
        return size

    catalogue_class.__getitem__ = keyed_lookup
    catalogue_class.__contains__ = keyed_holds
    catalogue_class.__iter__ = whole_iteration
    catalogue_class.__len__ = whole_count
    setattr(catalogue_class, _PATCHED, True)


class _PatchingLoader(importlib.abc.Loader):
    """Execute the catalogue module with its own loader, then patch the class it defines."""

    def __init__(self, loader: importlib.abc.Loader, observation: Observation) -> None:
        self._loader = loader
        self._observation = observation

    @override
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        return self._loader.create_module(spec)

    @override
    def exec_module(self, module: ModuleType) -> None:
        self._loader.exec_module(module)
        _patch(self._observation, module)


class _CatalogueFinder(importlib.abc.MetaPathFinder):
    """Find the catalogue module as the other finders do, and patch it once it has run."""

    def __init__(self, observation: Observation) -> None:
        self._observation = observation

    @override
    def find_spec(
        self, fullname: str, path: Sequence[str] | None, target: ModuleType | None = None
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname != CATALOGUE_MODULE:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(fullname, path, target)
            if spec is not None and spec.loader is not None:
                spec.loader = _PatchingLoader(spec.loader, self._observation)
                return spec
        return None


def install(observation: Observation) -> None:
    """Key ``observation``'s catalogue reads from now on, whether the catalogue is imported already or later."""
    loaded = sys.modules.get(CATALOGUE_MODULE)
    if loaded is not None:
        _patch(observation, loaded)
        return
    sys.meta_path.insert(0, _CatalogueFinder(observation))


class CatalogueReader:
    """Answers keyed reads again from the catalogues as they stand when first asked, each opened once.

    It runs in a process that imports the product. A fresh reader reads the shards as they are now.
    """

    def __init__(self) -> None:
        """Open no catalogue until a key is asked of it."""
        self._catalogues: dict[Path, Any] = {}

    def entry_digest(self, shard_directory: Path, key: str) -> str:
        """What the catalogue under ``shard_directory`` answers for ``key``, as :func:`entry_digest` states it.

        A missing directory is ``absent``, which no answer digests to.
        """
        catalogue = self._catalogues.get(shard_directory)
        if catalogue is None:
            if not shard_directory.is_dir():
                return "absent"
            from cadrumo.core.i18n.lazy_catalogue import LazyLocaleCatalogue

            catalogue = LazyLocaleCatalogue(shard_directory.name, shard_dir=shard_directory)
            self._catalogues[shard_directory] = catalogue
        # Membership resolves the key exactly as the observed lookup did.
        _ = key in catalogue
        return entry_digest(_entry(catalogue, key))


def catalogue_shards(shard_directory: Path) -> tuple[Path, ...]:
    """Every shard file of the catalogue under ``shard_directory``, sorted; none when it is absent."""
    if not shard_directory.is_dir():
        return ()
    return tuple(sorted(path for path in shard_directory.rglob(f"*{_SHARD_SUFFIX}") if path.is_file()))
