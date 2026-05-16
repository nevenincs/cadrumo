"""Real-behavior tests for the census refuse-load guard.

Locks the contract that
:func:`aeat.domain.usage_ratios.load_usage_ratios_with_census_guard`
refuses on every disagreement path between the persisted
:class:`UsageRatioProfile` and the bound census, with no auto-migration
and no silent coercion (per the modelo-036-037-foundation ADR
2026-05-16 amendment).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.domain.categories import SpendingCategory
from aeat.domain.usage_ratios import (
    CensusRatioMismatchError,
    UsageRatioProfile,
    load_usage_ratios_with_census_guard,
    save_usage_ratios,
)


pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'aeat.db'}")
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


def test_load_returns_profile_when_no_home_office_overrides() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.50")}),
        bucket_id="b1",
    )

    profile = load_usage_ratios_with_census_guard(
        bucket_id="b1",
        raw_afectacion_ratio=None,
    )

    assert profile.ratios == {SpendingCategory.TELEFONIA_MOVIL: Decimal("0.50")}


def test_refuses_when_census_unset_but_home_office_override_persisted() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.20")}),
        bucket_id="b1",
    )

    with pytest.raises(CensusRatioMismatchError) as exc:
        load_usage_ratios_with_census_guard(
            bucket_id="b1",
            raw_afectacion_ratio=None,
        )

    assert "suministros_home_office_luz" in str(exc.value)


def test_refuses_on_mismatch_between_persisted_and_census_derived() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO: Decimal("0.50")}),
        bucket_id="b1",
    )

    with pytest.raises(CensusRatioMismatchError) as exc:
        load_usage_ratios_with_census_guard(
            bucket_id="b1",
            raw_afectacion_ratio=Decimal("0.20"),
        )

    assert "amortizacion_vivienda_afecto" in str(exc.value)
    assert "0.50" in str(exc.value)
    assert "0.20" in str(exc.value)


def test_accepts_when_persisted_matches_census_derived_value() -> None:
    raw = Decimal("0.20")
    save_usage_ratios(
        UsageRatioProfile(
            ratios={
                SpendingCategory.IBI_VIVIENDA_AFECTO: raw,
                SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO: raw,
            }
        ),
        bucket_id="b1",
    )

    profile = load_usage_ratios_with_census_guard(
        bucket_id="b1",
        raw_afectacion_ratio=raw,
    )

    assert profile.ratios[SpendingCategory.IBI_VIVIENDA_AFECTO] == raw
    assert profile.ratios[SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO] == raw
