"""Construct/export/revision referential-integrity tests split from part1."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import Period
from ..._export_field_kind import CasillaFieldKind
from .. import CasillaId, validated_casilla_id
from .._schema import (
    AlgorithmBindingDefinition,
    AlgorithmProviderDefinition,
    FormulaDefinition,
    FormulaExpression,
    ModeloDefinition,
    ModeloScheduleDefinition,
)
from .._schema_input_kind import InputKind
from .._validate import RegistryValidator
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    ApplicationLinkDefinition,
    ConstructDefinition,
    DeadlineWindowDefinition,
    DependencyClassificationDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistryValidationError,
    RelationDefinition,
    SupportRemovalDecisionDefinition,
    build_minimal_snapshot,
    build_snapshot_with_missing_legal,
    check_all_id_references,
    date,
    minimal_application_link,
    minimal_casilla,
    minimal_catalogues,
    minimal_legal_ref,
    minimal_modelo,
    minimal_revision,
    minimal_source_ref,
    snapshot_for_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NONEXISTENT_CASILLA: CasillaId = validated_casilla_id("nonexistent-casilla", surface="_NONEXISTENT_CASILLA")
_NUMERIC_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_NUMERIC_CASILLA_01")
_MISSING_LEGAL_ID = "lirpf:art-99"


def _modelo_validation_failures(modelo: ModeloDefinition) -> list[str]:
    try:
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)
    except RegistryValidationError as exc:
        return str(exc).splitlines()
    return []


def _assert_missing_legal_ref_rejected(revision: ModeloRevision, expected_match: str) -> None:
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)
    with pytest.raises(RegistryValidationError, match=expected_match):
        check_all_id_references(snapshot)


def test_dangling_application_link_legal_refs() -> None:
    """application_link.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    link = ApplicationLinkDefinition(
        id="al.test2",
        surface="workflow",
        consumer="test",
        requires_snapshot=True,
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(
        application_links=(minimal_application_link("filing"), link),
    )
    _assert_missing_legal_ref_rejected(revision, r"application_link al.test2.legal_refs")


def test_dangling_deadline_window_legal_refs() -> None:
    """deadline_window.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    window = DeadlineWindowDefinition(
        id="dw.test",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        period_kind="annual",
        opens_on=date(2024, 1, 1),
        closes_on=date(2024, 6, 30),
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(
        deadline_windows=(window,),
    )
    _assert_missing_legal_ref_rejected(revision, r"deadline_window dw.test.legal_refs")


def test_dangling_support_removal_decision_legal_refs() -> None:
    """support_removal_decision.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    decision = SupportRemovalDecisionDefinition(
        id="srd.test",
        subject_type="application_link",
        subject_id="al.removed",
        decision="remove_from_filing_grade",
        reason="out_of_scope",
        evidence_note="test",
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(support_removal_decisions=(decision,))
    _assert_missing_legal_ref_rejected(revision, r"support_removal_decision srd.test.legal_refs")


def test_dangling_construct_casilla_ref() -> None:
    """construct.casilla_ids pointing at nonexistent CasillaId raises."""
    construct = ConstructDefinition(
        id="ct.test",
        title="Test construct",
        casilla_ids=(_NONEXISTENT_CASILLA,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(constructs=(construct,))
    with pytest.raises(RegistryValidationError, match=r"construct ct.test.casilla_ids"):
        build_minimal_snapshot(revision)


def test_snapshot_integrity_checks_construct_algorithm_provider_ref() -> None:
    """construct.algorithm_providers must point at declared algorithm providers."""

    provider = AlgorithmProviderDefinition(
        id="provider.test",
        import_path="aeat.tests.provider",
        callable_name="run",
        deterministic=True,
        side_effect_free=True,
        allowed_input_schema={"value": "decimal"},
        output_schema={"result": "decimal"},
        trace_contract="test trace",
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    construct = ConstructDefinition(
        id="ct.algorithm-provider",
        title="Algorithm provider construct",
        algorithm_providers=("provider.test",),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision().model_copy(
        update={"algorithm_providers": (provider,), "constructs": (construct,)},
    )
    snapshot = snapshot_for_revision(minimal_modelo(revision), minimal_catalogues(), revision)
    patched_revision = revision.model_copy(update={"algorithm_providers": ()})
    snapshot = snapshot.model_copy(update={"revision": patched_revision})

    with pytest.raises(RegistryValidationError, match=r"construct ct\.algorithm-provider\.algorithm_providers"):
        check_all_id_references(snapshot)


def test_snapshot_integrity_checks_construct_algorithm_binding_ref() -> None:
    """construct.algorithm_bindings must point at declared algorithm bindings."""

    provider = AlgorithmProviderDefinition(
        id="provider.test",
        import_path="aeat.tests.provider",
        callable_name="run",
        deterministic=True,
        side_effect_free=True,
        allowed_input_schema={"value": "decimal"},
        output_schema={"result": "decimal"},
        trace_contract="test trace",
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    binding = AlgorithmBindingDefinition(
        id="algorithm-binding.test",
        provider="provider.test",
        target_casilla_id=_NUMERIC_CASILLA_01,
        inputs={},
        output_casilla_ids={},
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    construct = ConstructDefinition(
        id="ct.algorithm-binding",
        title="Algorithm binding construct",
        algorithm_bindings=("algorithm-binding.test",),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision().model_copy(
        update={
            "algorithm_providers": (provider,),
            "algorithm_bindings": (binding,),
            "constructs": (construct,),
        },
    )
    snapshot = snapshot_for_revision(minimal_modelo(revision), minimal_catalogues(), revision)
    patched_revision = revision.model_copy(update={"algorithm_bindings": ()})
    snapshot = snapshot.model_copy(update={"revision": patched_revision})

    with pytest.raises(RegistryValidationError, match=r"construct ct\.algorithm-binding\.algorithm_bindings"):
        check_all_id_references(snapshot)


def test_snapshot_integrity_checks_construct_filing_schedule_ref() -> None:
    """construct.filing_schedules must point at declared filing schedules."""

    schedule = ModeloScheduleDefinition(
        id="schedule.test",
        period_kind="annual",
        periods=("0A",),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    construct = ConstructDefinition(
        id="ct.filing-schedule",
        title="Filing schedule construct",
        filing_schedules=("schedule.test",),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision().model_copy(
        update={"filing_schedules": (schedule,), "constructs": (construct,)},
    )
    snapshot = snapshot_for_revision(minimal_modelo(revision), minimal_catalogues(), revision)
    patched_revision = revision.model_copy(update={"filing_schedules": ()})
    snapshot = snapshot.model_copy(update={"revision": patched_revision})

    with pytest.raises(RegistryValidationError, match=r"construct ct\.filing-schedule\.filing_schedules"):
        check_all_id_references(snapshot)


def test_dangling_dependency_classification_target_construct() -> None:
    """dependency_classification.target_constructs pointing at nonexistent ConstructId raises."""
    classification = DependencyClassificationDefinition(
        id="dc.test",
        source_modelo="100",
        treatment="factual_evidence",
        target_constructs=("nonexistent-construct",),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(dependency_classifications=(classification,))
    with pytest.raises(RegistryValidationError, match=r"dependency_classification dc.test.target_constructs"):
        build_minimal_snapshot(revision)


def test_dangling_export_layout_legal_refs() -> None:
    """export_layout.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    layout = ExportLayoutDefinition(
        id="el.test",
        source_refs=(REFERENCE_SOURCE_ID,),
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
    )
    revision = minimal_revision(export_layouts=(layout,))
    _assert_missing_legal_ref_rejected(revision, r"export_layout el.test.legal_refs")


def test_dangling_export_field_casilla_ref() -> None:
    """export_field.casilla_id pointing at nonexistent CasillaId raises."""
    casilla = minimal_casilla(_NUMERIC_CASILLA_01)
    field = ExportFieldDefinition(
        id="el.test.field-01",
        kind=CasillaFieldKind.CASILLA,
        casilla_id=_NONEXISTENT_CASILLA,
        data_type="money",
        required=True,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    record = ExportRecordDefinition(
        id="rec.test",
        record_type="1",
        order=0,
        encoding="ascii",
        line_ending="crlf",
        fields=(field,),
    )
    layout = ExportLayoutDefinition(
        id="el.test",
        source_refs=(REFERENCE_SOURCE_ID,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        records=(record,),
    )
    revision = minimal_revision(casillas=(casilla,), export_layouts=(layout,))
    with pytest.raises(RegistryValidationError, match=r"field el.test.field-01.casilla_id"):
        build_minimal_snapshot(revision)


def test_dangling_export_record_row_field_casilla_ref() -> None:
    """export_record.row_field_casilla_ids values must reference canonical casilla ids."""
    record = ExportRecordDefinition(
        id="rec.test",
        record_type="1",
        order=0,
        encoding="ascii",
        line_ending="crlf",
        row_field_casilla_ids={"importe": _NONEXISTENT_CASILLA},
    )
    layout = ExportLayoutDefinition(
        id="el.test",
        source_refs=(REFERENCE_SOURCE_ID,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        records=(record,),
    )
    revision = minimal_revision(export_layouts=(layout,))

    with pytest.raises(RegistryValidationError, match=r"row_field_casilla_ids\.importe"):
        build_minimal_snapshot(revision)


def test_export_record_row_field_casilla_refs_must_resolve_in_registry_validation() -> None:
    """Registry validation rejects export-record row-field mappings to unknown casillas."""
    record = ExportRecordDefinition(
        id="rec.test",
        record_type="1",
        order=0,
        encoding="ascii",
        line_ending="crlf",
        row_field_casilla_ids={"importe": _NONEXISTENT_CASILLA},
    )
    layout = ExportLayoutDefinition(
        id="el.test",
        source_refs=(REFERENCE_SOURCE_ID,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        records=(record,),
    )
    revision = minimal_revision(export_layouts=(layout,))

    failures = _modelo_validation_failures(minimal_modelo(revision))

    assert any(
        "export record 'rec.test' row_field_casilla_ids.importe references unknown casilla 'nonexistent-casilla'"
        in failure
        for failure in failures
    ), f"row_field_casilla_ids values must be checked against declared casillas; got: {failures}"


def test_dangling_revision_legal_refs() -> None:
    """revision.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    revision = minimal_revision()
    revision = revision.model_copy(update={"legal_refs": (REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID)})
    _assert_missing_legal_ref_rejected(revision, r"revision.legal_refs")


def test_dangling_revision_orden_aplicabilidad_refs() -> None:
    """revision.orden_aplicabilidad must be represented in the snapshot legal map."""
    revision = minimal_revision().model_copy(update={"orden_aplicabilidad": (_MISSING_LEGAL_ID,)})

    with pytest.raises(RegistryValidationError, match=r"revision\.orden_aplicabilidad"):
        build_minimal_snapshot(revision)


def test_dangling_modelo_source_refs() -> None:
    """modelo.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-extra-v1"
    revision = minimal_revision()
    extra_source = minimal_source_ref().model_copy(update={"id": _extra})
    augmented_catalogues = RegistryCatalogues(
        legal={REFERENCE_LEGAL_ID: minimal_legal_ref()},
        sources={REFERENCE_SOURCE_ID: minimal_source_ref(), _extra: extra_source},
    )
    modelo = minimal_modelo(revision).model_copy(update={"source_refs": (REFERENCE_SOURCE_ID, _extra)})
    snapshot = snapshot_for_revision(modelo, augmented_catalogues, revision)
    patched_sources = {k: v for k, v in snapshot.sources.items() if k != _extra}
    snapshot = snapshot.model_copy(update={"sources": patched_sources})
    with pytest.raises(RegistryValidationError, match=r"modelo.source_refs"):
        check_all_id_references(snapshot)


def test_config_repair_report_includes_registry_integrity_check(tmp_path: Path) -> None:
    """build_config_repair_report produces a registry.integrity DiagnosticCheck."""
    from .....application.diagnostics import build_config_repair_report
    from .....tests.secure_sql import isolated_runtime_profile

    with isolated_runtime_profile(tmp_path=tmp_path):
        report = build_config_repair_report()
    check_names = [check.name for check in report.checks]
    assert "registry.integrity" in check_names

    integrity_check = next(c for c in report.checks if c.name == "registry.integrity")
    assert integrity_check.status in {"ok", "fail", "warn"}


def test_informative_modelo_with_formula_fails_validation() -> None:
    """An informative modelo that declares a formula raises RegistryValidationError."""
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NUMERIC_CASILLA_01,
        expression=FormulaExpression(casilla_id=_NUMERIC_CASILLA_01),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    computed_casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    revision = minimal_revision(
        casillas=(computed_casilla,),
        formulas=(formula,),
    )
    catalogues = minimal_catalogues()
    informative_modelo = minimal_modelo(revision).model_copy(update={"calculation_class": "informative"})
    validator = RegistryValidator(catalogues)
    with pytest.raises(RegistryValidationError, match="informative modelo must not declare calculation formulas"):
        validator.validate_modelo(informative_modelo)


def test_informative_modelo_with_relation_fails_validation() -> None:
    """An informative modelo that declares a cross-model relation raises RegistryValidationError."""
    relation = RelationDefinition.model_validate(
        {
            "id": "test.relation",
            "kind": "cross_model_output",
            "dependency_role": "factual_evidence",
            "source_modelo": "100",
            "source_revision_selector": {"year_from": 2024},
            "source_casilla_id": _NUMERIC_CASILLA_01,
            "target_binding": "test.binding",
            "period_alignment": {"source_period": "0A", "target_period": "0A", "filing_year_delta": 0},
            "source_periods": ("0A",),
            "target_periods": ("0A",),
            "legal_refs": (REFERENCE_LEGAL_ID,),
            "source_refs": (REFERENCE_SOURCE_ID,),
        },
    )
    revision = minimal_revision(relations=(relation,))
    catalogues = minimal_catalogues()
    informative_modelo = minimal_modelo(revision).model_copy(update={"calculation_class": "informative"})
    validator = RegistryValidator(catalogues)
    with pytest.raises(RegistryValidationError, match="informative modelo must not declare cross-model relations"):
        validator.validate_modelo(informative_modelo)
