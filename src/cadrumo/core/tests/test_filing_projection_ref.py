"""Canonical ownership and strict-shape proofs for filing projection references."""

from __future__ import annotations

import ast
import inspect
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
    M303RegimenSimplificadoFact,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
    compile_filing_projection_ref,
    filing_projection_ref_casilla_id,
)
from .. import _filing_projection_ref as owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Derived from the union rather than hand-listed, so a new member cannot be
#: added to the union and silently skipped by every test below it.
_REF_MODELS = get_args(get_args(FilingProjectionRef)[0])


def test_core_facade_exposes_the_canonical_flat_projection_union() -> None:
    assert core.FilingProjectionRef is FilingProjectionRef
    assert core.compile_filing_projection_ref is compile_filing_projection_ref
    # Gated on the PROPERTY, not the tally. A member count pins a moment and
    # then detects nothing except its own staleness; what this union has to
    # guarantee is that it stays flat and discriminated, so every member is
    # asserted to be a distinct model carrying a unique required
    # `projection_kind` discriminator.
    members = get_args(get_args(FilingProjectionRef)[0])
    assert members, "the projection union must not be empty"
    assert len(set(members)) == len(members), "the projection union repeats a member"
    discriminators = [get_args(member.model_fields["projection_kind"].annotation)[0] for member in members]
    assert len(set(discriminators)) == len(discriminators), f"projection kinds are not unique: {discriminators}"


def test_every_projection_discriminator_and_payload_field_is_required() -> None:
    for model_type in _REF_MODELS:
        assert model_type.model_fields
        optional = {"sub_index"} if model_type is M303RegimenSimplificadoFactProjectionRef else set()
        assert all(field.is_required() for name, field in model_type.model_fields.items() if name not in optional), (
            model_type.__name__
        )
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
            fact=M303RegimenSimplificadoFact.INDICE_CUOTA,
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
            "value": "cuota_devengada",
        },
    ) == M303RegimenSimplificadoModuleProjectionRef(
        projection_kind="m303_regimen_simplificado_module",
        cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
        slot=1,
        module_order=7,
        value=M303RegimenSimplificadoModuleValue.CUOTA_DEVENGADA,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "projection_kind": "m303_regimen_simplificado_fact",
            "cohort": "agricola",
            "slot": 1,
            "fact": "  indice_cuota  ",
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


def test_fact_model_refuses_instead_of_normalizing_whitespace() -> None:
    with pytest.raises(ValidationError):
        M303RegimenSimplificadoFactProjectionRef(
            projection_kind="m303_regimen_simplificado_fact",
            cohort=M303RegimenSimplificadoCohort.AGRICOLA,
            slot=1,
            fact="  indice_cuota  ",
        )


@pytest.mark.parametrize(
    "fact, sub_index, message",
    [
        (M303RegimenSimplificadoFact.INDICE_CUOTA, 1, "must not carry sub_index"),
    ],
)
def test_fact_model_only_admits_source_declared_multiplicity(
    fact: M303RegimenSimplificadoFact,
    sub_index: int | None,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        M303RegimenSimplificadoFactProjectionRef(
            projection_kind="m303_regimen_simplificado_fact",
            cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
            slot=1,
            fact=fact,
            sub_index=sub_index,
        )


@pytest.mark.parametrize("sub_index", [0, -1, 5, "1", True])
def test_fact_ref_requires_a_positive_exact_sub_index_when_present(sub_index: object) -> None:
    with pytest.raises((ValidationError, ValueError)):
        compile_filing_projection_ref(
            {
                "projection_kind": "m303_regimen_simplificado_fact",
                "cohort": "no_agricola",
                "slot": 1,
                "fact": "mesas_capacidad",
                "sub_index": sub_index,
            }
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
        {
            "projection_kind": "m303_regimen_simplificado_module",
            "cohort": "no_agricola",
            "slot": 1,
            "module_order": 1,
            "value": "off_form_result",
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


def test_core_facade_exposes_the_single_projection_union_owner() -> None:
    assert core.FilingProjectionRef is owner.FilingProjectionRef
    declarations = {
        node.name for node in ast.walk(ast.parse(inspect.getsource(owner))) if isinstance(node, ast.ClassDef)
    }
    assert {model_type.__name__ for model_type in _REF_MODELS} <= declarations
    assert core.M303ProrrataActivityProjectionRef is owner.M303ProrrataActivityProjectionRef
    assert core.filing_projection_ref_casilla_id is owner.filing_projection_ref_casilla_id


def test_simplified_activity_reference_refuses_cross_cohort_field_drift() -> None:
    with pytest.raises(ValidationError, match="requires field"):
        M303RegimenSimplificadoActivityProjectionRef(
            projection_kind="m303_regimen_simplificado_activity",
            cohort=M303RegimenSimplificadoCohort.AGRICOLA,
            slot=1,
            field=M303RegimenSimplificadoActivityField.IAE_EPIGRAFE,
        )


def test_numbered_endpoint_accessor_answers_only_for_casilla_bearing_variants() -> None:
    assert (
        filing_projection_ref_casilla_id(
            M303ProrrataActivityProjectionRef(
                projection_kind="m303_prorrata_activity",
                slot=1,
                field=M303ProrrataActivityProjectionField.CNAE,
                casilla_id="500",
            ),
        )
        == "500"
    )
    assert (
        filing_projection_ref_casilla_id(
            M303DifferentiatedDeductionProjectionRef(
                projection_kind="m303_differentiated_deduction",
                slot=2,
                field=M303DifferentiatedDeductionProjectionField.TOTAL,
                casilla_id="700",
            ),
        )
        == "700"
    )
    for slotless in (
        M303RegimenSimplificadoActivityProjectionRef(
            projection_kind="m303_regimen_simplificado_activity",
            cohort=M303RegimenSimplificadoCohort.AGRICOLA,
            slot=1,
            field=M303RegimenSimplificadoActivityField.ACTIVITY_CODE,
        ),
        M303Exonerado390ActivityProjectionRef(
            projection_kind="m303_exonerado_390_activity",
            slot=1,
            field=M303Exonerado390ActivityField.ACTIVITY_CODE,
        ),
        M303Exonerado390OperacionesTercerosProjectionRef(
            projection_kind="m303_exonerado_390_operaciones_terceros",
        ),
    ):
        assert filing_projection_ref_casilla_id(slotless) is None


def test_a_reference_survives_its_own_python_mode_serialisation() -> None:
    """``model_dump()`` emits StrEnum members, and the compiler must accept them.

    The exact-type guards refuse anything that is not literally ``str``, which a
    StrEnum member is not -- although a member's value IS the wire primitive.
    That made a dumped reference unreadable by the model that produced it, and
    it reached real data: seven committed export layouts (Modelo 200's 2024 and
    all six Modelo 303 revisions) could not be re-validated from their own dump.

    Asserted as strict equality through the real compiler, so a narrowing that
    merely stopped raising while losing a field would still fail.
    """
    reference = M303RegimenSimplificadoActivityProjectionRef(
        projection_kind="m303_regimen_simplificado_activity",
        cohort=M303RegimenSimplificadoCohort.AGRICOLA,
        slot=1,
        field=M303RegimenSimplificadoActivityField.ACTIVITY_CODE,
    )
    payload = reference.model_dump()

    assert isinstance(payload["field"], M303RegimenSimplificadoActivityField), (
        "python-mode dump no longer emits enum members, so this proof no longer "
        "exercises the narrowing it was written for"
    )
    assert compile_filing_projection_ref(payload) == reference


def test_the_enum_narrowing_did_not_loosen_the_primitive_guards() -> None:
    """Narrowing an enum to its value must not admit genuine non-primitives.

    The integer guard in particular has to keep refusing ``bool``: ``True`` is an
    ``int`` subclass, and a slot silently reading as 1 would address the wrong
    projection row.
    """
    base = {
        "projection_kind": "m303_regimen_simplificado_activity",
        "cohort": M303RegimenSimplificadoCohort.AGRICOLA.value,
        "field": M303RegimenSimplificadoActivityField.ACTIVITY_CODE.value,
    }

    with pytest.raises(ValueError, match="must be an exact integer"):
        compile_filing_projection_ref(base | {"slot": True})
    with pytest.raises(ValueError, match="must be an exact string"):
        compile_filing_projection_ref(base | {"slot": 1, "field": 7})
    with pytest.raises(ValueError, match="must not contain surrounding whitespace"):
        compile_filing_projection_ref(base | {"slot": 1, "cohort": " agricola "})
