"""Regression test for Modelo 100 2024 cuota íntegra — Cluster T fix (contract/contract).

Cluster T root cause: casillas 0511/0512 (mínimo del contribuyente
estatal/autonómica) lacked a formula in the 2024 registry revision, so the
engine silently defaulted them to 0.  The fix (contract) adds parameter
``renta-2024-minimo-contribuyente-base-2024`` (5,550 EUR, LIRPF Art. 57) and
two computed formulas that populate 0511/0512.

contract tests: Pere-shape profile (single taxpayer, Catalonia, base liquidable
general 35,400 EUR, no ahorro base, no family supplements).

contract tests: Supplement scenarios exercising casillas 0513 (mínimo por
descendientes, LIRPF Art. 58) and 0515 (mínimo por ascendientes, LIRPF Art. 59)
as operator-supplied manual inputs.  These casillas follow the same input_kind
= manual pattern as 2025 — the engine does not auto-compute them from birth dates
(no age_at formula op exists).  Operators or the UI supply the statutory amounts
directly based on the taxpayer's declared family situation.

All expected values are derived from the official LIRPF 2024 escala general and
the AEAT Renta 2024 Manual — not from re-running the formula engine.

Calculation authority:
- LIRPF Art. 62-63 (escala estatal base general)
- LIRPF Art. 57 (mínimo del contribuyente: 5,550 EUR base, +1,150 age 65-74,
  +1,400 additional age >=75)
- LIRPF Art. 58 (mínimo por descendientes)
- LIRPF Art. 59 (mínimo por ascendientes)
- LIRPF Art. 73-74 (cuota íntegra autonómica y escala autonómica, Cataluña 2024)
- AEAT Renta 2024 Manual, Part 1, "Liquidación del impuesto"
- BOE Orden HAC-563-2024 (confirming 5,550 EUR unchanged for 2024)
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..schema import RegistrySnapshot
from . import modelo_100_tarifa_real_scenarios as scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def tariff_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """The tariff exercise at calculation grade: these tests assert arithmetic, never filing eligibility."""
    return registry_snapshot("100", scenarios.TARIFF_EXERCISE, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def test_m100_minimo_contribuyente_computed_not_zero(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_m100_minimo_contribuyente_computed_not_zero(tariff_snapshot)


def test_m100_cuota_integra_estatal_matches_lirpf_tables(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_m100_cuota_integra_estatal_matches_lirpf_tables(tariff_snapshot)


def test_m100_cuota_integra_autonomica_cataluna_matches_lirpf_tables(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_m100_cuota_integra_autonomica_cataluna_matches_lirpf_tables(tariff_snapshot)


def test_m100_cuota_integra_estatal_is_positive(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_m100_cuota_integra_estatal_is_positive(tariff_snapshot)


def test_m100_cuota_estatal_pere_age_70_with_age_supplement(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_m100_cuota_estatal_pere_age_70_with_age_supplement(tariff_snapshot)


def test_m100_cuota_estatal_two_descendants_one_under_three(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_m100_cuota_estatal_two_descendants_one_under_three(tariff_snapshot)


def test_m100_cuota_estatal_ascendant_over_75(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_m100_cuota_estatal_ascendant_over_75(tariff_snapshot)


def test_0505_computed_from_0500_no_anualidades(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0505_computed_from_0500_no_anualidades(tariff_snapshot)


def test_anualidades_alimentos_separate_escala(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_anualidades_alimentos_separate_escala(tariff_snapshot)


def test_anti_tautology_anualidades_changes_cuota(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_anti_tautology_anualidades_changes_cuota(tariff_snapshot)


def test_anualidades_regime_off_shared_custody_reduces_to_single_escala(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_anualidades_regime_off_shared_custody_reduces_to_single_escala(tariff_snapshot)


def test_anualidades_regime_off_when_anualidades_exceed_base(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_anualidades_regime_off_when_anualidades_exceed_base(tariff_snapshot)


def test_0587_equals_sum_of_liquida_incrementada(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0587_equals_sum_of_liquida_incrementada(tariff_snapshot)


def test_0609_equals_retencion_trabajo_operand(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0609_equals_retencion_trabajo_operand(tariff_snapshot)


def test_0610_equals_0595_minus_0609(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0610_equals_0595_minus_0609(tariff_snapshot)


def test_anti_tautology_higher_retencion_reduces_cuota_diferencial(tariff_snapshot: RegistrySnapshot) -> None:
    scenarios.check_anti_tautology_higher_retencion_reduces_cuota_diferencial(tariff_snapshot)
