"""The frozen Modelo 200 page-qualified table agrees with every edition the registry serves.

The read seam moves a bare PyG id only when the row's stamped revision no longer
declares it and declares its qualified replacement. If a table entry named a
qualified id no edition declares, the move would never happen and the earlier
return's box would read as unobserved; this check catches such a typo per year.
"""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.casilla_membership import declared_casilla_ids
from ....domain.calculations.registry.errors import RegistryError
from ..prior_filing_page_qualified_reads import MODELO_200_PAGE_QUALIFIED_CASILLAS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_modelo_200_edition_declares_each_qualified_id_and_retires_its_bare_id() -> None:
    checked: list[int] = []
    with bundled_indexed_authority().operation() as operation:
        for year in sorted(operation.supported_filing_years().years):
            try:
                snapshot = operation.snapshot(
                    "200", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
                )
            except RegistryError:
                continue
            declared = declared_casilla_ids(snapshot.revision)
            for bare, qualified in MODELO_200_PAGE_QUALIFIED_CASILLAS.items():
                assert qualified in declared, (year, qualified)
                assert bare not in declared, (year, bare)
            checked.append(year)
    assert checked
