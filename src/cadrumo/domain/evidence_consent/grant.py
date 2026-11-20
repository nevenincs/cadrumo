"""Whether a person's recorded grant still covers an off-host read, read from the consent ledger alone.

A grant covers one task kind on one lane: the provider, transport and model the
person consented to. Its scope bounds how long: one job, the agent session it
was given in, or until the person revokes it. A revocation covers every read
after it. The ledger is the only source: a grant is never inferred from a job,
a setting or a lane, and a grant the ledger does not hold covers nothing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ..transactions.classification_job import ClassificationConsentScope
from .record import EvidenceConsentLedgerEntry, EvidenceConsentRecordKind

__all__ = [
    "ConsentGrantLane",
    "ConsentGrantStanding",
    "consent_grant_standing",
    "standing_consent_grant",
]


class ConsentGrantStanding(StrEnum):
    """Whether one recorded grant covers a read now, and if not, why not."""

    VALID = "valid"
    MISSING = "missing"
    """The ledger holds no such grant for this profile, or the grant was for another job."""
    REVOKED = "revoked"
    EXPIRED = "expired"
    """The grant covered the agent session it was given in, and that session has ended."""
    LANE_MISMATCH = "lane_mismatch"
    """The grant covers another lane or task kind than the read would use."""


@dataclass(frozen=True, slots=True)
class ConsentGrantLane:
    """The lane and task kind a read would use, as a grant must name them."""

    provider: str
    transport: str
    model: str
    task_kind: str


def _grants(entries: Iterable[EvidenceConsentLedgerEntry], profile_bucket_id: str) -> list[EvidenceConsentLedgerEntry]:
    return [
        entry
        for entry in entries
        if entry.profile_bucket_id == profile_bucket_id and entry.record_kind is EvidenceConsentRecordKind.GRANT
    ]


def _revoked(entries: Iterable[EvidenceConsentLedgerEntry], profile_bucket_id: str) -> frozenset[str]:
    return frozenset(
        entry.revoked_grant_id
        for entry in entries
        if entry.profile_bucket_id == profile_bucket_id
        and entry.record_kind is EvidenceConsentRecordKind.REVOCATION
        and entry.revoked_grant_id is not None
    )


def _covers_lane(entry: EvidenceConsentLedgerEntry, lane: ConsentGrantLane) -> bool:
    grant = entry.grant
    return grant is not None and (entry.provider, grant.transport, entry.model, grant.task_kind) == (
        lane.provider,
        lane.transport,
        lane.model,
        lane.task_kind,
    )


def consent_grant_standing(
    entries: Iterable[EvidenceConsentLedgerEntry],
    *,
    grant_id: str,
    profile_bucket_id: str,
    lane: ConsentGrantLane,
    job_id: str,
    session_reference: str | None,
) -> ConsentGrantStanding:
    """Return whether the grant ``grant_id`` covers a read by ``job_id`` on ``lane`` in the current session.

    ``session_reference`` names the profile session open now, or ``None`` when
    none is, in which case no session grant covers anything.
    """
    recorded = tuple(entries)
    entry = next(
        (
            entry
            for entry in _grants(recorded, profile_bucket_id)
            if entry.grant is not None and entry.grant.grant_id == grant_id
        ),
        None,
    )
    grant = None if entry is None else entry.grant
    if entry is None or grant is None:
        return ConsentGrantStanding.MISSING
    if grant_id in _revoked(recorded, profile_bucket_id):
        return ConsentGrantStanding.REVOKED
    if not _covers_lane(entry, lane):
        return ConsentGrantStanding.LANE_MISMATCH
    if grant.scope is ClassificationConsentScope.ONCE and grant.job_id != job_id:
        return ConsentGrantStanding.MISSING
    if grant.scope is ClassificationConsentScope.AGENT_SESSION and (
        session_reference is None or grant.session_reference != session_reference
    ):
        return ConsentGrantStanding.EXPIRED
    return ConsentGrantStanding.VALID


def standing_consent_grant(
    entries: Iterable[EvidenceConsentLedgerEntry],
    *,
    profile_bucket_id: str,
    lane: ConsentGrantLane,
    session_reference: str | None,
) -> EvidenceConsentLedgerEntry | None:
    """Return the newest unrevoked grant that covers any job on ``lane`` now, or ``None``.

    Only a remembered grant, or a grant for the agent session open now, covers
    a job it was not given for; a grant for one job never does.
    """
    recorded = tuple(entries)
    revoked = _revoked(recorded, profile_bucket_id)
    covering = [
        entry
        for entry in _grants(recorded, profile_bucket_id)
        if entry.grant is not None
        and entry.grant.grant_id not in revoked
        and _covers_lane(entry, lane)
        and (
            entry.grant.scope is ClassificationConsentScope.REMEMBERED
            or (
                entry.grant.scope is ClassificationConsentScope.AGENT_SESSION
                and session_reference is not None
                and entry.grant.session_reference == session_reference
            )
        )
    ]
    if not covering:
        return None
    return max(covering, key=lambda entry: (entry.recorded_at, entry.entry_id))
