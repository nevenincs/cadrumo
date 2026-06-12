"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from .. import RegistrySnapshot
from ._registry_schema_support import (
    _EXPECTED_DEADLINE_WINDOWS,
    _EXPECTED_LIVE_CROSS_REFERENCES,
    _REGISTRY_ROOT,
    _REQUIRED_APPLICATION_LINKS,
    _SNAPSHOT_HEADER_EXPECTATIONS,
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
    ExportFieldDefinition,
    ExtractionTargetDefinition,
    FormulaExpression,
    ModeloRevision,
    Path,
    RegistryLoadError,
    RegistryValidationError,
    RegistryValidator,
    SupportRemovalDecisionDefinition,
    ValidationError,
    _committed_modelo,
    _committed_registry,
    _copy_committed_modelo,
    _revision,
    _with_first_export_field,
    _with_revision,
    build_model_law_coverage_ledger,
    build_snapshot,
    bundled_path,
    date,
    load_modelo_file,
    load_registry_tree,
    re,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def _modelo_130_snapshot(registry_snapshot: Callable[[str, int, str], RegistrySnapshot]) -> RegistrySnapshot:
    return registry_snapshot("130", 2024, "3T")


def test_formula_expression_accepts_dispatch_table_entries() -> None:
    expression = FormulaExpression.model_validate(
        {
            "dispatch_table_entries": [
                {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                {"key": "cataluna", "parameter": "renta-2025-escala-autonomica-cataluna-base-general"},
            ],
        },
    )

    assert expression.dispatch_table == {
        "madrid": "renta-2025-escala-autonomica-madrid-base-general",
        "cataluna": "renta-2025-escala-autonomica-cataluna-base-general",
    }


def test_formula_expression_rejects_duplicate_dispatch_table_entries() -> None:
    with pytest.raises(ValidationError, match="duplicate key 'madrid'"):
        FormulaExpression.model_validate(
            {
                "dispatch_table_entries": [
                    {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                    {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                ],
            },
        )


def test_formula_expression_rejects_mixed_dispatch_table_shapes() -> None:
    with pytest.raises(ValidationError, match="dispatch_table or dispatch_table_entries"):
        FormulaExpression.model_validate(
            {
                "dispatch_table": {"madrid": "renta-2025-escala-autonomica-madrid-base-general"},
                "dispatch_table_entries": [
                    {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                ],
            },
        )


@pytest.mark.parametrize(("attr_path", "expected"), _SNAPSHOT_HEADER_EXPECTATIONS)
def test_committed_snapshot_resolves_header_field(_modelo_130_snapshot, attr_path: str, expected: object) -> None:  # type: ignore[no-untyped-def]
    """Snapshot ``(modelo, revision, filing_year, period)`` tuple matches the committed registry coordinates."""
    actual: object = _modelo_130_snapshot
    for segment in attr_path.split("."):
        actual = getattr(actual, segment)
    assert actual == expected


def test_committed_snapshot_indexes_legal_reference_with_authority_tier(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    """Legal-reference is indexed and its evidence_tier reads as legal_authority."""
    assert "rd-439-2007:art-110" in _modelo_130_snapshot.legal
    assert _modelo_130_snapshot.legal["rd-439-2007:art-110"].evidence_tier == "legal_authority"


def test_committed_snapshot_indexes_source_reference_with_layout_tier(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    """Source-reference is indexed and its evidence_tier reads as layout_authority."""
    assert "aeat-dr-130-2019-v12" in _modelo_130_snapshot.sources
    assert _modelo_130_snapshot.sources["aeat-dr-130-2019-v12"].evidence_tier == "layout_authority"


def test_committed_snapshot_lists_single_extraction_profile(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert tuple(_modelo_130_snapshot.extraction_profiles) == ("modelo-130-declaracion-pdf",)


def test_committed_snapshot_lists_expected_live_cross_references(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert set(_modelo_130_snapshot.live_cross_references) == _EXPECTED_LIVE_CROSS_REFERENCES


def test_committed_snapshot_static_cross_reference_carries_layout_tier(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert _modelo_130_snapshot.live_cross_references["modelo-130-static-official"].evidence_tier == "layout_authority"


def test_committed_snapshot_filed_declarations_read_is_authenticated_read_surface(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    """The filed-declarations cross-reference must declare an authenticated read surface."""
    filed_read = _modelo_130_snapshot.live_cross_references["modelo-130-filed-declarations-read"]
    assert filed_read.surface == "authenticated_read_surface"
    assert set(filed_read.allowed_methods).issubset({"GET", "HEAD", "OPTIONS"})
    assert filed_read.requires_authentication is True
    assert filed_read.requires_aeat_authorization is True


def test_committed_snapshot_lists_single_workbook_parity_ref(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert tuple(_modelo_130_snapshot.workbook_parity_refs) == ("modelo-130-dr-xls",)


def test_committed_snapshot_lists_single_verification_expectation(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert tuple(_modelo_130_snapshot.verification_expectations) == ("modelo-130-calculation-verification",)


def test_committed_snapshot_declares_no_support_removal_decisions(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert _modelo_130_snapshot.support_removal_decisions == {}


def test_committed_registry_contains_no_zero_casilla_revisions() -> None:
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)

    zero_casilla_revisions = [
        (modelo.id, revision.id)
        for modelo in modelos
        for revision in modelo.revisions.values()
        if not revision.casillas
    ]

    assert zero_casilla_revisions == []


def test_revision_without_casillas_is_registry_validation_failure() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    empty_revision = revision.model_copy(
        update={
            "casillas": (),
            "formulas": (),
            "bindings": (),
            "relations": (),
            "export_layouts": (),
            "extraction_profiles": (),
            "verification_expectations": (),
        },
    )

    with pytest.raises(
        RegistryValidationError,
        match="revision must declare at least one casilla",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, empty_revision),
        )


def test_committed_snapshot_lists_four_quarterly_deadline_windows(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert tuple(_modelo_130_snapshot.deadline_windows) == _EXPECTED_DEADLINE_WINDOWS


def test_committed_snapshot_application_links_cover_required_surfaces(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert set(_modelo_130_snapshot.application_links) >= _REQUIRED_APPLICATION_LINKS


def test_model_law_coverage_ledger_does_not_count_layout_source_as_guidance() -> None:
    modelo, catalogues = _committed_registry()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="3T")
    layout_only_snapshot = snapshot.model_copy(
        update={
            "sources": {
                source_id: source.model_copy(update={"evidence_tier": "layout_authority"})
                for source_id, source in snapshot.sources.items()
            },
            "live_cross_references": {
                cross_reference_id: cross_reference.model_copy(update={"evidence_tier": "layout_authority"})
                for cross_reference_id, cross_reference in snapshot.live_cross_references.items()
            },
        },
    )

    layout_only_ledger = build_model_law_coverage_ledger(layout_only_snapshot)

    assert {gate.tier for gate in layout_only_ledger.gates} == {
        "legal_authority",
        "official_source_guidance",
        "executable_parity_evidence",
        "layout_authority",
    }
    by_tier = {gate.tier: gate for gate in layout_only_ledger.gates}

    assert by_tier["official_source_guidance"].status == "gap"
    assert by_tier["layout_authority"].status == "satisfied"


def test_model_law_coverage_ledger_moves_status_when_evidence_tier_changes() -> None:
    modelo, catalogues = _committed_registry()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="3T")
    source_id, source = next(iter(snapshot.sources.items()))
    workbook_id, workbook = next(iter(snapshot.workbook_parity_refs.items()))
    cross_reference_id, cross_reference = next(iter(snapshot.live_cross_references.items()))
    parity_source = source.model_copy(update={"evidence_tier": "executable_parity_evidence"})
    parity_workbook = workbook.model_copy(
        update={
            "formula_coverage": "formula_form",
            "runner_required": True,
            "output_cells": {"result": "Modelo!A1"},
        },
    )
    guidance_cross_reference = cross_reference.model_copy(update={"evidence_tier": "official_source_guidance"})
    parity_snapshot = snapshot.model_copy(
        update={
            "sources": {source_id: parity_source},
            "workbook_parity_refs": {workbook_id: parity_workbook},
            "live_cross_references": {cross_reference_id: guidance_cross_reference},
        },
    )

    by_tier = {gate.tier: gate for gate in build_model_law_coverage_ledger(parity_snapshot).gates}

    assert by_tier["executable_parity_evidence"].status == "satisfied"
    assert by_tier["layout_authority"].status == "gap"


def test_modelo_file_rejects_local_source_catalogue(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    path.write_text(path.read_text(encoding="utf-8") + '\n[source."local"]\nkind = "record_design"\n', encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="must not define local legal/source"):
        load_modelo_file(path)


def test_modelo_file_rejects_empty_filing_grade_evidence(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    text = path.read_text(encoding="utf-8")
    mutated, replacements = re.subn(
        r"legal_refs = \[[^\]]+\]",
        "legal_refs = []",
        text,
        count=1,
    )
    assert replacements == 1, "M130 fixture must contain at least one legal_refs list"
    path.write_text(mutated, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="too_short"):
        load_modelo_file(path)


def test_snapshot_requires_source_integrity(tmp_path: Path) -> None:
    modelo, catalogues = _committed_registry()

    with pytest.raises(RegistryValidationError, match="missing corpus file"):
        build_snapshot(modelo, catalogues, source_root=tmp_path, filing_year=2024, period="3T")


def test_validator_rejects_duplicate_formula_targets() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    duplicate = revision.formulas[0].model_copy(update={"id": f"{revision.formulas[0].id}-duplicate"})
    mutated = revision.model_copy(update={"formulas": (*revision.formulas, duplicate)})

    with pytest.raises(RegistryValidationError, match="duplicate formula target"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_formula_id_matching_casilla_id() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = revision.formulas[0]
    renamed_formula = formula.model_copy(update={"id": formula.target})
    casillas = tuple(
        casilla.model_copy(update={"formula": renamed_formula.id}) if casilla.id == formula.target else casilla
        for casilla in revision.casillas
    )
    formulas = (renamed_formula, *revision.formulas[1:])
    mutated = revision.model_copy(update={"casillas": casillas, "formulas": formulas})

    with pytest.raises(RegistryValidationError, match=f"duplicate registry id '{formula.target}'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_formula_target_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = revision.formulas[0]
    mismatched_formula = formula.model_copy(update={"target": "01"})
    mutated = revision.model_copy(update={"formulas": (mismatched_formula, *revision.formulas[1:])})

    with pytest.raises(RegistryValidationError, match="targeting '01'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_workbook_parity_coverage() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo).model_copy(update={"workbook_parity_refs": ()})

    with pytest.raises(RegistryValidationError, match="must declare official workbook parity coverage"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, revision))


def test_modelo_file_rejects_unknown_support_removal_decision(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    path.write_text(
        path.read_text(encoding="utf-8")
        + """

[[revisions."2019-y-siguientes".support_removal_decisions]]
id = "modelo-130-invalid-removal-decision"
subject_type = "filing_path"
subject_id = "aeat.entrypoints.cli.modelo"
decision = "not_a_supported_removal_decision"
reason = "out_of_scope"
evidence_note = "Invalid support-removal decision value."
legal_refs = ["rd-439-2007:art-110"]
source_refs = ["aeat-dr-130-2019-v12"]
""",
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="remove_from_filing_grade"):
        load_modelo_file(path)


def test_validator_rejects_removal_decision_for_active_registry_surface() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    decision = SupportRemovalDecisionDefinition(
        id="modelo-130-remove-active-export",
        subject_type="export_layout",
        subject_id=revision.export_layouts[0].id,
        decision="remove_from_filing_grade",
        reason="out_of_scope",
        evidence_note="The active export layout cannot also be recorded as removed.",
        legal_refs=("rd-439-2007:art-110",),
        source_refs=("aeat-dr-130-2019-v12",),
    )
    mutated = revision.model_copy(update={"support_removal_decisions": (decision,)})

    with pytest.raises(RegistryValidationError, match="but it is still present"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_modelo_file_rejects_formula_workbook_without_runner(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    text = path.read_text(encoding="utf-8").replace(
        'formula_coverage = "record_design_layout"',
        'formula_coverage = "formula_form"',
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="formula coverage requires a runner"):
        load_modelo_file(path)


def test_validator_rejects_formula_workbook_without_executable_parity_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    workbook = revision.workbook_parity_refs[0].model_copy(
        update={
            "formula_coverage": "formula_form",
            "runner_required": True,
            "output_cells": {"result": "Modelo!A1"},
        },
    )
    mutated = revision.model_copy(update={"workbook_parity_refs": (workbook,)})

    with pytest.raises(RegistryValidationError, match="requires executable parity evidence source"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_formula_without_official_source_guidance() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formulas = tuple(
        formula.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
        if formula.id == "modelo-130-pago-fraccionado-directa"
        else formula
        for formula in revision.formulas
    )
    mutated = revision.model_copy(update={"formulas": formulas})

    with pytest.raises(RegistryValidationError, match="requires official_source_guidance source evidence"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_formula_citation_missing_from_official_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = next(item for item in revision.formulas if item.id == "modelo-130-pago-fraccionado-directa")
    bad_citations = tuple(
        citation.model_copy(update={"required_text": ("official source does not contain this calculation anchor",)})
        for citation in formula.source_citations
    )
    formulas = tuple(
        item.model_copy(update={"source_citations": bad_citations}) if item.id == formula.id else item
        for item in revision.formulas
    )
    mutated = revision.model_copy(update={"formulas": formulas})

    with pytest.raises(RegistryValidationError, match=r"source citation .* missing text"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_binding_citation_missing_from_official_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0]
    bad_citations = tuple(
        citation.model_copy(update={"required_text": ("official source does not contain this binding anchor",)})
        for citation in binding.source_citations
    )
    bindings = tuple(
        item.model_copy(update={"source_citations": bad_citations}) if item.id == binding.id else item
        for item in revision.bindings
    )
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match=r"source citation .* missing text"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_binding_without_typed_selector() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "collectible_invoice",
            "selector": {"claves": ("E",)},
            "aggregation": {"op": "sum"},
        },
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="malformed invoice selector"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_profile_binding_selector_missing_from_user_profile_schema() -> None:
    modelo, catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    binding = next(item for item in revision.bindings if item.source == "profile")
    mutated_binding = binding.model_copy(update={"selector": {**binding.selector, "profile_key": "unknown.profile"}})
    mutated = revision.model_copy(
        update={"bindings": tuple(mutated_binding if item.id == binding.id else item for item in revision.bindings)},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"user-profile schema .* selector 'unknown\.profile'",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_binding_aggregation_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "collectible_invoice",
            "selector": {"fact": "operator_count", "claves": ("E",)},
            "aggregation": {"op": "sum"},
        },
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="requires aggregation op 'count_distinct'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_rectification_delta_without_rectification_scope() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "collectible_invoice",
            "selector": {"fact": "rectified_base_delta_sum", "claves": ("E",)},
            "aggregation": {"op": "sum"},
        },
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="requires rectification_scope 'only_rectifications'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_period_rows_without_rectification_scope() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "collectible_invoice",
            "selector": {
                "fact": "row_field",
                "row_field": "base_imponible",
                "grouping": "operator_clave_period",
                "claves": ("E",),
            },
            "aggregation": {"op": "rows"},
        },
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="grouping 'operator_clave_period' requires"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_export_fields_can_reference_structured_bindings() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    bound_revision = _with_first_export_field(
        revision,
        ExportFieldDefinition.model_validate(
            {
                **revision.export_layouts[0].records[0].fields[0].model_dump(mode="python"),
                "id": "modelo-130-export-bound-net-income",
                "kind": "binding",
                "binding": revision.bindings[0].id,
                "casilla": None,
                "literal": None,
                "header_key": None,
                "draft_attribute": None,
                "computed_key": None,
                "data_type": "money",
                "required": False,
                "padding": "left_zero",
                "justification": "right",
            },
        ),
    )

    new_field = bound_revision.export_layouts[0].records[0].fields[0]
    assert new_field.kind == "binding"
    assert new_field.binding == revision.bindings[0].id
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, bound_revision))


def test_validator_rejects_export_field_with_unknown_binding() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    bound_revision = _with_first_export_field(
        revision,
        ExportFieldDefinition.model_validate(
            {
                **revision.export_layouts[0].records[0].fields[0].model_dump(mode="python"),
                "id": "modelo-130-export-bound-missing",
                "kind": "binding",
                "binding": "missing.export.binding",
                "casilla": None,
                "literal": None,
                "header_key": None,
                "draft_attribute": None,
                "computed_key": None,
                "data_type": "money",
                "required": False,
                "padding": "left_zero",
                "justification": "right",
            },
        ),
    )

    with pytest.raises(RegistryValidationError, match="unknown binding"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, bound_revision),
        )


def test_validator_rejects_literal_export_field_longer_than_declared_length() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    layout = revision.export_layouts[0]
    record = layout.records[0]
    field = next(item for item in record.fields if item.kind == "literal" and item.length is not None)
    assert field.length is not None
    oversized = field.model_copy(update={"literal": "X" * (field.length + 1)})
    fields = tuple(oversized if item.id == field.id else item for item in record.fields)
    records = tuple(
        record.model_copy(update={"fields": fields}) if item.id == record.id else item for item in layout.records
    )
    layouts = tuple(
        layout.model_copy(update={"records": records}) if item.id == layout.id else item
        for item in revision.export_layouts
    )
    mutated = revision.model_copy(update={"export_layouts": layouts})

    with pytest.raises(RegistryValidationError, match=r"literal length .* exceeds declared length"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_parameter_without_official_source_guidance() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    parameters = tuple(
        parameter.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
        if parameter.id == "irpf.direct_estimation_fractional_payment_rate"
        else parameter
        for parameter in revision.parameters
    )
    mutated = revision.model_copy(update={"parameters": parameters})

    with pytest.raises(RegistryValidationError, match="requires official_source_guidance source evidence"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_modelo_file_rejects_static_cross_reference_as_executable_parity(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    text = path.read_text(encoding="utf-8").replace(
        'evidence_tier = "layout_authority"\nsurface = "static_official_documentation"',
        'evidence_tier = "executable_parity_evidence"\nsurface = "static_official_documentation"',
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="static documentation is not executable parity evidence"):
        load_modelo_file(path)


def test_validator_rejects_cross_reference_source_tier_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    cross_reference = revision.live_cross_references[0].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated = revision.model_copy(update={"live_cross_references": (cross_reference,)})

    with pytest.raises(RegistryValidationError, match="requires official_source_guidance source evidence"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_modelo_file_rejects_runner_without_formula_workbook(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    text = path.read_text(encoding="utf-8").replace("runner_required = false", "runner_required = true", 1)
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="runner requires formula coverage"):
        load_modelo_file(path)


def test_validator_rejects_missing_legal_reference() -> None:
    modelo, catalogues = _committed_registry()
    missing_legal = catalogues.model_copy(update={"legal": {}})

    with pytest.raises(RegistryValidationError, match="unknown legal id"):
        RegistryValidator(missing_legal, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_extraction_profile_unknown_casilla() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(
        update={
            "target_casillas": (
                ExtractionTargetDefinition(
                    casilla_id="missing",
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
            ),
        },
    )
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match=r"extraction profile .* unknown casilla"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_extraction_profile_artefact_surface_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"accepted_artefact_kinds": ("justificante_pdf",)})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match="surface 'declaracion_pdf' requires"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_extraction_target_definition_roundtrip() -> None:
    """ExtractionTargetDefinition strict-frozen roundtrip with non-default fields."""
    target = ExtractionTargetDefinition(
        casilla_id="my-label",
        match_strategy="named_label",
        value_kind="text",
        label_pattern=r"Mi etiqueta especial",
    )
    raw = target.model_dump()
    restored = ExtractionTargetDefinition.model_validate(raw)
    assert restored == target
    assert restored.casilla_id == "my-label"
    assert restored.match_strategy == "named_label"
    assert restored.value_kind == "text"
    assert restored.label_pattern == r"Mi etiqueta especial"


def test_extraction_target_definition_anti_tautology() -> None:
    """Mutating the serialised payload surfaces inequality after reload."""
    target = ExtractionTargetDefinition(
        casilla_id="01",
        match_strategy="numeric_casilla",
        value_kind="amount",
    )
    raw = target.model_dump()
    raw["match_strategy"] = "named_label"
    raw["label_pattern"] = "Retenciones"
    mutated = ExtractionTargetDefinition.model_validate(raw)
    assert mutated != target


def test_extraction_target_named_label_requires_label_pattern() -> None:
    with pytest.raises(ValidationError, match="named_label extraction targets require label_pattern"):
        ExtractionTargetDefinition(
            casilla_id="decl.cnae",
            match_strategy="named_label",
            value_kind="text",
        )


def test_extraction_target_numeric_casilla_rejects_label_pattern() -> None:
    with pytest.raises(ValidationError, match="numeric_casilla extraction targets must not define label_pattern"):
        ExtractionTargetDefinition(
            casilla_id="01",
            match_strategy="numeric_casilla",
            value_kind="amount",
            label_pattern="Retenciones",
        )


def test_casilla_accepts_continuidad_id_roundtrip() -> None:
    casilla = CasillaDefinition.model_validate(
        {
            "id": "0700",
            "number": "0700",
            "label": "Base liquidable general",
            "section": ("base",),
            "data_type": "money",
            "continuidad_id": "renta.base-liquidacion.general",
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
        },
    )

    restored = CasillaDefinition.model_validate(casilla.model_dump())

    assert restored == casilla
    assert restored.continuidad_id == "renta.base-liquidacion.general"


def test_casilla_continuidad_id_uses_registry_id_shape() -> None:
    with pytest.raises(ValidationError, match="continuidad_id"):
        CasillaDefinition.model_validate(
            {
                "id": "0700",
                "number": "0700",
                "label": "Base liquidable general",
                "section": ("base",),
                "continuidad_id": "Renta Base",
                "legal_refs": ("ley-35-2006:art-48",),
                "source_refs": ("aeat-manual",),
            },
        )


def test_casilla_continuidad_evolution_rejects_same_revision_pair() -> None:
    with pytest.raises(ValidationError, match="must span two different revisions"):
        CasillaContinuidadEvolutionDefinition(
            id="renta-2024-self-evolution",
            continuidad_id="renta.base-liquidacion.general",
            from_revision="2024",
            to_revision="2024",
            evolution_kind="label_evolved",
            legal_refs=("ley-35-2006:art-48",),
            source_refs=("aeat-manual",),
        )


def test_modelo_revision_defaults_to_advisory_continuidad_validation() -> None:
    revision = ModeloRevision.model_validate(
        {
            "id": "2024",
            "valid_from": date(2024, 1, 1),
            "period_selector": {"years": (2024,), "periods": ("0A",)},
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
        },
    )

    assert revision.continuidad_validation == "advisory"
    assert revision.casilla_continuidad_evolutions == ()
