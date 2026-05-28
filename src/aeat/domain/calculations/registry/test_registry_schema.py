"""Tests for the registry-backed AEAT calculation schema."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.core.resources import bundled_path

from . import (
    ExtractionProfileDefinition,
    RegistryCatalogues,
    RegistryLoadError,
    RegistryValidationError,
    build_model_law_coverage_ledger,
    build_snapshot,
    load_modelo_file,
)
from ._loader import load_registry_tree
from ._schema import (
    ExportFieldDefinition,
    ExtractionTargetDefinition,
    FormulaExpression,
    KeyedBracketEntry,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    SupportRemovalDecisionDefinition,
    VerificationPredicateDefinition,
)
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_MODELO_130_DIR = _REGISTRY_ROOT / "modelos" / "130"


@cache
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


def test_formula_expression_accepts_dispatch_table_entries() -> None:
    expression = FormulaExpression.model_validate(
        {
            "dispatch_table_entries": [
                {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                {"key": "cataluna", "parameter": "renta-2025-escala-autonomica-cataluna-base-general"},
            ]
        }
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
                ]
            }
        )


def test_formula_expression_rejects_mixed_dispatch_table_shapes() -> None:
    with pytest.raises(ValidationError, match="dispatch_table or dispatch_table_entries"):
        FormulaExpression.model_validate(
            {
                "dispatch_table": {"madrid": "renta-2025-escala-autonomica-madrid-base-general"},
                "dispatch_table_entries": [
                    {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"}
                ],
            }
        )


def _as_communication_revision(revision: ModeloRevision) -> ModeloRevision:
    filing_link = next(link for link in revision.application_links if link.surface == "filing")
    communication_link = filing_link.model_copy(
        update={
            "id": f"{filing_link.id}-communication",
            "surface": "communication",
            "consumer": "aeat.application.modelo",
        }
    )
    application_links = tuple(
        communication_link if link.id == filing_link.id else link
        for link in revision.application_links
        if link.id == filing_link.id or link.surface != "filing"
    )
    constructs = tuple(
        construct.model_copy(
            update={
                "application_links": tuple(
                    communication_link.id if link_id == filing_link.id else link_id
                    for link_id in construct.application_links
                ),
                "filing_schedules": (),
            }
        )
        for construct in revision.constructs
    )
    return revision.model_copy(
        update={
            "application_links": application_links,
            "filing_schedules": (),
            "constructs": constructs,
        }
    )


def _copy_committed_modelo(path: Path) -> None:
    revision_dir = _MODELO_130_DIR / "revisions" / "2019-y-siguientes"
    fragments = [revision_dir / "revision.toml"]
    fragments.extend(sorted(item for item in revision_dir.rglob("*.toml") if item.name != "revision.toml"))
    text = _MODELO_130_DIR.joinpath("manifest.toml").read_text(encoding="utf-8")
    text += "".join(fragment.read_text(encoding="utf-8") for fragment in fragments)
    path.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def _modelo_130_snapshot():  # type: ignore[no-untyped-def]
    """Validate + build the committed Modelo 130 / 2024 3T snapshot once per module.

    Module scope is safe — both validation and snapshot construction
    are read-only against the bundled registry data. Every focused
    snapshot-attribute test below asserts against the same instance.
    """
    modelo, catalogues = _committed_registry()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="3T")


_SNAPSHOT_HEADER_EXPECTATIONS = (
    ("modelo.id", "130"),
    ("revision.id", "2019-y-siguientes"),
    ("filing_year", 2024),
    ("period", "3T"),
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


_EXPECTED_LIVE_CROSS_REFERENCES = frozenset(
    {"modelo-130-static-official", "modelo-130-filed-declarations-read"}
)


def test_committed_snapshot_lists_expected_live_cross_references(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert set(_modelo_130_snapshot.live_cross_references) == _EXPECTED_LIVE_CROSS_REFERENCES


def test_committed_snapshot_static_cross_reference_carries_layout_tier(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert (
        _modelo_130_snapshot.live_cross_references["modelo-130-static-official"].evidence_tier
        == "layout_authority"
    )


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
        }
    )

    with pytest.raises(
        RegistryValidationError,
        match="revision must declare at least one casilla",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, empty_revision)
        )


_EXPECTED_DEADLINE_WINDOWS = (
    "modelo-130-2026-1t",
    "modelo-130-2026-2t",
    "modelo-130-2026-3t",
    "modelo-130-2026-4t",
)


def test_committed_snapshot_lists_four_quarterly_deadline_windows(_modelo_130_snapshot) -> None:  # type: ignore[no-untyped-def]
    assert tuple(_modelo_130_snapshot.deadline_windows) == _EXPECTED_DEADLINE_WINDOWS


_REQUIRED_APPLICATION_LINKS = frozenset(
    {
        "modelo-130-calculation",
        "modelo-130-deadline",
        "modelo-130-export",
        "modelo-130-extractor",
        "modelo-130-filed-declarations-observation",
        "modelo-130-filing",
        "modelo-130-portal-cross-reference",
        "modelo-130-verification",
    }
)


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
        }
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
            "source": "invoice",
            "selector": {"claves": ("E",)},
            "aggregation": {"op": "sum"},
        }
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
        update={"bindings": tuple(mutated_binding if item.id == binding.id else item for item in revision.bindings)}
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
            "source": "invoice",
            "selector": {"fact": "operator_count", "claves": ("E",)},
            "aggregation": {"op": "sum"},
        }
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
            "source": "invoice",
            "selector": {"fact": "rectified_base_delta_sum", "claves": ("E",)},
            "aggregation": {"op": "sum"},
        }
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
            }
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
            }
        ),
    )

    with pytest.raises(RegistryValidationError, match="unknown binding"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, bound_revision)
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
        record.model_copy(update={"fields": fields}) if item.id == record.id else item
        for item in layout.records
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
            )
        }
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


def test_extraction_profile_target_casillas_uniqueness_rejects_duplicate_casilla_id() -> None:
    """target_casillas with duplicate casilla_id values raises ValidationError."""
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        ExtractionProfileDefinition(
            id="test.profile",
            surface="declaracion_pdf",
            artefact_kind="declaration_pdf",
            accepted_artefact_kinds=("declaration_pdf",),
            parser="aeat.adapters.inbound.declaracion.parse_declaracion",
            target_casillas=(
                ExtractionTargetDefinition(
                    casilla_id="01",
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
                ExtractionTargetDefinition(
                    casilla_id="01",
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
            ),
            confidence="strict",
            min_coverage=Decimal("1"),
            failure_semantics="fail_hard",
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-dr-130-2019-v12",),
        )


def test_validator_rejects_extraction_profile_parser_that_does_not_resolve() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"parser": "aeat.missing_registry_parser"})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match=r"does not resolve attribute 'missing_registry_parser'.*aeat"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_application_link_for_extraction_profile() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    links = tuple(link for link in revision.application_links if link.surface != "extractor")
    mutated = revision.model_copy(update={"application_links": links})

    with pytest.raises(RegistryValidationError, match="extraction profiles require an extractor application link"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_application_link_for_formulas() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    links = tuple(link for link in revision.application_links if link.surface != "calculation")
    mutated = revision.model_copy(update={"application_links": links})

    with pytest.raises(RegistryValidationError, match="formulas require a calculation application link"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_allows_modelo_145_communication_link_for_non_filing_casillas() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    communication = _as_communication_revision(revision)
    # A pure communication-only modelo does not file declarations and
    # therefore has no PDF-extraction surface; strip extraction_profiles
    # and their corpus-PDF requirements from the mutated revision.
    extractor_link_ids = frozenset(
        link.id for link in communication.application_links if link.surface == "extractor"
    )
    constructs_without_extractor = tuple(
        construct.model_copy(
            update={
                "extraction_profiles": (),
                "application_links": tuple(
                    link_id for link_id in construct.application_links if link_id not in extractor_link_ids
                ),
            }
        )
        for construct in communication.constructs
    )
    mutated = communication.model_copy(
        update={
            "constructs": constructs_without_extractor,
            "extraction_profiles": (),
            "application_links": tuple(
                link for link in communication.application_links if link.surface != "extractor"
            ),
        }
    )
    modelo_145 = modelo.model_copy(update={"id": "145"})

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo_145, mutated))


def test_validator_rejects_verification_predicate_with_unknown_operator() -> None:
    """P09.S63: predicate with an unknown DSL operator must fail at registry-load.

    The runtime DSL evaluator falls through to ``return True`` for any
    unrecognised expression — silent-pass is the documented behaviour
    so unknown DSL extensions don't block. That same behaviour means
    a typo like ``cap_lt_when_positive`` for ``cap_le_when_positive``
    silently passes the predicate gate and the cap rule is lost
    without diagnostic.

    The P09.S63 hardening rejects unknown operators at registry-load
    time. The known set is enumerated in
    ``_validate_surfaces._KNOWN_VERIFICATION_PREDICATE_OPERATORS``:
    ``all_nonzero``, ``any_nonzero``, ``cap_le_when_positive``.
    Typos are caught before any calculation runs.
    """

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    typo_predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-typo-predicate",
        legal_refs=("rd-439-2007:art-110",),
        expression='cap_lt_when_positive(["15", "14"])',  # typo: lt instead of le
        finding_kind="BLOCKING_RULE",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, typo_predicate)}
    )

    with pytest.raises(RegistryValidationError, match="unknown operator 'cap_lt_when_positive'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated)
        )


def test_validator_rejects_verification_predicate_with_malformed_expression() -> None:
    """P09.S63: predicate whose expression is not a parseable DSL call fails."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    malformed_predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-malformed-predicate",
        legal_refs=("rd-439-2007:art-110",),
        expression='just a string with no call shape',
        finding_kind="BLOCKING_RULE",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, malformed_predicate)}
    )

    with pytest.raises(RegistryValidationError, match="not a recognised DSL call"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated)
        )


def test_validator_accepts_known_verification_predicate_operators() -> None:
    """P09.S63: the cap_le_when_positive predicate declared by P08.S48 must pass.

    Pins that the committed M130 cap predicate
    (modelo-130-c15-cap-by-c14, expression
    cap_le_when_positive(["15", "14"])) validates cleanly. A
    future operator-set reduction that drops cap_le_when_positive
    from the known set would surface here, not at runtime.
    """

    modelo, catalogues = _committed_modelo("130")
    # No mutation — committed M130 carries the predicate from P08.S48.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_non_145_communication_link_for_casillas() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = _as_communication_revision(next(iter(modelo.revisions.values())))

    with pytest.raises(RegistryValidationError, match="communication application links are only valid for Modelo 145"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, revision))


def test_validator_rejects_communication_link_combined_with_filing() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    filing_link = next(link for link in revision.application_links if link.surface == "filing")
    communication_link = filing_link.model_copy(
        update={"id": f"{filing_link.id}-communication", "surface": "communication"}
    )
    mutated = revision.model_copy(update={"application_links": (*revision.application_links, communication_link)})

    with pytest.raises(
        RegistryValidationError,
        match="communication application links must not be combined with filing",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_modelo_145_without_communication_link() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    modelo_145 = modelo.model_copy(update={"id": "145"})

    with pytest.raises(RegistryValidationError, match="Modelo 145 requires a communication application link"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo_145, revision))


def test_validator_rejects_communication_link_with_deadline_surface() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = _as_communication_revision(next(iter(modelo.revisions.values())))
    workflow_link = next(link for link in revision.application_links if link.surface == "workflow")
    deadline_link = workflow_link.model_copy(update={"id": f"{workflow_link.id}-deadline", "surface": "deadline"})
    mutated = revision.model_copy(update={"application_links": (*revision.application_links, deadline_link)})

    with pytest.raises(RegistryValidationError, match="communication application links must not declare deadline"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_communication_link_with_portal_surface() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = _as_communication_revision(next(iter(modelo.revisions.values())))
    workflow_link = next(link for link in revision.application_links if link.surface == "workflow")
    portal_link = workflow_link.model_copy(update={"id": f"{workflow_link.id}-portal", "surface": "portal"})
    mutated = revision.model_copy(update={"application_links": (*revision.application_links, portal_link)})

    with pytest.raises(
        RegistryValidationError,
        match="communication application links must not declare live or portal",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_communication_link_with_filing_schedule() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    filing_link = next(link for link in revision.application_links if link.surface == "filing")
    communication_link = filing_link.model_copy(
        update={
            "id": f"{filing_link.id}-communication",
            "surface": "communication",
            "consumer": "aeat.application.modelo",
        }
    )
    application_links = tuple(
        communication_link if link.id == filing_link.id else link
        for link in revision.application_links
        if link.id == filing_link.id or link.surface != "filing"
    )
    constructs = tuple(
        construct.model_copy(
            update={
                "application_links": tuple(
                    communication_link.id if link_id == filing_link.id else link_id
                    for link_id in construct.application_links
                )
            }
        )
        for construct in revision.constructs
    )
    mutated = revision.model_copy(update={"application_links": application_links, "constructs": constructs})

    with pytest.raises(
        RegistryValidationError,
        match="communication application links must not declare filing schedules",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_submitted_file_profile_without_exported_casilla() -> None:
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
    profile = next(item for item in revision.extraction_profiles if item.surface == "export_record")
    target = profile.target_casillas[0].casilla_id
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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_reconciliation_total_unknown_casilla() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0].model_copy(
        update={"reconciliation_totals": {"ingresar": "missing"}}
    )
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(RegistryValidationError, match="reconciliation total 'ingresar' references unknown casilla"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_reconciliation_total_to_be_computed() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0].model_copy(update={"reconciliation_totals": {"ingresar": "01"}})
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(
        RegistryValidationError,
        match="reconciliation total 'ingresar' must be one of computed_casillas",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


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
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
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


# ---------------------------------------------------------------------------
# keyed_bracket_table parameter shape (W09.P41.S388)
#
# Sister shape to bracket_table for parameters that dispatch on a
# categorical enum key rather than a numeric interval. First consumer:
# M210 IRNR m210-tipo-gravamen-2025 (tipo_renta → rate).
# ---------------------------------------------------------------------------


def _keyed_bracket(key: str, value: str = "0.24") -> KeyedBracketEntry:
    return KeyedBracketEntry(
        key=key,
        value=Decimal(value),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def test_keyed_bracket_table_parses_with_distinct_keys() -> None:
    """A keyed_bracket_table with two distinct keys parses cleanly."""
    parameter = ParameterDefinition(
        id="test-keyed-rate-table",
        data_type="keyed_bracket_table",
        unit="percent",
        keyed_brackets=(
            _keyed_bracket("general", "0.24"),
            _keyed_bracket("ue_residente", "0.19"),
        ),
        legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
        source_refs=("aeat-modelo-210-procedure",),
    )

    assert parameter.data_type == "keyed_bracket_table"
    assert len(parameter.keyed_brackets) == 2
    assert parameter.keyed_brackets[0].key == "general"
    assert parameter.keyed_brackets[0].value == Decimal("0.24")
    assert parameter.keyed_brackets[1].key == "ue_residente"
    assert parameter.keyed_brackets[1].value == Decimal("0.19")


def test_keyed_bracket_table_rejects_duplicate_key_within_same_window() -> None:
    """A keyed_bracket_table with two rows sharing (key, valid_from) is rejected.

    Anti-tautology: the duplicate fixture deliberately reuses the
    SAME ``key`` AND the SAME ``valid_from`` across two rows with
    different values. If the validator silently dedup'd or kept the
    first row, the test would pass without surfacing the contract
    violation. The expected outcome is RegistryValidationError —
    the (key, valid_from) pair must be unique because the runtime
    lookup is exact-match and a duplicate would make the result
    non-deterministic.
    """
    # Pydantic wraps the inner RegistryValidationError raised from
    # @model_validator(mode="after") into its ValidationError because
    # RegistryValidationError does not extend ValueError. The substring
    # match still asserts the inner message text reaches the surface.
    with pytest.raises(ValidationError, match="duplicate"):
        ParameterDefinition(
            id="test-keyed-rate-table-duplicate",
            data_type="keyed_bracket_table",
            unit="percent",
            keyed_brackets=(
                _keyed_bracket("general", "0.24"),
                _keyed_bracket("general", "0.30"),
            ),
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
            source_refs=("aeat-modelo-210-procedure",),
        )


def test_keyed_bracket_table_rejects_mixed_brackets_and_keyed_brackets() -> None:
    """A keyed_bracket_table parameter cannot also carry numeric brackets.

    The two shapes are mutually exclusive by design — a parameter
    is either numeric-interval (``bracket_table``) or enum-keyed
    (``keyed_bracket_table``), never both. Mixing produces an
    ambiguous lookup contract; the validator rejects it at
    construction time.
    """
    from ._schema import BracketEntry as _BracketEntry

    numeric_bracket = _BracketEntry(
        lower_bound=Decimal("0"),
        upper_bound=Decimal("12450"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.19"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    with pytest.raises(ValidationError, match="cannot mix"):
        ParameterDefinition(
            id="test-keyed-rate-table-mixed",
            data_type="keyed_bracket_table",
            unit="percent",
            brackets=(numeric_bracket,),
            keyed_brackets=(_keyed_bracket("general", "0.24"),),
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
            source_refs=("aeat-modelo-210-procedure",),
        )
