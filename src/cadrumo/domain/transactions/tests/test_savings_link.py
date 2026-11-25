"""A ledger row links to one savings position and names its capital-mobiliario concept from the registry."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.capital_mobiliario_facts import resolve_capital_mobiliario_concept_vocabulary
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..models import Transaction
from .rental_link_rows import booked_date
from .savings_link_rows import savings_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def authority_operation() -> Iterator[None]:
    """Build every row inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


def test_a_row_carries_no_savings_link_by_default() -> None:
    row = savings_row()

    assert row.posicion_ref is None
    assert row.concepto_capital_mobiliario is None


def test_a_row_links_to_a_position_with_a_declared_concept() -> None:
    row = savings_row(posicion_ref="  deposito-1 ", concepto_capital_mobiliario="intereses")

    assert row.posicion_ref == "deposito-1"
    assert str(row.concepto_capital_mobiliario) == "intereses"


def test_the_vocabulary_resolves_in_every_supported_year() -> None:
    envelope = filing_year_envelope()
    for year in range(envelope.floor, envelope.horizon + 1):
        catalogue = resolve_capital_mobiliario_concept_vocabulary(effective_date=booked_date(year))
        assert catalogue.tokens


def test_every_declared_concept_is_admitted() -> None:
    catalogue = resolve_capital_mobiliario_concept_vocabulary(effective_date=booked_date())
    assert set(catalogue.tokens) >= {"intereses", "dividendos", "gasto_administracion_deposito"}
    for token in catalogue.tokens:
        row = savings_row(posicion_ref="pos-1", concepto_capital_mobiliario=token)
        assert str(row.concepto_capital_mobiliario) == token


def test_an_undeclared_concept_is_refused_on_its_field() -> None:
    with pytest.raises(ValidationError) as caught:
        savings_row(posicion_ref="pos-1", concepto_capital_mobiliario="bogus_concepto")

    errors = caught.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("concepto_capital_mobiliario",)
    assert "bogus_concepto" in errors[0]["msg"]


def test_a_concept_without_a_position_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        savings_row(concepto_capital_mobiliario="intereses")

    assert "requires posicion_ref" in str(caught.value)


def test_a_position_without_a_concept_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        savings_row(posicion_ref="pos-1")

    assert "requires concepto_capital_mobiliario" in str(caught.value)


@pytest.mark.parametrize("other", [{"arrendamiento_ref": "lease-1"}, {"inmueble_ref": "finca-1"}])
def test_a_position_row_cannot_also_link_a_lease_or_a_property(other: dict[str, str]) -> None:
    with pytest.raises(ValidationError) as caught:
        savings_row(posicion_ref="pos-1", concepto_capital_mobiliario="intereses", **other)

    assert "mutually exclusive" in str(caught.value)


def test_a_blank_position_reference_is_refused() -> None:
    with pytest.raises(ValidationError):
        savings_row(posicion_ref="   ", concepto_capital_mobiliario="intereses")


def test_the_link_survives_a_json_round_trip() -> None:
    row = savings_row(posicion_ref="pos-1", concepto_capital_mobiliario="dividendos")

    restored = Transaction.model_validate_json(row.model_dump_json())

    assert restored == row
    assert json.loads(restored.model_dump_json())["concepto_capital_mobiliario"] == "dividendos"
