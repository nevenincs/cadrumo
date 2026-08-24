"""Registry-build gates for canonical deadline revision ownership."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import Period
from .._schema import DeadlineWindowDefinition, PeriodSelector
from .._validate import RegistryValidator
from .._validate_revision_rules import validate_deadline_window_ownership
from ._referential_integrity_support import (
    RegistryValidationError,
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _window(window_id: str, period: str) -> DeadlineWindowDefinition:
    return DeadlineWindowDefinition(
        id=window_id,
        filing_year=2024,
        period=Period.from_year_and_code(2024, period),
        period_kind="monthly" if period.isdigit() else "quarterly",
        opens_on=date(2024, 1, 1),
        closes_on=date(2024, 1, 20),
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual-modelo",),
    )


def _cutover_modelo(*, quarter_in_monthly_revision: bool):
    monthly_windows = (_window("monthly-window", "01"),)
    quarterly_windows = (_window("quarterly-window", "1T"),)
    if quarter_in_monthly_revision:
        monthly_windows += quarterly_windows
        quarterly_windows = ()

    monthly = minimal_revision(deadline_windows=monthly_windows).model_copy(
        update={
            "id": "monthly",
            "valid_from": date(2024, 1, 1),
            "period_selector": PeriodSelector(year_from=2024, year_to=2024, periods=("01",)),
        },
    )
    quarterly = minimal_revision(deadline_windows=quarterly_windows).model_copy(
        update={
            "id": "quarterly",
            "valid_from": date(2024, 1, 1),
            "period_selector": PeriodSelector(year_from=2024, year_to=2024, periods=("1T",)),
        },
    )
    return minimal_modelo(minimal_revision()).model_copy(
        update={"revisions": {monthly.id: monthly, quarterly.id: quarterly}},
    )


def test_period_sensitive_cutover_accepts_windows_beneath_selected_revisions() -> None:
    modelo = _cutover_modelo(quarter_in_monthly_revision=False)

    assert validate_deadline_window_ownership(modelo) == []


def test_period_sensitive_cutover_rejects_window_beneath_non_selected_revision() -> None:
    modelo = _cutover_modelo(quarter_in_monthly_revision=True)

    failures = validate_deadline_window_ownership(modelo)

    assert failures == [
        "modelo 130 revision monthly: deadline window 'quarterly-window' belongs to canonically selected "
        "revision 'quarterly' for filing coordinate (2024, '1T')",
    ]


def test_registry_build_routes_ownership_through_canonical_validation_pass() -> None:
    modelo = _cutover_modelo(quarter_in_monthly_revision=True)

    with pytest.raises(
        RegistryValidationError,
        match=r"deadline window 'quarterly-window' belongs to canonically selected revision 'quarterly'",
    ):
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)
