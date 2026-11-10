"""Stored form codes in core enums equal the codes the pinned registry cites from the official designs.

Records persist these tokens, so each enum keeps its value. Core cannot read the
registry, so this proves the two spellings agree, in both directions.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

import pytest

from .....core.aggregation import IntracomOperationType
from .....core.declaracion_idioma import DeclaracionIdioma
from .....core.foreign_asset_obligation import M720AssetClassCode
from .....core.prorrata_register import ProrrataActivityRowType
from .....core.result_disposition import ResultDisposition
from ..authority import PinnedAuthorityOperation
from ..form_codes import resolve_form_codes
from ..m347_threshold import resolve_counterpart_operation_claves
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT = "form-row-codes"


@pytest.mark.parametrize(
    ("vocabulary", "key"),
    [
        (DeclaracionIdioma, "aeat.declaracion.idioma_codes"),
        (M720AssetClassCode, "m720.asset_class_codes"),
        (ProrrataActivityRowType, "m303.prorrata.activity_row_types"),
        (ResultDisposition, "aeat.tipo_declaracion.codes"),
    ],
)
def test_an_enum_holds_exactly_the_codes_its_fact_declares(
    registry_authority: PinnedAuthorityOperation,
    vocabulary: type[StrEnum],
    key: str,
) -> None:
    assert {member.value for member in vocabulary} == resolve_form_codes(_FACT).codes(key)


@pytest.mark.parametrize("day", [date(year, 6, 30) for year in filing_year_envelope().years])
def test_the_modelo_349_enum_holds_exactly_the_claves_the_calculation_admits(
    registry_authority: PinnedAuthorityOperation,
    day: date,
) -> None:
    letters = {member.value for member in IntracomOperationType}
    assert letters == resolve_counterpart_operation_claves("349", effective_date=day)
    keys = resolve_form_codes("detail-m349-m210-catalogues", effective_date=day).codes("m349.operation_keys")
    assert letters == keys
