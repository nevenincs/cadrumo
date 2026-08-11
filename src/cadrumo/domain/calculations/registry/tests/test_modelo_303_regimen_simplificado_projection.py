"""Typed reference proofs for Modelo 303 simplified-regime projection."""

from __future__ import annotations

import pytest

from .....core import (
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
)
from .....domain.iva import RegimenSimplificadoFilingRows
from .. import RegistryValidationError, project_m303_regimen_simplificado_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _activity_ref() -> M303RegimenSimplificadoActivityProjectionRef:
    return M303RegimenSimplificadoActivityProjectionRef(
        cohort=M303RegimenSimplificadoCohort.AGRICOLA,
        slot=1,
        field=M303RegimenSimplificadoActivityField.ACTIVITY_CODE,
    )


def test_non_applicable_projection_retains_the_typed_contract_without_source_text_inference() -> None:
    projected = project_m303_regimen_simplificado_rows(
        projection_refs=(_activity_ref(),),
        rows=RegimenSimplificadoFilingRows(ejercicio=2025, activities=()),
        orden=(),
        applicable=False,
        censo_iae_epigraphs=frozenset(),
    )

    assert projected == ()


def test_projection_rejects_missing_or_duplicate_typed_references() -> None:
    rows = RegimenSimplificadoFilingRows(ejercicio=2025, activities=())
    with pytest.raises(RegistryValidationError, match="requires typed"):
        project_m303_regimen_simplificado_rows(
            projection_refs=(),
            rows=rows,
            orden=(),
            applicable=False,
            censo_iae_epigraphs=frozenset(),
        )
    with pytest.raises(RegistryValidationError, match="duplicate"):
        project_m303_regimen_simplificado_rows(
            projection_refs=(_activity_ref(), _activity_ref()),
            rows=rows,
            orden=(),
            applicable=False,
            censo_iae_epigraphs=frozenset(),
        )
