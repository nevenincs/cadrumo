"""Tests for the bucket-scoped verify audit service."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import LIVE_VERIFY_OBSERVATION_NAMESPACE
from aeat.application.live._verify import (
    VerifyObservationNotFoundError,
    VerifyService,
    VerifySurface,
    verify_observation_object_key,
)
from aeat.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile


def _service(profile: TestRuntimeProfile) -> VerifyService:
    return VerifyService(settings=profile.settings)


class TestRecord:
    def test_record_persists_observation(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        obs = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE123456789",
            verdict="valid",
            checked_at=datetime(2025, 3, 15, 10, 0, tzinfo=UTC),
        )
        assert len(obs.observation_id) == 64
        assert obs.surface is VerifySurface.NIF_IVA
        assert obs.nif == "DE123456789"
        assert obs.verdict == "valid"
        assert obs.expected is None
        assert obs.matched_expectation is None

    def test_record_with_expected_sets_match_flag(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        match = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            expected="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        miss = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE2",
            verdict="invalid",
            expected="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        assert match.matched_expectation is True
        assert miss.matched_expectation is False

    def test_record_deduplicates_identical_observation(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        ts = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
        a = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        b = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        assert a.observation_id == b.observation_id
        assert len(svc.list_observations(bucket_id=secure_engine.bucket_id)) == 1

    def test_record_distinct_verdict_at_same_timestamp_yields_distinct_id(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        ts = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
        a = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        b = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="invalid",
            checked_at=ts,
        )
        assert a.observation_id != b.observation_id


class TestListObservations:
    def test_list_returns_all_observations(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.TGVI,
            nif="ES1",
            verdict="valid",
            checked_at=ts,
        )
        all_obs = svc.list_observations(bucket_id=secure_engine.bucket_id)
        assert len(all_obs) == 2

    def test_list_filters_by_surface(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.TGVI,
            nif="ES1",
            verdict="valid",
            checked_at=ts,
        )
        nif_iva_obs = svc.list_observations(bucket_id=secure_engine.bucket_id, surface=VerifySurface.NIF_IVA)
        tgvi_obs = svc.list_observations(bucket_id=secure_engine.bucket_id, surface=VerifySurface.TGVI)
        assert len(nif_iva_obs) == 1
        assert len(tgvi_obs) == 1
        assert nif_iva_obs[0].surface is VerifySurface.NIF_IVA
        assert tgvi_obs[0].surface is VerifySurface.TGVI

    def test_list_filters_by_nif(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE2",
            verdict="invalid",
            checked_at=ts,
        )
        de1_obs = svc.list_observations(bucket_id=secure_engine.bucket_id, nif="DE1")
        assert len(de1_obs) == 1
        assert de1_obs[0].nif == "DE1"


class TestShow:
    def test_show_resolves_full_and_prefix(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        obs = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        full = svc.show(bucket_id=secure_engine.bucket_id, observation_id=obs.observation_id)
        prefix = svc.show(bucket_id=secure_engine.bucket_id, observation_id=obs.observation_id[:8])
        assert full == obs
        assert prefix == obs

    def test_show_refuses_unknown_id(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        with pytest.raises(VerifyObservationNotFoundError, match="no verify observation"):
            svc.show(bucket_id=secure_engine.bucket_id, observation_id="0" * 64)


class TestLatestForNif:
    def test_latest_returns_most_recent_for_pair(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        older = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        newer = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="invalid",
            checked_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        latest = svc.latest_for_nif(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
        )
        assert latest == newer
        assert latest != older

    def test_latest_returns_none_when_no_observations(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        result = svc.latest_for_nif(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
        )
        assert result is None


class TestBucketIsolation:
    def test_observations_are_runtime_profile_scoped(self, tmp_path: Path) -> None:
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        with isolated_runtime_profile(tmp_path=tmp_path / "bucket-a", bucket_id="bucket-A") as bucket_a:
            svc_a = _service(bucket_a)
            svc_a.record(
                bucket_id=bucket_a.bucket_id,
                surface=VerifySurface.NIF_IVA,
                nif="DE1",
                verdict="valid",
                checked_at=ts,
            )
            assert svc_a.list_observations(bucket_id=bucket_a.bucket_id)[0].nif == "DE1"

        with isolated_runtime_profile(tmp_path=tmp_path / "bucket-b", bucket_id="bucket-B") as bucket_b:
            svc_b = _service(bucket_b)
            assert svc_b.list_observations(bucket_id=bucket_b.bucket_id) == ()
            svc_b.record(
                bucket_id=bucket_b.bucket_id,
                surface=VerifySurface.NIF_IVA,
                nif="DE2",
                verdict="invalid",
                checked_at=ts,
            )
            assert svc_b.list_observations(bucket_id=bucket_b.bucket_id)[0].nif == "DE2"


class TestSecureStorage:
    def test_record_persists_verify_observation_as_secure_object(
        self, secure_engine: TestRuntimeProfile
    ) -> None:
        obs = _service(secure_engine).record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE123456789",
            verdict="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )

        record = secure_engine.repository.load(
            LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace,
            verify_observation_object_key(secure_engine.bucket_id, obs.observation_id),
            expected_class=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            max_supported_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
        )

        assert record is not None
        assert b"DE123456789" in record.payload
        assert not (
            secure_engine.settings.aeat_audit_dir / "live" / "verify" / f"{secure_engine.bucket_id}.jsonl"
        ).exists()


class TestNoWriteSurface:
    def test_service_has_no_write_methods(self) -> None:
        assert not hasattr(VerifyService, "submit")
        assert not hasattr(VerifyService, "send")
        assert not hasattr(VerifyService, "modify_remote")
        assert not hasattr(VerifyService, "register_remote")
