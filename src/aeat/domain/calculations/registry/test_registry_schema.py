"""Tests for the registry-backed AEAT calculation schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import (
    RegistryCatalogues,
    RegistryLoadError,
    RegistryValidationError,
    build_model_law_coverage_ledger,
    build_snapshot,
    load_modelo_file,
)
from ._loader import load_registry_tree
from ._schema import ExportFieldDefinition, ModeloDefinition, ModeloRevision, SupportRemovalDecisionDefinition
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_MODELO_130_FILE = _REGISTRY_ROOT / "modelos" / "130.toml"


def _committed_modelo(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(modelo for modelo in modelos if modelo.id == modelo_id), catalogues


def _committed_registry() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("130")


def _revision(modelo: ModeloDefinition) -> ModeloRevision:
    return modelo.revisions["2019-y-siguientes"]


def _with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def _with_first_export_field(revision: ModeloRevision, field: ExportFieldDefinition) -> ModeloRevision:
    layout = revision.export_layouts[0]
    record = layout.records[0]
    updated_record = record.model_copy(update={"fields": (field, *record.fields[1:])})
    updated_layout = layout.model_copy(update={"records": (updated_record, *layout.records[1:])})
    return revision.model_copy(update={"export_layouts": (updated_layout, *revision.export_layouts[1:])})


def _copy_committed_modelo(path: Path) -> None:
    path.write_text(_MODELO_130_FILE.read_text(encoding="utf-8"), encoding="utf-8")


def test_modelo_file_loads_and_snapshot_selects_committed_revision() -> None:
    modelo, catalogues = _committed_registry()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2024, period="3T")

    assert snapshot.modelo.id == "130"
    assert snapshot.revision.id == "2019-y-siguientes"
    assert snapshot.filing_year == 2024
    assert snapshot.period == "3T"
    assert "rd-439-2007:art-110" in snapshot.legal
    assert "aeat-dr-130-2019-v12" in snapshot.sources
    assert snapshot.legal["rd-439-2007:art-110"].evidence_tier == "legal_authority"
    assert snapshot.sources["aeat-dr-130-2019-v12"].evidence_tier == "layout_authority"
    assert tuple(snapshot.extraction_profiles) == ("modelo-130-declaracion-pdf",)
    assert set(snapshot.live_cross_references) == {
        "modelo-130-static-official",
        "modelo-130-filed-declarations-read",
    }
    assert snapshot.live_cross_references["modelo-130-static-official"].evidence_tier == "layout_authority"
    filed_read = snapshot.live_cross_references["modelo-130-filed-declarations-read"]
    assert filed_read.surface == "authenticated_read_surface"
    assert set(filed_read.allowed_methods).issubset({"GET", "HEAD", "OPTIONS"})
    assert filed_read.requires_authentication is True
    assert filed_read.requires_aeat_authorization is True
    assert tuple(snapshot.workbook_parity_refs) == ("modelo-130-dr-xls",)
    assert tuple(snapshot.verification_expectations) == ("modelo-130-calculation-verification",)
    assert snapshot.support_removal_decisions == {}
    assert tuple(snapshot.deadline_windows) == (
        "modelo-130-2026-1t",
        "modelo-130-2026-2t",
        "modelo-130-2026-3t",
        "modelo-130-2026-4t",
    )
    required_application_links = {
        "modelo-130-calculation",
        "modelo-130-deadline",
        "modelo-130-export",
        "modelo-130-extractor",
        "modelo-130-filed-declarations-observation",
        "modelo-130-filing",
        "modelo-130-portal-cross-reference",
        "modelo-130-verification",
    }
    assert required_application_links <= set(snapshot.application_links)


def test_model_law_coverage_ledger_does_not_count_layout_source_as_guidance() -> None:
    modelo, catalogues = _committed_registry()
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2024, period="3T")
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
        }
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
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2024, period="3T")
    source_id, source = next(iter(snapshot.sources.items()))
    workbook_id, workbook = next(iter(snapshot.workbook_parity_refs.items()))
    cross_reference_id, cross_reference = next(iter(snapshot.live_cross_references.items()))
    parity_source = source.model_copy(update={"evidence_tier": "executable_parity_evidence"})
    parity_workbook = workbook.model_copy(
        update={
            "formula_coverage": "formula_form",
            "runner_required": True,
            "output_cells": {"result": "Modelo!A1"},
        }
    )
    guidance_cross_reference = cross_reference.model_copy(update={"evidence_tier": "official_source_guidance"})
    parity_snapshot = snapshot.model_copy(
        update={
            "sources": {source_id: parity_source},
            "workbook_parity_refs": {workbook_id: parity_workbook},
            "live_cross_references": {cross_reference_id: guidance_cross_reference},
        }
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
    text = path.read_text(encoding="utf-8").replace(
        'legal_refs = ["rd-439-2007:art-110"]',
        "legal_refs = []",
        1,
    )
    path.write_text(text, encoding="utf-8")

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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_formula_target_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = revision.formulas[0]
    mismatched_formula = formula.model_copy(update={"target": "01"})
    mutated = revision.model_copy(update={"formulas": (mismatched_formula, *revision.formulas[1:])})

    with pytest.raises(RegistryValidationError, match="targeting '01'"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_workbook_parity_coverage() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo).model_copy(update={"workbook_parity_refs": ()})

    with pytest.raises(RegistryValidationError, match="must declare official workbook parity coverage"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, revision))


def test_modelo_file_rejects_unknown_support_removal_decision(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    path.write_text(
        path.read_text(encoding="utf-8")
        + """

[[revisions."2019-y-siguientes".support_removal_decisions]]
id = "modelo-130-invalid-removal-decision"
subject_type = "filing_path"
subject_id = "aeat.entrypoints.cli.filing"
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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
        }
    )
    mutated = revision.model_copy(update={"workbook_parity_refs": (workbook,)})

    with pytest.raises(RegistryValidationError, match="requires executable parity evidence source"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_binding_without_typed_selector() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "invoice",
            "selector": {"claves": ("E",)},
            "aggregation": {"op": "sum"},
        }
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="malformed invoice selector"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_profile_binding_selector_missing_from_user_profile_schema() -> None:
    modelo, catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    binding = next(item for item in revision.bindings if item.source == "profile")
    mutated_binding = binding.model_copy(update={"selector": {**binding.selector, "profile_key": "unknown.profile"}})
    mutated = revision.model_copy(
        update={"bindings": tuple(mutated_binding if item.id == binding.id else item for item in revision.bindings)}
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"user-profile schema .* selector 'unknown\.profile'",
    ):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_binding_aggregation_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "invoice",
            "selector": {"fact": "operator_count", "claves": ("E",)},
            "aggregation": {"op": "sum"},
        }
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="requires aggregation op 'count_distinct'"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_rectification_delta_without_rectification_scope() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "invoice",
            "selector": {"fact": "rectified_base_delta_sum", "claves": ("E",)},
            "aggregation": {"op": "sum"},
        }
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="requires rectification_scope 'only_rectifications'"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_invoice_period_rows_without_rectification_scope() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0].model_copy(
        update={
            "source": "invoice",
            "selector": {
                "fact": "row_field",
                "row_field": "base_imponible",
                "grouping": "operator_clave_period",
                "claves": ("E",),
            },
            "aggregation": {"op": "rows"},
        }
    )
    bindings = tuple(item if item.id != binding.id else binding for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})

    with pytest.raises(RegistryValidationError, match="grouping 'operator_clave_period' requires"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
            }
        ),
    )

    new_field = bound_revision.export_layouts[0].records[0].fields[0]
    assert new_field.kind == "binding"
    assert new_field.binding == revision.bindings[0].id
    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, bound_revision))


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
            }
        ),
    )

    with pytest.raises(RegistryValidationError, match="unknown binding"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, bound_revision))


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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(missing_legal, source_root=PROJECT_ROOT).validate_modelo(modelo)


def test_validator_rejects_extraction_profile_unknown_casilla() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"target_casillas": ("missing",)})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match=r"extraction profile .* unknown casilla"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_extraction_profile_artefact_surface_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"accepted_artefact_kinds": ("justificante_pdf",)})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match="surface 'declaracion_pdf' requires"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_extraction_profile_parser_that_does_not_resolve() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"parser": "aeat.missing_registry_parser"})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match="does not resolve attribute"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_application_link_for_extraction_profile() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    links = tuple(link for link in revision.application_links if link.surface != "extractor")
    mutated = revision.model_copy(update={"application_links": links})

    with pytest.raises(RegistryValidationError, match="extraction profiles require an extractor application link"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_application_link_for_formulas() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    links = tuple(link for link in revision.application_links if link.surface != "calculation")
    mutated = revision.model_copy(update={"application_links": links})

    with pytest.raises(RegistryValidationError, match="formulas require a calculation application link"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_casilla_export_ref_without_export_field() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    target = next(casilla for casilla in revision.casillas if casilla.export_refs)
    casillas = tuple(
        casilla.model_copy(update={"export_refs": (*casilla.export_refs, "missing-export-field")})
        if casilla.id == target.id
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": casillas})

    with pytest.raises(RegistryValidationError, match="references unknown export field"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_export_field_not_declared_by_casilla() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    exported = next(
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla is not None
    )
    casillas = tuple(
        casilla.model_copy(update={"export_refs": tuple(ref for ref in casilla.export_refs if ref != exported.id)})
        if casilla.id == exported.casilla
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": casillas})

    with pytest.raises(RegistryValidationError, match="is not declared by casilla"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_submitted_file_profile_without_exported_casilla() -> None:
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
    profile = next(item for item in revision.extraction_profiles if item.surface == "export_record")
    target = profile.target_casillas[0]
    removed_export_fields = {
        field.id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla == target
    }
    export_layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={"fields": tuple(field for field in record.fields if field.casilla != target)}
                    )
                    for record in layout.records
                )
            }
        )
        for layout in revision.export_layouts
    )
    casillas = tuple(
        casilla.model_copy(
            update={"export_refs": tuple(ref for ref in casilla.export_refs if ref not in removed_export_fields)}
        )
        if casilla.id == target
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": casillas, "export_layouts": export_layouts})

    with pytest.raises(RegistryValidationError, match="targets casillas without export fields"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_reconciliation_total_unknown_casilla() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0].model_copy(
        update={"reconciliation_totals": {"ingresar": "missing"}}
    )
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(RegistryValidationError, match="reconciliation total 'ingresar' references unknown casilla"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_reconciliation_total_to_be_computed() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0].model_copy(update={"reconciliation_totals": {"ingresar": "01"}})
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(
        RegistryValidationError,
        match="reconciliation total 'ingresar' must be one of computed_casillas",
    ):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_dispatch_table_referencing_unknown_parameter() -> None:
    """The lookup_bracket_by_ccaa dispatch_table leaf must resolve every value
    to a declared parameter; otherwise the registry would only fault at runtime."""
    modelo, catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    formula = next(item for item in revision.formulas if item.target == "0529")
    dispatch_leaf = formula.expression.args[2]
    assert dispatch_leaf.dispatch_table is not None, "fixture must expose a dispatch_table leaf"

    mutated_dispatch = {**dispatch_leaf.dispatch_table, "madrid": "renta-2025-not-a-declared-parameter"}
    mutated_leaf = dispatch_leaf.model_copy(update={"dispatch_table": mutated_dispatch})
    mutated_args = (formula.expression.args[0], formula.expression.args[1], mutated_leaf)
    mutated_expression = formula.expression.model_copy(update={"args": mutated_args})
    mutated_formula = formula.model_copy(update={"expression": mutated_expression})
    mutated_formulas = tuple(mutated_formula if item.id == formula.id else item for item in revision.formulas)
    mutated_revision = revision.model_copy(update={"formulas": mutated_formulas})

    with pytest.raises(
        RegistryValidationError,
        match=r"dispatch_table\['madrid'\] references unknown parameter "
        r"'renta-2025-not-a-declared-parameter'",
    ):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(
            _with_revision(modelo, mutated_revision)
        )


def test_deadline_window_any_mode_requires_conditions() -> None:
    modelo, _catalogues = _committed_registry()
    revision = _revision(modelo)
    window = revision.deadline_windows[0]
    payload = window.model_dump()
    payload.update(
        {
            "applicability_condition_mode": "any",
            "applicability_conditions": (),
        }
    )

    with pytest.raises(ValueError, match="any-mode requires applicability conditions"):
        type(window).model_validate(payload)
