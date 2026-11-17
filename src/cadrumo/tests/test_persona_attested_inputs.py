"""The persona reader admits and refuses attested prior values and work inputs."""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

import pytest

from .persona_reader_support import _ENVELOPE, _LOWERED, _document, _parse
from .persona_types import PersonaCatalogueError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_ATTESTED_PRIOR_VALUE: dict[str, Any] = {
    "modelo": "130",
    "period": "1T",
    "year": "horizon-1",
    "binding": "irpf.previous_year_economic_activity_net_income",
    "value": "12846.30",
    "sources": [{"modelo": "100", "year": "horizon-2", "period": "0A"}],
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
    assert [(source.modelo, str(source.year), source.period) for source in item.sources] == [("100", "horizon-2", "0A")]
    assert item.legal_ref == ("rd-439-2007:art-110",)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"value": "12.846,30"}, "canonical decimal"),
        ({"value": 12846.3}, "canonical decimal"),
        ({"period": "5T"}, "is not a filing period"),
        ({"year": str(_ENVELOPE.floor)}, "not a year token"),
        ({"sources": [{"modelo": "100", "year": "horizon-2"}]}, "missing fields"),
        ({"sources": [{"modelo": "100", "year": "horizon-2", "period": "0A", "csv": "x"}]}, "unknown fields"),
        ({"sources": [{"modelo": "100", "year": "horizon-1", "period": "0A"}]}, "does not precede"),
        ({"sources": [{"modelo": "100", "year": "horizon-2", "period": "5T"}]}, "is not a filing period"),
        ({"sources": []}, "at least one earlier return"),
        ({"sources": [{"modelo": "100", "year": "horizon-2", "period": "0A"}] * 2}, "each earlier return once"),
        ({"source": {"modelo": "100", "year": "horizon-2", "period": "0A"}}, "unknown fields"),
        ({"derivation": ""}, "derivation must be a non-empty string"),
        ({"legal_ref": []}, "at least one provision"),
        ({"note": "extra"}, "unknown fields"),
    ],
)
def test_a_malformed_attested_prior_value_is_refused(changes: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_attested_prior_value(**changes))


def test_an_attested_prior_value_is_strict_unless_it_states_where_declared() -> None:
    (strict,) = _parse(_with_attested_prior_value()).attested_prior_values
    (flagged,) = _parse(_with_attested_prior_value(where_declared=True)).attested_prior_values
    (unflagged,) = _parse(_with_attested_prior_value(where_declared=False)).attested_prior_values

    assert (strict.where_declared, flagged.where_declared, unflagged.where_declared) == (False, True, False)


@pytest.mark.parametrize("value", ["true", 1, 0, None])
def test_where_declared_of_an_attested_prior_value_must_be_a_boolean(value: object) -> None:
    with pytest.raises(PersonaCatalogueError, match="where_declared must be a boolean"):
        _parse(_with_attested_prior_value(where_declared=value))


def test_an_annual_return_may_attest_one_figure_for_the_instalments_of_its_own_year() -> None:
    sources = [{"modelo": "202", "year": "horizon-1", "period": period} for period in ("1P", "2P", "3P")]
    (item,) = _parse(
        _with_attested_prior_value(modelo="200", period="0A", binding="instalments", sources=sources)
    ).attested_prior_values

    assert [source.period for source in item.sources] == ["1P", "2P", "3P"]


def test_an_instalment_may_attest_the_figure_its_base_reads_from_an_earlier_annual_return() -> None:
    sources = [{"modelo": "200", "year": "horizon-2", "period": "0A"}]
    (item,) = _parse(
        _with_attested_prior_value(modelo="202", period="1P", year="horizon", binding="base", sources=sources)
    ).attested_prior_values

    assert (item.modelo, item.period, str(item.year)) == ("202", "1P", "horizon")


@pytest.mark.parametrize(
    ("changes", "sources"),
    [
        ({"modelo": "200", "period": "0A"}, [{"modelo": "200", "year": "horizon-1", "period": "1P"}]),
        ({"modelo": "130", "period": "1T"}, [{"modelo": "202", "year": "horizon-1", "period": "1P"}]),
    ],
)
def test_a_same_year_source_precedes_only_an_annual_return_of_another_modelo(
    changes: dict[str, object], sources: list[dict[str, str]]
) -> None:
    with pytest.raises(PersonaCatalogueError, match="does not precede"):
        _parse(_with_attested_prior_value(**changes, sources=sources))


def test_an_attested_prior_value_listed_twice_is_refused() -> None:
    document = _with_attested_prior_value()
    document["attested_prior_values"].append(dict(_ATTESTED_PRIOR_VALUE))
    with pytest.raises(PersonaCatalogueError, match=r"attests .* twice"):
        _parse(document)


def test_an_attested_prior_value_may_name_a_source_below_the_floor_but_not_one_above_the_horizon() -> None:
    document = _with_attested_prior_value(sources=[{"modelo": "100", "year": "floor-3", "period": "0A"}])
    assert _parse(document).attested_prior_values
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(_with_attested_prior_value(sources=[{"modelo": "100", "year": "horizon+1", "period": "0A"}]))


def test_a_lowered_horizon_leaves_out_an_attested_prior_value_of_a_return_below_the_floor() -> None:
    document = _with_attested_prior_value(
        year="floor-1", sources=[{"modelo": "100", "year": "floor-2", "period": "0A"}]
    )
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED)
    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert persona.attested_prior_values == ()
    assert ("attested_prior_values", "130", "floor-1", ("1T",)) in [
        (item.block, item.modelo, str(item.year), item.periods) for item in persona.below_floor
    ]


_WORK_INPUT: dict[str, Any] = {
    "modelo": "100",
    "year": "horizon-1",
    "period": "0A",
    "roles": {"irpf_cuota_sindical": "120.00"},
    "sources": {"irpf_cuota_sindical": "Recibo anual de la cuota sindical"},
    "reason": "Ningún registro de la aplicación da la cuota sindical",
}


def _with_work_input(**changes: object) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    document["work_inputs"] = [{**_WORK_INPUT, **changes}]
    return document


def test_a_work_input_is_admitted_with_one_source_per_role() -> None:
    (item,) = _parse(_with_work_input()).work_inputs

    assert (item.modelo, str(item.year), item.period, item.reason) == (
        "100",
        "horizon-1",
        "0A",
        "Ningún registro de la aplicación da la cuota sindical",
    )
    assert item.roles == (("irpf_cuota_sindical", "120.00"),)
    assert item.sources == (("irpf_cuota_sindical", "Recibo anual de la cuota sindical"),)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"roles": {}}, "at least one role"),
        ({"roles": {"irpf_cuota_sindical": "120,00"}}, "canonical decimal"),
        ({"sources": {}}, r"none for \['irpf_cuota_sindical'\]"),
        ({"sources": {"irpf_cuota_sindical": "Recibo", "otro": "Otro"}}, r"does not give: \['otro'\]"),
        ({"sources": {"irpf_cuota_sindical": " "}}, "sources.irpf_cuota_sindical must be a non-empty string"),
        ({"reason": ""}, "reason must be a non-empty string"),
        ({"period": "5T"}, "is not one of"),
        ({"year": str(_ENVELOPE.floor)}, "not a year token"),
        ({"note": "extra"}, "unknown fields"),
    ],
)
def test_a_malformed_work_input_is_refused(changes: dict[str, object], message: str) -> None:
    with pytest.raises(PersonaCatalogueError, match=message):
        _parse(_with_work_input(**changes))


def test_a_work_input_missing_its_sources_or_reason_is_refused() -> None:
    for key in ("sources", "reason"):
        document = _with_work_input()
        del document["work_inputs"][0][key]
        with pytest.raises(PersonaCatalogueError, match="missing fields"):
            _parse(document)


def test_two_work_inputs_of_one_return_are_refused() -> None:
    document = _with_work_input()
    document["work_inputs"].append({**_WORK_INPUT, "roles": {"otro": "1.00"}, "sources": {"otro": "Recibo"}})
    with pytest.raises(PersonaCatalogueError, match="two work_inputs blocks"):
        _parse(document)


def test_a_work_input_asserted_back_as_an_expected_role_of_its_return_is_refused() -> None:
    # The persona's Modelo 100 horizon-1 expectations state this role.
    role = "irpf_deduccion_maternidad"
    document = _with_work_input(roles={role: "1.00"}, sources={role: "Recibo"})
    with pytest.raises(PersonaCatalogueError, match="asserts it back"):
        _parse(document)


def test_a_work_input_may_give_a_role_another_return_asserts() -> None:
    # The role is asserted for Modelo 100 horizon-1 and horizon-2; given on a horizon-3 return it asserts nothing back.
    role = "irpf_deduccion_maternidad"
    document = _with_work_input(year="horizon-3", roles={role: "1.00"}, sources={role: "Recibo"})
    (item,) = _parse(document).work_inputs
    assert str(item.year) == "horizon-3"


def test_a_lowered_horizon_leaves_out_a_work_input_of_a_return_below_the_floor() -> None:
    document = _with_work_input(year="floor-1")
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(document, envelope=_LOWERED)
    persona = _parse(document, envelope=_LOWERED, omit_below_floor=True)

    assert persona.work_inputs == ()
    assert ("work_inputs", "100", "floor-1", ("0A",)) in [
        (item.block, item.modelo, str(item.year), item.periods) for item in persona.below_floor
    ]


def test_a_work_income_statement_for_an_ejercicio_without_a_work_income_certificate_is_refused() -> None:
    document = copy.deepcopy(_document("persona.toml"))
    document["withholding_certificates"] = [
        item for item in document["withholding_certificates"] if item["income_class"] != "trabajo"
    ]
    assert document["work_income_none_statements"]
    with pytest.raises(PersonaCatalogueError, match="no work-income certificate for that ejercicio"):
        _parse(document)
