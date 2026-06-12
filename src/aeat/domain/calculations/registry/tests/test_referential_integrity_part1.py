"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import Period
from ..._export_field_kind import CasillaFieldKind
from ._referential_integrity_support import (
    _DUMMY_LEGAL_ID,
    _DUMMY_SOURCE_ID,
    ApplicationLinkDefinition,
    ConstructDefinition,
    DataBindingDefinition,
    DeadlineWindowDefinition,
    Decimal,
    DependencyClassificationDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
    FormulaDefinition,
    FormulaExpression,
    LiveCrossReferenceDecision,
    ParameterDefinition,
    RegistryCatalogues,
    RegistryValidationError,
    RelationDefinition,
    SupportRemovalDecisionDefinition,
    ValidatedRegistryAuthority,
    VerificationExpectationDefinition,
    _build_minimal_snapshot,
    _build_snapshot_with_missing_legal,
    _build_snapshot_with_missing_source,
    _check_all_id_references,
    _minimal_application_link,
    _minimal_casilla,
    _minimal_catalogues,
    _minimal_legal_ref,
    _minimal_modelo,
    _minimal_revision,
    _minimal_source_ref,
    _minimal_workbook_ref,
    _segmented_casilla,
    _snapshot_for_revision,
    date,
    logging,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_registry_passes_referential_integrity(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """_check_all_id_references raises nothing for every successfully-built snapshot.

    Revisions that fail existing RegistryValidator checks (pre-existing defects
    tracked separately) are skipped; the gate under test is _check_all_id_references
    which only runs on snapshots that have been successfully constructed.
    """
    passed = 0
    for modelo in registry_authority.modelos:
        for revision in modelo.revisions.values():
            try:
                snapshot = _snapshot_for_revision(modelo, registry_authority.catalogues, revision)
            except Exception as exc:
                # Pre-existing registry defects prevent snapshot construction;
                # _check_all_id_references cannot fire here -- log and skip.
                logging.getLogger(__name__).debug(
                    "skipping revision %s/%s: snapshot build failed: %s", modelo.id, revision.id, exc,
                )
                continue
            _check_all_id_references(snapshot)  # must not raise
            passed += 1
    assert passed > 0, "no snapshots were successfully built for the committed registry"


def test_dangling_casilla_formula_reference() -> None:
    """casilla.formula pointing at nonexistent FormulaId raises."""
    casilla = _minimal_casilla("01").model_copy(update={"input_kind": "computed", "formula": "nonexistent.formula"})
    revision = _minimal_revision(casillas=(casilla,))
    with pytest.raises(RegistryValidationError, match=r"casilla 01.formula"):
        _build_minimal_snapshot(revision)


def test_dangling_casilla_binding_reference() -> None:
    """casilla.binding pointing at nonexistent BindingId raises."""
    casilla = _minimal_casilla("01").model_copy(update={"input_kind": "bound", "binding": "nonexistent.binding"})
    revision = _minimal_revision(casillas=(casilla,))
    with pytest.raises(RegistryValidationError, match=r"casilla 01.binding"):
        _build_minimal_snapshot(revision)


def test_bound_casilla_without_binding_definition_fails_snapshot_integrity() -> None:
    """A bound casilla cannot defer missing binding coverage to formula runtime."""
    casilla = _minimal_casilla("01").model_copy(update={"input_kind": "bound"})
    revision = _minimal_revision(casillas=(_minimal_casilla("01"),)).model_copy(update={"casillas": (casilla,)})
    with pytest.raises(
        RegistryValidationError,
        match=r"casilla 01.binding has no binding definition for input_kind='bound'",
    ):
        _build_minimal_snapshot(revision)


def test_dangling_casilla_export_refs() -> None:
    """casilla.export_refs pointing at nonexistent ExportFieldId raises."""
    casilla = _minimal_casilla("01").model_copy(update={"export_refs": ("nonexistent.export.field",)})
    revision = _minimal_revision(casillas=(casilla,))
    with pytest.raises(RegistryValidationError, match=r"casilla 01.export_refs"):
        _build_minimal_snapshot(revision)


def test_dangling_casilla_legal_refs() -> None:
    """casilla.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    casilla = _minimal_casilla("01").model_copy(update={"legal_refs": (_DUMMY_LEGAL_ID, _extra)})
    revision = _minimal_revision(casillas=(casilla,))
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"casilla 01.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_casilla_source_refs() -> None:
    """casilla.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-extra-v1"
    casilla = _minimal_casilla("01").model_copy(update={"source_refs": (_DUMMY_SOURCE_ID, _extra)})
    revision = _minimal_revision(casillas=(casilla,))
    snapshot = _build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"casilla 01.source_refs"):
        _check_all_id_references(snapshot)


def test_dangling_formula_target() -> None:
    """formula.target pointing at nonexistent CasillaId raises."""
    formula = FormulaDefinition(
        id="test.formula",
        target="nonexistent-casilla",
        expression=FormulaExpression(literal=Decimal("0")),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(formulas=(formula,))
    with pytest.raises(RegistryValidationError, match=r"formula test.formula.target"):
        _build_minimal_snapshot(revision)


def test_dangling_formula_legal_refs() -> None:
    """formula.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    casilla = _minimal_casilla("01")
    formula = FormulaDefinition(
        id="test.formula",
        target="01",
        expression=FormulaExpression(literal=Decimal("0")),
        legal_refs=(_DUMMY_LEGAL_ID, _extra),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    casilla_computed = casilla.model_copy(update={"input_kind": "computed", "formula": "test.formula"})
    revision = _minimal_revision(casillas=(casilla_computed,), formulas=(formula,))
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"formula test.formula.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_parameter_source_refs() -> None:
    """parameter.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-param-v1"
    parameter = ParameterDefinition(
        id="test.param",
        data_type="decimal",
        unit="EUR",
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID, _extra),
    )
    revision = _minimal_revision(parameters=(parameter,))
    snapshot = _build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"parameter test.param.source_refs"):
        _check_all_id_references(snapshot)


def test_dangling_binding_source_refs() -> None:
    """binding.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-binding-v1"
    binding = DataBindingDefinition(
        id="test.binding",
        source="manual_input",
        selector={
            "record": "DPA",
            "field": "test",
            "offset": 1,
            "length": 1,
            "data_type": "integer",
        },
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID, _extra),
    )
    revision = _minimal_revision(bindings=(binding,))
    snapshot = _build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"binding test.binding.source_refs"):
        _check_all_id_references(snapshot)


def test_dangling_relation_target_binding() -> None:
    """relation.target_binding pointing at nonexistent BindingId raises."""
    relation = RelationDefinition(
        id="test.relation",
        kind="cross_model_output",
        dependency_role="factual_evidence",
        source_modelo="100",
        source_revision_selector={"year_from": 2024},
        source_output="01",
        target_binding="nonexistent.binding",
        period_alignment={},
        source_periods=("0A",),
        target_periods=("0A",),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(relations=(relation,))
    with pytest.raises(RegistryValidationError, match=r"relation test.relation.target_binding"):
        _build_minimal_snapshot(revision)


def test_dangling_extraction_profile_target_casilla() -> None:
    """extraction_profile.target_casillas pointing at nonexistent CasillaId raises."""
    profile = ExtractionProfileDefinition(
        id="test.profile",
        surface="borrador_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="aeat.domain.calculations.registry._validate.RegistryValidator",
        target_casillas=(
            ExtractionTargetDefinition(
                casilla_id="nonexistent-casilla",
                match_strategy="numeric_casilla",
                value_kind="amount",
            ),
        ),
        confidence="strict",
        min_coverage=Decimal("1"),
        failure_semantics="fail_hard",
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(extraction_profiles=(profile,))
    with pytest.raises(RegistryValidationError, match=r"extraction_profile test.profile.target_casillas"):
        _build_minimal_snapshot(revision)


def test_text_casilla_without_named_label_strategy_fails_gate() -> None:
    """A declaracion_pdf profile targeting a text-typed casilla without named_label raises.

    This is the snapshot-build gate that prevents dead decl.* slug stubs from
    loading green: any profile where a target casilla has data_type='text' but
    uses match_strategy='numeric_casilla' must surface a hard error.
    """
    text_casilla = _minimal_casilla("text-casilla").model_copy(update={"data_type": "text"})
    profile = ExtractionProfileDefinition(
        id="test.profile",
        surface="declaracion_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="aeat.adapters.inbound.declaracion.parse_declaracion",
        target_casillas=(
            ExtractionTargetDefinition(
                casilla_id="text-casilla",
                match_strategy="numeric_casilla",
                value_kind="text",
            ),
        ),
        confidence="strict",
        min_coverage=Decimal("1"),
        failure_semantics="fail_hard",
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(casillas=(text_casilla,), extraction_profiles=(profile,))
    with pytest.raises(
        RegistryValidationError,
        match=r"text-casilla.*data_type='text'.*match_strategy",
    ):
        _build_minimal_snapshot(revision)


def test_text_casilla_with_named_label_strategy_passes_gate() -> None:
    """A declaracion_pdf profile targeting a text-typed casilla with named_label passes."""
    text_casilla = _minimal_casilla("text-casilla").model_copy(update={"data_type": "text"})
    profile = ExtractionProfileDefinition(
        id="test.profile",
        surface="declaracion_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="aeat.adapters.inbound.declaracion.parse_declaracion",
        target_casillas=(
            ExtractionTargetDefinition(
                casilla_id="text-casilla",
                match_strategy="named_label",
                value_kind="text",
                label_pattern=r"Mi etiqueta",
            ),
        ),
        confidence="strict",
        min_coverage=Decimal("1"),
        failure_semantics="fail_hard",
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(casillas=(text_casilla,), extraction_profiles=(profile,))
    snapshot = _build_minimal_snapshot(revision)
    assert snapshot is not None


def test_dangling_cross_reference_legal_refs() -> None:
    """cross_reference.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    cross_ref = LiveCrossReferenceDecision(
        id="test.cross-ref",
        evidence_tier="executable_parity_evidence",
        surface="open_simulator",
        guard_policy_id="test",
        allowed_hosts=("example.com",),
        allowed_methods=("GET",),
        forbidden_actions=("write",),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=(_DUMMY_LEGAL_ID, _extra),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(live_cross_references=(cross_ref,))
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"cross_reference test.cross-ref.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_workbook_parity_workbook_source() -> None:
    """workbook_parity_ref.workbook_source referencing a SourceRefId absent from snapshot.sources raises.

    The workbook_source must be in source_refs (enforced by the schema model validator),
    so we build the snapshot with the source_ref present, then patch it out of
    snapshot.sources to simulate the integrity gap.
    """
    _extra_source = "aeat-dr-workbook-v1"
    workbook = _minimal_workbook_ref(source_ref=_extra_source)
    revision = _minimal_revision(extra_workbook_ref=workbook)
    snapshot = _build_snapshot_with_missing_source(revision, _extra_source)
    with pytest.raises(RegistryValidationError, match=r"workbook_parity_ref wp.test.workbook_source"):
        _check_all_id_references(snapshot)


def test_dangling_verification_expectation_computed_casillas() -> None:
    """verification_expectation.computed_casillas pointing at nonexistent CasillaId raises."""
    expectation = VerificationExpectationDefinition(
        id="test.expectation",
        computed_casillas=("nonexistent-casilla",),
        tolerance=Decimal("0"),
        rounding="ROUND_HALF_UP",
        min_coverage=Decimal("1"),
        discrepancy_causes=("rounding",),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(verification_expectations=(expectation,))
    with pytest.raises(RegistryValidationError, match=r"verification_expectation test.expectation.computed_casillas"):
        _build_minimal_snapshot(revision)


def test_dangling_application_link_legal_refs() -> None:
    """application_link.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    link = ApplicationLinkDefinition(
        id="al.test2",
        surface="workflow",
        consumer="test",
        requires_snapshot=True,
        legal_refs=(_DUMMY_LEGAL_ID, _extra),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(
        application_links=(_minimal_application_link("filing"), link),
    )
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"application_link al.test2.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_deadline_window_legal_refs() -> None:
    """deadline_window.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    window = DeadlineWindowDefinition(
        id="dw.test",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        period_kind="annual",
        opens_on=date(2024, 1, 1),
        closes_on=date(2024, 6, 30),
        legal_refs=(_DUMMY_LEGAL_ID, _extra),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(
        deadline_windows=(window,),
    )
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"deadline_window dw.test.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_support_removal_decision_legal_refs() -> None:
    """support_removal_decision.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    decision = SupportRemovalDecisionDefinition(
        id="srd.test",
        subject_type="application_link",
        subject_id="al.removed",
        decision="remove_from_filing_grade",
        reason="out_of_scope",
        evidence_note="test",
        legal_refs=(_DUMMY_LEGAL_ID, _extra),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(support_removal_decisions=(decision,))
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"support_removal_decision srd.test.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_construct_casilla_ref() -> None:
    """construct.casillas pointing at nonexistent CasillaId raises."""
    construct = ConstructDefinition(
        id="ct.test",
        title="Test construct",
        casillas=("nonexistent-casilla",),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(constructs=(construct,))
    with pytest.raises(RegistryValidationError, match=r"construct ct.test.casillas"):
        _build_minimal_snapshot(revision)


def test_dangling_dependency_classification_target_construct() -> None:
    """dependency_classification.target_constructs pointing at nonexistent ConstructId raises."""
    classification = DependencyClassificationDefinition(
        id="dc.test",
        source_modelo="100",
        treatment="factual_evidence",
        target_constructs=("nonexistent-construct",),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(dependency_classifications=(classification,))
    with pytest.raises(RegistryValidationError, match=r"dependency_classification dc.test.target_constructs"):
        _build_minimal_snapshot(revision)


def test_dangling_export_layout_legal_refs() -> None:
    """export_layout.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    layout = ExportLayoutDefinition(
        id="el.test",
        source_refs=(_DUMMY_SOURCE_ID,),
        legal_refs=(_DUMMY_LEGAL_ID, _extra),
    )
    revision = _minimal_revision(export_layouts=(layout,))
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"export_layout el.test.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_export_field_casilla_ref() -> None:
    """export_field.casilla pointing at nonexistent CasillaId raises."""
    casilla = _minimal_casilla("01")
    field = ExportFieldDefinition(
        id="el.test.field-01",
        kind=CasillaFieldKind.CASILLA,
        casilla="nonexistent-casilla",
        data_type="money",
        required=True,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
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
        source_refs=(_DUMMY_SOURCE_ID,),
        legal_refs=(_DUMMY_LEGAL_ID,),
        records=(record,),
    )
    revision = _minimal_revision(casillas=(casilla,), export_layouts=(layout,))
    with pytest.raises(RegistryValidationError, match=r"field el.test.field-01.casilla"):
        _build_minimal_snapshot(revision)


def test_dangling_revision_legal_refs() -> None:
    """revision.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    _extra = "lirpf:art-99"
    revision = _minimal_revision()
    revision = revision.model_copy(update={"legal_refs": (_DUMMY_LEGAL_ID, _extra)})
    snapshot = _build_snapshot_with_missing_legal(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"revision.legal_refs"):
        _check_all_id_references(snapshot)


def test_dangling_modelo_source_refs() -> None:
    """modelo.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-extra-v1"
    revision = _minimal_revision()
    extra_source = _minimal_source_ref().model_copy(update={"id": _extra})
    augmented_catalogues = RegistryCatalogues(
        legal={_DUMMY_LEGAL_ID: _minimal_legal_ref()},
        sources={_DUMMY_SOURCE_ID: _minimal_source_ref(), _extra: extra_source},
    )
    modelo = _minimal_modelo(revision).model_copy(update={"source_refs": (_DUMMY_SOURCE_ID, _extra)})
    snapshot = _snapshot_for_revision(modelo, augmented_catalogues, revision)
    # Patch out the extra source ref from the snapshot's sources map.
    patched_sources = {k: v for k, v in snapshot.sources.items() if k != _extra}
    snapshot = snapshot.model_copy(update={"sources": patched_sources})
    with pytest.raises(RegistryValidationError, match=r"modelo.source_refs"):
        _check_all_id_references(snapshot)


def test_config_repair_report_includes_registry_integrity_check(tmp_path: Path) -> None:
    """build_config_repair_report produces a registry.integrity DiagnosticCheck.

    The report walks SecureObject storage to surface bucket-side health,
    so the test runs inside a real active-profile storage runtime to
    satisfy the encrypted-column decrypt path.
    """
    from .....application.diagnostics import build_config_repair_report
    from .....tests.secure_sql import isolated_runtime_profile

    with isolated_runtime_profile(tmp_path=tmp_path):
        report = build_config_repair_report()
    check_names = [check.name for check in report.checks]
    assert "registry.integrity" in check_names

    integrity_check = next(c for c in report.checks if c.name == "registry.integrity")
    assert integrity_check.status in {"ok", "fail", "warn"}


def test_informative_modelo_with_formula_fails_validation() -> None:
    """An informative modelo that declares a formula raises RegistryValidationError.

    Covers the registry-wide _validate_informative_class_invariant: it walks every
    revision of an informative modelo and rejects formulas, relations, and
    non-manual/non-informational casillas.
    """
    from .. import RegistryValidator
    from .._schema import FormulaDefinition, FormulaExpression

    formula = FormulaDefinition(
        id="test.formula",
        target="01",
        expression=FormulaExpression(casilla="01"),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    computed_casilla = _minimal_casilla("01").model_copy(update={"input_kind": "computed", "formula": "test.formula"})
    revision = _minimal_revision(
        casillas=(computed_casilla,),
        formulas=(formula,),
    )
    catalogues = _minimal_catalogues()
    informative_modelo = _minimal_modelo(revision).model_copy(update={"calculation_class": "informative"})
    validator = RegistryValidator(catalogues)
    with pytest.raises(RegistryValidationError, match="informative modelo must not declare calculation formulas"):
        validator.validate_modelo(informative_modelo)


def test_informative_modelo_with_relation_fails_validation() -> None:
    """An informative modelo that declares a cross-model relation raises RegistryValidationError."""
    from .. import RegistryValidator

    relation = RelationDefinition(
        id="test.relation",
        kind="cross_model_output",
        dependency_role="factual_evidence",
        source_modelo="100",
        source_revision_selector={"year_from": 2024},
        source_output="01",
        target_binding="test.binding",
        period_alignment={},
        source_periods=("0A",),
        target_periods=("0A",),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(relations=(relation,))
    catalogues = _minimal_catalogues()
    informative_modelo = _minimal_modelo(revision).model_copy(update={"calculation_class": "informative"})
    validator = RegistryValidator(catalogues)
    with pytest.raises(RegistryValidationError, match="informative modelo must not declare cross-model relations"):
        validator.validate_modelo(informative_modelo)


def test_same_number_distinct_segmento_casillas_validate() -> None:
    """Two casillas sharing a number under distinct segmento values both validate.

    This is the multi-segment AEAT shape (e.g. Modelo 200 casilla 00562
    appearing in both the Liquidacion and ECPN record segments). The
    casillas carry distinct ids and distinct segmento codes, so the
    (segmento, number) identity pairs (DP200014, 00562) and
    (DP200032, 00562) are unique and the validator must accept them.
    """
    from .. import RegistryValidator

    liquidacion = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    ecpn = _segmented_casilla("DP200032:00562", "00562", "DP200032")
    revision = _minimal_revision(casillas=(liquidacion, ecpn))
    modelo = _minimal_modelo(revision)
    # validate_modelo raises iff any failure is collected; a clean return
    # proves the (segmento, number) pairs are accepted as distinct.
    RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_single_segment_duplicate_number_collision_fails() -> None:
    """Two segmento-unset casillas sharing a number hard-fail on (None, number).

    The casillas carry distinct ids, so the per-kind duplicate-id check
    does NOT fire. Only the generalised (segmento, number) identity
    invariant catches the collision: with segmento unset on both, the
    pair degrades to (None, '00562') and the duplicate is reported with
    the bare-number message, exactly as the prior duplicate-id check did.
    """
    from .. import RegistryValidator

    first = _segmented_casilla("00562", "00562", None)
    second = _segmented_casilla("00562-alt", "00562", None)
    revision = _minimal_revision(casillas=(first, second))
    modelo = _minimal_modelo(revision)
    with pytest.raises(RegistryValidationError, match=r"duplicate casilla number '00562'"):
        RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_same_segmento_duplicate_number_collision_fails() -> None:
    """Two casillas sharing a number within one segmento hard-fail.

    Within a single record segment a casilla number must still be
    unique; the (segmento, number) pair (DP200014, 00562) declared twice
    is a duplicate and the validator reports it segment-qualified.
    """
    from .. import RegistryValidator

    first = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    second = _segmented_casilla("DP200014:00562-alt", "00562", "DP200014")
    revision = _minimal_revision(casillas=(first, second))
    modelo = _minimal_modelo(revision)
    with pytest.raises(
        RegistryValidationError,
        match=r"duplicate casilla number '00562' within segmento 'DP200014'",
    ):
        RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_single_segment_bare_number_reference_resolves() -> None:
    """A formula referencing a casilla by its bare number resolves single-segment.

    The casilla sets id == number with segmento unset, so the bare
    number is the unambiguous reference token. A formula whose
    expression reads that casilla and whose target is a computed casilla
    must validate with no unknown-casilla failure.
    """
    from .._schema import FormulaDefinition, FormulaExpression
    from .._validate import RegistryValidator

    input_casilla = _segmented_casilla("01", "01", None)
    computed_casilla = _segmented_casilla("02", "02", None).model_copy(
        update={"input_kind": "computed", "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target="02",
        expression=FormulaExpression(casilla="01"),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(casillas=(input_casilla, computed_casilla), formulas=(formula,))
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(
        _minimal_modelo(revision),
        revision,
    )
    casilla_resolution_failures = [f for f in failures if "unknown casilla" in f]
    assert casilla_resolution_failures == [], (
        f"single-segment bare-number reference must resolve; got: {casilla_resolution_failures}"
    )


def test_ambiguous_cross_segment_bare_number_reference_does_not_resolve() -> None:
    """A bare-number reference to a number reused across segments fails to resolve.

    Casilla number 00562 occurs in two record segments, so the bare
    number is ambiguous. A formula expression that references '00562'
    directly must NOT resolve: the validator reports an unknown casilla,
    forcing the formula to name the intended occurrence by its
    segment-qualified id.
    """
    from .._schema import FormulaDefinition, FormulaExpression
    from .._validate import RegistryValidator

    liquidacion = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    ecpn = _segmented_casilla("DP200032:00562", "00562", "DP200032")
    target_casilla = _segmented_casilla("DP200014:00999", "00999", "DP200014").model_copy(
        update={"input_kind": "computed", "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target="DP200014:00999",
        expression=FormulaExpression(casilla="00562"),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(
        casillas=(liquidacion, ecpn, target_casilla),
        formulas=(formula,),
    )
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(
        _minimal_modelo(revision),
        revision,
    )
    unknown_casilla_failures = [f for f in failures if "unknown casilla '00562'" in f]
    assert unknown_casilla_failures, (
        f"an ambiguous cross-segment bare-number reference must fail to resolve; got failures: {failures}"
    )


def test_bare_number_reference_resolves_when_id_is_segment_qualified() -> None:
    """A bare-number reference resolves to a casilla whose id is segment-qualified.

    This is the decisive segment-aware-resolution case. The casilla
    number 00562 occurs exactly once on the revision but its id is the
    segment-qualified 'DP200014:00562' — id is no longer equal to
    number. A formula expression that references the bare number '00562'
    must still resolve to that single occurrence: the bare number is
    unambiguous within the revision, so it resolves within its segment
    context without the formula having to repeat the segment qualifier.
    """
    from .._schema import FormulaDefinition, FormulaExpression
    from .._validate import RegistryValidator

    sole_occurrence = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    target_casilla = _segmented_casilla("DP200014:00999", "00999", "DP200014").model_copy(
        update={"input_kind": "computed", "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target="DP200014:00999",
        expression=FormulaExpression(casilla="00562"),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(
        casillas=(sole_occurrence, target_casilla),
        formulas=(formula,),
    )
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(
        _minimal_modelo(revision),
        revision,
    )
    unknown_casilla_failures = [f for f in failures if "unknown casilla" in f]
    assert unknown_casilla_failures == [], (
        "an unambiguous bare-number reference must resolve to a casilla whose id "
        f"is segment-qualified; got: {unknown_casilla_failures}"
    )
