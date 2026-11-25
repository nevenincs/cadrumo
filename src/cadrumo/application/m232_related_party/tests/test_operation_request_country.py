"""A Modelo 232 operation request takes its counterparty country in the one ISO 3166 alpha-2 shape.

The stored operation is already typed ``CountryCodeAlpha2``; the request now
refuses any other length at its boundary instead of admitting up to eight
characters for the worker to refuse later.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from ....core.time.clock import today_madrid
from ....domain.modelos.m232_related_party import Modelo232OperationKind
from ...operations.public_scalar import PublicDecimal
from ..requests import Modelo232OperationStateRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _request(country: str) -> Modelo232OperationStateRequest:
    return Modelo232OperationStateRequest(
        profile_id=uuid.uuid4(),
        ejercicio=today_madrid().year,
        operation_kind=Modelo232OperationKind.RELATED_PARTY,
        counterparty_name="Sociedad vinculada",
        counterparty_country=country,
        amount_eur=PublicDecimal(decimal="250000.00"),
    )


def test_a_two_letter_country_is_admitted() -> None:
    assert _request("DE").counterparty_country == "DE"


@pytest.mark.parametrize("country", ["D", "DEU", "ESPANA"])
def test_a_country_of_any_other_length_is_refused_at_the_request(country: str) -> None:
    with pytest.raises(ValidationError):
        _request(country)
