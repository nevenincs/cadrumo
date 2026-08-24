"""Canonical qualified filing-window resolution tests."""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest

from cadrumo.core import Period, ResultDisposition
from cadrumo.domain.calculations.registry import DeadlineWindowDefinition, ModeloRevision

from .._errors import DeadlineValidationError
from .._plazo import _resolve_projected_filing_window, resolve_filing_window

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "0A")
_PROVENANCE = cast(ModeloRevision, object())


def _window(identifier: str, **qualifiers: object) -> DeadlineWindowDefinition:
    return DeadlineWindowDefinition.model_validate(
        {
            "id": identifier,
            "filing_year": _YEAR,
            "period": _PERIOD,
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
