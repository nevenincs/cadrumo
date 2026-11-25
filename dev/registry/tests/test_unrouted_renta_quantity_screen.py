"""The quantity screen catches a dropped retención the row screen cannot see.

Every ``RentaIncomeObservation`` is built with ``target_casilla_id = "01"``
whatever fact a binding reads off it, so the row-level screen
(``unsupported_ledger_renta_income_observations``) reports a row as consumed the
moment ANY income binding selects it. A row therefore stays "routed" while a
second, independent quantity it carries -- the retención suffered -- reaches no
binding at all. These tests pin that gap closed on the axis the row screen is
blind to, and prove the blindness rather than asserting it.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests import unrouted_renta_quantity_screen_scenarios as scenarios

from .ledger_income_chain_oracle_support import modelo_130_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_committed_revision_draws_every_quantity_its_rows_carry() -> None:
    scenarios.check_the_committed_revision_draws_every_quantity_its_rows_carry(modelo_130_revision)


def test_a_dropped_retenciones_binding_is_surfaced() -> None:
    scenarios.check_a_dropped_retenciones_binding_is_surfaced(modelo_130_revision)


def test_the_row_screen_stays_silent_on_the_same_defect() -> None:
    scenarios.check_the_row_screen_stays_silent_on_the_same_defect(modelo_130_revision)


def test_a_taxpayer_who_suffered_no_retencion_raises_nothing() -> None:
    scenarios.check_a_taxpayer_who_suffered_no_retencion_raises_nothing(modelo_130_revision)


@pytest.mark.parametrize("fact", ["ingresos_integros_sum", "taxable_base_sum"])
def test_an_omitted_alternative_income_measure_raises_nothing(fact: str) -> None:
    scenarios.check_an_omitted_alternative_income_measure_raises_nothing(modelo_130_revision, fact)


def test_the_screen_reads_the_revision_it_is_given() -> None:
    scenarios.check_the_screen_reads_the_revision_it_is_given(modelo_130_revision)
