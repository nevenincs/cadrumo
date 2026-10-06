"""Refusal boundaries for immutable review evidence and publication identities."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ..managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ..publication_receipt import PublicationFailure, PublicationReceipt, PublicationState
from ..review_snapshot import (
    CalculationReviewSelection,
    EvidenceDisposition,
    EvidenceInventoryItem,
    LedgerReviewSelection,
    ReviewAmount,
    ReviewContribution,
    ReviewSnapshot,
    ReviewSnapshotContent,
    ReviewSourceKind,
    ReviewStatus,
    seal_review_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID(int=1)
_PUBLICATION = UUID(int=2)


def _root() -> ArtifactCreationReceipt:
    return ArtifactCreationReceipt(
        profile_id=_PROFILE,
        root_folder_id="root",
        artifact_id="root",
        creation_id=UUID(int=3),
        kind=ManagedArtifactKind.ROOT,
    )


def _child(*, profile_id: UUID = _PROFILE) -> ArtifactCreationReceipt:
    return ArtifactCreationReceipt(
        profile_id=profile_id,
        root_folder_id="root",
        artifact_id="sheet",
        parent_id="root",
        creation_id=UUID(int=4),
        kind=ManagedArtifactKind.REVIEW_SHEET,
        publication_id=_PUBLICATION,
    )


def _publication() -> PublicationReceipt:
    return PublicationReceipt(publication_id=_PUBLICATION, profile_id=_PROFILE, root=_root(), snapshot_digest="a" * 64)


def _selection() -> CalculationReviewSelection:
    return CalculationReviewSelection(
        profile_id=_PROFILE,
        work_unit_id="a" * 64,
        calculation_revision_id="b" * 64,
        modelo="303",
        filing_year=2026,
        period="1T",
        registry_snapshot_ref=RegistrySnapshotRef(modelo="303", revision_id="2026", modelo_year=2026, period="1T"),
        authority_generation="c" * 64,
        registry_digest="d" * 64,
    )


def _amount() -> ReviewAmount:
    return ReviewAmount(
        amount_id="amount-01",
        casilla_id="01",
        value=Decimal("10.25"),
        unit="EUR",
        currency="EUR",
        rounding="0.01 HALF_UP",
        contribution_ids=("manual-1",),
    )


def test_snapshot_roundtrip_and_tampered_amount_digest_refusal() -> None:
    content = ReviewSnapshotContent(
        selection=_selection(),
        status=ReviewStatus.PROVISIONAL,
        amounts=(_amount(),),
        contributions=(
            ReviewContribution(
                contribution_id="manual-1",
                kind=ReviewSourceKind.MANUAL_INPUT,
                source_id="fact-1",
                source_revision="r1",
            ),
        ),
    )
    snapshot = seal_review_snapshot(content)
    assert ReviewSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    changed = json.loads(snapshot.model_dump_json())
    changed["amounts"][0]["value"] = "999.00"
    with pytest.raises(ValidationError, match="digest"):
        ReviewSnapshot.model_validate_json(json.dumps(changed))


def test_ledger_selection_has_no_calculation_and_refuses_invented_amounts() -> None:
    selection = LedgerReviewSelection(profile_id=_PROFILE, ledger_snapshot_id="e" * 64)
    snapshot = seal_review_snapshot(ReviewSnapshotContent(selection=selection, status=ReviewStatus.PROVISIONAL))
    assert "calculation_revision_id" not in snapshot.selection.model_dump()
    with pytest.raises(ValidationError, match="ledger-only"):
        ReviewSnapshotContent(selection=selection, status=ReviewStatus.PROVISIONAL, amounts=(_amount(),))


def test_amount_cannot_claim_missing_attribution() -> None:
    with pytest.raises(ValidationError, match="missing contribution"):
        ReviewSnapshotContent(selection=_selection(), status=ReviewStatus.PROVISIONAL, amounts=(_amount(),))


def test_missing_evidence_requires_reason_and_prevents_verified_status() -> None:
    with pytest.raises(ValidationError, match="reason"):
        EvidenceInventoryItem(evidence_id="attachment", source_revision="r1", disposition=EvidenceDisposition.MISSING)
    missing = EvidenceInventoryItem(
        evidence_id="attachment", source_revision="r1", disposition=EvidenceDisposition.MISSING, reason="not captured"
    )
    with pytest.raises(ValidationError, match="verified"):
        ReviewSnapshotContent(selection=_selection(), status=ReviewStatus.VERIFIED, evidence=(missing,))


def test_publication_requires_ordered_verification_and_is_terminal_after_publish() -> None:
    prepared = _publication()
    with pytest.raises(ValueError, match="skipped"):
        prepared.advance(PublicationState.PUBLISHED, artifacts=(_child(),))
    current = prepared.advance(PublicationState.REMOTE_CREATED, artifacts=(_child(),))
    current = current.advance(PublicationState.POPULATED)
    current = current.advance(PublicationState.VERIFIED)
    current = current.advance(PublicationState.PUBLISHED)
    with pytest.raises(ValueError, match="terminal"):
        current.advance(PublicationState.REMOTE_CREATED)


def test_unknown_create_cannot_be_blindly_replayed() -> None:
    uncertain = _publication().advance(PublicationState.UNCERTAIN, failure=PublicationFailure.CREATE_UNKNOWN)
    assert uncertain.artifacts == ()
    with pytest.raises(ValueError, match="reconciliation"):
        uncertain.advance(PublicationState.REMOTE_CREATED, artifacts=(_child(),))


def test_publication_refuses_another_profiles_artifact() -> None:
    with pytest.raises(ValidationError, match="artifact identity"):
        _publication().advance(PublicationState.REMOTE_CREATED, artifacts=(_child(profile_id=UUID(int=5)),))


def test_root_cannot_claim_external_ancestry() -> None:
    with pytest.raises(ValidationError, match="root creation identity"):
        ArtifactCreationReceipt.model_validate({**_root().model_dump(), "parent_id": "outside"})
