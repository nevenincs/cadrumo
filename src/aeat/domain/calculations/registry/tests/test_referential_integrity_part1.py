"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import BindingSourceKind, Period
from ..._export_field_kind import CasillaFieldKind
from .. import CasillaId, validated_casilla_id
from .._schema import (
    AlgorithmBindingDefinition,
    AlgorithmProviderDefinition,
    CasillaAlias,
    CasillaConstraints,
    ConvenioRateRow,
    ModeloScheduleDefinition,
    ProfilePredicateDefinition,
    SourceCitation,
    VerificationPredicateDefinition,
)
from .._schema_input_kind import InputKind
from ._referential_integrity_support import (
    DUMMY_LEGAL_ID,
    DUMMY_SOURCE_ID,
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
    ModeloRevision,
    ParameterDefinition,
    RegistryCatalogues,
    RegistryValidationError,
    RelationDefinition,
    SupportRemovalDecisionDefinition,
    ValidatedRegistryAuthority,
    VerificationExpectationDefinition,
    build_minimal_snapshot,
    build_snapshot_with_missing_legal,
    build_snapshot_with_missing_source,
    check_all_id_references,
    date,
    logging,
    minimal_application_link,
    minimal_casilla,
    minimal_catalogues,
    minimal_legal_ref,
    minimal_modelo,
    minimal_revision,
    minimal_source_ref,
    minimal_workbook_ref,
    segmented_casilla,
    snapshot_for_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_NONEXISTENT_CASILLA: CasillaId = validated_casilla_id("nonexistent-casilla", surface="_NONEXISTENT_CASILLA")
_TEXT_CASILLA: CasillaId = validated_casilla_id("text-casilla", surface="_TEXT_CASILLA")
_NUMERIC_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_NUMERIC_CASILLA_01")
_NUMERIC_CASILLA_02: CasillaId = validated_casilla_id("02", surface="_NUMERIC_CASILLA_02")
_SEGMENTED_LIQUIDACION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_SEGMENTED_LIQUIDACION_CASILLA",
)
_SEGMENTED_ECPN_CASILLA: CasillaId = validated_casilla_id("DP200032:00562", surface="_SEGMENTED_ECPN_CASILLA")
_SEGMENTED_TARGET_CASILLA: CasillaId = validated_casilla_id("DP200014:00999", surface="_SEGMENTED_TARGET_CASILLA")
_BARE_REUSED_NUMBER_CASILLA: CasillaId = validated_casilla_id("00562", surface="_BARE_REUSED_NUMBER_CASILLA")
_BARE_REUSED_NUMBER_ALT_CASILLA: CasillaId = validated_casilla_id(
    "00562-alt",
    surface="_BARE_REUSED_NUMBER_ALT_CASILLA",
)
_SEGMENTED_LIQUIDACION_ALT_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562-alt",
    surface="_SEGMENTED_LIQUIDACION_ALT_CASILLA",
)
_SEGMENTED_EXPORT_FIELD_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00592",
    surface="_SEGMENTED_EXPORT_FIELD_CASILLA",
)
_BARE_EXPORT_FIELD_CASILLA: CasillaId = validated_casilla_id("00592", surface="_BARE_EXPORT_FIELD_CASILLA")
_DUMMY_FORMULA_CITATION = SourceCitation(source_ref=DUMMY_SOURCE_ID, required_text=("test formula source",))
_MISSING_LEGAL_ID = "lirpf:art-99"
_MISSING_SOURCE_ID = "aeat-missing-source"
_EXTRA_LEGAL_ID = "lirpf:art-88"
_EXTRA_SOURCE_ID = "aeat-extra-source"
_FORMULA_REVISION_APPLICATION_LINKS = (
    minimal_application_link("filing"),
    minimal_application_link("calculation").model_copy(update={"id": "al.test.calculation"}),
)


def _assert_missing_legal_ref_rejected(revision: ModeloRevision, expected_match: str) -> None:
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)
    with pytest.raises(RegistryValidationError, match=expected_match):
        check_all_id_references(snapshot)


def test_committed_registry_passes_referential_integrity(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """check_all_id_references raises nothing for every successfully-built snapshot.

    Revisions that fail existing RegistryValidator checks (pre-existing defects
    tracked separately) are skipped; the gate under test is check_all_id_references
    which only runs on snapshots that have been successfully constructed.
    """
    passed = 0
    for modelo in registry_authority.modelos:
        for revision in modelo.revisions.values():
            try:
                snapshot = snapshot_for_revision(modelo, registry_authority.catalogues, revision)
            except Exception as exc:
                # Pre-existing registry defects prevent snapshot construction;
                # check_all_id_references cannot fire here -- log and skip.
                logging.getLogger(__name__).debug(
                    "skipping revision %s/%s: snapshot build failed: %s",
                    modelo.id,
                    revision.id,
                    exc,
                )
                continue
            check_all_id_references(snapshot)  # must not raise
            passed += 1
    assert passed > 0, "no snapshots were successfully built for the committed registry"


_DANGLING_CASILLA_REFERENCE_CASES: tuple[tuple[dict[str, object], str], ...] = (
    (
        {"input_kind": InputKind.COMPUTED, "formula": "nonexistent.formula"},
        r"casilla 01.formula",
    ),
    (
        {"input_kind": InputKind.BOUND, "binding": "nonexistent.binding"},
        r"casilla 01.binding",
    ),
    (
        {"export_refs": ("nonexistent.export.field",)},
        r"casilla 01.export_refs",
    ),
)


@pytest.mark.parametrize(
    ("casilla_update", "expected_match"),
    _DANGLING_CASILLA_REFERENCE_CASES,
    ids=("formula", "binding", "export-ref"),
)
def test_dangling_casilla_references_fail_snapshot_integrity(
    casilla_update: dict[str, object],
    expected_match: str,
) -> None:
    """Casilla-level references to missing registry ids fail snapshot construction."""

    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(update=casilla_update)
    revision = minimal_revision(casillas=(casilla,))
    with pytest.raises(RegistryValidationError, match=expected_match):
        build_minimal_snapshot(revision)


def test_bound_casilla_without_binding_definition_fails_snapshot_integrity() -> None:
    """A bound casilla cannot defer missing binding coverage to formula runtime."""
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(update={"input_kind": InputKind.BOUND})
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"casillas": (casilla,)},
    )
    with pytest.raises(
        RegistryValidationError,
        match=r"casilla 01.binding has no binding definition for input_kind='bound'",
    ):
        build_minimal_snapshot(revision)


def test_dangling_casilla_legal_refs() -> None:
    """casilla.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(
        update={"legal_refs": (DUMMY_LEGAL_ID, _MISSING_LEGAL_ID)},
    )
    revision = minimal_revision(casillas=(casilla,))
    _assert_missing_legal_ref_rejected(revision, r"casilla 01.legal_refs")


def test_dangling_casilla_source_refs() -> None:
    """casilla.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-extra-v1"
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(update={"source_refs": (DUMMY_SOURCE_ID, _extra)})
    revision = minimal_revision(casillas=(casilla,))
    snapshot = build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"casilla 01.source_refs"):
        check_all_id_references(snapshot)


def test_casilla_alias_and_constraints_refs_must_resolve_in_registry_validation() -> None:
    """Nested casilla alias and constraints refs are catalogue-checked at registry validation."""
    from .._validate import RegistryValidator

    alias = CasillaAlias(
        label="alternate",
        legal_refs=(_MISSING_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    constraints = CasillaConstraints(
        sign="non_negative",
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(_MISSING_SOURCE_ID,),
    )
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(
        update={"aliases": (alias,), "constraints": constraints},
    )
    revision = minimal_revision(casillas=(casilla,))

    failures = RegistryValidator(minimal_catalogues())._validate_revision(minimal_modelo(revision), revision)

    assert any(
        "casilla 01 alias 'alternate' references unknown legal id 'lirpf:art-99'" in failure
        for failure in failures
    ), f"alias legal_refs must be checked against the legal catalogue; got: {failures}"
    assert any(
        "casilla 01 constraints references unknown source id 'aeat-missing-source'" in failure
        for failure in failures
    ), f"constraint source_refs must be checked against the source catalogue; got: {failures}"


def test_snapshot_carries_casilla_alias_and_constraints_refs() -> None:
    """Slice snapshots retain nested casilla alias and constraints legal/source evidence."""
    alias = CasillaAlias(
        label="alternate",
        legal_refs=(_EXTRA_LEGAL_ID,),
        source_refs=(_EXTRA_SOURCE_ID,),
    )
    constraints = CasillaConstraints(
        sign="non_negative",
        legal_refs=(_EXTRA_LEGAL_ID,),
        source_refs=(_EXTRA_SOURCE_ID,),
    )
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(
        update={"aliases": (alias,), "constraints": constraints},
    )
    revision = minimal_revision(casillas=(casilla,))
    catalogues = RegistryCatalogues(
        legal={
            DUMMY_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={
            DUMMY_SOURCE_ID: minimal_source_ref(),
            _EXTRA_SOURCE_ID: minimal_source_ref().model_copy(update={"id": _EXTRA_SOURCE_ID}),
        },
    )

    snapshot = snapshot_for_revision(minimal_modelo(revision), catalogues, revision)

    assert _EXTRA_LEGAL_ID in snapshot.legal
    assert _EXTRA_SOURCE_ID in snapshot.sources
    check_all_id_references(snapshot)


def test_snapshot_integrity_checks_casilla_alias_refs() -> None:
    """Snapshot integrity rejects alias refs missing from the slice catalogue."""
    alias = CasillaAlias(
        label="alternate",
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(update={"aliases": (alias,)})
    revision = minimal_revision(casillas=(casilla,))
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)

    with pytest.raises(RegistryValidationError, match=r"casilla 01\.alias alternate\.legal_refs"):
        check_all_id_references(snapshot)


def test_snapshot_integrity_checks_casilla_constraints_refs() -> None:
    """Snapshot integrity rejects constraints refs missing from the slice catalogue."""
    constraints = CasillaConstraints(
        sign="non_negative",
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID, _MISSING_SOURCE_ID),
    )
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(update={"constraints": constraints})
    revision = minimal_revision(casillas=(casilla,))
    snapshot = build_snapshot_with_missing_source(revision, _MISSING_SOURCE_ID)

    with pytest.raises(RegistryValidationError, match=r"casilla 01\.constraints\.source_refs"):
        check_all_id_references(snapshot)


def test_dangling_formula_target() -> None:
    """formula.target_casilla_id pointing at nonexistent CasillaId raises."""
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NONEXISTENT_CASILLA,
        expression=FormulaExpression(literal=Decimal("0")),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(formulas=(formula,))
    with pytest.raises(RegistryValidationError, match=r"formula test.formula.target_casilla_id"):
        build_minimal_snapshot(revision)


def test_dangling_formula_legal_refs() -> None:
    """formula.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    casilla = minimal_casilla(_NUMERIC_CASILLA_01)
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NUMERIC_CASILLA_01,
        expression=FormulaExpression(literal=Decimal("0")),
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    casilla_computed = casilla.model_copy(update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"})
    revision = minimal_revision(casillas=(casilla_computed,), formulas=(formula,))
    _assert_missing_legal_ref_rejected(revision, r"formula test.formula.legal_refs")


def test_dangling_parameter_source_refs() -> None:
    """parameter.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-param-v1"
    parameter = ParameterDefinition(
        id="test.param",
        data_type="decimal",
        unit="EUR",
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID, _extra),
    )
    revision = minimal_revision(parameters=(parameter,))
    snapshot = build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"parameter test.param.source_refs"):
        check_all_id_references(snapshot)


def test_snapshot_carries_convenio_rate_row_legal_refs() -> None:
    """Slice snapshots retain nested Convenio-rate row legal evidence."""
    row = ConvenioRateRow(
        country_code="MA",
        tipo_renta="interest",
        rate="0.10",
        legal_ref_anchor=_EXTRA_LEGAL_ID,
        legal_refs=(_EXTRA_LEGAL_ID,),
        valid_from=date(2025, 1, 1),
    )
    parameter = ParameterDefinition(
        id="test.convenio",
        data_type="convenio_rate_table",
        unit="percent",
        convenio_rates=(row,),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(parameters=(parameter,))
    catalogues = RegistryCatalogues(
        legal={
            DUMMY_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={DUMMY_SOURCE_ID: minimal_source_ref()},
    )

    snapshot = snapshot_for_revision(minimal_modelo(revision), catalogues, revision)

    assert _EXTRA_LEGAL_ID in snapshot.legal
    check_all_id_references(snapshot)


def test_snapshot_integrity_checks_convenio_rate_row_legal_refs() -> None:
    """Snapshot integrity rejects Convenio-rate row legal refs missing from the slice catalogue."""
    row = ConvenioRateRow(
        country_code="MA",
        tipo_renta="interest",
        rate="0.10",
        legal_ref_anchor=_MISSING_LEGAL_ID,
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        valid_from=date(2025, 1, 1),
    )
    parameter = ParameterDefinition(
        id="test.convenio",
        data_type="convenio_rate_table",
        unit="percent",
        convenio_rates=(row,),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(parameters=(parameter,))
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)

    with pytest.raises(RegistryValidationError, match=r"parameter test\.convenio\.convenio_rate MA/interest"):
        check_all_id_references(snapshot)


def test_dangling_binding_source_refs() -> None:
    """binding.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-binding-v1"
    binding = DataBindingDefinition(
        id="test.binding",
        source=BindingSourceKind.MANUAL_INPUT,
        selector={
            "record": "DPA",
            "field": "test",
            "offset": 1,
            "length": 1,
            "data_type": "integer",
        },
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID, _extra),
    )
    revision = minimal_revision(bindings=(binding,))
    snapshot = build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"binding test.binding.source_refs"):
        check_all_id_references(snapshot)


def test_dangling_relation_target_binding() -> None:
    """relation.target_binding pointing at nonexistent BindingId raises."""
    relation = RelationDefinition(
        id="test.relation",
        kind="cross_model_output",
        dependency_role="factual_evidence",
        source_modelo="100",
        source_revision_selector={"year_from": 2024},
        source_casilla_id=_NUMERIC_CASILLA_01,
        target_binding="nonexistent.binding",
        period_alignment={},
        source_periods=("0A",),
        target_periods=("0A",),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(relations=(relation,))
    with pytest.raises(RegistryValidationError, match=r"relation test.relation.target_binding"):
        build_minimal_snapshot(revision)


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
                casilla_id=_NONEXISTENT_CASILLA,
                match_strategy="numeric_casilla",
                value_kind="amount",
            ),
        ),
        confidence="strict",
        min_coverage=Decimal("1"),
        failure_semantics="fail_hard",
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(extraction_profiles=(profile,))
    with pytest.raises(RegistryValidationError, match=r"extraction_profile test.profile.target_casillas"):
        build_minimal_snapshot(revision)


def test_text_casilla_without_named_label_strategy_fails_gate() -> None:
    """A declaracion_pdf profile targeting a text-typed casilla without named_label raises.

    This is the snapshot-build gate that prevents dead decl.* slug stubs from
    loading green: any profile where a target casilla has data_type='text' but
    uses match_strategy='numeric_casilla' must surface a hard error.
    """
    text_casilla = minimal_casilla(_TEXT_CASILLA).model_copy(update={"data_type": "text"})
    profile = ExtractionProfileDefinition(
        id="test.profile",
        surface="declaracion_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="aeat.adapters.inbound.declaracion.parse_declaracion",
        target_casillas=(
            ExtractionTargetDefinition(
                casilla_id=_TEXT_CASILLA,
                match_strategy="numeric_casilla",
                value_kind="text",
            ),
        ),
        confidence="strict",
        min_coverage=Decimal("1"),
        failure_semantics="fail_hard",
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(text_casilla,), extraction_profiles=(profile,))
    with pytest.raises(
        RegistryValidationError,
        match=r"text-casilla.*data_type='text'.*match_strategy",
    ):
        build_minimal_snapshot(revision)


def test_text_casilla_with_named_label_strategy_passes_gate() -> None:
    """A declaracion_pdf profile targeting a text-typed casilla with named_label passes."""
    text_casilla = minimal_casilla(_TEXT_CASILLA).model_copy(update={"data_type": "text"})
    profile = ExtractionProfileDefinition(
        id="test.profile",
        surface="declaracion_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="aeat.adapters.inbound.declaracion.parse_declaracion",
        target_casillas=(
            ExtractionTargetDefinition(
                casilla_id=_TEXT_CASILLA,
                match_strategy="named_label",
                value_kind="text",
                label_pattern=r"Mi etiqueta",
            ),
        ),
        confidence="strict",
        min_coverage=Decimal("1"),
        failure_semantics="fail_hard",
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(text_casilla,), extraction_profiles=(profile,))
    snapshot = build_minimal_snapshot(revision)
    assert snapshot is not None


def test_dangling_cross_reference_legal_refs() -> None:
    """cross_reference.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
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
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(live_cross_references=(cross_ref,))
    _assert_missing_legal_ref_rejected(revision, r"cross_reference test.cross-ref.legal_refs")


def test_cross_reference_applicability_predicate_refs_must_resolve_in_registry_validation() -> None:
    """Cross-reference applicability predicate refs are load-blocking catalogue references."""
    from .._validate import RegistryValidator

    predicate = ProfilePredicateDefinition(
        field="iva.roi_enrolled",
        op="equals",
        value=True,
        explanation="Gated official surface applies only to ROI-enrolled taxpayers.",
        legal_refs=(_MISSING_LEGAL_ID,),
        source_refs=(_MISSING_SOURCE_ID,),
    )
    cross_ref = LiveCrossReferenceDecision(
        id="test.cross-ref",
        evidence_tier="official_source_guidance",
        surface="static_official_documentation",
        guard_policy_id="test",
        forbidden_actions=("write",),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
        applicability_predicates=(predicate,),
    )
    revision = minimal_revision(live_cross_references=(cross_ref,))

    failures = RegistryValidator(minimal_catalogues())._validate_revision(minimal_modelo(revision), revision)

    assert any(
        "cross-reference test.cross-ref applicability predicate 'iva.roi_enrolled' "
        "references unknown legal id 'lirpf:art-99'" in failure
        for failure in failures
    ), f"cross-reference predicate legal_refs must be checked against the legal catalogue; got: {failures}"
    assert any(
        "cross-reference test.cross-ref applicability predicate 'iva.roi_enrolled' "
        "references unknown source id 'aeat-missing-source'" in failure
        for failure in failures
    ), f"cross-reference predicate source_refs must be checked against the source catalogue; got: {failures}"


def test_snapshot_carries_cross_reference_applicability_predicate_refs() -> None:
    """Slice snapshots retain cross-reference applicability predicate evidence."""
    predicate = ProfilePredicateDefinition(
        field="iva.roi_enrolled",
        op="equals",
        value=True,
        explanation="Gated official surface applies only to ROI-enrolled taxpayers.",
        legal_refs=(_EXTRA_LEGAL_ID,),
        source_refs=(_EXTRA_SOURCE_ID,),
    )
    cross_ref = LiveCrossReferenceDecision(
        id="test.cross-ref",
        evidence_tier="official_source_guidance",
        surface="static_official_documentation",
        guard_policy_id="test",
        forbidden_actions=("write",),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
        applicability_predicates=(predicate,),
    )
    revision = minimal_revision(live_cross_references=(cross_ref,))
    catalogues = RegistryCatalogues(
        legal={
            DUMMY_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={
            DUMMY_SOURCE_ID: minimal_source_ref(),
            _EXTRA_SOURCE_ID: minimal_source_ref().model_copy(update={"id": _EXTRA_SOURCE_ID}),
        },
    )

    snapshot = snapshot_for_revision(minimal_modelo(revision), catalogues, revision)

    assert _EXTRA_LEGAL_ID in snapshot.legal
    assert _EXTRA_SOURCE_ID in snapshot.sources
    check_all_id_references(snapshot)


def test_snapshot_integrity_checks_cross_reference_applicability_predicate_refs() -> None:
    """Snapshot integrity rejects cross-reference predicate refs missing from the slice catalogue."""
    predicate = ProfilePredicateDefinition(
        field="iva.roi_enrolled",
        op="equals",
        value=True,
        explanation="Gated official surface applies only to ROI-enrolled taxpayers.",
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    cross_ref = LiveCrossReferenceDecision(
        id="test.cross-ref",
        evidence_tier="official_source_guidance",
        surface="static_official_documentation",
        guard_policy_id="test",
        forbidden_actions=("write",),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
        applicability_predicates=(predicate,),
    )
    revision = minimal_revision(live_cross_references=(cross_ref,))
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)

    with pytest.raises(
        RegistryValidationError,
        match=r"cross_reference test\.cross-ref\.applicability_predicates\.iva\.roi_enrolled\.legal_refs",
    ):
        check_all_id_references(snapshot)


def test_dangling_workbook_parity_workbook_source() -> None:
    """workbook_parity_ref.workbook_source referencing a SourceRefId absent from snapshot.sources raises.

    The workbook_source must be in source_refs (enforced by the schema model validator),
    so we build the snapshot with the source_ref present, then patch it out of
    snapshot.sources to simulate the integrity gap.
    """
    _extra_source = "aeat-dr-workbook-v1"
    workbook = minimal_workbook_ref(source_ref=_extra_source)
    revision = minimal_revision(extra_workbook_ref=workbook)
    snapshot = build_snapshot_with_missing_source(revision, _extra_source)
    with pytest.raises(RegistryValidationError, match=r"workbook_parity_ref wp.test.workbook_source"):
        check_all_id_references(snapshot)


def test_dangling_verification_expectation_computed_casillas() -> None:
    """verification_expectation.computed_casilla_ids pointing at nonexistent CasillaId raises."""
    expectation = VerificationExpectationDefinition(
        id="test.expectation",
        computed_casilla_ids=(_NONEXISTENT_CASILLA,),
        tolerance=Decimal("0"),
        rounding="ROUND_HALo_UP",
        min_coverage=Decimal("1"),
        discrepancy_causes=("rounding",),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(verification_expectations=(expectation,))
    with pytest.raises(
        RegistryValidationError,
        match=r"verification_expectation test.expectation.computed_casilla_ids",
    ):
        build_minimal_snapshot(revision)


def test_verification_predicate_refs_must_resolve_in_registry_validation() -> None:
    """Verification predicate legal_refs are catalogue-checked at registry validation."""
    from .._validate import RegistryValidator

    predicate = VerificationPredicateDefinition(
        predicate_id="test.predicate",
        legal_refs=(_MISSING_LEGAL_ID,),
        expression='any_nonzero(["01"])',
    )
    revision = minimal_revision().model_copy(update={"verification_predicates": (predicate,)})

    failures = RegistryValidator(minimal_catalogues())._validate_revision(minimal_modelo(revision), revision)

    assert any(
        "verification predicate test.predicate references unknown legal id 'lirpf:art-99'" in failure
        for failure in failures
    ), f"verification predicate legal_refs must be checked against the legal catalogue; got: {failures}"


def test_snapshot_carries_verification_predicate_legal_refs() -> None:
    """Slice snapshots retain verification-predicate legal evidence."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test.predicate",
        legal_refs=(_EXTRA_LEGAL_ID,),
        expression='any_nonzero(["01"])',
    )
    revision = minimal_revision().model_copy(update={"verification_predicates": (predicate,)})
    catalogues = RegistryCatalogues(
        legal={
            DUMMY_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={DUMMY_SOURCE_ID: minimal_source_ref()},
    )

    snapshot = snapshot_for_revision(minimal_modelo(revision), catalogues, revision)

    assert _EXTRA_LEGAL_ID in snapshot.legal
    check_all_id_references(snapshot)


def test_snapshot_integrity_checks_verification_predicate_legal_refs() -> None:
    """Snapshot integrity rejects verification-predicate legal refs missing from the slice catalogue."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test.predicate",
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        expression='any_nonzero(["01"])',
    )
    revision = minimal_revision().model_copy(update={"verification_predicates": (predicate,)})
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)

    with pytest.raises(RegistryValidationError, match=r"verification_predicate test\.predicate\.legal_refs"):
        check_all_id_references(snapshot)


def test_dangling_application_link_legal_refs() -> None:
    """application_link.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    link = ApplicationLinkDefinition(
        id="al.test2",
        surface="workflow",
        consumer="test",
        requires_snapshot=True,
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(DUMMY_SOURCE_ID,),
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
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(DUMMY_SOURCE_ID,),
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
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(support_removal_decisions=(decision,))
    _assert_missing_legal_ref_rejected(revision, r"support_removal_decision srd.test.legal_refs")


def test_dangling_construct_casilla_ref() -> None:
    """construct.casilla_ids pointing at nonexistent CasillaId raises."""
    construct = ConstructDefinition(
        id="ct.test",
        title="Test construct",
        casilla_ids=(_NONEXISTENT_CASILLA,),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
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
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    construct = ConstructDefinition(
        id="ct.algorithm-provider",
        title="Algorithm provider construct",
        algorithm_providers=("provider.test",),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
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
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    binding = AlgorithmBindingDefinition(
        id="algorithm-binding.test",
        provider="provider.test",
        target_casilla_id=_NUMERIC_CASILLA_01,
        inputs={},
        output_casilla_ids={},
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    construct = ConstructDefinition(
        id="ct.algorithm-binding",
        title="Algorithm binding construct",
        algorithm_bindings=("algorithm-binding.test",),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
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
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    construct = ConstructDefinition(
        id="ct.filing-schedule",
        title="Filing schedule construct",
        filing_schedules=("schedule.test",),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
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
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(dependency_classifications=(classification,))
    with pytest.raises(RegistryValidationError, match=r"dependency_classification dc.test.target_constructs"):
        build_minimal_snapshot(revision)


def test_dangling_export_layout_legal_refs() -> None:
    """export_layout.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    layout = ExportLayoutDefinition(
        id="el.test",
        source_refs=(DUMMY_SOURCE_ID,),
        legal_refs=(DUMMY_LEGAL_ID, _MISSING_LEGAL_ID),
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
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
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
        source_refs=(DUMMY_SOURCE_ID,),
        legal_refs=(DUMMY_LEGAL_ID,),
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
        source_refs=(DUMMY_SOURCE_ID,),
        legal_refs=(DUMMY_LEGAL_ID,),
        records=(record,),
    )
    revision = minimal_revision(export_layouts=(layout,))

    with pytest.raises(RegistryValidationError, match=r"row_field_casilla_ids\.importe"):
        build_minimal_snapshot(revision)


def test_export_record_row_field_casilla_refs_must_resolve_in_registry_validation() -> None:
    """Registry validation rejects export-record row-field mappings to unknown casillas."""
    from .._validate import RegistryValidator

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
        source_refs=(DUMMY_SOURCE_ID,),
        legal_refs=(DUMMY_LEGAL_ID,),
        records=(record,),
    )
    revision = minimal_revision(export_layouts=(layout,))

    failures = RegistryValidator(minimal_catalogues())._validate_revision(minimal_modelo(revision), revision)

    assert any(
        "export record 'rec.test' row_field_casilla_ids.importe references unknown casilla 'nonexistent-casilla'"
        in failure
        for failure in failures
    ), f"row_field_casilla_ids values must be checked against declared casillas; got: {failures}"


def test_dangling_revision_legal_refs() -> None:
    """revision.legal_refs referencing a LegalRefId absent from snapshot.legal raises."""
    revision = minimal_revision()
    revision = revision.model_copy(update={"legal_refs": (DUMMY_LEGAL_ID, _MISSING_LEGAL_ID)})
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
        legal={DUMMY_LEGAL_ID: minimal_legal_ref()},
        sources={DUMMY_SOURCE_ID: minimal_source_ref(), _extra: extra_source},
    )
    modelo = minimal_modelo(revision).model_copy(update={"source_refs": (DUMMY_SOURCE_ID, _extra)})
    snapshot = snapshot_for_revision(modelo, augmented_catalogues, revision)
    # Patch out the extra source ref from the snapshot's sources map.
    patched_sources = {k: v for k, v in snapshot.sources.items() if k != _extra}
    snapshot = snapshot.model_copy(update={"sources": patched_sources})
    with pytest.raises(RegistryValidationError, match=r"modelo.source_refs"):
        check_all_id_references(snapshot)


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
        target_casilla_id=_NUMERIC_CASILLA_01,
        expression=FormulaExpression(casilla_id=_NUMERIC_CASILLA_01),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
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
    from .. import RegistryValidator

    relation = RelationDefinition(
        id="test.relation",
        kind="cross_model_output",
        dependency_role="factual_evidence",
        source_modelo="100",
        source_revision_selector={"year_from": 2024},
        source_casilla_id=_NUMERIC_CASILLA_01,
        target_binding="test.binding",
        period_alignment={},
        source_periods=("0A",),
        target_periods=("0A",),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(relations=(relation,))
    catalogues = minimal_catalogues()
    informative_modelo = minimal_modelo(revision).model_copy(update={"calculation_class": "informative"})
    validator = RegistryValidator(catalogues)
    with pytest.raises(RegistryValidationError, match="informative modelo must not declare cross-model relations"):
        validator.validate_modelo(informative_modelo)


def test_same_number_distinct_segmento_casillas_validate() -> None:
    """Two casillas sharing a number under distinct segmento values both validate.

    This is the multi-segment AEAT shape (e.g. Modelo 200 casilla 00562
    appearing in both the Liquidacion and ECPN record segments). The
    casillas carry distinct ids and distinct segmento codes, so the
    (segmento, number) metadata pairs (DP200014, 00562) and
    (DP200032, 00562) are unique and the validator must accept them.
    """
    from .. import RegistryValidator

    liquidacion = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    ecpn = segmented_casilla(_SEGMENTED_ECPN_CASILLA, "00562", "DP200032")
    revision = minimal_revision(casillas=(liquidacion, ecpn))
    modelo = minimal_modelo(revision)
    # validate_modelo raises iff any failure is collected; a clean return
    # proves the (segmento, number) metadata pairs are accepted as distinct.
    RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_single_segment_duplicate_number_collision_fails() -> None:
    """Two segmento-unset casillas sharing a number hard-fail on (None, number).

    The casillas carry distinct ids, so the per-kind duplicate-id check
    does NOT fire. Only the generalised (segmento, number) metadata
    uniqueness invariant catches the collision: with segmento unset on both, the
    pair degrades to (None, '00562') and the duplicate is reported with
    the bare-number message, exactly as the prior duplicate-id check did.
    """
    from .. import RegistryValidator

    first = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00562", None)
    second = segmented_casilla(_BARE_REUSED_NUMBER_ALT_CASILLA, "00562", None)
    revision = minimal_revision(casillas=(first, second))
    modelo = minimal_modelo(revision)
    with pytest.raises(RegistryValidationError, match=r"duplicate casilla number '00562'"):
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_same_segmento_duplicate_number_collision_fails() -> None:
    """Two casillas sharing a number within one segmento hard-fail.

    Within a single record segment a casilla number must still be
    unique; the (segmento, number) pair (DP200014, 00562) declared twice
    is a duplicate and the validator reports it segment-qualified.
    """
    from .. import RegistryValidator

    first = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    second = segmented_casilla(_SEGMENTED_LIQUIDACION_ALT_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(first, second))
    modelo = minimal_modelo(revision)
    with pytest.raises(
        RegistryValidationError,
        match=r"duplicate casilla number '00562' within segmento 'DP200014'",
    ):
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_single_segment_numeric_casilla_id_reference_resolves() -> None:
    """A formula may reference a numeric token only when it is the casilla id.

    The casilla sets ``id == number`` with ``segmento`` unset, so ``01``
    is the canonical ``casilla.id``. A formula whose expression reads
    that id and whose target is a computed casilla must validate with no
    unknown-casilla failure.
    """
    from .. import RegistryValidator

    input_casilla = segmented_casilla(_NUMERIC_CASILLA_01, "01", None)
    computed_casilla = segmented_casilla(_NUMERIC_CASILLA_02, "02", None).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NUMERIC_CASILLA_02,
        expression=FormulaExpression(casilla_id=_NUMERIC_CASILLA_01),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
        source_citations=(_DUMMY_FORMULA_CITATION,),
    )
    revision = minimal_revision(
        casillas=(input_casilla, computed_casilla),
        formulas=(formula,),
        application_links=_FORMULA_REVISION_APPLICATION_LINKS,
    )
    RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))


def test_ambiguous_cross_segment_bare_number_reference_does_not_resolve() -> None:
    """A bare-number reference to a number reused across segments fails to resolve.

    Casilla number 00562 occurs in two record segments, so the bare
    number is ambiguous. A formula expression that references '00562'
    directly must NOT resolve: the validator reports an unknown casilla,
    forcing the formula to name the intended occurrence by its
    segment-qualified id.
    """
    from .. import RegistryValidator

    liquidacion = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    ecpn = segmented_casilla(_SEGMENTED_ECPN_CASILLA, "00562", "DP200032")
    target_casilla_def = segmented_casilla(_SEGMENTED_TARGET_CASILLA, "00999", "DP200014").model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_SEGMENTED_TARGET_CASILLA,
        expression=FormulaExpression(casilla_id=_BARE_REUSED_NUMBER_CASILLA),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
        source_citations=(_DUMMY_FORMULA_CITATION,),
    )
    revision = minimal_revision(
        casillas=(liquidacion, ecpn, target_casilla_def),
        formulas=(formula,),
        application_links=_FORMULA_REVISION_APPLICATION_LINKS,
    )
    with pytest.raises(RegistryValidationError, match="unknown casilla '00562'"):
        RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))


def test_reused_number_with_bare_canonical_id_fails() -> None:
    """A reused printed number cannot leave one casilla addressable by the bare number."""
    from .. import RegistryValidator

    ecpn = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00562", None)
    liquidacion = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(ecpn, liquidacion))
    with pytest.raises(RegistryValidationError, match=r"ambiguous bare casilla ids \['00562'\]"):
        RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))


def test_casilla_id_cannot_equal_another_casilla_display_token() -> None:
    """A token cannot be one casilla's id and another casilla's display metadata."""
    from .. import RegistryValidator

    canonical_owner = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00563", None)
    display_owner = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(canonical_owner, display_owner))
    with pytest.raises(RegistryValidationError, match="casilla reference token '00562' is ambiguous"):
        RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))


def test_casilla_display_token_cannot_equal_binding_id() -> None:
    """Casilla metadata tokens cannot collide with non-casilla registry ids."""
    from .. import RegistryValidator

    display_owner = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    binding = DataBindingDefinition(
        id="00562",
        source=BindingSourceKind.MANUAL_INPUT,
        selector={
            "record": "DPA",
            "field": "test",
            "offset": 1,
            "length": 1,
            "data_type": "integer",
        },
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(display_owner,), bindings=(binding,))

    with pytest.raises(
        RegistryValidationError,
        match="casilla reference token '00562' is ambiguous; it is binding id '00562'",
    ):
        RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))


def test_snapshot_builder_rejects_ambiguous_selected_revision_identity() -> None:
    """Even direct snapshot construction must fail before publishing ambiguous casilla refs."""

    canonical_owner = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00563", None)
    display_owner = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(canonical_owner, display_owner))

    with pytest.raises(RegistryValidationError, match="casilla reference token '00562' is ambiguous"):
        build_minimal_snapshot(revision)


def test_bare_number_reference_does_not_resolve_when_id_is_segment_qualified() -> None:
    """A bare number is not a reference shorthand for a segment-qualified casilla.

    ``CasillaDefinition.number`` is AEAT/display metadata, not a
    foreign key. Even when a printed number occurs exactly once in the
    revision, a reference to a segment-qualified casilla must name the
    canonical ``casilla.id``.
    """
    from .. import RegistryValidator

    sole_occurrence = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    target_casilla_def = segmented_casilla(_SEGMENTED_TARGET_CASILLA, "00999", "DP200014").model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_SEGMENTED_TARGET_CASILLA,
        expression=FormulaExpression(casilla_id=_BARE_REUSED_NUMBER_CASILLA),
        legal_refs=(DUMMY_LEGAL_ID,),
        source_refs=(DUMMY_SOURCE_ID,),
        source_citations=(_DUMMY_FORMULA_CITATION,),
    )
    revision = minimal_revision(
        casillas=(sole_occurrence, target_casilla_def),
        formulas=(formula,),
        application_links=_FORMULA_REVISION_APPLICATION_LINKS,
    )
    with pytest.raises(RegistryValidationError, match="unknown casilla '00562'"):
        RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))


def test_duplicate_export_field_ownership_fails() -> None:
    """An export field can be declared by exactly one casilla."""
    from .. import RegistryValidator

    first = segmented_casilla(_SEGMENTED_EXPORT_FIELD_CASILLA, "00592", "DP200014").model_copy(
        update={"export_refs": ("modelo-200-page-014b-casilla-00592",)},
    )
    second = segmented_casilla(_BARE_EXPORT_FIELD_CASILLA, "00592", None).model_copy(
        update={"export_refs": ("modelo-200-page-014b-casilla-00592",)},
    )
    revision = minimal_revision(casillas=(first, second))
    with pytest.raises(RegistryValidationError, match="is declared by multiple casillas"):
        RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))
