"""Tests for the bucket-scoped verify audit service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.application.live._verify import (
    VerifyObservation,
    VerifyObservationNotFoundError,
    VerifyService,
    VerifySurface,
)
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return Settings(aeat_audit_dir=tmp_path / "audit")


class TestRecord:
    def test_record_persists_observation(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        obs = svc.record(
            bucket_id="bucket-001",
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

    def test_record_with_expected_sets_match_flag(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        match = svc.record(
            bucket_id="bucket-001",
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            expected="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        miss = svc.record(
            bucket_id="bucket-001",
            surface=VerifySurface.NIF_IVA,
            nif="DE2",
            verdict="invalid",
            expected="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        assert match.matched_expectation is True
        assert miss.matched_expectation is False

    def test_record_deduplicates_identical_observation(
        self, isolated_settings: Settings,
    ) -> None:
        svc = VerifyService(settings=isolated_settings)
        ts = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
        a = svc.record(
            bucket_id="bucket-001",
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        b = svc.record(
            bucket_id="bucket-001",
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        assert a.observation_id == b.observation_id
        assert len(svc.list_observations(bucket_id="bucket-001")) == 1

    def test_record_distinct_verdict_at_same_timestamp_yields_distinct_id(
        self, isolated_settings: Settings,
    ) -> None:
        svc = VerifyService(settings=isolated_settings)
        ts = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
        a = svc.record(
            bucket_id="bucket-001",
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="valid",
            checked_at=ts,
        )
        b = svc.record(
            bucket_id="bucket-001",
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict="invalid",
            checked_at=ts,
        )
        assert a.observation_id != b.observation_id


class TestListObservations:
    def test_list_returns_all_observations(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
            verdict="valid", checked_at=ts,
        )
        svc.record(
            bucket_id="b1", surface=VerifySurface.TGVI, nif="ES1",
            verdict="valid", checked_at=ts,
        )
        all_obs = svc.list_observations(bucket_id="b1")
        assert len(all_obs) == 2

    def test_list_filters_by_surface(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
            verdict="valid", checked_at=ts,
        )
        svc.record(
            bucket_id="b1", surface=VerifySurface.TGVI, nif="ES1",
            verdict="valid", checked_at=ts,
        )
        nif_iva_obs = svc.list_observations(bucket_id="b1", surface=VerifySurface.NIF_IVA)
        tgvi_obs = svc.list_observations(bucket_id="b1", surface=VerifySurface.TGVI)
        assert len(nif_iva_obs) == 1
        assert len(tgvi_obs) == 1
        assert nif_iva_obs[0].surface is VerifySurface.NIF_IVA
        assert tgvi_obs[0].surface is VerifySurface.TGVI

    def test_list_filters_by_nif(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
            verdict="valid", checked_at=ts,
        )
        svc.record(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE2",
            verdict="invalid", checked_at=ts,
        )
        de1_obs = svc.list_observations(bucket_id="b1", nif="DE1")
        assert len(de1_obs) == 1
        assert de1_obs[0].nif == "DE1"


class TestShow:
    def test_show_resolves_full_and_prefix(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        obs = svc.record(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
            verdict="valid", checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        full = svc.show(bucket_id="b1", observation_id=obs.observation_id)
        prefix = svc.show(bucket_id="b1", observation_id=obs.observation_id[:8])
        assert full == obs
        assert prefix == obs

    def test_show_refuses_unknown_id(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        with pytest.raises(VerifyObservationNotFoundError, match="no verify observation"):
            svc.show(bucket_id="b1", observation_id="0" * 64)


class TestLatestForNif:
    def test_latest_returns_most_recent_for_pair(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        older = svc.record(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
            verdict="valid", checked_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        newer = svc.record(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
            verdict="invalid", checked_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        latest = svc.latest_for_nif(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
        )
        assert latest == newer
        assert latest != older

    def test_latest_returns_none_when_no_observations(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        result = svc.latest_for_nif(
            bucket_id="b1", surface=VerifySurface.NIF_IVA, nif="DE1",
        )
        assert result is None


class TestBucketIsolation:
    def test_observations_are_bucket_scoped(self, isolated_settings: Settings) -> None:
        svc = VerifyService(settings=isolated_settings)
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id="bucket-A", surface=VerifySurface.NIF_IVA, nif="DE1",
            verdict="valid", checked_at=ts,
        )
        svc.record(
            bucket_id="bucket-B", surface=VerifySurface.NIF_IVA, nif="DE2",
            verdict="invalid", checked_at=ts,
        )
        a = svc.list_observations(bucket_id="bucket-A")
        b = svc.list_observations(bucket_id="bucket-B")
        assert len(a) == 1
        assert len(b) == 1
        assert a[0].nif == "DE1"
        assert b[0].nif == "DE2"


class TestNoWriteSurface:
    def test_service_has_no_write_methods(self) -> None:
        assert not hasattr(VerifyService, "submit")
        assert not hasattr(VerifyService, "send")
        assert not hasattr(VerifyService, "modify_remote")
        assert not hasattr(VerifyService, "register_remote")
