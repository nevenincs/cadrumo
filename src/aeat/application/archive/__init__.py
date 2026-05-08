"""Archive subsystem: portable export and import of every encrypted secure object.

The archive subsystem captures every namespace registered in
:mod:`aeat.application.archive._registry` (invoice catalogue,
transaction catalogue, filing drafts, ...) into a single
:class:`ArchiveBundle` JSON document and restores from one. Records are
emitted as decoded :class:`Envelope` JSON (not the encrypted bytes), so
a bundle is portable across machines and across master keys: the
restore re-saves through the same per-namespace
:class:`SecureObjectRepository.save` path that the domain repositories
use, which encrypts under the receiving machine's master key.

Public surface:

- :class:`ArchiveBundle`, :class:`ArchiveRecord`,
  :class:`RestoreReport`, :class:`RestoreEntry`, :class:`RestoreOutcome`,
  :class:`ConflictPolicy` — wire models.
- :func:`create_archive` — produce a bundle from the live backend.
- :func:`restore_archive` — write a bundle back into the backend.
- :class:`ArchiveAdapter`, :func:`register_archive_adapter`,
  :func:`archive_adapter_for`, :func:`all_archive_adapters` — extension
  surface for new namespaces.
- :class:`ArchiveError` and concrete subclasses — typed failures.
"""

from __future__ import annotations

from ._errors import (
    ArchiveAdapterMissingError,
    ArchiveBundleSchemaError,
    ArchiveConflictError,
    ArchiveError,
)
from ._export import create_archive
from ._import import restore_archive
from ._models import (
    ARCHIVE_BUNDLE_SCHEMA_VERSION,
    ArchiveBundle,
    ArchiveRecord,
    ConflictPolicy,
    RestoreEntry,
    RestoreOutcome,
    RestoreReport,
)
from ._registry import (
    ArchiveAdapter,
    KeyStrategy,
    all_archive_adapters,
    archive_adapter_for,
    register_archive_adapter,
)

__all__ = [
    "ARCHIVE_BUNDLE_SCHEMA_VERSION",
    "ArchiveAdapter",
    "ArchiveAdapterMissingError",
    "ArchiveBundle",
    "ArchiveBundleSchemaError",
    "ArchiveConflictError",
    "ArchiveError",
    "ArchiveRecord",
    "ConflictPolicy",
    "KeyStrategy",
    "RestoreEntry",
    "RestoreOutcome",
    "RestoreReport",
    "all_archive_adapters",
    "archive_adapter_for",
    "create_archive",
    "register_archive_adapter",
    "restore_archive",
]
