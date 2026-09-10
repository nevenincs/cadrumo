from __future__ import annotations

import ast
import inspect
from collections import Counter
from pathlib import Path

import pytest
import rtoml
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind

from ..analysis import m200_semantic_casilla_candidates as subject
from ..pipeline.record_design_intermediate import RecordDesignIntermediateField, load_record_design_intermediate
from ..pipeline.semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def target_identity_inputs():
    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(registry_root / "modelos" / "200")
    target = modelo.revisions["2024"]
    catalogues = load_catalogue_file(registry_root / "legal" / "is.toml")
    source_ref = subject._record_design_source(target.source_refs, catalogues.sources)
    epoch = catalogues.sources[source_ref].record_design_epoch
    assert epoch is not None
    return (
        load_semantic_map(Path("dev/registry/mappings/modelo_200") / epoch),
        load_record_design_intermediate(
            source_root,
            catalogues.sources,
            source_ref=source_ref,
            filing_year=target.valid_from.year,
            design_epoch=epoch,
        ),
        {declaration.id: declaration for declaration in target.casillas},
        frozenset(),
    )


@pytest.fixture(scope="module")
def target_identity_worklist(target_identity_inputs):
    target_map, target_design, declarations, candidates = target_identity_inputs
    return subject.classify_m200_target_identities(
        target_map,
        target_design,
        target_declarations=declarations,
        target_candidate_ids=candidates,
    )


def _candidate() -> subject.M200CasillaCandidate:
    return subject.M200CasillaCandidate(
        export_field_id="m200-2024.dp200018.f0172",
        authored_token="588",  # noqa: S106 - official casilla token, not a credential
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


def test_review_toml_is_deterministic_and_serializes_disposition() -> None:
    rendered = subject.render_m200_casilla_candidates_toml((_candidate(),))

    assert rendered == subject.render_m200_casilla_candidates_toml((_candidate(),))
    assert "disposition = 'segment_qualified_identity'" in rendered
    assert "registry_data_type" not in rendered
    assert "legal_refs" not in rendered


def test_cli_stdout_exports_the_complete_proposal_only_target_identity_worklist(
    capsys,
    monkeypatch,
    target_identity_worklist,
) -> None:
    monkeypatch.setattr(subject, "load_bundled_m200_target_identity_worklist", lambda: target_identity_worklist)

    assert subject.main([]) == 0
    document = rtoml.loads(capsys.readouterr().out)

    assert document["authority_status"] == "proposal_only"
    # The counts once carried a frozen corpus snapshot - 185, 2 and 15 - which
    # went stale within an afternoon of being written when the modelo 200 2024
    # declarations landed, and then reported a fall of four in one number and a
    # rise of a hundred and fifty-two in another as one failed equality. What
    # the assertion was for survives without the snapshot: the document must
    # describe its own contents, and it must describe something.
    sections = {
        "map_owner_mismatches": "map_owner_mismatch",
        "orphaned_declarations": "orphaned_declaration",
        "printed_identity_diagnostics": "printed_identity_diagnostic",
    }
    assert set(document["counts"]) == set(sections)
    for count_key, section_key in sections.items():
        assert len(document[section_key]) == document["counts"][count_key]
        assert document["counts"][count_key] > 0, f"{section_key} is empty, so the export proves nothing"
    assert "candidate" not in document


def test_cli_rejects_retired_output_arguments_before_loading_worklist(monkeypatch) -> None:
    monkeypatch.setattr(
        subject,
        "load_bundled_m200_target_identity_worklist",
        lambda: pytest.fail("retired output arguments must fail during parsing"),
    )

    for arguments in (("--output", "review.toml"), ("--check",)):
        with pytest.raises(SystemExit) as error:
            subject.main(list(arguments))
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
    tree = ast.parse(inspect.getsource(subject))
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
    assert not hasattr(subject, "_write_review_output")
    assert not hasattr(subject, "_resolve_review_output_path")


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
    disposition, reason, proposed_id, _kind = subject._classify_sibling(
        target_field,
        None,
        None,
        authored_token="2971",  # noqa: S106 - official casilla token
        target_ids_by_number={"00355": ("00355",)},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "02971"


def test_current_2024_casilla_identity_beats_later_sibling_filler() -> None:
    target_field = _record_design_field(normalized_description="Importe [01683]")

    disposition, reason, proposed_id, _kind = subject._classify_sibling(
        target_field,
        None,
        None,
        authored_token="1683",  # noqa: S106 - official casilla token
        target_ids_by_number={},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "01683"


def test_target_identity_worklist_classifies_every_noncanonical_owner_and_true_orphan(target_identity_worklist) -> None:
    worklist = target_identity_worklist
    dispositions = Counter(row.disposition for row in worklist.map_owner_mismatches)

    assert worklist.map_owner_mismatches
    assert set(dispositions) == {subject.M200MapOwnerIdentityDisposition.ZERO_PADDING_PROPOSAL}
    assert all(row.proposed_identity_origin == "declared" for row in worklist.map_owner_mismatches)
    assert all(
        row.printed_identity_state is subject.M200PrintedIdentityState.MATCHES_IDENTITY_PROPOSAL
        for row in worklist.map_owner_mismatches
    )
    # These two were the whole orphan set when this test was written and are now
    # two of a hundred and fifty-four, because the 2024 declarations landed
    # without map owners. They are kept as named members rather than as the set,
    # so the anchor survives a population that grows.
    orphans = {row.casilla_id for row in worklist.orphaned_declarations}
    assert {"DP200014:SAL_RESERVA_DOTACION", "DP200014:bin-aplicada-maxima"} <= orphans
    assert {row.disposition for row in worklist.orphaned_declarations} == {
        subject.M200OrphanDisposition.UNMAPPED_DECLARATION
    }


def test_target_identity_worklist_keeps_printed_diagnostics_separate_from_map_owner(target_identity_worklist) -> None:
    worklist = target_identity_worklist

    assert len(worklist.printed_identity_diagnostics) == 15
    assert Counter(row.state for row in worklist.printed_identity_diagnostics) == {
        subject.M200PrintedIdentityState.MISSING_OFFICIAL_PRINTED_IDENTITY: 11,
        subject.M200PrintedIdentityState.CONFLICTS_WITH_MAP_OWNER: 4,
    }
    assert {row.export_field_id for row in worklist.printed_identity_diagnostics}.isdisjoint(
        row.export_field_id for row in worklist.map_owner_mismatches
    )
    rendered = subject.render_m200_target_identity_worklist_toml(worklist)
    assert rendered == subject.render_m200_target_identity_worklist_toml(worklist)
    assert "proposed_target_identity_non_authoritative" in rendered
    assert "[[entries]]" not in rendered


def test_target_identity_classifier_refuses_source_anchor_omission_noncasilla_owner_and_source_drift(
    target_identity_inputs,
) -> None:
    target_map, target_design, declarations, candidates = target_identity_inputs
    kwargs = {"target_declarations": declarations, "target_candidate_ids": candidates}
    # Every variant below is a real, typed `SemanticMap`/`SemanticMapEntry`,
    # perturbed through `model_copy` rather than duck-typed: the classifier's
    # own checks are what must refuse the drift, not a stand-in object shaped
    # only well enough to reach them. `model_copy` does not re-run the
    # frozen model's validators, so the perturbed structure survives
    # construction and reaches the classifier unresolved.
    omitted = target_map.model_copy(update={"entries": target_map.entries[1:]})
    with pytest.raises(ValueError, match="omits"):
        subject.classify_m200_target_identities(omitted, target_design, **kwargs)

    first_casilla = next(entry for entry in target_map.entries if entry.kind is CasillaFieldKind.CASILLA)
    noncasilla_owner = first_casilla.model_copy(update={"kind": CasillaFieldKind.FILLER})
    invalid_entries = tuple(noncasilla_owner if entry is first_casilla else entry for entry in target_map.entries)
    invalid_map = target_map.model_copy(update={"entries": invalid_entries})
    with pytest.raises(ValueError, match="non-casilla"):
        subject.classify_m200_target_identities(invalid_map, target_design, **kwargs)

    missing_owner = first_casilla.model_copy(update={"casilla_id": None})
    missing_owner_entries = tuple(missing_owner if entry is first_casilla else entry for entry in target_map.entries)
    missing_owner_map = target_map.model_copy(update={"entries": missing_owner_entries})
    with pytest.raises(ValueError, match="omits its owner"):
        subject.classify_m200_target_identities(missing_owner_map, target_design, **kwargs)

    drifted = target_map.model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(ValueError, match="source identity drifted"):
        subject.classify_m200_target_identities(drifted, target_design, **kwargs)


def test_target_identity_classifier_refuses_ambiguous_or_wrong_segment_proposals() -> None:
    field = _record_design_field(normalized_description="Importe", record_identity="DP200018")
    with pytest.raises(ValueError, match="ambiguous"):
        subject._classify_noncanonical_map_owner(
            "588",
            field=field,
            known_ids=frozenset({"00588", "DP200018:00588"}),
        )
    with pytest.raises(ValueError, match="ambiguous"):
        subject._classify_noncanonical_map_owner(
            "588",
            field=field,
            known_ids=frozenset({"DP200014B:00588"}),
        )
