"""Real-source tests for the typed Modelo 390 page-zero composition contract."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import ValidationError

from cadrumo.core import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity, Period
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.authority import bundled_revision_inspection
from cadrumo.domain.calculations.registry.loader import load_catalogue_file

from ..pipeline import _m390_auxiliary_envelope
from ..pipeline._m390_auxiliary_envelope import (
    M390_AUXILIARY_ENVELOPE_TARGETS,
    M390AuxiliaryEnvelopeGenerationInput,
    M390AuxiliaryEnvelopeNumberedPage,
    render_m390_auxiliary_envelope_bytes,
    validate_m390_auxiliary_envelope,
)
from ..pipeline._provenance_manifest import ExportFragmentTarget
from ..pipeline._record_design_ir import RecordDesignIntermediate, load_record_design_intermediate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_M390_DESIGNS = (
    ("aeat-dr-390-2022", "2022", "2022", 2022),
    ("aeat-dr-390-2023", "2023", "2023", 2023),
    ("aeat-dr-390-2024", "2024", "2024", 2024),
    ("aeat-dr-390-2025", "2025", "2025-y-siguientes", 2025),
)


def _product_identity() -> AeatProductSoftwareIdentity:
    return AeatProductSoftwareIdentity(
        program_identifier="C390",
        developer_tax_id="Y0000001S",
        evidence=(
            AeatProductSoftwareEvidence(
                reference="aeat-software-registration:c390",
                digest="a" * 64,
            ),
        ),
    )


def _source_catalogue():
    return load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))


def _intermediate(source_ref: str, filing_year: int, design_epoch: str) -> RecordDesignIntermediate:
    catalogue = _source_catalogue()
    return load_record_design_intermediate(
        bundled_path(),
        catalogue.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )


def _input(
    intermediate: RecordDesignIntermediate,
    revision_id: str,
    design_epoch: str,
    filing_year: int,
) -> M390AuxiliaryEnvelopeGenerationInput:
    return M390AuxiliaryEnvelopeGenerationInput(
        target=ExportFragmentTarget(modelo="390", revision_id=revision_id, design_epoch=design_epoch),
        filing_period=Period.from_year_and_code(filing_year, "0A"),
        product_software_identity=_product_identity(),
        numbered_pages=tuple(
            M390AuxiliaryEnvelopeNumberedPage(
                record_identity=sheet.record_identity,
                payload=f"rendered-page-{ordinal:02d}\\r\\n".encode("ascii"),
            )
            for ordinal, sheet in enumerate(intermediate.sheets, start=1)
        ),
    )


def _render(
    intermediate: RecordDesignIntermediate,
    generation_input: M390AuxiliaryEnvelopeGenerationInput,
):
    return render_m390_auxiliary_envelope_bytes(
        intermediate,
        generation_input,
        source_catalogue=_source_catalogue().sources,
        source_root=bundled_path(),
    )


def _validate(
    intermediate: RecordDesignIntermediate,
    generation_input: M390AuxiliaryEnvelopeGenerationInput,
):
    return validate_m390_auxiliary_envelope(
        intermediate,
        generation_input,
        source_catalogue=_source_catalogue().sources,
        source_root=bundled_path(),
    )


@pytest.mark.parametrize(("source_ref", "design_epoch", "revision_id", "filing_year"), _M390_DESIGNS)
def test_renders_each_real_modelo_390_header_once_before_parser_ordered_pages(
    source_ref: str,
    design_epoch: str,
    revision_id: str,
    filing_year: int,
) -> None:
    """Each epoch composes only its hash-selected source header and numbered pages."""
    intermediate = _intermediate(source_ref, filing_year, design_epoch)
    generation_input = _input(intermediate, revision_id, design_epoch, filing_year)

    rendered = _render(intermediate, generation_input)

    assert intermediate.source.source_ref == source_ref
    assert intermediate.source.design_epoch == design_epoch
    assert tuple(target.target.revision_id for target in M390_AUXILIARY_ENVELOPE_TARGETS) == (
        "2022",
        "2023",
        "2024",
        "2025-y-siguientes",
    )
    assert len(rendered.header) == 328
    assert rendered.header[:22] == f"<T3900{filing_year:04d}0A0000><AUX>".encode("ascii")
    assert rendered.header[22:92] == b" " * 70
    assert rendered.header[92:96] == b"C390"
    assert rendered.header[96:100] == b" " * 4
    assert rendered.header[100:109] == b"Y0000001S"
    assert rendered.header[109:322] == b" " * 213
    assert rendered.header[322:] == b"</AUX>"
    assert tuple(page.record_identity for page in rendered.numbered_pages) == tuple(
        sheet.record_identity for sheet in intermediate.sheets
    )
    assert rendered.payload == rendered.header + b"".join(page.payload for page in rendered.numbered_pages)


def test_refuses_prospective_target_source_cross_epoch() -> None:
    intermediate = _intermediate("aeat-dr-390-2025", 2025, "2025")

    with pytest.raises(RegistryValidationError, match="does not apply to filing year"):
        _render(
            intermediate,
            _input(intermediate, "2024", "2024", 2025),
        )


def test_refuses_source_hash_drift_after_parser_projection() -> None:
    intermediate = _intermediate("aeat-dr-390-2025", 2025, "2025")
    drifting_source = intermediate.source.model_copy(update={"source_sha256": "0" * 64})

    with pytest.raises(RegistryValidationError, match="does not match its reviewed prospective target"):
        _render(
            intermediate.model_copy(update={"source": drifting_source}),
            _input(intermediate, "2025-y-siguientes", "2025", 2025),
        )


def test_refuses_reordered_numbered_pages() -> None:
    intermediate = _intermediate("aeat-dr-390-2025", 2025, "2025")
    generation_input = _input(intermediate, "2025-y-siguientes", "2025", 2025)
    reordered = generation_input.model_copy(update={"numbered_pages": tuple(reversed(generation_input.numbered_pages))})

    with pytest.raises(RegistryValidationError, match="must exactly match the parser-owned source order"):
        _render(intermediate, reordered)


def test_refuses_mutated_header_geometry_and_literal() -> None:
    intermediate = _intermediate("aeat-dr-390-2025", 2025, "2025")
    (header,) = intermediate.auxiliary_envelope_headers
    shifted_second_field = header.fields[1].model_copy(
        update={"parser_field": header.fields[1].parser_field.model_copy(update={"offset": 4})},
    )
    malformed_geometry = header.model_copy(
        update={"fields": (header.fields[0], shifted_second_field, *header.fields[2:])},
    )
    altered_closing_field = header.fields[-1].model_copy(
        update={"parser_field": header.fields[-1].parser_field.model_copy(update={"content": '"</BAD>"'})},
    )
    malformed_literal = header.model_copy(
        update={"fields": (*header.fields[:-1], altered_closing_field)},
    )
    shifted_anchor_field = header.fields[1].model_copy(
        update={"parser_field": header.fields[1].parser_field.model_copy(update={"source_row": 8})},
    )
    malformed_anchor = header.model_copy(
        update={"fields": (header.fields[0], shifted_anchor_field, *header.fields[2:])},
    )
    generation_input = _input(intermediate, "2025-y-siguientes", "2025", 2025)

    with pytest.raises(RegistryValidationError, match="source anchors must be contiguous"):
        _validate(
            intermediate.model_copy(update={"auxiliary_envelope_headers": (malformed_geometry,)}),
            generation_input,
        )
    with pytest.raises(RegistryValidationError, match="literals conflict"):
        _validate(
            intermediate.model_copy(update={"auxiliary_envelope_headers": (malformed_literal,)}),
            generation_input,
        )
    with pytest.raises(RegistryValidationError, match="source rows must retain their exact anchors"):
        _validate(
            intermediate.model_copy(update={"auxiliary_envelope_headers": (malformed_anchor,)}),
            generation_input,
        )


def test_refuses_missing_product_software_identity_and_non_annual_period() -> None:
    intermediate = _intermediate("aeat-dr-390-2025", 2025, "2025")
    generation_input = _input(intermediate, "2025-y-siguientes", "2025", 2025)

    with pytest.raises(ValidationError, match="product_software_identity"):
        M390AuxiliaryEnvelopeGenerationInput.model_validate(
            generation_input.model_dump(mode="python", exclude={"product_software_identity"}),
        )
    with pytest.raises(ValidationError, match="annual period 0A"):
        M390AuxiliaryEnvelopeGenerationInput(
            target=ExportFragmentTarget(modelo="390", revision_id="2025-y-siguientes", design_epoch="2025"),
            filing_period=Period.from_year_and_code(2025, "4T"),
            product_software_identity=_product_identity(),
            numbered_pages=generation_input.numbered_pages,
        )


def test_refuses_current_unreviewed_registry_revision_as_a_prospective_target() -> None:
    # Naming the current revision is revision selection, not filing: a filing
    # snapshot would refuse the very revision this test needs, because being
    # unreviewed is the property under test.
    intermediate = _intermediate("aeat-dr-390-2025", 2025, "2025")
    current = bundled_revision_inspection("390", filing_year=2025, period="0A")
    generation_input = _input(intermediate, str(current.revision_id), "2025", 2025)

    with pytest.raises(RegistryValidationError, match="has no reviewed source binding"):
        _validate(intermediate, generation_input)


def test_m390_auxiliary_authority_has_no_layout_or_historical_output_dependency() -> None:
    """The page-zero contract admits only prospective parser authority and supplied bytes."""
    module = ast.parse(inspect.getsource(_m390_auxiliary_envelope))
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    attribute_names = {node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)}

    assert "cadrumo.domain.calculations.registry.export" not in imported_modules
    assert "resolve_export_layout" not in referenced_names
    assert "export_layouts" not in attribute_names
