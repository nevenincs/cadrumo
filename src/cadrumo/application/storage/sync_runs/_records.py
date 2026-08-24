"""Local typed record of one completed synchronisation run, and its store.

The provenance authority for "when was this last synchronised". Before this
store, no such authority existed anywhere in the source tree -- a searched
absence, not an assumed one: there is no ``last_sync``, ``synced_at`` or
``last_synced`` field in production code, so the only signal an operator had was
whatever the remote surface happened to stamp on itself. A remote stamp answers
"when did the far side last change", which is a different question and is
unavailable at all when the run fails partway.

Why a second run-record store rather than an existing one
---------------------------------------------------------
:class:`~adapters.outbound.llm.LLMRunRecord` is a shipped local encrypted
run-record store, and it is deliberately not extended here. Its fields are
provider-call accounting -- caller, provider, model, duration, succeeded,
error kind -- and not one of them carries a SUBJECT. It cannot express what was
synchronised, and a sync run has no provider or model to record. That store is a
latency-and-failure shape; this one is a coverage shape, and substitutability
fails in both directions. Its package documents that it admits no parallel
capture path, which is an invariant about its own projections rather than a
prohibition on any second run record in the tree.

What a record claims, and what it does not
------------------------------------------
A record is written on completion of a run over ONE surface, on partial failure
as well as on success. That is deliberate and it is the half most easily
dropped: a record written only on success makes every truncated sweep invisible,
which is precisely the state a reader would otherwise mistake for complete
coverage. Partial failure means a run that TRIED to write and got partway --
a different event from a run that declined to write by design.

A DRY RUN WRITES NO RECORD, and the absence is declared rather than accidental.
A preview reads the remote surface and persists nothing, so it has no last-sync
provenance: nothing was synced. A provenance record is itself a persist, so
writing one from the preview branch would defeat the guard whose entire purpose
is that a preview leaves no trace. A reader finding no record after a dry run
is seeing the contract, not a gap.

``unit_count`` and ``divergence_count`` describe what the run actually reached,
never what it intended to reach. A run that swept three of ten periods records
three, and its ``resolved_scope`` says which three. The pair is what lets a
later reader distinguish a clean full sweep from a clean partial one -- two runs
that are identical in every other field and mean entirely different things.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import SyncSurface
from ....core.identity import BucketId
from ....core.time import validate_utc_aware
from ....domain.buckets import BucketEvent, BucketEventId

__all__ = [
    "SyncRunCoverage",
    "SyncRunCoverageSource",
    "SyncRunRecord",
    "SyncRunRecordReference",
    "SyncRunRecordRepositoryProtocol",
    "bounded_scope_description",
    "coverage_of",
    "sync_run_record_key",
]

SyncRunRecordReference = Annotated[
    str,
    Field(pattern=r"^sync-run:(?:filed_declarations|calc_sheets_export):[0-9a-f]{64}$"),
]
"""Stable encrypted-store key resolving one persisted sync-run record."""

#: Bound on the persisted scope description. Not a formality: a filed sweep with
#: no explicit modelo list resolves to EVERY bundled modelo, which enumerates
#: past a kilobyte, so an unbounded field would refuse the default sweep at the
#: end of the run -- after every unit had already been fetched and written.
_RESOLVED_SCOPE_MAX_LENGTH = 256


@runtime_checkable
class SyncRunCoverageSource(Protocol):
    """One object that knows BOTH what a run reached and what diverged.

    The whole point of the protocol is that it is a single object. A run's two
    coverage counts have to be drawn from one population, and the way they stop
    being drawn from one population is a caller reading each from a different
    place -- which is not a hypothetical. The filed sweep once paired advisories
    raised per observation ABSORBED against the count of observations
    successfully ENROLLED, two populations that narrow apart under a
    latest-per-period collapse and under a best-effort enrolment failure. The
    record refused the impossible pair at the very end of a real run, after
    every unit had already been fetched and written.

    Passing counts as two integers makes that mistake expressible at every call
    site. Passing one source makes it expressible only by writing an object that
    lies about itself, which is a far higher bar and one a reviewer can see.

    The member names are deliberately surface-neutral rather than borrowed from
    the filed sweep's own vocabulary, because the second surface has to satisfy
    the same contract without renaming it.
    """

    @property
    def reached_count(self) -> int:
        """How many units the run REACHED, counted in every mode."""
        ...

    @property
    def divergences(self) -> Sequence[object]:
        """The divergences found among those reached units, one entry each."""
        ...


class SyncRunCoverage(BaseModel):
    """What one run covered: units reached, and how many of them diverged.

    Built only through :func:`coverage_of`, so the two counts always come from
    one source. The bound below is therefore a backstop against a lying source
    rather than the primary defence -- the primary defence is that there is
    nowhere to pass two unrelated numbers in.
    """

    model_config = _STRICT_FROZEN

    unit_count: int = Field(ge=0)
    divergence_count: int = Field(ge=0)

    @field_validator("divergence_count")
    @classmethod
    def _divergences_are_bounded_by_units(cls, value: int, info: object) -> int:
        """Refuse more divergences than units reached."""
        data = getattr(info, "data", {})
        unit_count = data.get("unit_count")
        if unit_count is not None and value > unit_count:
            raise ValueError(
                f"divergence_count {value} exceeds unit_count {unit_count}: "
                "a unit that was never reached cannot have diverged",
            )
        return value


def coverage_of(source: SyncRunCoverageSource) -> SyncRunCoverage:
    """Derive both coverage counts from one source, which is the entire contract.

    Read both numbers off ``source`` and nothing else. A caller that wants to
    record a run over a surface teaches that surface's own accumulator to answer
    :attr:`SyncRunCoverageSource.reached_count` and
    :attr:`SyncRunCoverageSource.divergences`, rather than picking two counts at
    the call site and hoping they describe the same population.

    Args:
        source: The run's own accumulator, or anything else that can answer for
            one population.

    Returns:
        The validated pair, ready to hand to :func:`record_sync_run`.
    """
    return SyncRunCoverage(
        unit_count=source.reached_count,
        divergence_count=len(source.divergences),
    )


class SyncRunRecord(BaseModel):
    """One completed synchronisation run over one surface, in full.

    Carries the surface, the scope the run actually resolved, the instant it
    finished, how many units it reached and how many of those diverged, plus the
    id of the bucket event it is co-written with. Read
    :class:`~core.SyncSurface` for why the surface axis is a closed set and why
    it has exactly two members.

    ``succeeded`` is not redundant against ``divergence_count``. A run can
    finish cleanly having found divergences -- that is the normal outcome the
    store exists to record -- and a run can fail partway having found none,
    because it never got far enough to look. Reading failure off the divergence
    count would invert both cases.

    Attributes:
        bucket_event_id: Id of the co-written sync-run bucket event. Also the
            trailing segment of this record's storage key, so record and event
            are joined by identity rather than by a field that could drift.
        bucket_id: Profile bucket the run belongs to.
        surface: Which external surface this run covered.
        resolved_scope: What the run actually resolved its scope to, as the
            operator-facing description of the covered set. Empty only when the
            run failed before a scope could be resolved at all.
        succeeded: Whether the run completed without a refusal. False for a
            partial run, which is still recorded rather than dropped.
        unit_count: How many units the run REACHED. Never the intended total --
            a sweep that covered three of ten periods records three.
        divergence_count: How many of those reached units diverged. Bounded by
            ``unit_count``, because a unit that was never reached cannot have
            been found to diverge.
        completed_at: UTC instant the run finished, successfully or not.
    """

    model_config = _STRICT_FROZEN

    bucket_event_id: BucketEventId
    bucket_id: BucketId
    surface: SyncSurface
    resolved_scope: str = Field(default="", max_length=_RESOLVED_SCOPE_MAX_LENGTH)
    """What the run resolved its scope to, bounded so a wide sweep can persist.

    The bound is a real constraint rather than a formality: a filed sweep with
    no explicit modelo list resolves to EVERY bundled modelo, which enumerates
    past a kilobyte. A caller with a scope that would overflow must summarise it
    through :func:`bounded_scope_description` rather than truncate it, because a
    truncated enumeration reads as a complete list of a smaller set -- which is
    the same class of lie as a partial sweep reading as a full one.
    """
    succeeded: bool
    unit_count: int = Field(default=0, ge=0)
    divergence_count: int = Field(default=0, ge=0)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def _completed_at_is_utc(cls, value: datetime) -> datetime:
        """Hold the persisted instant to the canonical UTC-aware contract.

        A bare ``datetime`` accepts a naive or ``+01:00`` value, which would
        make two runs over the same surface unorderable against each other and
        would read a Madrid-local instant back as if it were UTC -- in a store
        whose entire purpose is answering "when did this last happen".
        """
        return validate_utc_aware(value)

    @field_validator("divergence_count")
    @classmethod
    def _divergences_are_bounded_by_units(cls, value: int, info: object) -> int:
        """Refuse more divergences than units reached.

        A unit the run never reached cannot have been found to diverge, so a
        record claiming otherwise is describing a run that did not happen.

        This repeats the bound :class:`SyncRunCoverage` already enforces, and
        the repetition is deliberate rather than an oversight. The two guard
        different paths: coverage guards CONSTRUCTION, where the invalid pair
        is authored, while this guards the LOAD, where a corrupted or
        hand-edited on-disk payload never passed through coverage at all. A
        persisted boundary that trusts its writer has no defence against bytes
        the writer did not produce.
        """
        data = getattr(info, "data", {})
        unit_count = data.get("unit_count")
        if unit_count is not None and value > unit_count:
            raise ValueError(
                f"divergence_count {value} exceeds unit_count {unit_count}: "
                "a unit that was never reached cannot have diverged",
            )
        return value


def bounded_scope_description(items: tuple[str, ...], *, suffix: str = "") -> str:
    """Describe a scope within the record's bound, summarising rather than truncating.

    A truncated enumeration is worse than a summary: it reads as a COMPLETE list
    of a smaller set, which is the same lie a partial sweep tells when it reads
    as a full one, and this store exists to stop exactly that. So an oversized
    scope collapses to a count and a range rather than to a prefix.

    Args:
        items: The scope members, in the order the caller resolved them.
        suffix: Trailing qualifier appended to either form, e.g. a year range.

    Returns:
        Either the full enumeration or a summary, always inside the field bound.
    """
    tail = f" {suffix}" if suffix else ""
    enumerated = f"{','.join(items)}{tail}"
    if len(enumerated) <= _RESOLVED_SCOPE_MAX_LENGTH:
        return enumerated
    return f"{len(items)} modelos ({items[0]}..{items[-1]}){tail}"


def sync_run_record_key(*, surface: SyncSurface, bucket_event_id: str) -> SyncRunRecordReference:
    """Return the storage key for one run over one surface.

    Keyed ``sync-run:{surface}:{bucket_event_id}``, matching the namespace's
    declared grammar. N records per surface rather than one: the store is the
    last-sync provenance authority, and a key scoped to the surface alone would
    make the last sync the only sync.

    The scope is deliberately absent from the key. A run's resolved scope
    describes what it covered, not which run it was, so a truncated sweep and a
    full sweep over the same surface stay distinct records -- the pair a reader
    needs in order to tell partial coverage from complete.
    """
    return f"sync-run:{surface.value}:{bucket_event_id}"


@runtime_checkable
class SyncRunRecordRepositoryProtocol(Protocol):
    """Persistence port for one sync-run record and its history event.

    The concrete encrypted implementation lives in
    :mod:`adapters.persistence.profile.sync_runs`. Application orchestration
    supplies the record and already-derived event; the adapter owns the shared
    secure-object transaction that makes the pair durable together.
    """

    def save_with_bucket_event(self, record: SyncRunRecord, event: BucketEvent) -> None:
        """Persist ``record`` and ``event`` in one atomic storage transaction."""
        ...
