"""Publication keeps source applicability, storage identity and authority grade distinct."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from ...compiler.validate_export_field_placement import binding_export_spans, validate_export_record_field_placement
from ..bootstrap_supersession import require_stable_layout_identity_for_storage_lineage
from ..cli import GeneratedTreeInvocation, check_prepared_invocation, prepare_generated_tree_invocation
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("modelo_id", "revision", "stable_id"),
    (
        ("123", "2019-2023", "modelo-123-fichero-boe"),
        ("123", "2024-y-siguientes", "modelo-123-fichero-boe"),
        ("490", "2021", "modelo-490-fichero-boe"),
        ("490", "2022-1t", "modelo-490-fichero-boe"),
        ("490", "2022-2t-4t", "modelo-490-fichero-boe"),
        ("490", "2023-y-siguientes", "modelo-490-fichero-boe"),
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


@pytest.mark.parametrize(
    "invocation",
    (
        GeneratedTreeInvocation("122", "2017-y-siguientes", "aeat-dr-122-2016", 2022, "0A"),
        GeneratedTreeInvocation("490", "2022-1t", "aeat-dr-490-2021", 2022, "1T"),
    ),
)
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
    invocation = GeneratedTreeInvocation("122", "2017-y-siguientes", "aeat-dr-122-2016", 2015, "0A")
    with pytest.raises(ValueError, match=r"filing_year=2015.*eligible=\(\)"):
        prepare_generated_tree_invocation(invocation, tmp_path, authority=compiled_bundled_authority())


def test_modelo_131_historical_page_is_source_complete_without_duplicate_binding_spans(tmp_path: Path) -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    late_law = "real-decreto-ley-23-2026:art-1"
    assert late_law not in modelo.legal_refs
    assert late_law in modelo.revisions["2026-3t-4t"].legal_refs

    invocation = GeneratedTreeInvocation("131", "2019-2023", "aeat-dr-131-2019-2023-v101", 2022, "1T")
    prepared = prepare_generated_tree_invocation(invocation, tmp_path, authority=compiled_bundled_authority())
    result, rendered, _target_state = check_prepared_invocation(prepared)

    assert result in {"publishable_absence", "matched"}
    assert len(rendered.layout.records) == 1
    assert len(rendered.layout.records[0].fields) == 53
    assert rendered.layout.records[0].binding_record is None
    assert all(str(field.id).startswith("modelo-131-2019-2023-") for field in rendered.layout.records[0].fields)


def test_modelo_131_same_field_id_still_refuses_two_physical_writers() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    revision = modelo.revisions["2024"]
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


@pytest.mark.parametrize("epoch", ("2024", "2025", "2026", "2026-late"))
def test_modelo_131_single_did_retains_positive_gate_while_dpa_retains_row_repeat(epoch: str) -> None:
    root = Path(__file__).resolve().parents[2] / "mappings" / "modelo_131"
    semantic_map = load_semantic_map(root / epoch)
    records = {record.record_type: record for record in semantic_map.records}

    assert records["page_1"].binding_record is None
    assert records["DID"].binding_record is None
    assert str(records["DID"].requires_positive_casilla_id) == "15"
    assert records["DPA"].binding_record == "DPA"
    assert records["DPA"].repeat == "binding_rows"
