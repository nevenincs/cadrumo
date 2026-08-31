"""Tests for the bucket-scoped verify audit service.

The ``"live"`` literal in ``cadrumo_live_state_dir / "live" / "verify" / ...`` is a
``not (...).exists()`` refusal guard proving a captured tax id never leaks
into a plaintext audit-trail file alongside the encrypted secure-object
write. An accessor aimed at the wrong location would leave that assertion
trivially satisfied -- the exact silent-pass shape a refusal test must not
risk -- so the literal stays.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.envelope._envelope import Envelope
from ....adapters.persistence.storage.secure_object_namespaces import LIVE_VERIFY_OBSERVATION_NAMESPACE
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, read_db_at_rest_bytes
from ..errors import LiveApplicationInputError
from ..verify import (
    VerifyObservation,
    VerifyObservationNotFoundError,
    VerifyObservationRepository,
    VerifyService,
    VerifySurface,
    verify_observation_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"live"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""
_BUCKET_A_ID = "60606060-6060-4060-8060-606060606060"
_BUCKET_B_ID = "61616161-6161-4161-8161-616161616161"


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
        with pytest.raises(VerifyObservationNotFoundError) as exc_info:
            svc.show(bucket_id=secure_engine.bucket_id, observation_id="0" * 64)
        assert exc_info.value.translated_message == "application.live.verify.errors.observation_not_found"
        assert exc_info.value.context == {"observation_id": "0" * 64}
        assert secure_engine.bucket_id not in str(exc_info.value)

    def test_show_refuses_ambiguous_prefix_without_full_id_leak(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        by_prefix: dict[str, list[str]] = {}
        for index in range(17):
            obs = svc.record(
                bucket_id=secure_engine.bucket_id,
                surface=VerifySurface.NIF_IVA,
                nif=f"DE{index:011d}",
                verdict="valid",
                checked_at=datetime(2025, 3, 15, 10, index, tzinfo=UTC),
            )
            by_prefix.setdefault(obs.observation_id[:1], []).append(obs.observation_id)

        prefix, matches = next((candidate, ids) for candidate, ids in by_prefix.items() if len(ids) > 1)
        with pytest.raises(VerifyObservationNotFoundError) as exc_info:
            svc.show(bucket_id=secure_engine.bucket_id, observation_id=prefix)

        assert exc_info.value.translated_message == "application.live.verify.errors.observation_prefix_ambiguous"
        assert exc_info.value.context == {"observation_id": prefix, "match_count": len(matches)}
        for observation_id in matches:
            assert observation_id not in str(exc_info.value)


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
        with isolated_runtime_profile(tmp_path=tmp_path / "profile-a", bucket_id=_BUCKET_A_ID) as bucket_a:
            svc_a = _service(bucket_a)
            svc_a.record(
                bucket_id=bucket_a.bucket_id,
                surface=VerifySurface.NIF_IVA,
                nif="DE1",
                verdict="valid",
                checked_at=ts,
            )
            assert svc_a.list_observations(bucket_id=bucket_a.bucket_id)[0].nif == "DE1"

        with isolated_runtime_profile(tmp_path=tmp_path / "profile-b", bucket_id=_BUCKET_B_ID) as bucket_b:
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
    def test_record_persists_verify_observation_as_secure_object(self, secure_engine: TestRuntimeProfile) -> None:
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
        assert b"DE123456789" not in read_db_at_rest_bytes(secure_engine.paths.database_file)
        assert not (
            secure_engine.settings.cadrumo_live_state_dir / "live" / "verify" / f"{secure_engine.bucket_id}.jsonl"
        ).exists()

    def test_object_key_refuses_blank_bucket_with_locale_metadata(self) -> None:
        with pytest.raises(LiveApplicationInputError) as exc_info:
            verify_observation_object_key(" ", "a" * 64)
        assert exc_info.value.translated_message == "application.live.verify.errors.bucket_id_blank"

    def test_object_key_refuses_blank_observation_with_locale_metadata(self) -> None:
        with pytest.raises(LiveApplicationInputError) as exc_info:
            verify_observation_object_key(_BUCKET_A_ID, " ")
        assert exc_info.value.translated_message == "application.live.verify.errors.observation_id_blank"

    def test_list_refuses_misrouted_payload_bucket(self, secure_engine: TestRuntimeProfile) -> None:
        observation = VerifyObservation(
            observation_id="a" * 64,
            bucket_id=_BUCKET_B_ID,
            surface=VerifySurface.NIF_IVA,
            nif="DE123456789",
            verdict="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
            persisted_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        envelope = Envelope[VerifyObservation](
            schema_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            written_at=datetime(2025, 3, 15, tzinfo=UTC),
            classification=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            payload=observation,
        )
        secure_engine.repository.save(
            namespace=LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace,
            object_key=verify_observation_object_key(secure_engine.bucket_id, observation.observation_id),
            classification=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            schema_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        repository = VerifyObservationRepository(bucket_id=secure_engine.bucket_id, objects=secure_engine.repository)

        with pytest.raises(LiveApplicationInputError) as exc_info:
            repository.list_observations()

        assert exc_info.value.translated_message == "application.live.verify.errors.observation_bucket_mismatch"
        assert exc_info.value.context == {
            "observation_bucket": _BUCKET_B_ID,
            "repository_bucket": secure_engine.bucket_id,
        }


class TestListRefusesForeignNaturalKeys:
    """Enumeration re-addresses every row instead of trusting the key it sits under.

    ``load`` already refuses an observation whose id differs from the one
    requested. Without the same check on the list path, a valid observation
    re-encrypted under another observation's key reaches history, ``show``,
    and ``latest_for_nif`` through enumeration while a targeted ``load`` of
    that same key refuses it.
    """

    @staticmethod
    def _store_under_key(
        profile: TestRuntimeProfile,
        observation: VerifyObservation,
        *,
        object_key_observation_id: str,
    ) -> None:
        envelope = Envelope[VerifyObservation](
            schema_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            written_at=datetime(2025, 3, 15, tzinfo=UTC),
            classification=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            payload=observation,
        )
        profile.repository.save(
            namespace=LIVE_VERIFY_OBSERVATION_NAMESPACE.namespace,
            object_key=verify_observation_object_key(profile.bucket_id, object_key_observation_id),
            classification=LIVE_VERIFY_OBSERVATION_NAMESPACE.sensitivity,
            schema_version=LIVE_VERIFY_OBSERVATION_NAMESPACE.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    @staticmethod
    def _observation(profile: TestRuntimeProfile, observation_id: str) -> VerifyObservation:
        return VerifyObservation(
            observation_id=observation_id,
            bucket_id=profile.bucket_id,
            surface=VerifySurface.NIF_IVA,
            nif="DE123456789",
            verdict="valid",
            checked_at=datetime(2025, 3, 15, tzinfo=UTC),
            persisted_at=datetime(2025, 3, 15, tzinfo=UTC),
        )

    def test_list_returns_an_observation_stored_under_its_own_key(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        observation = self._observation(secure_engine, "a" * 64)
        self._store_under_key(secure_engine, observation, object_key_observation_id="a" * 64)
        repository = VerifyObservationRepository(bucket_id=secure_engine.bucket_id, objects=secure_engine.repository)

        assert repository.list_observations() == (observation,)

    def test_list_refuses_an_observation_stored_under_a_foreign_key(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        foreign = self._observation(secure_engine, "b" * 64)
        self._store_under_key(secure_engine, foreign, object_key_observation_id="a" * 64)
        repository = VerifyObservationRepository(bucket_id=secure_engine.bucket_id, objects=secure_engine.repository)

        with pytest.raises(LiveApplicationInputError) as exc_info:
            repository.list_observations()

        assert exc_info.value.translated_message == "application.live.verify.errors.observation_key_mismatch"
        assert exc_info.value.context == {"observation_id": "b" * 64}

    def test_targeted_load_of_the_same_row_already_refused_it(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        foreign = self._observation(secure_engine, "b" * 64)
        self._store_under_key(secure_engine, foreign, object_key_observation_id="a" * 64)
        repository = VerifyObservationRepository(bucket_id=secure_engine.bucket_id, objects=secure_engine.repository)

        with pytest.raises(LiveApplicationInputError) as exc_info:
            repository.load("a" * 64)

        assert exc_info.value.translated_message == "application.live.verify.errors.observation_id_mismatch"

    def test_service_history_surfaces_cannot_read_past_the_refusal(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        foreign = self._observation(secure_engine, "b" * 64)
        self._store_under_key(secure_engine, foreign, object_key_observation_id="a" * 64)
        svc = _service(secure_engine)

        for call in (
            lambda: svc.list_observations(bucket_id=secure_engine.bucket_id),
            lambda: svc.show(bucket_id=secure_engine.bucket_id, observation_id="b" * 64),
            lambda: svc.latest_for_nif(
                bucket_id=secure_engine.bucket_id,
                surface=VerifySurface.NIF_IVA,
                nif="DE123456789",
            ),
        ):
            with pytest.raises(LiveApplicationInputError):
                call()


class TestObservationIdentityAndInstantContracts:
    """``observation_id`` is a content digest and both instants are UTC-aware.

    The identity reaches the secure-object key, the ``load`` comparison, and
    the ``show`` projection, so a 64-character non-digest would be persisted
    as if it were a content address. The instants order encrypted history and
    ``checked_at`` feeds the content address itself.
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

    def test_derived_identity_round_trips_through_the_encrypted_store(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        recorded = svc.record(
            bucket_id=secure_engine.bucket_id,
            surface=VerifySurface.TGVI,
            nif="ESB12345674",
            verdict="valid",
            checked_at=datetime(2025, 3, 15, 10, 0, tzinfo=UTC),
        )

        repository = VerifyObservationRepository(bucket_id=secure_engine.bucket_id, objects=secure_engine.repository)
        loaded = repository.load(recorded.observation_id)

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
