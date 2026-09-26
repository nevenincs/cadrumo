"""Encrypted SQL persistence tests for append-only activity-asset history."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.actividad_asset.history import ActivityAssetHistory
from .....domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    effective_claims,
    effective_free_depreciation_claims,
)
from .....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
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
        "source_reference": "authority-no-plaintext-secret",
        "creating_operation": "record-amortization",
    }
    payload.update(overrides)
    return AmortizationClaim.model_validate(payload)


def _free_claim(revision: ActivityAssetRevision, **overrides: object) -> AmortizationClaim:
    free_fields: dict[str, object] = {
        "amount": Decimal("300.00"),
        "method": AmortizationMethod.LOW_VALUE_FREE,
        "free_depreciation_election_reference": f"election-{revision.asset_id}",
        "free_depreciation_new_material_evidence_reference": f"new-material-{revision.asset_id}",
        "free_depreciation_unit_acquisition_value": Decimal("300.00"),
        "free_depreciation_annual_cap": Decimal("500.00"),
    }
    free_fields.update(overrides)
    return _claim(revision, **free_fields)


def test_history_roundtrips_encrypted_revision_and_claim_history(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f16731f4-c0ca-4aa9-9b2d-53c2731ae121") as profile:
        initial = _revision()
        correction = _revision(number=2, supersedes_revision_id=initial.revision_id)
        repository = ActividadAssetHistoryRepository()
        original_claim = _claim(initial)
        corrected_claim = _claim(
            correction,
            amount=Decimal("99.99"),
            supersedes_claim_id=original_claim.claim_id,
        )
        repository.append_revision(initial)
        repository.record_claim(original_claim)
        repository.append_revision(correction)
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


def test_cas_rechecks_effective_free_depreciation_cap_after_an_independent_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A forecast cannot bypass the taxpayer-period cap by racing another claim."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="70dc4d0b-56b5-4fd5-aaee-23d307738b06"):
        repository = ActividadAssetHistoryRepository()
        interloper = ActividadAssetHistoryRepository()
        first_revision = _revision(asset_id="free-cap-first")
        second_revision = _revision(asset_id="free-cap-second")
        repository.append_revision(first_revision)
        repository.append_revision(second_revision)
        first = _free_claim(first_revision)
        second = _free_claim(second_revision)
        original_mutate = repository._storage.mutate
        interloper_written = False

        def mutate_after_interloper(
            mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory],
            *,
            attempts: int = 4,
        ) -> ActivityAssetHistory:
            nonlocal interloper_written
            if not interloper_written:
                interloper_written = True
                interloper.record_claim(second)
            return original_mutate(mutation, attempts=attempts)

        monkeypatch.setattr(repository._storage, "mutate", mutate_after_interloper)

        with pytest.raises(ActividadAssetClaimConflictError, match="annual cap"):
            repository.record_claim(first)

        reopened = repository.load()
        assert effective_free_depreciation_claims(reopened.claims, tax_year=2025) == (second,)


def test_cas_rechecks_the_remaining_basis_after_an_independent_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two claims validated against the same history cannot both consume one basis."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="3c9d1f0e-5a2b-4f7c-8e6d-1b2a3c4d5e6f"):
        repository = ActividadAssetHistoryRepository()
        interloper = ActividadAssetHistoryRepository()
        revision = _revision(asset_id="basis-race")
        repository.append_revision(revision)
        first_quarter = _claim(revision, amount=Decimal("600.00"))
        second_quarter = _claim(
            revision,
            covered_from=date(2025, 4, 1),
            covered_until=date(2025, 7, 1),
            amount=Decimal("600.00"),
        )
        original_mutate = repository._storage.mutate
        interloper_written = False

        def mutate_after_interloper(
            mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory],
            *,
            attempts: int = 4,
        ) -> ActivityAssetHistory:
            nonlocal interloper_written
            if not interloper_written:
                interloper_written = True
                interloper.record_claim(first_quarter)
            return original_mutate(mutation, attempts=attempts)

        monkeypatch.setattr(repository._storage, "mutate", mutate_after_interloper)

        # 600 + 600 would reach 1,200 of a 1,000 amortizable basis.
        with pytest.raises(ActividadAssetClaimConflictError, match="lawful amortizable basis"):
            repository.record_claim(second_quarter)

        reopened = repository.load()
        assert effective_claims(reopened.claims) == (first_quarter,)
