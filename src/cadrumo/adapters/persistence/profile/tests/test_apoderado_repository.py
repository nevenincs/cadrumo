"""Tests for the encrypted apoderado configuration persistence adapter."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .....application.auth.apoderado_service import (
    ApoderadoConfiguration,
    ApoderadoConfigurationIdentityError,
    ApoderadoService,
)
from .....core.identity.bucket import canonical_bucket_id
from .....core.time.clock import now
from ..apoderado import ApoderadoConfigRepository, build_apoderado_config_repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_BUCKET_ID = "26262626-2626-4262-8262-262626262626"
_SECONDARY_PROFILE_BUCKET_ID = "27272727-2727-4272-8272-272727272727"


@pytest.fixture
def isolated_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Run adapter tests against a real encrypted bucket runtime."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_BUCKET_ID) as profile:
        yield profile


class TestStoredConfigurationOwnership:
    """A stored row must belong to the bucket whose key addresses it."""

    def _foreign_configuration(self) -> ApoderadoConfiguration:
        return ApoderadoConfiguration(
            bucket_id=_SECONDARY_PROFILE_BUCKET_ID,
            represented_nif="12345678Z",
            granted_scopes=(),
            catalogue_version="v1",
            configured_at=now(),
            notes="",
        )

    def _rekey_under(self, repo: ApoderadoConfigRepository, key: str, config: ApoderadoConfiguration) -> None:
        """Write a valid encrypted envelope under a deliberately foreign key."""
        envelope = repo._identified_envelope(config)[1]
        repo._objects.save(
            namespace=repo.namespace,
            object_key=key,
            classification=repo.sensitivity,
            schema_version=repo.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def test_load_refuses_a_configuration_keyed_under_a_foreign_bucket(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        repo = ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)
        self._rekey_under(repo, _PROFILE_BUCKET_ID, self._foreign_configuration())

        with pytest.raises(ApoderadoConfigurationIdentityError):
            repo.load()

    def test_status_refuses_rather_than_projecting_a_foreign_represented_identity(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        """The identity refusal remains typed when it crosses the service port."""
        repo = ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)
        self._rekey_under(repo, _PROFILE_BUCKET_ID, self._foreign_configuration())

        with pytest.raises(ApoderadoConfigurationIdentityError):
            from .....domain.calculations.registry.authority import bundled_indexed_authority

            with bundled_indexed_authority().operation() as operation:
                ApoderadoService(
                    repository_factory=build_apoderado_config_repository,
                    operation=operation,
                    settings=isolated_profile.settings,
                ).status(bucket_id=_PROFILE_BUCKET_ID)

    def test_save_refuses_a_configuration_for_another_bucket(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        """A bound adapter cannot write another bucket's represented identity."""
        from .....core.errors.error_codes import get_registered_error_code, resolve_error_message

        repo = ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)
        foreign = self._foreign_configuration()

        with pytest.raises(ApoderadoConfigurationIdentityError) as excinfo:
            repo.save(foreign)

        error = excinfo.value
        assert error.translated_message == "errors.integrity.integrity_apoderado_configuration_identity"
        assert error.context == {
            "bucket_id": foreign.bucket_id,
            "repository_bucket_id": canonical_bucket_id(_PROFILE_BUCKET_ID),
        }
        assert get_registered_error_code(error).code == "INTEGRITY_APODERADO_CONFIGURATION_IDENTITY"
        assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
        resolved = resolve_error_message(error)
        assert resolved and resolved != error.translated_message
        assert foreign.represented_nif not in resolved

    def test_same_bucket_round_trip_still_succeeds(
        self,
        isolated_profile: TestRuntimeProfile,
    ) -> None:
        """The adapter still round-trips a legitimate bucket-local record."""
        repo = ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)
        config = ApoderadoConfiguration(
            bucket_id=_PROFILE_BUCKET_ID,
            represented_nif="12345678Z",
            granted_scopes=(),
            catalogue_version="v1",
            configured_at=now(),
            notes="own bucket",
        )

        repo.save(config)

        assert repo.load() == config

    def test_absent_record_still_reads_as_none(self, isolated_profile: TestRuntimeProfile) -> None:
        """An unconfigured bucket is not an identity violation."""
        repo = ApoderadoConfigRepository(bucket_id=_PROFILE_BUCKET_ID, settings=isolated_profile.settings)

        assert repo.load() is None
