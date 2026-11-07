"""Publication keeps source applicability, storage identity and authority grade distinct."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
    split_exercise_revisions,
)

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from ...compiler.validate_export_field_placement import binding_export_spans, validate_export_record_field_placement
from ...tests.authored_edition_support import source_first_exercise, source_reference
from ..bootstrap_supersession import require_stable_layout_identity_for_storage_lineage
from ..cli import GeneratedTreeInvocation, check_prepared_invocation, prepare_generated_tree_invocation
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_M131_MAPPINGS = Path(__file__).resolve().parents[2] / "mappings" / "modelo_131"
_M122_SOURCE = "aeat-dr-122-2016"


def test_preparation_preserves_distinct_sibling_lineage_evidence_in_source_scope(tmp_path: Path) -> None:
    authority = compiled_bundled_authority()
    oldest, sibling_id = (str(revision.id) for revision in authored_revisions("194")[:2])
    sibling = authority.modelo("194").revisions[sibling_id]
    attestation = next(
        item for item in sibling.lineage_attestations if item.continuidad_id == "declarante-contacto-telefono"
    )
    field = next(item for item in sibling.casillas if item.continuidad_id == attestation.continuidad_id)
    assert attestation.source_refs != field.source_refs
    invocation = GeneratedTreeInvocation("194", oldest, "aeat-dr-194-2019", filing_year_envelope().floor, "0A")
    prepared = prepare_generated_tree_invocation(invocation, tmp_path, authority=authority)
    assert prepared.validation.scope_authority is authority
    assert prepared.validation.continuity_metadata_modelo_root is None
    assert not (tmp_path / "continuity-metadata").exists()
    assert prepared.validation.scope_authority.modelo("194").revisions[sibling_id] == sibling


@pytest.mark.parametrize(
    ("modelo_id", "revision", "stable_id"),
    tuple(
        (modelo_id, str(revision.id), f"modelo-{modelo_id}-fichero-boe")
        for modelo_id in ("123", "490")
        for revision in authored_revisions(modelo_id)
    ),
)
def test_linked_editions_require_their_reviewed_stable_layout_identity(
    modelo_id: str,
    revision: str,
    stable_id: str,
) -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo_id))
    assert tuple(str(layout.id) for layout in modelo.revisions[revision].export_layouts) == (stable_id,)
    require_stable_layout_identity_for_storage_lineage(
        modelo,
        revision=revision,
        superseded_layout_id=stable_id,
        generated_layout_id=stable_id,
    )
    with pytest.raises(ValueError, match="must retain stable layout id"):
        require_stable_layout_identity_for_storage_lineage(
            modelo,
            revision=revision,
            superseded_layout_id=stable_id,
            generated_layout_id=f"generated-modelo-{modelo_id}-{revision}-fichero",
        )


def _static_export_invocations() -> tuple[GeneratedTreeInvocation, ...]:
    early_490, _late = split_exercise_revisions("490", early_period="1T", late_period="2T")
    return (
        GeneratedTreeInvocation(
            "122", str(open_ended_revision("122").id), _M122_SOURCE, filing_year_envelope().floor, "0A"
        ),
        GeneratedTreeInvocation("490", str(early_490.id), "aeat-dr-490-2021", early_490.valid_from.year, "1T"),
    )


@pytest.mark.parametrize("invocation", _static_export_invocations())
def test_static_export_can_validate_at_the_revisions_applicability_grade(
    tmp_path: Path,
    invocation: GeneratedTreeInvocation,
) -> None:
    authority = compiled_bundled_authority()
    prepared = prepare_generated_tree_invocation(invocation, tmp_path, authority=authority)
    assert prepared.validation.required_grade is RegistryAuthorityGrade.APPLICABILITY
    result, rendered, _target_state = check_prepared_invocation(prepared)
    assert result in {"publishable_absence", "matched"}
    assert rendered.output_files
    with pytest.raises(RegistryValidationError, match="cannot satisfy the requested 'filing' snapshot authority"):
        authority.snapshot(
            invocation.modelo,
            filing_year=invocation.filing_year,
            period=invocation.period,
            revision_id=invocation.revision,
            grade=RegistryAuthorityGrade.FILING,
        )


def test_static_export_refuses_unsupported_source_frame(tmp_path: Path) -> None:
    before_source = source_first_exercise(source_reference(_M122_SOURCE)) - 1
    invocation = GeneratedTreeInvocation("122", str(open_ended_revision("122").id), _M122_SOURCE, before_source, "0A")
    with pytest.raises(ValueError, match=rf"filing_year={before_source}.*eligible=\(\)"):
        prepare_generated_tree_invocation(invocation, tmp_path, authority=compiled_bundled_authority())


def test_modelo_131_historical_page_is_source_complete_without_duplicate_binding_spans(tmp_path: Path) -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    late_law = "real-decreto-ley-23-2026:art-1"
    _early, late = split_exercise_revisions("131", early_period="2T", late_period="3T")
    assert late_law not in modelo.legal_refs
    assert late_law in modelo.revisions[str(late.id)].legal_refs

    historical = str(authored_revisions("131")[0].id)
    invocation = GeneratedTreeInvocation(
        "131", historical, "aeat-dr-131-2019-2023-v101", filing_year_envelope().floor, "1T"
    )
    prepared = prepare_generated_tree_invocation(invocation, tmp_path, authority=compiled_bundled_authority())
    result, rendered, _target_state = check_prepared_invocation(prepared)

    assert result in {"publishable_absence", "matched"}
    assert len(rendered.layout.records) == 1
    assert len(rendered.layout.records[0].fields) == 53
    assert rendered.layout.records[0].binding_record is None
    assert all(str(field.id).startswith(f"modelo-131-{historical}-") for field in rendered.layout.records[0].fields)


def test_modelo_131_same_field_id_still_refuses_two_physical_writers() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    revision = modelo.revisions[str(authored_revisions("131")[1].id)]
    record = next(record for record in revision.export_layouts[0].records if record.binding_record == "DPA")
    spans = binding_export_spans(revision)
    selector = next(span for span in spans["DPA"] if span.offset == 13)
    duplicate = record.fields[0].model_copy(
        update={"id": selector.origin, "offset": selector.offset, "length": selector.length}
    )
    candidate = record.model_copy(update={"fields": (*record.fields, duplicate)})

    failures = validate_export_record_field_placement(
        prefix="modelo 131 identity probe", record=candidate, binding_spans=spans
    )
    assert len(failures) == 1
    assert "positions 13-16 are written twice" in failures[0]


@pytest.mark.parametrize("epoch", sorted(path.name for path in _M131_MAPPINGS.iterdir() if path.is_dir())[1:])
def test_modelo_131_single_did_retains_positive_gate_while_dpa_retains_row_repeat(epoch: str) -> None:
    semantic_map = load_semantic_map(_M131_MAPPINGS / epoch)
    records = {record.record_type: record for record in semantic_map.records}

    assert records["page_1"].binding_record is None
    assert records["DID"].binding_record is None
    assert str(records["DID"].requires_positive_casilla_id) == "15"
    assert records["DPA"].binding_record == "DPA"
    assert records["DPA"].repeat == "binding_rows"
