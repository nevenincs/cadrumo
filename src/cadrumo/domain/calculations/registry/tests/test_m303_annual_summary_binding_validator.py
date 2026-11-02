"""The annual-summary validator holds each binding to the endpoints the assembler places."""

from __future__ import annotations

import pytest

from ..bindings import validate_binding_selector_shape
from ..m303_regimen_simplificado_annual_summary_bindings import (
    M390_SUMMARY_AGRICULTURAL_RESULT,
    M390_SUMMARY_NON_AGRICULTURAL_RESULT,
    M390_SUMMARY_SOURCE_READ_ENDPOINTS,
)
from .binding_family_support import family_binding

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EIGHT_SOURCES = tuple(f"iva.test-source-{index}" for index in range(8))


def _provider(
    *,
    sources: tuple[str, ...] = _EIGHT_SOURCES,
    summary: str = M390_SUMMARY_NON_AGRICULTURAL_RESULT,
) -> dict[str, object]:
    return {
        "kind": "m303_regimen_simplificado_annual_summary",
        "source_modelo": "303",
        "source_casilla_ids": sources,
        "summary_casilla_id": summary,
    }


def test_a_well_formed_summary_binding_passes() -> None:
    assert validate_binding_selector_shape(family_binding(_provider())) == []


@pytest.mark.parametrize("endpoint", [*M390_SUMMARY_SOURCE_READ_ENDPOINTS, M390_SUMMARY_AGRICULTURAL_RESULT])
def test_every_endpoint_the_assembler_places_passes(endpoint: str) -> None:
    assert validate_binding_selector_shape(family_binding(_provider(summary=endpoint))) == []


def test_seven_source_casillas_are_refused_on_any_binding() -> None:
    """The retired revision check read only the first binding, so a later one escaped it."""
    binding = family_binding(
        _provider(sources=_EIGHT_SOURCES[:7], summary=M390_SUMMARY_SOURCE_READ_ENDPOINTS[3]),
        binding_id="test.summary.seven-sources",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.summary.seven-sources" in failures[0]
    assert "found 7" in failures[0]


def test_a_summary_casilla_outside_the_endpoint_vocabulary_is_refused() -> None:
    binding = family_binding(
        _provider(summary="iva.anual.regimen-simplificado.not-an-endpoint"),
        binding_id="test.summary.unknown-endpoint",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.summary.unknown-endpoint" in failures[0]
    assert "is not an endpoint the assembler places" in failures[0]


def test_an_authored_aggregation_is_refused() -> None:
    binding = family_binding(_provider(), aggregation={"op": "sum"}, binding_id="test.summary.aggregation")

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.summary.aggregation" in failures[0]
    assert "never reads an aggregation" in failures[0]


def test_a_non_money_value_is_refused() -> None:
    binding = family_binding(_provider(), data_type="integer", channel="integer", binding_id="test.summary.integer")

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "value data_type must be money" in failures[0]
