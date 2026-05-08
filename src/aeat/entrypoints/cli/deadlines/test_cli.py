"""Unit tests for the ``aeat deadlines`` CLI sub-app.

Verifies that ``list``, ``next``, and ``explain`` render correctly for
a representative :class:`aeat.domain.deadlines.AutonomoProfile`,
respect the ``--profile`` flag, and fall back to
``AEAT_DEFAULT_PROFILE_PATH`` when the flag is omitted. Profile fixtures
are written through the encrypted persistence layer so the CLI loads a
real on-disk envelope.
"""

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
def _patch_master_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from ....adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    dispose_engine()
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
        dispose_engine()


@pytest.fixture()
def profile_path(tmp_path: Path) -> Path:
    """Persist an :class:`AutonomoProfile` through the SQL secure-object backend.

    The setup-profile namespace is path-keyed: the natural object key
    is the resolved POSIX path, so we write under that key and return
    the same path. ``AEAT_DEFAULT_PROFILE_PATH``-style consumers reach
    the same SQL row.
    """
    from ....adapters.persistence.storage.sql import SecureObjectRepository

    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=True,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    path = tmp_path / "profile.json"
    SecureObjectRepository().save(
        namespace="aeat.application.setup.profile",
        object_key=path.expanduser().resolve().as_posix(),
        classification=SensitivityClass.IDENTITY,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=profile.model_dump_json().encode("utf-8"),
    )
    return path


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_list_renders_obligations(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["list", "--year", "2026", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert "111" in result.output
    assert "130" in result.output
    assert "2026Q1" in result.output


def test_next_renders_an_obligation(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["next", "--year", "2026", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert "111" in result.output


def test_explain_known_modelo(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["explain", "111", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert "111" in result.output
    assert "retencion" in result.output


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
