"""The persona reader admits the catalogue's contract and refuses a departure from it."""

from __future__ import annotations

import copy

import pytest

from .persona_identities import parse_identity_catalogue
from .persona_reader_support import _ENVELOPE, _LOWERED, _changed, _document, _parse, _with_filed_returns
from .persona_types import PersonaCatalogueError, YearToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_unchanged_persona_is_admitted_with_a_birth_before_the_floor() -> None:
    document = _document("persona.toml")
    birth = document["profile"]["taxpayer-birth-date"]["year"]
    assert birth.startswith("horizon-") and int(birth.removeprefix("horizon-")) > _ENVELOPE.horizon - _ENVELOPE.floor
    _parse(document)


def test_an_unknown_format_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="format must be 1"):
        _parse(_changed(("format",), 2))
    with pytest.raises(PersonaCatalogueError, match="format must be 1"):
        parse_identity_catalogue({"format": 2, "convention": {}, "identities": []})


_NATURAL_NAME = {"primer_apellido": "Vidal", "segundo_apellido": "Soler", "nombre": "Andrés"}


def _identity_document(identity: dict[str, object]) -> dict[str, object]:
    return {"format": 1, "convention": {}, "identities": [identity]}


def _one_identity(**fields: object) -> dict[str, object]:
    """A natural person with a stated name, unless the fields state a razón social instead."""
    name = {} if "razon_social" in fields else _NATURAL_NAME
    return _identity_document(
        {"role": "a.titular", "persona": "a", "kind": "nif", "value": "00001001N", **name, **fields}
    )


def test_a_natural_person_states_apellidos_and_nombre_and_an_entity_its_razon_social() -> None:
    person = parse_identity_catalogue(_one_identity()).role("a.titular")
    assert (person.primer_apellido, person.segundo_apellido, person.nombre) == ("Vidal", "Soler", "Andrés")
    assert person.is_entity is False
    assert person.surnames == "Vidal Soler"
    assert person.field("nombre") == "Andrés"
    entity = parse_identity_catalogue(
        _one_identity(kind="cif", value="B00010017", razon_social="Ediciones del Turia, S.L.")
    ).role("a.titular")
    assert entity.is_entity is True
    assert entity.field("razon_social") == "Ediciones del Turia, S.L."
    assert entity.surnames is None


def test_a_single_surname_is_stated_and_never_read_from_a_blank() -> None:
    document = _identity_document(
        {
            "role": "a.titular",
            "persona": "a",
            "kind": "nie",
            "value": "X0001001N",
            "primer_apellido": "Holm",
            "nombre": "Mikkel",
            "no_second_surname": True,
        }
    )
    single = parse_identity_catalogue(document).role("a.titular")
    assert single.no_second_surname is True
    assert single.segundo_apellido is None
    assert single.surnames == "Holm"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"kind": "nif", "nombre": "Andrés"}, "states a razon_social, or a natural person's"),
        (
            {"kind": "nif", "primer_apellido": "Vidal", "nombre": "Andrés"},
            "states segundo_apellido, or says no_second_surname",
        ),
        (
            {
                "kind": "nif",
                "primer_apellido": "Vidal",
                "segundo_apellido": "Soler",
                "nombre": "Andrés",
                "no_second_surname": True,
            },
            "contradicts a stated segundo_apellido",
        ),
        (
            {"kind": "nif", "razon_social": "Ediciones del Turia, S.L."},
            "identifies a natural person",
        ),
        (
            {"kind": "cif", "primer_apellido": "Vidal", "segundo_apellido": "Soler", "nombre": "Andrés"},
            "identifies an entity",
        ),
        (
            {"kind": "cif", "razon_social": "Ediciones del Turia, S.L.", "nombre": "Andrés"},
            "states no person name part",
        ),
        ({"kind": "cif"}, "states a razon_social, or a natural person's"),
        (
            {
                "kind": "cif",
                "razon_social": "Ediciones del Turia, S.L.",
                "renderings": [{"width": 10, "text": "Ediciones del Turia"}],
            },
            "fits the width it is stated for",
        ),
        (
            {"kind": "cif", "razon_social": "Ediciones del Turia, S.L.", "renderings": [{"width": 0, "text": "E"}]},
            "positive field width",
        ),
        (
            {
                "kind": "cif",
                "razon_social": "Ediciones del Turia, S.L.",
                "renderings": [{"width": 20, "text": "Ediciones Turia"}, {"width": 20, "text": "Ed. Turia"}],
            },
            "one rendering per field width",
        ),
    ],
)
def test_a_malformed_identity_name_is_refused(fields: dict[str, object], message: str) -> None:
    identity = {"role": "a.titular", "persona": "a", "value": "00001001N", **fields}
    with pytest.raises(PersonaCatalogueError, match=message):
        parse_identity_catalogue(_identity_document(identity))


def test_an_identity_states_the_operators_rendering_for_a_narrower_field() -> None:
    identity: dict[str, object] = {
        "role": "a.titular",
        "persona": "a",
        "value": "00001001N",
        "kind": "cif",
        "razon_social": "Ediciones del Turia, S.L.",
        "renderings": [{"width": 20, "text": "Ediciones del Turia"}],
    }
    stated = parse_identity_catalogue(_identity_document(identity)).role("a.titular")
    assert stated.renderings == ((20, "Ediciones del Turia"),)


@pytest.mark.parametrize("key", ["name", "surnames", "legal_name"])
def test_the_replaced_identity_keys_are_refused(key: str) -> None:
    with pytest.raises(PersonaCatalogueError, match="unknown fields"):
        parse_identity_catalogue(_one_identity(**{key: "Vidal"}))


def test_an_identity_states_its_domicile_province_and_ceuta_melilla_determination() -> None:
    catalogue = parse_identity_catalogue(_one_identity(province="46", ceuta_melilla_deduction=False))
    identity = catalogue.role("a.titular")
    assert identity.province == "46"
    assert identity.ceuta_melilla_deduction is False
    bare = parse_identity_catalogue(_one_identity()).role("a.titular")
    assert bare.province is None
    assert bare.ceuta_melilla_deduction is None


@pytest.mark.parametrize("province", ["00", "53", "98", "6", "460"])
def test_a_province_outside_the_spanish_codes_is_refused(province: str) -> None:
    with pytest.raises(PersonaCatalogueError, match="province must be a two-digit Spanish province code"):
        parse_identity_catalogue(_one_identity(province=province))


def test_an_unknown_identity_role_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="unknown identity role"):
        _parse(_changed(("profile", "tax-id"), {"identity": "asalariada.desconocida"}))


def test_another_personas_identity_role_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="belongs to persona"):
        _parse(_changed(("profile", "tax-id"), {"identity": "fontanero.titular"}))


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="unknown fields"):
        _parse(_changed(("persona", "nickname"), "Lucía"))


@pytest.mark.parametrize(
    ("path", "token"),
    [
        (("persona", "fiscal_year"), "horizon+1"),
        (("persona", "fiscal_year"), "floor-1"),
        (("clock", "as_of"), {"year": "horizon+1", "month": 2, "day": 16}),
        (("profile", "taxpayer-birth-date"), {"year": "horizon+1", "month": 6, "day": 14}),
    ],
)
def test_a_year_outside_the_envelope_is_refused(path: tuple[str, ...], token: object) -> None:
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(_changed(path, token))


def test_a_history_record_below_the_floor_is_refused_unless_a_lowered_horizon_omits_it() -> None:
    document = _document("persona.toml")
    (observation,) = document["local_observations"]
    assert YearToken.parse(observation["year"], where="test").precedes_floor(_LOWERED)
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED)

    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert persona.local_observations == ()
    (history,) = [item for item in persona.below_floor if item.history]
    assert (history.block, history.modelo, str(history.year), history.periods) == (
        "local_observations",
        observation["modelo"],
        observation["year"],
        (observation["period"],),
    )
    assert f"floor {_LOWERED.floor}" in history.reason(_LOWERED)
    assert all(item.year.precedes_floor(_LOWERED) for item in persona.below_floor)


def test_a_withholding_certificate_below_the_floor_is_left_out_under_a_lowered_horizon() -> None:
    document = _document("persona.toml")
    stated = [YearToken.parse(item["ejercicio"], where="test") for item in document["withholding_certificates"]]
    below = [token for token in stated if token.precedes_floor(_LOWERED)]
    assert below and len(below) < len(stated)

    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert [str(item.ejercicio) for item in persona.withholding_certificates] == [
        str(token) for token in stated if not token.precedes_floor(_LOWERED)
    ]
    left_out = [item for item in persona.below_floor if item.block == "withholding_certificates"]
    assert [str(item.year) for item in left_out] == [str(token) for token in below]
    assert not any(item.history for item in left_out)


def test_work_income_none_statements_are_read_with_their_ejercicio() -> None:
    document = _document("persona.toml")
    stated = [item["ejercicio"] for item in document["work_income_none_statements"]]
    assert stated

    persona = _parse(document)

    assert [str(item.ejercicio) for item in persona.work_income_none_statements] == stated


def test_a_work_income_none_statement_with_an_unknown_key_or_no_ejercicio_is_refused() -> None:
    document = copy.deepcopy(_document("persona.toml"))
    document["work_income_none_statements"][0]["amount"] = "0.00"
    with pytest.raises(PersonaCatalogueError, match="unknown fields"):
        _parse(document)

    document = copy.deepcopy(_document("persona.toml"))
    del document["work_income_none_statements"][0]["ejercicio"]
    with pytest.raises(PersonaCatalogueError, match="missing fields"):
        _parse(document)


def test_a_work_income_none_statement_below_the_floor_is_left_out_under_a_lowered_horizon() -> None:
    document = _document("persona.toml")
    stated = [YearToken.parse(item["ejercicio"], where="test") for item in document["work_income_none_statements"]]
    below = [token for token in stated if token.precedes_floor(_LOWERED)]
    assert below and len(below) < len(stated)

    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert [str(item.ejercicio) for item in persona.work_income_none_statements] == [
        str(token) for token in stated if not token.precedes_floor(_LOWERED)
    ]
    left_out = [item for item in persona.below_floor if item.block == "work_income_none_statements"]
    assert [str(item.year) for item in left_out] == [str(token) for token in below]
    assert not any(item.history for item in left_out)
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED)


def test_records_and_expectations_of_supported_years_survive_a_lowered_horizon() -> None:
    document = _with_filed_returns(
        {"modelo": "303", "year": "horizon-1", "periods": ["1T"], "iva_compensation_carried_in": "0.00"},
        {"modelo": "303", "year": "horizon-2", "periods": ["4T"], "iva_compensation_carried_in": "0.00"},
    )
    expectations = copy.deepcopy(_document("expectations.toml"))
    stated = copy.deepcopy(expectations["values"][0])
    expectations["values"].append({**stated, "year": "horizon-2"})
    expectations["obligations"].append({**expectations["obligations"][0], "year": "horizon-2"})
    expectations["deadlines"].append({**expectations["deadlines"][0], "year": "horizon-2"})
    unchanged = _parse(document, expectations_document=expectations)

    persona = _parse(document, envelope=_LOWERED, expectations_document=expectations, omit_below_floor=True)

    assert unchanged.below_floor == ()
    assert [(block.modelo, str(block.year)) for block in persona.filed_returns] == [("303", "horizon-1")]
    for kept, every in (
        (persona.expectations.values, unchanged.expectations.values),
        (persona.expectations.obligations, unchanged.expectations.obligations),
        (persona.expectations.deadlines, unchanged.expectations.deadlines),
    ):
        assert kept == tuple(item for item in every if str(item.year) != "horizon-2")
    assert persona.prior_carries == tuple(item for item in unchanged.prior_carries if str(item.year) != "horizon-2")
    carries_dropped = {"prior_carries"} if len(persona.prior_carries) < len(unchanged.prior_carries) else set()
    assert {item.block for item in persona.below_floor} == {
        "expectations.deadlines",
        "expectations.obligations",
        "expectations.values",
        "filed_returns",
        "local_observations",
        "withholding_certificates",
        "work_income_none_statements",
        *carries_dropped,
    }
    assert sorted(item.block for item in persona.below_floor if item.history) == [
        "filed_returns",
        "local_observations",
    ]


@pytest.mark.parametrize(
    ("path", "token"),
    [
        (("persona", "fiscal_year"), "horizon-2"),
        (("persona", "fiscal_year"), "horizon+1"),
        (("clock", "as_of"), {"year": "horizon-2", "month": 2, "day": 16}),
    ],
)
def test_a_lowered_horizon_still_refuses_a_scenario_year_outside_the_envelope(
    path: tuple[str, ...], token: object
) -> None:
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(_changed(path, token), envelope=_LOWERED, omit_below_floor=True)


def test_a_lowered_horizon_still_refuses_a_history_record_above_the_horizon() -> None:
    document = _with_filed_returns({"modelo": "303", "year": "horizon+1", "periods": ["1T"]})
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED, omit_below_floor=True)


def test_a_literal_year_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="is not a year token"):
        _parse(_changed(("persona", "fiscal_year"), str(_ENVELOPE.horizon)))
