"""The dated IVA catalogues are read on the date the caller passes, never the day the program runs.

A date below the support floor is refused by the governed-fact gate with the
query year in the refusal, so a resolver that substituted the current date for
the one it was handed would answer where these must refuse. The same call on a
date inside the envelope resolves, which keeps the refusal attributable to the
date alone.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest

from ....core.iva_deduction_fact import IvaDeductionFactKind
from ...calculations.registry.errors import RegistryError
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..components import (
    registry_category_projection,
    registry_component_catalogue,
    registry_cuota_settlement_catalogue,
)
from ..deduction_facts import admits_iva_deduction_classification, required_deduction_evidence_authority
from ..errors import IvaError
from ..flow import IvaFlowDirection
from ..oss import resolve_oss_ioss_regime_catalogue
from ..schema import IvaCategory
from ..supply_nature import registry_citation_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_ENVELOPE = filing_year_envelope()
_INSIDE = date(_ENVELOPE.horizon, 6, 15)
_BELOW_FLOOR = date(_ENVELOPE.floor, 1, 1) - timedelta(days=1)

_READERS: dict[str, Callable[[date], object]] = {
    "deduction-authority": lambda on: required_deduction_evidence_authority(
        IvaDeductionFactKind.from_registry("domestic_current"), effective_date=on
    ),
    "deduction-admission": lambda on: admits_iva_deduction_classification(
        category=IvaCategory("domestic_general"),
        flow_direction=IvaFlowDirection.from_registry("soportado"),
        effective_date=on,
    ),
    "component-catalogue": lambda on: registry_component_catalogue(effective_date=on),
    "category-projection": lambda on: registry_category_projection("evidence_exempt", effective_date=on),
    "cuota-settlement": lambda on: registry_cuota_settlement_catalogue(effective_date=on),
    "oss-ioss": lambda on: resolve_oss_ioss_regime_catalogue(effective_date=on),
    "statutory-citations": lambda on: registry_citation_catalogue(effective_date=on),
}


@pytest.mark.parametrize("reader", sorted(_READERS))
def test_a_date_inside_the_envelope_resolves(reader: str) -> None:
    assert _READERS[reader](_INSIDE) is not None


@pytest.mark.parametrize("reader", sorted(_READERS))
def test_a_date_below_the_floor_is_refused_on_the_year_it_names(reader: str) -> None:
    with pytest.raises((IvaError, RegistryError), match=str(_BELOW_FLOOR.year)):
        _READERS[reader](_BELOW_FLOOR)
