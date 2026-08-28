"""Source-shape contract for pre-map Modelo 390 repeated-row references."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from .. import (
    FilingProjectionRef,
    M390ActivityField,
    M390DifferentiatedDeductionProjectionField,
    M390ProrrataActivityProjectionField,
    M390RegimenSimplificadoActivityField,
    M390RegimenSimplificadoCohort,
    M390RegimenSimplificadoModuleValue,
    M390RepresentativeField,
    M390RepresentativeKind,
    compile_filing_projection_ref,
    filing_projection_ref_casilla_id,
)
from .._filing_projection_ref import (
    M390ActivityProjectionRef,
    M390DifferentiatedDeductionProjectionRef,
    M390ProrrataActivityProjectionRef,
    M390RegimenSimplificadoActivityProjectionRef,
    M390RegimenSimplificadoModuleProjectionRef,
    M390RepresentativeProjectionRef,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_all_six_m390_repeated_row_reference_families_are_flat_and_closed() -> None:
    """Each source family is one union member, never a raw open-ended payload."""
    references: tuple[FilingProjectionRef, ...] = (
        M390ActivityProjectionRef(projection_kind="m390_activity", slot=6, field=M390ActivityField.IAE_EPIGRAFE),
        M390RepresentativeProjectionRef(
            projection_kind="m390_representative",
            representative_kind=M390RepresentativeKind.JURIDICA,
            slot=3,
            field=M390RepresentativeField.NOTARIA,
        ),
        M390RegimenSimplificadoActivityProjectionRef(
            projection_kind="m390_regimen_simplificado_activity",
            cohort=M390RegimenSimplificadoCohort.AGRICOLA_GANADERA,
            slot=5,
            field=M390RegimenSimplificadoActivityField.CUOTA_DERIVADA_REGIMEN_SIMPLIFICADO,
        ),
        M390RegimenSimplificadoModuleProjectionRef(
            projection_kind="m390_regimen_simplificado_module",
            slot=2,
            module_order=7,
            value=M390RegimenSimplificadoModuleValue.IMPORTE,
        ),
        M390ProrrataActivityProjectionRef(
            projection_kind="m390_prorrata_activity",
            slot=5,
            field=M390ProrrataActivityProjectionField.PORCENTAJE,
        ),
        M390DifferentiatedDeductionProjectionRef(
            projection_kind="m390_differentiated_deduction",
            slot=3,
            field=M390DifferentiatedDeductionProjectionField.TOTAL,
        ),
    )

    adapter: TypeAdapter[FilingProjectionRef] = TypeAdapter(FilingProjectionRef)
    assert tuple(adapter.validate_python(reference) for reference in references) == references
    assert all(filing_projection_ref_casilla_id(reference) is None for reference in references)
    assert all("casilla_id" not in type(reference).model_fields for reference in references)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"projection_kind": "m390_unknown", "slot": 1, "field": "cnae"},
            "union_tag_invalid",
        ),
        (
            {"projection_kind": "m390_activity", "slot": 7, "field": "activity_code"},
            "less_than_equal",
        ),
        (
            {
                "projection_kind": "m390_representative",
                "representative_kind": "fisica_comunidad_bienes",
                "slot": 2,
                "field": "nif",
            },
            "physical/community",
        ),
        (
            {
                "projection_kind": "m390_regimen_simplificado_activity",
                "cohort": "no_agricola",
                "slot": 3,
                "field": "iae_epigrafe",
            },
            "non-agricultural",
        ),
        (
            {
                "projection_kind": "m390_regimen_simplificado_activity",
                "cohort": "agricola_ganadera",
                "slot": 1,
                "field": "iae_epigrafe",
            },
            "agricultural",
        ),
        (
            {
                "projection_kind": "m390_regimen_simplificado_module",
                "slot": 1,
                "module_order": 8,
                "value": "units",
            },
            "less_than_equal",
        ),
        (
            {"projection_kind": "m390_prorrata_activity", "slot": 6, "field": "cnae"},
            "less_than_equal",
        ),
        (
            {"projection_kind": "m390_differentiated_deduction", "slot": 4, "field": "total"},
            "less_than_equal",
        ),
    ],
)
def test_m390_reference_compiler_refuses_unknown_families_and_source_shape_mutations(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises((ValidationError, ValueError), match=message):
        compile_filing_projection_ref(payload)


def test_m390_compiler_retains_exact_string_and_integer_wire_guards() -> None:
    """A bool slot or padded family token must not select an adjacent row."""
    with pytest.raises(ValueError, match="exact integer"):
        compile_filing_projection_ref(
            {"projection_kind": "m390_prorrata_activity", "slot": True, "field": "cnae"},
        )
    with pytest.raises(ValueError, match="must not contain surrounding whitespace"):
        compile_filing_projection_ref(
            {"projection_kind": " m390_prorrata_activity ", "slot": 1, "field": "cnae"},
        )
