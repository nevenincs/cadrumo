"""Oracle + anti-tautology tests for Art. 81 bis LIRPF incremento guardería (casilla 0613).

Art. 81 bis LIRPF formula:
    min(gastos_reales, hijos_menores_3 × 1.000, cotizaciones_ss_madre)

  - gastos_reales: sum of gastos_guarderia_euros for eligible children under 3 at year-end
  - hijos_menores_3: count of eligible children under 3 at year-end 2024
  - cotizaciones_ss_madre: mother's SS cotizaciones paid in 2024

Oracle anchoring (from task spec):
  gastos €7,700 + 2 hijos menores 3 + cotizaciones SS €1,500
  → min(7700, 2×1000, 1500) = min(7700, 2000, 1500) = 1500

Anti-tautology: change cotizaciones_ss from 1500 to 2500 → 0613 must change from 1500 to 2000.

Persistence: gastos_guarderia_reales_2024 aggregate emitted by descendant_facts_from_list.
"""

from __future__ import annotations

from datetime import date

import pytest

from .._descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family import DescendantInfo, RentaFamilyProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _hijo_guarderia(gastos: int) -> DescendantInfo:
    """Child born 2022-06-01 → age 2 at 2024-12-31, eligible menor-3."""
    return DescendantInfo(
        birth_date=date(2022, 6, 1),
        gastos_guarderia_euros=gastos,
    )


def _hijo_no_menor_3(gastos: int) -> DescendantInfo:
    """Child born 2020-01-01 → age 4 at 2024-12-31, NOT eligible for Art. 81 bis."""
    return DescendantInfo(
        birth_date=date(2020, 1, 1),
        gastos_guarderia_euros=gastos,
    )


# ---------------------------------------------------------------------------
# RentaFamilyProfile.incremento_guarderia_0613 — oracle tests
# ---------------------------------------------------------------------------


class TestIncrementoGuarderia0613Oracle:
    """Oracle values for Art. 81 bis: min(gastos_reales, hijos×1000, cotizaciones_ss)."""

    def test_spec_oracle_gastos_7700_dos_hijos_cotizaciones_1500(self) -> None:
        """Spec oracle: gastos 7700 + 2 hijos + cot.SS 1500 → min(7700, 2000, 1500) = 1500."""
        profile = RentaFamilyProfile(
            descendientes=(
                _hijo_guarderia(3850),
                _hijo_guarderia(3850),
            ),
            cotizaciones_ss_madre_2024=1500,
        )
        assert profile.gastos_guarderia_reales_2024 == 7700
        assert profile.descendientes_menores_3_2024 == 2
        assert profile.incremento_guarderia_0613(2024) == 1500

    def test_hijos_limit_binds_when_cotizaciones_high(self) -> None:
        """When hijos_menores_3 × 1000 < gastos and cotizaciones_ss, hijos cap binds."""
        profile = RentaFamilyProfile(
            descendientes=(_hijo_guarderia(5000),),
            cotizaciones_ss_madre_2024=3000,
        )
        # min(5000, 1×1000, 3000) = 1000
        assert profile.incremento_guarderia_0613(2024) == 1000

    def test_gastos_limit_binds_when_smallest(self) -> None:
        """When gastos_reales < hijos×1000 and cotizaciones_ss, gastos cap binds."""
        profile = RentaFamilyProfile(
            descendientes=(_hijo_guarderia(300),),
            cotizaciones_ss_madre_2024=2000,
        )
        # min(300, 1×1000, 2000) = 300
        assert profile.incremento_guarderia_0613(2024) == 300

    def test_anti_tautology_raise_cotizaciones_from_1500_to_2500(self) -> None:
        """Anti-tautology: raising cotizaciones from 1500 to 2500 changes 0613 from 1500 to 2000."""
        base = RentaFamilyProfile(
            descendientes=(
                _hijo_guarderia(3850),
                _hijo_guarderia(3850),
            ),
            cotizaciones_ss_madre_2024=1500,
        )
        raised = RentaFamilyProfile(
            descendientes=(
                _hijo_guarderia(3850),
                _hijo_guarderia(3850),
            ),
            cotizaciones_ss_madre_2024=2500,
        )
        assert base.incremento_guarderia_0613(2024) == 1500
        assert raised.incremento_guarderia_0613(2024) == 2000
        assert base.incremento_guarderia_0613(2024) != raised.incremento_guarderia_0613(2024)

    def test_non_eligible_hijo_not_counted(self) -> None:
        """Hijo aged 4 at year-end 2024 does not contribute to gastos or hijos count."""
        profile = RentaFamilyProfile(
            descendientes=(
                _hijo_guarderia(3850),
                _hijo_no_menor_3(5000),
            ),
            cotizaciones_ss_madre_2024=2000,
        )
        # Only the age-2 child counts: min(3850, 1×1000, 2000) = 1000
        assert profile.gastos_guarderia_reales_2024 == 3850
        assert profile.descendientes_menores_3_2024 == 1
        assert profile.incremento_guarderia_0613(2024) == 1000

    def test_zero_cotizaciones_gives_zero(self) -> None:
        """No SS cotizaciones paid → increment is always 0 regardless of gastos."""
        profile = RentaFamilyProfile(
            descendientes=(
                _hijo_guarderia(5000),
                _hijo_guarderia(5000),
            ),
            cotizaciones_ss_madre_2024=0,
        )
        assert profile.incremento_guarderia_0613(2024) == 0

    def test_zero_gastos_gives_zero(self) -> None:
        """No guardería expenses → increment is always 0."""
        profile = RentaFamilyProfile(
            descendientes=(_hijo_guarderia(0),),
            cotizaciones_ss_madre_2024=2000,
        )
        assert profile.incremento_guarderia_0613(2024) == 0

    def test_future_filing_year_gives_zero(self) -> None:
        """Filing year other than 2024 returns 0 (no binding declared yet)."""
        profile = RentaFamilyProfile(
            descendientes=(_hijo_guarderia(5000),),
            cotizaciones_ss_madre_2024=2000,
        )
        assert profile.incremento_guarderia_0613(2025) == 0


# ---------------------------------------------------------------------------
# Persistence: gastos_guarderia aggregate stored in descendant_facts_from_list
# ---------------------------------------------------------------------------


class TestGastosGuarderiaFactPersistence:
    """descendant_facts_from_list must emit renta_family.gastos_guarderia_reales_2024."""

    def test_aggregate_emitted_when_eligible_hijos_have_gastos(self) -> None:
        """Sum of gastos from eligible menores-3 stored as aggregate fact."""
        hijos = (
            _hijo_guarderia(2500),
            _hijo_guarderia(4000),
        )
        facts = dict(descendant_facts_from_list(hijos))
        assert facts["renta_family.gastos_guarderia_reales_2024"] == "6500"

    def test_aggregate_not_emitted_when_zero(self) -> None:
        """Aggregate fact absent when gastos are all zero."""
        hijos = (_hijo_guarderia(0),)
        facts = dict(descendant_facts_from_list(hijos))
        assert "renta_family.gastos_guarderia_reales_2024" not in facts

    def test_aggregate_excludes_non_eligible_hijos(self) -> None:
        """Aggregate only sums gastos for children under 3 at year-end 2024."""
        hijos = (
            _hijo_guarderia(2000),
            _hijo_no_menor_3(9999),
        )
        facts = dict(descendant_facts_from_list(hijos))
        assert facts["renta_family.gastos_guarderia_reales_2024"] == "2000"

    def test_roundtrip_gastos_via_facts(self) -> None:
        """gastos_guarderia_euros survives descendant_facts_from_list → descendant_list_from_facts roundtrip."""
        original = (
            DescendantInfo(
                birth_date=date(2022, 6, 1),
                gastos_guarderia_euros=1500,
            ),
        )
        facts = dict(descendant_facts_from_list(original))
        assert facts["renta_family.descendiente.0.gastos_guarderia"] == "1500"
        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 1
        assert reloaded[0].gastos_guarderia_euros == 1500


# ---------------------------------------------------------------------------
# parse_descendiente_flag: GASTOS_GUARDERIA= key acceptance
# ---------------------------------------------------------------------------


class TestParseDescendienteFlagGastosGuarderia:
    """parse_descendiente_flag must accept GASTOS_GUARDERIA= and validate >= 0."""

    def test_gastos_accepted(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=1500")
        assert d.gastos_guarderia_euros == 1500

    def test_gastos_zero_accepted(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=0")
        assert d.gastos_guarderia_euros == 0

    def test_gastos_absent_defaults_to_zero(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01")
        assert d.gastos_guarderia_euros == 0

    def test_gastos_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="GASTOS_GUARDERIA"):
            parse_descendiente_flag("NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=-1")
