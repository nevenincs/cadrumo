"""Tests for the evidence bundle service."""

from __future__ import annotations

import hashlib
import zipfile
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.secure_object_namespaces import APPLICATION_EVIDENCE_BUNDLE_NAMESPACE
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._models import (
    BundleVerificationState,
    EvidenceBundle,
    EvidenceBundleNotFoundError,
    EvidenceBundleVerificationError,
    EvidenceRecordRef,
    VerificationCheck,
    derive_bundle_id,
)
from .._service import EvidenceBundleRepository, EvidenceBundleService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _hex64(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


WU_100 = _hex64("wu-100")
WU_A = _hex64("wu-A")
WU_B = _hex64("wu-B")
REV_1_ID = _hex64("rev-1")
FILING_1_ID = _hex64("filing-1")
_BUCKET_ID = "41e0c259-7c89-4c5f-9908-c5d44d8d77a8"
_BUCKET_A_ID = "2585593c-dcdb-4af7-8c1a-4852593c2d4e"
_BUCKET_B_ID = "e46b34f4-5d44-49da-97f8-830ec116d038"
_WORK_UNIT_CREATED_AT = datetime(2026, 8, 1, tzinfo=UTC)
_WORK_UNIT_PERIOD = Period.from_year_and_code(2026, "0A")
_WORK_UNIT_REVISION_ID = "r" + "0" * 63
WU_1 = derive_work_unit_id(
    bucket_id=_BUCKET_ID,
    modelo="100",
    filing_year=2026,
    period=_WORK_UNIT_PERIOD,
    revision_id=_WORK_UNIT_REVISION_ID,
)


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Generator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        WorkUnitCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository).save(
            WorkUnitCatalogue(
                work_units={
                    WU_1: WorkUnit(
                        work_unit_id=WU_1,
                        bucket_id=profile.bucket_id,
                        modelo=ModeloCode("100"),
                        filing_year=2026,
                        period=_WORK_UNIT_PERIOD,
                        revision_id=_WORK_UNIT_REVISION_ID,
                        name="100-2026-0A",
                        created_at=_WORK_UNIT_CREATED_AT,
                        updated_at=_WORK_UNIT_CREATED_AT,
                    ),
                },
            ),
        )
        yield profile


@pytest.fixture
def payloads() -> dict[tuple[str, str], bytes]:
    return {
        ("calculation_revision", "rev-1"): b"casilla-01=1000.00\ncasilla-02=210.00\n",
        ("filing_record", "filing-1"): b"justificante: CSV12345\n",
    }


def _raw_bundle(
    *,
    bundle_id: str,
    bucket_id: str,
    work_unit_id: str,
    records: tuple[EvidenceRecordRef, ...] = (),
) -> EvidenceBundle:
    """Build an :class:`EvidenceBundle` model directly, bypassing ``build()``.

    Lets a test stamp an arbitrary ``bundle_id`` (for a controlled prefix
    collision) or an arbitrary ``bucket_id`` (a manifest claiming a
    different bucket than the one it is physically persisted through) —
    a shape ``build()`` itself can never produce, but which the storage
    layer does not otherwise forbid.
    """
    return EvidenceBundle(
        bundle_id=bundle_id,
        manifest_version=1,
        bucket_id=bucket_id,
        work_unit_id=work_unit_id,
        records=records,
        verification_state=BundleVerificationState.PENDING,
        completeness_ratio=1.0,
        created_at=_WORK_UNIT_CREATED_AT,
    )


def _secure_object_fingerprint(
    runtime_profile: TestRuntimeProfile,
) -> tuple[tuple[str, bytes, str | None, str | None], ...]:
    return tuple(
        (row.namespace, row.object_key, row.revision_id, row.ciphertext_hash)
        for row in runtime_profile.repository.iter_all_records_raw()
    )


class TestBuild:
    def test_build_produces_content_addressed_bundle_id(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        bundle = svc.build(
            bucket_id=runtime_profile.bucket_id,
            work_unit_id=WU_100,
            record_payloads=payloads,
            calculation_revision_id=REV_1_ID,
            filing_record_id=FILING_1_ID,
        )
        assert len(bundle.bundle_id) == 64  # sha256 hex
        assert bundle.bucket_id == _BUCKET_ID
        assert bundle.work_unit_id == WU_100
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
            work_unit_id=WU_100,
            record_payloads=payloads,
        )
        # Fresh service, same payloads, same bucket: bundle_id should match.
        svc2 = EvidenceBundleService(settings=runtime_profile.settings)
        bundle2 = svc2.build(
            bucket_id=runtime_profile.bucket_id,
            work_unit_id=WU_100,
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
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
        full = svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=added.bundle_id)
        prefix = svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=added.bundle_id[:12])
        assert full == added
        assert prefix == added

    def test_show_refuses_on_unknown_id(self, runtime_profile: TestRuntimeProfile) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        with pytest.raises(EvidenceBundleNotFoundError) as excinfo:
            svc.show(bucket_id=runtime_profile.bucket_id, bundle_id="no-such-bundle")

        assert excinfo.value.translated_message == "errors.refused.refused_evidence_bundle_not_found"
        assert excinfo.value.context == {"bundle_id": "no-such-bundle", "bucket_id": runtime_profile.bucket_id}

    def test_show_refuses_an_ambiguous_prefix(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        repository = EvidenceBundleRepository(objects=runtime_profile.repository)
        shared_prefix = "ab"
        first = _raw_bundle(bundle_id=shared_prefix + "1" * 62, bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1)
        second = _raw_bundle(bundle_id=shared_prefix + "2" * 62, bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1)
        repository.save(first)
        repository.save(second)

        svc = EvidenceBundleService(settings=runtime_profile.settings)
        with pytest.raises(EvidenceBundleNotFoundError) as excinfo:
            svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=shared_prefix)

        assert excinfo.value.translated_message == "errors.refused.refused_evidence_bundle_ambiguous"
        assert excinfo.value.context is not None
        assert excinfo.value.context["match_count"] == 2

        # An unambiguous, longer prefix still resolves cleanly.
        resolved = svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=first.bundle_id[:10])
        assert resolved.bundle_id == first.bundle_id


class TestForeignBucketManifest:
    def test_show_never_returns_a_manifest_claiming_a_different_bucket(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        # A bundle physically persisted through bucket A's repository but
        # whose own manifest claims bucket B - the shape a corrupted or
        # misrouted write would produce.
        repository = EvidenceBundleRepository(objects=runtime_profile.repository)
        foreign = _raw_bundle(bundle_id="c" * 64, bucket_id=_BUCKET_B_ID, work_unit_id=WU_1)
        repository.save(foreign)

        svc = EvidenceBundleService(settings=runtime_profile.settings)
        with pytest.raises(EvidenceBundleNotFoundError):
            svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=foreign.bundle_id)
        with pytest.raises(EvidenceBundleNotFoundError):
            svc.show(bucket_id=runtime_profile.bucket_id, bundle_id=foreign.bundle_id[:10])


class TestVerify:
    def test_check_passes_on_unmodified_payloads(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
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
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
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
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
        partial = {("calculation_revision", "rev-1"): payloads[("calculation_revision", "rev-1")]}
        report = svc.check(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=partial,
        )
        assert report.verification_state is BundleVerificationState.INCOMPLETE
        # Byte-weighted, not record-count-based: the reached record's own
        # byte share of the manifest's total payload bytes.
        reachable_bytes = len(payloads[("calculation_revision", "rev-1")])
        total_bytes = sum(len(payload) for payload in payloads.values())
        assert report.completeness_ratio == pytest.approx(reachable_bytes / total_bytes)

    def test_completeness_ratio_is_weighted_by_payload_bytes_not_record_count(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        # A 90-byte record and a 10-byte record: reaching only the small one
        # is 1-of-2 records (a count-based ratio of 0.5) but only 10/100 of
        # the documented byte-weighted completeness.
        skewed_payloads = {
            ("calculation_revision", "rev-1"): b"x" * 90,
            ("filing_record", "filing-1"): b"y" * 10,
        }
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=skewed_payloads)

        only_small = {("filing_record", "filing-1"): skewed_payloads[("filing_record", "filing-1")]}
        report_small = svc.check(
            bucket_id=runtime_profile.bucket_id, bundle_id=added.bundle_id, record_payloads=only_small
        )
        assert report_small.completeness_ratio == pytest.approx(0.1)

        only_large = {("calculation_revision", "rev-1"): skewed_payloads[("calculation_revision", "rev-1")]}
        report_large = svc.check(
            bucket_id=runtime_profile.bucket_id, bundle_id=added.bundle_id, record_payloads=only_large
        )
        assert report_large.completeness_ratio == pytest.approx(0.9)

    def test_check_fails_when_manifest_work_unit_is_not_persisted(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(
            bucket_id=runtime_profile.bucket_id,
            work_unit_id=WU_100,
            record_payloads=payloads,
        )

        report = svc.check(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=payloads,
        )

        assert report.verification_state is BundleVerificationState.FAILED
        work_unit_finding = next(f for f in report.findings if f.check is VerificationCheck.WORK_UNIT_BINDING)
        assert work_unit_finding.passed is False


class TestExport:
    def test_export_writes_manifest_last(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
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
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
        tampered = dict(payloads)
        tampered[("calculation_revision", "rev-1")] = b"tampered\n"
        with pytest.raises(EvidenceBundleVerificationError) as excinfo:
            svc.export(
                bucket_id=runtime_profile.bucket_id,
                bundle_id=added.bundle_id,
                record_payloads=tampered,
                output_path=tmp_path / "bundle.zip",
            )

        assert excinfo.value.translated_message == "errors.refused.refused_evidence_bundle_verification"
        assert excinfo.value.context == {
            "bundle_id": added.bundle_id,
            "verification_state": BundleVerificationState.FAILED.value,
        }

    def test_export_refuses_incomplete_without_force(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
        partial = {("calculation_revision", "rev-1"): payloads[("calculation_revision", "rev-1")]}
        with pytest.raises(EvidenceBundleVerificationError) as excinfo:
            svc.export(
                bucket_id=runtime_profile.bucket_id,
                bundle_id=added.bundle_id,
                record_payloads=partial,
                output_path=tmp_path / "bundle.zip",
            )

        assert excinfo.value.translated_message == "errors.refused.refused_evidence_bundle_verification"
        assert excinfo.value.context == {
            "bundle_id": added.bundle_id,
            "verification_state": BundleVerificationState.INCOMPLETE.value,
            "force_incomplete": False,
        }

    def test_export_accepts_incomplete_when_forced(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
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

    def test_export_is_operator_directed_and_does_not_mutate_secure_catalogue(
        self,
        runtime_profile: TestRuntimeProfile,
        payloads: dict[tuple[str, str], bytes],
        tmp_path: Path,
    ) -> None:
        svc = EvidenceBundleService(settings=runtime_profile.settings)
        added = svc.build(bucket_id=runtime_profile.bucket_id, work_unit_id=WU_1, record_payloads=payloads)
        before_export = _secure_object_fingerprint(runtime_profile)
        archive_path = tmp_path / "operator-export" / "bundle.zip"

        result = svc.export(
            bucket_id=runtime_profile.bucket_id,
            bundle_id=added.bundle_id,
            record_payloads=payloads,
            output_path=archive_path,
        )

        assert result == archive_path
        assert archive_path.exists()
        assert not archive_path.is_relative_to(runtime_profile.storage_root)
        assert _secure_object_fingerprint(runtime_profile) == before_export


class TestBucketIsolation:
    def test_bundles_are_bucket_scoped(
        self,
        tmp_path: Path,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A_ID) as profile_a:
            service_a = EvidenceBundleService(settings=profile_a.settings)
            a_added = service_a.build(
                bucket_id=profile_a.bucket_id,
                work_unit_id=WU_A,
                record_payloads=payloads,
            )
            assert service_a.show(bucket_id=profile_a.bucket_id, bundle_id=a_added.bundle_id) == a_added

        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_B_ID) as profile_b:
            service_b = EvidenceBundleService(settings=profile_b.settings)
            b_added = service_b.build(
                bucket_id=profile_b.bucket_id,
                work_unit_id=WU_B,
                record_payloads=payloads,
            )
            assert service_b.show(bucket_id=profile_b.bucket_id, bundle_id=b_added.bundle_id) == b_added
            with pytest.raises(EvidenceBundleNotFoundError) as excinfo:
                service_b.show(bucket_id=profile_b.bucket_id, bundle_id=a_added.bundle_id)

            assert excinfo.value.translated_message == "errors.refused.refused_evidence_bundle_not_found"
            assert excinfo.value.context == {"bundle_id": a_added.bundle_id, "bucket_id": profile_b.bucket_id}


class TestDeriveBundleId:
    def test_derive_changes_when_record_digest_changes(self) -> None:
        from ....domain.buckets.event import BucketEventObjectType
        from .._models import EvidenceRecordRef

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
            bucket_id=_BUCKET_ID,
            work_unit_id=WU_1,
            manifest_version=1,
            records=(rec_a,),
        )
        id_b = derive_bundle_id(
            bucket_id=_BUCKET_ID,
            work_unit_id=WU_1,
            manifest_version=1,
            records=(rec_b,),
        )
        assert id_a != id_b
