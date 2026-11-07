"""The source-pinned literal readings answer only for their exact official anchor."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ..export_field_literal_source_pins import (
    source_pinned_190_transport_constant,
    source_pinned_194_transport_constant,
    source_pinned_349_constant,
)
from ..joined_record_design import JoinedRecordDesignField
from ..render_check import GeneratedExportBootstrapTransport, RevisionRenderInputs, build_revision_render_inputs
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M194_OPEN_ENDED = open_ended_revision("194")
_M194_REVISION = str(_M194_OPEN_ENDED.id)
_SOPORTE = "modelo-194-decl-soporte"
_SOPORTE_CONTENT = "Se cumplimentará una de las siguientes claves: 'T': Transmisión telemática."


@pytest.fixture(scope="module")
def inputs() -> RevisionRenderInputs:
    root = Path("src/cadrumo/_data")
    mapping = load_semantic_map(Path("dev/registry/mappings/modelo_194") / _M194_REVISION)
    return build_revision_render_inputs(
        load_modelo_directory(root / "registry/aeat/modelos/194"),
        load_shared_catalogues(root / "registry/aeat"),
        modelo="194",
        revision=_M194_REVISION,
        source_ref=mapping.source_ref,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id=f"generated-modelo-194-{_M194_REVISION}-fichero",
            line_ending="crlf",
            source_ref=mapping.source_ref,
            source_sha256=mapping.source_sha256,
        ),
        filing_year=_M194_OPEN_ENDED.valid_from.year,
        period="0A",
        source_root=root,
    )


def _field(inputs: RevisionRenderInputs, export_field_id: str) -> JoinedRecordDesignField:
    return next(field for field in inputs.joined.fields if str(field.semantic_entry.export_field_id) == export_field_id)


def test_the_m194_soporte_code_is_read_from_its_exact_2024_design(inputs: RevisionRenderInputs) -> None:
    soporte = _field(inputs, _SOPORTE)

    assert source_pinned_194_transport_constant(soporte, inputs.render_profile, _SOPORTE_CONTENT) == "T"


def test_the_m194_soporte_code_is_refused_when_its_design_text_changes(inputs: RevisionRenderInputs) -> None:
    soporte = _field(inputs, _SOPORTE)

    with pytest.raises(RegistryValidationError, match="modelo 194 telematic constant"):
        source_pinned_194_transport_constant(
            soporte, inputs.render_profile, "Se cumplimentará una de las siguientes claves: 'C': Soporte."
        )


def test_a_field_that_is_not_the_pinned_anchor_has_no_pinned_reading(inputs: RevisionRenderInputs) -> None:
    other = next(field for field in inputs.joined.fields if str(field.semantic_entry.export_field_id) != _SOPORTE)

    assert source_pinned_194_transport_constant(other, inputs.render_profile, _SOPORTE_CONTENT) is None
    assert source_pinned_190_transport_constant(other, inputs.render_profile, _SOPORTE_CONTENT) is None


def test_another_modelos_pin_does_not_answer_for_the_m194_design(inputs: RevisionRenderInputs) -> None:
    soporte = _field(inputs, _SOPORTE)

    assert source_pinned_349_constant(soporte, inputs.render_profile, _SOPORTE_CONTENT) is None
    assert source_pinned_190_transport_constant(soporte, inputs.render_profile, _SOPORTE_CONTENT) is None
