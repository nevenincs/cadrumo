"""Stored descendant yes/no flags read through the canonical boolean vocabulary."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.errors.hierarchy import ProfileAnswerTypeError
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..descendant_facts import descendant_list_from_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BIRTH_DATE = date(filing_year_envelope().horizon - 6, 4, 1).isoformat()

_PREFIX = "renta_family.descendiente.0."
_BASE = {f"{_PREFIX}birth_date": _BIRTH_DATE}

_YES = ["true", "1", "si", "sí", "yes", "verdadero", "TRUE"]
_NO = ["false", "0", "no", "n", "falso", "No"]
_FIELDS = [
    ("convivencia", "convive_con_contribuyente", True),
    ("custodia_compartida", "custodia_compartida", False),
]


@pytest.mark.parametrize(("stored", "attr", "default"), _FIELDS)
def test_absent_flag_keeps_its_documented_default(stored: str, attr: str, default: bool) -> None:
    (child,) = descendant_list_from_facts(dict(_BASE))
    assert getattr(child, attr) is default


@pytest.mark.parametrize(("stored", "attr", "default"), _FIELDS)
@pytest.mark.parametrize("word", _YES)
def test_stored_affirmative_words_read_true(stored: str, attr: str, default: bool, word: str) -> None:
    (child,) = descendant_list_from_facts({**_BASE, f"{_PREFIX}{stored}": word})
    assert getattr(child, attr) is True


@pytest.mark.parametrize(("stored", "attr", "default"), _FIELDS)
@pytest.mark.parametrize("word", _NO)
def test_stored_negative_words_read_false(stored: str, attr: str, default: bool, word: str) -> None:
    (child,) = descendant_list_from_facts({**_BASE, f"{_PREFIX}{stored}": word})
    assert getattr(child, attr) is False


@pytest.mark.parametrize(("stored", "attr", "default"), _FIELDS)
@pytest.mark.parametrize("word", ["maybe", "", "nope"])
def test_stored_unreadable_word_refuses_naming_its_key(stored: str, attr: str, default: bool, word: str) -> None:
    with pytest.raises(ProfileAnswerTypeError) as raised:
        descendant_list_from_facts({**_BASE, f"{_PREFIX}{stored}": word})
    assert (raised.value.context or {}).get("key") == f"{_PREFIX}{stored}"


def test_stored_non_numeric_discapacidad_refuses_naming_its_key() -> None:
    with pytest.raises(ProfileAnswerTypeError) as raised:
        descendant_list_from_facts({**_BASE, f"{_PREFIX}discapacidad": "bogus"})
    assert (raised.value.context or {}).get("key") == f"{_PREFIX}discapacidad"
