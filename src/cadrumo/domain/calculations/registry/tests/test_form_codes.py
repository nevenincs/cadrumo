"""A coded vocabulary reads its codes from the published fact, and refuses drift."""

from __future__ import annotations

import json
from typing import override

import pytest
from pydantic import BaseModel

from cadrumo.core.errors.hierarchy import InternalInvariantError

from ....invoices.business_premises import SituacionInmueble
from ....iva.sepa_marca import SepaMarca
from ..errors import RegistryValidationError
from ..form_codes import RegistryCodedEnum, resolve_form_codes

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _Lease(BaseModel):
    situacion: SituacionInmueble


class _UndeclaredMember(RegistryCodedEnum):
    ESPANA = "espana"
    UE_SEPA = "ue_sepa"
    RESTO_PAISES = "resto_paises"
    LUNA = "luna"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return "modelo-303-identification-form-codes", "sepa_marca"


@pytest.mark.usefixtures("operation")
def test_a_member_reads_the_code_of_the_official_design() -> None:
    # DR303 "Devolución - Marca SEPA", Nota 2 and the Modelo 347 situation list.
    assert (SepaMarca.ESPANA.code, SepaMarca.UE_SEPA.code, SepaMarca.RESTO_PAISES.code) == ("1", "2", "3")
    assert SituacionInmueble.ABROAD.code == "4"


@pytest.mark.usefixtures("operation")
def test_a_stored_code_and_a_semantic_token_read_as_one_member() -> None:
    assert SituacionInmueble("4") is SituacionInmueble.ABROAD
    assert SituacionInmueble("abroad") is SituacionInmueble.ABROAD
    with pytest.raises(ValueError, match="not a SituacionInmueble code"):
        SituacionInmueble("9")


@pytest.mark.usefixtures("operation")
def test_a_model_keeps_the_stored_bytes_through_a_round_trip() -> None:
    stored = '{"situacion":"2"}'

    lease = _Lease.model_validate_json(stored)

    assert lease.situacion is SituacionInmueble.BASQUE_COUNTRY_OR_NAVARRE
    assert json.loads(lease.model_dump_json()) == json.loads(stored)
    assert _Lease.model_validate(lease.model_dump(mode="json")) == lease


@pytest.mark.usefixtures("operation")
def test_a_vocabulary_that_does_not_match_its_fact_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match="is not the vocabulary"):
        _UndeclaredMember.form_codes()


def test_a_code_read_outside_a_pinned_scope_refuses() -> None:
    with pytest.raises(InternalInvariantError, match="generation-pinned"):
        _ = SituacionInmueble.ABROAD.code


def test_a_semantic_token_needs_no_scope() -> None:
    assert SituacionInmueble("abroad") is SituacionInmueble.ABROAD


@pytest.mark.usefixtures("operation")
def test_an_undeclared_key_is_refused() -> None:
    codes = resolve_form_codes("modelo-303-identification-form-codes")
    assert codes.code("answer.yes") == "1"
    with pytest.raises(RegistryValidationError, match="declares no"):
        codes.code("answer.maybe")
