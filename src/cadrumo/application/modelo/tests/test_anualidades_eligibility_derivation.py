"""LIRPF art. 64/75 anualidades separate-escala eligibility flag derivation.

The régimen predicate for casillas 0528/0530/0529/0531 consumes a profile
binding whose value is derived, not operator-typed: it is 1 (eligible — the
non-custodial payer without the mínimo por descendientes) unless custody is
shared, in which case the payer retains the mínimo and the régimen is off
(flag 0). These tests pin the derivation
(:func:`inject_derived_anualidades_eligibility_facts`) directly on a
fact-index dict so the custody negation and the per-year gating are exercised
without the full calculation harness.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from .._profile_binding import inject_derived_anualidades_eligibility_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _key(year: int) -> str:
    return f"renta_family.anualidades_sin_minimo_descendientes_{year}"


def test_default_eligible_when_no_descendants() -> None:
    fact_index: dict[str, object] = {}
    fact_index_narrowed: Any = fact_index
    inject_derived_anualidades_eligibility_facts(fact_index_narrowed, 2024)
    assert fact_index[_key(2024)] == Decimal("1")


def test_flag_off_when_custody_shared() -> None:
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-05-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    fact_index_narrowed: Any = fact_index
    inject_derived_anualidades_eligibility_facts(fact_index_narrowed, 2024)
    assert fact_index[_key(2024)] == Decimal("0")


def test_flag_eligible_when_custody_not_shared() -> None:
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-05-01",
        "renta_family.descendiente.0.custodia_compartida": "false",
    }
    fact_index_narrowed: Any = fact_index
    inject_derived_anualidades_eligibility_facts(fact_index_narrowed, 2024)
    assert fact_index[_key(2024)] == Decimal("1")


def test_shared_custody_ignored_when_descendant_not_eligible_ordinary() -> None:
    # A non-cohabiting descendant is not eligible for the Art. 58.1 ordinary
    # mínimo, so a shared-custody flag on that row does not negate eligibility.
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-05-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
        "renta_family.descendiente.0.convivencia": "false",
    }
    fact_index_narrowed: Any = fact_index
    inject_derived_anualidades_eligibility_facts(fact_index_narrowed, 2024)
    assert fact_index[_key(2024)] == Decimal("1")


def test_untouched_for_out_of_scope_year() -> None:
    fact_index: dict[str, object] = {}
    fact_index_narrowed: Any = fact_index
    inject_derived_anualidades_eligibility_facts(fact_index_narrowed, 2019)
    assert _key(2019) not in fact_index


def test_idempotent_explicit_fact_preserved() -> None:
    fact_index: dict[str, object] = {_key(2024): Decimal("0")}
    fact_index_narrowed: Any = fact_index
    inject_derived_anualidades_eligibility_facts(fact_index_narrowed, 2024)
    assert fact_index[_key(2024)] == Decimal("0")


@pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
def test_all_in_scope_years_default_eligible(year: int) -> None:
    fact_index: dict[str, object] = {}
    fact_index_narrowed: Any = fact_index
    inject_derived_anualidades_eligibility_facts(fact_index_narrowed, year)
    assert fact_index[_key(year)] == Decimal("1")
