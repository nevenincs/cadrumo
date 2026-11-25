"""The filing runtime builds an export schema for an authored year and refuses one no edition authors.

Local export renders its fichero through the schema provider this module builds, so a
year the registry only carries across from the nearest edition cannot produce an
official-format file, while the year authored by that edition still can.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, projected_exercise
from ..runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "100"


def test_the_newest_authored_year_builds_an_export_schema() -> None:
    year = newest_authored_edition(_MODELO)

    provider = build_runtime_schema_provider(
        filing_year=year, period=Period.from_year_and_code(year, "0A"), modelos=(_MODELO,)
    )

    snapshot = provider.get_snapshot(_MODELO)
    assert snapshot.filing_year == year
    assert snapshot.revision.export_layouts


def test_a_projected_year_builds_no_export_schema() -> None:
    year = projected_exercise(_MODELO)

    with pytest.raises(RegistryValidationError) as refused:
        build_runtime_schema_provider(
            filing_year=year, period=Period.from_year_and_code(year, "0A"), modelos=(_MODELO,)
        )

    assert refused.value.translated_message == "errors.snapshot.filing_year_projected"
    failure = refused.value.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
    assert failure.facts["authored_filing_year"] == newest_authored_edition(_MODELO)
