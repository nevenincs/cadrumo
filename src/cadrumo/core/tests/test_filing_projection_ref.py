"""Canonical ownership and strict-shape proofs for filing projection references."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import TypeAdapter, ValidationError

import cadrumo.core as core_facade
from cadrumo.core import (
    FilingProjectionRef,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
    compile_filing_projection_ref,
)
from cadrumo.core import _filing_projection_ref as owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_core_facade_exposes_the_single_projection_union_owner() -> None:
    assert core_facade.FilingProjectionRef is owner.FilingProjectionRef
    declarations = {
        node.name for node in ast.walk(ast.parse(inspect.getsource(owner))) if isinstance(node, ast.ClassDef)
    }
    assert "M303ProrrataActivityProjectionRef" in declarations
    assert core_facade.M303ProrrataActivityProjectionRef is owner.M303ProrrataActivityProjectionRef


def test_discriminator_hydrates_one_exact_member_and_rejects_unknown_shapes() -> None:
    adapter: TypeAdapter[FilingProjectionRef] = TypeAdapter(FilingProjectionRef)
    hydrated = adapter.validate_python(
        {
            "projection_kind": "m303_prorrata_activity",
            "slot": 1,
            "field": "cnae",
            "casilla_id": "500",
        },
        strict=False,
    )

    assert hydrated == M303ProrrataActivityProjectionRef(
        slot=1,
        field=M303ProrrataActivityProjectionField.CNAE,
        casilla_id="500",
    )
    with pytest.raises(ValidationError):
        adapter.validate_python({"projection_kind": "legacy_slot", "slot": 1}, strict=False)


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


def test_persisted_projection_compiler_accepts_only_the_exact_integer_wire_shape() -> None:
    assert compile_filing_projection_ref(
        {
            "projection_kind": "m303_prorrata_activity",
            "slot": 1,
            "field": "cnae",
            "casilla_id": "500",
        },
    ) == M303ProrrataActivityProjectionRef(
        slot=1,
        field=M303ProrrataActivityProjectionField.CNAE,
        casilla_id="500",
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


def test_simplified_module_reference_owns_a_source_slot_not_an_activity_identity() -> None:
    assert compile_filing_projection_ref(
        {
            "projection_kind": "m303_regimen_simplificado_module",
            "cohort": "no_agricola",
            "slot": 1,
            "module_order": 1,
            "value": "declared_quantity",
        },
    ) == M303RegimenSimplificadoModuleProjectionRef(
        slot=1,
        module_order=1,
        value=M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY,
    )

    with pytest.raises(ValidationError):
        compile_filing_projection_ref(
            {
                "projection_kind": "m303_regimen_simplificado_module",
                "cohort": "no_agricola",
                "slot": 1,
                "module_identity": "retired-activity-specific-address",
                "value": "declared_quantity",
            },
        )


def test_simplified_activity_reference_refuses_cross_cohort_field_drift() -> None:
    with pytest.raises(ValidationError, match="requires field"):
        M303RegimenSimplificadoActivityProjectionRef(
            cohort=M303RegimenSimplificadoCohort.AGRICOLA,
            slot=1,
            field=M303RegimenSimplificadoActivityField.IAE_EPIGRAFE,
        )
