"""A party's filing name holds the parts the record designs name, as the person stated them.

A natural person states the first surname, the given name, and the second
surname or that there is none; an entity states its razón social and nothing
else. A shorter rendering is stated for one width and fits it. Nothing is
trimmed, reordered or shortened: a part with stray spaces is refused, not
cleaned.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..declared_party_name import DeclaredPartyFilingName, DeclaredPartyKind, DeclaredPartyNameRendering

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_natural_person_keeps_each_stated_part() -> None:
    name = DeclaredPartyFilingName(
        kind=DeclaredPartyKind.NATURAL_PERSON,
        primer_apellido="Ejemplo",
        segundo_apellido="De la Prueba",
        nombre="Ana María",
    )

    assert (name.primer_apellido, name.segundo_apellido, name.nombre) == ("Ejemplo", "De la Prueba", "Ana María")
    assert name.razon_social is None
    assert name.no_second_surname is False


def test_an_entity_keeps_its_razon_social_verbatim() -> None:
    name = DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social="Suministros Ficticios del Norte, S.L.")

    assert name.razon_social == "Suministros Ficticios del Norte, S.L."
    assert name.primer_apellido is None


def test_a_single_surname_is_stated_and_never_read_from_a_blank() -> None:
    stated = DeclaredPartyFilingName(
        kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="Muster", nombre="Erika", no_second_surname=True
    )
    assert stated.segundo_apellido is None

    with pytest.raises(ValidationError):
        DeclaredPartyFilingName(kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="Muster", nombre="Erika")
    with pytest.raises(ValidationError):
        DeclaredPartyFilingName(
            kind=DeclaredPartyKind.NATURAL_PERSON,
            primer_apellido="Muster",
            segundo_apellido="Beispiel",
            nombre="Erika",
            no_second_surname=True,
        )


@pytest.mark.parametrize(
    "parts",
    [
        {"segundo_apellido": "Prueba", "nombre": "Ana"},
        {"primer_apellido": "Ejemplo", "segundo_apellido": "Prueba"},
        {"primer_apellido": "Ejemplo", "segundo_apellido": "Prueba", "nombre": "Ana", "razon_social": "Otra, S.A."},
    ],
)
def test_a_natural_person_missing_a_required_part_or_carrying_a_razon_social_is_refused(
    parts: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        DeclaredPartyFilingName.model_validate({"kind": DeclaredPartyKind.NATURAL_PERSON, **parts})


@pytest.mark.parametrize(
    "parts",
    [
        {},
        {"razon_social": "Ficticia, S.L.", "nombre": "Ana"},
        {"razon_social": "Ficticia, S.L.", "no_second_surname": True},
    ],
)
def test_an_entity_states_only_its_razon_social(parts: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DeclaredPartyFilingName.model_validate({"kind": DeclaredPartyKind.ENTITY, **parts})


@pytest.mark.parametrize("text", ["", " Ficticia", "Ficticia ", "Ficticia  S.L.", "Ficticia\tS.L."])
def test_a_part_with_stray_spaces_or_unprintable_characters_is_refused_not_cleaned(text: str) -> None:
    with pytest.raises(ValidationError):
        DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social=text)


def test_a_rendering_fits_its_width_and_one_is_stated_per_width() -> None:
    fits = DeclaredPartyNameRendering(width=12, text="Ficticia S.L")
    name = DeclaredPartyFilingName(
        kind=DeclaredPartyKind.ENTITY, razon_social="Ficticia Suministros del Norte S.L.", renderings=(fits,)
    )
    assert name.renderings == (fits,)

    with pytest.raises(ValidationError):
        DeclaredPartyNameRendering(width=11, text="Ficticia S.L")
    with pytest.raises(ValidationError):
        DeclaredPartyNameRendering(width=0, text="F")
    with pytest.raises(ValidationError):
        DeclaredPartyFilingName(
            kind=DeclaredPartyKind.ENTITY,
            razon_social="Ficticia Suministros del Norte S.L.",
            renderings=(fits, DeclaredPartyNameRendering(width=12, text="Ficticia")),
        )


def test_a_stated_name_round_trips_through_its_json_form() -> None:
    name = DeclaredPartyFilingName(
        kind=DeclaredPartyKind.NATURAL_PERSON,
        primer_apellido="Ejemplo",
        segundo_apellido="Prueba",
        nombre="Ana",
        renderings=(DeclaredPartyNameRendering(width=10, text="Ejemplo A"),),
    )

    assert DeclaredPartyFilingName.model_validate_json(name.model_dump_json()) == name
