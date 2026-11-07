"""Export tree manifest emission and renderer refusals."""

from __future__ import annotations

import ast
import inspect
from types import ModuleType
from typing import TypedDict, get_args

import pytest

from cadrumo.core.directory_scan import (
    scan_directory,
)
from cadrumo.domain.calculations.registry.errors import (
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy

from ...compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ...compiler.loader import load_modelo_directory
from .. import export_field_derivation, export_tree
from .. import export_tree_serialization as serialization
from ..export_field_literal_derivation import OFFICIAL_QUOTE_FOLD
from ..export_field_numeric_derivation import numeric_derivation
from ..export_field_render_profile_derivation import WIDTH_17_SIGNED_POLICY, WIDTH_17_UNSIGNED_POLICY
from ..export_fragment_provenance import (
    ExportFragmentTarget,
    emit_export_fragment_provenance_manifest,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
    write_canonical_manifest_atomically,
)
from ..export_tree import render_complete_export_tree
from ..joined_record_design import JoinedRecordDesignField, join_record_design_semantics
from ..render_profile_rules import Width17MembershipRule
from .export_tree_support import (
    DESIGN_EPOCH,
    SHELL_REVISION,
    blank_integer_profile,
    export_tree_intermediate,
    export_tree_joined,
    export_tree_profile,
    export_tree_semantic_map,
    m130_inspection,
    oversized_authorities,
    synthetic_static_inspection,
    wire_evidence,
    wire_profile,
    write_modelo_shell,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_direct_manifest_emission_and_real_loader_verification(tmp_path) -> None:
    """The public provenance-manifest emitter and verifier operate on a real fresh tree only."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    semantic_map = export_tree_semantic_map()
    joined = export_tree_joined(m130_inspection())
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id=SHELL_REVISION,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )
    layout = load_modelo_directory(tmp_path / "modelos" / "130").revisions[SHELL_REVISION].export_layouts[0]
    manifest_path = revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    manifest_path.unlink()

    emitted = emit_export_fragment_provenance_manifest(
        joined=joined,
        semantic_map=semantic_map,
        target=ExportFragmentTarget(modelo="130", revision_id=SHELL_REVISION, design_epoch=DESIGN_EPOCH),
        loaded_layout=layout,
        export_root=revision_dir / "export",
        field_derivations=rendered.field_derivations,
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert load_export_fragment_provenance_manifest(manifest_path.read_bytes()) == emitted
    assert (
        verify_export_fragment_provenance_manifest(
            export_root=revision_dir / "export",
            joined=joined,
            semantic_map=semantic_map,
            target=ExportFragmentTarget(modelo="130", revision_id=SHELL_REVISION, design_epoch=DESIGN_EPOCH),
            loaded_layout=layout,
            field_derivations=rendered.field_derivations,
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )
        == emitted
    )


def test_manifest_writer_refuses_a_target_that_already_exists(tmp_path) -> None:
    """Pin the refusal this writer delegates to its publish-once primitive.

    The development-owned primitive publishes with :func:`os.link`, which fails
    with :exc:`FileExistsError` in one uninterruptible step rather than
    overwriting. This test pins this boundary's registry-error translation.

    The first write is the positive control -- without it a refusal that fired
    unconditionally, or a writer that never wrote at all, would pass too.
    """
    target = tmp_path / EXPORT_FRAGMENT_PROVENANCE_FILENAME

    write_canonical_manifest_atomically(target, b'{"first": true}')
    assert target.read_bytes() == b'{"first": true}'

    with pytest.raises(RegistryValidationError, match="already exists"):
        write_canonical_manifest_atomically(target, b'{"second": true}')

    assert target.read_bytes() == b'{"first": true}', "the refused write must not have replaced the target"
    assert scan_directory(tmp_path) == (target,), "the refused write must not leave its staging tempfile behind"


def test_renderer_refuses_mismatched_map_without_emitting_a_manifest(tmp_path) -> None:
    """Manifest emission never leaves a partial sibling attestation when map authority drifts."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    semantic_map = export_tree_semantic_map()
    mismatched_map = semantic_map.model_copy(
        update={
            "entries": (
                semantic_map.entries[0].model_copy(update={"literal": "XX"}),
                *semantic_map.entries[1:],
            ),
        },
    )

    with pytest.raises(RegistryValidationError, match="joined fields do not attest"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=mismatched_map,
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="semantic-map SHA-256 does not match joined official source"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=semantic_map.model_copy(update={"source_sha256": "b" * 64}),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_refuses_semantic_map_source_and_incomplete_entries_without_emitting_a_manifest(
    tmp_path,
) -> None:
    """The remaining two semantic-map attestation comparisons must each refuse on their own
    terms rather than inherit coverage from the coarse whole-map and SHA-256 siblings pinned
    above: a source-ref drift on the map argument, and an entries set that no longer bijects
    the compiled map once the joined design itself carries a duplicated field."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    semantic_map = export_tree_semantic_map()

    with pytest.raises(RegistryValidationError, match=r"semantic-map source .+ does not match joined source"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=semantic_map.model_copy(update={"source_ref": "aeat-dr-130-2019-v13"}),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    # The coarse whole-map equality check above intercepts every semantic_map
    # argument that merely differs from what the join used, so the
    # entries-completeness comparison can only be reached by keeping that
    # argument identical to the join's own authored map and instead corrupting
    # the JOINED design: one already-joined field duplicated so its flattened
    # entry set no longer bijects the compiled map's entries.
    joined = export_tree_joined(m130_inspection())
    joined_with_duplicated_field = joined.model_copy(update={"fields": (*joined.fields, joined.fields[0])})

    with pytest.raises(
        RegistryValidationError,
        match="joined fields do not attest the supplied complete semantic map",
    ):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=joined_with_duplicated_field,
            semantic_map=semantic_map,
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_tolerates_reordered_joined_fields_without_tripping_the_entries_gate(
    tmp_path,
) -> None:
    """Sibling-blindness for the entries-completeness gate above: it compares the joined
    fields' entries as a SET against the compiled map's entries, so reordering those fields
    without dropping or duplicating any of them must still render cleanly. A gate that fired
    on any change to field order, rather than genuine incompleteness, would not have proven
    the completeness comparison the prior test exercises."""
    joined = export_tree_joined(m130_inspection())
    reordered_fields = (joined.fields[1], joined.fields[0], *joined.fields[2:])
    reordered_joined = joined.model_copy(update={"fields": reordered_fields})

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=SHELL_REVISION,
        joined=reordered_joined,
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert rendered.output_files


def test_renderer_refuses_incomplete_joined_records_without_emitting_a_manifest(
    tmp_path,
) -> None:
    """The records-completeness comparison is the fifth attestation raise and, unlike the
    entries duplication above, a literal duplicated record collides with the renderer's own
    duplicate-output-id refusal before this comparison is ever reached (proven: duplicating
    ``joined.records[0]`` raises "generated export tree has duplicate record id", not this
    comparison's message, because a shared ``semantic_record`` always shares its rendered
    export_record_id). Dropping a record from the joined design instead -- so the joined set
    is a proper subset of the compiled map's records, with no id collision -- reaches the
    comparison this raise site actually guards."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    joined = export_tree_joined(m130_inspection())
    joined_missing_a_record = joined.model_copy(update={"records": joined.records[:1]})

    with pytest.raises(
        RegistryValidationError,
        match="joined records do not attest the supplied complete semantic map",
    ):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=joined_missing_a_record,
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_tolerates_reordered_joined_records_without_tripping_the_records_gate(
    tmp_path,
) -> None:
    """Sibling-blindness for the records-completeness gate above: it compares joined records
    as a SET against the compiled map's records, so reordering them without dropping or
    duplicating any must still render cleanly."""
    joined = export_tree_joined(m130_inspection())
    reordered_records = (joined.records[1], joined.records[0])
    reordered_joined = joined.model_copy(update={"records": reordered_records})

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=SHELL_REVISION,
        joined=reordered_joined,
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert rendered.output_files


def test_renderer_refuses_transport_profile_identity_axes_without_emitting_a_manifest(
    tmp_path,
) -> None:
    """The transport profile's modelo, design-epoch, source-ref, and serializer-convention
    comparisons must each refuse on their own terms: the sibling SHA-256 comparison already
    pinned in ``test_renderer_refuses_mismatched_map_without_emitting_a_manifest`` proves only
    that one axis, and two differently-named parametrize labels that both mutate the SHA-256
    field would leave these other four axes silently undriven."""
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    profile = export_tree_profile()

    with pytest.raises(RegistryValidationError, match="export tree transport profile modelo"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            transport_profile=profile.model_copy(update={"modelo": "184"}),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="export tree transport profile design epoch"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            transport_profile=profile.model_copy(update={"design_epoch": str(int(DESIGN_EPOCH) + 1)}),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="export tree transport profile source "):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            transport_profile=profile.model_copy(update={"source_ref": "aeat-dr-130-2019-v13"}),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    with pytest.raises(RegistryValidationError, match="export tree transport profile serializer"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection()),
            semantic_map=export_tree_semantic_map(),
            transport_profile=profile.model_copy(update={"serializer_convention": "unsupported-convention"}),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).exists()


def test_renderer_tolerates_transport_profile_line_ending_drift(tmp_path) -> None:
    """Sibling-blindness for the transport-profile identity gate above: it compares five
    named axes (modelo, design epoch, source ref, source digest, serializer convention), not
    the profile as a whole, so a drifted line_ending -- not one of those axes -- must reach a
    normal render rather than tripping any of the four gates just pinned."""
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=SHELL_REVISION,
        joined=export_tree_joined(m130_inspection()),
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile().model_copy(update={"line_ending": "lf"}),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert rendered.output_files


def test_renderer_refuses_uncovered_blank_numeric_anchor_without_emitting_a_partial_fragment(
    tmp_path,
) -> None:
    """A blank numeric field needs its exact reviewed profile rule before output."""
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="must cover exactly the eligible blank numeric fields"):
        render_complete_export_tree(
            target,
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection(), numeric_content=None),
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not target.exists()


def test_renderer_resolves_one_blank_numeric_field_only_through_its_exact_profile_anchor(
    tmp_path,
) -> None:
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    joined = export_tree_joined(m130_inspection(), numeric_content=None)
    profile = blank_integer_profile()

    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id=SHELL_REVISION,
        joined=joined,
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=profile,
        render_profile_source_evidence=wire_evidence(),
    )
    loaded = load_modelo_directory(tmp_path / "modelos" / "130").revisions[SHELL_REVISION].export_layouts[0]
    derived = rendered.field_derivations[-1]

    assert loaded == rendered.layout
    assert derived.derivation_code == "render-profile-singleton-v1"
    assert derived.field.value_policy == "unsigned-integer"
    assert derived.field.data_type == "integer"
    assert derived.field.length == 4
    assert rendered.provenance_manifest.render_profile_sha256 != "0" * 64


class _IntermediateKwargs(TypedDict, total=False):
    first_record_declared_total: int | None
    first_field_offset: int
    second_field_offset: int
    numeric_content: str | None


@pytest.mark.parametrize(
    ("intermediate_kwargs", "error"),
    (
        ({"first_record_declared_total": None}, "no declared total"),
        ({"first_field_offset": 2}, "expected offset 1, got 2"),
        ({"second_field_offset": 4, "first_record_declared_total": 5}, "has a gap"),
        ({"second_field_offset": 2, "first_record_declared_total": 3}, "has an overlap"),
        ({"first_record_declared_total": 5}, "declares total 5, but parsed fields end at 4"),
    ),
)
def test_renderer_refuses_missing_or_noncontiguous_official_record_geometry(
    tmp_path,
    intermediate_kwargs: _IntermediateKwargs,
    error: str,
) -> None:
    """No inferred total, first position, gap, overlap, or terminal extent may be emitted."""
    target = tmp_path / "export"
    joined = join_record_design_semantics(
        export_tree_semantic_map(),
        export_tree_intermediate(**intermediate_kwargs),
        m130_inspection(),
    )

    with pytest.raises(RegistryValidationError, match=error):
        render_complete_export_tree(
            target,
            revision_id=SHELL_REVISION,
            joined=joined,
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not target.exists()


def test_renderer_refuses_unstructured_quoted_numeric_prose(tmp_path) -> None:
    """Quoted digits form an enum only under the reviewed comma-delimited source grammar."""
    target = tmp_path / "export"
    joined = export_tree_joined(
        m130_inspection(),
        # Four digits each, matching the declared slot width, so the ambiguity
        # refusal is reached rather than the slot-width refusal.
        numeric_content='"0000" only if the taxpayer elects "0050"',
    )

    with pytest.raises(RegistryValidationError, match="ambiguous content"):
        render_complete_export_tree(
            target,
            revision_id=SHELL_REVISION,
            joined=joined,
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not target.exists()


def test_note_governed_numeric_enumeration_retains_the_period_specific_closed_domain() -> None:
    """The official Nota 8/9 form adds ``0`` without opening the enum.

    The annotation is the mutation: without the paired notes the two printed
    values remain the complete closed enum; with the pair, ``0`` is a required
    period-reserved wire token in addition to the printed Yes/No values.
    """
    annotated = (
        export_tree_joined(
            synthetic_static_inspection(),
            numeric_content='"0001" SI, "0002" NO. Nota 8. Nota 9',
        )
        .records[1]
        .fields[1]
    )
    unannotated = (
        export_tree_joined(
            synthetic_static_inspection(),
            numeric_content='"0001" SI, "0002" NO',
        )
        .records[1]
        .fields[1]
    )
    incomplete_note_pair = (
        export_tree_joined(
            synthetic_static_inspection(),
            numeric_content='"0001" SI, "0002" NO. Nota 8',
        )
        .records[1]
        .fields[1]
    )

    annotated_derivation = numeric_derivation(
        annotated,
        export_record_id="generated-record-type-2",
    )
    unannotated_derivation = numeric_derivation(
        unannotated,
        export_record_id="generated-record-type-2",
    )
    incomplete_note_pair_derivation = numeric_derivation(
        incomplete_note_pair,
        export_record_id="generated-record-type-2",
    )

    assert annotated_derivation.field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS
    assert annotated_derivation.field.allowed_values == ("0", "1", "2")
    assert annotated_derivation.derivation_code == "numeric-enumeration-v1"
    assert unannotated_derivation.field.value_policy is ExportValuePolicy.ENUMERATED_DIGITS
    assert unannotated_derivation.field.allowed_values == ("1", "2")
    assert incomplete_note_pair_derivation.field.allowed_values == ("1", "2")


def test_renderer_refuses_profile_hash_drift_literal_extent_and_nonempty_target(tmp_path) -> None:
    """The renderer rejects unsafe authority mismatches and never overwrites a prior output."""
    joined = export_tree_joined(m130_inspection())
    with pytest.raises(RegistryValidationError, match="SHA-256"):
        render_complete_export_tree(
            tmp_path / "export",
            revision_id=SHELL_REVISION,
            joined=joined,
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile().model_copy(update={"source_sha256": "b" * 64}),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    literal_map = export_tree_semantic_map().model_copy(
        update={
            "entries": (
                export_tree_semantic_map().entries[0].model_copy(update={"literal": "TOO LONG"}),
                *export_tree_semantic_map().entries[1:],
            ),
        },
    )
    intermediate = export_tree_intermediate()
    first_sheet = intermediate.sheets[0]
    oversized_literal = first_sheet.fields[0].model_copy(update={"content": 'Constante "TOO LONG"'})
    intermediate = intermediate.model_copy(
        update={
            "sheets": (
                first_sheet.model_copy(update={"fields": (oversized_literal, *first_sheet.fields[1:])}),
                *intermediate.sheets[1:],
            ),
        },
    )
    with pytest.raises(RegistryValidationError, match="encoded bytes"):
        render_complete_export_tree(
            tmp_path / "second" / "export",
            revision_id=SHELL_REVISION,
            joined=join_record_design_semantics(literal_map, intermediate, m130_inspection()),
            semantic_map=literal_map,
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )
    assert not (tmp_path / "second" / "export").exists()

    occupied = tmp_path / "occupied" / "export"
    occupied.mkdir(parents=True)
    (occupied / "foreign.toml").write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="not empty"):
        render_complete_export_tree(
            occupied,
            revision_id=SHELL_REVISION,
            joined=joined,
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )


@pytest.mark.parametrize(
    "official_content",
    (
        None,
        'Constante "<T" o "ZZ"',
        'Constante "<T". o "ZZ"',
        'Constante "E". o "S". rentas.',
        'Constante "E". rentas.\no "S".',
        'Constante "<T',
    ),
)
def test_renderer_refuses_missing_or_ambiguous_official_literal_without_output(
    tmp_path,
    official_content: str | None,
) -> None:
    """Literal meaning never substitutes for absent or ambiguous official constant bytes."""
    intermediate = export_tree_intermediate()
    first_sheet = intermediate.sheets[0]
    first_field = first_sheet.fields[0].model_copy(update={"content": official_content})
    intermediate = intermediate.model_copy(
        update={
            "sheets": (
                first_sheet.model_copy(update={"fields": (first_field, *first_sheet.fields[1:])}),
                *intermediate.sheets[1:],
            ),
        },
    )
    semantic_map = export_tree_semantic_map()
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="official constant"):
        render_complete_export_tree(
            target,
            revision_id=SHELL_REVISION,
            joined=join_record_design_semantics(semantic_map, intermediate, m130_inspection()),
            semantic_map=semantic_map,
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not target.exists()


def _intermediate_with_first_content(content: str, *, in_contenido_column: bool):
    intermediate = export_tree_intermediate()
    first_sheet = intermediate.sheets[0]
    first_field = first_sheet.fields[0].model_copy(
        update={"content": content, "content_in_contenido_column": in_contenido_column},
    )
    return intermediate.model_copy(
        update={
            "sheets": (
                first_sheet.model_copy(update={"fields": (first_field, *first_sheet.fields[1:])}),
                *intermediate.sheets[1:],
            ),
        },
    )


def test_bare_constant_is_the_literal_only_when_it_fills_the_printed_contenido_column(tmp_path) -> None:
    """A lone unlabelled token states the constant when the reader located it in the Contenido cell."""
    semantic_map = export_tree_semantic_map()
    tree = render_complete_export_tree(
        write_modelo_shell(tmp_path / "modelos" / "130") / "export",
        revision_id=SHELL_REVISION,
        joined=join_record_design_semantics(
            semantic_map,
            _intermediate_with_first_content("<T", in_contenido_column=True),
            m130_inspection(),
        ),
        semantic_map=semantic_map,
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    assert tree.field_derivations[0].derivation_code == "literal-exact-v1"


@pytest.mark.parametrize("official_content", ("<T", '"<T" "ZZ"', "<T ZZ"))
def test_bare_constant_not_proven_in_the_contenido_column_is_refused(tmp_path, official_content: str) -> None:
    """The same token as text merely attributed to the field, or a multi-token cell, is no constant."""
    in_column = official_content != "<T"
    semantic_map = export_tree_semantic_map()
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="ambiguous official constant"):
        render_complete_export_tree(
            target,
            revision_id=SHELL_REVISION,
            joined=join_record_design_semantics(
                semantic_map,
                _intermediate_with_first_content(official_content, in_contenido_column=in_column),
                m130_inspection(),
            ),
            semantic_map=semantic_map,
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not target.exists()


def test_labelled_official_literal_accepts_the_m184_sentence_stop_but_not_an_alternative() -> None:
    """M184 2025 prints the constant before a merged explanatory sentence."""
    labelled = export_field_derivation.OFFICIAL_LABELLED_LITERAL_RE.fullmatch(
        'Constante "E". rentas. Declaración anual.',
    )

    assert labelled is not None
    assert labelled.group("literal") == "E"
    assert (
        export_field_derivation.OFFICIAL_ALTERNATIVE_LITERALS_RE.fullmatch('Constante "E". o "S". rentas.') is not None
    )
    assert (
        export_field_derivation.OFFICIAL_ALTERNATIVE_LITERALS_RE.fullmatch('Constante "E". rentas.\no "S".') is not None
    )


def test_labelled_official_literal_accepts_m296_field_enumeration_after_the_constant() -> None:
    """M296's later quoted 1/2 values describe another field, not tipo-hoja."""
    official_content = (
        "Constante «F» ANEXO «VALORES NEGOCIABLES. RELACIÓN DE PAGO A CONTRIBUYENTES» "
        'Sólo para claves de percepción "1" ó "2" (posiciones 100-101 del tipo de registro 2).'
    )
    folded = official_content.translate(OFFICIAL_QUOTE_FOLD)

    assert export_field_derivation.OFFICIAL_ALTERNATIVE_LITERALS_RE.fullmatch(folded) is None
    labelled = export_field_derivation.OFFICIAL_LABELLED_LITERAL_RE.fullmatch(folded)
    assert labelled is not None
    assert labelled.group("literal") == "F"


def test_renderer_refuses_wrong_same_width_literal_without_output(tmp_path) -> None:
    """A reviewed literal with the right width still cannot override different official bytes."""
    semantic_map = export_tree_semantic_map().model_copy(
        update={
            "entries": (
                export_tree_semantic_map().entries[0].model_copy(update={"literal": "ZZ"}),
                *export_tree_semantic_map().entries[1:],
            ),
        },
    )
    target = tmp_path / "export"

    with pytest.raises(RegistryValidationError, match="byte-for-byte"):
        render_complete_export_tree(
            target,
            revision_id=SHELL_REVISION,
            joined=join_record_design_semantics(semantic_map, export_tree_intermediate(), m130_inspection()),
            semantic_map=semantic_map,
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )

    assert not target.exists()


def test_renderer_partitions_oversized_record_deterministically_and_loader_merges_exactly(
    tmp_path,
) -> None:
    """A real-shaped 245-field record stays reviewable and roundtrips exactly once in source order."""
    semantic_map, joined = oversized_authorities(m130_inspection())
    first_revision = write_modelo_shell(tmp_path / "first" / "modelos" / "130")
    second_revision = write_modelo_shell(tmp_path / "second" / "modelos" / "130")
    first = render_complete_export_tree(
        first_revision / "export",
        revision_id=SHELL_REVISION,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )
    second = render_complete_export_tree(
        second_revision / "export",
        revision_id=SHELL_REVISION,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )
    compact_map, compact_joined = oversized_authorities(m130_inspection(), field_count=20)
    compact_revision = write_modelo_shell(tmp_path / "compact" / "modelos" / "130")
    compact = render_complete_export_tree(
        compact_revision / "export",
        revision_id=SHELL_REVISION,
        joined=compact_joined,
        semantic_map=compact_map,
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    oversized_parts = tuple(
        path for path in first.output_files if path.endswith("-record-generated-oversized-record.toml")
    )
    compact_parts = tuple(
        path for path in compact.output_files if path.endswith("-record-generated-oversized-record.toml")
    )
    assert len(oversized_parts) > 1
    # Each part takes its own administrative prefix, numbered consecutively from 0001,
    # because the loader admits exactly one fragment per prefix.
    assert oversized_parts == tuple(
        f"{prefix:04d}-record-generated-oversized-record.toml" for prefix in range(1, len(oversized_parts) + 1)
    )
    assert len(oversized_parts) > len(compact_parts)
    assert compact_parts[0] == oversized_parts[0]
    # The trailing record follows the oversized record's last part rather than colliding
    # with it, so its prefix moves as the partition count grows.
    assert first.output_files[-1] == f"{len(oversized_parts) + 1:04d}-record-generated-trailing-record.toml"
    assert compact.output_files[-1] == f"{len(compact_parts) + 1:04d}-record-generated-trailing-record.toml"
    assert first.output_files[-1] != compact.output_files[-1]
    assert first.output_files == second.output_files
    assert len(set(first.output_files)) == len(first.output_files)
    assert [path.split("-", 1)[0] for path in first.output_files] == sorted(
        path.split("-", 1)[0] for path in first.output_files
    )
    assert {path.name: path.read_bytes() for path in scan_directory(first_revision / "export")} == {
        path.name: path.read_bytes() for path in scan_directory(second_revision / "export")
    }
    for relative_path in first.output_files:
        lines = (first_revision / "export" / relative_path).read_text(encoding="utf-8").splitlines()
        assert len(lines) < 1_400
        assert max(map(len, lines), default=0) < 520

    loaded_layout = (
        load_modelo_directory(tmp_path / "first" / "modelos" / "130").revisions[SHELL_REVISION].export_layouts[0]
    )
    assert loaded_layout == first.layout
    emitted_ids = tuple(str(field.id) for field in loaded_layout.records[0].fields)
    assert emitted_ids == tuple(f"generated.oversized.field-{index:03d}" for index in range(1, 246))
    assert len(emitted_ids) == len(set(emitted_ids)) == 245


def test_renderer_refuses_a_fragment_prefix_that_overflows_its_padded_width() -> None:
    """An overflowed prefix is refused at render rather than emitted as an unreadable name.

    Reaching this by rendering would need ten thousand fragments, so the naming
    function is exercised directly. The last in-width prefix must still render, or
    the guard would be refusing legitimate output one short of the boundary.
    """
    width = serialization.FRAGMENT_PREFIX_DIGITS
    last_in_width = 10**width - 1

    assert (
        serialization.record_relative_path(last_in_width, "generated-record")
        == f"{last_in_width}-record-generated-record.toml"
    )

    with pytest.raises(RegistryValidationError, match="overflows"):
        serialization.record_relative_path(last_in_width + 1, "generated-record")


def _code_only_source(module: ModuleType) -> str:
    """Return a module's source with comments and string literals removed.

    Uses the tokeniser rather than a regex so an apostrophe or a `#` inside a
    string cannot desynchronise the scan.
    """
    import io
    import tokenize

    text = inspect.getsource(module)
    kept: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type in {tokenize.COMMENT, tokenize.STRING}:
            continue
        kept.append(token.string)
    return " ".join(kept)


def test_renderer_module_has_no_old_tree_or_approximate_admission_surface() -> None:
    """The renderer must fail closed instead of importing an older output as guidance."""
    module = ast.parse(inspect.getsource(export_tree))
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name for node in ast.walk(module) if isinstance(node, ast.Import) for alias in node.names
    )
    # Scanned with COMMENTS AND DOCSTRINGS STRIPPED. The forbidden tokens name a
    # surface the renderer must not have, not a word it must not say: the module
    # explains in a comment why it refuses "a fuzzy match", and a raw substring
    # scan read that explanation as the defect it warns against. Stripping prose
    # keeps the tokens meaningful -- an actual `shutil` import or `read_text`
    # call is still caught, because those survive tokenisation as code.
    source = _code_only_source(export_tree).casefold()

    assert "resolve_export_layout" not in referenced_names
    assert "bundled_authority" not in referenced_names
    assert "cadrumo.domain.calculations.registry.export" not in imported_modules
    for forbidden in (
        "fallback",
        "fuzzy",
        "legacy",
        "copytree",
        "shutil",
        "rglob",
        ".extracted",
        "read_text",
    ):
        assert forbidden not in source


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # The two spellings AEAT actually ships for one closed value set.
        ("1 - Sí  2 - No", ("1", "2")),
        ("1 -Sí, 2 -No", ("1", "2")),
        ("3 -Mensual, 6 -Trimestral, 12 -Anual", ("3", "6", "12")),
        # A RANGE states an interval, not a set. Reading "01-12" as two members
        # would emit an enumeration of {1, 12} and silently refuse every month
        # between them, so the separator refuses a digit on its right.
        ("01-12", ()),
        ("Periodos 01-12 del ejercicio", ()),
        # A single dash-labelled value is not enough to call it an enumeration;
        # the caller requires more than one member before taking this reading.
        ("1 - Sí", ("1",)),
    ],
)
def test_dash_numeric_enumeration_reads_labels_and_refuses_ranges(
    content: str,
    expected: tuple[str, ...],
) -> None:
    """The dash-enumeration reader admits AEAT's label spellings, never a range."""
    values = tuple(
        match.group("value") for match in export_field_derivation.DASH_NUMERIC_ENUMERATION_TOKEN_RE.finditer(content)
    )

    assert values == expected


def test_bare_record_tag_is_recognised_without_a_constante_label() -> None:
    """A record's own identifier is readable even when printed unlabelled.

    Modelo 353 prints `</T35301000>` with neither the `Constante` label nor
    quotes its own opening tag carries; Modelo 322 prints BOTH ends bare. The
    pattern keys on the tag's SHAPE, so admitting them cannot turn an arbitrary
    unlabelled cell into a mandated literal.
    """
    matcher = export_field_derivation.OFFICIAL_BARE_RECORD_TAG_RE

    assert matcher.fullmatch("</T35301000>") is not None
    assert matcher.fullmatch("<T32201000>") is not None
    assert matcher.fullmatch("</T303DID>") is not None
    assert matcher.fullmatch("blanco o 'C' (compl.)") is None
    assert matcher.fullmatch("BLANCOS") is None
    assert matcher.fullmatch("15 enteros + 2 decimales") is None


def test_width_17_sign_policies_cover_every_declared_policy() -> None:
    """The signed/unsigned pair must be the whole policy set the model admits.

    ``_profile_width_17_derivation`` coerces ``sign_policy`` to a boolean, and that
    boolean picks ``data_type`` (money vs decimal), ``signed``, and whether the
    rule's scale is emitted at all. A policy admitted by the model but unknown to
    that coercion therefore renders as an unsigned decimal with a scale -- wrong in
    all three -- and nothing refuses, because the comparison simply evaluates
    false. Adding a policy must break here rather than in a filed amount.
    """
    declared = set(get_args(Width17MembershipRule.model_fields["sign_policy"].annotation))
    handled = {WIDTH_17_SIGNED_POLICY, WIDTH_17_UNSIGNED_POLICY}
    assert handled == declared, (
        f"width-17 sign policies handled by the derivation {sorted(handled)} do not match the "
        f"declared set {sorted(declared)}; an unhandled policy renders as unsigned decimal"
    )


@pytest.mark.parametrize(
    ("aeat_type", "expected_code"),
    [
        ("A", "text-a-v1"),
        ("Alfabético", "text-a-v1"),
        ("Alfabetico", "text-a-v1"),
        ("An", "text-an-v1"),
        ("Alfanumérico", "text-an-v1"),
        ("Alfanumerico", "text-an-v1"),
    ],
)
def test_every_spelling_of_a_text_naturaleza_reaches_its_own_derivation_code(
    tmp_path,
    aeat_type: str,
    expected_code: str,
) -> None:
    """A naturaleza must derive from what it names, not from which vocabulary named it.

    AEAT states the same two text naturalezas in two vocabularies: a workbook
    prints the abbreviation, and a PDF design prints the word the shipped parser
    canonicalises to ``Alfabético``/``Alfanumérico``. Both spellings of
    *alfabético* have to reach the alphabetic derivation. Keying the choice on
    the abbreviation alone silently records every PDF-sourced alphabetic field as
    the ALPHANUMERIC derivation, and nothing refuses, because the folded word is
    simply not the abbreviation.
    """
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")
    rendered = render_complete_export_tree(
        revision_dir / "export",
        revision_id=SHELL_REVISION,
        joined=export_tree_joined(m130_inspection(), second_field_aeat_type=aeat_type),
        semantic_map=export_tree_semantic_map(),
        transport_profile=export_tree_profile(),
        render_profile=wire_profile(),
        render_profile_source_evidence=wire_evidence(),
    )

    codes = {str(derivation.field.id): derivation.derivation_code for derivation in rendered.field_derivations}
    text_field = next(field_id for field_id in codes if codes[field_id] in {"text-a-v1", "text-an-v1"})
    assert codes[text_field] == expected_code


def test_a_blank_run_naturaleza_the_semantic_map_calls_value_bearing_is_refused(
    tmp_path,
) -> None:
    """``Blancos`` states no text representation, so deriving one is a guess.

    A blank run is a fill, and the semantic map already routes a declared filler
    to its own derivation before any naturaleza is read. Reaching this branch
    means the design says "blanks" while the map says the field carries a value:
    the two disagree, and the honest answer is a refusal naming the field, not a
    text derivation invented for it.
    """
    revision_dir = write_modelo_shell(tmp_path / "modelos" / "130")

    with pytest.raises(RegistryValidationError, match="blank-run naturaleza"):
        render_complete_export_tree(
            revision_dir / "export",
            revision_id=SHELL_REVISION,
            joined=export_tree_joined(m130_inspection(), second_field_aeat_type="Blancos"),
            semantic_map=export_tree_semantic_map(),
            transport_profile=export_tree_profile(),
            render_profile=wire_profile(),
            render_profile_source_evidence=wire_evidence(),
        )


def _joined_field_with_aeat_type(aeat_type: str) -> JoinedRecordDesignField:
    """Return a parser-owned field from the hermetic joined-design fixture."""
    joined = export_tree_joined(synthetic_static_inspection(), second_field_aeat_type=aeat_type)
    return next(field for field in joined.fields if field.parser_field.aeat_type == aeat_type)


@pytest.mark.unit
def test_an_unsigned_official_type_derives_an_unsigned_slot() -> None:
    """`Num` is numerico SIN signo, and it must still render without refusal."""
    from ..export_field_numeric_derivation import derive_sign_from_official_type

    unsigned = _joined_field_with_aeat_type("Num")

    assert derive_sign_from_official_type(unsigned) is False


@pytest.mark.unit
def test_a_signed_official_type_derives_a_signed_slot() -> None:
    """`N` is numerico CON signo, and its representation is now grounded.

    AEAT's "Disenos de registro" manual states the convention for every design:
    numeric fields are right-aligned and zero-filled SIN SIGNOS, and only
    NEGATIVE amounts are preceded by the character ``N``. So a signed slot
    reserves no byte -- the marker displaces the leading digit when the value is
    negative -- and the derivation reads that grounding rather than refusing.
    """
    from ..export_field_numeric_derivation import derive_sign_from_official_type

    signed = _joined_field_with_aeat_type("N")

    assert derive_sign_from_official_type(signed) is True


def test_requirement_reading_sets_aside_sentence_punctuation_but_not_a_qualifier() -> None:
    """Prove the punctuation repair lands and each wording is read as what it states.

    The defect was an exact-match comparison: ``OBLIGATORIO.`` fell through to
    ``False``, so twelve stated requirements in modelo 390 shipped as no
    requirement, defeated by a full stop. Sentence punctuation is now set
    aside.

    ``Obligatorio PI`` is unconditional: PI names the value list in modelo
    303's Nota 1, not a condition. ``OBLIGATORIO (persona fisica)`` is not
    unconditional; it is read as a requirement for natural persons only. A
    wording nobody has adjudicated is neither, and stays unclaimed.
    """
    from ..export_field_schema import is_required, qualified_requirement

    assert is_required(None) is False
    assert is_required("Obligatorio") is True
    assert is_required("OBLIGATORIO") is True
    assert is_required("  obligatorio  ") is True
    assert is_required("OBLIGATORIO.") is True
    assert is_required("Obligatorio PI") is True

    for qualified in ("OBLIGATORIO (persona fisica)", "Obligatorio si procede"):
        assert is_required(qualified) is False

    assert qualified_requirement("OBLIGATORIO (persona fisica)") == "natural_person"
    assert qualified_requirement("Obligatorio (persona física).") == "natural_person"
    assert qualified_requirement("Obligatorio si procede") is None
    assert qualified_requirement("OBLIGATORIO") is None


def test_an_obligatory_casilla_whose_contenido_admits_blank_keeps_a_blank_representation() -> None:
    """Read obligatoriness and an admitted blank together for casilla and computed text.

    DR145 row 2 is ``obligatorio`` with contenido ``blanco o "C" (compl.)``: the
    position is always written and blank is one of its two values. A layout
    ``required`` field has no blank representation, so the principal page's
    indicator could not be rendered at all. A contenido that names no blank keeps
    the field required, and a cell that is not obligatorio stays unrequired.
    """
    from ..export_field_schema import is_required_admitting_blank_text

    assert is_required_admitting_blank_text("obligatorio", 'blanco o "C" (compl.)') is False
    assert is_required_admitting_blank_text("Obligatorio", "C o blanco") is False
    assert is_required_admitting_blank_text("obligatorio", None) is True
    assert is_required_admitting_blank_text("obligatorio", '"C" (compl.)') is True
    assert is_required_admitting_blank_text("obligatorio", "Blanquear") is True
    assert is_required_admitting_blank_text(None, 'blanco o "C"') is False


@pytest.mark.parametrize(
    ("official_content", "expected"),
    (
        ('"<T840010>"', "<T840010>"),
        ("'</T840010>'", "</T840010>"),
        ("<T840010>", "<T840010>"),
        ('"576"', "576"),
    ),
)
def test_record_tag_printed_quoted_without_a_label_is_the_literal(official_content: str, expected: str) -> None:
    """Modelo 840 prints its opening tag quoted and unlabelled; the reader returns the bare token."""
    from dev.registry.pipeline.export_field_literal_derivation import _parse_official_literal

    field = _joined_field_with_aeat_type("Num")

    assert _parse_official_literal(field, official_content) == (expected, False)


@pytest.mark.parametrize(
    "official_content", ('"<T840010', '"<T840010>', '"<T840010>" o "<T840020>"', '"576" "ZZ"', '""', '"<T 840010>"')
)
def test_quoted_unlabelled_text_that_is_not_one_token_stays_refused(official_content: str) -> None:
    """Quotes alone make no constant: only a single complete quoted token is admitted."""
    from dev.registry.pipeline.export_field_literal_derivation import _parse_official_literal

    field = _joined_field_with_aeat_type("Num")

    with pytest.raises(RegistryValidationError, match="ambiguous official constant"):
        _parse_official_literal(field, official_content)
