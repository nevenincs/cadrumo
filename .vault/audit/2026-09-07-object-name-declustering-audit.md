---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:886c448c17c7a619471c2aa53712284888ebe3632b71ea931ba2bc24c99a1a9b'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `Object name declustering S32 transaction disposition implementation review`

## Scope

Reviewed the current uncommitted S32 changes in `dev/quality/object_name_replay.py`,
`dev/quality/object_name_declustering.py`, `dev/quality/tests/test_object_name_replay.py`,
and `dev/quality/tests/test_object_name_declustering.py` against the accepted
`object-name-declustering` ADR, the W04.P11 plan, the receipt-scope and teardown-authority
audit, and the S31 review. The review covered receipt-integrity validation, exact
receipt-derived root identity, recursive member-tree containment, the canonical empty
`.absent-paths` marker, byte equality of every retained backup with both the receipt
baseline and live tree, the mandatory second verification immediately before strict
removal, structured result reporting, and the `dispose` CLI boundary.

The focused detector run passed all 20 replay-disposition cases and all 4 disposal CLI
cases after the latest changes. The implementation is deliberately manifest-independent
for disposal: the CLI validates the receipt and explicit receipt ID, then dispatches
directly to the disposition API without loading rename context.

The two retained campaign roots remain correctly non-disposable in the observed live
state. Root `51d62ca4efd5668f88149559b71de8162d7536ea19b18fad74c8f0980d7a537d`, backed by
`scratch/b3a2_receipt.json`, has the exact expected member tree and an empty marker; its
backup hashes match the receipt, but live `src/cadrumo/application/workflow/run_models.py`
is `sha256:cdfd864a3cebff95483e26702b9117cb3de3560ceaf5ca38ee0ca92237c5a371` instead of
the receipt's `sha256:132f87c8ac2343607bc607bd889178567f68c51627c04378beae7a549d6a63e7`.
Root `815c231d5a505afd339d2129c289cc505b67bd4238ed8a2dd37137376a5ecc13`, backed by
`scratch/b3f_receipt.json`, likewise has an exact member tree, empty marker, and matching
backups, but live `test_file_flow_verify.py`, `run_models.py`, and
`test_cross_boundary_roundtrip.py` differ from their recorded baselines. These mismatches
must refuse before strict removal; neither root was mutated or removed during this review.

## Findings

No findings at any severity. The disposition implementation refuses before
`shutil.rmtree` for every observed non-inert condition, and its detector suite proves the
required guards independently: each receipt-integrity field, every backup/live byte pair
in a multi-path receipt, malformed and extra member shapes, link-like members, foreign
receipt-derived siblings, drift between the two inertness checks, and strict-removal
failure with evidence retention. The CLI tests prove the explicit mode/argument contract,
manifest independence, deterministic structured JSON, and successful removal only for an
inert receipt-bound root.

## Recommendations

Keep the strict distinction recorded by the accepted ADR: verified-copy cleanup is
best-effort, while retained transaction evidence is semantically meaningful and must be
removed only after a complete, repeated inertness proof. Do not dispose of the two
campaign roots until the live bytes named above are restored or their owners provide a
new reviewed disposition; rerun the receipt-bound CLI after any such change.
