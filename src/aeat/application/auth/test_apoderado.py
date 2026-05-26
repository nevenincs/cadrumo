"""Tests for the apoderado application service."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.application.auth._apoderado import (
    ApoderadoService,
    ApoderadoStatus,
)
from aeat.core.config import Settings
from aeat.domain.auth.apoderamientos import UnknownScopeError
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Iterator[Settings]:
    """Run apoderado tests against a per-test active-profile runtime."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile.settings


class TestStatus:
    def test_status_on_unconfigured_bucket_reports_not_configured(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        status = svc.status(bucket_id="bucket-001")
        assert status.configured is False
        assert status.represented_nif is None
        assert status.granted_scopes == ()


class TestConfigure:
    def test_configure_persists_canonical_scopes(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id="bucket-001",
            represented_nif="B12345678",
            scope_tokens=("IVA", "RENT"),
        )
        assert config.represented_nif == "B12345678"
        assert config.granted_scopes == ("IVA", "RENT")
        assert config.catalogue_version.startswith("2026")

    def test_configure_dedupes_repeated_scopes(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id="bucket-001",
            represented_nif="B1",
            scope_tokens=("IVA", "RENT", "IVA"),
        )
        assert config.granted_scopes == ("IVA", "RENT")

    def test_configure_expands_all_token(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        config = svc.configure(
            bucket_id="bucket-001",
            represented_nif="B1",
            scope_tokens=("ALL",),
        )
        assert set(config.granted_scopes) == svc.catalogue.code_set()

    def test_configure_rejects_unknown_scope(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(UnknownScopeError):
            svc.configure(
                bucket_id="bucket-001",
                represented_nif="B1",
                scope_tokens=("BOGUS",),
            )

    def test_configure_rejects_comma_separated_scope(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        with pytest.raises(UnknownScopeError, match="comma"):
            svc.configure(
                bucket_id="bucket-001",
                represented_nif="B1",
                scope_tokens=("IVA,RENT",),
            )

    def test_configure_overwrites_existing_record(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id="bucket-001",
            represented_nif="B1",
            scope_tokens=("IVA",),
        )
        new_config = svc.configure(
            bucket_id="bucket-001",
            represented_nif="B2",
            scope_tokens=("RENT",),
        )
        assert new_config.represented_nif == "B2"
        assert new_config.granted_scopes == ("RENT",)
        status = svc.status(bucket_id="bucket-001")
        assert status.represented_nif == "B2"


class TestStatusAfterConfigure:
    def test_status_reads_configured_record(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id="bucket-001",
            represented_nif="B12345678",
            scope_tokens=("IVA", "CENSO"),
        )
        status = svc.status(bucket_id="bucket-001")
        assert status.configured is True
        assert status.represented_nif == "B12345678"
        assert status.granted_scopes == ("IVA", "CENSO")


class TestClear:
    def test_clear_retires_configuration(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id="bucket-001",
            represented_nif="B1",
            scope_tokens=("IVA",),
        )
        cleared = svc.clear(bucket_id="bucket-001")
        assert cleared is True
        status = svc.status(bucket_id="bucket-001")
        assert status.configured is False

    def test_clear_on_unconfigured_is_idempotent(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        assert svc.clear(bucket_id="bucket-001") is False


class TestCheck:
    def test_check_returns_local_status_until_live_wired(
        self,
        isolated_settings: Settings,
    ) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(
            bucket_id="bucket-001",
            represented_nif="B1",
            scope_tokens=("IVA",),
        )
        report = svc.check(bucket_id="bucket-001")
        assert isinstance(report, ApoderadoStatus)
        assert report.configured is True
        assert report.represented_nif == "B1"


class TestBucketIsolation:
    def test_configurations_are_bucket_scoped(self, isolated_settings: Settings) -> None:
        svc = ApoderadoService(settings=isolated_settings)
        svc.configure(bucket_id="bucket-A", represented_nif="NIF-A", scope_tokens=("IVA",))
        svc.configure(bucket_id="bucket-B", represented_nif="NIF-B", scope_tokens=("RENT",))
        a = svc.status(bucket_id="bucket-A")
        b = svc.status(bucket_id="bucket-B")
        assert a.represented_nif == "NIF-A"
        assert a.granted_scopes == ("IVA",)
        assert b.represented_nif == "NIF-B"
        assert b.granted_scopes == ("RENT",)
