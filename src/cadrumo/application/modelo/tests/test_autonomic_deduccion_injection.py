"""Unit tests for the Madrid nacimiento/adopción derived-fact injector.

Exercises ``inject_derived_autonomic_deduccion_facts``
``inject_derived_autonomic_deduccion_facts``): the fail-closed projection of the
prorrateo-weighted eligible-descendant count and the unidad-familiar base term
onto the synthetic keys the casilla-1039 registry formula consumes.

The over-claim guard is the load-bearing property: the count is injected only for
the determinable single / monoparental individual filer resident in Madrid; a
tributación conjunta declaration, a married filer, or a non-Madrid resident
leaves the count at the neutral 0 default so the deducción is never silently
auto-claimed on an indeterminate unidad-familiar aggregate.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....domain.user_profile.values import UserProfileFactValue
from ..profile_binding import inject_derived_autonomic_deduccion_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_COUNT_KEY = "renta_family.madrid_nacimiento_adopcion_eligible_count"
_OTROS_KEY = "renta_family.unidad_familiar_otros_miembros_base"


def _facts(**overrides: UserProfileFactValue) -> dict[str, UserProfileFactValue]:
    base: dict[str, UserProfileFactValue] = {
        "tax_residence.ccaa": "madrid",
        "renta_filing.declaration_type": "1",
        "renta_taxpayer.marital_status": "1",
        "renta_family.descendiente.0.birth_date": "2024-06-01",
        "renta_family.descendiente.0.convivencia": "true",
    }
    base.update(overrides)
    return base


def test_madrid_single_individual_filer_injects_weighted_count() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts()
        inject_derived_autonomic_deduccion_facts(facts, 2025, operation=_authority_operation_for_test)
        assert facts[_COUNT_KEY] == Decimal("1")
        assert facts[_OTROS_KEY] == Decimal("0")


def test_shared_custody_child_injects_prorrateo_weighted_half() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts(**{"renta_family.descendiente.0.custodia_compartida": "true"})
        inject_derived_autonomic_deduccion_facts(facts, 2025, operation=_authority_operation_for_test)
        assert facts[_COUNT_KEY] == Decimal("0.5")


def test_out_of_window_child_leaves_count_at_zero_default() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts(**{"renta_family.descendiente.0.birth_date": "2019-01-01"})
        inject_derived_autonomic_deduccion_facts(facts, 2025, operation=_authority_operation_for_test)
        assert facts[_COUNT_KEY] == Decimal("0")


def test_conjunta_declaration_is_fail_closed_no_auto_claim() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts(**{"renta_filing.declaration_type": "2"})
        inject_derived_autonomic_deduccion_facts(facts, 2025, operation=_authority_operation_for_test)
        # Default 0 supplied so the formula resolves, but no count auto-claimed.
        assert facts[_COUNT_KEY] == Decimal("0")


def test_married_filer_is_fail_closed_no_auto_claim() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts(**{"renta_taxpayer.marital_status": "2"})
        inject_derived_autonomic_deduccion_facts(facts, 2025, operation=_authority_operation_for_test)
        assert facts[_COUNT_KEY] == Decimal("0")


def test_non_madrid_resident_leaves_count_at_zero_default() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts(**{"tax_residence.ccaa": "cataluna"})
        inject_derived_autonomic_deduccion_facts(facts, 2025, operation=_authority_operation_for_test)
        # The two bindings still default to 0 so the formula resolves for every filer.
        assert facts[_COUNT_KEY] == Decimal("0")
        assert facts[_OTROS_KEY] == Decimal("0")


def test_non_2025_filing_year_injects_nothing() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts()
        inject_derived_autonomic_deduccion_facts(facts, 2024, operation=_authority_operation_for_test)
        assert _COUNT_KEY not in facts
        assert _OTROS_KEY not in facts


def test_non_cohabiting_child_leaves_count_at_zero() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        facts = _facts(**{"renta_family.descendiente.0.convivencia": "false"})
        inject_derived_autonomic_deduccion_facts(facts, 2025, operation=_authority_operation_for_test)
        assert facts[_COUNT_KEY] == Decimal("0")
