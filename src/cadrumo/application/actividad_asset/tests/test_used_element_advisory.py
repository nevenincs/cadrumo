"""The plan warns about RIS art. 4.3's last paragraph on the used elements its letter a doubles.

The table maximum for ``maquinaria`` is 12% and the normal modality's multiplier is 2, so an
unelected used machine charges 24%.  The warning changes neither that nor any plan figure.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetPlanAdvisoryKind
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.i18n.render import tr
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    OriginalPriceDetermination,
    UsedAssetOriginalPrice,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, _published_authority, memory_register_authority
from .test_register import _ACQUISITION, _NAME, _forecast, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _element(
    *,
    condition: AcquiredCondition = AcquiredCondition.USED,
    class_key: str = "maquinaria",
    original_price: UsedAssetOriginalPrice | None = None,
    coefficient: Decimal | None = None,
    regime: DirectEstimationRegime = DirectEstimationRegime.NORMAL,
    built: date | None = None,
) -> ActivityAssetRevision:
    base = _revision()
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    facts["acquired_condition"] = condition
    facts["building_construction_date"] = built
    facts["amortization"] = ActivityAssetAmortizationElection(
        regime=regime,
        method=AmortizationMethod.LINEAR,
        authority_class_key=class_key,
        used_original_price=original_price,
        linear_coefficient=coefficient,
    )
    return ActivityAssetRevision(**facts)


def _advisories(
    revision: ActivityAssetRevision,
) -> tuple[ActivityAssetOperations, tuple[ActivityAssetPlanAdvisoryKind, ...]]:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast,
        taxpayer_modality=lambda: revision.amortization.regime,
        register_authority=memory_register_authority(),
    )
    operations.create(revision, _NAME)
    return operations, tuple(item.kind for item in operations.plan_advisories(_ASSET))


def test_a_used_element_on_the_double_coefficient_is_warned_once() -> None:
    _, kinds = _advisories(_element())

    assert kinds == (ActivityAssetPlanAdvisoryKind.USED_ELEMENT_GROUP_LIMIT,)


def test_the_warning_changes_no_figure() -> None:
    revision = _element()
    operations, _ = _advisories(revision)
    before = operations.plan(_ASSET)

    operations.plan_advisories(_ASSET)

    assert operations.plan(_ASSET) == before
    assert _published_authority(revision, 2025).annual_rate == Decimal("0.24")


def test_a_coefficient_above_the_ordinary_maximum_is_warned() -> None:
    _, kinds = _advisories(_element(coefficient=Decimal("0.20")))

    assert kinds == (ActivityAssetPlanAdvisoryKind.USED_ELEMENT_GROUP_LIMIT,)


def test_a_coefficient_inside_the_ordinary_corridor_takes_no_double_and_is_not_warned() -> None:
    _, kinds = _advisories(_element(coefficient=Decimal("0.10")))

    assert kinds == ()


def test_a_new_element_is_not_warned() -> None:
    _, kinds = _advisories(_element(condition=AcquiredCondition.NEW))

    assert kinds == ()


@pytest.mark.parametrize(
    "determination",
    [OriginalPriceDetermination.KNOWN, OriginalPriceDetermination.EXPERT_VALUATION],
)
def test_the_original_price_route_of_letters_b_and_c_is_not_warned(determination: OriginalPriceDetermination) -> None:
    price = UsedAssetOriginalPrice(
        determination=determination,
        original_price=Decimal("25000.00"),
        evidence_reference="original-price-evidence-1",
    )

    _, kinds = _advisories(_element(original_price=price))

    assert kinds == ()


def test_a_modality_without_the_multiplier_is_not_warned() -> None:
    _, kinds = _advisories(_element(regime=DirectEstimationRegime.SIMPLIFIED))

    assert kinds == ()


def test_a_building_under_the_minimum_age_counts_as_new_and_is_not_warned() -> None:
    _, kinds = _advisories(_element(class_key="edificio-industrial", built=date(2020, 1, 1)))

    assert kinds == ()


def test_a_building_of_the_minimum_age_is_used_and_is_warned() -> None:
    _, kinds = _advisories(_element(class_key="edificio-industrial", built=date(2000, 1, 1)))

    assert kinds == (ActivityAssetPlanAdvisoryKind.USED_ELEMENT_GROUP_LIMIT,)


@pytest.mark.parametrize(
    ("locale", "phrase"),
    [
        ("en", "mercantile group"),
        ("es", "grupo mercantil"),
        ("ca", "grup mercantil"),
        ("hu", "vállalatcsoporton"),
    ],
)
def test_the_warning_is_worded_in_every_locale(locale: str, phrase: str) -> None:
    operations, _ = _advisories(_element())

    (advisory,) = operations.plan_advisories(_ASSET)

    assert advisory.label_key == "ledger.actividad_asset.plan_advisory.used_element_group_limit"
    assert phrase in tr(advisory.label_key, locale=locale)
