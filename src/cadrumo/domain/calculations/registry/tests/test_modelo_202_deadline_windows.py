"""Deadline-window regressions for the complete supported Modelo 202 corpus."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import PeriodKind, registry_period_kind
from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ..temporal import select_revision
from ..validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_EXPECTED_WINDOWS = {
    (2022, "1P"): (date(2022, 4, 1), date(2022, 4, 20), date(2022, 4, 15)),
    (2022, "2P"): (date(2022, 10, 1), date(2022, 10, 20), date(2022, 10, 15)),
    (2022, "3P"): (date(2022, 12, 1), date(2022, 12, 20), date(2022, 12, 15)),
    (2023, "1P"): (date(2023, 4, 1), date(2023, 4, 20), date(2023, 4, 15)),
    (2023, "2P"): (date(2023, 10, 1), date(2023, 10, 20), date(2023, 10, 15)),
    (2023, "3P"): (date(2023, 12, 1), date(2023, 12, 20), date(2023, 12, 15)),
    (2024, "1P"): (date(2024, 4, 1), date(2024, 4, 22), date(2024, 4, 17)),
    (2024, "2P"): (date(2024, 10, 1), date(2024, 10, 21), date(2024, 10, 16)),
    (2024, "3P"): (date(2024, 12, 1), date(2024, 12, 20), date(2024, 12, 17)),
    (2025, "1P"): (date(2025, 4, 1), date(2025, 4, 21), date(2025, 4, 15)),
    (2025, "2P"): (date(2025, 10, 1), date(2025, 10, 20), date(2025, 10, 15)),
    (2025, "3P"): (date(2025, 12, 1), date(2025, 12, 22), date(2025, 12, 17)),
    (2026, "1P"): (date(2026, 4, 1), date(2026, 4, 20), date(2026, 4, 15)),
    (2026, "2P"): (date(2026, 10, 1), date(2026, 10, 20), date(2026, 10, 15)),
    (2026, "3P"): (date(2026, 12, 1), date(2026, 12, 21), date(2026, 12, 15)),
}


def test_committed_modelo_202_has_exact_supported_year_deadline_census() -> None:
    """Bundled AEAT calendars publish each exact M202/M222 date and cutoff."""
    modelos, catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == "202")
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    observed = {
        (window.period.filing_year, window.period.registry_token): (
            window.opens_on,
            window.closes_on,
            window.payment_cutoff_on,
        )
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if 2022 <= window.period.filing_year <= 2026
    }

    assert observed == _EXPECTED_WINDOWS


def test_committed_modelo_202_windows_use_canonical_periods_sources_and_owners() -> None:
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == "202")
    windows = [
        (revision, window)
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if 2022 <= window.period.filing_year <= 2026
    ]
    assert len(windows) == len(_EXPECTED_WINDOWS) == 15

    for revision, window in windows:
        filing_year = window.period.filing_year
        period = window.period.registry_token
        calendar_ref = f"aeat-calendario-contribuyente-{filing_year}"

        assert window.id == f"modelo-202-{filing_year}-{period.lower()}"
        assert window.filing_year == filing_year
        assert registry_period_kind(period) is PeriodKind.INSTALMENT
        assert window.period.kind is PeriodKind.INSTALMENT
        assert window.period_kind == "quarterly"
        assert calendar_ref in window.source_refs
        assert calendar_ref in revision.source_refs
        assert calendar_ref in revision.constructs[0].source_refs
        assert select_revision(modelo, filing_year=filing_year, period=period) is revision
