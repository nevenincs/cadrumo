"""The persona reader admits and refuses expected refusals, advice, governed values and ledger accruals."""

from __future__ import annotations

import copy
import tomllib
from datetime import date
from typing import Any

import pytest

from .persona_expectations import values_in_force
from .persona_identities import identity_catalogue
from .persona_reader_support import _ENVELOPE, _PERSONA, _document
from .persona_types import PERSONAS_ROOT, PersonaCatalogueError, ProvisionPeriods, YearEnvelope
from .personas import parse_persona

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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
