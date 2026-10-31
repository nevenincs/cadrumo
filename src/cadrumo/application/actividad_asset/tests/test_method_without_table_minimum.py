"""A method with no table minimum says so, and does not claim that no edition covers the year."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_baja_correction import _low_value_forecast, _low_value_revision
from .test_register import _ACQUISITION, _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KEY = "ledger.actividad_asset.disposal_finding.method_has_no_minimum"
_UNRESOLVED = "ledger.actividad_asset.disposal_finding.minimum_unresolved"


def test_a_free_method_year_with_an_edition_has_the_no_table_minimum_reason() -> None:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_low_value_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(2026, 12, 31)),
    )
    operations.create(_low_value_revision(), _NAME)

    row = operations.plan("laptop-1")[0]

    assert row.minimum_complete is False
    assert row.minimum_through is None
    assert row.minimum_reason_key == _KEY


def test_a_table_method_with_an_edition_has_a_minimum_and_no_reason() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)

    row = operations.plan("laptop-1")[0]

    assert row.minimum_complete is True
    assert row.minimum_through is not None
    assert row.minimum_reason_key is None


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_the_reason_is_worded_in_every_locale_apart_from_the_unresolved_one(locale: str) -> None:
    worded = lookup_translation(_KEY, locale=locale)

    assert worded is not None
    assert worded != lookup_translation(_UNRESOLVED, locale=locale)
    assert "%{" not in worded
