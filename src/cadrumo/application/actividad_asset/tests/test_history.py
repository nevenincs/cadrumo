"""Append-only application-history contracts for activity assets."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.renta.actividad_asset.claims import AmortizationClaim, effective_claims
from ....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ....domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
from ....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ..history import ActivityAssetHistory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _revision(*, number: int = 1, supersedes_revision_id: str | None = None) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="asset-history-test",
        revision_number=number,
        supersedes_revision_id=supersedes_revision_id,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="invoice-history-test",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("1000"),
            prior_allocation_provenance="reviewed allocation record",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-proceso-informacion",
        ),
    )


def _claim(revision: ActivityAssetRevision, **overrides: object) -> AmortizationClaim:
    payload: dict[str, object] = {
        "asset_id": revision.asset_id,
        "asset_revision_id": revision.revision_id,
        "asset_kind": revision.asset_kind,
        "tax_year": 2025,
        "covered_from": date(2025, 1, 1),
        "covered_until": date(2025, 4, 1),
        "amount": Decimal("100.00"),
        "schedule_fingerprint": "c" * 64,
        "authority_generation": "2025.1",
        "source_reference": "authority-test",
        "creating_operation": "record-amortization",
    }
    payload.update(overrides)
    return AmortizationClaim.model_validate(payload)


def test_history_preserves_revision_and_claim_supersession_trails() -> None:
    initial = _revision()
    correction = _revision(number=2, supersedes_revision_id=initial.revision_id)
    original_claim = _claim(initial)
    amended_claim = _claim(
        correction,
        amount=Decimal("99.99"),
        supersedes_claim_id=original_claim.claim_id,
    )

    history = ActivityAssetHistory().append_revision(initial).record_claim(original_claim).history
    recorded = history.append_revision(correction).record_claim(amended_claim)

    assert tuple(revision.revision_id for revision in recorded.history.revisions) == (
        initial.revision_id,
        correction.revision_id,
    )
    assert effective_claims(recorded.history.claims) == (amended_claim,)


def test_history_exact_claim_retry_is_a_noop_and_conflicts_preserve_history() -> None:
    revision = _revision()
    history = ActivityAssetHistory().append_revision(revision)
    claim = _claim(revision)
    written = history.record_claim(claim)
    replay = written.history.record_claim(claim)

    assert replay.reused_existing_claim is True
    assert replay.history == written.history
    with pytest.raises(ActividadAssetClaimConflictError):
        written.history.record_claim(_claim(revision, amount=Decimal("101.00")))
    assert written.history.claims == (claim,)


def test_reopen_refuses_claim_with_kind_different_from_referenced_revision() -> None:
    revision = _revision()

    with pytest.raises(ValueError, match="kind does not match"):
        ActivityAssetHistory(
            revisions=(revision,),
            claims=(_claim(revision, asset_kind=AssetKind.INTANGIBLE),),
        )


def test_reopen_replays_claims_and_refuses_malformed_overlap_or_supersession() -> None:
    revision = _revision()
    first = _claim(revision)
    overlapping = _claim(
        revision,
        covered_from=date(2025, 3, 1),
        covered_until=date(2025, 5, 1),
    )
    missing_superseded_claim = _claim(revision, supersedes_claim_id="d" * 64)

    with pytest.raises(ValidationError, match="overlapping"):
        ActivityAssetHistory(revisions=(revision,), claims=(first, overlapping))
    with pytest.raises(ValidationError, match="absent"):
        ActivityAssetHistory(revisions=(revision,), claims=(missing_superseded_claim,))
