"""A value stated by a casilla's registry identity is compared at the casilla of the return's own edition."""

from __future__ import annotations

import dataclasses
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import ExpectedValue, Persona, YearEnvelope, YearToken, persona_ids, read_persona

from ..roles import compared, differing, edition_identities, mismatch_text, resolve, unresolved_roles
from ..rows import GREEN, Stage, TableRow, Verdict, planned_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_RESULT = "iva-resultado-regimen-general"
"""The continuity key of the Modelo 303 regime-general result, printed as box 46 of the official design."""
_RESULT_ROLE = "iva_resultado_regimen_general"
_RESULT_BOX = "46"
_SHARED_ROLE = "irpf_pf_importe"
"""A semantic role Modelo 130 gives to more than one casilla."""
_ABSENT = "dr303-46"
_QUARTER = "1T"


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _years() -> range:
    envelope = _envelope()
    return range(envelope.floor, envelope.horizon + 1)


def _form_number(modelo: str, year: int, casilla_id: str) -> str | None:
    with bundled_indexed_authority().operation() as operation:
        revision = operation.revision_for_context(modelo, filing_year=year, period=_QUARTER)
    return next(str(casilla.form_number) for casilla in revision.casillas if str(casilla.id) == casilla_id)


def _value(modelo: str, *roles: tuple[str, str]) -> ExpectedValue:
    return ExpectedValue(
        modelo=modelo,
        period=_QUARTER,
        year=YearToken(anchor="horizon", offset=-1),
        counterparty=None,
        casillas=(),
        concepts=(),
        parameters=(),
        derivation=None,
        legal_ref=("ley:art-1",),
        grounding="verified",
        reason=None,
        roles=roles,
    )


def _persona(*values: ExpectedValue) -> Persona:
    persona = read_persona(persona_ids()[0], envelope=_envelope())
    expectations = dataclasses.replace(persona.expectations, values=values, obligations=())
    return dataclasses.replace(persona, expectations=expectations, filed_returns=(), calculated_returns=())


def _passed_row(*values: ExpectedValue) -> TableRow:
    (plan,) = planned_rows(_persona(*values), _envelope().horizon, _envelope())
    return TableRow.from_plan(plan, Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED)


@pytest.mark.parametrize("key", [_RESULT, _RESULT_ROLE])
def test_a_role_resolves_to_the_box_the_official_design_prints_in_every_supported_year(key: str) -> None:
    for year in _years():
        casilla = resolve(edition_identities("303", year, _QUARTER), key)
        assert casilla is not None
        assert _form_number("303", year, casilla) == _RESULT_BOX


def test_a_resolved_role_is_compared_at_its_casilla_and_passes_or_names_the_mismatch() -> None:
    year = _envelope().horizon - 1
    casillas = edition_identities("303", year, _QUARTER)
    casilla = resolve(casillas, _RESULT)
    assert casilla is not None
    stated = compared([_value("303", (_RESULT, "1377.60"))], casillas, ())
    assert differing(stated, {casilla: "1377.6"}) == []
    ((item, found),) = differing(stated, {casilla: "1000.00"})
    assert mismatch_text(item, found) == f"role {_RESULT} (casilla {casilla}) exp 1377.60 got 1000.00"


def test_a_resolved_role_is_not_unchecked_and_its_row_can_pass() -> None:
    value = _value("303", (_RESULT, "1377.60"))
    assert unresolved_roles(value, _envelope().horizon - 1) == set()
    row = _passed_row(value)
    assert row.has_values
    assert row.unchecked == ()
    assert row.verdict is Verdict.PASSED


def test_a_role_absent_from_the_registry_is_unchecked_and_never_a_pass() -> None:
    value = _value("303", (_RESULT, "1377.60"), (_ABSENT, "1377.60"))
    assert resolve(edition_identities("303", _envelope().horizon - 1, _QUARTER), _ABSENT) is None
    row = _passed_row(value)
    assert row.unchecked == (f"role:{_ABSENT}",)
    assert row.verdict is Verdict.UNCHECKED
    assert row.verdict not in GREEN


def test_a_role_several_casillas_share_is_unchecked() -> None:
    year = _envelope().horizon - 1
    casillas = edition_identities("130", year, _QUARTER)
    assert sum(item.semantic_role == _SHARED_ROLE for item in casillas) > 1
    assert resolve(casillas, _SHARED_ROLE) is None
    row = _passed_row(_value("130", (_SHARED_ROLE, "10.00")))
    assert row.unchecked == (f"role:{_SHARED_ROLE}",)
    assert row.verdict is Verdict.UNCHECKED


def test_an_unresolved_role_the_row_does_not_list_stays_compared_against_no_value() -> None:
    year = _envelope().horizon - 1
    casillas = edition_identities("303", year, _QUARTER)
    value = _value("303", (_ABSENT, "5.00"))
    assert compared([value], casillas, (f"role:{_ABSENT}",)) == []
    ((item, found),) = differing(compared([value], casillas, ()), {})
    assert (mismatch_text(item, found), found) == (f"role {_ABSENT} exp 5.00 got None", None)
