"""The frozen Modelo 200 page-qualified table agrees with every edition the registry serves.

The read seam moves a bare id only when the row's stamped revision no longer
declares it and declares its qualified replacement. If a table entry named a
qualified id no edition declares, the move would never happen and the earlier
return's box would read as unobserved; this check catches such a typo.

Each edition is checked for the complementary defect: declaring an entry's bare
id and its qualified replacement at once, which would leave the stored figure
readable under two names in one edition. An edition that declares neither prints
no such box, which is the case for a number a later design introduced.
"""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.casilla_membership import declared_casilla_ids
from ....domain.calculations.registry.errors import RegistryError
from ..prior_filing_page_qualified_reads import MODELO_200_PAGE_QUALIFIED_CASILLAS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_modelo_200_edition_retires_each_bare_id_it_qualified() -> None:
    checked: list[int] = []
    serving: dict[str, list[int]] = {qualified: [] for qualified in MODELO_200_PAGE_QUALIFIED_CASILLAS.values()}
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
                assert bare not in declared, (year, bare)
                if qualified in declared:
                    serving[qualified].append(year)
            checked.append(year)
    assert checked
    for qualified, years in serving.items():
        assert years, qualified
