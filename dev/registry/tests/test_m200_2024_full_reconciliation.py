from __future__ import annotations

from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest
import rtoml

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..analysis import m200_2024_full_reconciliation as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def census():
    return subject.reconcile_bundled_m200_2024()


def test_full_reconciliation_accounts_for_every_declaration_candidate_and_target_anchor(census) -> None:
    rows = census.rows
    anchors = census.anchors

    assert len(rows) == 3329
    assert sum(row.origin == "current_declaration" for row in rows) == 3173
    assert sum(row.origin == "restoration_candidate" for row in rows) == 156
    assert len(anchors) == 6709
    assert len({anchor.anchor for anchor in anchors}) == len(anchors)
    assert len({anchor.export_field_id for anchor in anchors}) == len(anchors)
    assert sum(anchor.owner_state == "exact_planned_owner" for anchor in anchors) == 5288
    assert sum(anchor.owner_state == "zero_padding_mismatch_refused" for anchor in anchors) == 184
    assert sum(anchor.owner_state == "qualified_identity_mismatch_refused" for anchor in anchors) == 1
    assert sum(anchor.owner_state == "non_casilla" for anchor in anchors) == 1236
    assert sum(anchor.owner_state == "unknown_map_owner_refused" for anchor in anchors) == 0


def test_rebind_census_preserves_exact_map_ownership_and_withholds_identity_anomalies(census) -> None:
    current = tuple(row for row in census.rows if row.origin == "current_declaration")
    by_id = {row.casilla_id: row for row in census.rows}

    assert sum(row.source_ref_state == "mechanical_rebind" for row in current) == 3171
    assert sum(row.source_ref_state == "unmapped_no_rebind" for row in current) == 2
    assert sum(bool(row.fields) for row in current) == 3171
    assert sum(row.identity_review_required for row in current) == 15
    assert all(
        row.source_ref_state == "candidate_non_authoritative"
        for row in census.rows
        if row.origin == "restoration_candidate"
    )

    mismatched = next(anchor for anchor in census.anchors if anchor.export_field_id == "m200-2024.dp200022.f0032")
    assert mismatched.declared_map_owner == "03627"
    assert mismatched.printed_number == "00927"
    assert mismatched.owner_state == "exact_planned_owner"
    assert mismatched.printed_identity_state == "conflicts_with_declared_owner"
    assert mismatched in by_id["03627"].fields
    assert mismatched not in by_id["00927"].fields

    candidate = by_id["00093"]
    assert candidate.fields == ()
    assert candidate.proposed_fields_non_authoritative
    assert {field.declared_map_owner for field in candidate.proposed_fields_non_authoritative} == {"93"}
    assert candidate.declaration_payload is None
    assert candidate.candidate_payload_non_authoritative is not None


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
    subject._require_exact_source_identity(
        "test", subject.TARGET_SOURCE_REF, subject.TARGET_SOURCE_SHA256
    )
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
        subject._require_partition(
            SimpleNamespace(**{**vars(target), "valid_to": date(2025, 12, 31)}), sibling
        )
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
