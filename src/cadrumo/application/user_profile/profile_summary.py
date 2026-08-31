"""The pure, non-authenticating profile listing boundary.

This module is the whole public surface for "which profiles exist and what are
they called".  It is deliberately separate from
:mod:`cadrumo.application.user_profile.profile_repository`: that module owns the
authenticated aggregate, and reaching it pulls the transaction journal, the
password material reader, and the label-head publisher -- roughly a hundred
modules, and a per-profile custody lock, to answer a question that needs
neither.

Listing therefore never unwraps a DEK, derives a key, reads keyring or session
state, opens a password or recovery envelope, authenticates a sentinel, reads
encrypted facts, runs recovery, publishes a label head, or repairs a
projection.  Those all remain with the commands that own them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ...core.identity import ProfileId, ProfileLabel
from ...core.paths import effective_storage_root
from ...core.profile_discovery import ProfileSummaryOutcome
from .custody_ports import (
    ProfileCustodyCapsuleSummaryWitnessPort,
    ProfileCustodyConcurrentChangeError,
    ProfileCustodyRecordIntegrityError,
    profile_custody_port,
)

_SUMMARY_MODEL_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


class ProfileSummary(BaseModel):
    """Listing projection with no key, KDF, manifest, or recovery material.

    Every field is read from the two records one anchored observation already
    proved coherent, so building a summary costs no further filesystem work and
    cannot carry another capsule's provenance.  There is deliberately nothing
    here that implies custody health: a summary says a capsule is committed and
    what it is called, never that it can be unlocked.
    """

    model_config = _SUMMARY_MODEL_CONFIG

    profile_id: ProfileId
    label: ProfileLabel
    label_revision: int
    published_at: datetime
    publication_kind: Literal["enroll", "restore"]


class ProfileSummaryInventory(BaseModel):
    """The complete result of one non-authenticating listing observation.

    A caller reads ``outcome`` before ``summaries``.  A degraded or concurrent
    observation carries no summaries at all rather than a partial set, because
    a partial listing is indistinguishable from a store that genuinely holds
    fewer profiles -- and "your profile is gone" is the one wrong answer this
    boundary must never give.
    """

    model_config = _SUMMARY_MODEL_CONFIG

    outcome: ProfileSummaryOutcome = ProfileSummaryOutcome.RECOGNIZED
    summaries: tuple[ProfileSummary, ...] = ()
    detail: str | None = None

    @property
    def recognized(self) -> bool:
        """Whether the observation produced a trustworthy complete listing."""
        return self.outcome is ProfileSummaryOutcome.RECOGNIZED


def summary_inventory(*, root: Path | None = None) -> ProfileSummaryInventory:
    """Project every committed capsule from recognized witnesses alone.

    The adapter's single anchored scan is the entire read: an empty store costs
    one directory enumeration, and a populated one costs two bounded reads per
    profile.  Both failure endings are typed rather than raised, because a
    listing that cannot be trusted must still render -- saying so -- instead of
    aborting the command an operator ran to find out what they have.
    """
    try:
        witnesses = profile_custody_port().list_committed_capsule_summaries(root=effective_storage_root(root))
    except ProfileCustodyConcurrentChangeError as exc:
        return ProfileSummaryInventory(outcome=ProfileSummaryOutcome.CONCURRENT_CHANGE, detail=str(exc))
    except ProfileCustodyRecordIntegrityError as exc:
        return ProfileSummaryInventory(outcome=ProfileSummaryOutcome.DEGRADED, detail=str(exc))
    return ProfileSummaryInventory(summaries=tuple(_summary_of(witness) for witness in witnesses))


def require_summaries(*, root: Path | None = None) -> tuple[ProfileSummary, ...]:
    """Return the summaries, refusing rather than reporting a degraded read.

    :func:`summary_inventory` reports an unreadable store as a typed outcome
    with no rows, which is right for a surface that can show the operator why.
    A caller that only gets a sequence back cannot show anything, and an empty
    sequence there would mean "you have no profiles" -- the opposite of the
    truth, and the answer that makes someone think their data is gone. Such a
    caller uses this instead and handles the refusal.
    """
    inventory = summary_inventory(root=root)
    if not inventory.recognized:
        raise ProfileCustodyRecordIntegrityError(inventory.detail or str(inventory.outcome))
    return inventory.summaries


def _summary_of(witness: ProfileCustodyCapsuleSummaryWitnessPort) -> ProfileSummary:
    """Project one already-coherent witness with no further storage access."""
    return ProfileSummary(
        profile_id=str(witness.profile_id),
        label=witness.label.label,
        label_revision=witness.label.label_revision,
        published_at=datetime.fromisoformat(witness.commit.published_at.replace("Z", "+00:00")).astimezone(UTC),
        publication_kind=witness.commit.publication_kind,
    )


__all__ = ["ProfileSummary", "ProfileSummaryInventory", "require_summaries", "summary_inventory"]
