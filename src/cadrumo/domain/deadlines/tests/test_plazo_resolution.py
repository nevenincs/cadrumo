"""Canonical qualified filing-window resolution tests."""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest

from ....core import M210_TIPO_RENTA_CODE_PROJECTION
from ....core.result_disposition import ResultDisposition
from ....core.period import Period
from ...calculations.registry.schema import DeadlineWindowDefinition, ModeloRevision
from ..errors import DeadlineValidationError
from ..plazo import _resolve_projected_filing_window, resolve_filing_window

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "0A")
_PROVENANCE = cast(ModeloRevision, object())


def _window(
    identifier: str,
    *,
    period: Period = _PERIOD,
    **qualifiers: object,
) -> DeadlineWindowDefinition:
    return DeadlineWindowDefinition.model_validate(
        {
            "id": identifier,
            "filing_year": period.filing_year,
            "period": period,
            "period_kind": "annual",
            "opens_on": date(2026, 1, 1),
            "closes_on": date(2026, 1, 20),
            "legal_refs": ("legal.test",),
            "source_refs": ("source-test",),
            **qualifiers,
        },
    )


def _projection(*windows: DeadlineWindowDefinition) -> tuple[tuple[str, ModeloRevision, DeadlineWindowDefinition], ...]:
    return tuple(("210", _PROVENANCE, window) for window in windows)


def test_qualified_resolution_reuses_atomic_coordinate_scope_expansion() -> None:
    ingreso_rent = _window(
        "ingreso-rent",
        resultado_scope=ResultDisposition.INGRESO,
        tipo_renta_scope=("01", "35"),
    )
    devolucion = _window("devolucion", resultado_scope=ResultDisposition.DEVOLUCION)

    resolved = _resolve_projected_filing_window(
        _projection(ingreso_rent, devolucion),
        modelo="210",
        filing_year=_YEAR,
        period=_PERIOD,
        resultado=ResultDisposition.INGRESO,
        tipo_renta_code="35",
    )

    assert resolved is ingreso_rent


def test_official_codes_with_a_shared_rate_concept_remain_distinct_coordinates() -> None:
    assert M210_TIPO_RENTA_CODE_PROJECTION["01"] is M210_TIPO_RENTA_CODE_PROJECTION["35"]

    arrendamiento = _window(
        "arrendamiento",
        resultado_scope=ResultDisposition.INGRESO,
        tipo_renta_scope=("01",),
    )
    arrendamiento_alternativo = _window(
        "arrendamiento-alternativo",
        resultado_scope=ResultDisposition.INGRESO,
        tipo_renta_scope=("35",),
    )
    projection = _projection(arrendamiento, arrendamiento_alternativo)

    assert (
        _resolve_projected_filing_window(
            projection,
            modelo="210",
            filing_year=_YEAR,
            period=_PERIOD,
            resultado=ResultDisposition.INGRESO,
            tipo_renta_code="01",
        )
        is arrendamiento
    )
    assert (
        _resolve_projected_filing_window(
            projection,
            modelo="210",
            filing_year=_YEAR,
            period=_PERIOD,
            resultado=ResultDisposition.INGRESO,
            tipo_renta_code="35",
        )
        is arrendamiento_alternativo
    )


def test_unqualified_window_is_the_canonical_wildcard_for_a_typed_request() -> None:
    wildcard = _window("wildcard")

    resolved = _resolve_projected_filing_window(
        _projection(wildcard),
        modelo="210",
        filing_year=_YEAR,
        period=_PERIOD,
        resultado=ResultDisposition.NEGATIVA,
        tipo_renta_code="02",
    )

    assert resolved is wildcard


def test_ambiguous_atomic_resolution_refuses_instead_of_returning_first() -> None:
    wildcard = _window("wildcard")
    exact = _window("exact", resultado_scope=ResultDisposition.INGRESO, tipo_renta_scope=("01",))

    with pytest.raises(DeadlineValidationError, match=r"ambiguous.*wildcard.*exact"):
        _resolve_projected_filing_window(
            _projection(wildcard, exact),
            modelo="210",
            filing_year=_YEAR,
            period=_PERIOD,
            resultado=ResultDisposition.INGRESO,
            tipo_renta_code="01",
        )


def test_qualified_m210_event_work_resolves_the_annual_window_without_synthesizing_a_period() -> None:
    event_period = Period.from_year_and_code(_YEAR, "EVENT-1")
    annual = _window("imputadas", tipo_renta_scope=("02",))

    assert (
        _resolve_projected_filing_window(
            _projection(annual),
            modelo="210",
            filing_year=_YEAR,
            period=event_period,
            resultado=ResultDisposition.INGRESO,
            tipo_renta_code="02",
        )
        is annual
    )


def test_qualified_m210_event_to_annual_resolution_refuses_ambiguity() -> None:
    event_period = Period.from_year_and_code(_YEAR, "EVENT-1")
    first = _window("first", tipo_renta_scope=("02",))
    second = _window("second", resultado_scope=ResultDisposition.INGRESO, tipo_renta_scope=("02",))

    with pytest.raises(DeadlineValidationError, match=r"ambiguous.*first.*second"):
        _resolve_projected_filing_window(
            _projection(first, second),
            modelo="210",
            filing_year=_YEAR,
            period=event_period,
            resultado=ResultDisposition.INGRESO,
            tipo_renta_code="02",
        )


def test_unqualified_m210_event_resolution_does_not_borrow_an_annual_window() -> None:
    event_period = Period.from_year_and_code(_YEAR, "EVENT-1")

    assert (
        _resolve_projected_filing_window(
            _projection(_window("annual")),
            modelo="210",
            filing_year=_YEAR,
            period=event_period,
            resultado=None,
            tipo_renta_code=None,
        )
        is None
    )


def test_none_is_reserved_for_an_exact_absence_without_year_borrowing() -> None:
    exact = _window("exact", resultado_scope=ResultDisposition.INGRESO, tipo_renta_scope=("01",))

    assert (
        _resolve_projected_filing_window(
            _projection(exact),
            modelo="210",
            filing_year=_YEAR + 1,
            period=_PERIOD,
            resultado=ResultDisposition.INGRESO,
            tipo_renta_code="01",
        )
        is None
    )
    assert (
        _resolve_projected_filing_window(
            _projection(exact),
            modelo="210",
            filing_year=_YEAR,
            period=_PERIOD,
            resultado=ResultDisposition.INGRESO,
            tipo_renta_code="03",
        )
        is None
    )


def test_resolution_never_borrows_a_following_or_future_filing_year_window() -> None:
    following_period = Period.from_year_and_code(_YEAR + 1, "0A")
    future_period = Period.from_year_and_code(_YEAR + 2, "0A")
    following = _window("following", period=following_period)
    future = _window("future", period=future_period)

    assert (
        _resolve_projected_filing_window(
            _projection(following, future),
            modelo="210",
            filing_year=_YEAR,
            period=_PERIOD,
            resultado=None,
            tipo_renta_code=None,
        )
        is None
    )


@pytest.mark.parametrize(
    ("resultado", "tipo_renta_code"),
    [
        ("I", "01"),
        (ResultDisposition.INGRESO, "99"),
    ],
)
def test_public_resolver_refuses_invalid_qualifier_context_before_authority_lookup(
    resultado: object,
    tipo_renta_code: str,
) -> None:
    with pytest.raises(DeadlineValidationError, match=r"resultado|canonical official"):
        resolve_filing_window(
            "210",
            _YEAR,
            _PERIOD,
            resultado=resultado,  # type: ignore[arg-type]
            tipo_renta_code=tipo_renta_code,
        )
