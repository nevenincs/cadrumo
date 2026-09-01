"""Verify the LIVA art. 105.Cinco interrupted-activity seed against a genuine-gap register.

The art. 105.Cinco resumption seed is the GLOBAL percentage over the AGGREGATE
volumes of the last three activo años naturales, skipping the interruption gap -
NOT the average of the three years' definitive percentages, and NOT the three
calendar years. This is a hand-constructed multi-year register whose expected
figure is derived from the independently-stated volumes: the global percentage
differs from the percentage-average, so the two assertions together prove the
mechanism is not the percentage-average shortcut.

The register (whole-entity, one differentiated sector = None):

* 2020 active - con-derecho 9.000, sin-derecho 1.000 (total 10.000) -> 90%
* 2021 active - con-derecho 1.000, sin-derecho 1.000 (total 2.000)  -> 50%
* 2022 active - con-derecho 5.000, sin-derecho 5.000 (total 10.000) -> 50%
* 2023 INTERRUPTED (sin operaciones)
* 2024 resumes -> seed from the aggregate of 2020+2021+2022

Aggregate con-derecho 15.000 / total 22.000 = 68,18% -> rounded up per LIVA
art. 102.Dos to 69%. The average of the three definitive percentages
(90 + 50 + 50) / 3 = 63,33% is a DIFFERENT figure, so 69 != the average proves
the global-over-aggregate semantics.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ..prorrata_regularizacion import build_interrumpida_tres_ultimos_seed

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPECTED_GLOBAL_PERCENTAGE = Decimal("69")


def _settled(ejercicio: int, con: str, sin: str, percentage: str) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        definitive_percentage=Decimal(percentage),
        definitive_volume_con_derecho=Decimal(con),
        definitive_volume_sin_derecho=Decimal(sin),
    )


def _genuine_gap_register() -> ProrrataRegister:
    return ProrrataRegister(
        entries=(
            _settled(2020, "9000", "1000", "90"),
            _settled(2021, "1000", "1000", "50"),
            _settled(2022, "5000", "5000", "50"),
            ProrrataRegisterEntry(
                ejercicio=2023, regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None, interrupted=True
            ),
        ),
    )


def test_seed_uses_last_three_active_years_and_the_global_aggregate_percentage() -> None:
    """The 2024 seed skips the 2023 gap and uses the global percentage over the aggregate volumes."""
    seed, diagnostic = build_interrumpida_tres_ultimos_seed(_genuine_gap_register(), ejercicio=2024)

    assert diagnostic is None
    assert seed.resolved is True
    assert seed.contributing_ejercicios == (2022, 2021, 2020)
    assert seed.provenance is ProrrataProvisionalProvenance.INTERRUMPIDA_TRES_ULTIMOS
    assert seed.percentage == _EXPECTED_GLOBAL_PERCENTAGE
    assert seed.aggregate is not None
    assert seed.aggregate.summed_volume_con_derecho == Decimal("15000")
    assert seed.aggregate.summed_volume_sin_derecho == Decimal("7000")


def test_seed_is_the_global_percentage_not_the_average_of_the_three_definitives() -> None:
    """Anti-average: the seed differs from the mean of the three years' definitive percentages.

    Averaging the stored definitive percentages (90 + 50 + 50) / 3 = 63,33 would
    round to 63; the lawful global-over-aggregate figure is 69. Asserting the seed
    is 69 and NOT the average proves the mechanism is not the percentage-average
    shortcut LIVA art. 105.Cinco forbids.
    """
    register = _genuine_gap_register()
    active = [entry for entry in register.entries if not entry.interrupted]
    percentages = [entry.definitive_percentage for entry in active]
    assert all(percentage is not None for percentage in percentages)
    definitive_percentages = [percentage for percentage in percentages if percentage is not None]
    average_of_definitives = sum(definitive_percentages, Decimal("0")) / Decimal(len(definitive_percentages))

    seed, _diagnostic = build_interrumpida_tres_ultimos_seed(register, ejercicio=2024)

    assert seed.percentage == _EXPECTED_GLOBAL_PERCENTAGE
    assert seed.percentage != average_of_definitives.to_integral_value()


def test_seed_advises_visibly_on_insufficient_active_history() -> None:
    """With fewer than three active años the seed assumes no percentage and advises (never silent)."""
    register = ProrrataRegister(
        entries=(
            _settled(2022, "5000", "5000", "50"),
            ProrrataRegisterEntry(
                ejercicio=2023, regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None, interrupted=True
            ),
        ),
    )
    seed, diagnostic = build_interrumpida_tres_ultimos_seed(register, ejercicio=2024)

    assert seed.resolved is False
    assert seed.percentage is None
    assert diagnostic is not None
    assert "insuficiente" in diagnostic.message
