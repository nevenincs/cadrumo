"""Tests for the bucket-scoped verify audit service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....core.identity_check_verdict import IdentityCheckVerdict
from ..errors import LiveApplicationInputError
from ..verify import (
    VerifyObservation,
    VerifyObservationNotFoundError,
    VerifyService,
    VerifySurface,
    verify_observation_object_key,
)
from .verify_test_support import InMemoryVerifyObservationPersistence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_A_ID = "60606060-6060-4060-8060-606060606060"
_BUCKET_B_ID = "61616161-6161-4161-8161-616161616161"


_BUCKET_ID = _BUCKET_A_ID


def _service() -> VerifyService:
    return VerifyService(persistence=InMemoryVerifyObservationPersistence())


class TestRecord:
    def test_record_persists_observation(self) -> None:
        svc = _service()
        obs = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE123456789",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=datetime(2025, 3, 15, 10, 0, tzinfo=UTC),
        )
        assert len(obs.observation_id) == 64
        assert obs.surface is VerifySurface.NIF_IVA
        assert obs.nif == "DE123456789"
        assert obs.verdict == "valid"
        assert obs.expected is None
        assert obs.matched_expectation is None

    def test_record_with_expected_sets_match_flag(self) -> None:
        svc = _service()
        match = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            expected=IdentityCheckVerdict.VALID,
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        miss = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE2",
            verdict=IdentityCheckVerdict.INVALID,
            expected=IdentityCheckVerdict.VALID,
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        assert match.matched_expectation is True
        assert miss.matched_expectation is False

    def test_record_deduplicates_identical_observation(
        self,
    ) -> None:
        svc = _service()
        ts = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
        a = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        b = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        assert a.observation_id == b.observation_id
        assert len(svc.list_observations(bucket_id=_BUCKET_ID)) == 1

    def test_record_distinct_verdict_at_same_timestamp_yields_distinct_id(
        self,
    ) -> None:
        svc = _service()
        ts = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
        a = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        b = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.INVALID,
            checked_at=ts,
        )
        assert a.observation_id != b.observation_id


class TestListObservations:
    def test_list_returns_all_observations(self) -> None:
        svc = _service()
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.TGVI,
            nif="ES1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        all_obs = svc.list_observations(bucket_id=_BUCKET_ID)
        assert len(all_obs) == 2

    def test_list_filters_by_surface(self) -> None:
        svc = _service()
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.TGVI,
            nif="ES1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        nif_iva_obs = svc.list_observations(bucket_id=_BUCKET_ID, surface=VerifySurface.NIF_IVA)
        tgvi_obs = svc.list_observations(bucket_id=_BUCKET_ID, surface=VerifySurface.TGVI)
        assert len(nif_iva_obs) == 1
        assert len(tgvi_obs) == 1
        assert nif_iva_obs[0].surface is VerifySurface.NIF_IVA
        assert tgvi_obs[0].surface is VerifySurface.TGVI

    def test_list_filters_by_nif(self) -> None:
        svc = _service()
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE2",
            verdict=IdentityCheckVerdict.INVALID,
            checked_at=ts,
        )
        de1_obs = svc.list_observations(bucket_id=_BUCKET_ID, nif="DE1")
        assert len(de1_obs) == 1
        assert de1_obs[0].nif == "DE1"


class TestShow:
    def test_show_resolves_full_and_prefix(self) -> None:
        svc = _service()
        obs = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        full = svc.show(bucket_id=_BUCKET_ID, observation_id=obs.observation_id)
        prefix = svc.show(bucket_id=_BUCKET_ID, observation_id=obs.observation_id[:8])
        assert full == obs
        assert prefix == obs

    def test_show_refuses_unknown_id(self) -> None:
        svc = _service()
        with pytest.raises(VerifyObservationNotFoundError) as exc_info:
            svc.show(bucket_id=_BUCKET_ID, observation_id="0" * 64)
        assert exc_info.value.translated_message == "application.live.verify.errors.observation_not_found"
        assert exc_info.value.context == {"observation_id": "0" * 64}
        assert _BUCKET_ID not in str(exc_info.value)

    def test_show_refuses_ambiguous_prefix_without_full_id_leak(self) -> None:
        svc = _service()
        by_prefix: dict[str, list[str]] = {}
        for index in range(17):
            obs = svc.record(
                bucket_id=_BUCKET_ID,
                surface=VerifySurface.NIF_IVA,
                nif=f"DE{index:011d}",
                verdict=IdentityCheckVerdict.VALID,
                checked_at=datetime(2025, 3, 15, 10, index, tzinfo=UTC),
            )
            by_prefix.setdefault(obs.observation_id[:1], []).append(obs.observation_id)

        prefix, matches = next((candidate, ids) for candidate, ids in by_prefix.items() if len(ids) > 1)
        with pytest.raises(VerifyObservationNotFoundError) as exc_info:
            svc.show(bucket_id=_BUCKET_ID, observation_id=prefix)

        assert exc_info.value.translated_message == "application.live.verify.errors.observation_prefix_ambiguous"
        assert exc_info.value.context == {"observation_id": prefix, "match_count": len(matches)}
        for observation_id in matches:
            assert observation_id not in str(exc_info.value)


class TestLatestForNif:
    def test_latest_returns_most_recent_for_pair(self) -> None:
        svc = _service()
        older = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        newer = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.INVALID,
            checked_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        latest = svc.latest_for_nif(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
        )
        assert latest == newer
        assert latest != older

    def test_latest_returns_none_when_no_observations(self) -> None:
        svc = _service()
        result = svc.latest_for_nif(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
        )
        assert result is None


class TestBucketIsolation:
    def test_observations_are_bucket_scoped(self) -> None:
        ts = datetime(2025, 3, 15, tzinfo=UTC)
        persistence = InMemoryVerifyObservationPersistence()
        svc = VerifyService(persistence=persistence)
        svc.record(
            bucket_id=_BUCKET_A_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE1",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=ts,
        )
        assert svc.list_observations(bucket_id=_BUCKET_A_ID)[0].nif == "DE1"
        assert svc.list_observations(bucket_id=_BUCKET_B_ID) == ()
        svc.record(
            bucket_id=_BUCKET_B_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE2",
            verdict=IdentityCheckVerdict.INVALID,
            checked_at=ts,
        )
        assert svc.list_observations(bucket_id=_BUCKET_B_ID)[0].nif == "DE2"


class TestObservationObjectKey:
    def test_object_key_refuses_blank_bucket_with_locale_metadata(self) -> None:
        with pytest.raises(LiveApplicationInputError) as exc_info:
            verify_observation_object_key(" ", "a" * 64)
        assert exc_info.value.translated_message == "application.live.verify.errors.bucket_id_blank"

    def test_object_key_refuses_blank_observation_with_locale_metadata(self) -> None:
        with pytest.raises(LiveApplicationInputError) as exc_info:
            verify_observation_object_key(_BUCKET_A_ID, " ")
        assert exc_info.value.translated_message == "application.live.verify.errors.observation_id_blank"


class TestObservationIdentityAndInstantContracts:
    """``observation_id`` is a content digest and both instants are UTC-aware.

    The identity reaches persistence and the ``show`` projection, so a
    64-character non-digest would be persisted as if it were a content
    address. The instants order history and ``checked_at`` feeds the content
    address itself.
    """

    @staticmethod
    def _fields(**overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "observation_id": "a" * 64,
            "bucket_id": _BUCKET_A_ID,
            "surface": VerifySurface.NIF_IVA,
            "nif": "DE123456789",
            "verdict": "valid",
            "checked_at": datetime(2025, 3, 15, 10, 0, tzinfo=UTC),
            "persisted_at": datetime(2025, 3, 15, 11, 0, tzinfo=UTC),
        }
        base.update(overrides)
        return base

    def test_canonical_lowercase_hex_digest_is_accepted(self) -> None:
        observation = VerifyObservation.model_validate(self._fields())

        assert observation.observation_id == "a" * 64
        assert observation.checked_at.utcoffset() == timedelta(0)
        assert observation.persisted_at.utcoffset() == timedelta(0)

    @pytest.mark.parametrize(
        "malformed",
        ["z" * 64, "A" * 64, "0123456789ABCDEF" * 4, "a" * 63, "a" * 65, "-" * 64],
        ids=["non-hex", "uppercase", "uppercase-hex", "short", "long", "punctuation"],
    )
    def test_non_digest_observation_id_is_refused(self, malformed: str) -> None:
        with pytest.raises(ValidationError):
            VerifyObservation.model_validate(self._fields(observation_id=malformed))

    @pytest.mark.parametrize("field", ["checked_at", "persisted_at"])
    @pytest.mark.parametrize(
        "instant",
        [
            datetime(2025, 3, 15, 10, 0),
            datetime(2025, 3, 15, 10, 0, tzinfo=timezone(timedelta(hours=1))),
        ],
        ids=["naive", "offset-plus-one"],
    )
    def test_naive_or_non_utc_instant_is_refused(self, field: str, instant: datetime) -> None:
        with pytest.raises(ValidationError):
            VerifyObservation.model_validate(self._fields(**{field: instant}))

    def test_mixed_awareness_pair_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            VerifyObservation.model_validate(self._fields(persisted_at=datetime(2025, 3, 15, 11, 0)))

    def test_derived_identity_round_trips_through_persistence(self) -> None:
        persistence = InMemoryVerifyObservationPersistence()
        svc = VerifyService(persistence=persistence)
        recorded = svc.record(
            bucket_id=_BUCKET_ID,
            surface=VerifySurface.TGVI,
            nif="ESB12345674",
            verdict=IdentityCheckVerdict.VALID,
            checked_at=datetime(2025, 3, 15, 10, 0, tzinfo=UTC),
        )

        loaded = persistence.load(bucket_id=_BUCKET_ID, observation_id=recorded.observation_id)

        assert loaded is not None
        assert loaded == recorded
        assert loaded.observation_id == loaded.observation_id.lower()
        assert len(loaded.observation_id) == 64
        assert loaded.checked_at.utcoffset() == timedelta(0)
        assert loaded.persisted_at.utcoffset() == timedelta(0)


class TestNoWriteSurface:
    def test_service_has_no_write_methods(self) -> None:
        assert not hasattr(VerifyService, "submit")
        assert not hasattr(VerifyService, "send")
        assert not hasattr(VerifyService, "modify_remote")
        assert not hasattr(VerifyService, "register_remote")
