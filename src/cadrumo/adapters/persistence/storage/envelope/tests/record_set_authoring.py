"""Finite fixture set replacement over the actual atomic secure-object kernel."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pydantic import BaseModel

from ......core.logging import get_logger
from ..secure_bound_repository import SecureBoundRepository

_log = get_logger(__name__)


def replace_records[T: BaseModel](
    self: SecureBoundRepository[T], replacements: Sequence[T], stale_identifiers: Iterable[str]
) -> None:
    """Commit ``replacements`` and remove ``stale_identifiers`` in one transaction.

    The atomic set-replace primitive: a caller that must clear a window of
    rows and write its successor set gets all-or-nothing semantics instead
    of a delete loop followed by a save loop, where a failure part-way
    through leaves the store holding neither the old set nor the new one.

    An identifier that is BOTH stale and replaced is written, not deleted:
    :meth:`adapters.persistence.storage.sql._secure_object_writes.SecureObjectWriteOperations.apply_batch`
    applies writes before deletions, so a row carried across the replacement
    would otherwise be upserted and then removed in the same transaction.

    Args:
        replacements: The payloads that constitute the new set.
        stale_identifiers: Natural ids of rows to remove. Ids also carried
            by ``replacements`` are ignored.
    """
    writes = tuple(self.to_secure_object_write(payload) for payload in replacements)
    retained = {write.object_key for write in writes}
    deletions = tuple(
        self.to_secure_object_deletion(identifier)
        for identifier in dict.fromkeys(stale_identifiers)
        if identifier not in retained
    )
    self._objects.apply_batch(writes, deletions)
    _log.debug("secure-bound: replaced %d row(s) in %s, removed %d stale", len(writes), self.namespace, len(deletions))
