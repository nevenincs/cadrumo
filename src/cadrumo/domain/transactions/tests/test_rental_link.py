"""A ledger row links to one lease or one property, and names its rental expense concept from the registry."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..models import Transaction
from .rental_link_rows import booked_date, rental_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def authority_operation() -> Iterator[None]:
    """Build every row inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


def test_a_row_carries_no_rental_link_by_default() -> None:
    row = rental_row()

    assert row.arrendamiento_ref is None
    assert row.inmueble_ref is None
    assert row.gasto_capital_inmobiliario is None


def test_an_income_row_links_to_a_lease() -> None:
    row = rental_row(arrendamiento_ref="  lease-2025-a ")

    assert row.arrendamiento_ref == "lease-2025-a"
    assert row.inmueble_ref is None


def test_an_expense_row_links_to_a_property_with_a_declared_concept() -> None:
    row = rental_row(inmueble_ref="finca-1", gasto_capital_inmobiliario="comunidad")

    assert row.inmueble_ref == "finca-1"
    assert str(row.gasto_capital_inmobiliario) == "comunidad"


def test_the_vocabulary_resolves_in_every_supported_year() -> None:
    envelope = filing_year_envelope()
    for year in range(envelope.floor, envelope.horizon + 1):
        catalogue = resolve_gasto_capital_inmobiliario_catalogue(effective_date=booked_date(year))
        assert len(catalogue.concepts) == 12


def test_every_declared_concept_is_admitted_and_names_its_casilla() -> None:
    catalogue = resolve_gasto_capital_inmobiliario_catalogue(effective_date=booked_date())
    casillas = {str(concept.token): concept.casilla_id for concept in catalogue.concepts}

    assert casillas["interes_financiacion"] == "0105"
    assert casillas["reparacion_conservacion"] == "0106"
    assert casillas["otros"] == "0148"
    assert casillas["mejora"] == "0129"
    assert {c.token for c in catalogue.concepts if c.capitalised} == {catalogue.require("mejora")}
    for concept in catalogue.concepts:
        row = rental_row(inmueble_ref="finca-1", gasto_capital_inmobiliario=str(concept.token))
        assert row.gasto_capital_inmobiliario == concept.token


def test_a_row_with_both_references_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        rental_row(arrendamiento_ref="lease-1", inmueble_ref="finca-1")

    assert "mutually exclusive" in str(caught.value)


def test_an_undeclared_concept_is_refused_on_its_field() -> None:
    with pytest.raises(ValidationError) as caught:
        rental_row(inmueble_ref="finca-1", gasto_capital_inmobiliario="bogus_concepto")

    errors = caught.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("gasto_capital_inmobiliario",)
    assert "bogus_concepto" in errors[0]["msg"]


def test_a_concept_without_a_property_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        rental_row(gasto_capital_inmobiliario="comunidad")

    assert "requires inmueble_ref" in str(caught.value)


def test_a_blank_reference_is_refused() -> None:
    with pytest.raises(ValidationError):
        rental_row(inmueble_ref="   ")


def test_the_link_survives_a_json_round_trip() -> None:
    row = rental_row(inmueble_ref="finca-1", gasto_capital_inmobiliario="suministros")

    restored = Transaction.model_validate_json(row.model_dump_json())

    assert restored == row
    assert json.loads(restored.model_dump_json())["gasto_capital_inmobiliario"] == "suministros"
