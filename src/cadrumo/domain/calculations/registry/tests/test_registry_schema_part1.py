"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.domain.calculations.registry.coverage import build_model_law_coverage_ledger
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.loader import load_modelo_file
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.schema_extraction import BboxAnchorSpec, ExtractionTargetDefinition
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
)
from cadrumo.domain.calculations.registry.snapshot import build_snapshot
from cadrumo.domain.calculations.registry.tests._registry_schema_support import (
    _EXPECTED_LIVE_CROSS_REFERENCES,
    _NUMERIC_CASILLA_01,
    _REQUIRED_APPLICATION_LINKS,
    _SNAPSHOT_HEADER_EXPECTATIONS,
    Path,
    ValidationError,
    _committed_modelo,
    _committed_registry,
    _copy_committed_modelo,
    _revision,
    _with_first_export_field,
    _with_revision,
    bundled_path,
    date,
    re,
)
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core import CasillaId, validated_casilla_id
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.identity import SPANISH_TAX_ID_WIDTH, IdentityError, validate_spanish_tax_id
from ...export_field_kind import CasillaFieldKind
from .._validate_export_field_widths import DRAFT_ATTRIBUTE_CANONICAL_WIDTHS, validate_draft_field_slot_width
from ..authority import ValidatedRegistryAuthority
from ..binding_selector_utils import selector_as_dict
from ..schema import DataBindingDefinition
from ..schema_exports import FilingEnvelopePrefixRole

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_MISSING_CASILLA: CasillaId = validated_casilla_id("missing", surface="_MISSING_CASILLA")
_NAMED_LABEL_CASILLA: CasillaId = validated_casilla_id("my-label", surface="_NAMED_LABEL_CASILLA")
_DECL_CNAE_CASILLA: CasillaId = validated_casilla_id("decl.cnae", surface="_DECL_CNAE_CASILLA")
_EXPECTED_COMMITTED_M130_DEADLINE_WINDOWS = (
    "modelo-130-2024-1t",
    "modelo-130-2024-2t",
    "modelo-130-2024-3t",
    "modelo-130-2024-4t",
    "modelo-130-2025-1t",
    "modelo-130-2025-2t",
    "modelo-130-2025-3t",
    "modelo-130-2025-4t",
    "modelo-130-2026-1t",
    "modelo-130-2026-2t",
    "modelo-130-2026-3t",
    "modelo-130-2026-4t",
    "modelo-130-2022-1t",
    "modelo-130-2022-2t",
    "modelo-130-2022-3t",
    "modelo-130-2022-4t",
    "modelo-130-2023-1t",
    "modelo-130-2023-2t",
    "modelo-130-2023-3t",
    "modelo-130-2023-4t",
)


def _validate_modelo(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> None:
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def _validate_revision(modelo: ModeloDefinition, catalogues: RegistryCatalogues, revision: ModeloRevision) -> None:
    _validate_modelo(_with_revision(modelo, revision), catalogues)


def _with_binding(revision: ModeloRevision, binding: DataBindingDefinition) -> ModeloRevision:
    return revision.model_copy(
        update={"bindings": tuple(binding if item.id == binding.id else item for item in revision.bindings)},
    )


@pytest.fixture
def modelo_130_snapshot(registry_snapshot: Callable[[str, int, str], RegistrySnapshot]) -> RegistrySnapshot:
    return registry_snapshot("130", 2024, "3T")


def test_formula_expression_dispatch_table_entry_contract() -> None:
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

    with pytest.raises(ValidationError, match="duplicate key 'madrid'"):
        FormulaExpression.model_validate(
            {
                "dispatch_table_entries": [
                    {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                    {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                ],
            },
        )

    with pytest.raises(ValidationError, match="dispatch_table or dispatch_table_entries"):
        FormulaExpression.model_validate(
            {
                "dispatch_table": {"madrid": "renta-2025-escala-autonomica-madrid-base-general"},
                "dispatch_table_entries": [
                    {"key": "madrid", "parameter": "renta-2025-escala-autonomica-madrid-base-general"},
                ],
            },
        )


def test_committed_snapshot_exposes_expected_metadata(
    modelo_130_snapshot: RegistrySnapshot,
) -> None:
    """Committed M130 snapshot metadata matches the registry authority contracts."""

    for attr_path, expected in _SNAPSHOT_HEADER_EXPECTATIONS:
        actual: object = modelo_130_snapshot
        for segment in attr_path.split("."):
            actual = getattr(actual, segment)
        assert actual == expected, attr_path

    assert "rd-439-2007:art-110" in modelo_130_snapshot.legal
    assert modelo_130_snapshot.legal["rd-439-2007:art-110"].evidence_tier == "legal_authority"
    assert "aeat-dr-130-2019-v12" in modelo_130_snapshot.sources
    assert modelo_130_snapshot.sources["aeat-dr-130-2019-v12"].evidence_tier == "layout_authority"
    assert tuple(modelo_130_snapshot.extraction_profiles) == ("modelo-130-declaracion-pdf",)
    assert set(modelo_130_snapshot.live_cross_references) == _EXPECTED_LIVE_CROSS_REFERENCES
    assert modelo_130_snapshot.live_cross_references["modelo-130-static-official"].evidence_tier == "layout_authority"
    filed_read = modelo_130_snapshot.live_cross_references["modelo-130-filed-declarations-read"]
    assert filed_read.surface == "authenticated_read_surface"
    assert set(filed_read.allowed_methods).issubset({"GET", "HEAD", "OPTIONS"})
    assert filed_read.requires_authentication is True
    assert filed_read.requires_aeat_authorization is True
    assert tuple(modelo_130_snapshot.workbook_parity_refs) == ("modelo-130-dr-xls",)
    # The coverage-gated calculation contract plus the exhaustive
    # reconcile-when-present contract (situational computed casillas value-checked
    # when present, excluded from the coverage denominator).
    assert tuple(modelo_130_snapshot.verification_expectations) == (
        "modelo-130-calculation-verification",
        "modelo-130-2019-y-siguientes-reconcile-when-present",
    )
    assert tuple(modelo_130_snapshot.deadline_windows) == _EXPECTED_COMMITTED_M130_DEADLINE_WINDOWS
    assert set(modelo_130_snapshot.application_links) >= _REQUIRED_APPLICATION_LINKS


def test_committed_registry_contains_no_zero_casilla_revisions(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    zero_casilla_revisions = [
        (modelo.id, revision.id)
        for modelo in registry_authority.modelos
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
        _validate_revision(modelo, catalogues, empty_revision)


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
    workbook_source = snapshot.sources[workbook.workbook_source]
    cross_reference_id, cross_reference = next(iter(snapshot.live_cross_references.items()))
    parity_source = source.model_copy(update={"evidence_tier": "executable_parity_evidence"})
    parity_workbook_source = workbook_source.model_copy(update={"evidence_tier": "executable_parity_evidence"})
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
            "sources": {
                source_id: parity_source,
                workbook.workbook_source: parity_workbook_source,
            },
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


def test_modelo_file_rejects_casilla_binding_id_collision(tmp_path: Path) -> None:
    path = tmp_path / "999.toml"
    path.write_text(
        """
[modelo]
id = "999"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "01"
number = "01"
section = ["test"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".bindings]]
id = "01"
source = "manual_input"
selector = { record = "DPA", field = "test", offset = 1, length = 1, data_type = "integer" }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="duplicate registry id '01' shared by casilla, binding"):
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
        _validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_formula_id_matching_casilla_id() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = revision.formulas[0]
    renamed_formula = formula.model_copy(update={"id": formula.target_casilla_id})
    casillas = tuple(
        casilla.model_copy(update={"formula": renamed_formula.id})
        if casilla.id == formula.target_casilla_id
        else casilla
        for casilla in revision.casillas
    )
    formulas = (renamed_formula, *revision.formulas[1:])
    mutated = revision.model_copy(update={"casillas": casillas, "formulas": formulas})

    with pytest.raises(RegistryValidationError, match=f"duplicate registry id '{formula.target_casilla_id}'"):
        _validate_revision(modelo, catalogues, mutated)


def test_validator_reports_casilla_binding_id_collision_owners() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    collision_id = revision.casillas[0].id
    collision_binding = revision.bindings[0].model_copy(update={"id": collision_id})
    mutated = revision.model_copy(update={"bindings": (*revision.bindings, collision_binding)})

    with pytest.raises(
        RegistryValidationError,
        match=rf"duplicate registry id '{re.escape(collision_id)}' shared by casilla, binding",
    ):
        _validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_formula_target_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = revision.formulas[0]
    mismatched_formula = formula.model_copy(update={"target_casilla_id": _NUMERIC_CASILLA_01})
    mutated = revision.model_copy(update={"formulas": (mismatched_formula, *revision.formulas[1:])})

    with pytest.raises(RegistryValidationError, match=f"targeting '{_NUMERIC_CASILLA_01}'"):
        _validate_revision(modelo, catalogues, mutated)


def test_validator_requires_workbook_parity_coverage() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo).model_copy(update={"workbook_parity_refs": ()})

    with pytest.raises(RegistryValidationError, match="must declare official workbook parity coverage"):
        _validate_revision(modelo, catalogues, revision)


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
        _validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_layout_workbook_without_layout_authority_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    workbook = revision.workbook_parity_refs[0]
    source = catalogues.sources[workbook.workbook_source]
    mutated_catalogues = catalogues.model_copy(
        update={
            "sources": {
                **catalogues.sources,
                workbook.workbook_source: source.model_copy(update={"evidence_tier": "official_source_guidance"}),
            },
        },
    )

    with pytest.raises(RegistryValidationError, match="requires layout_authority source evidence"):
        _validate_revision(modelo, mutated_catalogues, revision)


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
        _validate_revision(modelo, catalogues, mutated)


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
        _validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_binding_citation_missing_from_official_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    binding = revision.bindings[0]
    bad_citations = tuple(
        citation.model_copy(update={"required_text": ("official source does not contain this binding anchor",)})
        for citation in binding.source_citations
    )
    mutated = _with_binding(revision, binding.model_copy(update={"source_citations": bad_citations}))

    with pytest.raises(RegistryValidationError, match=r"source citation .* missing text"):
        _validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_invalid_invoice_binding_shapes() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    cases = (
        (
            "missing-fact",
            {
                "source": "collectible_invoice",
                "selector": {"claves": ("E",)},
                "aggregation": BindingAggregation(op=BindingAggregationOp.SUM),
            },
            r"selector violates _InvoiceSelector",
        ),
        (
            "aggregation-mismatch",
            {
                "source": "collectible_invoice",
                "selector": {"fact": "operator_count", "claves": ("E",)},
                "aggregation": BindingAggregation(op=BindingAggregationOp.SUM),
            },
            "requires aggregation op 'count_distinct'",
        ),
        (
            "rectification-delta-without-scope",
            {
                "source": "collectible_invoice",
                "selector": {"fact": "rectified_base_delta_sum", "claves": ("E",)},
                "aggregation": BindingAggregation(op=BindingAggregationOp.SUM),
            },
            "requires rectification_scope 'only_rectifications'",
        ),
        (
            "period-rows-without-scope",
            {
                "source": "collectible_invoice",
                "selector": {
                    "fact": "row_field",
                    "row_field": "base_imponible",
                    "grouping": "operator_clave_period",
                    "claves": ("E",),
                },
                "aggregation": BindingAggregation(op=BindingAggregationOp.ROWS),
            },
            "grouping 'operator_clave_period' requires",
        ),
    )

    for case_id, update, match in cases:
        mutated = _with_binding(revision, revision.bindings[0].model_copy(update=update))
        with pytest.raises(RegistryValidationError, match=match) as excinfo:
            _validate_revision(modelo, catalogues, mutated)
        assert excinfo.type is RegistryValidationError, case_id


def test_validator_rejects_profile_binding_selector_missing_from_user_profile_schema() -> None:
    modelo, catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    binding = next(item for item in revision.bindings if item.source == "profile")
    mutated_binding = binding.model_copy(
        update={"selector": {**selector_as_dict(binding), "profile_key": "unknown.profile"}},
    )
    mutated = _with_binding(revision, mutated_binding)

    with pytest.raises(
        RegistryValidationError,
        match=r"user-profile schema .* selector 'unknown\.profile'",
    ):
        _validate_revision(modelo, catalogues, mutated)


def test_export_fields_can_reference_structured_bindings() -> None:
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
    bound_revision = _with_first_export_field(
        revision,
        ExportFieldDefinition.model_validate(
            {
                **revision.export_layouts[0].records[0].fields[0].model_dump(mode="python"),
                "id": "modelo-130-export-bound-net-income",
                "kind": "binding",
                "binding": revision.bindings[0].id,
                "casilla_id": None,
                "literal": None,
                "producer_key": None,
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
    assert new_field.kind is CasillaFieldKind.BINDING
    assert new_field.binding == revision.bindings[0].id
    _validate_revision(modelo, catalogues, bound_revision)


def test_validator_rejects_export_field_with_unknown_binding() -> None:
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
    bound_revision = _with_first_export_field(
        revision,
        ExportFieldDefinition.model_validate(
            {
                **revision.export_layouts[0].records[0].fields[0].model_dump(mode="python"),
                "id": "modelo-130-export-bound-missing",
                "kind": "binding",
                "binding": "missing.export.binding",
                "casilla_id": None,
                "literal": None,
                "producer_key": None,
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
        _validate_revision(modelo, catalogues, bound_revision)


def test_validator_rejects_literal_export_field_longer_than_declared_length() -> None:
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
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
        _validate_revision(modelo, catalogues, mutated)


#: The Modelo 200 page 001B slot the diseño reserves for the mercantile group's
#: ultimate parent company's foreign tax identification number.
_M200_PARENT_TIN_FIELD_ID = "modelo-200-page-001b-draft-profile_tax_id-pos-141"


def _export_field_by_id(
    revision: ModeloRevision,
    field_id: str,
) -> tuple[ExportFieldDefinition, str, str]:
    """Return one export field with its record and layout ids, or fail loudly."""
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                if field.id == field_id:
                    return field, record.id, layout.id
    raise AssertionError(f"the committed revision declares no export field {field_id!r}")


def _first_profile_tax_id_draft_field(
    revision: ModeloRevision,
) -> tuple[ExportFieldDefinition, str, str]:
    """Return the revision's first declarant-NIF draft field with its record and layout ids.

    Located by PROPERTY -- draft kind plus the ``profile_tax_id`` attribute -- not
    by a pinned field id, so renaming or renumbering the committed declaration
    cannot make the callers below pass without exercising anything.
    """
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                if field.kind == CasillaFieldKind.DRAFT and field.draft_attribute == "profile_tax_id":
                    return field, record.id, layout.id
    raise AssertionError("the committed revision declares no profile_tax_id draft export field to anchor on")


def _with_replaced_export_field(
    revision: ModeloRevision,
    *,
    layout_id: str,
    record_id: str,
    field: ExportFieldDefinition,
) -> ModeloRevision:
    def _replace_record(record):
        fields = tuple(field if item.id == field.id else item for item in record.fields)
        return record.model_copy(update={"fields": fields})

    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    _replace_record(record) if record.id == record_id else record for record in layout.records
                ),
            },
        )
        if layout.id == layout_id
        else layout
        for layout in revision.export_layouts
    )
    return revision.model_copy(update={"export_layouts": layouts})


def test_spanish_tax_id_width_is_the_width_the_identifier_validator_enforces() -> None:
    """The declared identifier width must still be the one the validator refuses around.

    The export slot-width check asserts a ``profile_tax_id`` slot is exactly
    ``SPANISH_TAX_ID_WIDTH`` characters. That assertion means nothing unless the
    constant still describes the identifier contract, so pin it against the
    validator's actual behaviour rather than against a second copy of the number:
    a canonical identifier of that width validates, and padding or truncating it
    by one character is refused.
    """
    canonical = validate_spanish_tax_id("B12345674")

    assert len(canonical) == SPANISH_TAX_ID_WIDTH
    with pytest.raises(IdentityError, match=rf"exactly {SPANISH_TAX_ID_WIDTH} characters"):
        validate_spanish_tax_id(f"{canonical}0")
    with pytest.raises(IdentityError, match=rf"exactly {SPANISH_TAX_ID_WIDTH} characters"):
        validate_spanish_tax_id(canonical[:-1])


def test_draft_attribute_width_ruling_covers_every_declarable_attribute() -> None:
    """Every declarable draft attribute must carry a width ruling, gated or abstained.

    Keys the gate on the property rather than on today's declarations: a new
    ``draft_attribute`` added to the field schema without a ruling makes the width
    mapping non-total, and registry validation then refuses any field binding it.
    Asserting the mapping is total here names that obligation at the schema, so the
    refusal is a design prompt rather than a puzzling build failure.
    """
    declarable = set(ExportDraftAttribute)

    assert declarable
    assert set(DRAFT_ATTRIBUTE_CANONICAL_WIDTHS) == declarable
    assert "profile_tax_id" not in declarable


def test_validator_rejects_declarant_nif_draft_field_bound_to_a_wider_slot() -> None:
    """Deleted profile draft authority cannot be restored at any slot width."""
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
    field = (
        revision.export_layouts[0]
        .records[0]
        .fields[0]
        .model_copy(
            update={"kind": CasillaFieldKind.DRAFT, "draft_attribute": "profile_tax_id", "literal": None, "length": 15},
        )
    )
    mutated = _with_first_export_field(revision, field)

    with pytest.raises(RegistryValidationError, match="profile_tax_id"):
        _validate_revision(modelo, catalogues, mutated)


def test_validator_accepts_declarant_nif_draft_field_at_the_identifier_width() -> None:
    """Deleted profile draft authority is refused even at the identifier width."""
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
    field = (
        revision.export_layouts[0]
        .records[0]
        .fields[0]
        .model_copy(
            update={
                "kind": CasillaFieldKind.DRAFT,
                "draft_attribute": "profile_tax_id",
                "literal": None,
                "length": SPANISH_TAX_ID_WIDTH,
            },
        )
    )
    mutated = _with_first_export_field(revision, field)

    with pytest.raises(RegistryValidationError, match="profile_tax_id"):
        _validate_revision(modelo, catalogues, mutated)


def _committed_export_field(revision: ModeloRevision) -> ExportFieldDefinition:
    """Return one real field from ``revision``'s committed export layout.

    The width proofs below mutate a field that actually shipped rather than
    building one, so the legal and source references, data type and padding are
    the committed revision's own and only the width under test differs. A
    constructed field can satisfy a detector that the real declaration's shape
    would slip past.
    """
    return next(field for layout in revision.export_layouts for record in layout.records for field in record.fields)


def test_validator_rejects_the_modelo_200_envelope_open_tag_collapsed_onto_one_draft_field() -> None:
    """Collapsing M200's envelope-open composite back onto the year field must be refused.

    The real-site proof for the ``filing_year`` width ruling, and the standing
    regression against re-authoring the defect it replaced. Modelo 200's page-000
    record once declared the whole 17-character envelope-open constant as a single
    ``filing_year`` draft field: the year rendered into the first four bytes and the
    remaining thirteen padded to blanks, so every export omitted the ``<T``, the
    modelo code, the discriminante, the period token and the ``0000>`` marker
    AEAT's ``DP200000`` sheet requires there.

    The defect site is now gone by CONSTRUCTION rather than by a validator
    refusing it: the seventeen bytes are declared once as a typed
    :attr:`FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG`, and
    :class:`FilingEnvelopeDefinition` refuses a declaration carrying both that
    spelling and the six-role one. So there is no ``filing_year`` draft field on
    a Modelo 200 record for a collapse to be re-authored onto.

    Asserting the emptiness this test used to assert would now be false anyway --
    the campaign authored Modelo 200's generated export tree, so the revision
    declares a layout again. The proof therefore has two halves: the repaired
    state is asserted on the real committed revision, and the width detector is
    driven over a constructed field, because a detector proven only where the
    defect can no longer occur proves nothing.
    """
    modelo, _catalogues = _committed_modelo("200")
    revision = modelo.revisions["2024-y-siguientes"]

    composed = tuple(
        prefix
        for layout in revision.export_layouts
        if layout.filing_envelope is not None
        for prefix in layout.filing_envelope.prefix_fields
        if prefix.role is FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG
    )
    assert len(composed) == 1, "Modelo 200 spells its envelope-open tag as one composed role"
    assert composed[0].length == 17, "the composed tag carries the whole AEAT identifier's width"

    collapsed_onto_a_record = tuple(
        field.id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.DRAFT
        and field.draft_attribute is ExportDraftAttribute.FILING_YEAR
        and field.length != DRAFT_ATTRIBUTE_CANONICAL_WIDTHS[ExportDraftAttribute.FILING_YEAR]
    )
    assert collapsed_onto_a_record == (), (
        f"a record field binds the ejercicio to a slot that is not the year's own width: {collapsed_onto_a_record}"
    )

    collapsed = _committed_export_field(revision).model_copy(
        update={
            "kind": CasillaFieldKind.DRAFT,
            "draft_attribute": ExportDraftAttribute.FILING_YEAR,
            "casilla_id": None,
            "literal": None,
            "length": 17,
        },
    )
    failures = validate_draft_field_slot_width(prefix="modelo 200 revision 2024-y-siguientes", field=collapsed)
    assert any("to a slot of length 17" in failure for failure in failures), failures


def test_validator_rejects_the_grupo_mercantil_parent_tin_slot_rebound_to_the_declarant() -> None:
    """Re-binding M200's foreign-parent-TIN slot to the declarant must be refused.

    The real-site proof for the width check, and the standing regression against
    re-authoring the misbinding. The checks above widen a correct declaration, which
    shows the validator works on input the test itself shaped; this one restores the
    defect exactly as it shipped -- the committed Modelo 200 field, at its
    AEAT-correct 15-byte width, re-bound to the declarant's own NIF -- and drives the
    real registry validator over the real loaded revision. A detector that only fires
    on shaped input can still miss the site that matters.

    This one is closed harder than the sibling above. The misbinding needed a
    draft attribute yielding the DECLARANT's own tax id, and no such attribute
    exists any more: :class:`ExportDraftAttribute` declares four members, all of
    them period or ejercicio facts. A slot reserved for a group parent's foreign
    TIN therefore has nothing to be re-bound to.

    What keeps that closed is the width mapping's TOTALITY, so this asserts the
    property rather than the current membership: re-introducing an identity
    attribute without ruling on its width fails validation instead of passing
    silently, and a 15-wide slot fed a 9-character Spanish tax id is exactly the
    contradiction the detector reports.
    """
    modelo, _catalogues = _committed_modelo("200")
    revision = modelo.revisions["2024-y-siguientes"]

    assert set(DRAFT_ATTRIBUTE_CANONICAL_WIDTHS) == set(ExportDraftAttribute), (
        "the width ruling must stay total over the declarable attributes, or a "
        "re-introduced identity attribute could be bound with no width ruling at all"
    )
    assert all(attribute.name.startswith(("FILING_", "PERIOD_")) for attribute in ExportDraftAttribute), (
        "a draft attribute yielding a party's identity is back; the grupo-mercantil "
        "parent-TIN misbinding becomes expressible again and needs its own width ruling"
    )

    declarant_bound_slots = tuple(
        field.id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.DRAFT and field.length == SPANISH_TAX_ID_WIDTH
    )
    assert declarant_bound_slots == (), f"a draft field is bound at the Spanish tax id's width: {declarant_bound_slots}"

    misbound = _committed_export_field(revision).model_copy(
        update={
            "kind": CasillaFieldKind.DRAFT,
            "draft_attribute": ExportDraftAttribute.FILING_YEAR,
            "casilla_id": None,
            "literal": None,
            "length": SPANISH_TAX_ID_WIDTH,
        },
    )
    failures = validate_draft_field_slot_width(prefix="modelo 200 revision 2024-y-siguientes", field=misbound)
    assert any(f"to a slot of length {SPANISH_TAX_ID_WIDTH}" in failure for failure in failures), failures


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
        _validate_revision(modelo, catalogues, mutated)


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
        _validate_revision(modelo, catalogues, mutated)


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
                    casilla_id=_MISSING_CASILLA,
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
            ),
        },
    )
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match=r"extraction profile .* unknown casilla"):
        _validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_extraction_profile_artefact_surface_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"accepted_artefact_kinds": ("justificante_pdf",)})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match="surface 'declaracion_pdf' requires"):
        _validate_revision(modelo, catalogues, mutated)


def test_extraction_target_definition_roundtrip() -> None:
    """ExtractionTargetDefinition strict-frozen roundtrip with non-default fields."""
    target = ExtractionTargetDefinition(
        casilla_id=_NAMED_LABEL_CASILLA,
        match_strategy="named_label",
        value_kind="text",
        label_pattern=r"Mi etiqueta especial",
    )
    raw = target.model_dump()
    restored = ExtractionTargetDefinition.model_validate(raw)
    assert restored == target
    assert restored.casilla_id == _NAMED_LABEL_CASILLA
    assert restored.match_strategy == "named_label"
    assert restored.value_kind == "text"
    assert restored.label_pattern == r"Mi etiqueta especial"


def test_bbox_anchor_rejects_inverted_anchor_x_range() -> None:
    with pytest.raises(ValidationError, match="bbox anchor_x_min must not exceed anchor_x_max"):
        BboxAnchorSpec(
            box_number_pattern=r"01",
            value_offset="right_of_number",
            anchor_x_min=200.0,
            anchor_x_max=100.0,
        )


def test_extraction_target_definition_anti_tautology() -> None:
    """Mutating the serialised payload surfaces inequality after reload."""
    target = ExtractionTargetDefinition(
        casilla_id=_NUMERIC_CASILLA_01,
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
            casilla_id=_DECL_CNAE_CASILLA,
            match_strategy="named_label",
            value_kind="text",
        )


def test_extraction_target_numeric_casilla_rejects_label_pattern() -> None:
    with pytest.raises(ValidationError, match="numeric_casilla extraction targets must not define label_pattern"):
        ExtractionTargetDefinition(
            casilla_id=_NUMERIC_CASILLA_01,
            match_strategy="numeric_casilla",
            value_kind="amount",
            label_pattern="Retenciones",
        )


def test_casilla_accepts_continuidad_id_roundtrip() -> None:
    casilla = CasillaDefinition.model_validate(
        {
            "id": "0700",
            "number": "0700",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("base",),
            "data_type": "money",
            "continuidad_id": "renta-base-liquidacion-general",
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
        },
    )

    restored = CasillaDefinition.model_validate(
        {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
    )

    assert restored == casilla
    assert restored.continuidad_id == "renta-base-liquidacion-general"


def test_casilla_continuidad_id_refuses_a_dotted_segment() -> None:
    """A chain id must be one plain locale-key segment, so dots are refused.

    The chain id is embedded whole into the shared locale key as
    ``modelo.schema.<modelo>.casilla.continuidad.<chain-id>.<field>``, and
    ``encode_modelo_locale_segment`` base32-encodes any segment that is not
    ``[A-Za-z0-9_-]+``. A dotted id therefore renders its own continuity key as
    an opaque ``x-...`` blob in all four catalogues -- a translator sees the blob
    and never the concept.

    The pattern used to permit ``.`` and ``:``, so nothing refused such an id and
    the damage surfaced only as unreadable keys afterwards; eleven Modelo 100
    pilots shipped that way before being converted. This asserts the refusal at
    the boundary, so the class cannot return by loosening the pattern back.
    """
    for rejected in ("irpf.inmueble.porcentaje-propiedad", "irpf:inmueble"):
        with pytest.raises(ValidationError, match="continuidad_id"):
            CasillaDefinition.model_validate(
                {
                    "id": "0700",
                    "number": "0700",
                    "localization_keys": ("test.schema.casilla.label",),
                    "section": ("base",),
                    "data_type": "money",
                    "continuidad_id": rejected,
                    "legal_refs": ("ley-35-2006:art-48",),
                    "source_refs": ("aeat-manual",),
                },
            )


def test_casilla_continuidad_id_uses_registry_id_shape() -> None:
    with pytest.raises(ValidationError, match="continuidad_id"):
        CasillaDefinition.model_validate(
            {
                "id": "0700",
                "number": "0700",
                "localization_keys": ("test.schema.casilla.label",),
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
            continuidad_id="renta-base-liquidacion-general",
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
            "localization_key": "test.schema.revision.label",
            "valid_from": date(2024, 1, 1),
            "period_selector": {"years": (2024,), "periods": ("0A",)},
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
        },
    )

    assert revision.continuidad_validation == "advisory"
    assert revision.casilla_continuidad_evolutions == ()
