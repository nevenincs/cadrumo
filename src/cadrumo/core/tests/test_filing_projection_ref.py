"""Canonical ownership and strict-shape proofs for filing projection references."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from ... import core
from .. import (
    FilingProjectionRef,
    M303DifferentiatedDeductionProjectionField,
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
    compile_filing_projection_ref,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REF_MODELS = (
    M303ProrrataActivityProjectionRef,
    M303DifferentiatedDeductionProjectionRef,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
)


def test_core_facade_exposes_the_canonical_flat_projection_union() -> None:
    assert core.FilingProjectionRef is FilingProjectionRef
    assert core.compile_filing_projection_ref is compile_filing_projection_ref
    assert len(get_args(get_args(FilingProjectionRef)[0])) == 7


def test_every_projection_discriminator_and_payload_field_is_required() -> None:
    for model_type in _REF_MODELS:
        assert model_type.model_fields
        assert all(field.is_required() for field in model_type.model_fields.values()), model_type.__name__
        assert model_type.model_fields["projection_kind"].is_required(), model_type.__name__


def test_all_seven_flat_projection_variants_validate() -> None:
    references: tuple[FilingProjectionRef, ...] = (
        M303ProrrataActivityProjectionRef(
            projection_kind="m303_prorrata_activity",
            slot=1,
            field=M303ProrrataActivityProjectionField.CNAE,
            casilla_id="500",
        ),
        M303DifferentiatedDeductionProjectionRef(
            projection_kind="m303_differentiated_deduction",
            slot=1,
            field=M303DifferentiatedDeductionProjectionField.DOMESTIC_CURRENT_BASE,
            casilla_id="700",
        ),
        M303RegimenSimplificadoActivityProjectionRef(
            projection_kind="m303_regimen_simplificado_activity",
            cohort=M303RegimenSimplificadoCohort.AGRICOLA,
            slot=1,
            field=M303RegimenSimplificadoActivityField.ACTIVITY_CODE,
        ),
        M303RegimenSimplificadoFactProjectionRef(
            projection_kind="m303_regimen_simplificado_fact",
            cohort=M303RegimenSimplificadoCohort.AGRICOLA,
            slot=1,
            fact_identity="indice-corrector",
        ),
        M303RegimenSimplificadoModuleProjectionRef(
            projection_kind="m303_regimen_simplificado_module",
            cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
            slot=1,
            module_order=1,
            value=M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY,
        ),
        M303Exonerado390ActivityProjectionRef(
            projection_kind="m303_exonerado_390_activity",
            slot=1,
            field=M303Exonerado390ActivityField.ACTIVITY_CODE,
        ),
        M303Exonerado390OperacionesTercerosProjectionRef(
            projection_kind="m303_exonerado_390_operaciones_terceros",
        ),
    )

    adapter: TypeAdapter[FilingProjectionRef] = TypeAdapter(FilingProjectionRef)
    assert tuple(adapter.validate_python(reference) for reference in references) == references


@pytest.mark.parametrize("slot", ["1", 1.0, True])
def test_persisted_projection_compiler_refuses_coerced_slot_primitives(slot: object) -> None:
    with pytest.raises(ValueError, match="exact integer"):
        compile_filing_projection_ref(
            {
                "projection_kind": "m303_prorrata_activity",
                "slot": slot,
                "field": "cnae",
                "casilla_id": "500",
            },
        )


@pytest.mark.parametrize("module_order", ["1", 1.0, True])
def test_persisted_projection_compiler_refuses_coerced_module_ordinals(module_order: object) -> None:
    with pytest.raises(ValueError, match=r"module_order.*exact integer"):
        compile_filing_projection_ref(
            {
                "projection_kind": "m303_regimen_simplificado_module",
                "cohort": "no_agricola",
                "slot": 1,
                "module_order": module_order,
                "value": "declared_quantity",
            },
        )


def test_compiler_constructs_the_required_module_shape_without_defaults() -> None:
    assert compile_filing_projection_ref(
        {
            "projection_kind": "m303_regimen_simplificado_module",
            "cohort": "no_agricola",
            "slot": 1,
            "module_order": 7,
            "value": "off_form_result",
        },
    ) == M303RegimenSimplificadoModuleProjectionRef(
        projection_kind="m303_regimen_simplificado_module",
        cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
        slot=1,
        module_order=7,
        value=M303RegimenSimplificadoModuleValue.OFF_FORM_RESULT,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "projection_kind": "m303_regimen_simplificado_fact",
            "cohort": "agricola",
            "slot": 1,
            "fact_identity": "  indice-corrector  ",
        },
        {
            "projection_kind": "m303_prorrata_activity",
            "slot": 1,
            "field": "cnae",
            "casilla_id": " 500 ",
        },
    ],
)
def test_compiler_refuses_surrounding_whitespace_in_identity_tokens(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must not contain surrounding whitespace"):
        compile_filing_projection_ref(payload)


def test_fact_identity_model_refuses_instead_of_normalizing_whitespace() -> None:
    with pytest.raises(ValidationError):
        M303RegimenSimplificadoFactProjectionRef(
            projection_kind="m303_regimen_simplificado_fact",
            cohort=M303RegimenSimplificadoCohort.AGRICOLA,
            slot=1,
            fact_identity="  indice-corrector  ",
        )


@pytest.mark.parametrize(
    "legacy_payload",
    [
        {"kind": "m303_prorrata_activity", "slot": 1, "field": "cnae", "casilla_id": "500"},
        {
            "projection_kind": "m303_regimen_simplificado",
            "cohort": "no_agricola",
            "slot": 1,
            "address": {"kind": "orden_module", "module_order": 1},
        },
        {
            "projection_kind": "m303_regimen_simplificado_module",
            "cohort": "no_agricola",
            "slot": 1,
            "module_identity": "modulo-1",
            "value": "declared_quantity",
        },
    ],
)
def test_compiler_refuses_every_retired_discriminator_and_shape(legacy_payload: dict[str, object]) -> None:
    with pytest.raises((ValidationError, ValueError)):
        compile_filing_projection_ref(legacy_payload)


def test_module_reference_requires_explicit_no_agricola_cohort_and_valid_order() -> None:
    with pytest.raises(ValidationError):
        M303RegimenSimplificadoModuleProjectionRef.model_validate(
            {
                "projection_kind": "m303_regimen_simplificado_module",
                "slot": 1,
                "module_order": 1,
                "value": "declared_quantity",
            },
        )
    with pytest.raises(ValidationError):
        M303RegimenSimplificadoModuleProjectionRef.model_validate(
            {
                "projection_kind": "m303_regimen_simplificado_module",
                "cohort": "agricola",
                "slot": 1,
                "module_order": 8,
                "value": "declared_quantity",
            },
        )


def test_slotless_marker_rejects_legacy_slot_and_models_are_frozen() -> None:
    with pytest.raises(ValidationError):
        M303Exonerado390OperacionesTercerosProjectionRef.model_validate(
            {
                "projection_kind": "m303_exonerado_390_operaciones_terceros",
                "slot": 1,
            },
        )
    reference = M303ProrrataActivityProjectionRef(
        projection_kind="m303_prorrata_activity",
        slot=1,
        field=M303ProrrataActivityProjectionField.CNAE,
        casilla_id="500",
    )
    with pytest.raises(ValidationError, match="frozen"):
        reference.slot = 2  # type: ignore[misc]
