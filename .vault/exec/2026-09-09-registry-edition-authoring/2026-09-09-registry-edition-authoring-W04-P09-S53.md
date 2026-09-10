---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c4ce5c3fef9f30c6800d9e55bd81410b3127e6195080d38cc2fde025d528ba2d'
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
- `A` `dev/registry/analysis/type_column_coverage.py`
- `A` `dev/registry/tests/test_type_column_coverage.py`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_type_column_coverage.py dev/registry/conformance/tests/test_stamp_delta_review_scope.py` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the four paths -> `pass`

## Notes

Ruling, stamp scope: option (a). A review stamp on an edition that names a predecessor covers the rows that edition states, judged against the named predecessor. Inherited rows are attested by the stamp of the edition that states them. Review is not redefined over the materialised edition. Under (b) every successor stamp would go stale when its predecessor changes, with nothing in the successor's file moving, and a reviewer would have to re-read inherited rows. That puts back in review the restatement the ADR removes from authoring.

The scope has to be written on the stamp. The four governance scalars have no field for it, so stating it needs a schema change: a manifest-only governance scalar naming the predecessor the review was made against, which the writer fills from the compiled record and never takes from a caller. Per the Step instruction this was not built. Until it exists, `stamp_revision` refuses any review claim on a delta edition. Returning the edition to `pending_review` and recording `engineered_by` stay writable. A migrated edition therefore cannot get a review claim through the writer.

Two gaps stay open until the schema field lands. A stamp written before migration survives it: the bundled 232/2018-y-siguientes is `agent_reviewed` today and would keep that claim if it were migrated. An operator editing a manifest by hand is not guarded either. Closing both needs a schema validator that refuses a review status beyond `pending_review` on a delta edition unless the scope scalar names the same predecessor the edition declares.

Ruling, manifest-presence blind spot: coverage is partitioned over the compiled authority. Eligibility comes from the compiled record's declared export layouts, not from files on disk. The states are `generated_manifest`, `hand_authored_layouts`, `no_export_surface` and `unchecked`, and `unchecked` carries a reason and names a delta predecessor where there is one. The existing generated-tree gate and hand-authored gate were not edited. Instead, the new gate checks that each one's real input is exactly the revisions credited to it. The shipped tree reads 32, 62 and 34 of 128, with none unchecked.
