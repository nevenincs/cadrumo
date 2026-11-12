"""The persona reader admits the catalogue's contract and refuses a departure from it."""

from __future__ import annotations

import copy
import tomllib
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from .personas import (
    PERSONAS_ROOT,
    Persona,
    PersonaCatalogueError,
    ProvisionPeriods,
    YearEnvelope,
    YearToken,
    cadastral_control_characters,
    identity_catalogue,
    parse_identity_catalogue,
    parse_persona,
    values_in_force,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A synthetic envelope: the reader only shifts tokens against its bounds, so any ordered pair serves.
_ENVELOPE = YearEnvelope(floor=100, horizon=104)
_PERSONA = "asalariada-familia"


def _document(name: str) -> dict[str, Any]:
    return tomllib.loads((PERSONAS_ROOT / _PERSONA / name).read_text(encoding="utf-8"))


def _parse(
    persona_document: dict[str, Any],
    *,
    envelope: YearEnvelope = _ENVELOPE,
    expectations_document: dict[str, Any] | None = None,
    omit_below_floor: bool = False,
) -> Persona:
    return parse_persona(
        _PERSONA,
        persona_document=persona_document,
        ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_document("documents.toml"),
        expectations_document=_document("expectations.toml")
        if expectations_document is None
        else expectations_document,
        catalogue=identity_catalogue(),
        envelope=envelope,
        omit_below_floor=omit_below_floor,
    )


def _changed(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    table = document
    for key in path[:-1]:
        table = table[key]
    table[path[-1]] = value
    return document


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
        {"role": "a.titular", "persona": "a", "kind": "nif", "value": "00000006Y", **name, **fields}
    )


def test_a_natural_person_states_apellidos_and_nombre_and_an_entity_its_razon_social() -> None:
    person = parse_identity_catalogue(_one_identity()).role("a.titular")
    assert (person.primer_apellido, person.segundo_apellido, person.nombre) == ("Vidal", "Soler", "Andrés")
    assert person.is_entity is False
    assert person.surnames == "Vidal Soler"
    assert person.field("nombre") == "Andrés"
    entity = parse_identity_catalogue(
        _one_identity(kind="cif", value="B00000059", razon_social="Ediciones del Turia, S.L.")
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
            "value": "X0000001R",
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
    identity = {"role": "a.titular", "persona": "a", "value": "00000006Y", **fields}
    with pytest.raises(PersonaCatalogueError, match=message):
        parse_identity_catalogue(_identity_document(identity))


def test_an_identity_states_the_operators_rendering_for_a_narrower_field() -> None:
    identity: dict[str, object] = {
        "role": "a.titular",
        "persona": "a",
        "value": "00000006Y",
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


#: The synthetic envelope with its horizon lowered one year above the floor, as a replay of an earlier year reads it.
_LOWERED = YearEnvelope(floor=_ENVELOPE.floor, horizon=_ENVELOPE.floor + 1)


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


def _with_filed_returns(*blocks: dict[str, object]) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    document["filed_returns"] = list(blocks)
    return document


def test_a_filed_returns_block_is_admitted() -> None:
    _parse(
        _with_filed_returns(
            {"modelo": "303", "year": "horizon-1", "periods": ["1T", "2T"], "iva_compensation_carried_in": "0.00"},
            {"modelo": "130", "year": "horizon-1", "periods": ["3T"]},
        )
    )


@pytest.mark.parametrize(
    ("block", "message"),
    [
        ({"modelo": "303", "year": "horizon-1", "periods": ["2T", "1T"]}, "distinct and in calendar order"),
        ({"modelo": "303", "year": "horizon-1", "periods": ["1T", "1T"]}, "distinct and in calendar order"),
        ({"modelo": "303", "year": "horizon-1", "periods": ["5T"]}, "is not one of"),
        (
            {"modelo": "130", "year": "horizon-1", "periods": ["1T"], "iva_compensation_carried_in": "0.00"},
            "only a Modelo 303 block",
        ),
        ({"modelo": "303", "year": "horizon+1", "periods": ["1T"]}, "outside the supported envelope"),
        ({"modelo": "303", "periods": ["1T"]}, "missing"),
    ],
)
def test_a_malformed_filed_returns_block_is_refused(block: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_filed_returns(block))


def test_a_period_both_filed_and_calculated_is_refused() -> None:
    document = _with_filed_returns({"modelo": "130", "year": "horizon-1", "periods": ["1T", "2T"]})
    document["calculated_returns"] = [{"modelo": "130", "year": "horizon-1", "periods": ["2T"]}]
    with pytest.raises(PersonaCatalogueError, match="is listed twice"):
        _parse(document)


def test_the_cadastral_control_letters_follow_the_catastro_algorithm() -> None:
    # Catastro's own published example of an urban reference and its control letters.
    assert cadastral_control_characters("9872023VH5797S0001") == "WX"


def _with_leased_premises(**changes: object) -> dict[str, Any]:
    premises: dict[str, object] = {
        "key": "local",
        "landlord": "asalariada.empleador",
        "landlord_tax_status": "resident",
        "landlord_tax_regime": "irpf",
        "landlord_province": "28",
        "situation": "1",
        "cadastral_reference": "9872023VH5797S0001WX",
        "modality": "1",
        "address": {
            "province_code": "28",
            "municipality_code": "28079",
            "municipality": "Madrid",
            "locality": "Madrid",
            "postal_code": "28001",
            "street_type": "CL",
            "street_name": "Ejemplo",
            "number_type": "NUM",
            "house_number": "1",
        },
    }
    premises.update(changes)
    document = copy.deepcopy(_document("persona.toml"))
    document["leased_premises"] = [premises]
    return document


def test_leased_premises_with_a_valid_cadastral_reference_are_admitted() -> None:
    _parse(_with_leased_premises())


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"cadastral_reference": "9872023VH5797S0001WY"}, "do not match the Catastro algorithm"),
        ({"cadastral_reference": "9872023VH5797S0001"}, "20-character urban cadastral reference"),
        ({"landlord": "asalariada.desconocida"}, "unknown identity role"),
        ({"address": {"province_code": "28"}}, "missing fields"),
    ],
)
def test_malformed_leased_premises_are_refused(changes: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_leased_premises(**changes))


def _with_own_accounts(*accounts: dict[str, object]) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    document["own_accounts"] = list(accounts)
    return document


def _own_account(**changes: object) -> dict[str, object]:
    account: dict[str, object] = {
        "label": "Cuenta",
        "holding": "titular",
        "iban": "ES5500000000000000000001",
        "designations": [{"role": "refund", "modelo": "100"}],
    }
    account.update(changes)
    return account


def test_an_own_account_with_a_designation_is_admitted() -> None:
    _parse(_with_own_accounts(_own_account(iban="ES55 0000 0000 0000 0000 0001")))


@pytest.mark.parametrize(
    ("accounts", "message"),
    [
        ((_own_account(iban="ES5600000000000000000001"),), "checksum-valid"),
        ((_own_account(holding="apoderado"),), "is not one of"),
        ((_own_account(designations=[{"role": "payout"}]),), "is not one of"),
        ((_own_account(designations=[{"role": "refund", "modelo": "303"}]),), "persona's modelos"),
        ((_own_account(designations=[{"role": "refund", "year": "horizon"}]),), "unknown fields"),
        ((_own_account(), _own_account(iban="ES2800000000000000000002")), "one role and scope"),
    ],
)
def test_a_malformed_own_account_is_refused(accounts: tuple[dict[str, object], ...], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_own_accounts(*accounts))


def _with_prior_carries(*statements: dict[str, object]) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    document["prior_carries"] = list(statements)
    return document


def test_the_pending_carries_are_stated_as_nothing_pending_or_as_amounts_per_box() -> None:
    nothing, amounts = _parse(
        _with_prior_carries(
            {"year": "horizon-1", "nothing_pending": True},
            {"year": "horizon-2", "pending": {"1388": "1250.40", "1380": "300.00"}},
        )
    ).prior_carries
    assert (str(nothing.year), nothing.pending) == ("horizon-1", ())
    assert (str(amounts.year), amounts.pending) == (
        "horizon-2",
        (("1380", Decimal("300.00")), ("1388", Decimal("1250.40"))),
    )


@pytest.mark.parametrize(
    ("statements", "message"),
    [
        (({"year": "horizon-1", "pending": {"1381": "10.00"}},), "is not one of"),
        (({"year": "horizon-1", "pending": {"1380": "0.00"}},), "positive amount"),
        (({"year": "horizon-1", "pending": {"1380": "1.234,00"}},), "canonical decimal"),
        (({"year": "horizon-1", "pending": {}},), "at least one box"),
        (({"year": "horizon-1", "nothing_pending": False},), "only be stated true"),
        (({"year": "horizon-1"},), "either nothing_pending"),
        (({"year": "horizon-1", "nothing_pending": True, "pending": {"1380": "1.00"}},), "either nothing_pending"),
        (({"year": "horizon-1", "nothing_pending": True, "modelo": "100"},), "unknown fields"),
        (({"year": _ENVELOPE.horizon, "nothing_pending": True},), "not a year token"),
        (({"year": "horizon+1", "nothing_pending": True},), "outside the supported envelope"),
        (({"year": "floor-1", "nothing_pending": True},), "outside the supported envelope"),
        (
            ({"year": "horizon-1", "nothing_pending": True}, {"year": "floor+3", "pending": {"1380": "5.00"}}),
            "stated twice",
        ),
    ],
)
def test_a_malformed_pending_carry_statement_is_refused(
    statements: tuple[dict[str, object], ...], message: str
) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_prior_carries(*statements))


def test_a_pending_carry_statement_below_the_floor_is_omitted_under_a_lowered_horizon() -> None:
    document = _with_prior_carries(
        {"year": "horizon-1", "nothing_pending": True}, {"year": "horizon-2", "nothing_pending": True}
    )
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED)

    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert [str(statement.year) for statement in persona.prior_carries] == ["horizon-1"]
    assert ("prior_carries", "100", "horizon-2", ("0A",)) in [
        (item.block, item.modelo, str(item.year), item.periods) for item in persona.below_floor
    ]


def test_a_pending_carry_statement_needs_a_persona_that_files_modelo_100() -> None:
    document = _with_prior_carries({"year": "horizon-1", "nothing_pending": True})
    document["persona"]["modelos"] = ["303"]
    document.pop("own_accounts", None)
    with pytest.raises(PersonaCatalogueError, match="files no Modelo 100"):
        _parse(document)


def test_a_local_observation_needs_canonical_casilla_amounts() -> None:
    document = copy.deepcopy(_document("persona.toml"))
    observation = {"modelo": "100", "year": "horizon-2", "period": "0A", "reason": "Copia propia"}
    document["local_observations"] = [{**observation, "casillas": {"0224": "12846.30"}}]
    _parse(document)
    document["local_observations"] = [{**observation, "casillas": {"0224": "12.846,30"}}]
    with pytest.raises(PersonaCatalogueError):
        _parse(document)


_AEAT_FILING: dict[str, object] = {
    "modelo": "100",
    "year": "horizon-2",
    "period": "0A",
    "presented": {"year": "horizon-1", "month": 6, "day": 9},
    "csv": "T5LW2N8RJ6DQ3VYB",
    "justificante": "1004459817240",
    "casillas": {"0224": "12846.30"},
    "reason": "Renta del ejercicio anterior presentada",
}


def _with_aeat_filing(**changes: object) -> dict[str, Any]:
    """The persona with its prior-year Renta as an AEAT filing instead of its own copy."""
    document = copy.deepcopy(_document("persona.toml"))
    document.pop("local_observations", None)
    document["aeat_filings"] = [{**_AEAT_FILING, **changes}]
    return document


def test_an_aeat_filing_with_its_receipt_is_admitted() -> None:
    _parse(_with_aeat_filing())


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"csv": "t5lw2n8rj6dq3vyb"}, "16-character Código Seguro de Verificación"),
        ({"csv": "T5LW2N8RJ6DQ3"}, "16-character Código Seguro de Verificación"),
        ({"justificante": "100445981724"}, "13-digit número de justificante"),
        ({"casillas": {}}, "at least one casilla"),
        ({"casillas": {"0224": "12.846,30"}}, "canonical decimal"),
        ({"period": "0B"}, "is not one of"),
        ({"presented": {"year": "horizon-2", "month": 12, "day": 31}}, "presented before its period closes"),
    ],
)
def test_a_malformed_aeat_filing_is_refused(changes: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_aeat_filing(**changes))


def test_a_return_both_observed_locally_and_filed_with_the_aeat_is_refused() -> None:
    document = _with_aeat_filing()
    document["local_observations"] = [
        {"modelo": "100", "year": "horizon-2", "period": "0A", "casillas": {"0224": "1.00"}, "reason": "Copia"}
    ]
    with pytest.raises(PersonaCatalogueError, match="listed twice"):
        _parse(document)


def _with_inventory(*books: dict[str, object]) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    document["inventory"] = list(books)
    return document


_BOOK: dict[str, object] = {
    "activity": "servicios",
    "year": "horizon-1",
    "valuation_method": "fifo",
    "opening_stock": "0.00",
    "closing_stock": "0.00",
    "statement": "No existencias",
}


def test_an_inventory_book_with_no_movement_is_admitted() -> None:
    persona = parse_persona(
        _PERSONA,
        persona_document=_with_inventory(_BOOK),
        ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_document("documents.toml"),
        expectations_document=_document("expectations.toml"),
        catalogue=identity_catalogue(),
        envelope=_ENVELOPE,
    )
    (book,) = persona.inventory
    assert (book.activity, book.year.resolve(_ENVELOPE), book.opening_stock, book.closing_stock) == (
        "servicios",
        103,
        Decimal("0.00"),
        Decimal("0.00"),
    )


def test_a_book_with_purchases_may_close_away_from_its_opening() -> None:
    (book,) = _parse(_with_inventory({**_BOOK, "closing_stock": "10.00", "purchases": ["ROW-1", "ROW-2"]})).inventory

    assert (book.closing_stock, book.purchases) == (Decimal("10.00"), ("ROW-1", "ROW-2"))


@pytest.mark.parametrize(
    ("books", "message"),
    [
        (({**_BOOK, "closing_stock": "10.00"},), "closes at its opening stock"),
        (({**_BOOK, "purchases": "ROW-1"},), "purchases must be an array of strings"),
        (({**_BOOK, "opening_stock": "-1.00", "closing_stock": "-1.00"},), "nonnegative"),
        (({**_BOOK, "opening_stock": "0,00"},), "canonical decimal"),
        (({**_BOOK, "year": "horizon+1"},), "outside the supported envelope"),
        ((_BOOK, _BOOK), "listed twice"),
    ],
)
def test_a_malformed_inventory_book_is_refused(books: tuple[dict[str, object], ...], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_inventory(*books))


def _expectations_with(*, obligation: dict[str, object] | None = None, value: dict[str, object] | None = None) -> Any:
    document = copy.deepcopy(_document("expectations.toml"))
    if obligation is not None:
        document["obligations"][0].update(obligation)
    if value is not None:
        document["values"][0].update(value)
    return parse_persona(
        _PERSONA,
        persona_document=_document("persona.toml"),
        ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_document("documents.toml"),
        expectations_document=document,
        catalogue=identity_catalogue(),
        envelope=_ENVELOPE,
    ).expectations


def test_a_stated_refusal_names_the_error_code_and_its_reason() -> None:
    expectations = _expectations_with(
        value={
            "refusal": "ERROR_MODELO_WORK_INPUT_REQUIRED",
            "reason": "Casilla pendiente de un dato manual",
            "not_sourced": {},
        }
    )
    assert expectations.values[0].refusal == "ERROR_MODELO_WORK_INPUT_REQUIRED"
    assert expectations.values[0].refusal_stage == "calculate"


def test_a_stated_refusal_names_the_stage_that_refuses_a_completed_calculation() -> None:
    expectations = _expectations_with(
        value={
            "refusal": "REFUSED_MODELO_EXPORT_VALUE_OVERFLOW",
            "refusal_stage": "export",
            "reason": "El nombre no cabe en su campo del diseño",
            "not_sourced": {},
        }
    )
    assert (expectations.values[0].refusal, expectations.values[0].refusal_stage) == (
        "REFUSED_MODELO_EXPORT_VALUE_OVERFLOW",
        "export",
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({"refusal": "input required", "reason": "Casilla pendiente"}, "names the application error code"),
        ({"refusal": "ERROR_MODELO_WORK_INPUT_REQUIRED"}, "says in its reason why"),
        (
            {"refusal": "ERROR_MODELO_WORK_INPUT_REQUIRED", "refusal_stage": "file", "reason": "Pendiente"},
            "is not one of",
        ),
        ({"refusal_stage": "export", "reason": "Pendiente"}, "belongs to a stated refusal"),
    ],
)
def test_a_malformed_refusal_is_refused(value: dict[str, object], message: str) -> None:
    document = copy.deepcopy(_document("expectations.toml"))
    document["values"][0].pop("reason", None)
    with pytest.raises(PersonaCatalogueError, match=message):
        parse_persona(
            _PERSONA,
            persona_document=_document("persona.toml"),
            ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
            documents_document=_document("documents.toml"),
            expectations_document={**document, "values": [{**document["values"][0], **value}]},
            catalogue=identity_catalogue(),
            envelope=_ENVELOPE,
        )


def test_a_not_sourced_casilla_states_the_law_figure_and_the_missing_source() -> None:
    expectations = _expectations_with(
        value={"not_sourced": {"0013": "2332.80"}, "reason": "Ningún origen registra la cotización del certificado"}
    )
    assert expectations.values[0].not_sourced == (("0013", "2332.80"),)


def test_a_role_states_an_amount_keyed_by_a_casillas_registry_identity() -> None:
    expectations = _expectations_with(value={"roles": {"iva-resultado-regimen-general": "1377.60"}})
    assert expectations.values[0].roles == (("iva-resultado-regimen-general", "1377.60"),)


@pytest.mark.parametrize("amount", ["1377,60", "mil", "01.5", 1377])
def test_a_role_amount_that_is_not_a_canonical_decimal_is_refused(amount: object) -> None:
    with pytest.raises(PersonaCatalogueError, match="roles"):
        _expectations_with(value={"roles": {"iva-resultado-regimen-general": amount}})


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({"not_sourced": {"0013": "2332.80"}}, "says in its reason what source is missing"),
        (
            {"not_sourced": {"0013": "2332.80"}, "refusal": "ERROR_MODELO_WORK_INPUT_REQUIRED", "reason": "Pendiente"},
            "states none as not sourced",
        ),
        ({"not_sourced": {"0596": "5412.00"}, "reason": "Pendiente"}, "either compared or stated as not sourced"),
    ],
)
def test_a_malformed_not_sourced_casilla_is_refused(value: dict[str, object], message: str) -> None:
    document = copy.deepcopy(_document("expectations.toml"))
    document["values"][0].pop("reason", None)
    document["values"][0].pop("not_sourced", None)
    document["values"][0]["casillas"] = {"0596": "5412.00"}
    with pytest.raises(PersonaCatalogueError, match=message):
        parse_persona(
            _PERSONA,
            persona_document=_document("persona.toml"),
            ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
            documents_document=_document("documents.toml"),
            expectations_document={**document, "values": [{**document["values"][0], **value}]},
            catalogue=identity_catalogue(),
            envelope=_ENVELOPE,
        )


def test_a_calendar_advice_stands_in_for_an_owed_window() -> None:
    expectations = _expectations_with(obligation={"applicable": True, "calendar_advice": "applicable_window_missing"})
    assert expectations.obligations[0].calendar_advice == "applicable_window_missing"


@pytest.mark.parametrize(
    ("obligation", "message"),
    [
        ({"applicable": True, "calendar_advice": "window_late"}, "is not one of"),
        ({"applicable": False, "calendar_advice": "applicable_window_missing"}, "window row of an owed modelo"),
    ],
)
def test_a_malformed_calendar_advice_is_refused(obligation: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _expectations_with(obligation=obligation)


def _governed_expectations(*, provision: str = "provision-x") -> dict[str, Any]:
    """The persona's expectations with its first value, made plain, and a copy limited to ``provision``."""
    document = copy.deepcopy(_document("expectations.toml"))
    plain = document["values"][0]
    plain.pop("governed_by", None)
    governed = copy.deepcopy(plain)
    governed["governed_by"] = provision
    governed["legal_ref"] = [*plain["legal_ref"], "provision-x"]
    governed["derivation"] = "the figures the provision gives"
    document["values"] = [plain, governed]
    return document


def _parse_expectations(document: dict[str, Any]) -> Any:
    return parse_persona(
        _PERSONA,
        persona_document=_document("persona.toml"),
        ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_document("documents.toml"),
        expectations_document=document,
        catalogue=identity_catalogue(),
        envelope=_ENVELOPE,
    ).expectations


def _envelope_governing(first: int, last: int | None) -> YearEnvelope:
    from datetime import date

    return YearEnvelope(
        floor=_ENVELOPE.floor,
        horizon=_ENVELOPE.horizon,
        provisions=(
            (
                "provision-x",
                ProvisionPeriods(first=date(first, 1, 1), last=None if last is None else date(last, 12, 31)),
            ),
        ),
    )


def test_a_governed_value_replaces_the_plain_one_only_in_the_years_its_provision_governs() -> None:
    expectations = _parse_expectations(_governed_expectations())
    plain, governed = expectations.values
    year = plain.year.resolve(_ENVELOPE)

    inside = values_in_force(expectations.values, _envelope_governing(year, year))
    assert [value for _year, value in inside] == [governed]

    before = values_in_force(expectations.values, _envelope_governing(year + 1, None))
    after = values_in_force(expectations.values, _envelope_governing(_ENVELOPE.floor, year - 1))
    assert [value for _year, value in before] == [plain]
    assert [value for _year, value in after] == [plain]


def test_a_governed_value_cites_its_provision_among_its_legal_references() -> None:
    document = _governed_expectations(provision="provision-y")
    with pytest.raises(PersonaCatalogueError, match="one of its legal references"):
        _parse_expectations(document)


def test_values_of_one_period_following_two_provisions_in_the_same_year_are_refused() -> None:
    from datetime import date

    document = _governed_expectations()
    other = copy.deepcopy(document["values"][1])
    other["governed_by"] = "provision-z"
    other["legal_ref"] = [*other["legal_ref"], "provision-z"]
    document["values"].append(other)
    expectations = _parse_expectations(document)
    year = expectations.values[0].year.resolve(_ENVELOPE)
    every_year = ProvisionPeriods(first=date(year, 1, 1), last=None)
    envelope = YearEnvelope(
        floor=_ENVELOPE.floor,
        horizon=_ENVELOPE.horizon,
        provisions=(("provision-x", every_year), ("provision-z", every_year)),
    )
    with pytest.raises(PersonaCatalogueError, match="in the same year"):
        values_in_force(expectations.values, envelope)


def test_a_provision_the_envelope_does_not_carry_is_refused_rather_than_ignored() -> None:
    expectations = _parse_expectations(_governed_expectations())
    with pytest.raises(PersonaCatalogueError, match="does not carry the governed periods"):
        values_in_force(expectations.values, _ENVELOPE)


_ACCRUING = "minorista-recargo"


def _accruing_ledger(ibi_accrual: str) -> Any:
    """The minorista persona with its IBI row's accrual cells replaced by ``ibi_accrual``."""
    text = (PERSONAS_ROOT / _ACCRUING / "ledger.csv").read_text(encoding="utf-8")
    lines = [
        line.rsplit(",", 3)[0] + "," + ibi_accrual if line.startswith("MIN-IBI-1,") else line
        for line in text.splitlines()
    ]
    return parse_persona(
        _ACCRUING,
        persona_document=tomllib.loads((PERSONAS_ROOT / _ACCRUING / "persona.toml").read_text(encoding="utf-8")),
        ledger_text="\n".join(lines) + "\n",
        documents_document=tomllib.loads((PERSONAS_ROOT / _ACCRUING / "documents.toml").read_text(encoding="utf-8")),
        expectations_document=tomllib.loads(
            (PERSONAS_ROOT / _ACCRUING / "expectations.toml").read_text(encoding="utf-8")
        ),
        catalogue=identity_catalogue(),
        envelope=_ENVELOPE,
    )


def test_a_ledger_row_states_its_accrual_date_apart_from_the_movement() -> None:
    persona = _accruing_ledger("horizon-1,1,1")
    rows = {row.ref: row for row in persona.ledger}
    ibi = rows["MIN-IBI-1"]
    assert ibi.accrual_date(_ENVELOPE) == date(_ENVELOPE.horizon - 1, 1, 1)
    assert ibi.operation_date(_ENVELOPE) != ibi.accrual_date(_ENVELOPE)
    assert all(row.accrual_date(_ENVELOPE) is None for ref, row in rows.items() if ref != "MIN-IBI-1")


@pytest.mark.parametrize("cells", ["horizon-1,1,", "horizon-1,13,1", ",1,1"])
def test_an_incomplete_or_impossible_accrual_date_is_refused(cells: str) -> None:
    with pytest.raises(PersonaCatalogueError, match="accrual"):
        _accruing_ledger(cells)


_ATTESTED_PRIOR_VALUE: dict[str, Any] = {
    "modelo": "130",
    "period": "1T",
    "year": "horizon-1",
    "binding": "irpf.previous_year_economic_activity_net_income",
    "value": "12846.30",
    "source": {"modelo": "100", "year": "horizon-2", "period": "0A"},
    "derivation": "Rendimiento neto declarado en la renta del ejercicio anterior",
    "legal_ref": ["rd-439-2007:art-110"],
}


def _with_attested_prior_value(**changes: object) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    document["attested_prior_values"] = [{**_ATTESTED_PRIOR_VALUE, **changes}]
    return document


def test_an_attested_prior_value_is_admitted_with_its_source_and_derivation() -> None:
    (item,) = _parse(_with_attested_prior_value()).attested_prior_values

    assert (item.modelo, item.period, str(item.year), item.value) == ("130", "1T", "horizon-1", Decimal("12846.30"))
    assert (item.source.modelo, str(item.source.year), item.source.period) == ("100", "horizon-2", "0A")
    assert item.legal_ref == ("rd-439-2007:art-110",)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"value": "12.846,30"}, "canonical decimal"),
        ({"value": 12846.3}, "canonical decimal"),
        ({"period": "5T"}, "is not one of"),
        ({"year": str(_ENVELOPE.floor)}, "not a year token"),
        ({"source": {"modelo": "100", "year": "horizon-2"}}, "missing fields"),
        ({"source": {"modelo": "100", "year": "horizon-2", "period": "0A", "csv": "x"}}, "unknown fields"),
        ({"source": {"modelo": "100", "year": "horizon-1", "period": "0A"}}, "does not precede"),
        ({"derivation": ""}, "derivation must be a non-empty string"),
        ({"legal_ref": []}, "at least one provision"),
        ({"note": "extra"}, "unknown fields"),
    ],
)
def test_a_malformed_attested_prior_value_is_refused(changes: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_attested_prior_value(**changes))


def test_an_attested_prior_value_listed_twice_is_refused() -> None:
    document = _with_attested_prior_value()
    document["attested_prior_values"].append(dict(_ATTESTED_PRIOR_VALUE))
    with pytest.raises(PersonaCatalogueError, match=r"attests .* twice"):
        _parse(document)


def test_an_attested_prior_value_may_name_a_source_below_the_floor_but_not_one_above_the_horizon() -> None:
    document = _with_attested_prior_value(source={"modelo": "100", "year": "floor-3", "period": "0A"})
    assert _parse(document).attested_prior_values
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(_with_attested_prior_value(source={"modelo": "100", "year": "horizon+1", "period": "0A"}))


def test_a_lowered_horizon_leaves_out_an_attested_prior_value_of_a_return_below_the_floor() -> None:
    document = _with_attested_prior_value(year="floor-1", source={"modelo": "100", "year": "floor-2", "period": "0A"})
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED)
    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert persona.attested_prior_values == ()
    assert ("attested_prior_values", "130", "floor-1", ("1T",)) in [
        (item.block, item.modelo, str(item.year), item.periods) for item in persona.below_floor
    ]
