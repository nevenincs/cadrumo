"""Registry declarations resolve through the canonical temporal selection, so a projected year reads its source edition.

A filing year no edition authors carries the newest authored edition forward, and the
registry declares no ceiling above its horizon. The Renta ledger and the M347/M349
counterpart readers must therefore answer such a year exactly as they answer the
edition it is projected from, and still refuse a modelo the registry does not know.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.errors import RegistrySnapshotError
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, projected_exercise
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from .. import counterpart
from ..renta_ledger import registry_renta_ledger_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNREGISTERED_MODELO = "999"
_PROJECTED_YEARS = (projected_exercise("100"), projected_exercise("100") + 3)


def test_the_newest_authored_year_resolves_its_declarations() -> None:
    year = newest_authored_edition("100")
    with private_authority_lease() as operation:
        declarations = registry_renta_ledger_declarations(modelo="100", filing_year=year, operation=operation)

    assert declarations["insurance.variant.general"].strip()


@pytest.mark.parametrize("year", _PROJECTED_YEARS)
def test_a_projected_year_reads_the_declarations_of_its_source_edition(year: int) -> None:
    source = newest_authored_edition("100")
    with private_authority_lease() as operation:
        assert operation.modelo_ids().count("100") == 1
        projected = registry_renta_ledger_declarations(modelo="100", filing_year=year, operation=operation)
        authored = registry_renta_ledger_declarations(modelo="100", filing_year=source, operation=operation)

    assert projected == authored


@pytest.mark.parametrize("year", [newest_authored_edition("100"), *_PROJECTED_YEARS])
def test_the_counterpart_catalogue_resolves_for_authored_and_projected_years(year: int) -> None:
    with private_authority_lease() as operation:
        catalogue = counterpart.registry_counterpart_catalogue(date(year, 12, 31), operation=operation)

    assert catalogue.model_kinds
    assert all(kinds for kinds in catalogue.model_kinds.values())


def test_a_modelo_the_registry_does_not_know_is_refused_with_a_typed_error() -> None:
    year = newest_authored_edition("100")
    with private_authority_lease() as operation:
        assert _UNREGISTERED_MODELO not in operation.modelo_ids()
        with pytest.raises(RegistrySnapshotError) as refused:
            registry_renta_ledger_declarations(modelo=_UNREGISTERED_MODELO, filing_year=year, operation=operation)

    assert refused.value.translated_message == "errors.snapshot.modelo_not_registered"
