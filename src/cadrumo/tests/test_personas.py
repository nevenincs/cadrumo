"""The persona reader admits the catalogue's contract and refuses a departure from it."""

from __future__ import annotations

import copy
import tomllib
from decimal import Decimal
from typing import Any

import pytest

from .personas import (
    PERSONAS_ROOT,
    PersonaCatalogueError,
    ProvisionPeriods,
    YearEnvelope,
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


def _parse(persona_document: dict[str, Any], *, envelope: YearEnvelope = _ENVELOPE) -> None:
    parse_persona(
        _PERSONA,
        persona_document=persona_document,
        ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_document("documents.toml"),
        expectations_document=_document("expectations.toml"),
        catalogue=identity_catalogue(),
        envelope=envelope,
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


def _one_identity(**fields: object) -> dict[str, object]:
    identity = {"role": "a.titular", "persona": "a", "kind": "nif", "value": "00000006Y", **fields}
    return {"format": 1, "convention": {}, "identities": [identity]}


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


def test_a_local_observation_needs_canonical_casilla_amounts() -> None:
    document = copy.deepcopy(_document("persona.toml"))
    observation = {"modelo": "100", "year": "horizon-2", "period": "0A", "reason": "Copia propia"}
    document["local_observations"] = [{**observation, "casillas": {"0224": "12846.30"}}]
    _parse(document)
    document["local_observations"] = [{**observation, "casillas": {"0224": "12.846,30"}}]
    with pytest.raises(PersonaCatalogueError):
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


@pytest.mark.parametrize(
    ("books", "message"),
    [
        (({**_BOOK, "closing_stock": "10.00"},), "closes at its opening stock"),
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


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({"refusal": "input required", "reason": "Casilla pendiente"}, "names the application error code"),
        ({"refusal": "ERROR_MODELO_WORK_INPUT_REQUIRED"}, "says in its reason why"),
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
    """The persona's expectations with a second copy of its first value limited to ``provision``."""
    document = copy.deepcopy(_document("expectations.toml"))
    plain = document["values"][0]
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
