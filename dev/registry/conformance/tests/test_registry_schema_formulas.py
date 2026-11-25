"""Focused calculation-registry tests."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.schema import (
    RegistrySnapshot,
)
from cadrumo.domain.calculations.registry.schema_base import EvidenceTier
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ...compiler.loader import load_modelo_directory
from ...compiler.validator import RegistryValidator
from ..coverage import build_model_law_coverage_ledger
from ..loader_directory_mode_support import (
    standard_manifest_text,
    standard_revision_preamble_text,
    write_fragmented_modelo_from_text,
)
from ..registry_schema_support import (
    NUMERIC_CASILLA_01,
    committed_registry,
)
from ..registry_schema_support import (
    revision as committed_revision,
)
from .registry_schema_support import (
    committed_modelo_revision_id,
    committed_modelo_text,
    load_modelo_text,
    validate_revision,
    with_binding,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = filing_year_envelope().horizon

_SNAPSHOT_HEADER_EXPECTATIONS = (
    ("modelo.id", "130"),
    ("revision.id", committed_modelo_revision_id()),
    ("filing_year", FILING_YEAR),
    ("period", "3T"),
)


_EXPECTED_LIVE_CROSS_REFERENCES = frozenset({"modelo-130-static-official", "modelo-130-filed-declarations-read"})


# Modelo 130's snapshot must carry these links as a floor rather than an
# inventory: the revision declares additional links that are not part of this
# focused assertion.
_REQUIRED_APPLICATION_LINKS = frozenset(
    {
        "modelo-130-approval",
        "modelo-130-calculation",
        "modelo-130-deadline",
        "modelo-130-export",
        "modelo-130-extractor",
        "modelo-130-filed-declarations-observation",
        "modelo-130-filing",
        "modelo-130-portal-cross-reference",
        "modelo-130-review",
    },
)


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


@pytest.fixture
def modelo_130_snapshot(registry_authority: ValidatedRegistryAuthority) -> RegistrySnapshot:
    return registry_authority.snapshot("130", filing_year=FILING_YEAR, period="3T")


def test_formula_expression_dispatch_table_entry_contract() -> None:
    expression = FormulaExpression.model_validate(
        {
            "dispatch_table_entries": [
                {"key": "madrid", "parameter": "renta-escala-autonomica-madrid-base-general"},
                {"key": "cataluna", "parameter": "renta-escala-autonomica-cataluna-base-general"},
            ],
        },
    )

    assert expression.dispatch_table == {
        "madrid": "renta-escala-autonomica-madrid-base-general",
        "cataluna": "renta-escala-autonomica-cataluna-base-general",
    }

    with pytest.raises(ValidationError, match="duplicate key 'madrid'"):
        FormulaExpression.model_validate(
            {
                "dispatch_table_entries": [
                    {"key": "madrid", "parameter": "renta-escala-autonomica-madrid-base-general"},
                    {"key": "madrid", "parameter": "renta-escala-autonomica-madrid-base-general"},
                ],
            },
        )

    with pytest.raises(ValidationError, match="dispatch_table or dispatch_table_entries"):
        FormulaExpression.model_validate(
            {
                "dispatch_table": {"madrid": "renta-escala-autonomica-madrid-base-general"},
                "dispatch_table_entries": [
                    {"key": "madrid", "parameter": "renta-escala-autonomica-madrid-base-general"},
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
        "modelo-130-reconcile-when-present",
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
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
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
        validate_revision(modelo, catalogues, empty_revision)


def test_model_law_coverage_ledger_does_not_count_layout_source_as_guidance() -> None:
    modelo, catalogues = committed_registry()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=FILING_YEAR, period="3T")
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

    assert by_tier[EvidenceTier.OFFICIAL_SOURCE_GUIDANCE].status == "gap"
    assert by_tier[EvidenceTier.LAYOUT_AUTHORITY].status == "satisfied"


def test_model_law_coverage_ledger_moves_status_when_evidence_tier_changes() -> None:
    modelo, catalogues = committed_registry()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=FILING_YEAR, period="3T")
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

    assert by_tier[EvidenceTier.EXECUTABLE_PARITY_EVIDENCE].status == "satisfied"
    assert by_tier[EvidenceTier.LAYOUT_AUTHORITY].status == "gap"


def test_modelo_file_rejects_local_source_catalogue(tmp_path: Path) -> None:
    text = committed_modelo_text() + '\n[source."local"]\nkind = "record_design"\n'

    with pytest.raises(RegistryLoadError, match="must not define local legal/source"):
        load_modelo_text(tmp_path, text)


def test_modelo_file_rejects_empty_filing_grade_evidence(tmp_path: Path) -> None:
    manifest = standard_manifest_text("minimal legal evidence fixture")
    revision = standard_revision_preamble_text()
    text = manifest + revision
    mutated, replacements = re.subn(
        r'(?m)^legal_refs = \["ley-58-2003:art-29"\]$',
        "legal_refs = []",
        text,
        count=1,
    )
    assert replacements == 1, "minimal typed fixture must contain its modelo-level legal evidence"

    with pytest.raises(RegistryLoadError, match="too_short"):
        load_modelo_text(tmp_path, mutated)


def test_modelo_file_rejects_casilla_binding_id_collision(tmp_path: Path) -> None:
    text = """
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
provider = { kind = "manual_input", record = "DPA", field = "test", offset = 1, length = 1, data_type = "integer" }
value = { data_type = "integer", channel = "integer" }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()

    with pytest.raises(RegistryValidationError, match="duplicate registry id '01' shared by casilla, binding"):
        load_modelo_directory(write_fragmented_modelo_from_text(tmp_path / "999", text))


def test_validation_requires_source_integrity(tmp_path: Path) -> None:
    """Validation against a source root lacking the cited corpus refuses by name."""
    modelo, catalogues = committed_registry()

    with pytest.raises(RegistryValidationError, match=r"missing (extracted )?corpus"):
        RegistryValidator(catalogues, source_root=tmp_path).validate_modelo(modelo)


def test_validator_rejects_duplicate_formula_targets() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    duplicate = revision.formulas[0].model_copy(update={"id": f"{revision.formulas[0].id}-duplicate"})
    mutated = revision.model_copy(update={"formulas": (*revision.formulas, duplicate)})

    with pytest.raises(RegistryValidationError, match="duplicate formula target"):
        validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_formula_id_matching_casilla_id() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
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
        validate_revision(modelo, catalogues, mutated)


def test_validator_reports_casilla_binding_id_collision_owners() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    collision_id = revision.casillas[0].id
    collision_binding = revision.bindings[0].model_copy(update={"id": collision_id})
    mutated = revision.model_copy(update={"bindings": (*revision.bindings, collision_binding)})

    with pytest.raises(
        RegistryValidationError,
        match=rf"duplicate registry id '{re.escape(collision_id)}' shared by casilla, binding",
    ):
        validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_formula_target_mismatch() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    formula = revision.formulas[0]
    mismatched_formula = formula.model_copy(update={"target_casilla_id": NUMERIC_CASILLA_01})
    mutated = revision.model_copy(update={"formulas": (mismatched_formula, *revision.formulas[1:])})

    with pytest.raises(RegistryValidationError, match=f"targeting '{NUMERIC_CASILLA_01}'"):
        validate_revision(modelo, catalogues, mutated)


@pytest.mark.parametrize("authority_grade", [RegistryAuthorityGrade.FILING, RegistryAuthorityGrade.APPLICABILITY])
def test_validator_requires_workbook_parity_for_filing_or_declared_layout(
    authority_grade: RegistryAuthorityGrade,
) -> None:
    """A parity anchor follows a filing claim or layout, never a bare schedule claim."""
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo).model_copy(
        update={"authority_grade": authority_grade, "workbook_parity_refs": ()},
    )

    with pytest.raises(RegistryValidationError, match="must declare official workbook parity coverage"):
        validate_revision(modelo, catalogues, revision)


def test_modelo_file_rejects_formula_workbook_without_runner(tmp_path: Path) -> None:
    text = committed_modelo_text().replace(
        'formula_coverage = "record_design_layout"',
        'formula_coverage = "formula_form"',
        1,
    )

    with pytest.raises(RegistryLoadError, match="formula coverage requires a runner"):
        load_modelo_text(tmp_path, text)


def test_validator_rejects_formula_workbook_without_executable_parity_source() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    workbook = revision.workbook_parity_refs[0].model_copy(
        update={
            "formula_coverage": "formula_form",
            "runner_required": True,
            "output_cells": {"result": "Modelo!A1"},
        },
    )
    mutated = revision.model_copy(update={"workbook_parity_refs": (workbook,)})

    with pytest.raises(RegistryValidationError, match="requires executable parity evidence source"):
        validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_layout_workbook_without_layout_authority_source() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
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
        validate_revision(modelo, mutated_catalogues, revision)


def test_validator_rejects_formula_without_official_source_guidance() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    formulas = tuple(
        formula.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
        if formula.id == "modelo-130-pago-fraccionado-directa"
        else formula
        for formula in revision.formulas
    )
    mutated = revision.model_copy(update={"formulas": formulas})

    with pytest.raises(RegistryValidationError, match="requires official_source_guidance source evidence"):
        validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_formula_citation_missing_from_official_source() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
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
        validate_revision(modelo, catalogues, mutated)


def test_validator_rejects_binding_citation_missing_from_official_source() -> None:
    modelo, catalogues = committed_registry()
    revision = committed_revision(modelo)
    binding = revision.bindings[0]
    bad_citations = tuple(
        citation.model_copy(update={"required_text": ("official source does not contain this binding anchor",)})
        for citation in binding.source_citations
    )
    mutated = with_binding(revision, binding.model_copy(update={"source_citations": bad_citations}))

    with pytest.raises(RegistryValidationError, match=r"source citation .* missing text"):
        validate_revision(modelo, catalogues, mutated)
