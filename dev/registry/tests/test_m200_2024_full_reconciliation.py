from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.legal import verify_legal_catalogue
from cadrumo.domain.calculations.registry.loader import load_catalogue_file

from ..analysis import m200_2024_full_reconciliation as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.timeout(600)]
"""The 600-second budget is contention, not a slow test.

The rebind-refusal case runs 251.48s alone but measured 305.46s under the
repository's DEFAULT `-n auto` parallelism, which is how it actually runs. The
300-second ceiling is wall clock, so a loaded box crosses it on a test that is
doing exactly what it should; the sibling two-channel-proof module already
carries a 600-second marker on its own long case for the same reason.

Two more cases here stand at 176.28s and 137.63s, so the margin is the
contention this suite meets in a full run, not headroom for a defect.
"""


@pytest.fixture(scope="module")
def reviewed_promotions():
    """One explicit evidence snapshot for the full reconciliation invocation."""
    from ..analysis.m200_2024_reviewed_promotions import build_m200_2024_reviewed_promotion_snapshot

    return build_m200_2024_reviewed_promotion_snapshot()


@pytest.fixture(scope="module")
def census(reviewed_promotions):
    return subject._reconcile_bundled_m200_2024(reviewed_promotions)


@pytest.fixture(scope="module")
def source_rebind_plan(census, reviewed_promotions):
    return subject._build_m200_source_rebind_plan(census, reviewed_promotions)


@pytest.fixture
def rebind_registry_root(tmp_path: Path) -> Path:
    source = bundled_path("registry", "aeat", "modelos", "200", "revisions", "2024", "casillas")
    destination = tmp_path / "registry" / "modelos" / "200" / "revisions" / "2024" / "casillas"
    shutil.copytree(source, destination)
    return tmp_path / "registry"


def test_full_reconciliation_accounts_for_every_declaration_candidate_and_target_anchor(census) -> None:
    rows = census.rows
    anchors = census.anchors

    assert len(rows) == 3329
    assert sum(row.origin == "current_declaration" for row in rows) == 3329
    assert sum(row.origin == "restoration_candidate" for row in rows) == 0
    assert len(anchors) == 6709
    assert len({anchor.anchor for anchor in anchors}) == len(anchors)
    assert len({anchor.export_field_id for anchor in anchors}) == len(anchors)
    assert sum(anchor.owner_state == "exact_planned_owner" for anchor in anchors) == 5292
    assert sum(anchor.owner_state == "zero_padding_mismatch_refused" for anchor in anchors) == 180
    assert sum(anchor.owner_state == "qualified_identity_mismatch_refused" for anchor in anchors) == 1
    assert sum(anchor.owner_state == "non_casilla" for anchor in anchors) == 1236
    assert sum(anchor.owner_state == "unknown_map_owner_refused" for anchor in anchors) == 0


def test_rebind_census_preserves_exact_map_ownership_and_withholds_identity_anomalies(census) -> None:
    current = tuple(row for row in census.rows if row.origin == "current_declaration")
    by_id = {row.casilla_id: row for row in census.rows}

    assert sum(row.source_ref_state == "mechanical_rebind" for row in current) == 3171
    # Receipt-backed promotions remain map-unowned until W04 admits their
    # qualified identities; the source-rebind planner verifies them separately.
    assert sum(row.source_ref_state == "unmapped_no_rebind" for row in current) == 154
    assert sum(bool(row.fields) for row in current) == 3175
    assert sum(row.identity_review_required for row in current) == 15
    assert all(
        row.source_ref_state != "candidate_non_authoritative"
        for row in census.rows
        if row.origin == "current_declaration"
    )

    mismatched = next(anchor for anchor in census.anchors if anchor.export_field_id == "m200-2024.dp200022.f0032")
    assert mismatched.declared_map_owner == "03627"
    assert mismatched.printed_number == "00927"
    assert mismatched.owner_state == "exact_planned_owner"
    assert mismatched.printed_identity_state == "conflicts_with_declared_owner"
    assert mismatched in by_id["03627"].fields
    assert mismatched not in by_id["00927"].fields

    promoted = by_id["00093"]
    assert promoted.origin == "current_declaration"
    assert promoted.declaration_payload is not None
    assert promoted.candidate_payload_non_authoritative is None


def test_report_carries_exact_source_map_and_legal_evidence_deterministically(census) -> None:
    first = subject.render_reconciliation_toml(census)
    second = subject.render_reconciliation_toml(census)
    document = rtoml.loads(first)

    assert first == second
    assert document["source_ref"] == subject.TARGET_SOURCE_REF
    assert document["source_sha256"] == subject.TARGET_SOURCE_SHA256
    assert document["semantic_map_source_ref"] == subject.TARGET_SOURCE_REF
    assert document["semantic_map_source_sha256"] == subject.TARGET_SOURCE_SHA256
    assert document["revision_valid_from"] == "2024-01-01"
    assert document["revision_valid_to"] == "2024-12-31"
    assert len(document["row"]) == 3329
    assert len(document["anchor"]) == 6709
    assert all("source_refs" in anchor for anchor in document["anchor"])
    assert all("legal_evidence_state" in anchor for anchor in document["anchor"])
    assert all("applicable_legal_refs" in anchor for anchor in document["anchor"])
    assert all("inapplicable_legal_refs" in anchor for anchor in document["anchor"])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("source_sha256", "b" * 64, "source identity drifted"),
        ("semantic_map_source_ref", subject.SIBLING_SOURCE_REF, "source identity drifted"),
        ("revision_valid_to", date(2025, 12, 31), "partition"),
    ),
)
def test_render_refuses_source_sha_map_and_partition_drift(census, field: str, value, message: str) -> None:
    with pytest.raises(RegistryValidationError, match=message):
        subject.render_reconciliation_toml(replace(census, **{field: value}))


def test_source_entry_collision_and_anchor_mutations_fail_closed() -> None:
    subject._require_exact_source_identity("test", subject.TARGET_SOURCE_REF, subject.TARGET_SOURCE_SHA256)
    with pytest.raises(RegistryValidationError, match="source identity drifted"):
        subject._require_exact_source_identity("test", subject.TARGET_SOURCE_REF, "0" * 64)
    with pytest.raises(RegistryValidationError, match="non-target source refs"):
        subject._require_entry_source_refs(
            (SimpleNamespace(export_field_id="field-1", source_refs=(subject.SIBLING_SOURCE_REF,)),)
        )
    with pytest.raises(RegistryValidationError, match="collide"):
        subject._require_disjoint_ids(frozenset({"00093"}), frozenset({"00093"}))
    with pytest.raises(RegistryValidationError, match="duplicate current declaration"):
        subject._require_unique_identifiers(("00001", "00001"), label="current declaration")
    with pytest.raises(RegistryValidationError, match="not bijective"):
        subject._require_anchor_bijection(
            design_keys=(("sheet", 1), ("sheet", 2)),
            map_keys=(("sheet", 1),),
            export_ids=("field-1",),
        )


def test_partition_and_catalogue_mutations_fail_closed() -> None:
    target = SimpleNamespace(
        id="2024",
        valid_from=subject.TARGET_VALID_FROM,
        valid_to=subject.TARGET_VALID_TO,
        source_refs=(subject.TARGET_SOURCE_REF,),
    )
    sibling = SimpleNamespace(
        id="2025-y-siguientes",
        valid_from=subject.SIBLING_VALID_FROM,
        valid_to=None,
        source_refs=(subject.SIBLING_SOURCE_REF,),
    )
    subject._require_partition(target, sibling)
    with pytest.raises(RegistryValidationError, match="partition drifted"):
        subject._require_partition(SimpleNamespace(**{**vars(target), "valid_to": date(2025, 12, 31)}), sibling)
    first = SimpleNamespace(sources={"duplicate": object()})
    second = SimpleNamespace(sources={"duplicate": object()})
    with pytest.raises(RegistryValidationError, match="duplicate sources catalogue"):
        subject._merge_unique_catalogue((first, second), attribute="sources")


def test_missing_map_legal_ref_is_visible_and_unreviewed_candidates_cannot_seed_peers(census) -> None:
    applicable, inapplicable = subject._legal_partition(
        ("missing-legal-ref",), {}, subject.TARGET_VALID_FROM, subject.TARGET_VALID_TO
    )
    assert applicable == ()
    assert inapplicable == ("missing-legal-ref",)
    assert subject._legal_evidence((), {}, subject.TARGET_VALID_FROM, subject.TARGET_VALID_TO) == (
        (),
        (),
        "missing_legal_provenance",
    )
    assert subject._legal_evidence(("missing-legal-ref",), {}, subject.TARGET_VALID_FROM, subject.TARGET_VALID_TO) == (
        (),
        ("missing-legal-ref",),
        "unresolved_or_inapplicable",
    )
    assert not subject._legal_refs_support_proposal((), {}, subject.TARGET_VALID_FROM, subject.TARGET_VALID_TO)
    assert not subject._legal_refs_support_proposal(
        ("missing-legal-ref",), {}, subject.TARGET_VALID_FROM, subject.TARGET_VALID_TO
    )
    assert all(row.legal_evidence_state == "applicable" for row in census.rows)
    assert all(anchor.legal_evidence_state == "applicable" for anchor in census.anchors)

    trusted_payload = next(row.declaration_payload for row in census.rows if row.declaration_payload)
    candidate_payload = replace(trusted_payload, semantic_role="candidate-only-role")
    clean_field = SimpleNamespace(template="same-template", printed_identity_state="matches_declared_owner")
    candidate_field = SimpleNamespace(template="same-template", printed_identity_state="matches_declared_owner")
    peers = subject._trusted_template_payloads(
        {"trusted": (clean_field,), "candidate": (candidate_field,)},
        {"trusted": trusted_payload},
    )
    assert peers == {"same-template": {trusted_payload}}
    assert candidate_payload not in peers["same-template"]


def test_legal_worklist_measures_the_complete_2024_population_and_closes_reviewed_authority(census) -> None:
    worklist = subject.build_m200_2024_legal_worklist(census)

    assert worklist.source_ref == subject.TARGET_SOURCE_REF
    assert worklist.source_sha256 == subject.TARGET_SOURCE_SHA256
    assert len(worklist.items) == len(census.rows) + len(census.anchors) + 4 == 10042
    assert {item.evidence_home for item in worklist.items} == {"declaration", "revision", "semantic_map"}
    assert all(item.source_ref == subject.TARGET_SOURCE_REF for item in worklist.items)
    assert all(item.source_sha256 == subject.TARGET_SOURCE_SHA256 for item in worklist.items)
    assert worklist.missing_provenance_count == 0
    assert worklist.unknown_reference_count == 0
    assert worklist.out_of_window_count == 0
    assert all(item.state == "applicable" for item in worklist.items)
    subject.require_closed_m200_2024_legal_worklist(worklist)

    with pytest.raises(RegistryValidationError, match="source identity drifted"):
        subject.build_m200_2024_legal_worklist(replace(census, source_sha256="0" * 64))


def test_modelo_200_orden_governed_period_is_verified_against_its_bundled_boe_text() -> None:
    reference_id = "orden-hac-657-2025:modelo-200"
    legal = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml")).legal[reference_id]

    verify_legal_catalogue({reference_id: legal}, source_root=bundled_path())

    assert legal.governs_periods_from == subject.TARGET_VALID_FROM
    assert legal.governs_periods_to == subject.TARGET_VALID_TO
    assert "períodos impositivos iniciados entre el 1 de enero y el 31 de diciembre de 2024" in legal.required_text


def test_legal_worklist_refuses_missing_unknown_wrong_and_later_year_authority() -> None:
    wrong_provision = SimpleNamespace(
        id="ley-27-2014:art-30",
        effective_from=date(2015, 1, 1),
        effective_to=None,
        governs_periods_from=None,
        governs_periods_to=None,
    )
    with pytest.raises(RegistryValidationError, match="provision mismatch"):
        subject._legal_worklist_partition(
            ("ley-27-2014:art-29",),
            {"ley-27-2014:art-29": wrong_provision},
            subject.TARGET_VALID_FROM,
            subject.TARGET_VALID_TO,
        )

    missing = subject._legal_worklist_item(
        evidence_home="declaration",
        subject_id="missing",
        legal_refs=(),
        legal={},
        source_ref=subject.TARGET_SOURCE_REF,
        source_sha256=subject.TARGET_SOURCE_SHA256,
        valid_from=subject.TARGET_VALID_FROM,
        valid_to=subject.TARGET_VALID_TO,
    )
    unknown = subject._legal_worklist_item(
        evidence_home="semantic_map",
        subject_id="unknown",
        legal_refs=("missing-legal-ref",),
        legal={},
        source_ref=subject.TARGET_SOURCE_REF,
        source_sha256=subject.TARGET_SOURCE_SHA256,
        valid_from=subject.TARGET_VALID_FROM,
        valid_to=subject.TARGET_VALID_TO,
    )
    later_year_substitute = SimpleNamespace(
        id="ley-27-2014:dt-44",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        governs_periods_from=None,
        governs_periods_to=None,
    )
    out_of_window = subject._legal_worklist_item(
        evidence_home="declaration",
        subject_id="later-year-substitute",
        legal_refs=("ley-27-2014:dt-44",),
        legal={"ley-27-2014:dt-44": later_year_substitute},
        source_ref=subject.TARGET_SOURCE_REF,
        source_sha256=subject.TARGET_SOURCE_SHA256,
        valid_from=subject.TARGET_VALID_FROM,
        valid_to=subject.TARGET_VALID_TO,
    )
    assert missing.state == "missing_provenance"
    assert unknown.unknown_legal_refs == ("missing-legal-ref",)
    assert out_of_window.out_of_window_legal_refs == ("ley-27-2014:dt-44",)
    with pytest.raises(RegistryValidationError, match="missing=1, unknown=1, out_of_window=1"):
        subject.require_closed_m200_2024_legal_worklist(
            subject.M200LegalWorklist(
                source_ref=subject.TARGET_SOURCE_REF,
                source_sha256=subject.TARGET_SOURCE_SHA256,
                revision_valid_from=subject.TARGET_VALID_FROM,
                revision_valid_to=subject.TARGET_VALID_TO,
                items=(missing, unknown, out_of_window),
            )
        )


def test_cli_legal_admission_refuses_an_open_worklist_and_pending_authority(census) -> None:
    missing = subject._legal_worklist_item(
        evidence_home="declaration",
        subject_id="missing",
        legal_refs=(),
        legal={},
        source_ref=subject.TARGET_SOURCE_REF,
        source_sha256=subject.TARGET_SOURCE_SHA256,
        valid_from=subject.TARGET_VALID_FROM,
        valid_to=subject.TARGET_VALID_TO,
    )
    open_worklist = subject.M200LegalWorklist(
        source_ref=subject.TARGET_SOURCE_REF,
        source_sha256=subject.TARGET_SOURCE_SHA256,
        revision_valid_from=subject.TARGET_VALID_FROM,
        revision_valid_to=subject.TARGET_VALID_TO,
        items=(missing,),
    )
    with pytest.raises(RegistryValidationError, match="legal worklist is unresolved"):
        subject._require_closed_m200_2024_legal_worklist(census, worklist=open_worklist)

    reference_id = "orden-hac-657-2025:modelo-200"
    reviewed = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml")).legal[reference_id]
    pending = reviewed.model_copy(
        update={
            "review_status": RevisionReviewStatus.PENDING_REVIEW,
            "reviewed_at": None,
            "reviewed_by": None,
        }
    )
    applicable = subject._legal_worklist_item(
        evidence_home="revision",
        subject_id="orden_aplicabilidad",
        legal_refs=(reference_id,),
        legal={reference_id: pending},
        source_ref=subject.TARGET_SOURCE_REF,
        source_sha256=subject.TARGET_SOURCE_SHA256,
        valid_from=subject.TARGET_VALID_FROM,
        valid_to=subject.TARGET_VALID_TO,
    )
    with pytest.raises(RegistryValidationError, match="filing-grade authority requires a reviewed status"):
        subject._verify_m200_2024_worklist_legal_authority((applicable,), {reference_id: pending})


def test_source_rebind_plan_is_complete_target_map_owned_and_refuses_only_true_orphans(
    source_rebind_plan, reviewed_promotions
) -> None:
    assert source_rebind_plan.source_ref == subject.TARGET_SOURCE_REF
    assert source_rebind_plan.source_sha256 == subject.TARGET_SOURCE_SHA256
    assert source_rebind_plan.semantic_map_source_ref == subject.TARGET_SOURCE_REF
    assert source_rebind_plan.semantic_map_source_sha256 == subject.TARGET_SOURCE_SHA256
    assert len(source_rebind_plan.rebinds) == 3171
    from ..analysis.m200_2024_reviewed_promotions import _verified_promoted_candidate_ids

    receipted = _verified_promoted_candidate_ids(reviewed_promotions)
    assert len(receipted) == 156
    assert source_rebind_plan.verified_current_design_ids == tuple(sorted(receipted))
    assert len(source_rebind_plan.refused_orphan_ids) == 2
    assert len(source_rebind_plan.expected_current_ids) == 3329
    assert {
        *(item.casilla_id for item in source_rebind_plan.rebinds),
        *source_rebind_plan.verified_current_design_ids,
        *source_rebind_plan.refused_orphan_ids,
    } == set(source_rebind_plan.expected_current_ids)
    assert all(item.expected_source_refs[0] == subject.SIBLING_SOURCE_REF for item in source_rebind_plan.rebinds)
    assert all(item.target_source_refs[0] == subject.TARGET_SOURCE_REF for item in source_rebind_plan.rebinds)
    assert all(len(item.non_source_payload_sha256) == 64 for item in source_rebind_plan.rebinds)


def test_source_rebind_excludes_only_receipted_current_design_declarations() -> None:
    """The closed receipt admits promotions before later identity-join review."""
    receipted = frozenset({"00942", "01603", "02239", "02412"})

    assert tuple(
        subject._receipted_current_design_id(
            SimpleNamespace(
                casilla_id=identifier,
                fields=(),
                declaration_payload=SimpleNamespace(source_refs=(subject.TARGET_SOURCE_REF,)),
            ),
            receipted,
        )
        for identifier in sorted(receipted)
    ) == ("00942", "01603", "02239", "02412")


def test_source_rebind_refuses_an_unreceipted_current_design_declaration() -> None:
    """A generic target-source row cannot bypass the receipt-bound exclusion."""

    with pytest.raises(RegistryValidationError, match="unreceipted current-design declaration"):
        subject._receipted_current_design_id(
            SimpleNamespace(
                casilla_id="99999",
                fields=(object(),),
                declaration_payload=SimpleNamespace(source_refs=(subject.TARGET_SOURCE_REF,)),
            ),
            frozenset({"00942", "01603", "02239", "02412"}),
        )


def test_source_rebind_refuses_a_receipted_declaration_bound_to_a_different_design() -> None:
    with pytest.raises(RegistryValidationError, match="not bound to the target design"):
        subject._receipted_current_design_id(
            SimpleNamespace(
                casilla_id="00093",
                fields=(),
                declaration_payload=SimpleNamespace(source_refs=(subject.SIBLING_SOURCE_REF,)),
            ),
            frozenset({"00093"}),
        )


def test_source_rebind_refuses_current_design_bytes_that_do_not_match_the_receipt(
    tmp_path: Path,
    reviewed_promotions,
) -> None:
    """The skipped generated row is rechecked against the same receipt at apply time."""
    casillas_root = tmp_path / "casillas"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "200", "revisions", "2024", "casillas"), casillas_root)
    path = casillas_root / "c00093.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("manual", "drifted", 1), encoding="utf-8", newline="\n")
    plan = subject.M200SourceRebindPlan(
        source_ref=subject.TARGET_SOURCE_REF,
        source_sha256=subject.TARGET_SOURCE_SHA256,
        semantic_map_source_ref=subject.TARGET_SOURCE_REF,
        semantic_map_source_sha256=subject.TARGET_SOURCE_SHA256,
        rebinds=(),
        verified_current_design_ids=subject._build_m200_source_rebind_plan(
            subject._reconcile_bundled_m200_2024(reviewed_promotions),
            reviewed_promotions,
        ).verified_current_design_ids,
        refused_orphan_ids=(),
        expected_current_ids=(),
    )
    tampered = _tree_bytes(casillas_root)

    with pytest.raises(RegistryValidationError, match="not compiler-identical"):
        subject._require_verified_current_design(plan, casillas_root)
    assert _tree_bytes(casillas_root) == tampered


def test_source_rebind_dry_run_and_apply_change_only_planned_source_lines(
    source_rebind_plan, rebind_registry_root: Path
) -> None:
    before = _tree_bytes(rebind_registry_root)
    preview = subject.apply_m200_source_rebind_plan(
        source_rebind_plan, registry_root=rebind_registry_root, dry_run=True
    )
    assert preview.dry_run
    assert preview.planned_rebind_count == 3171
    assert len(preview.changed_paths) == 965
    assert _tree_bytes(rebind_registry_root) == before

    applied = subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    assert not applied.dry_run
    assert applied.changed_paths == preview.changed_paths
    after = _tree_bytes(rebind_registry_root)
    changed = {path for path in before if before[path] != after[path]}
    assert changed == {path.relative_to(rebind_registry_root) for path in applied.changed_paths}
    for path in changed:
        _assert_only_direct_source_refs_changed(before[path], after[path])


def test_source_rebind_refuses_missing_anchor_source_drift_payload_drift_and_partial_application(
    source_rebind_plan, rebind_registry_root: Path
) -> None:
    first = source_rebind_plan.rebinds[0]
    path = rebind_registry_root / "modelos" / "200" / "revisions" / "2024" / "casillas" / f"c{first.casilla_id}.toml"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("source_refs =", "missing_refs =", 1), encoding="utf-8", newline="\n")
    missing_anchor_snapshot = _tree_bytes(rebind_registry_root)
    with pytest.raises(RegistryValidationError, match="source_refs anchors"):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    assert _tree_bytes(rebind_registry_root) == missing_anchor_snapshot

    path.write_text(original.replace("aeat-dr-200-2025", "aeat-dr-200-2099", 1), encoding="utf-8", newline="\n")
    source_drift_snapshot = _tree_bytes(rebind_registry_root)
    with pytest.raises(RegistryValidationError, match="input drifted"):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    assert _tree_bytes(rebind_registry_root) == source_drift_snapshot

    path.write_text(original.replace('number = "00001"', 'number = "99999"', 1), encoding="utf-8", newline="\n")
    payload_drift_snapshot = _tree_bytes(rebind_registry_root)
    with pytest.raises(RegistryValidationError, match="non-source payload drifted"):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    assert _tree_bytes(rebind_registry_root) == payload_drift_snapshot

    path.write_text(original.replace("aeat-dr-200-2025", "aeat-dr-200-2024", 1), encoding="utf-8", newline="\n")
    partial_snapshot = _tree_bytes(rebind_registry_root)
    with pytest.raises(RegistryValidationError, match="partially applied"):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    assert _tree_bytes(rebind_registry_root) == partial_snapshot


def test_source_rebind_refuses_duplicate_output_before_touching_the_tree(
    source_rebind_plan, rebind_registry_root: Path
) -> None:
    first = source_rebind_plan.rebinds[0]
    duplicate = replace(first, target_source_refs=(subject.TARGET_SOURCE_REF, subject.TARGET_SOURCE_REF))
    invalid = replace(source_rebind_plan, rebinds=(duplicate, *source_rebind_plan.rebinds[1:]))
    before = _tree_bytes(rebind_registry_root)
    with pytest.raises(RegistryValidationError, match="duplicates a source reference"):
        subject.apply_m200_source_rebind_plan(invalid, registry_root=rebind_registry_root)
    assert _tree_bytes(rebind_registry_root) == before


def test_source_rebind_transaction_rolls_back_after_mid_cutover_failure(
    source_rebind_plan, rebind_registry_root: Path, monkeypatch
) -> None:
    before = _tree_bytes(rebind_registry_root)
    real_replace = subject._replace_rebind_tree
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected candidate cutover failure")
        real_replace(source, destination)

    monkeypatch.setattr(subject, "_replace_rebind_tree", fail_second_replace)
    with pytest.raises(OSError, match="injected candidate"):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    assert _tree_bytes(rebind_registry_root) == before
    revision_root = rebind_registry_root / "modelos" / "200" / "revisions" / "2024"
    assert not (revision_root / subject._REBIND_JOURNAL).exists()
    assert not tuple(revision_root.glob(f"{subject._REBIND_STAGE_PREFIX}*"))
    assert not tuple(revision_root.glob(f"{subject._REBIND_BACKUP_PREFIX}*"))


def test_source_rebind_transaction_rolls_back_after_base_exception(
    source_rebind_plan, rebind_registry_root: Path, monkeypatch
) -> None:
    class InjectedInterrupt(BaseException):
        pass

    before = _tree_bytes(rebind_registry_root)
    real_replace = subject._replace_rebind_tree
    calls = 0

    def interrupt_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise InjectedInterrupt()
        real_replace(source, destination)

    monkeypatch.setattr(subject, "_replace_rebind_tree", interrupt_second_replace)
    with pytest.raises(InjectedInterrupt):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    assert _tree_bytes(rebind_registry_root) == before


def test_source_rebind_recovery_refuses_unknown_journal_state_without_touching_live_tree(
    source_rebind_plan, rebind_registry_root: Path
) -> None:
    revision_root = rebind_registry_root / "modelos" / "200" / "revisions" / "2024"
    backup = revision_root / f"{subject._REBIND_BACKUP_PREFIX}unknown"
    shutil.copytree(revision_root / "casillas", backup)
    journal = revision_root / subject._REBIND_JOURNAL
    journal.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "unknown",
                "stage": f"{subject._REBIND_STAGE_PREFIX}unknown",
                "backup": backup.name,
            }
        ),
        encoding="utf-8",
    )
    live_before = _tree_bytes(revision_root / "casillas")
    with pytest.raises(RegistryValidationError, match="invalid source rebind recovery journal"):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root, dry_run=True)
    assert _tree_bytes(revision_root / "casillas") == live_before
    assert backup.exists()
    assert journal.exists()


@pytest.mark.parametrize("state", ("unknown", ["candidate_live"]))
def test_source_rebind_recovery_refuses_malformed_journal_state_without_touching_live_tree(
    source_rebind_plan, rebind_registry_root: Path, state: object
) -> None:
    revision_root = rebind_registry_root / "modelos" / "200" / "revisions" / "2024"
    backup = revision_root / f"{subject._REBIND_BACKUP_PREFIX}malformed"
    shutil.copytree(revision_root / "casillas", backup)
    journal = revision_root / subject._REBIND_JOURNAL
    journal.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": state,
                "stage": f"{subject._REBIND_STAGE_PREFIX}malformed",
                "backup": backup.name,
            }
        ),
        encoding="utf-8",
    )
    live_before = _tree_bytes(revision_root / "casillas")
    with pytest.raises(RegistryValidationError, match="invalid source rebind recovery journal"):
        subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root, dry_run=True)
    assert _tree_bytes(revision_root / "casillas") == live_before
    assert backup.exists()
    assert journal.exists()


@pytest.mark.parametrize("state", ("intent", "backup_staged"))
def test_source_rebind_next_run_recovers_persisted_pre_candidate_journal(
    source_rebind_plan, rebind_registry_root: Path, state: str
) -> None:
    revision_root = rebind_registry_root / "modelos" / "200" / "revisions" / "2024"
    casillas = revision_root / "casillas"
    stage = revision_root / f"{subject._REBIND_STAGE_PREFIX}{state}"
    backup = revision_root / f"{subject._REBIND_BACKUP_PREFIX}{state}"
    if state == "backup_staged":
        subject._replace_rebind_tree(casillas, backup)
    else:
        shutil.copytree(casillas, stage)
        shutil.copytree(casillas, backup)
    (revision_root / subject._REBIND_JOURNAL).write_text(
        json.dumps({"schema_version": 1, "state": state, "stage": stage.name, "backup": backup.name}), encoding="utf-8"
    )
    result = subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root, dry_run=True)
    assert result.dry_run
    assert casillas.is_dir()
    assert not (revision_root / subject._REBIND_JOURNAL).exists()
    assert not stage.exists()
    assert not backup.exists()


def test_source_rebind_candidate_live_recovery_keeps_verified_candidate_and_cleans_transaction(
    source_rebind_plan, rebind_registry_root: Path
) -> None:
    revision_root = rebind_registry_root / "modelos" / "200" / "revisions" / "2024"
    casillas = revision_root / "casillas"
    original = _tree_bytes(casillas)
    backup = revision_root / f"{subject._REBIND_BACKUP_PREFIX}candidate-live"
    shutil.copytree(casillas, backup)
    subject.apply_m200_source_rebind_plan(source_rebind_plan, registry_root=rebind_registry_root)
    candidate = _tree_bytes(casillas)
    assert candidate != original
    (revision_root / subject._REBIND_JOURNAL).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "candidate_live",
                "stage": f"{subject._REBIND_STAGE_PREFIX}candidate-live",
                "backup": backup.name,
            }
        ),
        encoding="utf-8",
    )
    subject._recover_m200_source_rebind(source_rebind_plan, rebind_registry_root)
    assert _tree_bytes(casillas) == candidate
    assert not backup.exists()
    assert not (revision_root / subject._REBIND_JOURNAL).exists()


def test_source_rebind_candidate_live_recovery_rolls_back_partial_candidate(
    source_rebind_plan, rebind_registry_root: Path
) -> None:
    revision_root = rebind_registry_root / "modelos" / "200" / "revisions" / "2024"
    casillas = revision_root / "casillas"
    original = _tree_bytes(casillas)
    backup = revision_root / f"{subject._REBIND_BACKUP_PREFIX}partial-candidate"
    shutil.copytree(casillas, backup)
    first = source_rebind_plan.rebinds[0]
    path = casillas / f"c{first.casilla_id}.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(subject.SIBLING_SOURCE_REF, subject.TARGET_SOURCE_REF, 1),
        encoding="utf-8",
        newline="\n",
    )
    (revision_root / subject._REBIND_JOURNAL).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "candidate_live",
                "stage": f"{subject._REBIND_STAGE_PREFIX}partial-candidate",
                "backup": backup.name,
            }
        ),
        encoding="utf-8",
    )
    subject._recover_m200_source_rebind(source_rebind_plan, rebind_registry_root)
    assert _tree_bytes(casillas) == original
    assert not backup.exists()
    assert not (revision_root / subject._REBIND_JOURNAL).exists()


def _tree_bytes(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*.toml")}


def _assert_only_direct_source_refs_changed(before: bytes, after: bytes) -> None:
    before_lines = before.decode("utf-8").splitlines(keepends=True)
    after_lines = after.decode("utf-8").splitlines(keepends=True)
    assert len(before_lines) == len(after_lines)
    for left, right in zip(before_lines, after_lines, strict=True):
        if left.startswith("source_refs ="):
            assert left.replace(subject.SIBLING_SOURCE_REF, subject.TARGET_SOURCE_REF) == right
        else:
            assert left == right
