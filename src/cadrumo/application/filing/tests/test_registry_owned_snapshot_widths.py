"""The Modelo 296 and 360 producer rows enforce the record designs' widths, read from the registry."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator

import pytest
from pydantic import BaseModel, ValidationError

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.form_codes import resolve_form_codes
from ..producer_snapshot_m296 import Modelo296ProfileFacts
from ..producer_snapshot_m360 import (
    Modelo360ApartadoCorreos,
    Modelo360CuentaTitularFacts,
    Modelo360DireccionExtranjero,
    Modelo360DomicilioEspana,
    Modelo360RepresentanteFacts,
    Modelo360SolicitudFacts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _declared(key: str) -> int:
    return resolve_form_codes("form-row-codes").integer(key)


def _field_refused(model: type[BaseModel], field: str, value: object) -> bool:
    try:
        model.model_validate({field: value})
    except ValidationError as exc:
        return any(error["loc"][0] == field for error in exc.errors())
    return False


@pytest.mark.parametrize(
    ("model", "field", "key"),
    [
        (Modelo296ProfileFacts, "telefono", "m296.telefono_max"),
        (Modelo296ProfileFacts, "numero_total_de_perceptores", "m296.numero_total_perceptores_max"),
    ],
)
def test_a_modelo_296_digit_field_fits_the_design(model: type[BaseModel], field: str, key: str) -> None:
    limit = _declared(key)
    assert not _field_refused(model, field, "1")
    assert not _field_refused(model, field, "1" * limit)
    assert _field_refused(model, field, "1" * (limit + 1))
    assert _field_refused(model, field, "x" * limit)


@pytest.mark.parametrize(
    ("model", "field", "key"),
    [
        (Modelo360SolicitudFacts, "numero_registro_declaracion_anterior", "m360.numero_registro_anterior_max"),
        (Modelo360RepresentanteFacts, "full_name", "m360.full_name_max"),
        (Modelo360RepresentanteFacts, "phone", "m360.phone_max"),
        (Modelo360DomicilioEspana, "tipo_via", "m360.address.street_type_max"),
        (Modelo360DomicilioEspana, "nombre_via", "m360.address.street_name_max"),
        (Modelo360DomicilioEspana, "tipo_numeracion", "m360.address.number_type_max"),
        (Modelo360DomicilioEspana, "calificador_numero", "m360.address.number_qualifier_max"),
        (Modelo360DomicilioEspana, "bloque", "m360.address.block_max"),
        (Modelo360DomicilioEspana, "portal", "m360.address.portal_max"),
        (Modelo360DomicilioEspana, "escalera", "m360.address.staircase_max"),
        (Modelo360DomicilioEspana, "planta", "m360.address.floor_max"),
        (Modelo360DomicilioEspana, "puerta", "m360.address.door_max"),
        (Modelo360DomicilioEspana, "datos_complementarios", "m360.address.complement_max"),
        (Modelo360DomicilioEspana, "localidad", "m360.address.locality_max"),
        (Modelo360DomicilioEspana, "nombre_municipio", "m360.address.municipality_max"),
        (Modelo360DomicilioEspana, "provincia", "m360.address.province_max"),
        (Modelo360DireccionExtranjero, "street", "m360.foreign_address.street_max"),
        (Modelo360DireccionExtranjero, "city", "m360.foreign_address.city_max"),
        (Modelo360DireccionExtranjero, "postal_code", "m360.foreign_address.postal_code_max"),
        (Modelo360DireccionExtranjero, "region", "m360.foreign_address.region_max"),
        (Modelo360CuentaTitularFacts, "titular_nombre", "m360.account.holder_name_max"),
    ],
)
def test_a_modelo_360_text_field_fits_the_design(model: type[BaseModel], field: str, key: str) -> None:
    limit = _declared(key)
    assert not _field_refused(model, field, "X" * limit)
    assert _field_refused(model, field, "X" * (limit + 1))


@pytest.mark.parametrize(
    ("model", "field", "key"),
    [
        (Modelo360DomicilioEspana, "numero_casa", "m360.address.house_number_digits"),
        (Modelo360DomicilioEspana, "codigo_postal", "m360.address.postal_code_digits"),
        (Modelo360ApartadoCorreos, "numero", "m360.po_box.number_digits"),
        (Modelo360ApartadoCorreos, "codigo_postal", "m360.address.postal_code_digits"),
    ],
)
def test_a_modelo_360_digit_field_has_the_full_declared_width(model: type[BaseModel], field: str, key: str) -> None:
    width = _declared(key)
    assert not _field_refused(model, field, "1" * width)
    assert _field_refused(model, field, "1" * (width + 1))
    assert _field_refused(model, field, "1" * (width - 1))
    assert _field_refused(model, field, "x" * width)


def test_a_client_outside_every_scope_keeps_the_technical_bound_only() -> None:
    outside = contextvars.Context()
    limit = _declared("m296.telefono_max")
    assert not outside.run(_field_refused, Modelo296ProfileFacts, "telefono", "1" * (limit + 1))
    assert outside.run(_field_refused, Modelo296ProfileFacts, "telefono", "x")
