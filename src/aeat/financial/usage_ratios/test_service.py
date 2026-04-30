"""Unit tests for the usage-ratio persistence service (#259).

Post-USAGE-001 the service routes through the substrate's encrypted-
envelope helpers; every test here exercises the round-trip against a
real on-disk envelope under an :class:`EphemeralMasterKeyProvider`.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ...storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ..categories import SpendingCategory
from . import (
    UsageRatioPersistenceError,
    UsageRatioProfile,
    load_usage_ratios,
    save_usage_ratios,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


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


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    """A missing file yields an empty profile (the virgin state)."""
    target = tmp_path / "missing.json"
    assert not target.exists()
    assert load_usage_ratios(target) == UsageRatioProfile()


def test_save_creates_missing_parent_directory(tmp_path: Path) -> None:
    """``save_usage_ratios`` mkdirs parents when absent."""
    target = tmp_path / "a" / "b" / "ratios.json"
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    save_usage_ratios(profile, target)
    assert target.exists()


def test_save_round_trips(tmp_path: Path) -> None:
    """A saved profile reloads identically through the encrypted envelope."""
    target = tmp_path / "ratios.json"
    profile = UsageRatioProfile(
        ratios={
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21"),
            SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6"),
        }
    )
    save_usage_ratios(profile, target)
    assert load_usage_ratios(target) == profile


def test_save_replaces_previous_payload(tmp_path: Path) -> None:
    """Successive saves replace the payload without leaving ``.tmp`` debris."""
    target = tmp_path / "ratios.json"
    first = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    second = first.with_ratio(SpendingCategory.TELEFONIA_MOVIL, Decimal("0.6"))
    save_usage_ratios(first, target)
    save_usage_ratios(second, target)
    assert load_usage_ratios(target) == second
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_writes_ciphertext_envelope(tmp_path: Path) -> None:
    """The on-disk record is a CipherEnvelope at FINANCIAL class.

    The percentage values must not survive in plaintext.
    """
    target = tmp_path / "ratios.json"
    profile = UsageRatioProfile(
        ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")},
    )
    save_usage_ratios(profile, target)
    on_disk = target.read_text(encoding="utf-8")
    assert '"classification":"financial"' in on_disk
    assert '"encryption":' in on_disk
    # Plaintext canary — the ratio value itself must never appear in the
    # on-disk bytes.
    assert "0.21" not in on_disk
    assert "suministros_home_office_luz" not in on_disk


def test_load_corrupt_envelope_raises_persistence_error(tmp_path: Path) -> None:
    """A corrupted envelope file surfaces as :class:`UsageRatioPersistenceError`."""
    target = tmp_path / "bad.json"
    target.write_text("{not-a-cipher-envelope", encoding="utf-8")
    with pytest.raises(UsageRatioPersistenceError):
        load_usage_ratios(target)


def test_save_target_is_existing_directory_raises(tmp_path: Path) -> None:
    """Pointing ``target`` at an existing directory surfaces cleanly."""
    target = tmp_path / "ratios-as-dir"
    target.mkdir()
    profile = UsageRatioProfile()
    with pytest.raises(UsageRatioPersistenceError):
        save_usage_ratios(profile, target)
    assert list(tmp_path.glob("*.tmp")) == []
