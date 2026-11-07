from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Mapping
from pathlib import Path

import pytest
import rtoml

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind

from ..analysis import m200_semantic_casilla_candidates as subject
from ..analysis import m200_target_identity_worklist as identity_subject
from ..analysis.m200_record_design_support import record_design_field_index, record_design_source
from ..compiler.authority import compiled_bundled_authority
from ..conformance.modelo_200_echoes import MODELO_200_ECHO_CELLS
from ..pipeline.record_design_intermediate import RecordDesignIntermediateField, load_record_design_intermediate
from ..pipeline.semantic_map import SemanticMapEntry, load_semantic_map_for_revision, semantic_anchor_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# The earlier of the two editions the identity worklists cover; its cell ceiling below is that edition's.
_TARGET_REVISION = identity_subject.load_bundled_m200_target_identity_worklists()[0].revision
_SHARED_OWNER_CELL_CEILING = 2717


@pytest.fixture(scope="module")
def target_identity_inputs():
    authority = compiled_bundled_authority()
    target = authority.modelo("200").revisions[_TARGET_REVISION]
    sources = authority.catalogues.sources
    source_ref = record_design_source(target.source_refs, sources)
    epoch = sources[source_ref].record_design_epoch
    assert epoch is not None
    return (
        load_semantic_map_for_revision(Path("dev/registry/mappings/modelo_200") / epoch, target.id),
        load_record_design_intermediate(
            bundled_path(),
            sources,
            source_ref=source_ref,
            filing_year=target.valid_from.year,
            design_epoch=epoch,
        ),
        {declaration.id: declaration for declaration in target.casillas},
        {placement.casilla_id: placement.kind for layout in target.form_layouts for placement in layout.placements},
    )


def _classify(target_map, target_design, declarations, placements):
    return identity_subject.classify_m200_target_identities(
        target_map,
        target_design,
        revision_id=_TARGET_REVISION,
        target_declarations=declarations,
        target_candidate_ids=frozenset(),
        declared_placements=placements,
    )


@pytest.fixture(scope="module")
def target_identity_worklist(target_identity_inputs):
    return _classify(*target_identity_inputs)


def _candidate() -> subject.M200CasillaCandidate:
    return subject.M200CasillaCandidate(
        export_field_id="m200-2024.dp200018.f0172",
        authored_token=_CASILLA_588,
        disposition=subject.M200CasillaDisposition.SEGMENT_QUALIFIED_IDENTITY,
        reason="segment ownership cannot be inferred",
        source_ref="aeat-dr-200-2024",
        source_sha256="a" * 64,
        sibling_source_ref="aeat-dr-200-2025",
        sibling_source_sha256="b" * 64,
        sheet="DP200018",
        record_identity="DP200018",
        source_row=177,
        source_cell="A177",
        ordinal="172",
        offset=1,
        length=5,
        aeat_type="Num",
        label="[00588]",
        proposed_casilla_id="DP200014B:00588",
    )


_CASILLA_588 = "588"
_CASILLA_2971 = "2971"
_CASILLA_1683 = "1683"


def test_review_toml_is_deterministic_and_serializes_disposition() -> None:
    rendered = subject.render_m200_casilla_candidates_toml((_candidate(),))

    assert rendered == subject.render_m200_casilla_candidates_toml((_candidate(),))
    parsed = parse_toml(rendered)
    assert parsed["candidate"][0]["disposition"] == "segment_qualified_identity"
    assert "registry_data_type" not in rendered
    assert "legal_refs" not in rendered


def test_cli_stdout_exports_one_proposal_only_table_per_screened_revision(
    capsys,
    monkeypatch,
    target_identity_worklist,
) -> None:
    monkeypatch.setattr(
        identity_subject, "load_bundled_m200_target_identity_worklists", lambda: (target_identity_worklist,)
    )

    assert identity_subject.main([]) == 0
    document = rtoml.loads(capsys.readouterr().out)

    assert document["authority_status"] == "proposal_only"
    (table,) = document["revision_worklist"]
    assert table["revision"] == _TARGET_REVISION
    sections = {
        "map_owner_mismatches": "map_owner_mismatch",
        "orphaned_declarations": "orphaned_declaration",
        "printed_identity_diagnostics": "printed_identity_diagnostic",
        "shared_owners": "shared_owner",
    }
    assert set(table["counts"]) == {*sections, "shared_owner_cells"}
    for count_key, section_key in sections.items():
        assert len(table.get(section_key, [])) == table["counts"][count_key]
    assert sum(len(row["cells"]) for row in table.get("shared_owner", [])) == table["counts"]["shared_owner_cells"]
    assert "candidate" not in document


def test_cli_rejects_retired_output_arguments_before_loading_worklist(monkeypatch) -> None:
    monkeypatch.setattr(
        identity_subject,
        "load_bundled_m200_target_identity_worklists",
        lambda: pytest.fail("retired output arguments must fail during parsing"),
    )

    for arguments in (("--output", "review.toml"), ("--check",)):
        with pytest.raises(SystemExit) as error:
            identity_subject.main(list(arguments))
        assert error.value.code == 2


def _called_attribute_names(tree: ast.Module) -> set[str]:
    """Return every attribute a call in ``tree`` targets, as in ``p.write_text()``."""
    return {
        node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def _called_bare_names(tree: ast.Module) -> set[str]:
    """Return every bare name a call in ``tree`` targets, as in ``open()``.

    The absence claim below forbids ``open``, which is a builtin and therefore
    almost always spelled bare. Read through attribute callees alone it was a
    name the gate could never see: the commonest way in Python to open a file
    for writing sits in this set and in no other.
    """
    return {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


#: Floors for the parsed surface behind the absence claims below, one per
#: callee shape. Live: the subject module makes 15 attribute calls and 45 bare
#: calls. They are counted separately on purpose - a single floor over the
#: union is satisfied by either shape alone, so the collection of the other
#: could collapse to nothing while every absence below still held.
_MINIMUM_SUBJECT_ATTRIBUTE_CALLS = 5
_MINIMUM_SUBJECT_BARE_CALLS = 15


def test_identity_cli_has_no_filesystem_write_surface() -> None:
    """The identity CLI reports; it does not write.

    Every claim here is an ABSENCE - a disjoint call set and two missing
    attributes - and all three are satisfied by a module that does nothing at
    all. A stubbed or emptied subject would pass this gate while the CLI it
    describes had stopped existing, so the surface is counted before the
    absences are believed.
    """
    tree = ast.parse(inspect.getsource(identity_subject))
    filesystem_writes = {
        "mkdir",
        "open",
        "replace",
        "truncate",
        "write_bytes",
        "write_text",
    }
    called_attributes = _called_attribute_names(tree)
    called_bare = _called_bare_names(tree)

    assert len(called_attributes) >= _MINIMUM_SUBJECT_ATTRIBUTE_CALLS, (
        f"the subject module makes only {len(called_attributes)} attribute call(s); below "
        "this the absence claims below hold because the module does nothing, not because "
        "it refrains from writing"
    )
    assert len(called_bare) >= _MINIMUM_SUBJECT_BARE_CALLS, (
        f"the subject module makes only {len(called_bare)} bare call(s); the builtin "
        "spellings among the forbidden names are only visible in this set"
    )
    assert filesystem_writes.isdisjoint(called_attributes | called_bare)
    for helper in ("write_review_output", "resolve_review_output_path"):
        assert not hasattr(identity_subject, helper)
        assert not hasattr(identity_subject, f"_{helper}")


def _record_design_field(
    *, normalized_description: str, aeat_type: str = "Num", record_identity: str = "DP200001"
) -> RecordDesignIntermediateField:
    """One minimal, fully valid field, for cases where only a few attributes matter."""
    return RecordDesignIntermediateField(
        sheet="S1",
        record_identity=record_identity,
        source_row=1,
        offset=1,
        length=17,
        aeat_type=aeat_type,
        normalized_description=normalized_description,
    )


def test_current_printed_identity_beats_sibling_casilla_identity() -> None:
    target_field = _record_design_field(normalized_description="Importe [02971]")

    # `_classify_sibling` does not read the sibling field or entry once the
    # current printed identity resolves, which the two `None`s below assert:
    # the classification below holds with no sibling evidence at all.
    disposition, reason, proposed_id, _kind = subject.classify_sibling(
        target_field,
        None,
        None,
        authored_token=_CASILLA_2971,
        target_ids_by_number={"00355": ("00355",)},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "02971"


def test_current_casilla_identity_beats_later_sibling_filler() -> None:
    target_field = _record_design_field(normalized_description="Importe [01683]")

    disposition, reason, proposed_id, _kind = subject.classify_sibling(
        target_field,
        None,
        None,
        authored_token=_CASILLA_1683,
        target_ids_by_number={},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "01683"


def _printed_number(fields: Mapping[tuple[object, ...], RecordDesignIntermediateField], entry: SemanticMapEntry) -> str:
    (number,) = re.findall(r"\[([0-9]+)\]", fields[semantic_anchor_key(entry.anchor)].normalized_description)
    return str(number).lstrip("0")


def _casilla_entries(target_map):
    return [entry for entry in target_map.entries if entry.kind is CasillaFieldKind.CASILLA]


def _with_entry(target_map, original, replacement):
    entries = tuple(replacement if entry is original else entry for entry in target_map.entries)
    return target_map.model_copy(update={"entries": entries})


def test_screen_covers_every_revision_the_registry_selects_for_filing() -> None:
    worklists = identity_subject.load_bundled_m200_target_identity_worklists()
    authority = compiled_bundled_authority()
    filing = {
        str(revision.id)
        for revision in authority.modelo("200").revisions.values()
        if revision.authority_grade is RegistryAuthorityGrade.FILING
    }

    assert filing
    assert filing <= {worklist.revision for worklist in worklists}
    for worklist in worklists:
        assert not worklist.map_owner_mismatches, worklist.revision
        assert not worklist.printed_identity_diagnostics, worklist.revision
        assert {row.disposition for row in worklist.orphaned_declarations} <= {
            identity_subject.M200OrphanDisposition.DECLARED_UNPLACED,
            identity_subject.M200OrphanDisposition.DECLARED_WORKING_FIGURE,
        }, worklist.revision


def test_target_identity_worklist_is_clean_and_dispositions_layout_declared_orphans(target_identity_worklist) -> None:
    worklist = target_identity_worklist

    assert worklist.revision == _TARGET_REVISION
    assert not worklist.map_owner_mismatches
    assert not worklist.printed_identity_diagnostics
    by_id = {row.casilla_id: row.disposition for row in worklist.orphaned_declarations}
    assert by_id["DP200014:SAL_RESERVA_DOTACION"] is identity_subject.M200OrphanDisposition.DECLARED_UNPLACED
    assert by_id["DP200014:bin-aplicada-maxima"] is identity_subject.M200OrphanDisposition.DECLARED_WORKING_FIGURE


def test_orphan_without_a_layout_declaration_stays_unmapped(target_identity_inputs) -> None:
    target_map, target_design, declarations, _placements = target_identity_inputs

    worklist = _classify(target_map, target_design, declarations, {})

    assert {row.disposition for row in worklist.orphaned_declarations} == {
        identity_subject.M200OrphanDisposition.UNMAPPED_DECLARATION
    }


def test_planted_wrong_owner_is_reported(target_identity_inputs, target_identity_worklist) -> None:
    target_map, target_design, declarations, placements = target_identity_inputs
    entries = _casilla_entries(target_map)
    victim = entries[0]
    wrong_owner = next(
        entry.casilla_id
        for entry in entries
        if entry.casilla_id is not None and entry.casilla_id.lstrip("0") != str(victim.casilla_id).lstrip("0")
    )
    planted = _with_entry(target_map, victim, victim.model_copy(update={"casilla_id": wrong_owner}))

    worklist = _classify(planted, target_design, declarations, placements)

    conflicts = [
        row
        for row in worklist.printed_identity_diagnostics
        if row.state is identity_subject.M200PrintedIdentityState.CONFLICTS_WITH_MAP_OWNER
    ]
    assert [row.export_field_id for row in conflicts] == [str(victim.export_field_id)]
    assert conflicts[0].declared_map_owner == wrong_owner
    assert len(worklist.printed_identity_diagnostics) == len(target_identity_worklist.printed_identity_diagnostics) + 1


def test_shared_owner_ignores_the_printed_number_match_that_hides_it(target_identity_inputs) -> None:
    """Teeth: two sheets printing one number with one owner pass every number check, and are still reported."""
    target_map, target_design, declarations, placements = target_identity_inputs
    fields = record_design_field_index(target_design)
    numbers: dict[str, list[SemanticMapEntry]] = {}
    for entry in _casilla_entries(target_map):
        numbers.setdefault(_printed_number(fields, entry), []).append(entry)
    worklist_before = _classify(target_map, target_design, declarations, placements)
    reported = {row.casilla_id for row in worklist_before.shared_owners}
    (left, right) = next(
        pair
        for pair in numbers.values()
        if len(pair) == 2
        and {str(pair[0].casilla_id), str(pair[1].casilla_id)}.isdisjoint(reported)
        and pair[0].casilla_id != pair[1].casilla_id
    )
    merged = _with_entry(target_map, right, right.model_copy(update={"casilla_id": left.casilla_id}))

    worklist = _classify(merged, target_design, declarations, placements)

    assert not worklist.printed_identity_diagnostics
    assert not worklist.map_owner_mismatches
    (planted,) = [row for row in worklist.shared_owners if row.casilla_id not in reported]
    assert planted.casilla_id == left.casilla_id
    assert {cell.export_field_id for cell in planted.cells} == {str(left.export_field_id), str(right.export_field_id)}


def test_declared_echo_of_another_sheet_is_not_a_shared_owner(target_identity_worklist) -> None:
    reported = {row.casilla_id: {cell.sheet for cell in row.cells} for row in target_identity_worklist.shared_owners}
    echoed = {casilla_id for _sheet, casilla_id in MODELO_200_ECHO_CELLS}

    assert echoed
    assert echoed.isdisjoint(reported)


def test_shared_owner_debt_does_not_grow() -> None:
    """Each cell here receives another concept's amount, so the count may only fall."""
    for worklist in identity_subject.load_bundled_m200_target_identity_worklists():
        cells = sum(len(row.cells) for row in worklist.shared_owners)
        assert cells <= _SHARED_OWNER_CELL_CEILING, worklist.revision


def test_padded_equivalent_owner_is_not_reported(target_identity_inputs, target_identity_worklist) -> None:
    target_map, target_design, declarations, placements = target_identity_inputs
    padded = next(
        entry
        for entry in _casilla_entries(target_map)
        if str(entry.casilla_id).isdecimal() and str(entry.casilla_id).startswith("0")
    )
    stripped = padded.model_copy(update={"casilla_id": str(padded.casilla_id).lstrip("0")})
    assert stripped.casilla_id not in declarations
    unpadded = _with_entry(target_map, padded, stripped)

    worklist = _classify(unpadded, target_design, declarations, placements)

    assert worklist == target_identity_worklist


def test_printed_identity_equal_after_padding_is_not_diagnosed_but_a_different_one_is() -> None:
    four_digit = _record_design_field(normalized_description="Importe [1501]")
    three_digit = _record_design_field(normalized_description="Importe [387]")

    assert identity_subject.printed_target_number(four_digit) == "1501"
    assert identity_subject.printed_target_number(three_digit) == "387"
    matches = identity_subject.M200PrintedIdentityState.MATCHES_MAP_OWNER
    assert identity_subject.printed_identity_state("1501", "01501", proposal=None) is matches
    assert identity_subject.printed_identity_state("1501", "1501", proposal=None) is matches
    assert identity_subject.printed_identity_state("387", "00387", proposal=None) is matches
    assert (
        identity_subject.printed_identity_state("1501", "01502", proposal=None)
        is identity_subject.M200PrintedIdentityState.CONFLICTS_WITH_MAP_OWNER
    )
    assert (
        identity_subject.printed_identity_state(None, "01501", proposal=None)
        is identity_subject.M200PrintedIdentityState.MISSING_OFFICIAL_PRINTED_IDENTITY
    )


def test_target_identity_worklist_renders_deterministically(target_identity_worklist) -> None:
    rendered = identity_subject.render_m200_target_identity_worklists_toml((target_identity_worklist,))

    assert rendered == identity_subject.render_m200_target_identity_worklists_toml((target_identity_worklist,))
    assert "declared_unplaced" in rendered
    assert "[[entries]]" not in rendered


def test_target_identity_classifier_refuses_source_anchor_omission_noncasilla_owner_and_source_drift(
    target_identity_inputs,
) -> None:
    target_map, target_design, declarations, placements = target_identity_inputs

    def classify(candidate):
        return _classify(candidate, target_design, declarations, placements)

    # Every variant is a real, typed map perturbed through `model_copy`, so the
    # classifier's own checks are what must refuse the drift.
    omitted = target_map.model_copy(update={"entries": target_map.entries[1:]})
    with pytest.raises(ValueError, match="omits"):
        classify(omitted)

    first_casilla = _casilla_entries(target_map)[0]
    noncasilla_owner = first_casilla.model_copy(update={"kind": CasillaFieldKind.FILLER})
    with pytest.raises(ValueError, match="non-casilla"):
        classify(_with_entry(target_map, first_casilla, noncasilla_owner))

    missing_owner = first_casilla.model_copy(update={"casilla_id": None})
    with pytest.raises(ValueError, match="omits its owner"):
        classify(_with_entry(target_map, first_casilla, missing_owner))

    unknown_owner = first_casilla.model_copy(update={"casilla_id": "99999999"})
    with pytest.raises(ValueError, match="ambiguous or missing"):
        classify(_with_entry(target_map, first_casilla, unknown_owner))

    with pytest.raises(ValueError, match="source identity drifted"):
        classify(target_map.model_copy(update={"source_sha256": "0" * 64}))


def test_target_identity_classifier_proposes_only_the_unique_segment_qualified_owner(target_identity_inputs) -> None:
    target_map, _design, _declarations, _placements = target_identity_inputs
    entry = _casilla_entries(target_map)[0].model_copy(update={"casilla_id": "588"})
    field = _record_design_field(normalized_description="Importe", record_identity="DP200018")

    disposition, proposed = identity_subject.classify_noncanonical_map_owner(
        entry, target_map, field=field, known_ids=frozenset({"DP200018:00588", "DP200014B:00588"})
    )
    assert disposition is identity_subject.M200MapOwnerIdentityDisposition.SEGMENT_QUALIFIED_PROPOSAL
    assert proposed == "DP200018:00588"

    with pytest.raises(ValueError, match="ambiguous or missing"):
        identity_subject.classify_noncanonical_map_owner(
            entry, target_map, field=field, known_ids=frozenset({"DP200014B:00588"})
        )
