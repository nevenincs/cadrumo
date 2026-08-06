"""Canonical two-stage retention selection for the LLM secure-object stores.

The response cache (:class:`~adapters.outbound.llm.LLMCache`), the usage
ledger (:class:`~adapters.outbound.llm.UsageRecorder`), and the run-telemetry
recorder (:class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`) each bound
their store under one operational obligation: an age cutoff, then an
oldest-first record-count cap. The namespaces, the settings that supply the
bounds, and the record timestamp field differ per store by design -- the cache
and the usage ledger stamp ``created_at`` at write time while a run record
carries its own ``started_at``. The *ordering and boundary policy* is not a
per-store choice, so it lives here once and each store supplies its timestamp
as a projection.

Deletion stays with the caller: each store owns its own secure-object
namespace and its own missing-key contract, so this module selects keys and
never removes anything.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

__all__ = ["select_retention_removal_keys"]


def select_retention_removal_keys[RecordT](
    rows: Sequence[tuple[RecordT, str]],
    *,
    cutoff: datetime,
    max_records: int,
    timestamp: Callable[[RecordT], datetime],
) -> list[str]:
    """Select object keys to delete under the two-stage retention/count bound.

    Args:
        rows: ``(record, object_key)`` pairs sorted oldest-first. The
            oldest-first order is what makes the count cap evict the oldest
            excess rather than an arbitrary slice; an unsorted input silently
            evicts the wrong records.
        cutoff: Age boundary. A record strictly older than ``cutoff`` is
            selected for removal; a record exactly at ``cutoff`` is retained,
            so the boundary is exclusive.
        max_records: Maximum number of records to retain *after* the age
            cutoff has been applied. When more than ``max_records`` survive
            the cutoff, the oldest excess survivors are selected too.
        timestamp: Projection returning the record's retention timestamp --
            ``created_at`` for cache and usage records, ``started_at`` for run
            telemetry.

    Returns:
        Object keys to delete, age-expired first then count-capped. The two
        stages cannot overlap, so no key is returned twice.
    """
    to_remove = [object_key for record, object_key in rows if timestamp(record) < cutoff]
    remaining = [row for row in rows if timestamp(row[0]) >= cutoff]
    if len(remaining) > max_records:
        excess_count = len(remaining) - max_records
        to_remove.extend(object_key for _, object_key in remaining[:excess_count])
    return to_remove
