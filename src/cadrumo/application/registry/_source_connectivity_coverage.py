"""Closure-limb projection from the canonical source-connectivity census.

The census owns candidate adjudication, live connected-proof validation, and
bounded follow-up.  This module only projects those reviewed decisions onto
loaded registry revisions.  A revision therefore cannot look clean merely
because the census has no candidate scoped to it.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, computed_field, model_validator

from ...core import STRICT_FROZEN_CONFIG, SourceConnectivityDisposition, SourceConnectivityExpiryPosture
from ...domain.calculations.registry import ModeloRevision, ValidatedRegistryAuthority
from ._closure import (
    RegistryClosureEvidence,
    RegistryClosureLimb,
    RegistryClosureOwnerDisposition,
    RegistryClosureRefusal,
)
from .source_connectivity import (
    RegistryDestinationCandidate,
    SourceConnectivityCensusEntry,
    SourceConnectivityCensusManifest,
    validate_census_destination_candidates,
)

__all__ = [
    "SourceConnectivityCoverageReport",
    "compose_source_connectivity_coverage",
]

_TERMINAL_DISPOSITIONS = frozenset(
    {
        SourceConnectivityDisposition.CONNECTED,
        SourceConnectivityDisposition.MANUAL_BY_DESIGN,
        SourceConnectivityDisposition.DUPLICATE_OR_STALE,
        SourceConnectivityDisposition.NOT_APPLICABLE,
    },
)
_BLOCKED_DISPOSITIONS = frozenset(
    {
        SourceConnectivityDisposition.GROUNDING_BLOCKED,
        SourceConnectivityDisposition.INGRESS_BLOCKED,
        SourceConnectivityDisposition.REGISTRY_BLOCKED,
    },
)


class SourceConnectivityCoverageReport(BaseModel):
    """Complete source-connectivity closure projection for one registry authority."""

    model_config = STRICT_FROZEN_CONFIG

    limbs: tuple[RegistryClosureLimb, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_one_source_limb_per_revision(self) -> SourceConnectivityCoverageReport:
        coordinates = tuple((limb.modelo, limb.revision) for limb in self.limbs)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("source-connectivity coverage requires one limb per registry revision")
        if any(limb.name != "source_connectivity" for limb in self.limbs):
            raise ValueError("source-connectivity coverage may contain only source-connectivity limbs")
        return self

    @computed_field
    @property
    def fully_satisfied(self) -> bool:
        """Return whether every registered revision has current terminal census evidence."""
        return all(limb.outcome == "satisfied" for limb in self.limbs)

    @computed_field
    @property
    def unsatisfied_limbs(self) -> tuple[RegistryClosureLimb, ...]:
        """Return visible source-census gaps without dropping their revision coordinates."""
        return tuple(limb for limb in self.limbs if limb.outcome != "satisfied")


def compose_source_connectivity_coverage(
    *,
    authority: ValidatedRegistryAuthority,
    census: SourceConnectivityCensusManifest,
    as_of: date,
) -> SourceConnectivityCoverageReport:
    """Project canonical census dispositions onto every loaded registry revision.

    ``census`` is the strict manifest returned by
    :func:`load_source_connectivity_census`; connected claims have consequently
    passed its live proof authority before this composer receives them.  The
    projection uses only validated registry declarations to decide whether a
    census destination applies to a particular revision.
    """
    authority.validate_registry()
    validate_census_destination_candidates(census, authority.modelos)
    limbs = tuple(
        _compose_revision_limb(
            census=census,
            modelo_id=modelo.id,
            revision=revision,
            as_of=as_of,
        )
        for modelo in sorted(authority.modelos, key=lambda item: item.id)
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id)
    )
    return SourceConnectivityCoverageReport(limbs=limbs)


def _compose_revision_limb(
    *,
    census: SourceConnectivityCensusManifest,
    modelo_id,
    revision: ModeloRevision,
    as_of: date,
) -> RegistryClosureLimb:
    """Compose one fail-closed source limb from entries scoped to this revision."""
    entries = tuple(
        entry
        for entry in census.entries
        if any(
            _candidate_applies_to_revision(candidate, modelo_id=modelo_id, revision=revision)
            for candidate in entry.registry_destination_candidates
        )
    )
    if not entries:
        return RegistryClosureLimb(
            modelo=modelo_id,
            revision=revision.id,
            name="source_connectivity",
            outcome="unmeasured",
            refusal=RegistryClosureRefusal(
                reason="unmeasured",
                detail="the canonical source-connectivity census declares no evidence scoped to this revision",
                disposition=RegistryClosureOwnerDisposition(
                    limb="source_connectivity",
                    state="deferred",
                    owner=census.census_id,
                    work_item=f"{census.census_id}:scope",
                    reconsideration_condition=(
                        "The canonical source-connectivity census declares current evidence scoped to this "
                        "validated revision."
                    ),
                ),
            ),
        )
    evidence = _entry_evidence(census, entries)
    expired = tuple(
        entry
        for entry in entries
        if entry.expiry_posture(as_of=as_of) is SourceConnectivityExpiryPosture.EXPIRED
    )
    if expired:
        entry = expired[0]
        if entry.disposition in _TERMINAL_DISPOSITIONS:
            return _expired_terminal_limb(
                modelo_id=modelo_id,
                revision=revision,
                evidence=evidence,
                entry=entry,
            )
        return _refused_limb(
            modelo_id=modelo_id,
            revision=revision,
            entries=entries,
            evidence=evidence,
            entry=entry,
            reason="stale_evidence",
            detail="source-connectivity census evidence expired without the required adjudication",
        )
    unresolved = tuple(entry for entry in entries if entry.disposition not in _TERMINAL_DISPOSITIONS)
    if unresolved:
        entry = unresolved[0]
        return _refused_limb(
            modelo_id=modelo_id,
            revision=revision,
            entries=entries,
            evidence=evidence,
            entry=entry,
            reason="unreviewed_evidence"
            if entry.disposition is SourceConnectivityDisposition.CONNECT_CANDIDATE
            else "missing_evidence",
            detail=(
                "source-connectivity census has a current connection candidate awaiting review"
                if entry.disposition is SourceConnectivityDisposition.CONNECT_CANDIDATE
                else "source-connectivity census retains a bounded blocking disposition"
            ),
        )
    return RegistryClosureLimb(
        modelo=modelo_id,
        revision=revision.id,
        name="source_connectivity",
        outcome="satisfied",
        evidence=evidence,
    )


def _candidate_applies_to_revision(
    candidate: RegistryDestinationCandidate,
    *,
    modelo_id,
    revision: ModeloRevision,
) -> bool:
    """Return whether one validated census destination exists in this revision."""
    if candidate.modelo_id != modelo_id:
        return False
    if candidate.semantic_role is not None:
        return any(casilla.semantic_role == candidate.semantic_role for casilla in revision.casillas)
    return any(binding.source is candidate.source_kind for binding in revision.bindings)


def _entry_evidence(
    census: SourceConnectivityCensusManifest,
    entries: tuple[SourceConnectivityCensusEntry, ...],
) -> tuple[RegistryClosureEvidence, ...]:
    """Preserve every applicable census grounding as closure evidence."""
    return tuple(
        RegistryClosureEvidence(
            authority=f"{census.census_id}:{entry.candidate_id}",
            locator=f"{grounding.locator_kind.value}:{grounding.reference}",
        )
        for entry in entries
        for grounding in entry.grounding
    )


def _expired_terminal_limb(
    *,
    modelo_id,
    revision: ModeloRevision,
    evidence: tuple[RegistryClosureEvidence, ...],
    entry: SourceConnectivityCensusEntry,
) -> RegistryClosureLimb:
    """Refuse expired terminal evidence with its census owner still accountable."""
    return RegistryClosureLimb(
        modelo=modelo_id,
        revision=revision.id,
        name="source_connectivity",
        outcome="refused",
        evidence=evidence,
        refusal=RegistryClosureRefusal(
            reason="stale_evidence",
            detail=f"source-connectivity terminal evidence expired: {entry.candidate_id}",
            disposition=RegistryClosureOwnerDisposition(
                limb="source_connectivity",
                state="owned",
                owner=entry.owner,
                work_item=f"{entry.candidate_id}:revalidate-expired-evidence",
                reconsideration_condition=(
                    "Current source-connectivity evidence revalidates the terminal disposition."
                ),
            ),
        ),
    )


def _refused_limb(
    *,
    modelo_id,
    revision: ModeloRevision,
    entries: tuple[SourceConnectivityCensusEntry, ...],
    evidence: tuple[RegistryClosureEvidence, ...],
    entry: SourceConnectivityCensusEntry,
    reason,
    detail: str,
) -> RegistryClosureLimb:
    """Retain the exact unresolved census row as an actionable closure refusal."""
    follow_up = entry.bounded_follow_up
    if follow_up is None or entry.review_condition is None:
        raise ValueError(f"unresolved census entry lacks bounded accountability: {entry.candidate_id}")
    state = "deferred" if entry.disposition is SourceConnectivityDisposition.CONNECT_CANDIDATE else "blocked"
    candidate_ids = ", ".join(item.candidate_id for item in entries)
    return RegistryClosureLimb(
        modelo=modelo_id,
        revision=revision.id,
        name="source_connectivity",
        outcome="refused",
        evidence=evidence,
        refusal=RegistryClosureRefusal(
            reason=reason,
            detail=f"{detail}: {entry.candidate_id}; applicable census rows: {candidate_ids}",
            disposition=RegistryClosureOwnerDisposition(
                limb="source_connectivity",
                state=state,
                owner=entry.follow_up_owner() or entry.owner,
                work_item=follow_up.action_id,
                reconsideration_condition=entry.review_condition,
            ),
        ),
    )
