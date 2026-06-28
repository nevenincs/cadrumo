"""Real-behavior tests for the censo refuse-load guard.

Locks the contract that
:func:`aeat.domain.usage_ratios.load_usage_ratios_with_censo_guard`
refuses on every disagreement path between the persisted
:class:`UsageRatioProfile` and the bound censo, with no auto-migration
and no silent coercion (per the modelo-036-037 foundation contract
2026-05-16 amendment).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...categories import SpendingCategory
from .. import (
    CensoRatioMismatchError,
    UsageRatioProfile,
    load_usage_ratios_with_censo_guard,
    save_usage_ratios,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="b1") as profile:
        yield profile


def test_load_returns_profile_when_no_home_office_overrides() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.50")}),
        bucket_id="b1",
    )

    profile = load_usage_ratios_with_censo_guard(
        bucket_id="b1",
        raw_afectacion_ratio=None,
    )

    assert profile.ratios == {SpendingCategory.TELEFONIA_MOVIL: Decimal("0.50")}


def test_refuses_when_censo_unset_but_home_office_override_persisted() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.20")}),
        bucket_id="b1",
    )

    with pytest.raises(CensoRatioMismatchError) as exc:
        load_usage_ratios_with_censo_guard(
            bucket_id="b1",
            raw_afectacion_ratio=None,
        )

    assert "suministros_home_office_luz" in str(exc.value)


def test_refuses_on_mismatch_between_persisted_and_censo_derived() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO: Decimal("0.50")}),
        bucket_id="b1",
    )

    with pytest.raises(CensoRatioMismatchError) as exc:
        load_usage_ratios_with_censo_guard(
            bucket_id="b1",
            raw_afectacion_ratio=Decimal("0.20"),
        )

    assert "amortizacion_vivienda_afecto" in str(exc.value)
    assert "0.50" in str(exc.value)
    assert "0.20" in str(exc.value)


def test_accepts_when_persisted_matches_censo_derived_value() -> None:
    raw = Decimal("0.20")
    save_usage_ratios(
        UsageRatioProfile(
            ratios={
                SpendingCategory.IBI_VIVIENDA_AFECTO: raw,
                SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO: raw,
            },
        ),
        bucket_id="b1",
    )

    profile = load_usage_ratios_with_censo_guard(
        bucket_id="b1",
        raw_afectacion_ratio=raw,
    )

    assert profile.ratios[SpendingCategory.IBI_VIVIENDA_AFECTO] == raw
    assert profile.ratios[SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO] == raw
