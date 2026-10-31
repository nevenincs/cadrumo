"""Settlement-chain tail of Modelo 100, checked against a worked Renta 2024 oracle.

Covers the casillas of the renta-final-settlement construct:
  0587 — cuota líquida incrementada total (0585 + 0586)
  0595 — cuota resultante de la autoliquidación (0587 - deducciones)
  0598 — suma retenciones arrendamientos urbanos (copy of 0153)
  0609 — total pagos a cuenta (sum of retenciones operands)
  0610 — cuota diferencial (0595 - 0609)
  0670 — resultado de la declaración (0610 ± ajustes)

The chain is authored at the earliest edition whose record design carries it
and inherited forward; its identities in every supported year are covered by
``test_modelo_100_filing_surface_across_supported_years``. This module keeps a
figure-level oracle for the 2024 edition, where one exists.

Oracle authority
----------------
Expected values are derived from:
  - LIRPF 2024 Art. 63 (escala estatal — unchanged for 2024)
  - Comunidad de Madrid 2024 autonomic escala
    (registry parameter ``renta-2024-escala-autonomica-madrid-base-general``,
    sourced from ``aeat-renta-2024-manual-parte1``)
  - AEAT Renta 2024 Manual Parte 1, "Liquidación del impuesto"

Roberto landlord persona derivation (base liquidable general 55,500 EUR,
Madrid CCAA, arrendamientos urbanos retenciones 1,824 EUR):

  Escala estatal 2024 at 55,500 EUR (LIRPF Art. 63):
    0-12,450      @ 9.50%  = 1,182.75
    12,450-20,200 @ 12.00% = 930.00   (cumul 2,112.75)
    20,200-35,200 @ 15.00% = 2,250.00 (cumul 4,362.75)
    35,200-55,500 @ 18.50% = 3,755.50 (cumul 8,118.25)
  tarifa_estatal(55,500) = 8,118.25
  tarifa_estatal(5,550)  =   527.25  (mínimo contribuyente)
  Cuota íntegra estatal (0545) = 7,591.00
  No deducciones -> cuota líquida estatal (0570) = 7,591.00
  No incrementos  -> cuota líquida estatal incrementada (0585) = 7,591.00

  Madrid 2024 autonomic escala
  (source: registry parameter file
   ``0014-renta-2024-escala-autonomica-madrid-base-general.toml``,
   authority ``aeat-renta-2024-manual-parte1``):
    0-13,362.22       @ 8.50%  = 1,135.79
    13,362.22-19,004.63 @ 10.70% = 603.74  (cumul 1,739.53)
    19,004.63-35,425.68 @ 12.80% = 2,101.89 (cumul 3,841.42)
    35,425.68-57,320.40 @ 17.40%: 55,500-35,425.68 = 20,074.32 @ 17.40% = 3,492.93
    tarifa_madrid(55,500) = 7,334.35
  The escala autonómica applies to casilla 0523, the Madrid mínimo del
  contribuyente for the gravamen autonómico (5,956.65 EUR for 2024: Ley
  13/2023, applicable from 1 January 2023; Renta 2024 manual, parte 1, p. 1205):
  tarifa_madrid(5,956.65) = 5,956.65 * 8.50% = 506.32
  Cuota íntegra autonómica (0546) = 7,334.35 - 506.32 = 6,828.03
  No deducciones → cuota líquida autonómica (0571) = 6,828.03
  No incrementos  → cuota líquida autonómica incrementada (0586) = 6,828.03

  0587 = 0585 + 0586 = 7,591.00 + 6,828.03 = 14,419.03
  0595 = 0587 (no special deductions 0588/0589/0590/0591) = 14,419.03
  0598 = 0153 (copy formula) = 1,824.00
  0609 = 0598 (all other operands zero) = 1,824.00
  0610 = 0595 - 0609 = 14,419.03 - 1,824.00 = 12,595.03
  0670 = 0610 (no further adjustments) = 12,595.03
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.tests import modelo_100_settlement_chain_scenarios as scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_0587_cuota_liquida_total_is_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0587_cuota_liquida_total_is_computed(m100_2024_snapshot)


def test_0609_total_pagos_a_cuenta_computed_from_0598(m100_2024_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0609_total_pagos_a_cuenta_computed_from_0598(m100_2024_snapshot)


def test_0610_cuota_diferencial_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0610_cuota_diferencial_computed(m100_2024_snapshot)


def test_0670_resultado_declaracion_computed(m100_2024_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0670_resultado_declaracion_computed(m100_2024_snapshot)


def test_settlement_chain_not_zero_for_non_zero_base(m100_2024_snapshot: RegistrySnapshot) -> None:
    scenarios.check_settlement_chain_not_zero_for_non_zero_base(m100_2024_snapshot)


def test_anti_tautology_retenciones_change_affects_chain(m100_2024_snapshot: RegistrySnapshot) -> None:
    scenarios.check_anti_tautology_retenciones_change_affects_chain(m100_2024_snapshot)
