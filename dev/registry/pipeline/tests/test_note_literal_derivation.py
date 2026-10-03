"""Referenced constants remain exact source facts through export generation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from .._export_tree import ExportTreeTransportProfile, render_complete_export_tree
from ..export_field_literal_derivation import _literal_derivation
from ..joined_record_design import join_record_design_semantics
from ..note_literals import NoteLiteralDeclaration, note_literal_for, note_literals_for
from ..record_design_intermediate import RecordDesignIntermediateRelativeSuffixMarker, load_record_design_intermediate
from ..render_check import RevisionRenderInputs
from ..render_profile_loading import load_render_profile
from ..render_profile_source_reader import load_render_profile_source_evidence
from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def inputs() -> RevisionRenderInputs:
    root = bundled_path()
    catalogues = load_shared_catalogues(root / "registry/aeat")
    definition = load_modelo_directory(root / "registry/aeat/modelos/122")
    revision = definition.revisions["2017-y-siguientes"]
    source_ref = "aeat-dr-122-2016"
    intermediate = load_record_design_intermediate(
        root,
        dict(catalogues.sources),
        source_ref=source_ref,
        filing_year=2024,
        design_epoch="2016",
    )
    semantic = load_semantic_map(Path("dev/registry/mappings/modelo_122/2016"))
    profile = load_render_profile(Path("dev/registry/render_profiles/modelo_122/2016"))
    inspection = RegistryRevisionInspection.from_revision(
        modelo=definition,
        revision=revision,
        source_root=root,
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    joined = join_record_design_semantics(semantic, intermediate, inspection)
    layout_id = "generated-modelo-122-2017-y-siguientes-fichero"
    transport = ExportTreeTransportProfile(
        modelo="122",
        design_epoch="2016",
        source_ref=source_ref,
        source_sha256=intermediate.source.source_sha256,
        layout_id=layout_id,
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="none",
        serializer_convention="rtoml-pretty-v1",
    )
    return RevisionRenderInputs(
        revision_id=revision.id,
        layout_id=layout_id,
        joined=joined,
        semantic_map=joined.compiled_semantic_map or semantic,
        render_profile=profile,
        render_profile_source_evidence=load_render_profile_source_evidence(
            root / catalogues.sources[source_ref].corpus_path,
            profile,
        ),
        transport_profile=transport,
    )


def test_note_constant_is_grounded_in_the_exact_workbook_and_emitted(
    inputs: RevisionRenderInputs, tmp_path: Path
) -> None:
    declaration = note_literals_for(inputs.joined.source)[0]
    source_path = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_122",
        "files",
        "01-122-ejercicio-2016-y-siguientes.xlsx",
    )
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == declaration.source_sha256
    workbook = load_workbook(source_path, read_only=True, data_only=True)
    try:
        sheet = workbook[declaration.sheet]
        assert sheet[declaration.note_source_cell].value == declaration.note_statement
        assert sheet["G11"].value == declaration.published_pointer
    finally:
        workbook.close()
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    derivation = next(x for x in rendered.field_derivations if x.parser_field.source_cell == "A11")
    assert derivation.field.literal == "I" and derivation.field.length == 1
    assert derivation.derivation_code == "literal-note-exact-v1"
    period = next(x.field for x in rendered.field_derivations if x.parser_field.source_cell == "A16")
    assert period.literal == "0A"
    closer = inputs.joined.variable_envelopes[0].closing
    assert isinstance(closer, RecordDesignIntermediateRelativeSuffixMarker)
    assert closer.content == '"</T1220EEEE0A0000>"'
    assert rendered.layout.filing_envelope is not None
    contract = rendered.provenance_manifest.variable_envelope_contract
    assert contract is not None and len(contract.envelope.prefix_fields) == 13


@pytest.mark.parametrize(
    "closer, error",
    [
        ('"</T1220????0A0000>"', "official </T"),
        ('"</T1230EEEE0A0000>"', "names modelo"),
        ('"</T1221EEEE0A0000>"', "carries discriminant"),
    ],
)
def test_official_year_placeholder_does_not_relax_other_envelope_facts(
    inputs: RevisionRenderInputs, tmp_path: Path, closer: str, error: str
) -> None:
    envelope = inputs.joined.variable_envelopes[0]
    contract = inputs.joined.variable_envelope_contract
    assert contract is not None
    changed_envelope = envelope.model_copy(update={"closing": envelope.closing.model_copy(update={"content": closer})})
    changed = inputs.joined.model_copy(
        update={
            "variable_envelopes": (changed_envelope,),
            "variable_envelope_contract": contract.model_copy(update={"parser_envelope": changed_envelope}),
        }
    )
    with pytest.raises(RegistryValidationError, match=error):
        render_complete_export_tree(
            tmp_path / "export",
            revision_id=inputs.revision_id,
            joined=changed,
            semantic_map=inputs.semantic_map,
            transport_profile=inputs.transport_profile,
            render_profile=inputs.render_profile,
            render_profile_source_evidence=inputs.render_profile_source_evidence,
        )


@pytest.mark.parametrize("content", ['Constante "<T" o "<Z"', 'Constante "<T" si procede'])
def test_envelope_constant_label_does_not_admit_alternatives_or_conditions(
    inputs: RevisionRenderInputs, tmp_path: Path, content: str
) -> None:
    envelope = inputs.joined.variable_envelopes[0]
    contract = inputs.joined.variable_envelope_contract
    assert contract is not None
    prefix = (envelope.prefix_fields[0].model_copy(update={"content": content}), *envelope.prefix_fields[1:])
    changed_envelope = envelope.model_copy(update={"prefix_fields": prefix})
    changed = inputs.joined.model_copy(
        update={
            "variable_envelopes": (changed_envelope,),
            "variable_envelope_contract": contract.model_copy(update={"parser_envelope": changed_envelope}),
        }
    )
    with pytest.raises(RegistryValidationError, match="conflicts with exact official content"):
        render_complete_export_tree(
            tmp_path / "export",
            revision_id=inputs.revision_id,
            joined=changed,
            semantic_map=inputs.semantic_map,
            transport_profile=inputs.transport_profile,
            render_profile=inputs.render_profile,
            render_profile_source_evidence=inputs.render_profile_source_evidence,
        )


@pytest.mark.parametrize(
    "statement",
    [
        "1. El tipo de declaración para la presentación puede ser: I (ingreso) o N (negativa)",
        "1. El tipo de declaración para la presentación puede ser: I (ingreso) si procede",
        "1. El tipo de declaración para la presentación puede ser: I (ingreso condicionado)",
    ],
)
def test_alternative_or_conditional_note_is_refused(inputs: RevisionRenderInputs, statement: str) -> None:
    declaration = note_literals_for(inputs.joined.source)[0]
    with pytest.raises(ValidationError, match="without alternatives or conditions"):
        NoteLiteralDeclaration.model_validate({**declaration.model_dump(), "note_statement": statement})


def test_reissued_source_does_not_inherit_a_note_reading(inputs: RevisionRenderInputs) -> None:
    source = inputs.joined.source.model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(RegistryValidationError, match="parser-read source SHA-256"):
        note_literals_for(source)


@pytest.mark.parametrize("references", [(), (2,), (1, 2)])
def test_missing_or_ambiguous_note_reference_is_not_resolved(
    inputs: RevisionRenderInputs,
    references: tuple[int, ...],
) -> None:
    assert (
        note_literal_for(
            note_literals_for(inputs.joined.source),
            sheet="Pag. 1",
            source_cell="A11",
            published_pointer="Ver nota 1",
            note_references=references,
        )
        is None
    )


@pytest.mark.parametrize(
    "change, error",
    [
        ({"literal": "J"}, "byte-for-byte"),
        ({"length": 2}, "official slot"),
        ({"content": "Ver nota 2"}, "ambiguous official constant"),
    ],
)
def test_note_reading_cannot_override_literal_geometry_or_another_pointer(
    inputs: RevisionRenderInputs,
    change: dict[str, object],
    error: str,
) -> None:
    original = next(x for x in inputs.joined.fields if x.parser_field.source_cell == "A11")
    field = original.model_copy(
        update={
            "semantic_entry": original.semantic_entry.model_copy(update=change)
            if "literal" in change
            else original.semantic_entry,
            "parser_field": original.parser_field.model_copy(update=change)
            if "literal" not in change
            else original.parser_field,
        }
    )
    with pytest.raises(RegistryValidationError, match=error):
        _literal_derivation(
            field,
            encoding=inputs.transport_profile.encoding,
            render_profile=inputs.render_profile,
            export_record_id=str(inputs.joined.records[0].semantic_record.export_record_id),
            literal_notes=note_literals_for(inputs.joined.source),
        )


def test_duplicate_reading_is_ambiguous(inputs: RevisionRenderInputs) -> None:
    declaration = note_literals_for(inputs.joined.source)[0]
    with pytest.raises(RegistryValidationError, match="multiple declarations"):
        note_literal_for(
            (declaration, declaration),
            sheet="Pag. 1",
            source_cell="A11",
            published_pointer="Ver nota 1",
            note_references=(1,),
        )
