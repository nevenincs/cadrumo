"""``aeat app modelo bindings list`` reaches the Modelo 100 surface in every supported year.

The identity and ledger bindings are authored once, at the earliest edition
whose official design carries them. The live command must list them for every
year of the published support envelope, and list a ledger binding exactly when
that year's edition declares the casilla it fills.
"""

from __future__ import annotations

from functools import cache
from uuid import uuid4

import pytest

from ....application.modelo.query_read_operation import ModeloBindingsListRequest, _read_bindings_list
from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_snapshot,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODELO = "100"
_PERIOD = "0A"

_EVERY_EDITION = frozenset(
    {
        "renta-profile-tax-id",
        "renta-profile-display-name",
        "renta-profile-declaration-type",
        "renta-profile-marital-status",
        "renta-profile-taxpayer-birth-date",
        "renta-profile-spouse-tax-id",
        "renta-family-descendant-tax-id",
        "renta-family-ascendant-tax-id",
        "renta-certificado-trabajo-retenciones",
        "renta-base-liquidable-negativa-general-anterior",
    }
)

_LEDGER_CASILLA_BINDINGS = {
    "0171": "renta-ledger-income-0171",
    "0183": "renta-ledger-expense-0183-deductible",
    "0195": "renta-ledger-expense-0195-deductible",
    "0217": "renta-ledger-expense-0217-deductible",
}


@cache
def _supported_years() -> tuple[int, ...]:
    return PublishedGovernedFactSource().supported_filing_years().years


@pytest.mark.parametrize("filing_year", _supported_years())
def test_bindings_list_carries_the_identity_and_ledger_surface(filing_year: int) -> None:
    """The registered application query lists every binding in each edition."""
    with bundled_indexed_authority().operation() as operation:
        result = _read_bindings_list(
            ModeloBindingsListRequest(profile_id=uuid4(), modelo=_MODELO, year=filing_year, period_code=_PERIOD),
            operation=operation,
        )
    listed = {row.binding_id for row in result.bindings}

    assert listed >= _EVERY_EDITION, sorted(_EVERY_EDITION - listed)
    snapshot = published_snapshot(
        _MODELO, filing_year=filing_year, period=_PERIOD, grade=RegistryAuthorityGrade.CALCULATION
    )
    declared = {casilla.id for casilla in snapshot.revision.casillas}
    for casilla_id, binding_id in _LEDGER_CASILLA_BINDINGS.items():
        assert (binding_id in listed) is (casilla_id in declared), (filing_year, casilla_id, binding_id)
