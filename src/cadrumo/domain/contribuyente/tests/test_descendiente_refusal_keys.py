"""Every descendant-row refusal names the key it is about, and only that key.

The ``--descendiente`` boundary chooses its translated copy from the key a
refusal carries: only a refusal about ``NACIMIENTO`` may say that every row must
declare a birth date. A refusal that names no key, or the wrong one, is rendered
with a cause that did not happen, so each typed refusal is pinned to its key here.

A missing authority scope is a registry-authority failure rather than something
the operator typed, so it must not arrive as an answer-type refusal at all.
"""

from __future__ import annotations

import pytest

from ....core.errors.hierarchy import ProfileAnswerTypeError
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.governed_fact_scope import outside_governed_fact_validation
from ..descendant_facts import descendant_list_from_facts, parse_descendiente_flag
from ..guarderia_mensual import parse_guarderia_mensual
from ..meses_trabajo import parse_meses_trabajo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BIRTH = "NACIMIENTO=2018-04-01"


def _refusal_key(raw: str) -> object:
    with pytest.raises(ProfileAnswerTypeError) as raised:
        parse_descendiente_flag(raw)
    return (raised.value.context or {}).get("key")


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("DISCAPACIDAD=0", "NACIMIENTO"),
        ("NACIMIENTO=", "NACIMIENTO"),
        ("NACIMIENTO=2018-13-45", "NACIMIENTO"),
        (f"{_BIRTH},DISCAPACIDAD=50", "DISCAPACIDAD"),
        (f"{_BIRTH},DISCAPACIDAD=bogus", "DISCAPACIDAD"),
        (f"{_BIRTH},RELACION=cuñado", "RELACION"),
        (f"{_BIRTH},RENTAS=12.500", "RENTAS"),
        (f"{_BIRTH},RENTAS=-1", "RENTAS"),
        (f"{_BIRTH},ALTA_POSTERIOR_MES=13", "ALTA_POSTERIOR_MES"),
        (f"{_BIRTH},SEGUNDO_CICLO_INFANTIL_INICIO_MES=0", "SEGUNDO_CICLO_INFANTIL_INICIO_MES"),
        (f"{_BIRTH},GASTOS_GUARDERIA=-5", "GASTOS_GUARDERIA"),
        (f"{_BIRTH},MESES_TRABAJO=13", "MESES_TRABAJO"),
        (f"{_BIRTH},MESES_TRABAJO=1;1", "MESES_TRABAJO"),
        (f"{_BIRTH},GASTOS_GUARDERIA_MENSUAL=5", "GASTOS_GUARDERIA_MENSUAL"),
        (f"{_BIRTH},GASTOS_GUARDERIA_MENSUAL=5:-1", "GASTOS_GUARDERIA_MENSUAL"),
    ],
)
def test_each_flag_refusal_carries_the_key_it_is_about(raw: str, key: str) -> None:
    assert _refusal_key(raw) == key


def test_an_unknown_key_refusal_names_no_key() -> None:
    """The unknown token is operator text, so it never enters the envelope context."""
    assert _refusal_key(f"{_BIRTH},NOT_A_KEY=1") is None


@pytest.mark.parametrize(
    ("facts", "key"),
    [
        (
            {"renta_family.descendiente.0.birth_date": "2018-04-01", "renta_family.descendiente.0.relacion": "cuñado"},
            "renta_family.descendiente.0.relacion",
        ),
        (
            {"renta_family.descendiente.0.birth_date": "2018-04-01", "renta_family.descendiente.0.rentas_anuales": "x"},
            "renta_family.descendiente.0.rentas_anuales",
        ),
    ],
)
def test_a_stored_row_refusal_carries_its_fact_path(facts: dict[str, str], key: str) -> None:
    with pytest.raises(ProfileAnswerTypeError) as raised:
        descendant_list_from_facts(facts)
    assert (raised.value.context or {}).get("key") == key


@pytest.mark.parametrize(
    "raw",
    ["5:10;;6:10", "5:10;5:20", "5", "9-5:10", "x:10", "13:10", "5:1.5"],
)
def test_every_guarderia_mensual_refusal_carries_its_field(raw: str) -> None:
    with pytest.raises(ProfileAnswerTypeError) as raised:
        parse_guarderia_mensual(raw, field="FIELD")
    assert (raised.value.context or {}).get("key") == "FIELD"


@pytest.mark.parametrize("raw", ["5;;6", "5;5", "x", "13", "9-5"])
def test_every_meses_trabajo_refusal_carries_its_field(raw: str) -> None:
    with pytest.raises(ProfileAnswerTypeError) as raised:
        parse_meses_trabajo(raw, field="FIELD")
    assert (raised.value.context or {}).get("key") == "FIELD"


@pytest.mark.parametrize(
    "raw",
    [f"{_BIRTH},DISCAPACIDAD=0", f"{_BIRTH},RELACION=tutela"],
)
def test_a_missing_authority_scope_is_a_registry_failure_not_an_answer_refusal(raw: str) -> None:
    with outside_governed_fact_validation(), pytest.raises(RegistryValidationError) as raised:
        parse_descendiente_flag(raw)
    assert not isinstance(raised.value, ProfileAnswerTypeError)
