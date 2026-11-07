"""Registry-build gates for cross-revision deadline identity."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.period import Period
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.validate_revision_rules import validate_deadline_window_uniqueness
from .profile_schema_support import committed_registry_validator
from .referential_integrity_support import minimal_catalogues, minimal_modelo, minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LATER = filing_year_envelope().horizon
_EARLIER = _LATER - 1


def _window(
    window_id: str,
    *,
    resultado_scope: ResultDisposition | None = None,
) -> DeadlineWindowDefinition:
    return DeadlineWindowDefinition(
        id=window_id,
        filing_year=_LATER,
        period=Period.from_year_and_code(_LATER, "0A"),
        period_kind="annual",
        opens_on=date(_LATER + 1, 1, 1),
        closes_on=date(_LATER + 1, 1, 20),
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
            "valid_from": date(_EARLIER, 1, 1),
            "valid_to": date(_EARLIER, 12, 31),
            "period_selector": PeriodSelector(year_from=_EARLIER, year_to=_EARLIER, periods=("0A",)),
        },
    )
    later = minimal_revision(deadline_windows=(second,)).model_copy(
        update={
            "id": "later",
            "valid_from": date(_LATER, 1, 1),
            "period_selector": PeriodSelector(year_from=_LATER, periods=("0A",)),
        },
    )
    return minimal_modelo(minimal_revision()).model_copy(
        update={"revisions": {earlier.id: earlier, later.id: later}},
    )


@pytest.mark.usefixtures("governed_fact_scope")
def test_duplicate_deadline_identifier_across_revisions_bites_independently() -> None:
    modelo = _two_revision_modelo(
        _window("same-id", resultado_scope=ResultDisposition.INGRESO),
        _window("same-id", resultado_scope=ResultDisposition.DEVOLUCION),
    )

    failures = validate_deadline_window_uniqueness(modelo)

    assert any("deadline window id 'same-id' is declared more than once" in failure for failure in failures)
    assert not any("deadline semantic coordinate" in failure for failure in failures)


@pytest.mark.usefixtures("governed_fact_scope")
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


@pytest.mark.usefixtures("governed_fact_scope")
def test_distinct_ids_and_qualified_coordinates_are_accepted() -> None:
    modelo = _two_revision_modelo(
        _window("ingreso", resultado_scope=ResultDisposition.INGRESO),
        _window("devolucion", resultado_scope=ResultDisposition.DEVOLUCION),
    )

    assert validate_deadline_window_uniqueness(modelo) == []


def test_registry_build_routes_deadline_uniqueness_through_the_canonical_pass() -> None:
    modelo = _two_revision_modelo(_window("first"), _window("second"))

    with pytest.raises(RegistryValidationError, match=r"deadline semantic coordinate .* is declared more than once"):
        committed_registry_validator(minimal_catalogues()).validate_modelo(modelo)
