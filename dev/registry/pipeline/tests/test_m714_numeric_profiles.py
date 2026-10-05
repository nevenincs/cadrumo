"""Complete, source-pinned numeric coverage for every enrolled M714 workbook."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...compiler.authority import compiled_bundled_authority
from .._export_tree import render_complete_export_tree
from ..export_field_numeric_derivation import _numeric_derivation
from ..export_field_numeric_source_pins import m714_numeric_values_for
from ..render_check import GeneratedExportBootstrapTransport, revision_render_inputs
from ..render_profile import validate_render_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def authority():
    return compiled_bundled_authority()


@pytest.mark.parametrize("year", range(2021, 2026))
def test_complete_official_design_renders_with_its_exact_numeric_profile(authority, year: int, tmp_path: Path) -> None:
    source_ref = f"aeat-dr-714-{year}"
    inputs = revision_render_inputs(
        authority,
        modelo="714",
        revision=str(year),
        source_ref=source_ref,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="modelo-714-fichero-aeat",
            line_ending="none",
            source_ref=source_ref,
            source_sha256=authority.catalogues.sources[source_ref].sha256,
            supersedes_layout_id="modelo-714-fichero-aeat",
        ),
        filing_year=year,
        period="0A",
        source_root=bundled_path(),
    )
    validate_render_profile(inputs.render_profile, inputs.joined, inputs.render_profile_source_evidence)
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    fields = {str(field.id): field for record in rendered.layout.records for field in record.fields}
    anchored = {
        (field.parser_field.sheet, field.parser_field.source_row): fields[str(field.semantic_entry.export_field_id)]
        for field in inputs.joined.fields
    }
    birth = anchored["714-01 Patrimonio", 18]
    assert (birth.length, birth.date_format) == (8, "ddmmaaaa")
    assert anchored["714-01 Patrimonio", 17].allowed_values == ("1", "2", "3", "4")
    assert anchored["714-01 Patrimonio", 48].allowed_values == ("0", "1", "2")
    assert anchored["714-01 Patrimonio", 37].allowed_values == tuple(sorted(str(value) for value in range(1, 53)))
    for row in (51, 56):
        code = anchored["714-01 Patrimonio", row]
        assert (code.length, code.data_type.value, code.decimals, code.allowed_values) == (2, "integer", None, None)
    assert anchored["714-03 Patrimonio", 27].allowed_values == ("0", "1", "2", "3", "4", "5")
    assert anchored["714-10 Patrimonio", 23].decimals == 2
    source_rows = {(field.parser_field.sheet, field.parser_field.source_row): field for field in inputs.joined.fields}
    identity = inputs.render_profile.design_identity
    for anchor in (("714-01 Patrimonio", 37), ("714-01 Patrimonio", 51), ("714-03 Patrimonio", 27)):
        joined_field = source_rows[anchor]
        with pytest.raises(RegistryValidationError, match="unreviewed or stale"):
            m714_numeric_values_for(joined_field, identity.model_copy(update={"source_sha256": "0" * 64}))
        for changed in (
            {"source_row": joined_field.parser_field.source_row + 1},
            {"length": joined_field.parser_field.length + 1},
            {"content": (joined_field.parser_field.content or "") + " unknown"},
        ):
            moved = joined_field.model_copy(
                update={"parser_field": joined_field.parser_field.model_copy(update=changed)}
            )
            assert m714_numeric_values_for(moved, identity) is None
    duplicate = source_rows["714-03 Patrimonio", 27]
    with pytest.raises(RegistryValidationError, match="ambiguous content"):
        _numeric_derivation(duplicate, export_record_id="modelo-714-page-03")
    missing = inputs.render_profile.model_copy(update={"singleton_rules": inputs.render_profile.singleton_rules[:-1]})
    with pytest.raises(RegistryValidationError, match="cover exactly"):
        validate_render_profile(missing, inputs.joined, inputs.render_profile_source_evidence)
    stale = inputs.render_profile.model_copy(
        update={"design_identity": inputs.render_profile.design_identity.model_copy(update={"source_sha256": "0" * 64})}
    )
    with pytest.raises(RegistryValidationError, match="exact official design"):
        validate_render_profile(stale, inputs.joined, inputs.render_profile_source_evidence)
