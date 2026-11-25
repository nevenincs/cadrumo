"""Append-only persisted history for IRPF activity assets."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    asset_schedule_history,
    claims_through_year,
    current_revisions,
    effective_claims,
    record_claim,
)
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.register_records import (
    ActivityAssetDescriptor,
    ActivityAssetDescriptorFacts,
    ActivityAssetEventKind,
    ActivityAssetHistoryEvent,
)
from ...domain.renta.actividad_asset.schedule import (
    last_day_covered,
    require_claim_after_opening_year,
    require_method_continuity,
    require_opening_method,
)


class ActivityAssetHistory(BaseModel):
    """One encrypted profile document containing immutable asset facts and claims.

    ``descriptors`` and ``events`` state nothing about tax: they stay out of every
    revision and claim identity, and :meth:`same_tax_facts` ignores them.  A record
    with no event is one written before order was kept; it sorts first.
    """

    model_config = STRICT_FROZEN_CONFIG

    revisions: tuple[ActivityAssetRevision, ...] = ()
    claims: tuple[AmortizationClaim, ...] = ()
    descriptors: tuple[ActivityAssetDescriptor, ...] = ()
    events: tuple[ActivityAssetHistoryEvent, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_history(self) -> Self:
        revisions_by_id = self._index_revisions_and_validate_chains()
        self._validate_claim_identities()
        self._validate_claim_references(revisions_by_id)
        self._validate_claim_replay()
        self._validate_descriptors()
        self._validate_events()
        return self

    def _index_revisions_and_validate_chains(self) -> dict[str, ActivityAssetRevision]:
        revisions_by_id = {revision.revision_id: revision for revision in self.revisions}
        if len(revisions_by_id) != len(self.revisions):
            raise ValueError("activity asset history contains duplicate revision identities")
        asset_ids = {revision.asset_id for revision in self.revisions}
        for asset_id in asset_ids:
            self._validate_asset_revision_chain(asset_id)
        return revisions_by_id

    def _validate_claim_identities(self) -> None:
        claim_ids = {claim.claim_id for claim in self.claims}
        if len(claim_ids) != len(self.claims):
            raise ValueError("activity asset history contains duplicate claim identities")

    def _validate_claim_references(self, revisions_by_id: dict[str, ActivityAssetRevision]) -> None:
        for claim in self.claims:
            revision = revisions_by_id.get(claim.asset_revision_id)
            if revision is None:
                raise ValueError("activity asset claim references an unknown revision")
            if revision.asset_id != claim.asset_id:
                raise ValueError("activity asset claim identity does not match its revision")
            if revision.asset_kind is not claim.asset_kind:
                raise ValueError("activity asset claim kind does not match its revision")
            self._validate_baja_reference(claim, revisions_by_id)

    @staticmethod
    def _validate_baja_reference(
        claim: AmortizationClaim,
        revisions_by_id: dict[str, ActivityAssetRevision],
    ) -> None:
        if claim.disposal_revision_id is None:
            return
        baja = revisions_by_id.get(claim.disposal_revision_id)
        if baja is None or baja.asset_id != claim.asset_id or baja.disposal is None:
            raise ValueError("activity asset claim names a baja its asset does not have")
        boundary = baja.disposal.boundary
        if claim.covered_until != boundary and not (claim.amount == Decimal("0") and claim.covered_from >= boundary):
            raise ValueError("a claim a baja wrote ends at its boundary or lies after it at amount zero")

    def _validate_claim_replay(self) -> None:
        replayed_claims: tuple[AmortizationClaim, ...] = ()
        for claim in self.claims:
            replayed_claims = record_claim(replayed_claims, claim).claims

    def _validate_asset_revision_chain(self, asset_id: str) -> None:
        chain = tuple(revision for revision in self.revisions if revision.asset_id == asset_id)
        for position, revision in enumerate(chain, start=1):
            if revision.revision_number != position:
                raise ValueError("asset revisions must be append-only and consecutively numbered")
            expected_superseded_id = None if position == 1 else chain[position - 2].revision_id
            if revision.supersedes_revision_id != expected_superseded_id:
                raise ValueError("asset revision supersession must point to the prior revision of the same asset")

    def _validate_descriptors(self) -> None:
        known_assets = {revision.asset_id for revision in self.revisions}
        numbers: dict[str, int] = {}
        for descriptor in self.descriptors:
            if descriptor.asset_id not in known_assets:
                raise ValueError("activity asset descriptor names an unknown asset")
            numbers[descriptor.asset_id] = numbers.get(descriptor.asset_id, 0) + 1
            if descriptor.descriptor_number != numbers[descriptor.asset_id]:
                raise ValueError("activity asset descriptors must be append-only and consecutively numbered")

    def _validate_events(self) -> None:
        records = self._record_ids()
        unlogged = len(records) - len(self.events)
        if unlogged < 0:
            raise ValueError("activity asset history has more events than records")
        previous = unlogged
        seen: set[tuple[ActivityAssetEventKind, str]] = set()
        for event in self.events:
            if event.sequence <= previous:
                raise ValueError("activity asset events must follow the unlogged records in strictly increasing order")
            previous = event.sequence
            address = (event.kind, event.record_id)
            if records.get(address) != event.asset_id:
                raise ValueError("activity asset event references an unknown record")
            if address in seen:
                raise ValueError("activity asset history orders a record twice")
            seen.add(address)

    def _record_ids(self) -> dict[tuple[ActivityAssetEventKind, str], str]:
        """Map every record's kind and identity to its asset, revisions before claims before descriptors."""
        revisions_by_id = {item.revision_id: item for item in self.revisions}
        return {
            **{
                (_revision_event_kind(item, revisions_by_id), item.revision_id): item.asset_id
                for item in self.revisions
            },
            **{(ActivityAssetEventKind.CLAIM, item.claim_id): item.asset_id for item in self.claims},
            **{(ActivityAssetEventKind.DESCRIPTOR, item.descriptor_id): item.asset_id for item in self.descriptors},
        }

    def ordered_events(self) -> tuple[ActivityAssetHistoryEvent, ...]:
        """Return one event per record in history order; records written before order was kept come first."""
        logged = {(event.kind, event.record_id) for event in self.events}
        unlogged = tuple(address for address in self._record_ids().items() if address[0] not in logged)
        return (
            *(
                ActivityAssetHistoryEvent(sequence=position, kind=kind, asset_id=asset_id, record_id=record_id)
                for position, ((kind, record_id), asset_id) in enumerate(unlogged, start=1)
            ),
            *self.events,
        )

    def _next_event(
        self,
        kind: ActivityAssetEventKind,
        asset_id: str,
        record_id: str,
        *,
        recorded_at: datetime | None,
        origin: str | None,
    ) -> ActivityAssetHistoryEvent:
        unlogged = len(self._record_ids()) - len(self.events)
        last = self.events[-1].sequence if self.events else unlogged
        return ActivityAssetHistoryEvent(
            sequence=last + 1,
            kind=kind,
            asset_id=asset_id,
            record_id=record_id,
            recorded_at=recorded_at,
            origin=origin,
        )

    def same_tax_facts(self, other: ActivityAssetHistory) -> bool:
        """Say whether two documents hold the same revisions and claims, whatever their descriptors."""
        return self.revisions == other.revisions and self.claims == other.claims

    def current_descriptor(self, asset_id: str) -> ActivityAssetDescriptor | None:
        """Return an element's latest descriptor, or ``None`` when none was ever written."""
        return next((item for item in reversed(self.descriptors) if item.asset_id == asset_id), None)

    def describe(
        self,
        asset_id: str,
        facts: ActivityAssetDescriptorFacts,
        *,
        recorded_at: datetime | None = None,
        origin: str | None = None,
    ) -> ActivityAssetHistory:
        """Append a descriptor; restating the current one is an exact replay and writes nothing."""
        if not any(revision.asset_id == asset_id for revision in self.revisions):
            raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.asset_not_found")
        current = self.current_descriptor(asset_id)
        if current is not None and current.facts == facts:
            return self
        facts.require_document_pair()
        descriptor = ActivityAssetDescriptor(
            asset_id=asset_id,
            descriptor_number=1 if current is None else current.descriptor_number + 1,
            facts=facts,
        )
        event = self._next_event(
            ActivityAssetEventKind.DESCRIPTOR,
            asset_id,
            descriptor.descriptor_id,
            recorded_at=recorded_at,
            origin=origin,
        )
        return self.model_copy_validated(descriptors=(*self.descriptors, descriptor), events=(*self.events, event))

    def model_copy_validated(
        self,
        *,
        revisions: tuple[ActivityAssetRevision, ...] | None = None,
        claims: tuple[AmortizationClaim, ...] | None = None,
        descriptors: tuple[ActivityAssetDescriptor, ...] | None = None,
        events: tuple[ActivityAssetHistoryEvent, ...] | None = None,
    ) -> ActivityAssetHistory:
        """Build the next document through the full history validation."""
        return ActivityAssetHistory(
            revisions=self.revisions if revisions is None else revisions,
            claims=self.claims if claims is None else claims,
            descriptors=self.descriptors if descriptors is None else descriptors,
            events=self.events if events is None else events,
        )

    def append_revision(
        self,
        revision: ActivityAssetRevision,
        *,
        recorded_at: datetime | None = None,
        origin: str | None = None,
    ) -> ActivityAssetHistory:
        """Append only a creation or the exact successor of the current revision.

        The encrypted repository invokes this against the value read inside its
        compare-and-swap mutation.  Checking the latest revision here therefore
        closes the pre-read/write race for corrections made by concurrent
        callers.
        """
        return self.apply_correction(revision, (), recorded_at=recorded_at, origin=origin)

    def apply_correction(
        self,
        revision: ActivityAssetRevision,
        superseding_claims: tuple[AmortizationClaim, ...],
        *,
        recorded_at: datetime | None = None,
        origin: str | None = None,
    ) -> ActivityAssetHistory:
        """Append a revision with the claims that replace what it invalidates, judged together.

        The basis check runs on the final state, so a correction below an effective
        claim is admitted exactly when the same write supersedes enough of them.
        Each new claim is judged against the years up to its own: a later standing
        claim was not recalculated by this correction, and the timeline reports it
        as no longer matching.
        """
        known = {item.claim_id for item in self.claims}
        if any(existing.revision_id == revision.revision_id for existing in self.revisions) and all(
            claim.claim_id in known for claim in superseding_claims
        ):
            return self
        self._require_successor(revision)
        claims = self.claims
        for claim in superseding_claims:
            claims = record_claim(claims, claim).claims
        logged = self._next_event(
            _revision_event_kind(revision, {item.revision_id: item for item in self.revisions}),
            revision.asset_id,
            revision.revision_id,
            recorded_at=recorded_at,
            origin=origin,
        )
        events = [logged]
        for claim in superseding_claims:
            events.append(
                ActivityAssetHistoryEvent(
                    sequence=events[-1].sequence + 1,
                    kind=ActivityAssetEventKind.CLAIM,
                    asset_id=claim.asset_id,
                    record_id=claim.claim_id,
                    recorded_at=recorded_at,
                    origin=origin,
                ),
            )
        candidate = self.model_copy_validated(
            revisions=(*self.revisions, revision),
            claims=claims,
            events=(*self.events, *events),
        )
        candidate._require_claims_within_basis(revision)
        candidate._require_claims_within_boundary(revision)
        for claim in superseding_claims:
            candidate._require_claim_invariants(
                claim,
                claims_through_year(claims, claim.tax_year),
            )
        return candidate

    def _require_successor(self, revision: ActivityAssetRevision) -> None:
        latest = current_revisions(self.revisions).get(revision.asset_id)
        if latest is None:
            if revision.revision_number != 1 or revision.supersedes_revision_id is not None:
                raise ActividadAssetValidationError(
                    translated_message="ledger.actividad_asset.errors.creation_requires_first_revision",
                )
        elif (
            revision.revision_number != latest.revision_number + 1
            or revision.supersedes_revision_id != latest.revision_id
        ):
            raise ActividadAssetClaimConflictError(
                translated_message="ledger.actividad_asset.errors.correction_must_supersede_current",
            )

    def _require_claims_within_basis(self, revision: ActivityAssetRevision) -> None:
        recorded = tuple(claim for claim in effective_claims(self.claims) if claim.asset_id == revision.asset_id)
        if not recorded:
            return
        opening = revision.opening_history.accumulated_amount
        if opening is None:
            raise ActividadAssetIncompleteError(
                translated_message="ledger.actividad_asset.errors.opening_history_missing",
            )
        for claim in recorded:
            require_claim_after_opening_year(revision, claim.tax_year)
        consumed = opening + sum((claim.amount for claim in recorded), Decimal("0"))
        if consumed > revision.amortizable_ceiling():
            raise ActividadAssetClaimConflictError(
                translated_message="ledger.actividad_asset.errors.correction_below_effective_claims",
            )

    def _require_claims_within_boundary(self, revision: ActivityAssetRevision) -> None:
        for claim in effective_claims(self.claims):
            if claim.asset_id == revision.asset_id:
                _require_claim_within_boundary(claim, revision)

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        recorded_at: datetime | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Record a claim through the domain replay/conflict contract.

        A new claim must also keep the asset's method continuity and stay
        within its remaining lawful basis.  The repository applies this inside
        its compare-and-swap mutation, so two forecasts taken against the same
        history can never both consume the same basis.
        """
        result = record_claim(self.claims, claim)
        if result.reused_existing_claim:
            return ActivityAssetHistoryClaimResult(history=self, claim=result.claim, reused_existing_claim=True)
        self._require_claim_invariants(claim, result.claims)
        event = self._next_event(
            ActivityAssetEventKind.CLAIM,
            claim.asset_id,
            claim.claim_id,
            recorded_at=recorded_at,
            origin=claim.creating_operation,
        )
        return ActivityAssetHistoryClaimResult(
            history=self.model_copy_validated(claims=result.claims, events=(*self.events, event)),
            claim=result.claim,
            reused_existing_claim=False,
        )

    def _require_claim_invariants(
        self,
        claim: AmortizationClaim,
        claims_after: tuple[AmortizationClaim, ...],
    ) -> None:
        revision = next((item for item in self.revisions if item.revision_id == claim.asset_revision_id), None)
        if revision is None:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.claim_revision_absent"
            )
        current = current_revisions(self.revisions)[claim.asset_id]
        if current.revision_id != revision.revision_id:
            raise ActividadAssetClaimConflictError(
                translated_message="ledger.actividad_asset.errors.claim_not_under_current_revision",
            )
        _require_claim_within_boundary(claim, current)
        summary = asset_schedule_history(
            claims_after,
            self.revisions,
            asset_id=claim.asset_id,
            tax_year=claim.tax_year,
        )
        election = revision.amortization
        require_method_continuity(election.method, election.fingerprint, summary)
        require_opening_method(revision, election.method)
        require_claim_after_opening_year(revision, claim.tax_year)
        opening = revision.opening_history.accumulated_amount
        if opening is None:
            raise ActividadAssetIncompleteError(
                translated_message="ledger.actividad_asset.errors.opening_history_missing",
            )
        consumed = (
            opening
            + summary.accumulated_before_tax_year
            + summary.accumulated_in_tax_year
            + summary.accumulated_after_tax_year
        )
        if consumed > revision.amortizable_ceiling():
            raise ActividadAssetClaimConflictError(
                translated_message="ledger.actividad_asset.errors.claims_exceed_amortizable_basis",
            )


def _revision_event_kind(
    revision: ActivityAssetRevision,
    revisions_by_id: dict[str, ActivityAssetRevision],
) -> ActivityAssetEventKind:
    """Name a revision a baja when it states a disposal its predecessor did not."""
    if revision.disposal is None:
        return ActivityAssetEventKind.REVISION
    previous = revisions_by_id.get(revision.supersedes_revision_id or "")
    if previous is not None and previous.disposal == revision.disposal:
        return ActivityAssetEventKind.REVISION
    return ActivityAssetEventKind.BAJA


def _require_claim_within_boundary(claim: AmortizationClaim, revision: ActivityAssetRevision) -> None:
    boundary = revision.out_of_service_date
    if boundary is not None and claim.amount > Decimal("0") and claim.covered_until > boundary:
        raise ActividadAssetClaimConflictError(
            context={
                "covered_until": claim.covered_until,
                "covered_through": last_day_covered(claim.covered_until),
                "boundary": boundary,
                "boundary_through": last_day_covered(boundary),
            },
            translated_message="ledger.actividad_asset.errors.disposal_claim_past_boundary",
        )


class ActivityAssetHistoryClaimResult(BaseModel):
    """Claim replay result paired with the history document it leaves behind."""

    model_config = STRICT_FROZEN_CONFIG

    history: ActivityAssetHistory
    claim: AmortizationClaim
    reused_existing_claim: bool


__all__ = ["ActivityAssetHistory", "ActivityAssetHistoryClaimResult"]
