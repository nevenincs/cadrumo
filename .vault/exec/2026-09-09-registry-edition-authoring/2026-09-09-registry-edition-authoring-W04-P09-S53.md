---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:494c0906af9f8cdcd82bcc0e6846c4b59c5ccfbed21e55d757f997f6a6040139'
step_id: 'S53'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [S | opus-medium] Rule on what a governance review stamp covers once editions inherit. The stamp writes declared scalars into the declaring file and is therefore still literally true after migration — but a reviewer signs off on a delta while the compiled edition carries inherited rows the reviewer never saw, so the stamp's SCOPE shrinks silently while its wording does not. Either the stamp states what it covers, or review is defined over the materialised edition. Silence here converts an honest attestation into a misleading one without anyone changing it. The same shape has already been confirmed once on a neighbouring gate: the type-column gate reads derivation records out of a generation manifest, so a hand-authored revision's 1,220 shipped fields are not explained, not pinned and not failing — they are invisible, and the gate covers 32 of 94 shipped revisions while reading as clean. Delta authoring produces stated rather than generated editions, so any gate keyed on manifest presence will read a migrated edition as absent rather than as unchecked. Rule on that too, or migration silently widens the blind spot. Proof: a migrated edition is distinguishable from an unreviewed one by what the stamp says, not by what a reader infers.

## Scope

- `dev/registry/conformance/_stamp.py`

## Changes

- `M` `dev/registry/conformance/_stamp.py`
- `A` `dev/registry/conformance/tests/test_stamp_delta_review_scope.py`
- `M` `dev/registry/conformance/tests/test_stamp_refusal_diagnostics.py`
- `A` `dev/registry/analysis/type_column_coverage.py`
- `A` `dev/registry/tests/test_type_column_coverage.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/_schema_governance.py`
- `M` `src/cadrumo/domain/calculations/registry/edition_materialisation.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_review_scope.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_edition_materialisation_entry_point.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_round_trip.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_governance_stamp.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_manifest_only_placement.py`
- `verify:` `aeat app registry verify` -> `pass`
- `verify:` 128 revisions dumped on one frozen HEAD package snapshot, HEAD schema vs changed schema -> 128 byte-identical
- `verify:` `pytest` review-scope, stamp, placement, governance, round-trip, materialisation and staging tests -> `pass`
- `verify:` `ruff check`, `ruff format --check`, `ty check` on every touched path -> `pass`

## Notes

Ruling, stamp scope: option (a). A review stamp on an edition that names a predecessor covers the rows that edition states, judged against the named predecessor. Inherited rows are attested by the stamp of the edition that states them. Review is not redefined over the materialised edition. Under (b) every successor stamp would go stale when its predecessor changes, with nothing in the successor's file moving, and a reviewer would have to re-read inherited rows. That puts back in review the restatement the ADR removes from authoring.

The scope is written on the stamp as `reviewed_against`, a manifest-only governance scalar naming the predecessor the review was made against. The schema requires it on a delta edition whose status is beyond `pending_review`, requires it to equal the declared predecessor, and refuses it on an unreviewed edition and on one that names no predecessor. `stamp_revision` fills it from the compiled record's predecessor whenever the resolved stamp claims a review, drops it on a return to `pending_review`, and takes no caller argument for it. A reviewed delta edition and an unreviewed one are therefore told apart by the stamp alone, and a predecessor declared or re-pointed after the review leaves a stamp that no longer loads. The shipped 232/2018-y-siguientes stamp is refused as soon as a copy of 232 declares the predecessor without re-review.

A migration that the round-trip gate proves exact may carry a reviewed edition's claim forward by stating `reviewed_against`: the full-copy review saw every row the materialised edition inherits. The gate's fixture migration now does that, and the gate excludes `reviewed_against` from equality alongside `predecessor`.

Materialising a delta edition into a full copy withdraws its review: the table states `review_status = "pending_review"`, drops the reviewer, date and scope, keeps `engineered_by`, and reports the withdrawn status on `MaterialisedEdition.withdrawn_review_status`. The claim cannot transfer, because the full copy names no predecessor and states rows the delta's reviewer never read. An edition stating every row keeps its stamp.

A stamp whose scope no longer matches cannot be repaired through the writer, because the writer must load the revision first. The repair is a manifest edit.

Ruling, manifest-presence blind spot: coverage is partitioned over the compiled authority. Eligibility comes from the compiled record's declared export layouts, not from files on disk. The states are `generated_manifest`, `hand_authored_layouts`, `no_export_surface` and `unchecked`, and `unchecked` carries a reason and names a delta predecessor where there is one. The existing generated-tree gate and hand-authored gate were not edited. Instead, the new gate checks that each one's real input is exactly the revisions credited to it. The shipped tree reads 32, 62 and 34 of 128, with none unchecked.

- The reviewer persona could not be launched. The orchestrating session reviewed the field, the schema check, the writer and the materialisation withdrawal against the ADR, and brought the ADR's stamp-scope paragraph up to date. Re-run: 99 passed across the scope, stamp, placement and staging tests; the round-trip gate passed; `registry verify` exit 0; ruff and ty clean.
