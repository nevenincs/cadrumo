"""Unit tests for the ``aeat deadlines`` CLI sub-app."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage import (
    EncryptedBlobStore,
    Envelope,
    EphemeralMasterKeyProvider,
    SecretStore,
    SensitivityClass,
    override_master_key_provider,
    override_secret_store,
    save_encrypted_envelope,
)
from ....domain.deadlines import AutonomoProfile, IVARegime
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs-secret",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


@pytest.fixture()
def profile_path(tmp_path: Path) -> Path:
    from ....adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=True,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    path = tmp_path / "profile.json"
    envelope = Envelope[AutonomoProfile](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.IDENTITY,
        payload=profile,
    )
    save_encrypted_envelope(
        envelope,
        path,
        master_key_provider=_resolve_master_key_provider(),
        hkdf_context=b"aeat.application.setup.profile.v1",
    )
    return path


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_list_renders_obligations(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["list", "--year", "2026", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert "303" in result.output
    assert "2026Q1" in result.output


def test_next_renders_an_obligation(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["next", "--year", "2026", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert any(token in result.output for token in ("303", "130", "115", "100"))


def test_explain_known_modelo(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["explain", "303", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert "303" in result.output
    assert "aplica" in result.output


def test_list_requires_profile_when_setting_unset(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", "")
    result = runner.invoke(app, ["list", "--year", "2026"])
    assert result.exit_code != 0
    assert "profile" in result.output.lower()


def test_next_uses_default_profile_path(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    profile_path: Path,
) -> None:
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(profile_path))
    result = runner.invoke(app, ["next", "--year", "2026"])
    assert result.exit_code == 0, result.output
