"""Deadline-window regression tests for committed Modelo 202 registry data."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_modelo_202_2025_2p_and_3p_deadline_windows_match_aeat_calendar() -> None:
    """AEAT Calendario del contribuyente 2025 fixes Modelo 202/222 PF 25 windows.

    Official source: AEAT Calendario del contribuyente 2025, "Plazos de
    presentacion de autoliquidaciones con domiciliacion bancaria", Modelos 202
    y 222: October PF 25 closes on 2025-10-20 with direct debit through
    2025-10-15, and December PF 25 closes on 2025-12-22 with direct debit
    through 2025-12-17.
    """
    modelos, catalogues = bundled_registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "202")
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    revision = modelo.revisions["2025-y-siguientes"]

    windows = {
        window.period.registry_token: window for window in revision.deadline_windows if window.filing_year == 2025
    }

    two_p = windows["2P"]
    assert two_p.id == "modelo-202-2025-2p"
    assert two_p.opens_on == date(2025, 10, 1)
    assert two_p.closes_on == date(2025, 10, 20)
    assert two_p.payment_cutoff_on == date(2025, 10, 15)

    three_p = windows["3P"]
    assert three_p.id == "modelo-202-2025-3p"
    assert three_p.opens_on == date(2025, 12, 1)
    assert three_p.closes_on == date(2025, 12, 22)
    assert three_p.payment_cutoff_on == date(2025, 12, 17)
