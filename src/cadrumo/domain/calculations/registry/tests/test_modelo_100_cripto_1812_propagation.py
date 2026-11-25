"""Regression tests for M100 casilla 1812 auto-propagation from 1811 (contract).

Casilla 1812 (Ganancia no exenta imputable al ejercicio) previously had
``input_kind = "manual"``.  Without an explicit ``--casilla "1812=<value>"``
the aggregators 1813/1814 received zero and the entire crypto gain disappeared
from base imponible del ahorro.

After contract, 1812 is ``input_kind = "computed"`` with formula
``renta-ganancia-cripto-imputable`` (identity copy from 1811).  The AEAT
form default is: 1812 equals 1811 unless the taxpayer defers under Art. 14.2.d
LIRPF (multi-year deferral); that override path is out of scope here.

Oracle authority
----------------
The expected values are structural identities — 1812 must equal 1811 exactly
because the formula is ``op = "copy"``.  The oracle is the TOML formula
declaration itself, verified against the AEAT 2024 form (boe-modelo-100-2024-form)
which shows 1812 pre-populated from 1811 for the standard single-year case.

Every supported filing year is covered; the same gap existed in every authored
revision — 1811 was computed, 1812 stayed manual, and the aggregator 1814
(``suma de las casillas [1812]``) silently received zero, so the crypto gain
never reached base imponible del ahorro.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ..schema import RegistrySnapshot
from . import modelo_100_cripto_1812_propagation_scenarios as scenarios
from .published_authority import PublishedGovernedFactSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


_AUTHORED_YEARS = scenarios.authored_years(PublishedGovernedFactSource().supported_filing_years())


@pytest.mark.parametrize("filing_year", _AUTHORED_YEARS)
def test_1812_identity_copy_standard_gain_reaches_aggregator(
    filing_year: int, registry_snapshot: Callable[..., RegistrySnapshot]
) -> None:
    scenarios.check_1812_identity_copy_standard_gain_reaches_aggregator(filing_year, registry_snapshot)


@pytest.mark.parametrize("filing_year", _AUTHORED_YEARS)
def test_1812_zero_when_no_crypto_gain(filing_year: int, registry_snapshot: Callable[..., RegistrySnapshot]) -> None:
    scenarios.check_1812_zero_when_no_crypto_gain(filing_year, registry_snapshot)


@pytest.mark.parametrize("filing_year", _AUTHORED_YEARS)
def test_1812_anti_tautology_tracks_input(filing_year: int, registry_snapshot: Callable[..., RegistrySnapshot]) -> None:
    scenarios.check_1812_anti_tautology_tracks_input(filing_year, registry_snapshot)
