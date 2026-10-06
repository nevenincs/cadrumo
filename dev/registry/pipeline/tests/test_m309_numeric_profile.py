"""Ground M309's missing numeric rules and its numbered source enumerations."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy

from ...compiler.authority import compiled_bundled_authority
from .._export_tree import render_complete_export_tree
from ..export_field_numeric_derivation import _numbered_line_enumeration_values, _numeric_derivation
from ..render_check import GeneratedExportBootstrapTransport, revision_render_inputs
from ..render_profile import validate_render_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def inputs():
    return revision_render_inputs(
        compiled_bundled_authority(),
        modelo="309",
        revision="2023-y-siguientes",
        source_ref="aeat-dr-309-2023",
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="modelo-309-fichero-boe",
            line_ending="none",
            source_ref="aeat-dr-309-2023",
            source_sha256="a84c6347a87ac4c4db8610010e100cb8632518a9d20e54e79ffbc713d770beb5",
            supersedes_layout_id="modelo-309-fichero-boe",
        ),
        filing_year=2023,
        period="AD-HOC",
        source_root=bundled_path(),
    )


def test_actual_source_render_retains_closed_codes_and_integer_kilograms(inputs, tmp_path: Path) -> None:
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
    # The identification block belongs to the taxpayer, even with a representative.
    assert fields["modelo-309-p1-nif"].producer_key is FilingProducerKey.TAXPAYER_TAX_ID
    assert fields["modelo-309-p1-apellidos"].producer_key is FilingProducerKey.TAXPAYER_FULL_NAME
    for field_id in ("modelo-309-p1-situacion-tributaria", "modelo-309-p1-hecho-imponible"):
        assert fields[field_id].allowed_values == ("1", "2", "3", "4", "5", "6")
        assert fields[field_id].value_policy is ExportValuePolicy.ENUMERATED_DIGITS
    weight = fields["modelo-309-p1-aeronave-peso"]
    assert (weight.length, weight.data_type.value, weight.decimals, weight.signed) == (10, "integer", None, False)
    assert weight.value_policy is ExportValuePolicy.UNSIGNED_INTEGER
    for field_id in ("modelo-309-p1-devengo-ejercicio", "modelo-309-p1-aeronave-ano"):
        assert fields[field_id].value_policy is ExportValuePolicy.FOUR_DIGIT_YEAR


def test_missing_numeric_anchor_is_refused_against_the_actual_design(inputs) -> None:
    incomplete = inputs.render_profile.model_copy(
        update={"singleton_rules": inputs.render_profile.singleton_rules[:-1]}
    )
    with pytest.raises(RegistryValidationError, match="cover exactly"):
        validate_render_profile(incomplete, inputs.joined, inputs.render_profile_source_evidence)


def test_numbered_source_codes_do_not_admit_prose_or_unlabelled_continuations() -> None:
    assert _numbered_line_enumeration_values("1. Label with 9 digits\n2. Other label") == ("1", "2")
    for ambiguous in (
        "Codes:\n1. First\n2. Second",
        "1. First\ncontinued prose\n2. Second",
        "1. First 2. Second",
        "1.\n2. Other",
    ):
        assert _numbered_line_enumeration_values(ambiguous) is None


def test_duplicate_numbered_codes_are_refused_before_generation(inputs) -> None:
    joined = next(field for field in inputs.joined.fields if field.parser_field.ordinal == "16")
    duplicate = joined.model_copy(
        update={"parser_field": joined.parser_field.model_copy(update={"content": "1. First\n1. Duplicate"})}
    )
    with pytest.raises(RegistryValidationError, match="duplicate values"):
        _numeric_derivation(duplicate, export_record_id="modelo-309-page-01")
