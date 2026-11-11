from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .. import work_addressing
from ..work_addressing import ModeloWorkPeriodTokenError, modelo_work_address_from_operator_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_OTHER_YEAR = filing_year_envelope().floor


def test_operator_target_accepts_typed_core_period() -> None:
    targets = (
        ("303", Period.from_year_and_code(_YEAR, "1T")),
        ("390", Period.from_year_and_code(_YEAR, "0A")),
        ("303", Period.from_year_and_code(_YEAR, "03")),
    )

    for modelo, period in targets:
        address = modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo=modelo,
            year=_YEAR,
            period=period,
            registry_revision_id=None,
        )

        assert address.period == period
        assert address.filing_year == _YEAR


def test_operator_target_rejects_period_the_modelo_does_not_declare() -> None:
    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="303",
            year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "0A"),
            registry_revision_id=None,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["modelo"] == "303"
    assert "0A" not in str(exc_info.value.context["tokens"]).split(", ")


def test_operator_target_rejects_period_year_mismatch() -> None:
    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="130",
            year=_OTHER_YEAR,
            period=Period.from_year_and_code(_YEAR, "1T"),
            registry_revision_id=None,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["year"] == _OTHER_YEAR


def test_worker_period_mismatch_uses_supplied_authority_pin_without_opening_another_lease(
    monkeypatch: pytest.MonkeyPatch, *, authority_operation: PinnedAuthorityOperation
) -> None:
    def unexpected_lease() -> object:
        pytest.fail("worker natural-address validation must use its existing authority pin")

    monkeypatch.setattr(work_addressing, "bundled_indexed_authority", unexpected_lease)

    with pytest.raises(ModeloWorkPeriodTokenError) as exc_info:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="303",
            year=_OTHER_YEAR,
            period=Period.from_year_and_code(_YEAR, "1T"),
            registry_revision_id=None,
            operation=authority_operation,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["year"] == _OTHER_YEAR
    assert "1T" in str(exc_info.value.context["tokens"])
