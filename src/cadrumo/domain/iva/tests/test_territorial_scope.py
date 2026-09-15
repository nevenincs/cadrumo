"""Contract tests for :class:`IvaTerritorialScope`.

The territorial-scope segmentation is grounded in Ley 37/1992 Art. 3.Dos
and Arts. 68-72; the five-member partition pins the values used by
on-disk fixtures, registry TOML selectors, and locale keys.
"""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ..classification import IvaTerritorialScope, resolve_iva_classification_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_member_names_preserved(operation: PinnedAuthorityOperation) -> None:
    catalogue = resolve_iva_classification_catalogue(date(2025, 1, 1), operation=operation)
    names = {member.value.upper() for member in catalogue.territorial_scopes}
    assert names == {
        "ES_MAINLAND",
        "ES_CANARIAS",
        "ES_CEUTA_MELILLA",
        "EU_MEMBER",
        "THIRD_COUNTRY",
    }


def test_string_values_preserved() -> None:
    assert IvaTerritorialScope._from_registry("es_mainland").value == "es_mainland"
    assert IvaTerritorialScope._from_registry("es_canarias").value == "es_canarias"
    assert IvaTerritorialScope._from_registry("es_ceuta_melilla").value == "es_ceuta_melilla"
    assert IvaTerritorialScope._from_registry("eu_member").value == "eu_member"
    assert IvaTerritorialScope._from_registry("third_country").value == "third_country"


def test_strenum_value_lookup_round_trips(operation: PinnedAuthorityOperation) -> None:
    catalogue = resolve_iva_classification_catalogue(date(2025, 1, 1), operation=operation)
    for member in catalogue.territorial_scopes:
        assert catalogue.require_territorial_scope(member.value) == member


def test_set_is_closed(operation: PinnedAuthorityOperation) -> None:
    catalogue = resolve_iva_classification_catalogue(date(2025, 1, 1), operation=operation)
    assert len(catalogue.territorial_scopes) == 5
