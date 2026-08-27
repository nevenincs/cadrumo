"""Real-behavior tests for the censo refuse-load guard.

Locks the contract that
:func:`cadrumo.domain.usage_ratios.load_usage_ratios_with_censo_guard`
refuses on every disagreement path between the persisted
:class:`UsageRatioProfile` and the bound censo, with no auto-migration
and no silent coercion (per the modelo-036-037 foundation contract
2026-05-16 amendment).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.profile.usage_ratios import (
    load_usage_ratios_with_censo_guard,
    save_usage_ratios,
)
from ....adapters.persistence.tests.runtime_profile_fixture import (
    bucket_scoped_runtime_profile_fixture,
)
from ...categories import SpendingCategory
from .. import (
    CensoRatioMismatchError,
    UsageRatioProfile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "73737373-7373-4373-8373-737373737311"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def test_load_returns_profile_when_no_home_office_overrides() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.50")}),
        bucket_id=_BUCKET_ID,
    )

    profile = load_usage_ratios_with_censo_guard(
        bucket_id=_BUCKET_ID,
        raw_afectacion_ratio=None,
        year=2025,
    )

    assert profile.ratios == {SpendingCategory.TELEFONIA_MOVIL: Decimal("0.50")}


def test_refuses_when_censo_unset_but_home_office_override_persisted() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.20")}),
        bucket_id=_BUCKET_ID,
    )

    with pytest.raises(CensoRatioMismatchError) as exc:
        load_usage_ratios_with_censo_guard(
            bucket_id=_BUCKET_ID,
            raw_afectacion_ratio=None,
            year=2025,
        )

    assert "suministros_home_office_luz" in str(exc.value)


def test_refuses_when_censo_unset_but_telefonia_fija_override_persisted() -> None:
    """The censo guard now covers telefonia_fija: it is no longer freely overridable.

    Before this category joined HOME_OFFICE_SUMINISTROS, an operator (or a
    bug) could persist any usage ratio for a fixed telephone line at their
    partially affected home with no consistency check against the bound
    censo -- the same defect class this guard closes for its four statutory
    siblings.
    """
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_FIJA: Decimal("0.20")}),
        bucket_id=_BUCKET_ID,
    )

    with pytest.raises(CensoRatioMismatchError) as exc:
        load_usage_ratios_with_censo_guard(
            bucket_id=_BUCKET_ID,
            raw_afectacion_ratio=None,
            year=2025,
        )

    assert "telefonia_fija" in str(exc.value)


def test_accepts_telefonia_fija_when_persisted_matches_censo_derived_value() -> None:
    """A telefonia_fija override equal to raw * 0.30 (its statutory_multiplier) is accepted."""
    raw = Decimal("0.20")
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_FIJA: raw * Decimal("0.30")}),
        bucket_id=_BUCKET_ID,
    )

    profile = load_usage_ratios_with_censo_guard(
        bucket_id=_BUCKET_ID,
        raw_afectacion_ratio=raw,
        year=2025,
    )

    assert profile.ratios[SpendingCategory.TELEFONIA_FIJA] == Decimal("0.060")


def test_refuses_when_censo_unset_but_arrendamiento_vivienda_afecto_override_persisted() -> None:
    """The censo guard now covers arrendamiento_vivienda_afecto: it is no longer freely overridable.

    Before this category joined HOME_OFFICE_OWNERSHIP (it lived in PREMISES,
    alongside a dedicated-local rent it has nothing in common with), an
    operator could persist any usage ratio for a partially affected home's
    rent with no consistency check against the bound censo -- the same
    defect class this guard closes for its three titularidad siblings.
    """
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO: Decimal("0.20")}),
        bucket_id=_BUCKET_ID,
    )

    with pytest.raises(CensoRatioMismatchError) as exc:
        load_usage_ratios_with_censo_guard(
            bucket_id=_BUCKET_ID,
            raw_afectacion_ratio=None,
            year=2025,
        )

    assert "arrendamiento_vivienda_afecto" in str(exc.value)


def test_accepts_arrendamiento_vivienda_afecto_when_persisted_matches_censo_derived_value() -> None:
    """An arrendamiento override equal to the raw ratio (no statutory_multiplier) is accepted."""
    raw = Decimal("0.20")
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO: raw}),
        bucket_id=_BUCKET_ID,
    )

    profile = load_usage_ratios_with_censo_guard(
        bucket_id=_BUCKET_ID,
        raw_afectacion_ratio=raw,
        year=2025,
    )

    assert profile.ratios[SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO] == Decimal("0.20")


def test_refuses_on_mismatch_between_persisted_and_censo_derived() -> None:
    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO: Decimal("0.50")}),
        bucket_id=_BUCKET_ID,
    )

    with pytest.raises(CensoRatioMismatchError) as exc:
        load_usage_ratios_with_censo_guard(
            bucket_id=_BUCKET_ID,
            raw_afectacion_ratio=Decimal("0.20"),
            year=2025,
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
        bucket_id=_BUCKET_ID,
    )

    profile = load_usage_ratios_with_censo_guard(
        bucket_id=_BUCKET_ID,
        raw_afectacion_ratio=raw,
        year=2025,
    )

    assert profile.ratios[SpendingCategory.IBI_VIVIENDA_AFECTO] == raw
    assert profile.ratios[SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO] == raw
