"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

import pytest

from .....core import BindingSourceKind
from .. import CasillaId, validated_casilla_id
from .._schema import (
    CasillaAlias,
    CasillaConstraints,
    ConvenioRateRow,
    ModeloDefinition,
    ProfilePredicateDefinition,
    VerificationPredicateDefinition,
)
from .._schema_input_kind import InputKind
from .._validate import RegistryValidator
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    DataBindingDefinition,
    Decimal,
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
    ValidatedRegistryAuthority,
    VerificationExpectationDefinition,
    build_minimal_snapshot,
    build_snapshot_with_missing_legal,
    build_snapshot_with_missing_source,
    check_all_id_references,
    date,
    minimal_casilla,
    minimal_catalogues,
    minimal_legal_ref,
    minimal_modelo,
    minimal_revision,
    minimal_source_ref,
    minimal_workbook_ref,
    snapshot_for_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_NONEXISTENT_CASILLA: CasillaId = validated_casilla_id("nonexistent-casilla", surface="_NONEXISTENT_CASILLA")
_TEXT_CASILLA: CasillaId = validated_casilla_id("text-casilla", surface="_TEXT_CASILLA")
_NUMERIC_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_NUMERIC_CASILLA_01")
_MISSING_LEGAL_ID = "lirpf:art-99"
_MISSING_SOURCE_ID = "aeat-missing-source"
_EXTRA_LEGAL_ID = "lirpf:art-88"
_EXTRA_SOURCE_ID = "aeat-extra-source"


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


def test_committed_registry_passes_referential_integrity(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Snapshot construction and id-reference checks pass for every committed revision."""
    passed = 0
    construction_failures: list[str] = []
    for modelo in registry_authority.modelos:
        for revision in modelo.revisions.values():
            try:
                snapshot = snapshot_for_revision(modelo, registry_authority.catalogues, revision)
            except Exception as exc:
                construction_failures.append(f"{modelo.id}/{revision.id}: {exc}")
                continue
            check_all_id_references(snapshot)  # must not raise
            passed += 1
    assert not construction_failures, "snapshot construction failed:\n  " + "\n  ".join(construction_failures)
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
        update={"legal_refs": (REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID)},
    )
    revision = minimal_revision(casillas=(casilla,))
    _assert_missing_legal_ref_rejected(revision, r"casilla 01.legal_refs")


def test_dangling_casilla_source_refs() -> None:
    """casilla.source_refs referencing a SourceRefId absent from snapshot.sources raises."""
    _extra = "aeat-dr-extra-v1"
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(update={"source_refs": (REFERENCE_SOURCE_ID, _extra)})
    revision = minimal_revision(casillas=(casilla,))
    snapshot = build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"casilla 01.source_refs"):
        check_all_id_references(snapshot)


def test_casilla_alias_and_constraints_refs_must_resolve_in_registry_validation() -> None:
    """Nested casilla alias and constraints refs are catalogue-checked at registry validation."""
    alias = CasillaAlias(
        label="alternate",
        legal_refs=(_MISSING_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    constraints = CasillaConstraints(
        sign="non_negative",
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(_MISSING_SOURCE_ID,),
    )
    casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(
        update={"aliases": (alias,), "constraints": constraints},
    )
    revision = minimal_revision(casillas=(casilla,))

    failures = _modelo_validation_failures(minimal_modelo(revision))

    assert any(
        "casilla 01 alias 'alternate' references unknown legal id 'lirpf:art-99'" in failure for failure in failures
    ), f"alias legal_refs must be checked against the legal catalogue; got: {failures}"
    assert any(
        "casilla 01 constraints references unknown source id 'aeat-missing-source'" in failure for failure in failures
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
            REFERENCE_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={
            REFERENCE_SOURCE_ID: minimal_source_ref(),
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
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID, _MISSING_SOURCE_ID),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID, _extra),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(parameters=(parameter,))
    catalogues = RegistryCatalogues(
        legal={
            REFERENCE_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={REFERENCE_SOURCE_ID: minimal_source_ref()},
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
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        valid_from=date(2025, 1, 1),
    )
    parameter = ParameterDefinition(
        id="test.convenio",
        data_type="convenio_rate_table",
        unit="percent",
        convenio_rates=(row,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID, _extra),
    )
    revision = minimal_revision(bindings=(binding,))
    snapshot = build_snapshot_with_missing_source(revision, _extra)
    with pytest.raises(RegistryValidationError, match=r"binding test.binding.source_refs"):
        check_all_id_references(snapshot)


def test_dangling_relation_target_binding() -> None:
    """relation.target_binding pointing at nonexistent BindingId raises."""
    relation = RelationDefinition.model_validate(
        {
            "id": "test.relation",
            "kind": "cross_model_output",
            "dependency_role": "factual_evidence",
            "source_modelo": "100",
            "source_revision_selector": {"year_from": 2024},
            "source_casilla_id": _NUMERIC_CASILLA_01,
            "target_binding": "nonexistent.binding",
            "period_alignment": {"source_period": "0A", "target_period": "0A", "filing_year_delta": 0},
            "source_periods": ("0A",),
            "target_periods": ("0A",),
            "legal_refs": (REFERENCE_LEGAL_ID,),
            "source_refs": (REFERENCE_SOURCE_ID,),
        },
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(live_cross_references=(cross_ref,))
    _assert_missing_legal_ref_rejected(revision, r"cross_reference test.cross-ref.legal_refs")


def test_cross_reference_applicability_predicate_refs_must_resolve_in_registry_validation() -> None:
    """Cross-reference applicability predicate refs are load-blocking catalogue references."""
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
        applicability_predicates=(predicate,),
    )
    revision = minimal_revision(live_cross_references=(cross_ref,))

    failures = _modelo_validation_failures(minimal_modelo(revision))

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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
        applicability_predicates=(predicate,),
    )
    revision = minimal_revision(live_cross_references=(cross_ref,))
    catalogues = RegistryCatalogues(
        legal={
            REFERENCE_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={
            REFERENCE_SOURCE_ID: minimal_source_ref(),
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
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
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
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(verification_expectations=(expectation,))
    with pytest.raises(
        RegistryValidationError,
        match=r"verification_expectation test.expectation.computed_casilla_ids",
    ):
        build_minimal_snapshot(revision)


def test_verification_predicate_refs_must_resolve_in_registry_validation() -> None:
    """Verification predicate legal_refs are catalogue-checked at registry validation."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test.predicate",
        legal_refs=(_MISSING_LEGAL_ID,),
        expression='any_nonzero(["01"])',
    )
    revision = minimal_revision().model_copy(update={"verification_predicates": (predicate,)})

    failures = _modelo_validation_failures(minimal_modelo(revision))

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
            REFERENCE_LEGAL_ID: minimal_legal_ref(),
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={REFERENCE_SOURCE_ID: minimal_source_ref()},
    )

    snapshot = snapshot_for_revision(minimal_modelo(revision), catalogues, revision)

    assert _EXTRA_LEGAL_ID in snapshot.legal
    check_all_id_references(snapshot)


def test_snapshot_integrity_checks_verification_predicate_legal_refs() -> None:
    """Snapshot integrity rejects verification-predicate legal refs missing from the slice catalogue."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test.predicate",
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        expression='any_nonzero(["01"])',
    )
    revision = minimal_revision().model_copy(update={"verification_predicates": (predicate,)})
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)

    with pytest.raises(RegistryValidationError, match=r"verification_predicate test\.predicate\.legal_refs"):
        check_all_id_references(snapshot)
