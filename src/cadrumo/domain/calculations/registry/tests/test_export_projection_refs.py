"""Direct validation and indexing proofs for typed export projection references."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from .....core import FilingProducerKey
from .....core.filing_projection_ref import (
    M303Exonerado390OperacionesTercerosProjectionRef,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
)
from .....core.casilla_id import validated_casilla_id
from .._loader_internals import _compile_export_semantic_field, _compile_projection_endpoint_declaration
from .._snapshot_internals import _validate_materialized_export_record_families
from .._validate_evidence import EvidenceValidator
from .._validate_exports import (
    _validate_export_record,
    _validate_generated_projection_layout_bijection,
    _validate_projection_endpoint_declarations,
)
from ..authority import bundled_authority
from ..errors import RegistryLoadError, RegistryValidationError
from ..export import derive_export_layouts_from_bindings
from ..fixed_width_codec import ExportEncoding
from ..schema import ModeloRevision
from ..schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ProjectionEndpointDeclaration,
)
from ..schema_references import PeriodSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-58-2003:art-98"
_SOURCE_REF = "aeat-dr-303-2025"
_PROJECTION_CASILLA = validated_casilla_id("500", surface="test projection endpoint")
_UNKNOWN_CASILLA = validated_casilla_id("missing", surface="test projection endpoint")


def _prorrata_ref(*, casilla_id: str = _PROJECTION_CASILLA) -> M303ProrrataActivityProjectionRef:
    return M303ProrrataActivityProjectionRef(
        projection_kind="m303_prorrata_activity",
        slot=1,
        field=M303ProrrataActivityProjectionField.CNAE,
        casilla_id=validated_casilla_id(casilla_id, surface="test projection endpoint"),
    )


def _field(*, field_id: str = "projection.field", projection_ref: object) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=field_id,
        offset=1,
        length=4,
        kind="projection",
        projection_ref=projection_ref,
        data_type="text",
        required=False,
        padding="right_space",
        justification="left",
        signed=False,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _declaration(*, projection_ref: object) -> ProjectionEndpointDeclaration:
    return ProjectionEndpointDeclaration(
        projection_ref=projection_ref,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _binding_field(*, field_id: str = "binding.field") -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=field_id,
        offset=1,
        length=4,
        kind="binding",
        binding="projection-test-binding",
        data_type="text",
        required=False,
        padding="right_space",
        justification="left",
        signed=False,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _revision(
    *fields: ExportFieldDefinition,
    repeat: Literal["binding_rows", "projection_rows"] | None = None,
    binding_record: str | None = None,
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...] = (),
) -> ModeloRevision:
    return ModeloRevision(
        id="projection-test",
        localization_key="test.projection.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        projection_endpoints=projection_endpoints,
        export_layouts=(
            ExportLayoutDefinition(
                id="projection-layout",
                legal_refs=(_LEGAL_REF,),
                source_refs=(_SOURCE_REF,),
                records=(
                    ExportRecordDefinition(
                        id="projection-record",
                        record_type="projection",
                        order=1,
                        encoding=ExportEncoding.LATIN_1,
                        line_ending="none",
                        repeat=repeat,
                        binding_record=binding_record,
                        fields=fields,
                    ),
                ),
            ),
        ),
    )


def _raw_projection_field(*, reference: object) -> dict[str, object]:
    return {
        "id": "projection.field",
        "offset": 1,
        "length": 4,
        "kind": "projection",
        "projection_ref": reference,
        "data_type": "text",
        "required": False,
        "padding": "right_space",
        "justification": "left",
        "signed": False,
        "legal_refs": (_LEGAL_REF,),
        "source_refs": (_SOURCE_REF,),
    }


def test_projection_field_declares_only_the_typed_projection_payload() -> None:
    reference = _prorrata_ref()

    with pytest.raises(ValidationError, match="only projection_ref"):
        ExportFieldDefinition.model_validate(
            {
                **_raw_projection_field(reference=reference),
                "producer_key": FilingProducerKey.PRESENTER_TAX_ID,
            },
        )
    # A well-formed raw payload is COMPILED, not refused, and that is deliberate.
    # These declarations are persisted and re-read, so a guard demanding an
    # already-typed reference could never admit their own serialised form --
    # ProjectionEndpointDeclaration's validator says exactly that. The invariant
    # is that the canonical compiler produced the value, not that the caller
    # arrived holding one. This assertion used to demand a refusal carrying
    # "loader-hydrated FilingProjectionRef", a message no code has raised since
    # the contract changed, so it failed while proving nothing.
    compiled_from_raw = ExportFieldDefinition.model_validate(
        _raw_projection_field(
            reference={
                "projection_kind": "m303_prorrata_activity",
                "slot": 1,
                "field": "cnae",
                "casilla_id": _PROJECTION_CASILLA,
            },
        ),
    )

    assert compiled_from_raw.projection_ref == reference

    # What must still be refused is a payload the compiler rejects.
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate(
            _raw_projection_field(
                reference={
                    "projection_kind": "m303_prorrata_activity",
                    "slot": True,
                    "field": "cnae",
                    "casilla_id": _PROJECTION_CASILLA,
                },
            ),
        )


def test_registry_loader_hydrates_only_exact_projection_ref_toml() -> None:
    source_path = Path("projection.toml")
    compiled = _compile_export_semantic_field(
        source_path,
        _raw_projection_field(
            reference={
                "projection_kind": "m303_prorrata_activity",
                "slot": 1,
                "field": "cnae",
                "casilla_id": _PROJECTION_CASILLA,
            },
        ),
    )
    field = ExportFieldDefinition.model_validate(compiled)

    assert field.projection_ref == _prorrata_ref()
    with pytest.raises(RegistryLoadError, match="does not match any of the expected tags"):
        _compile_export_semantic_field(
            source_path,
            _raw_projection_field(reference={"projection_kind": "m303_unknown_projection"}),
        )


def test_registry_loader_hydrates_required_flat_module_projection() -> None:
    compiled = _compile_export_semantic_field(
        Path("projection.toml"),
        _raw_projection_field(
            reference={
                "projection_kind": "m303_regimen_simplificado_module",
                "cohort": "no_agricola",
                "slot": 1,
                "module_order": 7,
                "value": "declared_quantity",
            },
        ),
    )

    field = ExportFieldDefinition.model_validate(compiled)
    assert field.projection_ref == M303RegimenSimplificadoModuleProjectionRef(
        projection_kind="m303_regimen_simplificado_module",
        cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
        slot=1,
        module_order=7,
        value=M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY,
    )


def test_projection_endpoint_index_preserves_duplicate_declarations_and_indexes_numbered_endpoints() -> None:
    reference = _prorrata_ref()
    first = _declaration(projection_ref=reference)
    second = _declaration(projection_ref=reference)
    slotless = _declaration(
        projection_ref=M303Exonerado390OperacionesTercerosProjectionRef(
            projection_kind="m303_exonerado_390_operaciones_terceros",
        ),
    )
    revision = _revision(projection_endpoints=(first, second, slotless))

    assert revision.projection_endpoint_index()[reference] == (first, second)
    assert revision.projection_declarations_for_casilla(_PROJECTION_CASILLA) == (first, second)
    assert revision.projection_declarations_for_casilla(_UNKNOWN_CASILLA) == ()


def test_repeat_field_family_positive_controls_include_fixed_slot_projection() -> None:
    projection_field = _field(field_id="projection.repeat", projection_ref=_prorrata_ref())
    projection_revision = _revision(projection_field, repeat="projection_rows")
    binding_revision = _revision(_binding_field(), repeat="binding_rows")
    derived_binding_revision = _revision(repeat="binding_rows", binding_record="projection-test-record")
    fixed_binding_revision = _revision(_binding_field())
    fixed_slot_revision = _revision(projection_field)

    assert projection_revision.export_layouts[0].records[0].repeat == "projection_rows"
    assert binding_revision.export_layouts[0].records[0].repeat == "binding_rows"
    assert derived_binding_revision.export_layouts[0].records[0].binding_record == "projection-test-record"
    assert fixed_binding_revision.export_layouts[0].records[0].repeat is None
    assert fixed_slot_revision.export_layouts[0].records[0].repeat is None


@pytest.mark.parametrize(
    ("repeat", "field", "message"),
    [
        ("projection_rows", _binding_field(), "projection-row export record cannot contain binding fields"),
        ("binding_rows", _field(projection_ref=_prorrata_ref()), "binding-row export record cannot contain projection"),
    ],
)
def test_repeat_mode_refuses_a_foreign_field_family(
    repeat: Literal["binding_rows", "projection_rows"] | None,
    field: ExportFieldDefinition,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _revision(field, repeat=repeat)


@pytest.mark.parametrize("repeat", ["binding_rows", "projection_rows"])
def test_repeat_mode_requires_its_own_field_family(repeat: Literal["binding_rows", "projection_rows"]) -> None:
    with pytest.raises(ValidationError, match=rf"repeats {repeat.removesuffix('_rows')} rows but has no"):
        _revision(repeat=repeat)


@pytest.mark.parametrize("repeat", [None, "binding_rows", "projection_rows"])
def test_every_repeat_mode_refuses_mixed_binding_and_projection_fields(
    repeat: Literal["binding_rows", "projection_rows"] | None,
) -> None:
    with pytest.raises(ValidationError, match="cannot mix binding and projection fields"):
        _revision(_binding_field(), _field(projection_ref=_prorrata_ref()), repeat=repeat)


def test_registry_validation_rechecks_repeat_family_after_model_copy() -> None:
    revision = _revision(_field(projection_ref=_prorrata_ref()), repeat="projection_rows")
    [record] = revision.export_layouts[0].records
    derived_record = record.model_copy(update={"repeat": "binding_rows"})
    failures: list[str] = []

    _validate_export_record(
        failures,
        prefix="modelo 303 revision projection-test",
        revision=revision,
        record=derived_record,
        casillas=set(),
        bindings=set(),
        casilla_by_id={},
        legal_refs={},
        source_refs={},
        evidence=EvidenceValidator(legal_refs={}, source_refs={}, source_root=None),
    )

    assert any("binding-row export record cannot contain projection fields" in failure for failure in failures)


def test_materialized_snapshot_boundary_refuses_unresolved_binding_record() -> None:
    revision = _revision(repeat="binding_rows", binding_record="missing-record-bindings")
    materialized = revision.model_copy(update={"export_layouts": derive_export_layouts_from_bindings(revision)})

    with pytest.raises(RegistryValidationError, match="did not materialize binding fields"):
        _validate_materialized_export_record_families(materialized)


@pytest.mark.parametrize(
    ("modelo_id", "filing_year", "period", "record_type", "repeat"),
    [
        ("131", 2024, "1T", "DPA", "binding_rows"),
        ("720", 2024, "0A", "type_1", None),
    ],
)
def test_active_snapshots_materialize_repeated_and_fixed_binding_records(
    modelo_id: str,
    filing_year: int,
    period: str,
    record_type: str,
    repeat: Literal["binding_rows"] | None,
) -> None:
    snapshot = bundled_authority().snapshot(modelo_id, filing_year=filing_year, period=period)
    record = next(record for record in snapshot.revision.export_layouts[0].records if record.record_type == record_type)

    assert record.repeat == repeat
    assert record.binding_record is not None
    assert any(field.kind == "binding" for field in record.fields)
    assert all(field.kind != "projection" for field in record.fields)


def test_projection_endpoint_validator_refuses_duplicate_and_unknown_casilla() -> None:
    duplicate = _prorrata_ref(casilla_id=_UNKNOWN_CASILLA)
    revision = _revision(
        projection_endpoints=(
            _declaration(projection_ref=duplicate),
            _declaration(projection_ref=duplicate),
        ),
    )
    failures: list[str] = []

    _validate_projection_endpoint_declarations(
        failures,
        prefix="modelo 303 revision projection-test",
        revision=revision,
        casillas=set(),
        casilla_by_id={},
        legal_refs={},
        source_refs={},
        evidence=EvidenceValidator(legal_refs={}, source_refs={}, source_root=None),
    )

    assert any("admitted by 2 projection declarations; expected exactly one" in failure for failure in failures)
    assert any("references unknown casilla 'missing'" in failure for failure in failures)


def test_generated_projection_fields_must_biject_revision_owned_declarations() -> None:
    reference = _prorrata_ref()
    revision = _revision(_field(projection_ref=reference))
    failures: list[str] = []

    _validate_generated_projection_layout_bijection(
        failures,
        prefix="modelo 303 revision projection-test",
        revision=revision,
    )

    assert failures == [
        "modelo 303 revision projection-test: generated export layouts must exactly biject projection declarations; "
        "undeclared generated refs "
        "(\"M303ProrrataActivityProjectionRef(projection_kind='m303_prorrata_activity', slot=1, "
        "field=<M303ProrrataActivityProjectionField.CNAE: 'cnae'>, casilla_id='500')\",)",
    ]
    declared = revision.model_copy(update={"projection_endpoints": (_declaration(projection_ref=reference),)})
    clean: list[str] = []
    _validate_generated_projection_layout_bijection(
        clean,
        prefix="modelo 303 revision projection-test",
        revision=declared,
    )
    assert clean == []


def test_projection_endpoint_loader_hydrates_only_the_canonical_toml_payload() -> None:
    source_path = Path("projection-endpoint.toml")
    compiled = _compile_projection_endpoint_declaration(
        source_path,
        {
            "projection_ref": {
                "projection_kind": "m303_prorrata_activity",
                "slot": 1,
                "field": "cnae",
                "casilla_id": _PROJECTION_CASILLA,
            },
            "legal_refs": (_LEGAL_REF,),
            "source_refs": (_SOURCE_REF,),
        },
    )

    assert ProjectionEndpointDeclaration.model_validate(compiled).projection_ref == _prorrata_ref()
    # Re-reading its own raw payload is the case this model exists to admit: the
    # declaration is persisted and read back, so the compiler runs on the way in
    # rather than the model demanding a caller that already holds a typed value.
    assert (
        ProjectionEndpointDeclaration.model_validate(
            {
                **compiled,
                "projection_ref": {
                    "projection_kind": "m303_prorrata_activity",
                    "slot": 1,
                    "field": "cnae",
                    "casilla_id": _PROJECTION_CASILLA,
                },
            },
        ).projection_ref
        == _prorrata_ref()
    )

    with pytest.raises((ValidationError, RegistryValidationError)):
        ProjectionEndpointDeclaration.model_validate(
            {**compiled, "projection_ref": {"projection_kind": "m303_prorrata_activity", "slot": "1"}},
        )
