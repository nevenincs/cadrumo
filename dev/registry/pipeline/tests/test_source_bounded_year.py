"""Official year bounds survive generation, serialization and both codec directions."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportEncoding,
    render_fixed_width_export_field,
)
from cadrumo.domain.calculations.registry.fixed_width_parser import parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from .._export_tree import render_complete_export_tree
from ..export_fragment_provenance_projection import loader_semantic_digest
from ..export_tree_field_derivation import _normalise_field
from ..export_tree_models import ExportTreeTransportProfile
from ..joined_record_design import JoinedRecordDesignField, join_record_design_semantics
from ..record_design_intermediate import load_record_design_intermediate
from ..render_profile_eligibility import resolve_render_profile_eligibility
from ..render_profile_evidence import ReviewedPolicyDecision
from ..render_profile_loading import load_render_profile
from ..render_profile_model import RenderProfile
from ..render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity
from ..render_profile_rules import SingletonNumericRule
from ..render_profile_source_reader import load_render_profile_source_evidence
from ..semantic_map import SemanticMapAnchor, SemanticMapEntry, load_semantic_map
from ..year_constraints import BoundedYearDeclaration, bounded_year_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def year_inputs() -> tuple[JoinedRecordDesignField, ExportTreeTransportProfile, RenderProfile]:
    root = Path("src/cadrumo/_data")
    catalogues = load_shared_catalogues(root / "registry/aeat")
    source = "aeat-dr-216-2024"
    intermediate = load_record_design_intermediate(
        root, catalogues.sources, source_ref=source, filing_year=2024, design_epoch="2024"
    )
    field = next(f for sheet in intermediate.sheets for f in sheet.fields if f.source_cell == "A14")
    assert field.content == ">= 2024" and field.offset == 103 and field.length == 4
    anchor = SemanticMapAnchor(
        sheet=field.sheet,
        source_row=field.source_row,
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        record_identity=field.record_identity,
    )
    entry = SemanticMapEntry(
        export_field_id="modelo-216-page-01-devengo-ejercicio",
        kind=CasillaFieldKind.DRAFT,
        draft_attribute=ExportDraftAttribute.FILING_YEAR,
        anchor=anchor,
        legal_refs=("orden-eha-3290-2008:art-1",),
        source_refs=(source,),
    )
    joined = JoinedRecordDesignField(parser_field=field, semantic_entry=entry)
    identity = RenderProfileDesignIdentity(
        modelo="216",
        design_epoch="2024",
        source_ref=source,
        source_sha256=intermediate.source.source_sha256,
    )
    profile_anchor = RenderProfileAnchor(**anchor.model_dump(exclude={"ordinal_absent"}))
    rule = SingletonNumericRule(
        rule_kind="singleton_numeric",
        aeat_type="Num",
        semantic_kind="year_yyyy",
        value_policy=ExportValuePolicy.FOUR_DIGIT_YEAR,
        integer_digits=4,
        decimal_digits=0,
        sign_policy="unsigned",
        allowed_values=(),
        anchor=profile_anchor,
        evidence=ReviewedPolicyDecision(
            authority_kind="reviewed_policy",
            decision_id="m216-2024-year-yyyy",
            governed_anchor=profile_anchor,
            decision_statement="Ejercicio is the four-digit filing year, subject to the official >= 2024 constraint.",
            justification=(
                "The source gives four Num positions for Ejercicio; "
                "its lower bound states eligibility rather than formatting."
            ),
        ),
    )
    profile = RenderProfile(
        schema_version=1,
        design_identity=identity,
        fragment_ids=(),
        width_17_rules=(),
        singleton_rules=(rule,),
    )
    transport = ExportTreeTransportProfile(
        **identity.model_dump(),
        layout_id="generated-modelo-216-2024-y-siguientes-fichero",
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="none",
        serializer_convention="rtoml-pretty-v1",
    )
    return joined, transport, profile


def _derive(inputs: tuple[JoinedRecordDesignField, ExportTreeTransportProfile, RenderProfile]):
    joined, transport, profile = inputs
    return _normalise_field(joined, transport, profile, export_record_id="modelo-216-page-01")


@pytest.mark.parametrize("year", [2024, 2026, 9999])
def test_official_minimum_accepts_boundary_and_later_four_digit_years(year_inputs, year: int) -> None:
    derived = _derive(year_inputs)
    assert derived.derivation_code == "numeric-source-bounded-year-v1"
    assert derived.field.minimum_year == 2024
    wire = render_fixed_width_export_field(derived.field, year)
    assert wire == str(year)
    assert str(parse_fixed_width_export_field(derived.field, wire)) == str(year)


def test_earlier_year_refuses_in_both_codec_directions(year_inputs) -> None:
    field = _derive(year_inputs).field
    with pytest.raises(RegistryValidationError, match="official minimum 2024"):
        render_fixed_width_export_field(field, 2023)
    with pytest.raises(RegistryValidationError, match="official minimum 2024"):
        parse_fixed_width_export_field(field, "2023")


def test_minimum_survives_strict_json_and_is_attested(year_inputs) -> None:
    field = _derive(year_inputs).field
    assert ExportFieldDefinition.model_validate_json(field.model_dump_json()) == field
    record = ExportRecordDefinition(
        id="modelo-216-page-01",
        record_type="page_01",
        order=1,
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="none",
        fields=(field,),
    )
    layout = ExportLayoutDefinition(
        id=year_inputs[1].layout_id,
        source_refs=field.source_refs,
        legal_refs=field.legal_refs,
        records=(record,),
    )
    changed = layout.model_copy(
        update={"records": (record.model_copy(update={"fields": (field.model_copy(update={"minimum_year": 2025}),)}),)}
    )
    assert loader_semantic_digest(layout) != loader_semantic_digest(changed)


def test_constraint_requires_reviewed_wire_rule_and_shared_eligibility(year_inputs) -> None:
    joined, transport, profile = year_inputs
    empty = RenderProfile.model_validate({**profile.model_dump(), "singleton_rules": ()})
    with pytest.raises(RegistryValidationError, match="exact reviewed four-digit-year rule"):
        _derive((joined, transport, empty))
    source = load_record_design_intermediate(
        Path("src/cadrumo/_data"),
        load_shared_catalogues(Path("src/cadrumo/_data/registry/aeat")).sources,
        source_ref=str(transport.source_ref),
        filing_year=2024,
        design_epoch="2024",
    ).source
    assert resolve_render_profile_eligibility((joined.parser_field,), source).smaller_fields == (joined.parser_field,)


@pytest.mark.parametrize("statement", ["<= 2024", "> 2024", ">= 2024 o 2022", ">= 2024 si procede"])
def test_alternatives_or_different_bounds_do_not_inherit_the_reading(year_inputs, statement: str) -> None:
    joined, transport, profile = year_inputs
    changed = joined.model_copy(update={"parser_field": joined.parser_field.model_copy(update={"content": statement})})
    with pytest.raises(RegistryValidationError, match="complete source-pinned reading"):
        _derive((changed, transport, profile))


@pytest.mark.parametrize("change", [{"length": 5}, {"aeat_type": "An"}])
def test_bound_cannot_supply_missing_or_wrong_wire_geometry(year_inputs, change) -> None:
    joined, transport, profile = year_inputs
    changed = joined.model_copy(update={"parser_field": joined.parser_field.model_copy(update=change)})
    with pytest.raises(RegistryValidationError, match="four-position Num draft filing_year"):
        _derive((changed, transport, profile))


def test_semantic_change_cannot_turn_the_official_year_into_a_filler(year_inputs) -> None:
    joined, transport, profile = year_inputs
    changed = joined.model_copy(
        update={
            "semantic_entry": joined.semantic_entry.model_copy(
                update={"kind": "filler", "draft_attribute": None},
            )
        }
    )
    with pytest.raises(RegistryValidationError, match="four-position Num draft filing_year"):
        _derive((changed, transport, profile))


def test_reissued_source_and_undeclared_cells_do_not_receive_the_bound(year_inputs) -> None:
    joined, transport, profile = year_inputs
    with pytest.raises(RegistryValidationError, match="parser-read source SHA-256"):
        _derive((joined, transport.model_copy(update={"source_sha256": "0" * 64}), profile))
    assert (
        bounded_year_for(
            source_ref=str(transport.source_ref),
            source_sha256=transport.source_sha256,
            sheet=joined.parser_field.sheet,
            source_cell="A15",
            published_statement=">= 2024",
        )
        is None
    )


def test_declaration_and_field_refuse_incoherent_constraints(year_inputs) -> None:
    declaration = bounded_year_for(
        source_ref="aeat-dr-216-2024",
        source_sha256=year_inputs[1].source_sha256,
        sheet="Pág. 1",
        source_cell="A14",
        published_statement=">= 2024",
    )
    assert declaration is not None
    with pytest.raises(ValidationError, match="exact inclusive lower bound"):
        BoundedYearDeclaration.model_validate({**declaration.model_dump(), "minimum_year": 2023})
    field = _derive(year_inputs).field
    with pytest.raises(ValidationError, match="four-digit-year value policy"):
        ExportFieldDefinition.model_validate({**field.model_dump(), "value_policy": None})


def test_complete_official_216_design_retains_year_bound_and_count_geometry(year_inputs, tmp_path: Path) -> None:
    root = Path("src/cadrumo/_data")
    catalogues = load_shared_catalogues(root / "registry/aeat")
    definition = load_modelo_directory(root / "registry/aeat/modelos/216")
    revision = definition.revisions["2024-y-siguientes"]
    intermediate = load_record_design_intermediate(
        root,
        dict(catalogues.sources),
        source_ref="aeat-dr-216-2024",
        filing_year=2024,
        design_epoch="2024",
    )
    semantic = load_semantic_map(Path("dev/registry/mappings/modelo_216/2024"))
    profile = load_render_profile(Path("dev/registry/render_profiles/modelo_216/2024"))
    joined = join_record_design_semantics(
        semantic,
        intermediate,
        RegistryRevisionInspection.from_revision(
            modelo=definition,
            revision=revision,
            source_root=root,
            sources=catalogues.sources,
            legal_ref_ids=frozenset(catalogues.legal),
        ),
    )
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=revision.id,
        joined=joined,
        semantic_map=joined.compiled_semantic_map or semantic,
        transport_profile=year_inputs[1],
        render_profile=profile,
        render_profile_source_evidence=load_render_profile_source_evidence(
            root / catalogues.sources["aeat-dr-216-2024"].corpus_path,
            profile,
        ),
    )
    assert rendered.layout.filing_envelope is not None
    assert len(rendered.layout.filing_envelope.prefix_fields) == 13
    year = next(field.field for field in rendered.field_derivations if field.parser_field.source_cell == "A14")
    assert year.minimum_year == 2024
    assert render_fixed_width_export_field(year, 2024) == "2024"
    with pytest.raises(RegistryValidationError, match="official minimum 2024"):
        parse_fixed_width_export_field(year, "2023")
    counts = tuple(
        field for field in rendered.field_derivations if field.parser_field.content == "[entero 17 posiciones]"
    )
    assert counts
    for count in counts:
        assert count.field.data_type == "integer" and not count.field.signed
        assert render_fixed_width_export_field(count.field, 123) == "0" * 14 + "123"


@pytest.mark.parametrize("content", ["[entero 18 posiciones]", "[entero 17 posiciones o 2 decimales]"])
def test_positioned_integer_clause_refuses_wrong_width_and_alternatives(year_inputs, content: str) -> None:
    joined, transport, profile = year_inputs
    parser = joined.parser_field.model_copy(update={"length": 17, "source_cell": "A16", "content": content})
    changed = joined.model_copy(update={"parser_field": parser})
    with pytest.raises(RegistryValidationError):
        _derive((changed, transport, profile))
