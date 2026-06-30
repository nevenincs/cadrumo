"""Tests for the apoderado application service."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import Settings, override_settings
from ....domain.auth.apoderamientos import UnknownScopeError
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, isolated_two_bucket_runtime
from .._apoderado import (
    ApoderadoLiveCheckUnavailableError,
    ApoderadoService,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_BUCKET_ID = "26262626-2626-4262-8262-262626262626"
_APODERADO_BUCKET_ID = _PROFILE_BUCKET_ID
_SECONDARY_PROFILE_BUCKET_ID = "27272727-2727-4272-8272-272727272727"


@pytest.fixture
def isolated_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Run apoderado tests against a per-test active-profile runtime."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def isolated_settings(isolated_profile: TestRuntimeProfile) -> Settings:
    return isolated_profile.settings


class TestStatus:
    def test_status_on_unconfigured_bucket_reports_not_configured(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is False
        assert status.represented_nif is None
        assert status.granted_scopes == ()


class TestConfigure:
    def test_configure_persists_canonical_scopes(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B12345678",
            scope_tokens=("IVA", "RENT"),
        )
        assert config.represented_nif == "B12345678"
        assert config.granted_scopes == ("IVA", "RENT")
        assert config.catalogue_version.startswith("2026")

    def test_configure_dedupes_repeated_scopes(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B1",
            scope_tokens=("IVA", "RENT", "IVA"),
        )
        assert config.granted_scopes == ("IVA", "RENT")

    def test_configure_expands_all_token(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B1",
            scope_tokens=("ALL",),
        )
        assert set(config.granted_scopes) == svc.catalogue.code_set()

    def test_configure_rejects_unknown_scope(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(UnknownScopeError):
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="B1",
                scope_tokens=("BOGUS",),
            )

    def test_configure_rejects_comma_separated_scope(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(UnknownScopeError, match="comma"):
            svc.configure(
                bucket_id=_APODERADO_BUCKET_ID,
                represented_nif="B1",
                scope_tokens=("IVA,RENT",),
            )

    def test_configure_overwrites_existing_record(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B1",
            scope_tokens=("IVA",),
        )
        new_config = svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B2",
            scope_tokens=("RENT",),
        )
        assert new_config.represented_nif == "B2"
        assert new_config.granted_scopes == ("RENT",)
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.represented_nif == "B2"


class TestStatusAfterConfigure:
    def test_status_reads_configured_record(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B12345678",
            scope_tokens=("IVA", "CENSO"),
        )
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is True
        assert status.represented_nif == "B12345678"
        assert status.granted_scopes == ("IVA", "CENSO")


class TestClear:
    def test_clear_retires_configuration(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B1",
            scope_tokens=("IVA",),
        )
        cleared = svc.clear(bucket_id=_APODERADO_BUCKET_ID)
        assert cleared is True
        status = svc.status(bucket_id=_APODERADO_BUCKET_ID)
        assert status.configured is False

    def test_clear_on_unconfigured_is_idempotent(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        assert svc.clear(bucket_id=_APODERADO_BUCKET_ID) is False


class TestCheck:
    def test_check_refuses_because_live_path_is_unwired(
        self,
        isolated_settings: Settings,
    ) -> None:
        """``check`` is live verification; the path is sealed, so it refuses.

        It must never silently re-read stored configuration and present it
        as a live result — that is the silent mislabelling this contract
        forbids. ``status`` is the offline read.
        """
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id=_APODERADO_BUCKET_ID,
            represented_nif="B1",
            scope_tokens=("IVA",),
        )
        with pytest.raises(ApoderadoLiveCheckUnavailableError):
            svc.check(bucket_id=_APODERADO_BUCKET_ID)

    def test_check_refuses_even_when_unconfigured(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(ApoderadoLiveCheckUnavailableError):
            svc.check(bucket_id=_APODERADO_BUCKET_ID)


class TestBucketIsolation:
    def test_configurations_are_bucket_scoped(self, tmp_path: Path) -> None:
        with isolated_two_bucket_runtime(
            tmp_path=tmp_path,
            primary_bucket_id=_PROFILE_BUCKET_ID,
            secondary_bucket_id=_SECONDARY_PROFILE_BUCKET_ID,
        ) as runtime:
            primary_svc = ApoderadoService(settings=runtime.primary.settings)
            primary_svc.configure(bucket_id=runtime.primary.bucket_id, represented_nif="NIF-A", scope_tokens=("IVA",))

            with runtime.switch_to_secondary():
                secondary_svc = ApoderadoService()
                secondary_svc.configure(
                    bucket_id=runtime.secondary.bucket_id,
                    represented_nif="NIF-B",
                    scope_tokens=("RENT",),
                )
                b = secondary_svc.status(bucket_id=runtime.secondary.bucket_id)

            a = primary_svc.status(bucket_id=runtime.primary.bucket_id)

        assert a.represented_nif == "NIF-A"
        assert a.granted_scopes == ("IVA",)
        assert b.represented_nif == "NIF-B"
        assert b.granted_scopes == ("RENT",)
        assert (runtime.primary.storage_root / "buckets" / runtime.primary.bucket_id / "db" / "aeat.db").is_file()
        assert (runtime.primary.storage_root / "buckets" / runtime.secondary.bucket_id / "db" / "aeat.db").is_file()


class TestSettingsRouting:
    def test_service_explicit_settings_route_survives_context_override(
        self,
        isolated_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        svc = ApoderadoService(settings=isolated_profile.settings)
        wrong_root = tmp_path / "wrong-storage-root"

        with override_settings(aeat_local_storage_root=wrong_root, aeat_active_profile=isolated_profile.bucket_id):
            config = svc.configure(
                bucket_id=isolated_profile.bucket_id,
                represented_nif="B12345678",
                scope_tokens=("IVA",),
            )

        assert config.bucket_id == isolated_profile.bucket_id
        assert svc.status(bucket_id=isolated_profile.bucket_id).represented_nif == "B12345678"
        assert not (wrong_root / "buckets" / isolated_profile.bucket_id / "db" / "aeat.db").exists()
