from __future__ import annotations

import ast
import inspect
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.loader import load_catalogue_file, load_modelo_directory

from ..analysis import m200_2024_sibling_remediation as remediation
from ..analysis import m200_semantic_casilla_candidates as subject
from ..analysis.m200_restored_semantic_audit import _candidate_payloads
from ..pipeline._record_design_ir import load_record_design_intermediate
from ..pipeline._semantic_map_loader import load_semantic_map

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
        frozenset(_candidate_payloads()),
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


def test_identity_cli_has_no_filesystem_write_surface() -> None:
    tree = ast.parse(inspect.getsource(subject))
    filesystem_writes = {
        "mkdir",
        "open",
        "replace",
        "truncate",
        "write_bytes",
        "write_text",
    }
    called_attributes = {
        node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert filesystem_writes.isdisjoint(called_attributes)
    assert not hasattr(subject, "_write_review_output")
    assert not hasattr(subject, "_resolve_review_output_path")


def test_current_printed_identity_beats_sibling_casilla_identity() -> None:
    target_field = SimpleNamespace(
        normalized_description="Importe [02971]",
        aeat_type="Num",
    )
    sibling_field = SimpleNamespace()
    sibling_entry = SimpleNamespace(kind=CasillaFieldKind.CASILLA, casilla_id="00355")

    disposition, reason, proposed_id, _kind = subject._classify_sibling(
        target_field,
        sibling_field,
        sibling_entry,
        authored_token="2971",  # noqa: S106 - official casilla token
        target_ids_by_number={"00355": ("00355",)},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "02971"


def test_current_2024_casilla_identity_beats_later_sibling_filler() -> None:
    target_field = SimpleNamespace(normalized_description="Importe [01683]", aeat_type="Num")
    sibling_entry = SimpleNamespace(kind=CasillaFieldKind.FILLER, casilla_id=None)

    disposition, reason, proposed_id, _kind = subject._classify_sibling(
        target_field,
        SimpleNamespace(),
        sibling_entry,
        authored_token="1683",  # noqa: S106 - official casilla token
        target_ids_by_number={},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "01683"


def test_m200_2024_sibling_remediation_refuses_target_first_restoration_gaps() -> None:
    """Sibling payload cannot replace the current design's printed identity."""
    proposals = remediation.load_bundled_m200_2024_sibling_remediation()
    counts = {
        disposition: sum(item.disposition is disposition for item in proposals)
        for disposition in remediation.M200RemediationDisposition
    }

    assert proposals
    assert counts[remediation.M200RemediationDisposition.DERIVE_DECLARATION] == 0
    assert counts[remediation.M200RemediationDisposition.CORRECT_SEMANTIC_MAP] == 0
    assert counts[remediation.M200RemediationDisposition.UNRESOLVED] == len(proposals)


def test_target_identity_worklist_classifies_every_noncanonical_owner_and_true_orphan(target_identity_worklist) -> None:
    worklist = target_identity_worklist
    dispositions = Counter(row.disposition for row in worklist.map_owner_mismatches)

    # Both dispositions must occur, so the classifier is shown discriminating,
    # and the segment-qualified one must be singular because every assertion
    # below reads THE qualified row. Their relative sizes are a fact about the
    # corpus on one day and were frozen here as 184 and 1.
    assert set(dispositions) == {
        subject.M200MapOwnerIdentityDisposition.ZERO_PADDING_PROPOSAL,
        subject.M200MapOwnerIdentityDisposition.SEGMENT_QUALIFIED_PROPOSAL,
    }
    assert dispositions[subject.M200MapOwnerIdentityDisposition.SEGMENT_QUALIFIED_PROPOSAL] == 1
    assert all(
        row.proposed_identity_origin in {"declared", "candidate_non_authoritative"}
        for row in worklist.map_owner_mismatches
    )
    assert all(
        row.printed_identity_state is subject.M200PrintedIdentityState.MATCHES_IDENTITY_PROPOSAL
        for row in worklist.map_owner_mismatches
    )
    qualified = next(
        row
        for row in worklist.map_owner_mismatches
        if row.disposition is subject.M200MapOwnerIdentityDisposition.SEGMENT_QUALIFIED_PROPOSAL
    )
    assert qualified.export_field_id == "m200-2024.dp200018.f0172"
    assert qualified.proposed_target_identity_non_authoritative == "DP200018:00588"
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
    omitted = SimpleNamespace(
        source_ref=target_map.source_ref,
        source_sha256=target_map.source_sha256,
        entries=target_map.entries[1:],
    )
    with pytest.raises(ValueError, match="omits"):
        subject.classify_m200_target_identities(omitted, target_design, **kwargs)

    first_casilla = next(entry for entry in target_map.entries if entry.kind is CasillaFieldKind.CASILLA)
    noncasilla_owner = SimpleNamespace(
        anchor=first_casilla.anchor,
        export_field_id=first_casilla.export_field_id,
        kind=CasillaFieldKind.FILLER,
        casilla_id=first_casilla.casilla_id,
    )
    invalid_entries = tuple(noncasilla_owner if entry is first_casilla else entry for entry in target_map.entries)
    invalid_map = SimpleNamespace(
        source_ref=target_map.source_ref,
        source_sha256=target_map.source_sha256,
        entries=invalid_entries,
    )
    with pytest.raises(ValueError, match="non-casilla"):
        subject.classify_m200_target_identities(invalid_map, target_design, **kwargs)

    missing_owner = SimpleNamespace(
        anchor=first_casilla.anchor,
        export_field_id=first_casilla.export_field_id,
        kind=CasillaFieldKind.CASILLA,
        casilla_id=None,
    )
    missing_owner_entries = tuple(missing_owner if entry is first_casilla else entry for entry in target_map.entries)
    missing_owner_map = SimpleNamespace(
        source_ref=target_map.source_ref,
        source_sha256=target_map.source_sha256,
        entries=missing_owner_entries,
    )
    with pytest.raises(ValueError, match="omits its owner"):
        subject.classify_m200_target_identities(missing_owner_map, target_design, **kwargs)

    drifted = SimpleNamespace(
        source_ref=target_map.source_ref,
        source_sha256="0" * 64,
        entries=target_map.entries,
    )
    with pytest.raises(ValueError, match="source identity drifted"):
        subject.classify_m200_target_identities(drifted, target_design, **kwargs)


def test_target_identity_classifier_refuses_ambiguous_or_wrong_segment_proposals() -> None:
    field = SimpleNamespace(record_identity="DP200018")
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
