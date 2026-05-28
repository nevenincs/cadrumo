"""Tests for the evidence bundle service per apex ADR §4.3."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import APPLICATION_EVIDENCE_BUNDLE_NAMESPACE
from aeat.application.evidence import (
    BundleVerificationState,
    EvidenceBundleNotFoundError,
    EvidenceBundleService,
    EvidenceBundleVerificationError,
    EvidenceBundleVerificationReport,
    VerificationCheck,
)
from aeat.application.evidence._models import derive_bundle_id
from aeat.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runtime_profile(tmp_path: Path) -> TestRuntimeProfile:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-001") as profile:
        yield profile


@pytest.fixture
def payloads() -> dict[tuple[str, str], bytes]:
    return {
        ("calculation_revision", "rev-1"): b"casilla-01=1000.00\ncasilla-02=210.00\n",
        ("filing_record", "filing-1"): b"justificante: CSV12345\n",
    }


class TestBuild:
    def test_build_produces_content_addressed_bundle_id(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        bundle = svc.build(
            bucket_id=runtime_profile.bucket_id,
            work_unit_id="wu-100",
            record_payloads=payloads,
            calculation_revision_id="rev-1",
            filing_record_id="filing-1",
        )
        assert len(bundle.bundle_id) == 64  # sha256 hex
        assert bundle.bucket_id == "bucket-001"
        assert bundle.work_unit_id == "wu-100"
        assert len(bundle.records) == 2
        assert bundle.verification_state is BundleVerificationState.PENDING
        assert runtime_profile.repository.exists(
            APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.namespace,
            bundle.bundle_id,
        )

    def test_build_is_deterministic_for_same_inputs(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc1 = EvidenceBundleService(settings=runtime_profile.settings)
        bundle1 = svc1.build(
            bucket_id=runtime_profile.bucket_id,
            work_unit_id="wu-100",
            record_payloads=payloads,
        )
        # Fresh service, same payloads, same bucket: bundle_id should match.
        svc2 = EvidenceBundleService(settings=runtime_profile.settings)
        bundle2 = svc2.build(
            bucket_id=runtime_profile.bucket_id,
            work_unit_id="wu-100",
            record_payloads=payloads,
        )
        assert bundle1.bundle_id == bundle2.bundle_id


class TestShow:
    def test_show_resolves_by_full_or_prefix(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        full = svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=added.bundle_id)
        prefix = svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=added.bundle_id[:12])
        assert full == added
        assert prefix == added

    def test_show_refuses_on_unknown_id(self, runtime_profile: TestRuntimeProfile) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        with pytest.raises(EvidenceBundleNotFoundError):
            svc.show(bucket_id=runtime_profile.bucket_id, bundle_id="no-such-bundle")


class TestVerify:
    def test_check_passes_on_unmodified_payloads(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        report = svc.check(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=payloads,
        )
        assert report.verification_state is BundleVerificationState.VERIFIED
        assert all(f.passed for f in report.findings)
        assert report.completeness_ratio == 1.0

    def test_check_fails_on_modified_payload(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        tampered = dict(payloads)
        tampered[("calculation_revision", "rev-1")] = b"casilla-01=9999.99\n"
        report = svc.check(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=tampered,
        )
        assert report.verification_state is BundleVerificationState.FAILED
        digest_finding = next(f for f in report.findings if f.check is VerificationCheck.RECORD_DIGESTS)
        assert digest_finding.passed is False

    def test_check_reports_incomplete_when_records_missing(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        partial = {("calculation_revision", "rev-1"): payloads[("calculation_revision", "rev-1")]}
        report = svc.check(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=partial,
        )
        assert report.verification_state is BundleVerificationState.INCOMPLETE
        assert report.completeness_ratio == 0.5


class TestExport:
    def test_export_writes_manifest_last(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        archive_path = tmp_path / "bundle.zip"
        svc.export(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=payloads,
            output_path=archive_path,
        )
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
        # manifest.json must be the final entry
        assert names[-1] == "manifest.json"
        # both record files must be present
        assert "records/calculation_revision/rev-1.bin" in names
        assert "records/filing_record/filing-1.bin" in names

    def test_export_refuses_on_failed_verification(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        tampered = dict(payloads)
        tampered[("calculation_revision", "rev-1")] = b"tampered\n"
        with pytest.raises(EvidenceBundleVerificationError, match="verification failed"):
            svc.export(
                bucket_id=runtime_profile.bucket_id,
                bundle_id=added.bundle_id,
                record_payloads=tampered,
                output_path=tmp_path / "bundle.zip",
            )

    def test_export_refuses_incomplete_without_force(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        partial = {("calculation_revision", "rev-1"): payloads[("calculation_revision", "rev-1")]}
        with pytest.raises(EvidenceBundleVerificationError, match="--force-incomplete"):
            svc.export(
                bucket_id=runtime_profile.bucket_id,
                bundle_id=added.bundle_id,
                record_payloads=partial,
                output_path=tmp_path / "bundle.zip",
            )

    def test_export_accepts_incomplete_when_forced(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        partial = {("calculation_revision", "rev-1"): payloads[("calculation_revision", "rev-1")]}
        archive_path = tmp_path / "bundle.zip"
        result = svc.export(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=partial,
            output_path=archive_path,
            force_incomplete=True,
        )
        assert result == archive_path
        assert archive_path.exists()


class TestReplay:
    def test_replay_never_mutates_bundle_state(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id="wu-1", record_payloads=payloads)
        report = svc.replay(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=payloads,
        )
        assert isinstance(report, EvidenceBundleVerificationReport)
        assert report.verification_state is BundleVerificationState.VERIFIED
        # replay must not have mutated the persisted bundle
        reloaded = svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=added.bundle_id)
        assert reloaded == added


class TestBucketIsolation:
    def test_bundles_are_bucket_scoped(
        self,
        tmp_path: Path,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-A") as profile_a:
            service_a = EvidenceBundleService(settings=profile_a.settings)
            a_added = service_a.build(
                bucket_id=profile_a.bucket_id,
                work_unit_id="wu-A",
                record_payloads=payloads,
            )
            assert service_a.show(bucket_id=profile_a.bucket_id, bundle_id=a_added.bundle_id) == a_added

        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-B") as profile_b:
            service_b = EvidenceBundleService(settings=profile_b.settings)
            b_added = service_b.build(
                bucket_id=profile_b.bucket_id,
                work_unit_id="wu-B",
                record_payloads=payloads,
            )
            assert service_b.show(bucket_id=profile_b.bucket_id, bundle_id=b_added.bundle_id) == b_added
            with pytest.raises(EvidenceBundleNotFoundError):
                service_b.show(bucket_id=profile_b.bucket_id, bundle_id=a_added.bundle_id)


class TestDeriveBundleId:
    def test_derive_changes_when_record_digest_changes(self) -> None:
        from aeat.application.evidence._models import EvidenceRecordRef
        from aeat.domain.buckets._event import BucketEventObjectType

        rec_a = EvidenceRecordRef(
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id="rev-1",
            content_sha256="a" * 64,
            payload_size_bytes=10,
        )
        rec_b = EvidenceRecordRef(
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id="rev-1",
            content_sha256="b" * 64,
            payload_size_bytes=10,
        )
        id_a = derive_bundle_id(
            bucket_id="bucket-001",
            work_unit_id="wu-1",
            manifest_version=1,
            records=(rec_a,),
        )
        id_b = derive_bundle_id(
            bucket_id="bucket-001",
            work_unit_id="wu-1",
            manifest_version=1,
            records=(rec_b,),
        )
        assert id_a != id_b
