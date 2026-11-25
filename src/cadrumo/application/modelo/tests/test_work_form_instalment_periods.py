"""A Modelo 202 instalment period has no calendar span, and the form still reads.

The instalment periods are dated by the registry's payment-month declaration, not by a
span, so the form, its export offer and the casilla help date are each read for every
supported year of the modelo without asking the period for an end it does not have.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from ....domain.period import calculation_filing_date
from ..work_form_export_offer import _instalment_share, asks_export_elections, form_export_offer
from .work_form_fixture import built_form, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "202"
_INSTALMENTS = ("1P", "2P", "3P")


def test_a_modelo_202_form_is_served_for_every_instalment_of_every_authored_year(
    operation: PinnedAuthorityOperation,
) -> None:
    years = supported_authored_exercises(_MODELO)
    assert years, "the registry authors no supported year, so this proves nothing"
    for year in years:
        for code in _INSTALMENTS:
            period = Period.from_year_and_code(year, code)
            assert not period.has_date_span(), (year, code)
            form = built_form(operation, _MODELO, year, code, entered=frozenset())
            assert form.period == period, (year, code)
            offer = form_export_offer(
                _MODELO,
                form_snapshot(operation, _MODELO, year, code),
                OutputLanguage.EN,
                form=form,
                verified=False,
                filed=False,
            )
            assert offer is not None, (year, code)
            assert _instalment_share(_MODELO, period) is None, (year, code)
            assert not asks_export_elections(_MODELO, period), (year, code)


def test_the_instalment_periods_are_dated_in_order_within_their_year(operation: PinnedAuthorityOperation) -> None:
    year = supported_authored_exercises(_MODELO)[-1]
    days = [
        calculation_filing_date(Period.from_year_and_code(year, code), authority=operation) for code in _INSTALMENTS
    ]
    assert days == sorted(days)
    assert {day.year for day in days} == {year}
