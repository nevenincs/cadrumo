"""Contract tests for :class:`IvaTerritorialScope`.

The territorial-scope segmentation is grounded in Ley 37/1992 Art. 3.Dos
and Arts. 68-72; the five-member partition pins the values used by
on-disk fixtures, registry TOML selectors, and locale keys.
"""

from __future__ import annotations

import pytest

from ..classification import IvaTerritorialScope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_member_names_preserved() -> None:
    names = {member.name for member in IvaTerritorialScope}
    assert names == {
        "ES_MAINLAND",
        "ES_CANARIAS",
        "ES_CEUTA_MELILLA",
        "EU_MEMBER",
        "THIRD_COUNTRY",
    }


def test_string_values_preserved() -> None:
    assert IvaTerritorialScope.ES_MAINLAND.value == "es_mainland"
    assert IvaTerritorialScope.ES_CANARIAS.value == "es_canarias"
    assert IvaTerritorialScope.ES_CEUTA_MELILLA.value == "es_ceuta_melilla"
    assert IvaTerritorialScope.EU_MEMBER.value == "eu_member"
    assert IvaTerritorialScope.THIRD_COUNTRY.value == "third_country"


def test_strenum_value_lookup_round_trips() -> None:
    for member in IvaTerritorialScope:
        assert IvaTerritorialScope(member.value) is member


def test_set_is_closed() -> None:
    assert len(list(IvaTerritorialScope)) == 5
