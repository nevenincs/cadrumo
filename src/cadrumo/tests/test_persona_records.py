"""The persona reader admits and refuses the return, premises, account, carry, filing, inventory and profile-row records."""

from __future__ import annotations

import copy
import tomllib
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from .persona_identities import identity_catalogue
from .persona_reader_support import _ENVELOPE, _LOWERED, _PERSONA, _document, _parse, _with_filed_returns
from .persona_sections import cadastral_control_characters
from .persona_types import PERSONAS_ROOT, IdentityRef, Persona, PersonaCatalogueError, PersonaDate
from .personas import parse_persona

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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


_GENERAL = "renta_negative_general_bases_pending"


_SAVINGS = "renta_negative_savings_capital_income_pending"


def test_the_pending_carries_are_stated_as_nothing_pending_or_as_amounts_per_box() -> None:
    nothing, amounts, savings = _parse(
        _with_prior_carries(
            {"year": "horizon-1", "family": _GENERAL, "nothing_pending": True},
            {"year": "horizon-2", "family": _GENERAL, "pending": {"1388": "1250.40", "1380": "300.00"}},
            {"year": "horizon-1", "family": _SAVINGS, "nothing_pending": True},
        )
    ).prior_carries
    assert (str(nothing.year), nothing.family, nothing.pending) == ("horizon-1", _GENERAL, ())
    assert (str(amounts.year), amounts.family, amounts.pending) == (
        "horizon-2",
        _GENERAL,
        (("1380", Decimal("300.00")), ("1388", Decimal("1250.40"))),
    )
    assert (savings.family, savings.pending) == (_SAVINGS, ())


def _carry(**keys: object) -> dict[str, object]:
    return {"year": "horizon-1", "family": _GENERAL, **keys}


@pytest.mark.parametrize(
    ("statements", "message"),
    [
        ((_carry(pending={"1381": "10.00"}),), "is not one of"),
        ((_carry(pending={"1380": "0.00"}),), "positive amount"),
        ((_carry(pending={"1380": "1.234,00"}),), "canonical decimal"),
        ((_carry(pending={}),), "at least one box"),
        ((_carry(nothing_pending=False),), "only be stated true"),
        ((_carry(),), "either nothing_pending"),
        ((_carry(nothing_pending=True, pending={"1380": "1.00"}),), "either nothing_pending"),
        ((_carry(nothing_pending=True, modelo="100"),), "unknown fields"),
        ((_carry(year=_ENVELOPE.horizon, nothing_pending=True),), "not a year token"),
        ((_carry(year="horizon+1", nothing_pending=True),), "outside the supported envelope"),
        ((_carry(year="floor-1", nothing_pending=True),), "outside the supported envelope"),
        (({"year": "horizon-1", "nothing_pending": True},), "missing fields"),
        ((_carry(family="Savings carry", nothing_pending=True),), "not a carry family token"),
        ((_carry(family=7, nothing_pending=True),), "not a carry family token"),
        ((_carry(family=_SAVINGS, pending={"abc": "1.00"}),), "four-digit casilla"),
        (
            (
                _carry(nothing_pending=True),
                _carry(year="floor+3", pending={"1380": "5.00"}),
                _carry(nothing_pending=True),
            ),
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
        {"year": "horizon-1", "family": "renta_negative_general_bases_pending", "nothing_pending": True},
        {"year": "horizon-2", "family": "renta_negative_general_bases_pending", "nothing_pending": True},
    )
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED)

    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert [str(statement.year) for statement in persona.prior_carries] == ["horizon-1"]
    assert ("prior_carries", "100", "horizon-2", ("0A",)) in [
        (item.block, item.modelo, str(item.year), item.periods) for item in persona.below_floor
    ]


def test_a_pending_carry_statement_needs_a_persona_that_files_modelo_100() -> None:
    document = _with_prior_carries(
        {"year": "horizon-1", "family": "renta_negative_general_bases_pending", "nothing_pending": True}
    )
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


def _with_profile_row(**changes: object) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    row: dict[str, object] = {
        "section": "some_section",
        "values": {
            "nif": {"identity": "asalariada.titular"},
            "apellidos_y_nombre": {"identity": "asalariada.titular", "field": "full_name"},
            "fecha_poder": {"year": "horizon-2", "month": 3, "day": 4},
            "notaria_otros": "NOTARIA DE PRUEBA",
            "representante": False,
        },
    }
    document["profile_rows"] = [{**row, **changes}]
    return document


def test_a_profile_row_keeps_its_section_and_typed_values() -> None:
    persona = _parse(_with_profile_row())
    (row,) = persona.profile_rows
    values = dict(row.values)

    assert row.section == "some_section"
    assert list(values) == sorted(values)
    assert values["notaria_otros"] == "NOTARIA DE PRUEBA"
    assert values["representante"] is False
    assert isinstance(values["fecha_poder"], PersonaDate)
    assert values["apellidos_y_nombre"] == IdentityRef(role="asalariada.titular", field="full_name")


def test_a_profile_row_date_may_precede_the_floor_but_not_pass_the_horizon() -> None:
    early = _with_profile_row(values={"fecha_poder": {"year": "floor-6", "month": 1, "day": 10}})
    (row,) = _parse(early).profile_rows
    (key, value), *_ = row.values
    assert key == "fecha_poder"
    assert isinstance(value, PersonaDate)
    assert value.resolve(_ENVELOPE) == date(_ENVELOPE.floor - 6, 1, 10)
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(_with_profile_row(values={"fecha_poder": {"year": "horizon+1", "month": 1, "day": 10}}))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"section": "activities"}, "has its own block"),
        ({"values": {}}, "at least one field"),
        ({"values": {"nif": {"identity": "fontanero.titular"}}}, "belongs to persona"),
        ({"values": {"nif": {"identity": "asalariada.titular", "field": "cargo"}}}, "is not one of"),
        ({"note": "x"}, "unknown fields"),
    ],
)
def test_a_malformed_profile_row_is_refused(changes: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_profile_row(**changes))


_LETTING = "arrendador-jubilado"


def _parse_letting(persona_document: dict[str, Any]) -> Persona:
    folder = PERSONAS_ROOT / _LETTING
    return parse_persona(
        _LETTING,
        persona_document=persona_document,
        ledger_text=(folder / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=tomllib.loads((folder / "documents.toml").read_text(encoding="utf-8")),
        expectations_document=tomllib.loads((folder / "expectations.toml").read_text(encoding="utf-8")),
        catalogue=identity_catalogue(),
        envelope=_ENVELOPE,
        omit_below_floor=False,
    )


def _letting_document(**changes: object) -> dict[str, Any]:
    document = tomllib.loads((PERSONAS_ROOT / _LETTING / "persona.toml").read_text(encoding="utf-8"))
    document["rental_properties"][0].update(changes)
    return document


def test_a_rental_property_states_its_letting_start_or_leaves_it_unstated() -> None:
    unstated = _letting_document()
    del unstated["rental_properties"][0]["arrendado_desde"]
    assert _parse_letting(unstated).rental_properties[0].arrendado_desde is None

    stated = _parse_letting(_letting_document(arrendado_desde={"year": "horizon-2", "month": 6, "day": 1}))

    start = stated.rental_properties[0].arrendado_desde
    assert start is not None
    assert (start.month, start.day) == (6, 1)


def test_a_malformed_letting_start_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match=r"month must be 1..12"):
        _parse_letting(_letting_document(arrendado_desde={"year": "horizon-2", "month": 13, "day": 1}))
