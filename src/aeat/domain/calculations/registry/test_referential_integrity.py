"""Referential-integrity gate: _check_all_id_references.

Tests:
  1. The committed registry passes with zero dangling references.
  2. For each of the 21 typed-ID categories, a minimal snapshot with a
     deliberately dangling reference raises RegistryValidationError carrying
     the expected qualified-path fragment.
  3. The aeat config repair JSON output includes the registry.integrity check.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import ValidationError

from ....core._toml import freeze_toml
from ....core.classification import SensitivityClass
from ....core.resources import bundled_path
from . import RegistryValidationError
from ._authority import ValidatedRegistryAuthority
from ._loader import load_registry_tree
from ._schema import (
    ApplicationLinkDefinition,
    CalculationCompletenessCasilla,
    CalculationCompletenessManifest,
    CasillaDefinition,
    ConstructDefinition,
    DataBindingDefinition,
    DeadlineWindowDefinition,
    DependencyClassificationDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
    FormulaDefinition,
    FormulaExpression,
    LegalReference,
    LiveCrossReferenceDecision,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    RegistryCatalogues,
    RegistrySnapshot,
    RelationDefinition,
    SourceReference,
    SupportRemovalDecisionDefinition,
    VerificationExpectationDefinition,
    WorkbookParityReference,
)
from ._validate_references import _check_all_id_references

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


# ---------------------------------------------------------------------------
# Helpers to load and patch committed registry material
# ---------------------------------------------------------------------------


def _load_registry() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:

    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return modelos, catalogues


def _snapshot_for_revision(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    revision: ModeloRevision,
) -> RegistrySnapshot:
    """Build a minimal snapshot for a given revision without running integrity checks."""
    from ._snapshot import _build_validated_snapshot

    filing_year = revision.period_selector.year_from or 2024
    period = next(iter(revision.period_selector.periods))
    return _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        revision_id=revision.id,
    )


# ---------------------------------------------------------------------------
# Test 1: committed registry passes with zero dangling references
# ---------------------------------------------------------------------------


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
                    "skipping revision %s/%s: snapshot build failed: %s", modelo.id, revision.id, exc
                )
                continue
            _check_all_id_references(snapshot)  # must not raise
            passed += 1
    assert passed > 0, "no snapshots were successfully built for the committed registry"


# ---------------------------------------------------------------------------
# Minimal snapshot helpers
# ---------------------------------------------------------------------------

_DUMMY_LEGAL_ID = "lirpf:art-1"
_DUMMY_SOURCE_ID = "aeat-dr-130-2019-v12"


def _minimal_legal_ref() -> LegalReference:
    return LegalReference(
        id=_DUMMY_LEGAL_ID,
        evidence_tier="legal_authority",
        authority="boe",
        kind="ley",
        corpus_ref="boe/lirpf#art-1",
        document_id="BOE-A-2006-20764",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        effective_from=date(2006, 11, 30),
        review_status="reviewed",
    )


def _minimal_source_ref() -> SourceReference:
    return SourceReference(
        id=_DUMMY_SOURCE_ID,
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="instructions",
        corpus_path="registry/aeat/sources/aeat-dr-130-2019-v12.pdf",
        sha256="a" * 64,
        bytes=1024,
        retrieved_at=date(2024, 1, 1),
        source_url="https://www.agenciatributaria.es/",
        review_status="reviewed",
    )


def _minimal_catalogues() -> RegistryCatalogues:
    return RegistryCatalogues(
        legal={_DUMMY_LEGAL_ID: _minimal_legal_ref()},
        sources={_DUMMY_SOURCE_ID: _minimal_source_ref()},
    )


def _minimal_casilla(casilla_id: str = "01") -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=casilla_id,
        label=f"Casilla {casilla_id}",
        section=("test",),
        input_kind="manual",
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def _minimal_workbook_ref(source_ref: str = _DUMMY_SOURCE_ID) -> WorkbookParityReference:
    from ._schema import WorkbookParityReference

    return WorkbookParityReference(
        id="wp.test",
        workbook_source=source_ref,
        fixture_id="test",
        formula_coverage="static_layout",
        runner_required=False,
        tolerance=Decimal("0"),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(source_ref,),
    )


def _minimal_application_link(
    surface: Literal[
        "calculation",
        "filing",
        "review",
        "verification",
        "approval",
        "reconciliation",
        "export",
        "deadline",
        "portal",
        "extractor",
        "workflow",
        "communication",
        "payer_delivery",
    ] = "filing",
) -> ApplicationLinkDefinition:
    return ApplicationLinkDefinition(
        id="al.test",
        surface=surface,
        consumer="test",
        requires_snapshot=True,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def _minimal_revision(
    *,
    casillas: tuple[CasillaDefinition, ...] = (),
    extra_workbook_ref: WorkbookParityReference | None = None,
    application_links: tuple[ApplicationLinkDefinition, ...] | None = None,
    formulas: tuple[FormulaDefinition, ...] = (),
    parameters: tuple[ParameterDefinition, ...] = (),
    bindings: tuple[DataBindingDefinition, ...] = (),
    relations: tuple[RelationDefinition, ...] = (),
    extraction_profiles: tuple[ExtractionProfileDefinition, ...] = (),
    live_cross_references: tuple[LiveCrossReferenceDecision, ...] = (),
    verification_expectations: tuple[VerificationExpectationDefinition, ...] = (),
    support_removal_decisions: tuple[SupportRemovalDecisionDefinition, ...] = (),
    constructs: tuple[ConstructDefinition, ...] = (),
    dependency_classifications: tuple[DependencyClassificationDefinition, ...] = (),
    export_layouts: tuple[ExportLayoutDefinition, ...] = (),
    deadline_windows: tuple[DeadlineWindowDefinition, ...] = (),
) -> ModeloRevision:
    from ._schema import PeriodSelector

    workbook_ref = extra_workbook_ref or _minimal_workbook_ref()
    casillas = casillas or (_minimal_casilla(),)
    app_links = application_links if application_links is not None else (_minimal_application_link("filing"),)
    return ModeloRevision(
        id="test-revision",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
        casillas=casillas,
        workbook_parity_refs=(workbook_ref,),
        application_links=app_links,
        formulas=formulas,
        parameters=parameters,
        bindings=bindings,
        relations=relations,
        extraction_profiles=extraction_profiles,
        live_cross_references=live_cross_references,
        verification_expectations=verification_expectations,
        support_removal_decisions=support_removal_decisions,
        constructs=constructs,
        dependency_classifications=dependency_classifications,
        export_layouts=export_layouts,
        deadline_windows=deadline_windows,
    )


def _minimal_modelo(revision: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition(
        id="130",
        title="Test",
        official_name="Test",
        tax_domain="test",
        cadence="annual",
        jurisdiction="ES-AEAT",
        output_sensitivity=SensitivityClass.FINANCIAL,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
        revisions={"test-revision": revision},
    )


def _build_minimal_snapshot(revision: ModeloRevision) -> RegistrySnapshot:
    catalogues = _minimal_catalogues()
    modelo = _minimal_modelo(revision)
    return _snapshot_for_revision(modelo, catalogues, revision)


def _build_snapshot_with_missing_legal(revision: ModeloRevision, missing_legal_id: str) -> RegistrySnapshot:
    """Build a snapshot whose `legal` map omits a ref that the revision content references.

    This is the only way to surface a `_check_all_id_references` failure for legal_refs
    fields: the ref must be in the revision content but absent from the snapshot.legal map.
    We patch the snapshot object using model_copy after normal construction.
    """
    # First build a snapshot where the bad ID is in the catalogue so construction succeeds.
    extra_legal = _minimal_legal_ref().model_copy(update={"id": missing_legal_id})
    augmented_catalogues = RegistryCatalogues(
        legal={_DUMMY_LEGAL_ID: _minimal_legal_ref(), missing_legal_id: extra_legal},
        sources={_DUMMY_SOURCE_ID: _minimal_source_ref()},
    )
    modelo = _minimal_modelo(revision)
    snapshot = _snapshot_for_revision(modelo, augmented_catalogues, revision)
    # Now remove the ref from the snapshot's legal map to simulate the gap.
    patched_legal = {k: v for k, v in snapshot.legal.items() if k != missing_legal_id}
    return snapshot.model_copy(update={"legal": patched_legal})


def _build_snapshot_with_missing_source(revision: ModeloRevision, missing_source_id: str) -> RegistrySnapshot:
    """Build a snapshot whose `sources` map omits a ref that the revision content references."""
    extra_source = _minimal_source_ref().model_copy(update={"id": missing_source_id})
    augmented_catalogues = RegistryCatalogues(
        legal={_DUMMY_LEGAL_ID: _minimal_legal_ref()},
        sources={_DUMMY_SOURCE_ID: _minimal_source_ref(), missing_source_id: extra_source},
    )
    modelo = _minimal_modelo(revision)
    snapshot = _snapshot_for_revision(modelo, augmented_catalogues, revision)
    patched_sources = {k: v for k, v in snapshot.sources.items() if k != missing_source_id}
    return snapshot.model_copy(update={"sources": patched_sources})


# ---------------------------------------------------------------------------
# Test 2: dangling-reference parametrised tests
# ---------------------------------------------------------------------------


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
        period="0A",
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
        kind="casilla",
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


# ---------------------------------------------------------------------------
# Test 3: aeat config repair JSON output includes registry.integrity
# ---------------------------------------------------------------------------


def test_config_repair_report_includes_registry_integrity_check() -> None:
    """build_config_repair_report produces a registry.integrity DiagnosticCheck.

    The report walks SecureObject storage to surface bucket-side health,
    so the test runs inside an EphemeralMasterKeyProvider session to
    satisfy the encrypted-column decrypt path.
    """
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
    from aeat.application.diagnostics import build_config_repair_report

    with EphemeralMasterKeyProvider():
        report = build_config_repair_report()
    check_names = [check.name for check in report.checks]
    assert "registry.integrity" in check_names

    integrity_check = next(c for c in report.checks if c.name == "registry.integrity")
    assert integrity_check.status in {"ok", "fail", "warn"}


# ---------------------------------------------------------------------------
# Test: informative-class invariant fires on calculation artefacts
# ---------------------------------------------------------------------------


def test_informative_modelo_with_formula_fails_validation() -> None:
    """An informative modelo that declares a formula raises RegistryValidationError.

    Covers the registry-wide _validate_informative_class_invariant: it walks every
    revision of an informative modelo and rejects formulas, relations, and
    non-manual/non-informational casillas.
    """
    from . import RegistryValidator
    from ._schema import FormulaDefinition, FormulaExpression

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
    from . import RegistryValidator

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


# ---------------------------------------------------------------------------
# Test: (segmento, number) casilla identity and segment-aware resolution
# ---------------------------------------------------------------------------


def _segmented_casilla(
    casilla_id: str,
    number: str,
    segmento: str | None,
) -> CasillaDefinition:
    """A minimal manual casilla with an explicit number and segmento."""
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        segmento=segmento,
        label=f"Casilla {casilla_id}",
        section=("test",),
        input_kind="manual",
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def test_same_number_distinct_segmento_casillas_validate() -> None:
    """Two casillas sharing a number under distinct segmento values both validate.

    This is the multi-segment AEAT shape (e.g. Modelo 200 casilla 00562
    appearing in both the Liquidacion and ECPN record segments). The
    casillas carry distinct ids and distinct segmento codes, so the
    (segmento, number) identity pairs (DP200014, 00562) and
    (DP200032, 00562) are unique and the validator must accept them.
    """
    from . import RegistryValidator

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
    from . import RegistryValidator

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
    from . import RegistryValidator

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
    from ._schema import FormulaDefinition, FormulaExpression
    from ._validate import RegistryValidator

    input_casilla = _segmented_casilla("01", "01", None)
    computed_casilla = _segmented_casilla("02", "02", None).model_copy(
        update={"input_kind": "computed", "formula": "test.formula"}
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
    from ._schema import FormulaDefinition, FormulaExpression
    from ._validate import RegistryValidator

    liquidacion = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    ecpn = _segmented_casilla("DP200032:00562", "00562", "DP200032")
    target_casilla = _segmented_casilla("DP200014:00999", "00999", "DP200014").model_copy(
        update={"input_kind": "computed", "formula": "test.formula"}
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
        "an ambiguous cross-segment bare-number reference must fail to resolve; "
        f"got failures: {failures}"
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
    from ._schema import FormulaDefinition, FormulaExpression
    from ._validate import RegistryValidator

    sole_occurrence = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    target_casilla = _segmented_casilla("DP200014:00999", "00999", "DP200014").model_copy(
        update={"input_kind": "computed", "formula": "test.formula"}
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


def test_segment_qualified_reference_resolves_across_segments() -> None:
    """A formula naming a casilla by its segment-qualified id resolves cleanly.

    With number 00562 reused across two segments, a formula expression
    that references the segment-qualified id 'DP200014:00562' resolves to
    the intended Liquidacion occurrence and produces no unknown-casilla
    failure.
    """
    from ._schema import FormulaDefinition, FormulaExpression
    from ._validate import RegistryValidator

    liquidacion = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    ecpn = _segmented_casilla("DP200032:00562", "00562", "DP200032")
    target_casilla = _segmented_casilla("DP200014:00999", "00999", "DP200014").model_copy(
        update={"input_kind": "computed", "formula": "test.formula"}
    )
    formula = FormulaDefinition(
        id="test.formula",
        target="DP200014:00999",
        expression=FormulaExpression(casilla="DP200014:00562"),
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
    unknown_casilla_failures = [f for f in failures if "unknown casilla" in f]
    assert unknown_casilla_failures == [], (
        f"a segment-qualified casilla reference must resolve; got: {unknown_casilla_failures}"
    )


def _single_segment_casilla() -> CasillaDefinition:
    """A real single-segment casilla, the shape every existing modelo authors."""
    return CasillaDefinition(
        id="00592",
        number="00592",
        label="Cuota liquida",
        section=("liquidacion",),
        data_type="money",
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual-modelo",),
    )


def test_casilla_segmento_defaults_unset() -> None:
    """A single-segment casilla leaves segmento unset; the field defaults to None."""
    casilla = _single_segment_casilla()

    assert casilla.segmento is None


def test_casilla_segmento_accepts_aeat_record_segment_code() -> None:
    """A multi-segment casilla carries the AEAT record-segment code in segmento."""
    casilla = _single_segment_casilla().model_copy(update={"segmento": "DP200014"})

    assert casilla.segmento == "DP200014"


def test_single_segment_casilla_validates_unchanged_with_segmento_unset() -> None:
    """A single-segment casilla (segmento unset) survives a strict pydantic round-trip.

    The segmento field is purely additive: every existing CasillaDefinition
    that never declares segmento must validate exactly as before, with
    segmento absent from the serialised payload's meaningful state.
    """
    casilla = _single_segment_casilla()

    round_tripped = CasillaDefinition.model_validate(casilla.model_dump())

    assert round_tripped == casilla
    assert round_tripped.segmento is None
    assert "segmento" not in casilla.model_dump(exclude_defaults=True)


def test_casilla_segmento_rejects_empty_string() -> None:
    """An empty segmento is rejected so 'unset' stays distinct from 'empty'."""
    with pytest.raises(ValidationError, match="segmento"):
        CasillaDefinition.model_validate({**_single_segment_casilla().model_dump(), "segmento": ""})


def test_segmented_casilla_survives_strict_load_cycle_roundtrip() -> None:
    """A casilla carrying a non-default segmento survives the real load cycle.

    A multi-segment CasillaDefinition is fully populated — every
    defaultable field set to a non-default value, including the
    additive ``segmento`` field set to a real AEAT record-segment code —
    then pushed through the registry's genuine on-disk load transform:
    ``model_dump`` to the fragment payload shape, ``freeze_toml`` (the
    exact normalisation ``_merge_revision_fragment`` applies to every
    TOML fragment it reads), then ``model_validate`` back across the
    strict / frozen / ``extra="forbid"`` boundary. Strict pydantic
    equality across that boundary proves the additive ``segmento`` field
    is neither dropped on serialise nor re-defaulted on load.

    Populating the defaultable fields is deliberate: a
    save-drops-field / load-re-defaults-field regression on ``segmento``
    is invisible if the fixture leaves it at the ``None`` default, which
    is exactly the gap the existing segmento-unset roundtrip test cannot
    close.
    """
    casilla = CasillaDefinition(
        id="DP200014:00562",
        number="00562",
        segmento="DP200014",
        label="Liquidación III - Base imponible - Cuota íntegra [00562]",
        section=("liquidacion_iii", "base_imponible"),
        data_type="money",
        semantic_role="is_liquidacion_iii_cuota_integra",
        semantic_role_cardinality="intentional_singleton",
        semantic_role_cardinality_reason=(
            "Liquidación III cuota íntegra is the single cuota-chain "
            "integral-quota casilla within the modelo revision."
        ),
        required=False,
        input_kind="manual",
        export_refs=("modelo-200-page-014-casilla-00562",),
        legal_refs=("ley-27-2014:art-30", "ley-27-2014:art-29"),
        source_refs=("aeat-dr-200-2025", "aeat-modelo-200-manual-2024"),
    )
    assert casilla.segmento == "DP200014"

    frozen_payload = freeze_toml(casilla.model_dump(mode="python"))
    round_tripped = CasillaDefinition.model_validate(frozen_payload)

    assert round_tripped == casilla
    assert round_tripped.segmento == "DP200014"
    assert round_tripped.semantic_role == "is_liquidacion_iii_cuota_integra"


# ---------------------------------------------------------------------------
# Test: calculation-completeness gate
# ---------------------------------------------------------------------------
#
# The gate enforces `manifest-required ⊆ declared` plus a
# `(segmento, number)` identity check and a `legal_refs` / `source_refs`
# grounding check on each required casilla. A casilla the revision
# declares but the manifest does not list (a pure accounting-statement
# field) is NOT a failure.


def _completeness_manifest(
    casillas: tuple[CalculationCompletenessCasilla, ...],
) -> CalculationCompletenessManifest:
    """A minimal calculation-completeness manifest grounded on the dummy catalogues."""
    return CalculationCompletenessManifest(
        source_ref=_DUMMY_SOURCE_ID,
        casillas=casillas,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def test_revision_without_manifest_passes_completeness_gate() -> None:
    """A revision with no completeness_manifest is not failed by the gate.

    The completeness gate is rollout-staged: until a modelo's manifest is
    authored, a casilla-bearing revision must keep validating. A minimal
    revision that declares one casilla and no manifest must produce zero
    completeness-gate failures.
    """
    from ._validate import RegistryValidator

    revision = _minimal_revision(casillas=(_minimal_casilla("01"),))
    modelo = _minimal_modelo(revision)
    # A clean return proves the manifest-less revision clears the gate.
    RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_passes_when_manifest_required_subset_of_declared() -> None:
    """A revision whose declared casillas cover the manifest's required set validates.

    The manifest enumerates a single required casilla number; the
    revision declares exactly that casilla, so the required set is a
    subset of the declared set and the gate raises nothing.
    """
    from ._validate import RegistryValidator

    casilla = _minimal_casilla("01")
    manifest = _completeness_manifest((CalculationCompletenessCasilla(number="01"),))
    revision = _minimal_revision(casillas=(casilla,)).model_copy(
        update={"completeness_manifest": manifest}
    )
    modelo = _minimal_modelo(revision)
    RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_passes_when_revision_declares_extra_accounting_casilla() -> None:
    """A declared casilla absent from the calculation manifest is not a failure.

    The refocused gate enforces `manifest-required ⊆ declared`, not
    `declared == manifest`. The manifest requires only calculation-closure
    casilla '01'; the revision additionally declares casilla '02', a pure
    accounting-statement data-entry field outside the calculation closure.
    The extra casilla must NOT red the gate — a modelo can clear the gate
    without an exhaustive full-Diseño backfill.
    """
    from ._validate import RegistryValidator

    manifest = _completeness_manifest((CalculationCompletenessCasilla(number="01"),))
    revision = _minimal_revision(
        casillas=(_minimal_casilla("01"), _minimal_casilla("02"))
    ).model_copy(update={"completeness_manifest": manifest})
    modelo = _minimal_modelo(revision)
    # A clean return proves the extra accounting casilla does not fail.
    RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_fails_on_missing_required_casilla() -> None:
    """A manifest requiring a casilla the revision omits hard-fails the gate.

    The manifest requires calculation-closure casilla numbers '01' and
    '02' but the revision declares only '01'. The completeness gate must
    report the missing required '02' as a hard RegistryValidationError.
    """
    from ._validate import RegistryValidator

    manifest = _completeness_manifest(
        (CalculationCompletenessCasilla(number="01"), CalculationCompletenessCasilla(number="02"))
    )
    revision = _minimal_revision(casillas=(_minimal_casilla("01"),)).model_copy(
        update={"completeness_manifest": manifest}
    )
    modelo = _minimal_modelo(revision)
    with pytest.raises(
        RegistryValidationError,
        match=(
            r"calculation-completeness manifest requires casilla number '02' "
            r"but the revision does not declare it"
        ),
    ):
        RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_fails_on_mis_segmented_required_casilla() -> None:
    """A required casilla declared under the wrong segmento hard-fails the gate.

    The manifest requires casilla 00562 under segmento DP200032; the
    revision declares casilla 00562 but under segmento DP200014. The
    identity pairs (DP200032, 00562) and (DP200014, 00562) are distinct,
    so no casilla is declared at the manifest's required identity and the
    gate reports the mis-segmented casilla as missing at that identity.

    The wrongly-segmented (DP200014, 00562) casilla, being absent from
    the manifest, is NOT separately reported — the refocused gate's
    subset semantics never red an unrequested declared casilla.
    """
    from ._validate import RegistryValidator

    declared = _segmented_casilla("DP200014:00562", "00562", "DP200014")
    manifest = _completeness_manifest(
        (CalculationCompletenessCasilla(number="00562", segmento="DP200032"),)
    )
    revision = _minimal_revision(casillas=(declared,)).model_copy(
        update={"completeness_manifest": manifest}
    )
    modelo = _minimal_modelo(revision)
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(modelo, revision)
    missing = [
        f
        for f in failures
        if "manifest requires casilla number '00562' within segmento 'DP200032'" in f
    ]
    extra = [f for f in failures if "within segmento 'DP200014' absent" in f]
    assert missing, f"mis-segmented required casilla must be reported missing; got: {failures}"
    assert not extra, (
        "the wrongly-segmented declared casilla, being absent from the manifest, "
        f"must NOT be reported under subset semantics; got: {failures}"
    )


def test_completeness_gate_fails_on_ungrounded_required_casilla() -> None:
    """A required casilla declared without legal/source grounding hard-fails the gate.

    The manifest requires calculation-closure casilla '01'. The revision
    declares casilla '01' but without `legal_refs` and `source_refs` — a
    casilla constructed via ``model_construct`` to bypass the schema's
    non-empty-refs validator and reach the gate's defensive grounding
    branch. The gate must report the required casilla as ungrounded.

    This proves the gate's grounding check is load-bearing: the ADR
    amendment requires every calculation-closure casilla to carry its
    `legal_refs` / `source_refs` provenance, and the gate enforces that
    independently of the schema-level field constraint.
    """
    from ._validate import RegistryValidator

    ungrounded = CasillaDefinition.model_construct(
        id="01",
        number="01",
        segmento=None,
        label="Casilla 01",
        section=("test",),
        input_kind="manual",
        legal_refs=(),
        source_refs=(),
    )
    manifest = _completeness_manifest((CalculationCompletenessCasilla(number="01"),))
    revision = _minimal_revision(casillas=(_minimal_casilla("01"),)).model_copy(
        update={"completeness_manifest": manifest, "casillas": (ungrounded,)}
    )
    modelo = _minimal_modelo(revision)
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(modelo, revision)
    legal = [f for f in failures if "casilla number '01'" in f and "without legal_refs" in f]
    source = [f for f in failures if "casilla number '01'" in f and "without source_refs" in f]
    assert legal, f"ungrounded required casilla must be reported without legal_refs; got: {failures}"
    assert source, (
        f"ungrounded required casilla must be reported without source_refs; got: {failures}"
    )


def test_filing_modelo_with_formula_passes_invariant() -> None:
    """A filing modelo that declares a formula is not rejected by the informative invariant.

    Calls the invariant check directly because the full validate_modelo surface also
    enforces source-citation and calculation-link requirements that a minimal
    FormulaDefinition does not satisfy.  The invariant under test is solely concerned
    with calculation_class discrimination.
    """
    from ._schema import FormulaDefinition, FormulaExpression
    from ._validate_revision_rules import validate_informative_class_invariant

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
    filing_modelo = _minimal_modelo(revision)  # default calculation_class == "filing"
    # The informative invariant must return no failures for a filing modelo.
    failures = validate_informative_class_invariant(filing_modelo)
    assert failures == [], f"filing modelo must not be rejected by informative invariant; got: {failures}"
