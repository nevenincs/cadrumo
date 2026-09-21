"""Encrypted SQL persistence tests for append-only activity-asset history."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....domain.renta.actividad_asset.claims import AmortizationClaim, effective_claims
from .....domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
from .....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..actividad_asset import ActividadAssetHistoryRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _revision(
    *,
    asset_id: str = "asset-no-plaintext-secret",
    number: int = 1,
    supersedes_revision_id: str | None = None,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=number,
        supersedes_revision_id=supersedes_revision_id,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="invoice-no-plaintext-secret",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("1000"),
            prior_allocation_provenance="reviewed allocation source",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
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
        "source_reference": "authority-no-plaintext-secret",
        "creating_operation": "record-amortization",
    }
    payload.update(overrides)
    return AmortizationClaim.model_validate(payload)


def test_history_roundtrips_encrypted_revision_and_claim_history(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f16731f4-c0ca-4aa9-9b2d-53c2731ae121") as profile:
        initial = _revision()
        correction = _revision(number=2, supersedes_revision_id=initial.revision_id)
        repository = ActividadAssetHistoryRepository()
        repository.append_revision(initial)
        repository.append_revision(correction)
        original_claim = _claim(initial)
        corrected_claim = _claim(
            correction,
            amount=Decimal("99.99"),
            supersedes_claim_id=original_claim.claim_id,
        )
        repository.record_claim(original_claim)
        repository.record_claim(corrected_claim)

        reopened = ActividadAssetHistoryRepository().load()

        assert reopened.revisions == (initial, correction)
        assert reopened.claims == (original_claim, corrected_claim)
        assert effective_claims(reopened.claims) == (corrected_claim,)
        on_disk_bytes = b"".join(path.read_bytes() for path in profile.storage_root.rglob("*") if path.is_file())
        assert b"asset-no-plaintext-secret" not in on_disk_bytes
        assert b"authority-no-plaintext-secret" not in on_disk_bytes


def test_claim_replay_is_idempotent_and_conflict_leaves_encrypted_history_unchanged(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="d537d6da-1a8f-4897-8d03-f21ed219814c"):
        revision = _revision()
        repository = ActividadAssetHistoryRepository()
        repository.append_revision(revision)
        claim = _claim(revision)
        first = repository.record_claim(claim)
        replay = repository.record_claim(claim)

        assert first.reused_existing_claim is False
        assert replay.reused_existing_claim is True
        with pytest.raises(ActividadAssetClaimConflictError):
            repository.record_claim(_claim(revision, amount=Decimal("101.00")))
        assert repository.load().claims == (claim,)


def test_cas_retry_keeps_revisions_appended_by_independent_repositories(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="e96a5c0f-c7d7-44bd-a655-11b9aef1ff63"):
        repository = ActividadAssetHistoryRepository()
        interloper = ActividadAssetHistoryRepository()
        first = _revision(asset_id="asset-cas-first")
        second = _revision(asset_id="asset-cas-second")
        interloper_written = False

        def _append_while_an_independent_write_lands(history):
            nonlocal interloper_written
            if not interloper_written:
                interloper_written = True
                interloper.append_revision(second)
            return history.append_revision(first)

        repository._storage.mutate(_append_while_an_independent_write_lands)

        assert {revision.asset_id for revision in repository.load().revisions} == {
            "asset-cas-first",
            "asset-cas-second",
        }
