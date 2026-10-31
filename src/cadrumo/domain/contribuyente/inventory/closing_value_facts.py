"""Build a closing-authority record from the facts an operator actually knows.

A record binds its parts by fingerprints derived from canonical content. An operator
states the value, the method and the documents; every fingerprint is derived here
through the record's own owners, so no caller holds a second hash route.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from .closing_authority_records import (
    InventoryClosingAuthorityDecision,
    InventoryClosingAuthorityRecord,
    PriorAuthoritativeClosingLink,
)
from .closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingValuationBasis,
    InventoryValidationError,
    PhysicalClosingEvidence,
    PhysicalClosingObservation,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
    fingerprint_prior_closing_source,
)
from .records import InventoryLedger, InventoryLedgerDocument
from .valuation import derive_inventory_authoritative_closing_value


@dataclass(frozen=True, slots=True)
class InventoryPhysicalCountFacts:
    """What a year-end count found, and the documents that show it."""

    observed_on: date
    closing_value: Decimal
    valuation_basis: InventoryClosingValuationBasis
    evidence: tuple[PhysicalClosingEvidence, ...]


@dataclass(frozen=True, slots=True)
class InventoryClosingValueFacts:
    """The plain facts of one closing value; ``decision_id`` makes a resubmission an exact replay."""

    decision_id: str
    actividad_id: str
    year: int
    authority: InventoryClosingAuthority
    reason: str
    decision_evidence: tuple[InventoryClosingDecisionEvidence, ...]
    physical_count: InventoryPhysicalCountFacts | None = None
    prior_evidence: tuple[PriorClosingContinuityEvidence, ...] = ()


def _physical_observation(facts: InventoryClosingValueFacts) -> PhysicalClosingObservation | None:
    count = facts.physical_count
    if count is None:
        return None
    return PhysicalClosingObservation(
        observation_id=f"count-{facts.decision_id}",
        observed_on=count.observed_on,
        as_of_date=date(facts.year, 12, 31),
        actividad_id=facts.actividad_id,
        filing_year=facts.year,
        closing_value=count.closing_value,
        valuation_basis=count.valuation_basis,
        evidence=count.evidence,
    )


def _find_ledger(document: InventoryLedgerDocument, actividad_id: str, year: int) -> InventoryLedger | None:
    return next(
        (item for item in document.ledgers if item.actividad_id == actividad_id and item.year == year),
        None,
    )


def _prior_closing_link(
    facts: InventoryClosingValueFacts,
    *,
    ledger: InventoryLedger,
    prior_ledger: InventoryLedger | None,
) -> PriorAuthoritativeClosingLink:
    """Link the opening to the closed prior book, or to the documents that show that closing."""
    record = None if prior_ledger is None else prior_ledger.closing_authority_record
    prior_year = facts.year - 1
    if prior_ledger is not None and record is not None:
        prior_value = derive_inventory_authoritative_closing_value(prior_ledger)
        evidence = facts.prior_evidence or tuple(
            PriorClosingContinuityEvidence(reference=item.reference, content_digest=item.content_digest)
            for item in record.decision.evidence
        )
        source = record.fingerprint
    else:
        if not facts.prior_evidence:
            raise InventoryValidationError("an opening with no closed prior book needs a document that shows it")
        prior_value = ledger.opening_stock
        evidence = facts.prior_evidence
        source = fingerprint_prior_closing_source(
            actividad_id=facts.actividad_id,
            filing_year=prior_year,
            evidence=evidence,
        )
    return PriorAuthoritativeClosingLink(
        actividad_id=facts.actividad_id,
        current_filing_year=facts.year,
        prior_filing_year=prior_year,
        prior_authoritative_closing_value=prior_value,
        current_opening_value=ledger.opening_stock,
        prior_authoritative_source_fingerprint=source,
        prior_authoritative_closing_fingerprint=fingerprint_prior_authoritative_closing(
            actividad_id=facts.actividad_id,
            filing_year=prior_year,
            authoritative_closing_value=prior_value,
            authoritative_source_fingerprint=source,
            evidence=evidence,
        ),
        evidence=evidence,
    )


def _decision_instant(facts: InventoryClosingValueFacts, *, ledger: InventoryLedger, now: datetime) -> datetime:
    """Keep the instant of a decision already on the book, so resubmitting it is an exact replay."""
    record = ledger.closing_authority_record
    if record is not None and record.decision.decision_id == facts.decision_id:
        return record.decision.decided_at
    return now


def build_closing_authority_record(
    facts: InventoryClosingValueFacts,
    *,
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    actor: str,
    source_command: str,
    now: datetime,
) -> InventoryClosingAuthorityRecord:
    """Derive the complete record of one closing value; the record's validators stay the only judges."""
    observation = _physical_observation(facts)
    return InventoryClosingAuthorityRecord(
        decision=InventoryClosingAuthorityDecision(
            decision_id=facts.decision_id,
            actividad_id=facts.actividad_id,
            filing_year=facts.year,
            authority=facts.authority,
            physical_observation_id=None if observation is None else observation.observation_id,
            physical_observation_fingerprint=None if observation is None else observation.fingerprint,
            reason=facts.reason,
            actor=actor,
            source_command=source_command,
            decided_at=_decision_instant(facts, ledger=ledger, now=now),
            evidence=facts.decision_evidence,
        ),
        physical_observation=observation,
        prior_closing_link=_prior_closing_link(
            facts,
            ledger=ledger,
            prior_ledger=_find_ledger(document, facts.actividad_id, facts.year - 1),
        ),
    )


__all__ = [
    "InventoryClosingValueFacts",
    "InventoryPhysicalCountFacts",
    "build_closing_authority_record",
]
