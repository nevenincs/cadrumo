"""Registry-build gates for cross-revision deadline identity."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import Period, ResultDisposition
from .._schema import DeadlineWindowDefinition, PeriodSelector
from .._validate import RegistryValidator
from .._validate_revision_rules import validate_deadline_window_uniqueness
from ._referential_integrity_support import (
    RegistryValidationError,
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _window(
    window_id: str,
    *,
    resultado_scope: ResultDisposition | None = None,
) -> DeadlineWindowDefinition:
    return DeadlineWindowDefinition(
        id=window_id,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        period_kind="annual",
        opens_on=date(2026, 1, 1),
        closes_on=date(2026, 1, 20),
        resultado_scope=resultado_scope,
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual-modelo",),
    )


def _two_revision_modelo(
    first: DeadlineWindowDefinition,
    second: DeadlineWindowDefinition,
):
    earlier = minimal_revision(deadline_windows=(first,)).model_copy(
        update={
            "id": "earlier",
            "valid_from": date(2024, 1, 1),
            "valid_to": date(2024, 12, 31),
            "period_selector": PeriodSelector(year_from=2024, year_to=2024, periods=("0A",)),
        },
    )
    later = minimal_revision(deadline_windows=(second,)).model_copy(
        update={
            "id": "later",
            "valid_from": date(2025, 1, 1),
            "period_selector": PeriodSelector(year_from=2025, periods=("0A",)),
        },
    )
    return minimal_modelo(minimal_revision()).model_copy(
        update={"revisions": {earlier.id: earlier, later.id: later}},
    )


def test_duplicate_deadline_identifier_across_revisions_bites_independently() -> None:
    modelo = _two_revision_modelo(
        _window("same-id", resultado_scope=ResultDisposition.INGRESO),
        _window("same-id", resultado_scope=ResultDisposition.DEVOLUCION),
    )

    failures = validate_deadline_window_uniqueness(modelo)

    assert any("deadline window id 'same-id' is declared more than once" in failure for failure in failures)
    assert not any("deadline semantic coordinate" in failure for failure in failures)


def test_duplicate_atomic_qualified_coordinate_across_revisions_bites_independently() -> None:
    modelo = _two_revision_modelo(
        _window("unqualified"),
        _window("qualified", resultado_scope=ResultDisposition.INGRESO),
    )

    failures = validate_deadline_window_uniqueness(modelo)

    assert not any("deadline window id" in failure for failure in failures)
    assert any(
        "deadline semantic coordinate" in failure and "resultado_scope=<ResultDisposition.INGRESO: 'I'>" in failure
        for failure in failures
    )


def test_distinct_ids_and_qualified_coordinates_are_accepted() -> None:
    modelo = _two_revision_modelo(
        _window("ingreso", resultado_scope=ResultDisposition.INGRESO),
        _window("devolucion", resultado_scope=ResultDisposition.DEVOLUCION),
    )

    assert validate_deadline_window_uniqueness(modelo) == []


def test_registry_build_routes_deadline_uniqueness_through_the_canonical_pass() -> None:
    modelo = _two_revision_modelo(_window("first"), _window("second"))

    with pytest.raises(RegistryValidationError, match=r"deadline semantic coordinate .* is declared more than once"):
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)
